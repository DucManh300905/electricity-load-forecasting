"""Calendar features for Vietnam: weekdays, public holidays, swapped days off, make-up
working Saturdays and the distance to Lunar New Year (Tết).

Holidays come from the `holidays` package (Vietnam), which follows the Labor Code and the
government's yearly day-swap decisions. Calendar is known in advance, so the default range
runs 60 days into the future, ready for forecasting.

    python calendar_features.py
    python calendar_features.py --start 2025-01-01 --end 2026-12-31

Output: data/calendar.csv, one row per date.
"""
import argparse
import datetime as dt
from pathlib import Path

import holidays
import pandas as pd

DATA = Path(__file__).parent / "data"


def tet_dates(years):
    """Mùng 1 Tết of each year."""
    vn = holidays.Vietnam(years=years, language="en_US")
    return sorted(d for d, name in vn.items() if name == "Lunar New Year")


def build(start, end):
    years = range(start.year - 1, end.year + 2)
    vn_vi = holidays.Vietnam(years=years, language="vi")
    vn = holidays.Vietnam(years=years)
    tets = pd.to_datetime(tet_dates(years))

    df = pd.DataFrame({"date": pd.date_range(start, end)})
    d = df["date"]
    df["dow"] = d.dt.dayofweek  # 0 = Monday
    df["month"] = d.dt.month
    df["day_of_year"] = d.dt.dayofyear
    df["week_of_year"] = d.dt.isocalendar().week.astype(int)
    df["is_weekend"] = (df["dow"] >= 5).astype(int)
    df["is_holiday"] = d.dt.date.map(lambda x: int(x in vn))
    df["holiday_name"] = d.dt.date.map(lambda x: vn_vi.get(x, ""))
    df["is_makeup_workday"] = d.dt.date.map(lambda x: int(x in vn.weekend_workdays))
    df["is_day_off"] = (((df["is_weekend"] == 1) & (df["is_makeup_workday"] == 0)) | (df["is_holiday"] == 1)).astype(int)

    # Length of the block of consecutive days off this date belongs to (0 on working days),
    # e.g. 9 for every day of the 2026 Tết break.
    block = (df["is_day_off"] != df["is_day_off"].shift()).cumsum()
    df["off_block_len"] = df.groupby(block)["is_day_off"].transform("size") * df["is_day_off"]
    df["is_pre_day_off"] = ((df["is_day_off"] == 0) & (df["is_day_off"].shift(-1) == 1)).astype(int)
    df["is_post_day_off"] = ((df["is_day_off"] == 0) & (df["is_day_off"].shift(1) == 1)).astype(int)

    # Signed days to the nearest Mùng 1 Tết (negative = before Tết).
    diff = d.values[:, None] - tets.values[None, :]
    days = diff.astype("timedelta64[D]").astype(int)
    df["tet_offset"] = days[range(len(df)), abs(days).argmin(axis=1)]

    df["date"] = d.dt.strftime("%Y-%m-%d")
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2026, 1, 1))
    ap.add_argument("--end", type=dt.date.fromisoformat, default=dt.date.today() + dt.timedelta(days=60))
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    df = build(args.start, args.end)
    df.to_csv(DATA / "calendar.csv", index=False, encoding="utf-8-sig")
    print(f"{len(df)} days, {df['date'].min()} -> {df['date'].max()}")
    print(df[df["is_holiday"] == 1][["date", "dow", "holiday_name", "off_block_len"]].to_string(index=False))
    print("make-up working days:", df.loc[df["is_makeup_workday"] == 1, "date"].tolist())
