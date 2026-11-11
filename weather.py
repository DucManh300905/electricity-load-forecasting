"""Daily weather for the three regional load centres, from Open-Meteo (free, no API key).

Two versions of every variable:
    obs_*  observed / reanalysis   (Archive API)        -> for analysis
    fc_*   forecast issued the day before (Previous Runs API, *_previous_day1)
                                                        -> what a real day-ahead model would have seen

    python weather.py                                   # 01/01/2026 -> yesterday
    python weather.py --start 2025-01-01 --end 2025-12-31

Output: data/weather.csv, one row per date. Columns <src>_<var>_<city>, plus <src>_<var>_vn,
the load-weighted national average (weights in REGION_WEIGHTS).
"""
import argparse
import datetime as dt
import time
from pathlib import Path

import pandas as pd
import requests

DATA = Path(__file__).parent / "data"
TZ = "Asia/Ho_Chi_Minh"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"

CITIES = {  # code: (name, lat, lon)
    "hn": ("Hà Nội", 21.0285, 105.8542),
    "dn": ("Đà Nẵng", 16.0544, 108.2022),
    "hcm": ("TP.HCM", 10.8231, 106.6297),
}
# Approximate share of national load by region (North / Central / South). An assumption,
# not an official figure: replace with EVN/NSMO numbers when available.
REGION_WEIGHTS = {"hn": 0.45, "dn": 0.10, "hcm": 0.45}

# short name: Open-Meteo daily variable (Archive API)
DAILY_VARS = {
    "tmax": "temperature_2m_max",
    "tmin": "temperature_2m_min",
    "tmean": "temperature_2m_mean",
    "app_tmax": "apparent_temperature_max",
    "rh": "relative_humidity_2m_mean",
    "rad": "shortwave_radiation_sum",
    "cloud": "cloud_cover_mean",
    "precip": "precipitation_sum",
}
# hourly variables of the Previous Runs API, aggregated to the same daily variables
HOURLY_VARS = ["temperature_2m", "apparent_temperature", "relative_humidity_2m",
               "shortwave_radiation", "cloud_cover", "precipitation"]


def get_json(url, params):
    for attempt in range(5):
        try:
            r = requests.get(url, params=params, timeout=120)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            wait = 5 * (attempt + 1)
            print(f"  ! {e} -> retry in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"failed: {url}")


def fetch_observed(lat, lon, start, end):
    j = get_json(ARCHIVE_URL, dict(latitude=lat, longitude=lon, start_date=start, end_date=end,
                                   daily=",".join(DAILY_VARS.values()), timezone=TZ))
    df = pd.DataFrame(j["daily"]).rename(columns={v: k for k, v in DAILY_VARS.items()})
    return df.rename(columns={"time": "date"})


def fetch_forecast(lat, lon, start, end):
    hourly = [f"{v}_previous_day1" for v in HOURLY_VARS]
    j = get_json(PREVIOUS_RUNS_URL, dict(latitude=lat, longitude=lon, start_date=start, end_date=end,
                                         hourly=",".join(hourly), timezone=TZ))
    h = pd.DataFrame(j["hourly"])
    h.columns = [c.removesuffix("_previous_day1") for c in h.columns]
    h["date"] = h["time"].str[:10]
    g = h.groupby("date")
    df = pd.DataFrame({
        "tmax": g["temperature_2m"].max(),
        "tmin": g["temperature_2m"].min(),
        "tmean": g["temperature_2m"].mean(),
        "app_tmax": g["apparent_temperature"].max(),
        "rh": g["relative_humidity_2m"].mean(),
        "rad": g["shortwave_radiation"].sum(min_count=1) * 3600 / 1e6,  # W/m² hourly -> MJ/m²/day
        "cloud": g["cloud_cover"].mean(),
        "precip": g["precipitation"].sum(min_count=1),
    })
    return df.round(2).reset_index()


def main(start, end):
    frames = []
    for code, (name, lat, lon) in CITIES.items():
        for src, fetch in (("obs", fetch_observed), ("fc", fetch_forecast)):
            print(f"{name}: {src}")
            df = fetch(lat, lon, start, end).set_index("date")
            frames.append(df.add_prefix(f"{src}_").add_suffix(f"_{code}"))
    out = pd.concat(frames, axis=1).sort_index()

    for src in ("obs", "fc"):
        for var in DAILY_VARS:
            cols = {code: f"{src}_{var}_{code}" for code in CITIES}
            out[f"{src}_{var}_vn"] = sum(out[c] * REGION_WEIGHTS[code] for code, c in cols.items()).round(2)

    out = out.reset_index()
    out.to_csv(DATA / "weather.csv", index=False, encoding="utf-8-sig")
    print(f"{len(out)} days, {out['date'].min()} -> {out['date'].max()}, {out.shape[1] - 1} columns")
    nulls = out.isna().sum()
    print("columns with gaps:", nulls[nulls > 0].to_dict() or "none")
    for code in list(CITIES) + ["vn"]:
        err = (out[f"fc_tmax_{code}"] - out[f"obs_tmax_{code}"]).abs().mean()
        print(f"  MAE forecast vs observed Tmax [{code}]: {err:.2f} °C")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-01-01", help="YYYY-MM-DD")
    ap.add_argument("--end", default=(dt.date.today() - dt.timedelta(days=1)).isoformat(), help="YYYY-MM-DD")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    main(args.start, args.end)
