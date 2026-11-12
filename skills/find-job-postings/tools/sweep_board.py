#!/usr/bin/env python3
"""Sweep a company's whole careers board for agentic-quality evidence.

This exists because the ad-hoc sweeps kept missing things, in three distinct ways.
Each is guarded here so the failure cannot recur silently:

1. THE TITLE FILTER WAS TOO NARROW. The original passes matched QA and test job
   TITLES, so Sabre's Principal AI/ML Engineer (which establishes evaluation
   harnesses with golden sets, trace replay and chaos for agents), Duck Creek's VP
   of Agentic AI and Toast's Voice AI Platform req were all structurally invisible.
   TITLE_WIDE below is deliberately over-inclusive; the cost of a false positive is
   one line of reading, the cost of a false negative is a wrong account score.

2. SILENT TRUNCATION LOOKED LIKE A CLEAN RESULT. A Workday pull read `total` as 0
   and returned 40 of 121 postings, which would have "confirmed" a board was clean
   off a third of it. Every fetcher now returns the board's own reported total and
   the sweep FAILS LOUDLY if it did not pull all of it.

3. THE REGEX WAS TREATED AS THE ANSWER. Keyword hits are not findings. Visa's
   three "voice" hits were a contact-centre quality analyst and office boilerplate
   about using a telephone; its "eval" hits were manual call review and technical
   evaluations of new technologies during procurement. So this prints the MATCHED
   CONTEXT for every hit and reports candidates, never verdicts. A human decides.

Usage:
  python3 tools/sweep_board.py greenhouse toast
  python3 tools/sweep_board.py ashby snowflake
  python3 tools/sweep_board.py workday duckcreek duckcreekcareers
  python3 tools/sweep_board.py smartrecruiters Flywire1
  python3 tools/sweep_board.py lever <org>
  python3 tools/sweep_board.py <provider> <slug> [key=value ...]   any provider in READERS,
        extras as discover_board.py prints them, e.g.
        oracle_hcm efpv site=CX_1 pod=us6      phenom careers.thredup.com path=us/en
        taleo weyerhaeuser section=10000       taleo_be NEKTAR host=phg.tbe.taleo.net code=phg04
  python3 tools/sweep_board.py --selftest        offline parser and registry controls
  python3 tools/sweep_board.py --live [prov ...] two real boards and one nonsense slug
                                                 per provider, against the live platforms

Every reader returns (postings, total). Each posting carries title, text (the full
description), url, location, department and posted, plus company where the platform
publishes the board owner's name. total is what the board says it holds; it is None
when the platform says the board does not exist, which is never the same as 0.
"""
import json, re, sys, time, html, socket, inspect, os, http.client, http.cookiejar
import urllib.request, urllib.error
from urllib.parse import quote, urlparse

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "Accept": "application/json"}

def _get(url, timeout=45):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout))

def _strip(t):
    t = html.unescape(t or "")
    t = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"[ \t]+", " ", t)

# ---------------------------------------------------------------- fetchers
# Each returns (postings, reported_total). reported_total is what the BOARD says
# it has, so the caller can prove the pull was complete.

def greenhouse(org):
    d = _get(f"https://boards-api.greenhouse.io/v1/boards/{org}/jobs?content=true")
    js = [{"title": j["title"], "text": _strip(j.get("content")), "url": j.get("absolute_url", ""),
           "location": (j.get("location") or {}).get("name", ""),
           "department": ", ".join(x.get("name", "") for x in (j.get("departments") or [])),
           "posted": (j.get("updated_at") or "")[:10]} for j in d["jobs"]]
    return js, d.get("meta", {}).get("total", len(d["jobs"]))

def ashby(org):
    d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{org}")
    js = [{"title": j["title"], "text": _strip(j.get("descriptionPlain") or j.get("descriptionHtml")),
           "url": j.get("jobUrl", ""), "location": j.get("location") or "",
           "department": j.get("department") or j.get("team") or "",
           "posted": (j.get("publishedAt") or "")[:10]} for j in d["jobs"]]
    return js, len(d["jobs"])

def lever(org):
    d = _get(f"https://api.lever.co/v0/postings/{org}?mode=json")
    js = [{"title": j["text"], "text": _strip(j.get("descriptionPlain") or j.get("description")),
           "url": j.get("hostedUrl", ""),
           "location": (j.get("categories") or {}).get("location") or "",
           "department": ((j.get("categories") or {}).get("department")
                          or (j.get("categories") or {}).get("team") or ""),
           "posted": time.strftime("%Y-%m-%d", time.gmtime((j.get("createdAt") or 0)/1000))} for j in d]
    return js, len(d)

def smartrecruiters(org):
    out, off, total = [], 0, None
    while True:
        d = _get(f"https://api.smartrecruiters.com/v1/companies/{org}/postings?limit=100&offset={off}")
        total = d.get("totalFound", 0)
        # A nonexistent org returns HTTP 200 with totalFound 0, so an empty board
        # and a wrong slug look identical. Flywire's real slug is Flywire1.
        for j in d.get("content", []):
            try: full = _get(f"https://api.smartrecruiters.com/v1/companies/{org}/postings/{j['id']}")
            except Exception: full = {}
            loc = j.get("location") or {}
            out.append({"title": j["name"], "text": _strip(json.dumps(full.get("jobAd", {}))),
                        "url": j.get("ref") or f"https://jobs.smartrecruiters.com/{org}/{j['id']}",
                        "location": ", ".join(x for x in (loc.get("city"), loc.get("region"),
                                                          loc.get("country")) if x),
                        "department": (j.get("department") or {}).get("label", ""),
                        "posted": (j.get("releasedDate") or "")[:10]})
            time.sleep(.05)
        off += 100
        if off >= total: break
    return out, total

