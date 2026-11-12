"""Pure SARIMA benchmark for daily Pmax (no calendar, no weather): comparison model only.

    python sarima.py     # stationarity tests, order selection on the validation year,
                         # walk-forward backtest on the test year
                         # -> data/sarima_backtest.csv, data/sarima_metrics.csv, data/sarima_dm.csv,
                         #    data/sarima_validation.csv, models/sarima_params.json

Same protocol as train.py: train from 2023-07-01, refit at the start of each month, a fit
used from day d onwards only sees data up to d-2, forecasts are 2 steps ahead, scored on the
same days as the main models.

2-step forecasts for every day come from the Kalman filter of the month's fitted model:
    y_hat(t | t-2) = Z T^2 a(t-2|t-2),   Var = Z [T (T P T' + RQR') T' + RQR'] Z' + H
which equals statsmodels' get_forecast(2) from origin t-2 (checked), without refitting per day.
"""
import json
import sys
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.statespace.sarimax import SARIMAX

import features as F
import train as T

ROOT = Path(__file__).parent
TARGET = "pmax_mw"
S = 7                       # weekly season
SD_ORDER = 1                # seasonal differencing
# d in {0, 1}: ADF with trend and KPSS say the series is trend-stationary, so d = 0 is a
# candidate. A first run fixed d = 1 (kept in data/sarima_run1/): its MA(1) came out at
# -0.999, the usual sign of over-differencing. Both are now compared on the validation year.
GRID = {"p": [0, 1, 2], "d": [0, 1], "q": [0, 1, 2], "P": [0, 1], "Q": [0, 1]}
Z80 = 1.2816                # 80% interval: P10-P90, same coverage target as the LightGBM quantiles

warnings.filterwarnings("ignore")


def load_series():
    """Daily Pmax on a full calendar from TRAIN_START; copy-paste errors (qc flag) set to NaN."""
    df = F.load()  # already blanks qc_same_as_adjacent days
    return df[TARGET].loc[T.TRAIN_START:].asfreq("D")


def stationarity(y):
    """ADF (H0: unit root) and KPSS (H0: stationary) on the level and differenced series."""
    tests = [
        ("y (gốc)", y, "c"), ("y (gốc)", y, "ct"),
        ("Δy (sai phân bậc 1)", y.diff(), "c"),
        ("Δ₇y (sai phân mùa)", y.diff(S), "c"),
        ("Δ Δ₇y (cả hai)", y.diff(S).diff(), "c"),
    ]
    rows = []
    for name, s, reg in tests:
        s = s.dropna()
        stat, p, lags, n, crit, _ = adfuller(s, regression=reg, autolag="AIC")
        k_stat, k_p, *_ = kpss(s, regression=reg, nlags="auto")
        rows.append({"chuỗi": name, "thành phần tất định": {"c": "hằng số", "ct": "hằng số + xu hướng"}[reg],
                     "ADF": stat, "ADF p": p, "KPSS": k_stat, "KPSS p": k_p, "n": n})
    return pd.DataFrame(rows)


def fit(y, order, sorder):
    return SARIMAX(y, order=order, seasonal_order=sorder).fit(disp=False, maxiter=200)


def two_step(res, y_until):
    """Apply fitted params to y_until; return 2-step-ahead mean and sd for every date in y_until + 2."""
    full = res.apply(y_until)
    ssm = full.model.ssm
    Tm, Zm, Rm = ssm["transition"], ssm["design"], ssm["selection"]
    RQR = Rm @ ssm["state_cov"] @ Rm.T
    H = ssm["obs_cov"][0, 0]
    a, P = full.filtered_state, full.filtered_state_cov
    TT = Tm @ Tm
    mean = (Zm @ TT @ a)[0]
    var = np.array([(Zm @ (Tm @ (Tm @ P[:, :, i] @ Tm.T + RQR) @ Tm.T + RQR) @ Zm.T)[0, 0] + H
                    for i in range(a.shape[1])])
    target_days = y_until.index + pd.Timedelta(days=2)
    return pd.Series(mean, index=target_days), pd.Series(np.sqrt(var), index=target_days)


def walk_forward(y, order, start, end):
    """order = (p, d, q, P, D, Q). Monthly refit; forecast for day t uses data up to t-2.
    Returns mean, sd and a per-month fit log."""
    order, sorder = order[:3], (*order[3:], S)
    days = pd.date_range(start, end)
    mean, sd, log = pd.Series(np.nan, index=days), pd.Series(np.nan, index=days), []
    for month in pd.date_range(pd.Timestamp(start).replace(day=1), end, freq="MS"):
        block = days[(days >= month) & (days < month + pd.offsets.MonthBegin(1))]
        if not len(block):
            continue
        cutoff = block[0] - pd.Timedelta(days=F.MIN_LAG)
        try:
            res = fit(y[:cutoff], order, sorder)
        except Exception as e:  # noqa: BLE001 - a failed fit leaves the month empty, logged
            log.append({"month": month.date(), "ok": False, "error": str(e)[:80]})
            continue
        m, s = two_step(res, y[: block[-1] - pd.Timedelta(days=F.MIN_LAG)])
        mean[block], sd[block] = m.reindex(block), s.reindex(block)
        log.append({"month": month.date(), "ok": True, "converged": bool(res.mle_retvals.get("converged", True)),
                    "aic": res.aic, "n_train": int(y[:cutoff].notna().sum())})
    return mean, sd, pd.DataFrame(log)


