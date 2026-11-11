"""Walk-forward backtest of day-ahead models for daily Pmax and energy.

    python train.py      # tune on the validation year, then backtest the test year
                         # -> data/backtest.csv, data/backtest_metrics.csv, models/params.json

Protocol (docs/Model.md):
    train   from 2023-07-01, expanding window
    valid   11/11/2024 -> 10/11/2025   choose hyper-parameters
    test    11/11/2025 -> 10/11/2026   used once, with the chosen parameters
    Models are refit at the start of every month; a fit for days starting on date d only
    uses labels up to d-2 (what is published when the first forecast of the month is made).
"""
import json
import os
import sys
import warnings
from itertools import product
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import features as F

ROOT = Path(__file__).parent
TRAIN_START = "2023-07-01"
VALID = ("2024-11-11", "2025-11-10")
TEST = ("2025-11-11", "2026-11-10")
RIDGE_ALPHAS = [0.3, 1, 3, 10, 30, 100]
LGB_GRID = {"objective": ["l2", "l1"], "num_leaves": [7, 15], "min_child_samples": [10, 20], "n_estimators": [300, 600]}
QUANTILES = (0.1, 0.9)

warnings.filterwarnings("ignore", category=UserWarning)
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")  # silences joblib's CPU-count probe on Windows
CANDIDATES = ("ridge", "lightgbm", "ensemble")  # final model = best of these on the validation year


def ridge_model(alpha):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=alpha))


def lgb_model(**p):
    return lgb.LGBMRegressor(learning_rate=0.03, subsample=0.9, subsample_freq=1, colsample_bytree=0.9,
                             random_state=0, verbose=-1, **p)


def walk_forward(X, info, start, end, make, design=None):
    """Monthly refit; returns predicted ratio for days in [start, end]."""
    Z = design(X) if design else X
    ok = info["y"].notna() & info["base"].notna()
    days = info.loc[start:end].index
    pred = pd.Series(np.nan, index=days)
    for month_start in pd.date_range(pd.Timestamp(start).replace(day=1), end, freq="MS"):
        block = days[(days >= max(month_start, pd.Timestamp(start))) & (days < month_start + pd.offsets.MonthBegin(1))]
        if not len(block):
            continue
        cutoff = block[0] - pd.Timedelta(days=F.MIN_LAG)
        tr = ok & (Z.index >= TRAIN_START) & (Z.index <= cutoff)
        model = make().fit(Z[tr], info.loc[tr, "ratio"])
        has_base = info.loc[block, "base"].notna()
        pred[block[has_base]] = model.predict(Z.loc[block[has_base]])
    return pred


def baselines(info):
    y = info["y"]
    return {
        "lag2": y.shift(2),
        "lag7": y.shift(7),
        "mean_lag7_28": pd.concat([y.shift(k) for k in (7, 14, 21, 28)], axis=1).mean(axis=1, skipna=False),
        "clean_base": info["base"],
    }


def mape(y, p):
    m = y.notna() & p.notna()
    return float((np.abs(p[m] - y[m]) / y[m]).mean() * 100)


def segments(info):
    hot_cut = info["fc_tmax_vn"].quantile(0.9)
    return {"tất cả": pd.Series(True, index=info.index), "ngày thường": ~info["special"],
            "lễ/Tết": info["special"], "nắng nóng (top 10% Tmax)": info["fc_tmax_vn"] >= hot_cut}


def metrics(info, preds):
    """Every model is scored on the same days: those where the actual and all forecasts exist."""
    rows = []
    segs = segments(info)
    common = info["y"].notna() & pd.concat(preds, axis=1).notna().all(axis=1)
    for name, p in preds.items():
        for seg, mask in segs.items():
            m = common & mask
            y, q = info["y"][m], p[m]
            err = q - y
            rows.append({"model": name, "segment": seg, "n": int(m.sum()), "MAPE": mape(y, q),
                         "MAE": float(err.abs().mean()), "RMSE": float(np.sqrt((err ** 2).mean()))})
    return pd.DataFrame(rows)


def dm_test(y, p1, p2, h=2):
    """Diebold-Mariano on absolute percentage errors, Harvey et al. (1997) small-sample correction.
    Negative statistic = p1 more accurate than p2."""
    m = y.notna() & p1.notna() & p2.notna()
    d = (np.abs(p1[m] - y[m]) - np.abs(p2[m] - y[m])) / y[m]
    n = len(d)
    dc = d - d.mean()
    lrv = (dc ** 2).mean() + 2 * sum((1 - k / h) * (dc[k:].values * dc[:-k].values).mean() for k in range(1, h))
    dm = d.mean() / np.sqrt(lrv / n)
    dm *= np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    return float(dm), float(2 * stats.t.sf(abs(dm), df=n - 1)), n