def workday(tenant, site, wd="wd1", title_filter=None, on_stub=None):
    """title_filter is an optional callable on the stub title. The stub list already
    carries the title, so an enterprise board can be narrowed before paying for one
    detail fetch per requisition. Visa's board is ~3,000 reqs; pulling every body
    took over half an hour and timed the caller out. The board's own reported total
    is still returned unchanged, so completeness is still checkable, and the count
    of stubs that passed the filter is printed so a too-narrow filter is loud rather
    than a silent zero.

    on_stub is an optional callable given every stub BEFORE the title filter, so a
    caller can record the whole board (title, location, url, posted text) without
    paying for a single detail fetch."""
    B = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant.replace('-', '_')}/{site}"
    def page(off):
        r = urllib.request.Request(B + "/jobs", method="POST",
            data=json.dumps({"appliedFacets": {}, "limit": 20, "offset": off, "searchText": ""}).encode(),
            headers={**UA, "Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(r, timeout=45))
    d0 = page(0)
    total = d0.get("total", 0)
    if not total:
        raise SystemExit("Workday reported total=0. Do NOT treat this as an empty board; "
                         "it means the tenant/site pair is wrong. Grep the careers page HTML.")
    stubs, off = list(d0.get("jobPostings", [])), 20
    while off < total:
        stubs += page(off).get("jobPostings", []); off += 20
    if on_stub is not None:
        root = f"https://{tenant}.{wd}.myworkdayjobs.com/{site}"
        for st in stubs:
            on_stub({"title": st.get("title", ""), "location": st.get("locationsText") or "",
                     "url": root + st.get("externalPath", "") if st.get("externalPath") else "",
                     "posted": st.get("postedOn", ""), "department": ""})
    if title_filter is not None:
        kept = [st for st in stubs if title_filter(st.get("title", ""))]
        print(f"  workday {tenant}/{site}: {len(stubs)} stubs pulled of {total} reported, "
              f"{len(kept)} passed the title filter", flush=True)
        if len(stubs) < total:
            raise SystemExit(f"Workday pull incomplete: {len(stubs)} stubs of {total}.")
        stubs = kept
    out = []
    for st in stubs:
        slug = st["externalPath"].split("/")[-1]
        try:
            j = _get(B + "/job/" + slug)["jobPostingInfo"]
            # The DETAIL payload has no externalPath; it has externalUrl. Reading
            # externalPath made every url collapse to the bare board root, so no req
            # could be re-verified or handed to anyone. The stub's externalPath is the
            # fallback, so the url is never just the board.
            base = f"https://{tenant}.{wd}.myworkdayjobs.com/{site}"
            out.append({"title": j["title"], "text": _strip(j.get("jobDescription")),
                        "url": j.get("externalUrl") or (base + st.get("externalPath", "")
                                                        if st.get("externalPath") else ""),
                        "location": j.get("location") or "",
                        "posted": j.get("startDate", "")})
        except Exception:
            out.append({"title": st["title"], "text": "", "url": "",
                        "location": (st.get("locationsText") or ""), "posted": ""})
        time.sleep(.15)
    return out, total

# ======================================================= the platforms added 2026-10-14
# discover_board.py could name these platforms and nothing could read them, so a company
# on one of them was recorded as "ats known, unreadable". Every call below was run against
# real boards on 2026-10-14; the field notes in reference/ats-field-notes.md say what each
# platform does with a wrong slug.
#
# THREE OUTCOMES, KEPT APART. A reader returns (postings, total) when the board answered,
# ([], None) when the PLATFORM says no such board exists (a 404, a redirect to the vendor's
# own homepage), and raises BoardClosed for a 401, 403, 429, 5xx, timeout or dropped
# connection. A closed door is never evidence of absence, so it must not reach a zero.
# A BoardClosed mid-board stops the read rather than retrying: if a platform blocks
# scripted reads, the answer is to record that, not to work around it.

BROWSER = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                     "application/json;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "identity"}
MISSING = (404, 410)
PACE = 0.2          # seconds between per-posting requests


class BoardClosed(RuntimeError):
    """The platform refused or failed to answer. Not an empty board and not a wrong slug."""


def _fetch(url, data=None, headers=None, method=None, timeout=45, missing=MISSING, opener=None):
    """(status, final_url, text). A status in `missing` comes back as a value because, for
    most platforms, that IS the no-such-board answer. Anything else that fails raises."""
    req = urllib.request.Request(url, data=data, headers={**BROWSER, **(headers or {})},
                                 method=method)
    try:
        with (opener.open if opener else urllib.request.urlopen)(req, timeout=timeout) as r:
            return r.status, r.geturl(), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in missing:
            return e.code, url, ""
        raise BoardClosed(f"HTTP {e.code} from {url}") from e
    except urllib.error.URLError as e:
        if isinstance(e.reason, socket.gaierror):
            # A tenant host that does not resolve is a missing board ONLY if the vendor's
            # own domain still resolves. Otherwise the network is down, and calling every
            # board missing would record a whole run as wrong slugs.
            host = urlparse(url).hostname or ""
            parent = ".".join(host.split(".")[-2:])
            for probe in (parent, "www." + parent):
                try:
                    socket.gethostbyname(probe)
                    return 404, url, ""
                except OSError:
                    pass
            raise BoardClosed(f"DNS failed for {host} and for {parent}: network down?") from e
        raise BoardClosed(f"{e.reason} from {url}") from e
    except (OSError, http.client.HTTPException) as e:
        raise BoardClosed(f"{type(e).__name__} from {url}") from e


def _jsonld_posting(page):
    """The schema.org JobPosting object embedded in a page, or None."""
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page or "",
                         re.S | re.I):
        try:
            d = json.loads(m.group(1).strip(), strict=False)
        except ValueError:
            continue
        todo = list(d) if isinstance(d, list) else [d]
        while todo:
            x = todo.pop(0)
            if not isinstance(x, dict):
                continue
            todo += x.get("@graph") or []
            t = x.get("@type")
            if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                return x
    return None


def _ld_location(ld):
    locs = ld.get("jobLocation") or []
    locs = [locs] if isinstance(locs, dict) else locs
    out = []
    for loc in locs:
        a = (loc or {}).get("address") if isinstance(loc, dict) else None
        if isinstance(a, str):
            s = a
        elif isinstance(a, dict):
            c = a.get("addressCountry")
            c = c.get("name", "") if isinstance(c, dict) else c
            s = ", ".join(x for x in (a.get("addressLocality"), a.get("addressRegion"), c)
                          if isinstance(x, str) and x and x.upper() != "UNAVAILABLE")
        else:
            s = ""
        if s and s not in out:
            out.append(s)
    if not out and ld.get("jobLocationType") == "TELECOMMUTE":
        out.append("Remote")
    return " | ".join(out)


def _ld_record(ld, stub):
    """Merge a JobPosting into a stub. The stub's own fields win only where the page is blank."""
    org = ld.get("hiringOrganization")
    dept = ld.get("occupationalCategory") or ld.get("industry") or ""
    dept = ", ".join(dept) if isinstance(dept, list) else dept
    return {**stub, "title": ld.get("title") or stub.get("title", ""),
            "text": _strip(ld.get("description")),
            "location": _ld_location(ld) or stub.get("location", ""),
            "department": stub.get("department") or dept,
            "posted": (ld.get("datePosted") or stub.get("posted") or "")[:10],
            "company": stub.get("company") or (org.get("name", "") if isinstance(org, dict)
                                               else org or "")}


def _xtag(block, tag):
    """One XML element's text, CDATA or escaped, without an XML parser (the feeds are not
    always well formed, and a parser that refuses a feed returns nothing)."""
    m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
    if not m:
        return ""
    v = m.group(1).strip()
    c = re.fullmatch(r"<!\[CDATA\[(.*)\]\]>", v, re.S)
    return c.group(1) if c else html.unescape(v)


def _unamp(u):
    """Unescape a URL taken from markup. Never html.unescape: browsers accept legacy
    entities with no semicolon, so it turns "&currentTime=" into "\u00a4tTime=" (&curren)
    and "&section=" into "\u00a7ion=". That broke Taleo Business Edition paging on
    2026-10-14 with a UnicodeEncodeError."""
    return u.replace("&amp;", "&")


def _blank(**kw):
    return {"title": "", "text": "", "url": "", "location": "", "department": "",
            "posted": "", "company": "", **kw}


def _details(stubs, one, title_filter, label, on_stub=None):
    """Fetch the body for each stub. The title filter runs on the stub so only survivors
    cost a request, and how many passed is printed so a too-narrow filter is loud. A page
    that fails to parse keeps its stub, so the count still reconciles with the board.

    on_stub, as in workday(), is given EVERY stub before the filter, so a caller can record
    the whole board and skip what it already holds without paying for a single body."""
    if on_stub is not None:
        for st in stubs:
            on_stub({**_blank(), **{k: v for k, v in st.items() if not k.startswith("_")}})
    keep = [s for s in stubs if title_filter is None or title_filter(s.get("title", ""))]
    if title_filter is not None:
        print(f"  {label}: {len(stubs)} stubs, {len(keep)} passed the title filter",
              flush=True)
    out = []
    for st in keep:
        try:
            rec = one(st)
        except BoardClosed:
            raise
        except Exception:                                   # noqa: BLE001
            rec = None
        out.append({k: v for k, v in (rec or st).items() if not k.startswith("_")})
        time.sleep(PACE)
    # A page that parses to nothing keeps its stub, which reads as a saved posting. Say so,
    # or a board of title-only stubs reports "N saved" like a good read (Meltwater, 2026-11-05).
    empty = sum(1 for r in out if len((r.get("text") or "").strip()) < 200)
    if out and empty:
        print(f"  WARNING {label}: {empty} of {len(out)} postings came back without a full "
              f"description (under 200 characters)", flush=True)
    return [{**_blank(), **r} for r in out]


# ---- bulk providers: one request returns every posting with its body ----

def workable(org):
    """The widget endpoint the embedded board itself calls. The documented SPI needs a
    token, and api/v3/accounts/<org>/jobs 404s for real boards (identiv)."""
    s, _, b = _fetch(f"https://apply.workable.com/api/v1/widget/accounts/{quote(org)}"
                     "?details=true")
    if s in MISSING:
        return [], None
    d = json.loads(b)
    # One row per job PER LOCATION, like Rippling: Alphatec's 40 rows were 29 jobs on
    # 2026-10-14, and its board page shows 29. The shortcode is the job.
    jobs = {}
    for j in d.get("jobs") or []:
        loc = ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
        r = jobs.setdefault(j.get("shortcode") or j.get("url"), _blank(
            title=j.get("title", ""), text=_strip(j.get("description")),
            url=j.get("url") or j.get("shortlink") or "",
            department=j.get("department") or j.get("function") or "",
            posted=(j.get("published_on") or j.get("created_at") or "")[:10],
            company=d.get("name") or "", _locs=[]))
        if loc and loc not in r["_locs"]:
            r["_locs"].append(loc)
    out = [{**{k: v for k, v in r.items() if k != "_locs"}, "location": " | ".join(r["_locs"])}
           for r in jobs.values()]
    return out, len(out)


def gem(org):
    s, _, b = _fetch(f"https://api.gem.com/job_board/v0/{quote(org)}/job_posts/")
    if s in MISSING:
        return [], None
    out = [_blank(title=j.get("title", ""),
                  text=_strip(j.get("content") or j.get("content_plain")),
                  url=j.get("absolute_url", ""),
                  location=(j.get("location") or {}).get("name", ""),
                  department=", ".join(x.get("name", "") for x in j.get("departments") or []),
                  posted=(j.get("first_published_at") or j.get("created_at") or "")[:10])
           for j in json.loads(b)]
    return out, len(out)


def jazzhr(org):
    """JazzHR's XML export carries every open job with its full body. The HTML board at
    <org>.applytojob.com/apply carries titles only, and a wrong org there redirects to
    jazzhr.com with HTTP 200; the export 404s instead."""
    s, _, x = _fetch(f"https://app.jazz.co/feeds/export/jobs/{quote(org)}")
    if s in MISSING:
        return [], None
    out = []
    for jb in re.findall(r"<job>(.*?)</job>", x, re.S):
        if _xtag(jb, "status") and _xtag(jb, "status").lower() != "open":
            continue
        out.append(_blank(title=_xtag(jb, "title"), text=_strip(_xtag(jb, "description")),
                          url=_xtag(jb, "url"),
                          location=", ".join(v for v in (_xtag(jb, "city"), _xtag(jb, "state"),
                                                         _xtag(jb, "country")) if v),
                          department=_xtag(jb, "department")))
    return out, len(out)


def pinpoint(org):
    s, _, b = _fetch(f"https://{org}.pinpointhq.com/postings.json")
    if s in MISSING:
        return [], None
    out = []
    for j in json.loads(b).get("data") or []:
        body = " ".join(_strip(j.get(k)) for k in ("description", "key_responsibilities",
                                                   "skills_knowledge_expertise", "benefits")
                        if j.get(k))
        out.append(_blank(title=j.get("title", ""), text=body, url=j.get("url", ""),
                          location=(j.get("location") or {}).get("name", ""),
                          department=(((j.get("job") or {}).get("department")) or {})
                          .get("name", "")))
    return out, len(out)


def teamtailor(org, host=None):
    """The RSS feed carries every job with its body and the board owner's name. A career
    site on the company's own host (careers.waitwhile.com) serves the same feed there."""
    # A caller that kept only the slug still works: a custom host has two dots or more
    # (careers.waitwhile.com), a regional slug has one (swishanalytics.na).
    host = host or (org if org.count(".") >= 2 else None)
    s, _, x = _fetch(f"https://{host}/jobs.rss" if host else f"https://{org}.teamtailor.com/jobs.rss")
    if s in MISSING:
        return [], None
    owner = _xtag(x.split("<item>")[0], "title")
    out = []
    for it in re.findall(r"<item>(.*?)</item>", x, re.S):
        locs = [_xtag(lc, "tt:city") or _xtag(lc, "tt:name")
                for lc in re.findall(r"<tt:location>(.*?)</tt:location>", it, re.S)]
        pub = _xtag(it, "pubDate")
        try:
            pub = time.strftime("%Y-%m-%d", time.strptime(pub[:16], "%a, %d %b %Y")) if pub else ""
        except ValueError:
            pub = ""
        out.append(_blank(title=_xtag(it, "title"), text=_strip(_xtag(it, "description")),
                          url=_xtag(it, "link"), location=" | ".join(x for x in locs if x),
                          department=_xtag(it, "tt:department"), posted=pub, company=owner))
    return out, len(out)


def successfactors(slug, company=None, tld="com"):
    """SAP SuccessFactors Recruiting Marketing (RMK). Its /sitemap.xml is an RSS feed of
    every posting in every language with the full body, so it is one request. The careers
    SEARCH page shows one language at a time and so shows fewer: PACCAR's showed 207 in US
    English against 240 in the feed on 2026-10-14, and the other 33 were live postings in
    Portuguese and UK English. The feed is the board.

    slug is the RMK host (jobs.paccar.com), or a classic career host label (career012)
    with company, which is followed to wherever it redirects."""
    host = slug if "." in slug else None
    if host is None:
        if not company:
            raise ValueError("successfactors needs company= with a career host label")
        # Without the job-search parameters the classic page renders in place instead of
        # redirecting to the RMK host (PACCAR, 2026-10-14).
        s, final, _ = _fetch(f"https://{slug}.successfactors.{tld}/career?company="
                             f"{quote(company)}&career_ns=job_listing_summary"
                             "&navBarLevel=JOB_SEARCH")
        if s in MISSING:
            return [], None
        host = urlparse(final).hostname or ""
        if "successfactors" in host:
            raise NotImplementedError(
                f"{company} runs the classic SuccessFactors career site with no RMK front "
                "end, which has no public feed. Route 7 (render it).")
    s, _, x = _fetch(f"https://{host}/sitemap.xml", timeout=180)
    if s in MISSING or "<rss" not in x[:400]:
        return [], None
    out = []
    for it in re.findall(r"<item>(.*?)</item>", x, re.S):
        loc = _xtag(it, "g:location")
        title = _xtag(it, "title")
        if loc and title.endswith(f"({loc})"):
            title = title[:-len(loc) - 2].strip()
        out.append(_blank(title=title, text=_strip(_xtag(it, "description")),
                          url=_xtag(it, "link"), location=loc,
                          department=_xtag(it, "g:job_function"),
                          company=_xtag(it, "g:employer")))
    return out, len(out)


# ---- list then detail: one request per posting, so these take a title filter ----

def rippling(org, title_filter=None, on_stub=None):
    s, _, b = _fetch(f"https://api.rippling.com/platform/api/ats/v1/board/{quote(org)}/jobs")
    if s in MISSING:
        return [], None
    rows = json.loads(b)
    if not isinstance(rows, list):
        raise BoardClosed(f"rippling {org}: unexpected payload {str(rows)[:80]}")
    # One row per job PER LOCATION. Emerald's 34 rows were 20 jobs on 2026-10-14, and
    # counting rows overstated the board by 70%. The uuid is the job.
    jobs = {}
    for r in rows:
        wl = r.get("workLocation")
        loc = (wl or {}).get("label", "") if isinstance(wl, dict) else (wl or "")
        j = jobs.setdefault(r.get("uuid"), _blank(
            title=r.get("name", ""),
            url=r.get("url") or f"https://ats.rippling.com/{org}/jobs/{r.get('uuid')}",
            department=(r.get("department") or {}).get("label", ""), _locs=[]))
        if loc and loc not in j["_locs"]:
            j["_locs"].append(loc)
    stubs = [{**j, "location": " | ".join(j["_locs"])} for j in jobs.values()]

    def one(st):
        _, _, h = _fetch(st["url"])
        m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
        jp = json.loads(m.group(1))["props"]["pageProps"]["apiData"]["jobPost"]
        d = jp.get("description") or {}
        body = " ".join(_strip(d.get(k)) for k in ("role", "company") if d.get(k)) \
            if isinstance(d, dict) else _strip(d)
        return {**st, "title": jp.get("name") or st["title"], "text": body,
                "department": (jp.get("department") or {}).get("name") or st["department"],
                "posted": (jp.get("createdOn") or "")[:10],
                "company": jp.get("companyName") or ""}
    return _details(stubs, one, title_filter, f"rippling {org}", on_stub), len(stubs)


def bamboohr(org, title_filter=None, on_stub=None):
    """A wrong org redirects to www.bamboohr.com with HTTP 200, so the final host decides.
    A real empty board answers {"meta":{"totalCount":0}}."""
    base = f"https://{org}.bamboohr.com"
    s, final, b = _fetch(base + "/careers/list")
    if s in MISSING or (urlparse(final).hostname or "") != f"{org}.bamboohr.com".lower():
        return [], None
    d = json.loads(b)
    rows = d.get("result") if isinstance(d, dict) else d
    rows = (rows.get("data") or []) if isinstance(rows, dict) else (rows or [])
    total = ((d.get("meta") or {}).get("totalCount") if isinstance(d, dict) else None)
    total = len(rows) if total is None else total

    def loc(x):
        x = x or {}
        return ", ".join(v for v in (x.get("city"), x.get("state"), x.get("country")) if v)
    stubs = [_blank(title=r.get("jobOpeningName", ""), url=f"{base}/careers/{r.get('id')}",
                    location=loc(r.get("location")) or loc(r.get("atsLocation")),
                    department=r.get("departmentLabel") or "",
                    _id=r.get("id")) for r in rows if isinstance(r, dict)]

    def one(st):
        _, _, b2 = _fetch(f"{base}/careers/{st['_id']}/detail")
        jo = (json.loads(b2).get("result") or {}).get("jobOpening") or {}
        return {**st, "text": _strip(jo.get("description")),
                "posted": (jo.get("datePosted") or "")[:10],
                "url": jo.get("jobOpeningShareUrl") or st["url"],
                "department": jo.get("departmentLabel") or st["department"],
                "location": loc(jo.get("location")) or loc(jo.get("atsLocation"))
                or st["location"]}
    return _details(stubs, one, title_filter, f"bamboohr {org}", on_stub), total


def breezy(org, title_filter=None, on_stub=None):
    s, _, b = _fetch(f"https://{org}.breezy.hr/json")
    if s in MISSING:
        return [], None
    rows = json.loads(b)
    stubs = [_blank(title=j.get("name", ""), url=j.get("url", ""),
                    location=(j.get("location") or {}).get("name", ""),
                    department=j.get("department") or "",
                    posted=(j.get("published_date") or "")[:10],
                    company=(j.get("company") or {}).get("name", "")) for j in rows]

    def one(st):
        _, _, h = _fetch(st["url"])
        ld = _jsonld_posting(h)
        return _ld_record(ld, st) if ld else None
    return _details(stubs, one, title_filter, f"breezy {org}", on_stub), len(rows)


def icims(slug, title_filter=None, on_stub=None):
    """slug is the host label, careers-rambus for careers-rambus.icims.com. The board's
    search page is a client-rendered shell, but its in_iframe=1 variant is server-rendered
    at 20 per page, and /sitemap.xml lists every posting. Each posting page carries JSON-LD
    with the employer's name. A host that does not exist serves a 404 'gone' page.
    An internal-<co> host is the employee-only board and cannot be read."""
    host = slug if "." in slug else f"{slug}.icims.com"
    try:
        s, _, sm = _fetch(f"https://{host}/sitemap.xml")
    except BoardClosed:
        # Some tenants forward the whole host to an iCIMS Career Site on the company's own
        # domain (PDF Solutions -> careers.pdf.com, Rivian -> careers.rivian.com) and 403 the
        # sitemap. The list page says where, in a script redirect. That site's own job API
        # is public; it is the board, not a way round a block.
        _, _, h = _fetch(f"https://{host}/jobs/search?pr=0&in_iframe=1")
        m = re.search(r"location\.href\s*=\s*'https?:\\?/\\?/([^'\\/]+)", h)
        if not m:
            raise
        return _jibe(m.group(1), title_filter, on_stub)
    if s in MISSING:
        return [], None
    urls = {}
    for u in re.findall(r"<loc>\s*([^<]*/jobs/(\d+)/[^<]*)</loc>", sm):
        urls.setdefault(u[1], _unamp(u[0]).strip())
    titles = {}
    for pr in range(0, 500):
        _, _, h = _fetch(f"https://{host}/jobs/search?pr={pr}&in_iframe=1")
        found = re.findall(r'href="[^"]*/jobs/(\d+)/[^"]*"[^>]*title="\d+ - ([^"]+)"', h)
        new = [(i, t) for i, t in found if i not in titles]
        if not new:
            break
        titles.update((i, html.unescape(t)) for i, t in new)
        time.sleep(PACE)
    ids = sorted(set(urls) | set(titles), key=int)
    stubs = [_blank(title=titles.get(i, ""),
                    url=urls.get(i) or f"https://{host}/jobs/{i}/job") for i in ids]

    def one(st):
        _, _, h = _fetch(st["url"].split("?")[0] + "?in_iframe=1")
        ld = _jsonld_posting(h)
        return _ld_record(ld, st) if ld else None
    return _details(stubs, one, title_filter, f"icims {host}", on_stub), len(ids)


def _jibe(host, title_filter=None, on_stub=None):
    """An iCIMS Career Site (Jibe) at <host>/api/jobs: every posting with its body, 100 a
    page, with totalCount. Bulk, so title_filter and on_stub only shape what is returned."""
    out, total, page = {}, None, 1
    while True:
        s, _, b = _fetch(f"https://{host}/api/jobs?page={page}&limit=100")
        if s in MISSING:
            return [], None
        d = json.loads(b)
        total = d.get("totalCount", 0) if total is None else total
        jobs = [j.get("data", j) for j in d.get("jobs") or []]
        new = [j for j in jobs if str(j.get("req_id") or j.get("slug")) not in out]
        for j in new:
            out[str(j.get("req_id") or j.get("slug"))] = _blank(
                title=j.get("title", ""),
                text=" ".join(_strip(j.get(k)) for k in ("description", "responsibilities",
                                                         "qualifications") if j.get(k)),
                url=f"https://{host}/jobs/{j.get('slug') or j.get('req_id')}",
                location=j.get("location_name") or ", ".join(
                    x for x in (j.get("city"), j.get("state"), j.get("country")) if x),
                department=j.get("department") or "",
                posted=(j.get("posted_date") or j.get("create_date") or "")[:10],
                company=j.get("hiring_organization") or "")
        if not new or len(out) >= (total or 0):
            break
        page += 1
        time.sleep(PACE)
    recs = list(out.values())
    if on_stub is not None:
        for r in recs:
            on_stub(dict(r))
    if title_filter is not None:
        recs = [r for r in recs if title_filter(r["title"])]
    return recs, len(out)


def oracle_hcm(tenant, site, pod="us2", title_filter=None, on_stub=None):
    """Oracle Recruiting Cloud. The list carries a 267-character teaser, so the body is one
    request per posting. siteNumber is not a usable control (some pods accept any site),
    and a tenant that does not exist does not answer at all: Oracle's edge holds the
    request and returns a 504 after about a minute. So a wrong tenant raises BoardClosed
    here rather than returning None. That is the one reader with no clean not-found."""
    B = f"https://{tenant}.fa.{pod}.oraclecloud.com/hcmRestApi/resources/latest"
    stubs, off, total = [], 0, None
    while True:
        f = (f"findReqs;siteNumber={site},facetsList=LOCATIONS%3BWORK_LOCATIONS%3BTITLES,"
             f"limit=200,offset={off},sortBy=POSTING_DATES_DESC")
        s, _, b = _fetch(f"{B}/recruitingCEJobRequisitions?onlyData=true&expand="
                         f"requisitionList.secondaryLocations,flexFieldsFacet.values&finder={f}",
                         timeout=60)
        if s in MISSING:
            return [], None
        it = (json.loads(b).get("items") or [{}])[0]
        total = it.get("TotalJobsCount", 0) if total is None else total
        page = it.get("requisitionList") or []
        stubs += page
        off += len(page)
        if not page or off >= (total or 0):
            break
        time.sleep(PACE)
    root = f"https://{tenant}.fa.{pod}.oraclecloud.com/hcmUI/CandidateExperience/en/sites/{site}"
    stubs = [_blank(title=r.get("Title", ""), url=f"{root}/job/{r.get('Id')}",
                    location=r.get("PrimaryLocation") or "",
                    department=r.get("Department") or r.get("JobFamily")
                    or r.get("JobFunction") or "",
                    posted=(r.get("PostedDate") or "")[:10], _id=r.get("Id")) for r in stubs]

    def one(st):
        _, _, b2 = _fetch(f"{B}/recruitingCEJobRequisitionDetails?expand=all&onlyData=true"
                          f"&finder=ById;Id=%22{st['_id']}%22,siteNumber={site}", timeout=60)
        j = (json.loads(b2).get("items") or [{}])[0]
        body = " ".join(_strip(j.get(k)) for k in ("ExternalDescriptionStr",
                                                   "ExternalResponsibilitiesStr",
                                                   "ExternalQualificationsStr") if j.get(k))
        return {**st, "title": j.get("Title") or st["title"], "text": body}
    return _details(stubs, one, title_filter, f"oracle_hcm {tenant}", on_stub), total


def jobvite(org, title_filter=None, on_stub=None):
    """A wrong org redirects to jobvite.com's support page with ?invalid=1 and HTTP 200.
    /jobs/positions is the whole list; /jobs alone is a landing page on some boards
    (loanDepot showed none there and 34 here)."""
    base = f"https://jobs.jobvite.com/{quote(org)}"
    lst, nl = base + "/jobs/positions?", ""
    s, final, h = _fetch(lst)
    # Some boards redirect /jobs/positions to the company's own site (Kodiak Sciences,
    # 2026-10-31); /search?nl=1 still lists every job there and on loanDepot.
    if s not in MISSING and "invalid=1" not in final and "jobs.jobvite.com" not in final:
        lst, nl = base + "/search?nl=1&", "?nl=1"     # job pages redirect too without it
        s, final, h = _fetch(lst)
    if s in MISSING or "invalid=1" in final or "jobs.jobvite.com" not in final:
        return [], None
    seen = {}
    for p in range(0, 200):
        if p:
            _, _, h = _fetch(f"{lst}p={p}")
        # The title can sit directly in the link (NuScale) or in a div inside it (loanDepot).
        new = [(i, t) for i, t in re.findall(
            rf'href="/{re.escape(org)}/job/([A-Za-z0-9]+)"[^>]*>(.*?)</a>', h, re.I | re.S)
            if i not in seen]
        if not new:
            break
        seen.update((i, " ".join(_strip(t).split())) for i, t in new)
        time.sleep(PACE)
    stubs = [_blank(title=t, url=f"{base}/job/{i}{nl}") for i, t in seen.items()]

    def one(st):
        _, _, h2 = _fetch(st["url"])
        ld = _jsonld_posting(h2)
        return _ld_record(ld, st) if ld else _jobvite_html(h2, st)
    return _details(stubs, one, title_filter, f"jobvite {org}", on_stub), len(seen)


def _jobvite_html(page, stub):
    """A Jobvite job page with no JSON-LD (Meltwater, 2026-11-05: every one of its 58 pages)
    still carries the body in div.jv-job-detail-description and the department and place in
    p.jv-job-detail-meta. Without this the stub was saved as a title with no text."""
    m = re.search(r'class="jv-job-detail-description"[^>]*>(.*?)'
                  r'(?:<div class="jv-job-detail-bottom-actions"|<div class="jv-share-widget")',
                  page or "", re.S)
    if not m:
        return None
    rec = {**stub, "text": _strip(m.group(1))}
    t = re.search(r'<h2 class="jv-header"[^>]*>(.*?)</h2>', page, re.S)
    if t and _strip(t.group(1)).strip():
        rec["title"] = " ".join(_strip(t.group(1)).split())
    meta = re.search(r'<p class="jv-job-detail-meta"[^>]*>(.*?)</p>', page, re.S)
    if meta:
        parts = [" ".join(_strip(x).split()).replace(" ,", ",").strip(" ,")
                 for x in re.split(r"<span class=.jv-inline-separator.></span>", meta.group(1))]
        parts = [x for x in parts if x]
        if parts and not rec.get("department"):
            rec["department"] = parts[0]
        if len(parts) > 1 and not rec.get("location"):
            rec["location"] = parts[-1]
    return rec


def phenom(host, path="us/en", title_filter=None, on_stub=None):
    """Phenom career sites live on the company's own host. The tenant code in the page
    (refNum, YELPUS) is ignored by the search endpoint, so the HOST identifies the board.
    path is the locale prefix the site uses, us/en or global/en. A host that is not a
    Phenom site answers 404 or 405 on /widgets."""
    country, lang = (path.split("/") + ["en"])[:2]
    size, total, frm, rows = 50, None, 0, []
    while True:
        body = {"lang": f"{lang}_{country}", "deviceType": "desktop", "country": country,
                "pageName": "search-results", "ddoKey": "refineSearch", "from": frm,
                "size": size, "jobs": True, "counts": True, "all_fields": ["category"],
                "keywords": "", "global": True, "selected_fields": {}, "siteType": "external"}
        s, _, b = _fetch(f"https://{host}/widgets", data=json.dumps(body).encode(),
                         headers={"Content-Type": "application/json"}, method="POST",
                         missing=(404, 405, 410))
        if s in (404, 405, 410):
            return [], None
        try:
            r = json.loads(b).get("refineSearch") or {}
        except ValueError:
            return [], None
        if not r:
            return [], None
        total = r.get("totalHits", 0) if total is None else total
        page = (r.get("data") or {}).get("jobs") or []
        rows += page
        frm += len(page)
        if not page or frm >= total:
            break
        time.sleep(PACE)
    stubs = [_blank(title=j.get("title", ""), url=f"https://{host}/{path}/job/{j.get('jobId')}",
                    location=j.get("location") or j.get("cityStateCountry") or "",
                    department=j.get("category") or "",
                    posted=(j.get("postedDate") or "")[:10]) for j in rows]

    def one(st):
        _, _, h = _fetch(st["url"])
        ld = _jsonld_posting(h)
        return _ld_record(ld, st) if ld else None
    return _details(stubs, one, title_filter, f"phenom {host}", on_stub), total


def taleo(slug, section, title_filter=None, max_details=None, on_stub=None):
    """Taleo Enterprise, <slug>.taleo.net/careersection/<section>. The search page is
    client-rendered; the sitemap lists every posting and each posting page carries JSON-LD.
    The sitemap has no titles, so a title filter saves nothing here: it runs after each
    fetch, and every posting still costs a request."""
    host = f"{slug}.taleo.net"
    s, _, sm = _fetch(f"https://{host}/careersection/sitemap.jss?portalCode={quote(section)}"
                      "&lang=en")
    if s in MISSING or "<urlset" not in sm:
        return [], None
    urls = {}
    for u in re.findall(r"<loc>\s*([^<]*jobdetail\.ftl\?job=([A-Za-z0-9]+)[^<]*)</loc>", sm):
        urls.setdefault(u[1], _unamp(u[0]).strip())
    stubs = [_blank(url=u) for u in urls.values()]

    def one(st):
        _, _, h = _fetch(st["url"])
        ld = _jsonld_posting(h)
        return _ld_record(ld, st) if ld else None
    # max_details caps the fetches when only a sample is wanted (the live controls). The
    # total still reports every posting in the sitemap.
    out = _details(stubs[:max_details] if max_details else stubs, one, None, f"taleo {slug}")
    if on_stub is not None:          # titles exist only after the fetch here
        for r in out:
            on_stub(dict(r))
    if title_filter is not None:
        out = [r for r in out if title_filter(r["title"])]
    return out, len(urls)


def taleo_be(org, host, code, cws="37", title_filter=None, on_stub=None):
    """Taleo Business Edition, the small-company product on <x>.tbe.taleo.net. The list
    pages through a session: the "next" link only works with the cookie from the first
    page, so this keeps a cookie jar. A wrong org serves a page titled "Taleo Business
    Edition" with no requisitions."""
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(
        http.cookiejar.CookieJar()))
    root = f"https://{host}"
    s, _, h = _fetch(f"{root}/{code}/ats/careers/v2/searchResults?org={quote(org)}&cws={cws}",
                     opener=op)
    if s in MISSING:
        return [], None
    seen = {}
    for _ in range(200):
        found = re.findall(r'href="[^"]*viewRequisition\?[^"]*rid=(\d+)"[^>]*>\s*([^<]*?)\s*</a>', h)
        new = [i for i, _ in found if i not in seen]
        # Each row links twice, once on the title and once on a "View" button, in either
        # order. Taking the first anchor named every posting "View".
        for i, t in found:
            t = html.unescape(t).strip()
            if t and t.lower() not in ("view", "apply", "view job", "apply now") and \
                    not seen.get(i):
                seen[i] = t
            seen.setdefault(i, "")
        nxt = re.search(r'href="([^"]*searchResults\?next[^"]*)"', h)
        if not new or not nxt:
            break
        time.sleep(PACE)
        _, _, h = _fetch(root + _unamp(nxt.group(1)), opener=op)
    if not seen and re.search(r"<title>\s*Taleo Business Edition\s*</title>", h):
        return [], None
    stubs = [_blank(title=t, url=f"{root}/{code}/ats/careers/v2/viewRequisition?org={org}"
                    f"&cws={cws}&rid={i}") for i, t in seen.items()]

    def one(st):
        _, _, h2 = _fetch(st["url"], opener=op)
        ld = _jsonld_posting(h2)
        if ld:
            return _ld_record(ld, st)
        i = h2.find("oracletaleocwsv2-job-description")
        j = h2.find("oracletaleocwsv2-button-navigation", i + 40)
        seg = h2[i:j if j > i else i + 60000]
        loc = re.search(r"Location\s*</[^>]+>\s*(?:<[^>]+>\s*)*([^<]{2,80})<", h2)
        return {**st, "text": " ".join(_strip(seg[seg.find(">") + 1:]).split()),
                "location": loc.group(1).strip() if loc else ""}
    return _details(stubs, one, title_filter, f"taleo_be {org}", on_stub), len(seen)


