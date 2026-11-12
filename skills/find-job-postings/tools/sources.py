#!/usr/bin/env python3
"""Registry-driven aggregator access.

  python3 sources.py --probe                assert every `feed` source still
                                            matches its required_fields
  python3 sources.py --pull <term> [...]    pull the feed sources and print
                                            rows matching any term
  python3 sources.py --pull-json out.json <term> [...]

The probe is the drift alarm. It does not re-derive a method; it tells you a
method broke, which is the cheap half and the half worth automating.
"""
import json, re, sys, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REG = json.loads((Path(__file__).parent / "sources.json").read_text())["sources"]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

# Sources whose method lives in a dedicated memory file and needs more than a
# generic GET. The probe skips them; they have their own documented procedure.
COMPLEX = {"hiringcafe", "wellfound"}


def fetch(url, params=None, timeout=30):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                  timeout=timeout).read().decode("utf-8", "replace")


def rows(name, spec):
    """Return a list of raw job dicts for a `feed` source."""
    body = fetch(spec["url"], spec.get("params"))
    if spec["payload"] == "$rss":
        root = ET.fromstring(body)
        return [{c.tag: (c.text or "") for c in item} for item in root.iter("item")]
    d = json.loads(body)
    out = d if spec["payload"] == "$root" else d.get(spec["payload"], [])
    if spec.get("skip_first"):
        out = out[1:]          # remoteok element 0 is legal metadata, not a job
    return [r for r in out if isinstance(r, dict)]


def probe_one(item):
    name, spec = item
    if spec.get("status") not in ("feed", "sample") or name in COMPLEX:
        return None
    try:
        rs = rows(name, spec)
    except Exception as e:
        return (name, "FETCH FAILED", f"{type(e).__name__}: {str(e)[:60]}", 0)
    if not rs:
        return (name, "EMPTY", "returned zero rows; treat as drift, not as a quiet day", 0)
    missing = [f for f in spec.get("required_fields", []) if f not in rs[0]]
    if missing:
        return (name, "DRIFTED", "missing fields: " + ", ".join(missing), len(rs))
    # A source that quietly starts serving fewer rows than recorded is the
    # silent-truncation failure. It looks like a clean pull off a fraction of
    # the data, so assert the cap rather than trusting the row count.
    cap = spec.get("served_cap")
    if cap and len(rs) != cap:
        return (name, "CAP CHANGED", f"recorded {cap}, served {len(rs)}; re-test pagination", len(rs))
    note = ""
    if spec.get("status") == "sample":
        dec = spec.get("declared_total")
        note = f"sample only, {len(rs)} rows" + (f" of a claimed {dec:,}" if dec and dec > len(rs) else "")
    return (name, "ok", note, len(rs))


def cmd_probe():
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = [r for r in ex.map(probe_one, REG.items()) if r]
    bad = [r for r in res if r[1] != "ok"]
    for name, state, detail, n in sorted(res):
        print(f"  {name:<18}{state:<14}{n:>5} rows  {detail}")
    counts = {}
    for s in REG.values():
        counts[s.get("status", "?")] = counts.get(s.get("status", "?"), 0) + 1
    print("\nregistry:", ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    if bad:
        print(f"\n{len(bad)} source(s) need attention. Re-read the method before trusting a pull.")
    return 1 if bad else 0


def cmd_pull(terms, outfile=None):
    pat = re.compile("|".join(re.escape(t) for t in terms), re.I)
    hits, per = [], {}
    for name, spec in REG.items():
        if spec.get("status") not in ("feed", "sample") or name in COMPLEX:
            continue
        try:
            rs = rows(name, spec)
        except Exception as e:
            print(f"  {name:<18}FETCH FAILED  {type(e).__name__}")
            per[name] = -1
            continue
        keep = []
        for r in rs:
            blob = " ".join(str(v) for v in r.values() if isinstance(v, (str, int)))
            title = (r.get("title") or r.get("jobTitle") or r.get("position") or "")
            if pat.search(title) or pat.search(blob[:2000]):
                keep.append({
                    "source": name,
                    "title": title,
                    "company": r.get("company_name") or r.get("companyName") or r.get("company") or "",
                    "location": (r.get("candidate_required_location") or r.get("jobGeo")
                                 or r.get("location") or str(r.get("locationRestrictions") or "")),
                    "date": r.get(spec.get("date_field", ""), ""),
                    "url": r.get("url") or r.get("applicationLink") or r.get("link") or "",
                })
        per[name] = f"{len(keep)}/{len(rs)}"
        hits += keep
    print(f"\n{'source':<18}{'match/total':>12}")
    for k, v in per.items():
        print(f"  {k:<18}{str(v):>12}")
    print(f"\n{len(hits)} matching rows across {len([v for v in per.values() if v != -1])} sources")
    if outfile:
        json.dump(hits, open(outfile, "w"), indent=1)
        print(f"written to {outfile}")
    return hits


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "--probe":
        sys.exit(cmd_probe())
    if a[0] == "--pull":
        cmd_pull(a[1:])
    elif a[0] == "--pull-json":
        cmd_pull(a[2:], a[1])
    else:
        print(__doc__)
