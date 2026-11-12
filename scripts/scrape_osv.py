"""Scrape 0eurosouvenirs.com banknote pages (English) + thumbnails.

Resumable: each note is cached as data/osv_raw/<slug>.json; images in images/osv/.
Run: python3 -I scripts/scrape_osv.py [limit]
"""
import html
import json
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "osv_raw"
IMG = ROOT / "images" / "osv"
UA = "Mozilla/5.0 (personal archive; 0euro collector)"
WORKERS = 6
DELAY = 0.6  # seconds per worker between requests


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                return data if binary else data.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (attempt + 1))
        except Exception:
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"failed: {url}")


def parse(page, url):
    # Notes without a sales point carry a CreativeWork block, notes with one a Product block.
    note, crumbs = None, []
    for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        try:
            d = json.loads(block)
        except ValueError:
            continue
        if d.get("@type") in ("CreativeWork", "Product"):
            note = d
        elif d.get("@type") == "BreadcrumbList":
            crumbs = [i["name"] for i in d.get("itemListElement", [])]
    ident = (note or {}).get("identifier") or (note or {}).get("productID", "")
    if "_" not in ident:
        return None
    code, edition = ident.split("_", 1)
    name = html.unescape(note.get("name", ""))
    text = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", "", page, flags=re.S)
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)))
    head = re.search(
        re.escape(ident) + " " + re.escape(name) + r" (.+?) Code " + re.escape(code)
        + " Year edition " + re.escape(edition) + r"(?: Print run (.+?))?(?: Serial no\. (.+?))? All 0 euro",
        text,
    )
    place, print_run, serial = head.groups() if head else ("", "", "")
    city, _, country = (place or "").rpartition(", ")
    offers = note.get("offers", [])
    return {
        "code": code,
        "edition": edition,
        "name": name,
        "city": city,
        "country": country or (crumbs[2] if len(crumbs) > 3 else ""),
        "print_run": print_run or "",
        "serial": serial or "",
        "sellers": [
            {"name": o.get("seller", {}).get("name", ""), "price": o.get("price"), "currency": o.get("priceCurrency", "")}
            for o in (offers if isinstance(offers, list) else [offers])
        ],
        "url": url,
        "image_url": note.get("image", "").split("?")[0],
    }


lock = threading.Lock()
done = [0]


def work(url, total):
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    cache = RAW / f"{slug}.json"
    if cache.exists():
        rec = json.loads(cache.read_text())
    else:
        page = get(url)
        time.sleep(DELAY)
        rec = parse(page, url) if page else None
        cache.write_text(json.dumps(rec, ensure_ascii=False))
    if rec and rec["image_url"]:
        img = IMG / f"{rec['code']}_{rec['edition']}.webp"
        if not img.exists():
            data = get(rec["image_url"], binary=True)
            if data:
                img.write_bytes(data)
            time.sleep(DELAY)
    with lock:
        done[0] += 1
        if done[0] % 100 == 0:
            print(f"{done[0]}/{total}", flush=True)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    sitemap = get("https://0eurosouvenirs.com/sitemap-banknotes.xml")
    urls = sorted(set(re.findall(r"<loc>(https://0eurosouvenirs\.com/en/banknotes/[^<]+)</loc>", sitemap)))
    if len(sys.argv) > 1:
        urls = urls[: int(sys.argv[1])]
    print(f"{len(urls)} notes", flush=True)
    with ThreadPoolExecutor(WORKERS) as pool:
        list(pool.map(lambda u: work(u, len(urls)), urls))
    notes = [json.loads(p.read_text()) for p in sorted(RAW.glob("*.json"))]
    notes = [n for n in notes if n]
    (ROOT / "data" / "osv.json").write_text(json.dumps(notes, ensure_ascii=False, indent=1))
    print(f"saved {len(notes)} notes", flush=True)


if __name__ == "__main__":
    main()