def workatastartup(slug, title_filter=None, on_stub=None):
    """YC's Work at a Startup. For a YC company with no ATS this IS the job board: the
    company posts there and its own careers page links there. Read through the public
    mirror at ycombinator.com/companies/<slug>/jobs, whose job pages carry JSON-LD;
    workatastartup.com itself needs a login for bodies. YC publishes the company's
    website beside its jobs, which is the ownership check."""
    s, _, h = _fetch(f"https://www.ycombinator.com/companies/{quote(slug)}/jobs")
    if s in MISSING:
        return [], None
    m = re.search(r'data-page="([^"]+)"', h)
    if not m:
        raise BoardClosed(f"workatastartup {slug}: page carried no data-page payload")
    p = json.loads(html.unescape(m.group(1))).get("props") or {}
    co = p.get("company") or {}
    rows = p.get("jobPostings") or []
    stubs = [_blank(title=j.get("title", ""),
                    url="https://www.ycombinator.com" + j["url"] if j.get("url", "").startswith("/")
                    else j.get("url", ""),
                    location=j.get("location") or "", department=j.get("prettyRole") or "",
                    company=co.get("name") or j.get("companyName") or "") for j in rows]

    def one(st):
        _, _, h2 = _fetch(st["url"])
        ld = _jsonld_posting(h2)
        return _ld_record(ld, st) if ld else None
    return _details(stubs, one, title_filter, f"workatastartup {slug}", on_stub), len(rows)


