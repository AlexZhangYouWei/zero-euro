"""Scrape the nulleuro.ch catalogue (login required) + images.

Reads the session cookie from nulleuro_cookie.txt ("sessionid=..." or the full Cookie header).
Catalogue pages are cached in data/nulleuro_raw/page-<n>.json; images in images/nulleuro/.
Writes data/nulleuro.json in the normalized shape used by build.py.
Run: python3 -I scripts/scrape_nulleuro.py
"""
import html
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "nulleuro_raw"
IMG = ROOT / "images" / "nulleuro"
BASE = "https://www.nulleuro.ch"
UA = "Mozilla/5.0 (personal archive; 0euro collector)"
DELAY = 1.0
COOKIE = (ROOT / "nulleuro_cookie.txt").read_text().strip()


def get(url, binary=False, xhr=False):
    headers = {"User-Agent": UA, "Cookie": COOKIE}
    if xhr:
        headers["X-Requested-With"] = "XMLHttpRequest"
    req = urllib.request.Request(url, headers=headers)
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


def text(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def parse_cards(fragment):
    cards = []
    for m in re.finditer(r'<div class="karte" data-id="(\d+)">(.*?)<div class="karte-footer">(.*?)</div>\s*</div>',
                         fragment, re.S):
        sid, body, footer = m.groups()
        field = lambda cls: text((re.search(rf'<div class="{cls}">(.*?)</div>', body, re.S) or [None, ""])[1])
        meta = re.findall(r"<span[^>]*>(.*?)</span>", (re.search(r'<div class="karte-meta">(.*?)</div>', body, re.S)
                                                        or [None, ""])[1], re.S)
        meta = [text(x) for x in meta]
        img = re.search(r'<img src="([^"]+)"', body)
        avail = re.search(r'border-radius:50%[^"]*" title="([^"]+)"', footer)
        badges = [text(b) for b in re.findall(r'<span class="badge[^"]*"[^>]*>(.*?)</span>', footer, re.S)]
        cards.append({
            "id": int(sid),
            "nr": field("karte-nr"),
            "title": field("karte-titel"),
            "ort": field("karte-ort"),
            "year": next((x[2:].strip() for x in meta if x.startswith("📅")), ""),
            "print_run": next((x[2:].strip() for x in meta if x.startswith("🔢")), ""),
            "badges": badges,
            "availability": avail.group(1) if avail else "",
            "image_url": img.group(1) if img else "",
        })
    return cards


def fetch_catalogue():
    # Full HTML pages, not the XHR endpoint: only the full page carries the availability dot.
    RAW.mkdir(parents=True, exist_ok=True)
    page = 1
    while True:
        cache = RAW / f"page-{page}.html"
        if cache.exists():
            raw = cache.read_text()
        else:
            raw = get(f"{BASE}/katalog/?lang=en&page={page}")
            if 'class="karte"' not in raw:
                raise RuntimeError("unexpected response (session expired?)")
            cache.write_text(raw)
            time.sleep(DELAY)
        print(f"page {page}", flush=True)
        if "var hasNext = true" not in raw:
            break
        page += 1
    cards = []
    for p in sorted(RAW.glob("page-*.html"), key=lambda p: int(p.stem.split("-")[1])):
        cards += parse_cards(p.read_text())
    return list({c["id"]: c for c in cards}.values())


def normalize(cards):
    notes = []
    for c in cards:
        code = c["nr"].rsplit("-", 1)[0] if "-" in c["nr"] else c["nr"]
        country, _, city = c["ort"].partition(" / ")
        badges = c["badges"]
        fields = {
            "Nr.": c["nr"],
            "Type": badges[0] if badges else "",
            "Series": badges[1] if len(badges) > 1 else "",
            "Print run": c["print_run"],
            "Availability": c["availability"],
        }
        img = f"images/nulleuro/{c['id']}.jpg" if c["image_url"] else ""
        notes.append({
            "code": code,
            "edition": c["year"] or c["nr"],
            "nr": c["nr"],
            "name": c["title"],
            "city": city,
            "country": country,
            "fields": {k: v for k, v in fields.items() if v},
            "img": img,
            "image_url": c["image_url"],
            "url": f"{BASE}/schein/{c['id']}/",
        })
    # Same code + same year happens (e.g. variants A/B); keep editions unique within a code.
    seen = {}
    for n in notes:
        seen.setdefault((n["code"], n["edition"]), []).append(n)
    for dupes in seen.values():
        if len(dupes) > 1:
            for n in dupes:
                n["edition"] = f"{n['edition']} · {n['nr']}"
    return notes


def fetch_images(notes):
    IMG.mkdir(parents=True, exist_ok=True)
    todo = [n for n in notes if n["img"] and not (ROOT / n["img"]).exists()]
    for i, n in enumerate(todo, 1):
        url = n["image_url"].replace("/image/upload/", "/image/upload/f_jpg,w_600,q_85/", 1)
        data = get(url, binary=True)
        if data:
            (ROOT / n["img"]).write_bytes(data)
        time.sleep(DELAY / 2)
        if i % 100 == 0:
            print(f"images {i}/{len(todo)}", flush=True)


def main():
    notes = normalize(fetch_catalogue())
    print(f"{len(notes)} notes", flush=True)
    (ROOT / "data" / "nulleuro.json").write_text(json.dumps(notes, ensure_ascii=False, indent=1))
    fetch_images(notes)
    print("done", flush=True)


if __name__ == "__main__":
    main()
