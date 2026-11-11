"""Parse cached EVN posts (data/raw_html/*.html) into one row per operating day.

    python parser.py   ->  data/evn_daily.csv, data/parse_issues.csv

Column naming:
    pmax_mw, pmax_time, energy_mkwh           headline figures (rooftop solar = "ước tính thương phẩm",
                                              or the only figure in older posts)
    pmax_mw_dc, pmax_time_dc, energy_mkwh_dc  same, with rooftop solar "ước tính đầu cực" (newer posts only)
    e_<source>                                daily energy by source, million kWh
    noon_<source>, eve_<source>               dispatched MW at midday low / evening peak (table)
"""
import csv
import re
import unicodedata
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

DATA = Path(__file__).parent / "data"
RAW = DATA / "raw_html"

NUM = r"(\d[\d.,]*)"


def norm(s):
    s = unicodedata.normalize("NFC", s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def to_float(s):
    s = s.strip().rstrip(".,")
    if not s:
        return None
    if "," in s and "." in s:  # 50.018,6
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:  # 50018,6
        s = s.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):  # 50.018
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def to_time(s):
    m = re.search(r"(\d{1,2})\s*(?:h|:|giờ)\s*(\d{1,2})?", s or "", re.I)
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}"


def source_key(label):
    """Map a Vietnamese source label to a short column key (None = not a source row)."""
    t = label.lower()
    dc = "đầu cực" in t
    if "toàn quốc" in t or "quốc gia" in t or "tổng" in t:
        return "total_dc" if dc else "total"
    if "mái nhà" in t:
        return "rooftop_dc" if dc else "rooftop"
    if "thủy điện" in t or "thuỷ điện" in t:
        return "hydro"
    if "than" in t:
        return "coal"
    if "tuabin khí" in t or "tua bin khí" in t:
        if "chạy gas" in t:
            return "gas_gasfuel"
        if "chạy dầu" in t:
            return "gas_oilfuel"
        return "gas"
    if "điện dầu" in t:
        return "oil"
    if "gió" in t:
        return "wind"
    if "trang trại" in t:
        return "solar_farm"
    if "mặt trời" in t or "đmt" in t:
        return "solar_total"
    if "nhập khẩu" in t:
        return "import"
    if "khác" in t:
        return "other"
    return None


def parse_date(text):
    m = re.search(r"ngày\s*(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})", text, re.I)
    if m:
        d, mo, y = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def parse_headline(text, row):
    """Pmax + daily energy. Newer posts give them twice (thương phẩm, then đầu cực)."""
    pmax = list(re.finditer(r"Công suất lớn nhất trong ngày\s*:?\s*" + NUM + r"\s*MW\s*(\([^)]*\))?", text, re.I))
    energy = list(re.finditer(r"Sản lượng (?:điện )?[^:]{0,40}?:\s*" + NUM + r"\s*triệu kWh", text, re.I))

    def suffix(m):
        before = text[: m.start()]
        i = before.lower().rfind("tính với số liệu")
        return "_dc" if i >= 0 and "đầu cực" in before[i:].lower() else ""

    for m in pmax:
        sfx = suffix(m)
        row.setdefault("pmax_mw" + sfx, to_float(m.group(1)))
        row.setdefault("pmax_time" + sfx, to_time(m.group(2)))
    for m in energy:
        row.setdefault("energy_mkwh" + suffix(m), to_float(m.group(1)))


def parse_energy_mix(text, row):
    start = text.lower().find("cơ cấu sản lượng")
    if start < 0:
        return
    end = text.upper().find("CÔNG SUẤT HUY ĐỘNG", start)
    seg = text[start : end if end > 0 else None]
    # "triệu k" too: some posts truncate the unit (e.g. 04/08/2026)
    for m in re.finditer(r"[-*•]\s*([^\d\-*•]+?)\s*:?\s*" + NUM + r"\s*triệu k", seg):
        key = source_key(m.group(1))
        if key:
            row.setdefault("e_" + key, to_float(m.group(2)))


def parse_table(soup, row):
    for table in soup.find_all("table"):
        rows = [[norm(td.get_text(" ")) for td in tr.find_all(["td", "th"])] for tr in table.find_all("tr")]
        rows = [r for r in rows if any(r)]
        found = False
        for cells in rows:
            if len(cells) < 3:
                continue
            key = source_key(cells[0])
            vals = [to_float(c) for c in cells[1:3]]
            if key and any(v is not None for v in vals):
                found = True
                row.setdefault("noon_" + key, vals[0])
                row.setdefault("eve_" + key, vals[1])
            elif not found and ("trưa" in " ".join(cells).lower()):
                row.setdefault("noon_label", cells[-2])
                row.setdefault("eve_label", cells[-1])
        if found:
            return


def parse_file(path, titles):
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
    body = soup.select_one("div.chitiettinbai") or soup.body
    text = norm(body.get_text(" "))
    aid = path.stem
    title = titles.get(aid) or norm(soup.title.get_text() if soup.title else "")
    row = {"article_id": int(aid), "title": title}
    row["date"] = parse_date(title) or parse_date(text)
    m = re.search(r"(\d{2}/\d{2}/\d{4}) - (\d{2}:\d{2}) \(GMT\+7\)", text)
    row["published"] = f"{m.group(1)} {m.group(2)}" if m else None
    parse_headline(text, row)
    parse_energy_mix(text, row)
    parse_table(body, row)
    return row


FIRST = ["date", "pmax_mw", "pmax_time", "energy_mkwh", "pmax_mw_dc", "pmax_time_dc", "energy_mkwh_dc"]


def main():
    titles = {}
    if (DATA / "links.csv").exists():
        with (DATA / "links.csv").open(encoding="utf-8") as f:
            titles = {r["article_id"]: r["title"] for r in csv.DictReader(f)}
    rows = [parse_file(p, titles) for p in sorted(RAW.glob("*.html"))]
    df = pd.DataFrame(rows)

    # Problems worth a look: no date, no Pmax/energy, or the same day posted twice.
    issues = df[df["date"].isna() | df["pmax_mw"].isna() | df["energy_mkwh"].isna()]
    dup = df[df["date"].notna() & df.duplicated("date", keep=False)]
    pd.concat([issues.assign(issue="missing"), dup.assign(issue="duplicate_date")])[
        ["article_id", "date", "title", "issue"]
    ].to_csv(DATA / "parse_issues.csv", index=False, encoding="utf-8-sig")

    # Keep the latest post per day (corrections are re-posted with a higher id).
    df = df.dropna(subset=["date"]).sort_values("article_id").drop_duplicates("date", keep="last")
    df = df.sort_values("date")
    cols = FIRST + sorted(c for c in df.columns if c.startswith("e_"))
    cols += sorted(c for c in df.columns if c.startswith(("noon_", "eve_")))
    cols += ["article_id", "published", "title"]
    df = df.reindex(columns=[c for c in cols if c in df.columns])
    df.to_csv(DATA / "evn_daily.csv", index=False, encoding="utf-8-sig")

    full = pd.date_range(df["date"].min(), df["date"].max())
    missing = full.difference(pd.to_datetime(df["date"]))
    print(f"{len(df)} days, {df['date'].min()} -> {df['date'].max()}, {len(missing)} calendar days missing")
    print(f"{len(issues)} posts with missing fields, {dup['date'].nunique()} duplicated dates -> parse_issues.csv")
    print("non-null share per column:")
    print(df.notna().mean().round(3).to_string())


if __name__ == "__main__":
    main()