# ------------------------------------------------------------------ the registry
READERS = {"greenhouse": greenhouse, "ashby": ashby, "lever": lever,
           "smartrecruiters": smartrecruiters, "workday": workday,
           "workable": workable, "gem": gem, "jazzhr": jazzhr, "pinpoint": pinpoint,
           "teamtailor": teamtailor, "successfactors": successfactors,
           "rippling": rippling, "bamboohr": bamboohr, "breezy": breezy, "icims": icims,
           "oracle_hcm": oracle_hcm, "jobvite": jobvite, "phenom": phenom, "taleo": taleo,
           "taleo_be": taleo_be, "workatastartup": workatastartup}

# Detected, and deliberately NOT read. Each refused scripted reads on 2026-10-14, and the
# rule is to record that and stop rather than work around it.
BLOCKED = {
    "eightfold": "HTTP 403 'Not authorized for PCSX' on /api/apply/v2/jobs for PayPal and "
                 "Starbucks on the first request, 2026-10-14. Netflix earlier gave 429 then 403.",
    "wellfound": "HTTP 403 on the first request to wellfound.com/company/<slug>/jobs, "
                 "2026-10-14.",
}


def read(provider, slug, extra=None, title_filter=None, max_details=None, on_stub=None):
    """One entry point for every provider, taking discover_board.py's (provider, slug,
    extra) as it comes. Returns (postings, total) like the readers themselves."""
    if provider in BLOCKED:
        raise BoardClosed(f"{provider} blocks scripted reads: {BLOCKED[provider]}")
    if provider not in READERS:
        raise NotImplementedError(f"no reader for {provider!r}")
    ex = dict(extra or {})
    fn = READERS[provider]
    params = inspect.signature(fn).parameters
    kw = {k: v for k, v in (("title_filter", title_filter), ("on_stub", on_stub))
          if v is not None and k in params}
    if provider == "workday":
        return workday(slug, ex.get("site"), ex.get("server", "wd1"), **kw)
    if provider == "oracle_hcm":
        return oracle_hcm(slug, ex["site"], ex.get("pod", "us2"), **kw)
    if provider == "phenom":
        return phenom(slug, ex.get("path", "us/en"), **kw)
    if provider == "taleo":
        if "section" not in ex:
            raise ValueError("taleo needs section=, the careersection number on the page")
        return taleo(slug, ex["section"], max_details=max_details, **kw)
    if provider == "taleo_be":
        return taleo_be(slug, ex["host"], ex["code"], ex.get("cws", "37"), **kw)
    if provider == "successfactors":
        return successfactors(slug, ex.get("company"), ex.get("tld", "com"))
    if provider == "teamtailor" and ex.get("host"):
        return teamtailor(slug, host=ex["host"])
    return fn(slug, **kw)

