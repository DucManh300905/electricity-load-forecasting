import argparse
import csv
import datetime as dt
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

LIST_URL = "https://www.evn.com.vn/vi-VN/news-l/Thong-tin-tom-tat-van-hanh-HTD-Quoc-gia-60-2015"
SEARCH_URL = "https://www.evn.com.vn/vi-VN/tim-kiem"
BASE = "https://www.evn.com.vn"
CTRL = "ctl00$ContentPlaceHolder1$ctl00$11260$"
TITLE = "Thông tin chung về vận hành hệ thống điện Quốc gia ngày {}"
LINK_RE = re.compile(r"/d/vi-VN/news/[^\"'#?]+-60-2015-(\d+)")
# second "/" optional: some titles have typos like "ngày 06/102023"
DATE_RE = re.compile(r"ngày\s*(\d{1,2})\s*/\s*(\d{1,2})\s*/?\s*(\d{4})", re.I)

DATA = Path(__file__).parent / "data"
RAW = DATA / "raw_html"
LINKS_CSV = DATA / "links.csv"
NOT_FOUND = DATA / "not_found_dates.txt"
DELAY = 0.7  # seconds between requests, be polite to the server

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (research crawler for load forecasting)"


def request(method, url, **kw):
    for attempt in range(5):
        try:
            r = session.request(method, url, timeout=60, **kw)
            r.raise_for_status()
            r.encoding = "utf-8"
            time.sleep(DELAY)
            return r.text
        except requests.RequestException as e:
            wait = 5 * (attempt + 1)
            print(f"  ! {e} -> retry in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"failed: {url}")


def postback(html, target):
    soup = BeautifulSoup(html, "lxml")
    form = {i["name"]: i.get("value", "") for i in soup.find_all("input") if i.get("name")}
    form["__EVENTTARGET"] = CTRL + target
    form["__EVENTARGUMENT"] = ""
    return request("POST", LIST_URL, data=form)


def title_date(title):
    m = DATE_RE.search(title)
    if not m:
        return None
    d, mo, y = map(int, m.groups())
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def extract_posts(html):
    """All links to posts of this series on a page, as {id: {date, url, title}}."""
    posts = {}
    for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
        m = LINK_RE.search(a["href"])
        title = a.get_text(" ", strip=True)
        if m and title and m.group(1) not in posts:
            d = title_date(title)
            posts[m.group(1)] = {"date": d.isoformat() if d else "", "url": BASE + m.group(0), "title": title}
    return posts


def load_links():
    if not LINKS_CSV.exists():
        return {}
    with LINKS_CSV.open(encoding="utf-8") as f:
        return {r.pop("article_id"): r for r in csv.DictReader(f)}


def save_links(links):
    with LINKS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["article_id", "date", "url", "title"])
        w.writeheader()
        for aid in sorted(links, key=int, reverse=True):
            w.writerow({"article_id": aid, **links[aid]})


def crawl_listing(links):
    html = request("GET", LIST_URL)
    links.update(extract_posts(html))
    page2 = postback(html, "lbtXemThem")  # "Bấm để xem thêm"
    links.update(extract_posts(page2))
    # From page 2 the server maps these repeater items to pages 3, 4, 5 regardless of state.
    for item in ("ctl04", "ctl06", "ctl08"):
        links.update(extract_posts(postback(page2, f"Paging$rptPaging${item}$lnkPaging")))
    links.update(extract_posts(postback(page2, "Paging$lnkLast")))
    print(f"listing: {len(links)} posts known")


def search_date(day):
    """Search the post for one day; titles mix 5/3/2024, 05/3/2024 and 05/03/2024 styles."""
    variants = [
        f"{day.day}/{day.month}/{day.year}",
        f"{day.day:02d}/{day.month}/{day.year}",
        f"{day.day:02d}/{day.month:02d}/{day.year}",
        f"{day.day}/{day.month:02d}/{day.year}",
    ]
    for v in dict.fromkeys(variants):
        found = extract_posts(request("GET", SEARCH_URL, params={"textSearch": TITLE.format(v)}))
        hits = {aid: p for aid, p in found.items() if p["date"] == day.isoformat()}
        if hits:
            return hits
    return {}


def in_range(links, start, end):
    """Keep only posts whose date falls in [start, end]."""
    return {aid: p for aid, p in links.items() if p["date"] and start.isoformat() <= p["date"] <= end.isoformat()}


