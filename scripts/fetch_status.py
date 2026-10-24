#!/usr/bin/env python3
"""Build status.json for the Two Hand Tide Clock.

Fetches (server side, because neither source sends CORS headers):
  * Scottish Water near-real-time overflow feed (public, no key)
  * Met Office weather warnings RSS for Dumfries, Galloway, Lothian & Borders (region "dg")

Writes a small status.json beside index.html. Standard library only.
The page decides the traffic-light colour itself, using its own settings,
so this script only gathers and tidies the data.
Run: python3 scripts/fetch_status.py [output path, default status.json]
"""
import datetime as dt
import json
import math
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

try:
    from zoneinfo import ZoneInfo
    LONDON = ZoneInfo("Europe/London")
except Exception:  # pragma: no cover
    LONDON = None

SW_URL = "https://api.scottishwater.co.uk/overflow-event-monitoring/v1/near-real-time"
MO_REGION = "dg"  # Dumfries, Galloway, Lothian & Borders
MO_URL = "https://www.metoffice.gov.uk/public/data/PWSCache/WarningsRSS/Region/" + MO_REGION

# Assets the clock tracks by default (the page's settings can track others,
# so we also keep every East Lothian asset and anything within NEARBY_KM).
TRACKED = [
    "GULLANE WWTW CSO",
    "NORTH BERWICK WESTER DUNES WWPS CSO",
    "NORTH BERWICK, FIDRA SPS CSO",
    "NORTH BERWICK, 1 MELBOURNE ROAD CSO",
    "NORTH BERWICK, TANTALLON TERRACE CSO",
]
CENTRE = (56.04, -2.80)  # between Gullane and North Berwick
NEARBY_KM = 25
UA = "tide-clock-status/1.0 (+https://github.com)"


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iso(s):
    """Scottish Water gives ISO UTC like 2026-10-23T09:55:00.000Z; normalise, '' -> None."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except ValueError:
        return s


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def fetch_overflows():
    raw = json.loads(get(SW_URL, timeout=120))
    rows = raw.get("results", [])
    out = []
    for r in rows:
        name = (r.get("ASSET_NAME") or "").strip()
        lat, lon = num(r.get("DISCHARGE_OVERFLOW_LOCATION_LATITUDE")), num(r.get("DISCHARGE_OVERFLOW_LOCATION_LONGITUDE"))
        near = lat is not None and lon is not None and km(CENTRE, (lat, lon)) <= NEARBY_KM
        if not (name in TRACKED or r.get("LOCAL_AUTHORITY_NAME") == "East Lothian" or near):
            continue
        desc = (r.get("OVERFLOW_STATUS_DESCRIPTION") or "").strip()
        out.append({
            "asset_id": r.get("ASSET_ID"),
            "asset_name": name,
            "status_code": desc.split(" - ")[0] if " - " in desc else desc,
            "status": desc,
            "start_utc": iso(r.get("OVERFLOW_START_DATETIME")),
            "end_utc": iso(r.get("OVERFLOW_END_DATETIME")),
            "duration_min": num(r.get("OVERFLOW_DURATION_MIN")),
            "prev_start_utc": iso(r.get("OVERFLOW_START_DATETIME_PREVIOUS")),
            "prev_end_utc": iso(r.get("OVERFLOW_END_DATETIME_PREVIOUS")),
            "total_min_48h": num(r.get("TOTAL_OVERFLOWS_DURATION_MIN_PAST_48_HRS")) or 0,
            "last_transmitted_utc": iso(r.get("LAST_TRANSMITTED_DATETIME")),
            "receiving_water": (r.get("RECEIVING_WATER") or "").strip(),
            "local_authority": r.get("LOCAL_AUTHORITY_NAME"),
            "lat": lat,
            "lon": lon,
            "tracked": name in TRACKED,
        })
    out.sort(key=lambda o: (not o["tracked"], o["asset_name"]))
    lu = raw.get("last_updated")
    if isinstance(lu, (int, float)):
        lu = dt.datetime.fromtimestamp(lu / 1000, dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    missing = [t for t in TRACKED if t not in {o["asset_name"] for o in out}]
    return out, lu, len(rows), missing


MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
VALID = re.compile(r"valid from (\d{4}) \w{3} (\d{1,2}) (\w{3}) to (\d{4}) \w{3} (\d{1,2}) (\w{3})")


def uk_time(hhmm, day, mon, ref):
    """'2000', '24', 'Oct' in UK local time -> ISO UTC. Year chosen nearest to ref."""
    best = None
    for y in (ref.year - 1, ref.year, ref.year + 1):
        try:
            d = dt.datetime(y, MONTHS[mon], int(day), int(hhmm[:2]), int(hhmm[2:]))
        except (KeyError, ValueError):
            return None
        d = d.replace(tzinfo=LONDON) if LONDON else d.replace(tzinfo=dt.timezone.utc)
        if best is None or abs(d - ref) < abs(best - ref):
            best = d
    return best.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_warnings():
    root = ET.fromstring(get(MO_URL))
    ch = root.find("channel")
    pub = (ch.findtext("pubDate") or "").strip() if ch is not None else ""
    ref = dt.datetime.now(dt.timezone.utc)
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        desc = (it.findtext("description") or "").strip()
        m = re.match(r"(Yellow|Amber|Red) warning of (.+?) affecting", title, re.I)
        level = m.group(1).lower() if m else ""
        wtype = m.group(2).strip().lower() if m else ""
        areas = []
        if ":" in desc:
            tail = desc.split(":", 1)[1]
            tail = tail.split(" valid from")[0]
            areas = [a.strip() for a in tail.split(",") if a.strip()]
        v = VALID.search(desc)
        vf = vt = None
        vtext = ""
        if v:
            vf = uk_time(v.group(1), v.group(2), v.group(3), ref)
            vt = uk_time(v.group(4), v.group(5), v.group(6), ref)
            vtext = desc[v.start():]
        out.append({
            "level": level, "type": wtype, "title": title, "areas": areas,
            "valid_from_utc": vf, "valid_to_utc": vt, "valid_text": vtext,
            "link": (it.findtext("link") or "").strip(),
        })
    return out, pub


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "status.json"
    status = {"schema": 1, "generated_utc": now_iso(), "sources": {}, "overflows": [], "warnings": []}
    try:
        ovs, lu, n, missing = fetch_overflows()
        status["overflows"] = ovs
        status["sources"]["scottish_water"] = {"ok": True, "url": SW_URL, "feed_updated_utc": lu,
                                               "assets_in_feed": n, "tracked_missing": missing,
                                               "fetched_utc": now_iso(), "error": None}
    except Exception as e:  # keep going: the page shows 'overflow data unavailable'
        status["sources"]["scottish_water"] = {"ok": False, "url": SW_URL, "fetched_utc": now_iso(), "error": str(e)[:300]}
    try:
        ws, pub = fetch_warnings()
        status["warnings"] = ws
        status["sources"]["met_office"] = {"ok": True, "url": MO_URL, "region": "Dumfries, Galloway, Lothian & Borders",
                                           "feed_published": pub, "fetched_utc": now_iso(), "error": None}
    except Exception as e:
        status["sources"]["met_office"] = {"ok": False, "url": MO_URL, "fetched_utc": now_iso(), "error": str(e)[:300]}

    # If both sources failed, keep the previous file's data (it carries its own timestamps) rather than blanking it.
    if not any(s.get("ok") for s in status["sources"].values()):
        try:
            with open(path) as f:
                old = json.load(f)
            old["sources"] = status["sources"]
            status = old
        except Exception:
            pass
    with open(path, "w") as f:
        json.dump(status, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    sw = status["sources"].get("scottish_water", {})
    mo = status["sources"].get("met_office", {})
    print("overflows:", len(status["overflows"]), "sw ok:", sw.get("ok"), "warnings:", len(status["warnings"]), "mo ok:", mo.get("ok"))
    # Exit 0 even on partial failure so the workflow still commits what it has.


if __name__ == "__main__":
    main()