# ------------------------------------------------------------------ filters
# Deliberately over-inclusive. See failure 1 in the module docstring.
TITLE_WIDE = re.compile(
    r"agent|\bAI\b|\bML\b|machine learning|eval|quality|test|QA\b|SDET|governance|"
    r"developer experience|platform|reliab|infrastructure|architect|product owner|"
    r"product manag|principal|staff|director|\bVP\b|vice president|head of", re.I)

SIGNALS = {
    "eval":    re.compile(r"\beval(uat\w+|s)?\b|golden.{0,12}(set|dataset)|trace replay|scenario test|"
                          r"measurement framework|\bLLMOps\b", re.I),
    "agent-q": re.compile(r"agent.{0,40}(behaviou?r|test|quality|retr|governance)|guardrail|hallucinat|"
                          r"red.?team|non.?determinis", re.I),
    "voice":   re.compile(r"\bvoice\b|\bIVR\b|speech|\bASR\b|text.to.speech|\bTTS\b|telephon", re.I),
    "ai-test": re.compile(r"AI to (generate|write|create|identify|analyz|analys)|AI.{0,25}test case|"
                          r"test case.{0,30}(AI|LLM)|(LLM|AI|GenAI).{0,35}(test automation|test coverage)", re.I),
}

# ------------------------------------------------------------------ controls
# OFFLINE: parsers and the registry, no network, run before every command.
_LD_FIXTURE = ('<script type="application/ld+json">{"@context":"http://schema.org","@graph":'
               '[{"@type":"WebPage"},{"@type":"JobPosting","title":"Data Engineer",'
               '"description":"&lt;p&gt;Build pipelines&lt;/p&gt;","datePosted":"2026-10-01T00:00",'
               '"hiringOrganization":{"@type":"Organization","name":"Acme"},"jobLocation":'
               '[{"address":{"addressLocality":"Reno","addressRegion":"NV","addressCountry":'
               '{"name":"US"}}}]}]}</script>')