def tune(X, info):
    """Pick Ridge alpha and LightGBM parameters by MAPE on the validation year."""
    y = info["y"].loc[VALID[0]:VALID[1]]
    base = info["base"].loc[VALID[0]:VALID[1]]
    r_preds = {a: walk_forward(X, info, *VALID, lambda a=a: ridge_model(a), F.ridge_design) * base for a in RIDGE_ALPHAS}
    grid = [dict(zip(LGB_GRID, v)) for v in product(*LGB_GRID.values())]
    g_preds = [walk_forward(X, info, *VALID, lambda p=p: lgb_model(**p)) * base for p in grid]
    a = min(r_preds, key=lambda k: mape(y, r_preds[k]))
    i = int(np.argmin([mape(y, p) for p in g_preds]))
    valid = {"clean_base": mape(y, base), "ridge": mape(y, r_preds[a]), "lightgbm": mape(y, g_preds[i]),
             "ensemble": mape(y, (r_preds[a] + g_preds[i]) / 2)}
    return {"ridge_alpha": a, "lgb": grid[i], "valid_mape": valid, "final": min(CANDIDATES, key=valid.get)}


def run_target(target, df, params=None):
    X, info = F.build(target, df)
    params = params or tune(X, info)
    lo, hi = TEST
    ridge = walk_forward(X, info, lo, hi, lambda: ridge_model(params["ridge_alpha"]), F.ridge_design)
    gbm = walk_forward(X, info, lo, hi, lambda: lgb_model(**params["lgb"]))
    qp = {k: v for k, v in params["lgb"].items() if k != "objective"}
    q = {a: walk_forward(X, info, lo, hi, lambda a=a: lgb_model(objective="quantile", alpha=a, **qp)) for a in QUANTILES}

    t = info.loc[lo:hi]
    preds = {k: v.loc[lo:hi] for k, v in baselines(info).items()}
    preds["ridge"] = ridge * t["base"]
    preds["lightgbm"] = gbm * t["base"]
    preds["ensemble"] = (preds["ridge"] + preds["lightgbm"]) / 2
    out = pd.DataFrame({"target": target, "y": t["y"], "base": t["base"], "special": t["special"],
                        "fc_tmax_vn": t["fc_tmax_vn"], "tet_offset": t["tet_offset"], **preds,
                        "lgb_p10": q[0.1] * t["base"], "lgb_p90": q[0.9] * t["base"]})
    return out, metrics(t, preds), params


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    df = F.load()
    frames, mets, params, dm_rows = [], [], {}, []
    for target in F.TARGETS:
        print(f"== {target}: tuning on {VALID[0]} -> {VALID[1]}")
        out, met, p = run_target(target, df)
        print(f"   chosen: ridge alpha={p['ridge_alpha']}, lgb={p['lgb']}")
        print(f"   valid MAPE: {({k: round(v, 2) for k, v in p['valid_mape'].items()})} -> final model: {p['final']}")
        frames.append(out)
        mets.append(met.assign(target=target))
        params[target] = p
        # same days as the metrics table: actual and every forecast available
        common = out[["y", "lag2", "lag7", "mean_lag7_28", "clean_base", *CANDIDATES]].notna().all(axis=1)
        for model in CANDIDATES:
            for ref in ("mean_lag7_28", "clean_base"):
                stat, pval, n = dm_test(out["y"][common], out[model][common], out[ref][common])
                dm_rows.append({"target": target, "model": model, "vs": ref, "DM": stat, "p_value": pval, "n": n})
    bt = pd.concat(frames).rename_axis("date").reset_index()
    bt.to_csv(ROOT / "data" / "backtest.csv", index=False, encoding="utf-8-sig")
    met = pd.concat(mets)
    met.to_csv(ROOT / "data" / "backtest_metrics.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(dm_rows).to_csv(ROOT / "data" / "backtest_dm.csv", index=False, encoding="utf-8-sig")
    (ROOT / "models").mkdir(exist_ok=True)
    (ROOT / "models" / "params.json").write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")
    print(met.pivot_table(index=["target", "model"], columns="segment", values="MAPE").round(2).to_string())
    print(pd.DataFrame(dm_rows).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