def tune(y):
    """Grid over (p,d,q,P,Q) with D=1, scored by MAPE on the validation year."""
    yv = y.loc[T.VALID[0]:T.VALID[1]]
    rows = []
    for p, d, q, P, Q in product(*GRID.values()):
        order = (p, d, q, P, SD_ORDER, Q)
        m, _, log = walk_forward(y, order, *T.VALID)
        ok = log[log["ok"]]
        rows.append({"p": p, "d": d, "q": q, "P": P, "D": SD_ORDER, "Q": Q, "MAPE_valid": T.mape(yv, m),
                     "mean_aic": ok["aic"].mean() if len(ok) else np.nan,
                     "months_failed": int((~log["ok"]).sum()),
                     "months_not_converged": int((ok["converged"] == False).sum()) if len(ok) else 0})  # noqa: E712
        print(f"  SARIMA({p},{d},{q})({P},1,{Q})7  valid MAPE {rows[-1]['MAPE_valid']:.3f}")
    return pd.DataFrame(rows).sort_values("MAPE_valid").reset_index(drop=True)


def post_special(info):
    """Days since the last holiday/Tết day (1..7) for non-special days, else NaN."""
    sp = info["special"].astype(bool)
    last = pd.Series(np.where(sp, np.arange(len(sp)), np.nan), index=sp.index).ffill()
    k = pd.Series(np.arange(len(sp)), index=sp.index) - last
    return k.where(~sp & (k <= 7))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    y = load_series()
    print("== ADF")
    adf = stationarity(y)
    print(adf.round(4).to_string(index=False))

    print(f"== tuning on {T.VALID[0]} -> {T.VALID[1]} ({np.prod([len(v) for v in GRID.values()])} configurations)")
    val = tune(y)
    best = val.iloc[0]
    order = tuple(int(best[k]) for k in ("p", "d", "q", "P", "D", "Q"))
    print("chosen:", order, f"valid MAPE {best['MAPE_valid']:.3f}")

    print(f"== test {T.TEST[0]} -> {T.TEST[1]}")
    mean, sd, log = walk_forward(y, order, *T.TEST)
    X, info = F.build(TARGET)
    t = info.loc[T.TEST[0]:T.TEST[1]]
    bt = pd.read_csv(ROOT / "data" / "backtest.csv", parse_dates=["date"])
    bt = bt[bt["target"] == TARGET].set_index("date")
    preds = {k: v.loc[t.index] for k, v in T.baselines(info).items()}
    final_main = json.loads((ROOT / "models" / "params.json").read_text(encoding="utf-8"))[TARGET]["final"]
    preds["ensemble (mô hình chính)"] = bt[final_main].reindex(t.index)
    preds["sarima"] = mean
    met = T.metrics(t, preds)

    common = t["y"].notna() & pd.concat(preds, axis=1).notna().all(axis=1)
    dm = []
    for ref in ("lag2", "lag7", "mean_lag7_28", "clean_base", "ensemble (mô hình chính)"):
        stat, p, n = T.dm_test(t["y"][common], preds["sarima"][common], preds[ref][common])
        dm.append({"sarima vs": ref, "DM": stat, "p_value": p, "n": n})
    dm = pd.DataFrame(dm)

    out = pd.DataFrame({"y": t["y"], "sarima": mean, "sarima_sd": sd,
                        "sarima_p10": mean - Z80 * sd, "sarima_p90": mean + Z80 * sd,
                        "special": t["special"], "tet_offset": t["tet_offset"],
                        "days_after_special": post_special(info).loc[t.index], "common": common,
                        **{k: v for k, v in preds.items() if k != "sarima"}}).rename_axis("date")
    out.to_csv(ROOT / "data" / "sarima_backtest.csv", encoding="utf-8-sig")
    met.to_csv(ROOT / "data" / "sarima_metrics.csv", index=False, encoding="utf-8-sig")
    dm.to_csv(ROOT / "data" / "sarima_dm.csv", index=False, encoding="utf-8-sig")
    val.to_csv(ROOT / "data" / "sarima_validation.csv", index=False, encoding="utf-8-sig")

    # final model on everything up to the end of the test year, for the parameter table and diagnostics
    res = fit(y[: T.TEST[1]], order[:3], (*order[3:], S))
    lb = acorr_ljungbox(res.resid[S + 1:].dropna(), lags=[7, 14], return_df=True)
    params = {"order": order[:3], "seasonal_order": [*order[3:], S], "valid_mape": float(best["MAPE_valid"]),
              "test_fit_log": log.astype(str).to_dict(orient="records"),
              "final_fit": {"through": T.TEST[1], "params": res.params.round(6).to_dict(), "aic": res.aic,
                            "bic": res.bic, "ljung_box": lb.round(6).to_dict(orient="index"),
                            "bse": res.bse.round(6).to_dict()},
              "adf": adf.round(6).to_dict(orient="records")}
    (ROOT / "models" / "sarima_params.json").write_text(json.dumps(params, indent=2, ensure_ascii=False, default=str),
                                                        encoding="utf-8")
    print(met.pivot_table(index="model", columns="segment", values="MAPE").round(2).to_string())
    print(dm.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