_JV_FIXTURE = ('<h2 class="jv-header">\n AI Engineer\n </h2><p class="jv-job-detail-meta">'
               'Engineering<span class=\'jv-inline-separator\'></span>Hybrid Remote<span>,</span>'
               '\n Hyderabad,\n India\n </p><div class="jv-job-detail-description" ng-non-bindable>'
               '<h3>Description</h3><p><div>Build agents</p></div>'
               '<div class="jv-job-detail-bottom-actions">')


def selftest():
    bad = []
    ld = _jsonld_posting(_LD_FIXTURE)
    rec = _ld_record(ld or {}, _blank(url="u"))
    want = {"title": "Data Engineer", "posted": "2026-10-01", "company": "Acme",
            "location": "Reno, NV, US"}
    for k, v in want.items():
        if rec.get(k) != v:
            bad.append(f"JSON-LD {k}: got {rec.get(k)!r}, wanted {v!r}")
    if " ".join(rec.get("text", "").split()) != "Build pipelines":
        bad.append(f"JSON-LD body not stripped to text: {rec.get('text')!r}")
    jv = _jobvite_html(_JV_FIXTURE, _blank(url="u", title="stub"))
    if not jv or " ".join(jv.get("text", "").split()) != "Description Build agents":
        bad.append(f"Jobvite page without JSON-LD: body not read: {jv and jv.get('text')!r}")
    elif (jv["title"], jv["department"], jv["location"]) != \
            ("AI Engineer", "Engineering", "Hybrid Remote, Hyderabad, India"):
        bad.append(f"Jobvite page fields wrong: {jv['title']!r} {jv['department']!r} "
                   f"{jv['location']!r}")
    if _jobvite_html("<html>Just a moment...</html>", _blank(url="u")) is not None:
        bad.append("Jobvite fallback invented a posting from a page with no description")
    if _jsonld_posting('<script type="application/ld+json">{"@type":"Organization"}</script>'):
        bad.append("an Organization block was taken for a JobPosting")
    if _xtag("<d><![CDATA[<b>x</b>]]></d>", "d") != "<b>x</b>" or \
            _xtag("<d>&lt;b&gt;x&lt;/b&gt;</d>", "d") != "<b>x</b>":
        bad.append("_xtag does not read CDATA and escaped text alike")
    u = "/x/searchResults?next&rowFrom=10&amp;sortOrder=null&currentTime=17&section=2"
    if _unamp(u) != u.replace("&amp;", "&"):
        bad.append(f"_unamp mangled a URL: {_unamp(u)!r}")
    # The registry must agree with what discovery calls readable, in both directions:
    # discovery claiming a platform nobody reads is the "0 jobs" trap this file exists for.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import discover_board as DB
        if set(DB.READABLE) != set(READERS):
            bad.append(f"discover_board.READABLE and READERS disagree: "
                       f"{sorted(set(DB.READABLE) ^ set(READERS))}")
        if set(getattr(DB, "BLOCKED", ())) != set(BLOCKED):
            bad.append("discover_board.BLOCKED and sweep_board.BLOCKED disagree")
        for p in list(READERS) + list(BLOCKED):
            if p not in DB.ATS:
                bad.append(f"{p} has a reader but discovery has no fingerprint for it")
    except ImportError as e:
        bad.append(f"discover_board.py not importable beside sweep_board.py: {e}")
    if set(READERS) & set(BLOCKED):
        bad.append(f"listed as both readable and blocked: {set(READERS) & set(BLOCKED)}")
    for b in bad:
        print("  " + b, file=sys.stderr)
    print(f"sweep_board offline: 12 parser checks, {len(READERS)} readers and {len(BLOCKED)} "
          f"blocked platforms reconciled with discover_board, {len(bad)} failure(s)")
    return 1 if bad else 0


