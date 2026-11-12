"""Merge both sources by code + edition, group by code (one "place" per code), write data.js.

Run: python3 -I scripts/build.py
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABELS = {"osv": "0eurosouvenirs.com", "nulleuro": "nulleuro.ch"}


def edition_key(edition):
    # "2021-10" -> ([2021, 10], ...) so newest sorts first when reversed; text only breaks ties
    return [int(p) for p in re.findall(r"\d+", edition)], edition


def load(name):
    path = ROOT / "data" / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else []


def image(rel):
    return rel if rel and (ROOT / rel).exists() else ""


def osv_notes():
    out = []
    for n in load("osv"):
        fields = {"Print run": n["print_run"], "Serial no.": n["serial"]}
        if n["sellers"]:
            fields["Sold at"] = "; ".join(
                s["name"] + (f" ({s['price']} {s['currency']})" if s["price"] is not None else "") for s in n["sellers"]
            )
        out.append({
            "code": n["code"], "edition": n["edition"], "name": n["name"],
            "city": n["city"], "country": n["country"],
            "img": image(f"images/osv/{n['code']}_{n['edition']}.webp"),
            "source": {"src": "osv", "url": n["url"], "fields": {k: v for k, v in fields.items() if v}},
        })
    return out


def nulleuro_notes():
    out = []
    for n in load("nulleuro"):
        # nulleuro keeps the variant letter in the number (ZEKG-1A, year 2017-1); 0eurosouvenirs writes 2017-1A
        year = n["edition"].split(" · ")[0]
        letter = re.search(r"\d([A-Za-z]+)$", n["nr"])
        out.append({
            "code": n["code"], "edition": year + (letter.group(1) if letter else ""), "nr": n["nr"],
            "name": n["name"], "city": n["city"].split(" / ")[-1], "country": n["country"],
            "img": image(n["img"]),
            "source": {"src": "nulleuro", "url": n["url"], "fields": n["fields"]},
        })
    seen = Counter((n["code"], n["edition"]) for n in out)
    for n in out:
        if seen[(n["code"], n["edition"])] > 1:
            n["edition"] = f"{n['edition']} · {n['nr']}"
    return out


def name_map(pairs, min_count=1):
    """nulleuro spelling -> 0eurosouvenirs spelling, learned from notes present on both sites."""
    votes = defaultdict(Counter)
    for ne, osv in pairs:
        if ne and osv:
            votes[ne][osv] += 1
    out = {}
    for ne, c in votes.items():
        best, count = c.most_common(1)[0]
        if count >= min_count and count / sum(c.values()) >= 0.8:
            out[ne] = best
    return out


def merge(osv, ne):
    by_key = {(n["code"], n["edition"]): n for n in osv}
    matched = [(n, by_key[(n["code"], n["edition"])]) for n in ne if (n["code"], n["edition"]) in by_key]
    countries = name_map((n["country"], o["country"]) for n, o in matched)
    cities = name_map(((n["country"], n["city"]), (o["country"], o["city"])) for n, o in matched)

    notes = {}
    for n in osv:
        notes[(n["code"], n["edition"])] = {**n, "sources": [n.pop("source")]}
    for n in ne:
        key = (n["code"], n["edition"])
        if key in notes:
            note = notes[key]
            note["sources"].append(n["source"])
            note["img"] = note["img"] or n["img"]
            note["city"] = note["city"] or n["city"]
        else:
            country = countries.get(n["country"], n["country"])
            city = cities.get((n["country"], n["city"]), (None, n["city"]))[1]
            notes[key] = {**n, "country": country, "city": city, "sources": [n.pop("source")]}
    print(f"matched {len(matched)} notes on both sites; "
          f"{len(countries)} country / {len(cities)} city spellings mapped")
    return list(notes.values())


def load_zh(name, batches):
    """Chinese map data/<name>.json plus any data/<batches>/out_*.json translation batches folded into it."""
    path = ROOT / "data" / f"{name}.json"
    names = json.loads(path.read_text()) if path.exists() else {}
    for out in sorted((ROOT / "data" / batches).glob("out_*.json")):
        names.update(json.loads(out.read_text()))
    path.write_text(json.dumps(names, ensure_ascii=False, indent=1))
    return names


def group(notes):
    # country name -> ISO code (from the 0eurosouvenirs catalogue), used for flags
    codes = json.loads((ROOT / "data" / "country_codes.json").read_text())
    names_zh = load_zh("names_zh", "translate")
    # cities are keyed "Country|City": the same spelling can be a different town in another country
    cities_zh = load_zh("cities_zh", "translate_city")
    for n in notes:
        n["city_zh"] = cities_zh.get(f"{n['country']}|{n['city']}", "")
        zh = names_zh.get(n["name"].strip(), "")
        # A trailing "ANNIVERSARY" marks the anniversary series, not part of the subject ("2025 蛇年週年紀念" reads wrong)
        # ...but "280th BIRTH ANNIVERSARY" is a real anniversary, so leave those alone
        marker = re.search(r"(?<!BIRTH)(?<!\d(st|nd|rd|th)) ANNIVERSARY$", n["name"].rstrip())
        if marker and zh.endswith("週年紀念"):
            zh = zh[: -len("週年紀念")].rstrip(" -－") + "（週年紀念版）"
        n["name_zh"] = zh
    groups = defaultdict(list)
    for n in notes:
        groups[n["code"]].append(n)
    out = []
    for code, versions in groups.items():
        versions.sort(key=lambda v: edition_key(v["edition"]), reverse=True)
        latest = versions[0]
        out.append({
            "code": code, "name": latest["name"], "name_zh": latest["name_zh"],
            "city": latest["city"], "city_zh": latest["city_zh"], "country": latest["country"], "cc": codes.get(latest["country"], ""),
            "versions": [{k: v[k] for k in ("edition", "name", "name_zh", "city", "city_zh", "img", "sources")} for v in versions],
        })
    out.sort(key=lambda g: (g["country"], g["city"], g["name"].lower()))
    return out


def main():
    groups = group(merge(osv_notes(), nulleuro_notes()))
    data = {"labels": LABELS, "groups": groups}
    js = "window.DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    (ROOT / "data.js").write_text(js)
    notes = [v for g in groups for v in g["versions"]]
    both = sum(len(v["sources"]) == 2 for v in notes)
    print(f"{len(groups)} places, {len(notes)} notes ({both} on both sites), "
          f"{sum(bool(v['img']) for v in notes)} with image")


if __name__ == "__main__":
    main()
