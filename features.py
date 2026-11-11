"""Feature table for day-ahead forecasting of daily Pmax and energy.

Forecast for day t is made on day t-1, when EVN has published days up to t-2, so every
EVN-derived feature uses lag >= 2. Calendar and the day-ahead weather forecast (fc_*) of
day t are known in advance.

The model target is a ratio to a "clean" seasonal baseline, to cope with the ~7.5%/year
growth that tree models cannot extrapolate:

    base(t)  = mean of the 4 most recent same-weekday days t-7k (k = 1..8) that are
               not holidays / Tết and have data
    ratio(t) = y(t) / base(t)          ->  forecast = predicted ratio * base(t)

    from features import build
    X, info = build("pmax_mw")
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).parent / "data"
TARGETS = ["pmax_mw", "energy_mkwh"]
REGIONS = ["hn", "dn", "hcm"]
HOT = 30.0           # °C, load rises above this Tmax (EDA, question 4)
TET_WINDOW = (-10, 15)
MIN_LAG = 2          # newest EVN day known when forecasting


def load():
    """Daily frame on a complete calendar; EVN figures flagged as copy-paste errors set to NaN."""
    evn = pd.read_csv(DATA / "evn_daily.csv", parse_dates=["date"])
    wx = pd.read_csv(DATA / "weather.csv", parse_dates=["date"])
    cal = pd.read_csv(DATA / "calendar.csv", parse_dates=["date"])
    days = pd.DataFrame({"date": pd.date_range(evn["date"].min(), wx["date"].max())})
    df = days.merge(evn, how="left").merge(wx, how="left").merge(cal, how="left").set_index("date")
    bad = df["qc_same_as_adjacent"] == 1
    df.loc[bad, TARGETS] = np.nan
    df["special"] = (df["is_holiday"] == 1) | df["tet_offset"].between(-10, 10)
    # fc_ temperatures miss 21 days (30/12/2023-19/01/2024): fill those past rows with observed values
    for r in REGIONS:
        for v in ("tmax", "tmean"):
            df[f"fc_{v}_{r}"] = df[f"fc_{v}_{r}"].fillna(df[f"obs_{v}_{r}"])
    return df


def ref_mean(s, special, n=4, max_weeks=8, min_count=1):
    """Mean of s over the n most recent same-weekday days t-7k (k <= max_weeks) that are
    not special and have a value. Used for the baseline and for reference-day weather."""
    lags = [s.shift(7 * k).where(~special.shift(7 * k, fill_value=True)) for k in range(1, max_weeks + 1)]
    stack = np.column_stack([x.values for x in lags])
    out = np.full(len(s), np.nan)
    for i, row in enumerate(stack):
        vals = row[~np.isnan(row)][:n]
        if len(vals) >= min_count:
            out[i] = vals.mean()
    return pd.Series(out, index=s.index)


def clean_base(y, special):
    return ref_mean(y, special, min_count=2)


def build(target, df=None):
    """Returns X (features, one row per target day) and info (y, base, ratio, special)."""
    df = load() if df is None else df
    y = df[target]
    special = df["special"]
    base = clean_base(y, special)
    ratio = y / base

    X = pd.DataFrame(index=df.index)
    # calendar of the target day
    X["dow"] = df["dow"]
    X["is_holiday"] = df["is_holiday"]
    X["off_block_len"] = df["off_block_len"]
    X["is_pre_day_off"] = df["is_pre_day_off"]
    X["is_post_day_off"] = df["is_post_day_off"]
    X["is_makeup_workday"] = df["is_makeup_workday"]
    tet = df["tet_offset"]
    X["tet_offset"] = tet.where(tet.between(*TET_WINDOW), 99)  # 99 = outside the Tết window
    doy = df["day_of_year"]
    X["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    X["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)

    # recent deviation from baseline, normal days only, lag >= 2
    r_norm = ratio.where(~special)
    X["ratio_lag2"] = r_norm.shift(MIN_LAG)
    X["ratio_mean_2_8"] = r_norm.shift(MIN_LAG).rolling(7, min_periods=3).mean()
    X["base_growth_4w"] = base / base.shift(28) - 1

    # day-ahead temperature forecast, and change versus the baseline's reference days
    for r in REGIONS:
        tmax = df[f"fc_tmax_{r}"]
        X[f"fc_tmax_{r}"] = tmax
        X[f"fc_tmean_{r}"] = df[f"fc_tmean_{r}"]
        X[f"hot_{r}"] = (tmax - HOT).clip(lower=0)
        obs = df[f"obs_tmax_{r}"]
        X[f"dtmax_{r}"] = tmax - ref_mean(obs, special)
        X[f"dhot_{r}"] = X[f"hot_{r}"] - ref_mean((obs - HOT).clip(lower=0), special)

    info = pd.DataFrame({"y": y, "base": base, "ratio": ratio, "special": special,
                         "fc_tmax_vn": df["fc_tmax_vn"], "tet_offset": tet, "is_holiday": df["is_holiday"]})
    return X, info


def ridge_design(X):
    """Linear-model version: one-hot weekday and Tết-period bins, drop tree-only encodings."""
    Z = X.drop(columns=["dow", "tet_offset"]).copy()
    for d in range(1, 7):
        Z[f"dow_{d}"] = (X["dow"] == d).astype(float)
    bins = [(-10, -8), (-7, -4), (-3, -1), (0, 3), (4, 6), (7, 10), (11, 15)]
    for a, b in bins:
        Z[f"tet_{a}_{b}"] = X["tet_offset"].between(a, b).astype(float)
    for d in (5, 6):  # holidays hit weekdays harder than weekends
        Z[f"holiday_x_dow{d}"] = Z["is_holiday"] * Z[f"dow_{d}"]
    return Z