# LIVE: two real boards per provider and one slug that must not exist. Every real slug
# below was read off the company's own careers page, or the platform publishes an owner
# name that matches, and each was checked against the board's own page on 2026-10-14.
# (label, slug, extra, owner token the platform must publish or None)
LIVE = {
    "workable": ([("Anvilogic", "anvilogic-inc", {}, "anvilogic"),
                  ("Alphatec", "atec-spine", {}, "alphatec")], ("zzqqnope-control", {})),
    "gem": ([("Rootly", "rootly", {}, None), ("Cloudanix", "cloudanix-com", {}, None)],
            ("zzqqnope-control", {})),
    "jazzhr": ([("H2O.ai", "h2oai", {}, None), ("RedSeal", "redseal", {}, None)],
               ("zzqqnope-control", {})),
    "pinpoint": ([("Codexis", "codexis", {}, None), ("Revolve", "revolve", {}, None)],
                 ("zzqqnope-control", {})),
    "teamtailor": ([("Sully.ai", "sullyai", {}, "sully"), ("Tibber", "tibber", {}, "tibber")],
                   ("zzqqnope-control", {})),
    "successfactors": ([("PACCAR", "career012", {"company": "paccarinc", "tld": "eu"}, "paccar"),
                        ("Vail Resorts", "jobs.vailresortscareers.com", {}, "vail")],
                       ("www.example.com", {})),
    "rippling": ([("Terray", "terraytx", {}, "terray"),
                  ("Emerald", "emeraldx", {}, "emerald")], ("zzqqnope-control", {})),
    "bamboohr": ([("Research Solutions", "researchsol", {}, None),
                  ("Leona Bio", "leonabio", {}, None)], ("zzqqnope-control", {})),
    "breezy": ([("Vaxart", "vaxart-inc", {}, "vaxart")], ("zzqqnope-control", {})),
    "icims": ([("Rambus", "careers-rambus", {}, "rambus"),
               ("Exponent", "careers-exponent", {}, "exponent"),
               # forwards to its own iCIMS Career Site, read through /api/jobs
               ("PDF Solutions", "careers-pdf", {}, "pdf")], ("careers-zzqqnope", {})),
    "oracle_hcm": ([("Infoblox", "efpv", {"site": "CX_1", "pod": "us6"}, None),
                    ("Southwest Gas", "ebtw", {"site": "CX_1", "pod": "us2"}, None)],
                   ("zzqqnope", {"site": "CX_1", "pod": "us2"})),
    "jobvite": ([("NuScale", "nuscale-power", {}, "nuscale"),
                 ("loanDepot", "loandepot", {}, "loandepot"),
                 # /jobs/positions redirects to kodiak.com; read through /search?nl=1
                 ("Kodiak Sciences", "kodiak-science", {}, "kodiak"),
                 # job pages carry no JSON-LD; bodies come from the page markup
                 ("Meltwater", "meltwater", {}, None)], ("zzqqnope-control", {})),
    # ThredUp's JSON-LD carries hiringOrganization with an EMPTY name, so no owner check.
    "phenom": ([("ThredUp", "careers.thredup.com", {"path": "us/en"}, None),
                ("Yelp", "www.yelp.careers", {"path": "us/en"}, "yelp")],
               ("www.example.com", {"path": "us/en"})),
    "taleo": ([("Weyerhaeuser", "weyerhaeuser", {"section": "10000"}, "weyerhaeuser")],
              ("zzqqnope-control", {"section": "10000"})),
    # Business Edition pages carry no JSON-LD and no owner field.
    "taleo_be": ([("Nektar", "NEKTAR", {"host": "phg.tbe.taleo.net", "code": "phg04"}, None),
                  ("Puma Biotechnology", "PUMABIOTECH",
                   {"host": "phf.tbe.taleo.net", "code": "phf03"}, None)],
                 ("ZZQQNOPE", {"host": "phg.tbe.taleo.net", "code": "phg04"})),
    "workatastartup": ([("Overlap", "overlap", {}, "overlap"),
                        ("The Prompting Company", "the-prompting-company", {}, "prompting")], ("zzqqnope-control", {})),
}
# A board that is real and empty must come back as 0, never as None.
LIVE_EMPTY = {"bamboohr": ("LimaCharlie", "refractionpoint"), "pinpoint": ("Everi", "everi")}
# Oracle cannot say "no such tenant"; its control must raise BoardClosed instead.
NOT_FOUND_RAISES = {"oracle_hcm"}