def search_missing(links, start, end, retry_not_found):
    have = {p["date"] for p in links.values()}
    skip = set() if retry_not_found or not NOT_FOUND.exists() else set(NOT_FOUND.read_text().split())
    todo = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    todo = [d for d in todo if d.isoformat() not in have and d.isoformat() not in skip]
    print(f"searching {len(todo)} missing dates ({start} -> {end})")
    not_found = set(skip)
    for i, day in enumerate(todo, 1):
        hits = in_range(search_date(day), start, end)
        links.update(hits)
        if not hits:
            not_found.add(day.isoformat())
        if i % 25 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)} searched, {len(not_found)} not found so far")
            save_links(links)
    NOT_FOUND.write_text("\n".join(sorted(not_found)))


def page_title(html):
    t = BeautifulSoup(html, "lxml").title
    return t.get_text(" ", strip=True) if t else ""


def scan_id_gaps(links, start, end, max_gap=400):
    """Fallback for dates search could not find: posts resolve by id alone, so probe every
    id between the known posts of the neighbouring days. Downloads are cached on the way."""
    if not NOT_FOUND.exists():
        return
    missing = {d for d in NOT_FOUND.read_text().split() if start.isoformat() <= d <= end.isoformat()}
    known = sorted((p["date"], int(aid)) for aid, p in links.items() if p["date"])
    gaps = set()
    for (d0, id0), (d1, id1) in zip(known, known[1:]):
        if any(d0 < m < d1 for m in missing) and 1 < id1 - id0 <= max_gap:
            gaps.add((id0, id1))
    ids = sorted({i for a, b in gaps for i in range(a + 1, b)} - {int(a) for a in links})
    print(f"scanning {len(ids)} ids in {len(gaps)} gaps for {len(missing)} not-found dates")
    RAW.mkdir(parents=True, exist_ok=True)
    for n, aid in enumerate(ids, 1):
        html = request("GET", f"{BASE}/d/vi-VN/news/x-60-2015-{aid}")
        title = page_title(html)
        d = title_date(title)
        if "thông tin chung về vận hành" in title.lower():
            # Titles without a single d/m/yyyy (e.g. multi-day holiday posts) are kept with
            # an empty date for manual review; the parser still reads the date from the body.
            links[str(aid)] = {"date": d.isoformat() if d else "", "url": f"{BASE}/d/vi-VN/news/x-60-2015-{aid}", "title": title}
            (RAW / f"{aid}.html").write_text(html, encoding="utf-8")
            if d:
                missing.discard(d.isoformat())
            print(f"  found {d or '?'} -> {aid}: {title[:80]}")
        if n % 100 == 0:
            print(f"  {n}/{len(ids)} ids scanned")
            save_links(links)
    NOT_FOUND.write_text("\n".join(sorted(missing)))


def download_posts(links):
    RAW.mkdir(parents=True, exist_ok=True)
    todo = [aid for aid in links if not (RAW / f"{aid}.html").exists()]
    print(f"{len(todo)} posts to download")
    for i, aid in enumerate(todo, 1):
        (RAW / f"{aid}.html").write_text(request("GET", links[aid]["url"]), encoding="utf-8")
        if i % 50 == 0:
            print(f"  {i}/{len(todo)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--retry-not-found", action="store_true", help="re-search dates not found earlier")
    ap.add_argument("--scan-ids", action="store_true", help="probe article ids around dates search missed")
    ap.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2023, 5, 28), help="first date, YYYY-MM-DD (series starts 2023-05-28)")
    ap.add_argument("--end", type=dt.date.fromisoformat, default=dt.date.today() - dt.timedelta(days=1),
                    help="last date, YYYY-MM-DD (default: yesterday)")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    sys.stdout.reconfigure(encoding="utf-8")  # Vietnamese titles in the log on Windows consoles
    # links.csv keeps every post ever found; --start/--end only limit searching and downloading.
    links = load_links()
    crawl_listing(links)
    save_links(links)
    search_missing(links, args.start, args.end, args.retry_not_found)
    save_links(links)
    if args.scan_ids:
        scan_id_gaps(links, args.start, args.end)
        save_links(links)
    download_posts(in_range(links, args.start, args.end))