def page_count(provider, slug, extra):
    """The count a person sees on the board's own human page, from a different request than
    the reader uses. None where the page is client-rendered and shows nothing to count."""
    ids = lambda pat, h: len(set(re.findall(pat, h)))      # noqa: E731
    if provider == "jazzhr":
        return ids(r"/apply/([A-Za-z0-9]{8,12})/", _fetch(f"https://{slug}.applytojob.com/apply")[2])
    if provider == "teamtailor":
        return ids(r"/jobs/(\d+)-", _fetch(f"https://{slug}.teamtailor.com/jobs")[2])
    if provider == "breezy":
        return ids(r'href="/p/([a-z0-9]+)-', _fetch(f"https://{slug}.breezy.hr/")[2])
    if provider == "rippling":
        # The page renders 20 and then "Show more", so a count of 20 is only a floor.
        n = ids(r"/jobs/([0-9a-f\-]{36})", _fetch(f"https://ats.rippling.com/{slug}/jobs")[2])
        return n if n < 20 else None
    if provider == "icims":
        n, seen = 0, set()
        for pr in range(0, 500):
            h = _fetch(f"https://{slug}.icims.com/jobs/search?pr={pr}&in_iframe=1")[2]
            new = set(re.findall(r"/jobs/(\d+)/[^\"'?]+/job", h)) - seen
            if pr == 0 and not new and "window.top.location.href" in h:
                return None      # a redirect stub to a Career Site whose page is script-built
            if not new:
                return len(seen)
            seen |= new
    if provider == "phenom":
        m = re.search(r'"totalHits"\s*:\s*(\d+)', _fetch(
            f"https://{slug}/{extra.get('path', 'us/en')}/search-results")[2])
        return int(m.group(1)) if m else None
    if provider == "workatastartup":
        h = _fetch(f"https://www.workatastartup.com/companies/{slug}")[2]
        m = re.search(r'data-page="([^"]+)"', h)
        return len((json.loads(html.unescape(m.group(1)))["props"].get("company") or {})
                   .get("jobs") or []) if m else None
    return None


def live(providers, plant=False, sample=3):
    """Run the live controls. Returns the number of failed checks."""
    fails, rows = 0, []
    provs = providers or list(LIVE)
    for pi, prov in enumerate(provs):
        reals, (bad_slug, bad_extra) = LIVE[prov]
        for ri, (label, slug, extra, owner) in enumerate(reals):
            if plant and pi == 0 and ri == 0:
                owner = "zzqq-planted-wrong-owner"
            n = [0]

            def sampler(_t, n=n):
                n[0] += 1
                return n[0] <= sample
            problems = []
            try:
                stubs_seen = []
                posts, total = read(prov, slug, extra, title_filter=sampler,
                                    max_details=sample, on_stub=stubs_seen.append)
            except BoardClosed as e:
                rows.append((prov, label, "BLOCKED", "", "", str(e)[:70]))
                fails += 1
                continue
            except Exception as e:                          # noqa: BLE001
                rows.append((prov, label, "CRASH", "", "", f"{type(e).__name__}: {e}"[:90]))
                fails += 1
                continue
            if total is None or not total:
                problems.append(f"board reported {total}")
            # on_stub must see the WHOLE board (Taleo only has titles after a fetch, so it
            # sees the sample), or a caller's roster silently covers part of it.
            if "on_stub" in inspect.signature(READERS[prov]).parameters and \
                    len(stubs_seen) != (len(posts) if prov == "taleo" else total):
                problems.append(f"on_stub saw {len(stubs_seen)} of {total} postings")
            if not posts:
                problems.append("no postings came back")
            for p in posts:
                if not p.get("title") or not p.get("url"):
                    problems.append(f"posting without title or url: {p.get('url') or p}")
                    break
            urls = [p.get("url") for p in posts]
            if len(set(urls)) != len(urls):
                problems.append(f"{len(urls) - len(set(urls))} duplicate posting urls: one "
                                f"row per location counted as separate jobs?")
            bodied = sum(1 for p in posts if len(p.get("text") or "") >= 200)
            if posts and bodied < 0.8 * len(posts):
                problems.append(f"only {bodied} of {len(posts)} carry a full description")
            if owner and not any(owner in (p.get("company") or "").lower() for p in posts):
                problems.append(f"owner {owner!r} not published; got "
                                f"{sorted({p.get('company') for p in posts})[:2]}")
            try:
                pc = page_count(prov, slug, extra)
            except BoardClosed:
                pc = None
            if pc is not None and total is not None and pc != total:
                problems.append(f"board page shows {pc}, reader reports {total}")
            fails += bool(problems)
            rows.append((prov, label, total, pc if pc is not None else "-",
                          f"{bodied}/{len(posts)}", "; ".join(problems) or "ok"))
        # The slug that must not exist.
        try:
            posts, total = read(prov, bad_slug, bad_extra, title_filter=lambda t: False)
            ok = prov not in NOT_FOUND_RAISES and posts == [] and total is None
            verdict = "ok" if ok else f"WRONG: returned {len(posts)} postings, total {total}"
        except BoardClosed as e:
            ok = prov in NOT_FOUND_RAISES
            verdict = "ok (raised BoardClosed, Oracle's only answer)" if ok else f"WRONG: {e}"
        fails += not ok
        rows.append((prov, f"nonsense {bad_slug}", "None", "", "", verdict))
        if prov in LIVE_EMPTY:
            label, slug = LIVE_EMPTY[prov]
            posts, total = read(prov, slug)
            ok = posts == [] and total == 0
            fails += not ok
            rows.append((prov, f"{label} (real, empty)", total, "", "",
                         "ok" if ok else "WRONG: a real empty board must be 0, not None"))
    for r in rows:
        print(f"  {r[0]:15} {str(r[1])[:30]:30} total={str(r[2]):6} page={str(r[3]):5} "
              f"bodies={r[4]:6} {r[5]}")
    print(f"sweep_board live: {len(rows)} checks across {len(provs)} provider(s), "
          f"{fails} failure(s)")
    return fails


def main(argv):
    if len(argv) >= 2 and argv[1] == "--selftest":
        return selftest()
    if selftest() != 0:
        print("FAILED: offline controls do not pass. Not fetching anything.")
        return 1
    if len(argv) >= 2 and argv[1] == "--live":
        rest = [a for a in argv[2:] if not a.startswith("--")]
        unknown = [p for p in rest if p not in LIVE]
        if unknown:
            print(f"no live controls for {unknown}; have {sorted(LIVE)}")
            return 2
        return 1 if live(rest, plant="--plant-failure" in argv) else 0
    if len(argv) < 3:
        print(__doc__); return 2
    kind, org = argv[1], argv[2]
    if kind == "workday" and len(argv) > 3 and "=" not in argv[3]:
        jobs, total = workday(org, argv[3], argv[4] if len(argv) > 4 else "wd1")
    else:
        extra = dict(a.split("=", 1) for a in argv[3:] if "=" in a)
        jobs, total = read(kind, org, extra)
    if total is None:
        print(f"{org} via {kind}: the platform says this board does not exist. That is a "
              f"wrong slug, not an empty board. Read the slug off the careers page.")
        return 3

    # Guard 2: prove the pull was complete before drawing any conclusion from it.
    if total and len(jobs) < total:
        print(f"!! INCOMPLETE: pulled {len(jobs)} of {total}. Fix pagination before trusting this.")
        return 1
    print(f"{org} via {kind}: {len(jobs)} postings, board reports {total}. COMPLETE.\n")

    cands = [j for j in jobs if TITLE_WIDE.search(j["title"])]
    print(f"{len(cands)} of {len(jobs)} titles pass the wide filter. Candidates with signal:\n")
    n = 0
    for j in cands:
        hits = {k: p.search(j["text"]) for k, p in SIGNALS.items()}
        hits = {k: m for k, m in hits.items() if m}
        if not hits: continue
        n += 1
        print(f'  {j["title"][:70]}   [{j["posted"]}]  {", ".join(hits)}')
        print(f'    {j["url"]}')
        # Guard 3: the context is printed because the keyword is not the finding.
        for k, m in hits.items():
            s = max(0, m.start() - 130)
            frag = " ".join(j["text"][s:m.end() + 130].split())
            print(f'      {k}: ...{frag}...')
        print()
    print(f"{n} candidates for review. These are CANDIDATES, not findings: read each "
          f"matched line above and decide. Keyword hits have produced false positives on "
          f"every board swept so far.")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
