#!/usr/bin/env python3
"""Read an ATS slug off a company's OWN careers page. The step before sweep_board.

    python3 discover_board.py --selftest
    python3 discover_board.py stripe.com
    python3 discover_board.py f5.com paloaltonetworks.com anvilogic.com

WHY THIS IS IN THE SKILL. sweep_board.py takes a slug you already have. Without a
shared discovery step, every project ends up writing its own, worse one.

WHY READING BEATS GUESSING. A guessed slug fails silently and looks exactly like an empty
board. Measured on 2026-10-13 across twenty security companies whose boards could not be
confirmed by name matching: TEN were on a platform sweep_board already reads, with a slug
nothing would guess. F5 is Workday tenant "ffive". A10 Networks is "osv-a10networks".
Vectra AI is greenhouse "vectranetworks", its legacy name. Kai is "kaicyberinc", its legal
name. Mitek is lever "miteksystems-2". Palo Alto Networks is Workday site
"panwexternalcareers", where the tenant matched a guess all along and the site name did not.

AND IT IS BETTER EVIDENCE. A slug printed in a link on the company's own careers page was
published by that company pointing at its own board. That is a stronger claim than a name
match and strictly stronger than the slug-equality rule Ashby and Lever fall back to.
"""
import argparse
import concurrent.futures as cf
import json
import re
import sys
import time
import urllib.request
from urllib.parse import urlparse

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

CAREERS_PATHS = ("/careers", "/company/careers", "/about/careers", "/jobs",
                 "/company/jobs", "/about/jobs", "/en/careers", "/about-us/careers",
                 "/careers/jobs", "/company/about/careers", "/careers.html", "", "/about",
                 "/company")

# sweep_board.py can PULL from these. Its selftest fails if this list and its READERS
# disagree in either direction.
READABLE = ("greenhouse", "ashby", "lever", "smartrecruiters", "workday",
            "workable", "gem", "jazzhr", "pinpoint", "teamtailor", "successfactors",
            "rippling", "bamboohr", "breezy", "icims", "oracle_hcm", "jobvite", "phenom",
            "taleo", "taleo_be", "workatastartup")
# Detected, and refusing scripted reads. Recorded, never worked around. The reason for each
# is in sweep_board.BLOCKED.
BLOCKED = ("eightfold", "wellfound")

ATS = {
    # The for= form is listed first AND the path form excludes "embed", because regex
    # alternation takes the LEFTMOST match rather than the first branch: without the
    # exclusion, `boards.greenhouse.io/embed/...` returns the literal "embed" as a slug.
    "greenhouse": (r"greenhouse\.io/[^\"'\s]*?[?&](?:for|job_board)=([a-z0-9\-_]+)"
                   r"|(?:boards|job-boards)\.greenhouse\.io/(?!embed\b)([a-z0-9\-_]+)"
                   r"|boards-api\.greenhouse\.io/v1/boards/([a-z0-9\-_]+)"),
    "ashby": r"(?:jobs\.ashbyhq\.com|ashbyhq\.com/job-board)/([A-Za-z0-9._%\-]+)",
    "lever": r"jobs\.lever\.co/([A-Za-z0-9_\-]+)",
    "smartrecruiters": r"careers\.smartrecruiters\.com/([A-Za-z0-9_\-]+)",
    "workday": (r"([a-z0-9\-]+)\.(wd\d+)\.myworkdayjobs\.com/"
                r"(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_\-]+)"),
    # Detected and named, not yet readable. A company that lands here is far more useful
    # than one recorded as "no board found": the platform is known and a reader is writable.
    # The widget address names the board after /accounts/; read naively it yields "api"
    # (Stellar Cyber, 2026-10-14).
    "workable": (r"apply\.workable\.com/api/v\d+/widget/accounts/([A-Za-z0-9_\-]+)"
                 r"|apply\.workable\.com/([A-Za-z0-9_\-]+)"),
    # A locale segment can sit before the slug: ats.rippling.com/en-GB/<slug>/jobs (Eridu).
    "rippling": r"ats\.rippling\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9._%\-]+)",
    "bamboohr": r"([A-Za-z0-9_\-]+)\.bamboohr\.com",
    "jazzhr": r"([A-Za-z0-9_\-]+)\.applytojob\.com",
    "recruitee": r"([A-Za-z0-9_\-]+)\.recruitee\.com",
    "breezy": r"([A-Za-z0-9_\-]+)\.breezy\.hr",
    # A regional board keeps its region in the host: swishanalytics.na.teamtailor.com (Swish
    # Analytics, 2026-10-21). Without the optional label the slug came back "na".
    "teamtailor": r"([A-Za-z0-9_\-]+(?:\.[a-z]{2})?)\.teamtailor\.com",
    "personio": r"([A-Za-z0-9_\-]+)\.jobs\.personio",
    "pinpoint": r"([A-Za-z0-9_\-]+)\.pinpointhq\.com",
    "workatastartup": r"workatastartup\.com/companies/([A-Za-z0-9_\-]+)",
    "wellfound": r"wellfound\.com/company/([A-Za-z0-9_\-]+)",
    "oracle_hcm": (r"([a-z0-9\-]+)\.fa\.([a-z0-9]+)\.oraclecloud\.com/hcmUI"
                   r"[^\"'\s]*?sites/([A-Za-z0-9_]+)"),
    "icims": r"([a-z0-9\-]+)\.icims\.com",
    # Business Edition before Enterprise: a TBE host contains ".taleo.net" too, and its
    # identifier is the org= parameter, never the host label (which is always "tbe").
    "taleo_be": (r"([a-z0-9]+)\.tbe\.taleo\.net/([a-z0-9]+)/ats/careers/"
                 r"[^\"'\s<>]*?org=([A-Za-z0-9_]+)"),
    "taleo": r"([a-z0-9\-]+)\.taleo\.net(?:/careersection/(?!iam/|rest/|sitemap)([A-Za-z0-9_]+)/)?",
    # A classic career link carries the company code, and an RMK site (the SAP front end
    # on the company's own host) loads its assets from rmkcdn. Either is readable.
    "successfactors": (r"(career\d*)\.successfactors\.(com|eu)"
                       r"(?:/career\?[^\"'\s<>]*?company=([A-Za-z0-9_]+))?"
                       r"|(rmkcdn)\.successfactors\.com"),
    "eightfold": r"([a-z0-9\-]+)\.eightfold\.ai",
    # The tenant code sits in the asset path. The search endpoint ignores it, so the board
    # is identified by the HOST the careers page landed on; see match_ats.
    "phenom": r"phenompeople\.com/CareerConnectResources/(?:prod/|st/)?((?-i:[A-Z][A-Z0-9]{4,}))/",
    # The embed widget names the board in data-careersite and links only to __assets__.
    "jobvite": (r"jobs\.jobvite\.com/([a-z0-9\-_]+)"
                r"|data-careersite=[\"']([a-z0-9\-_]+)"),
    "gem": r"jobs\.gem\.com/([a-z0-9\-_]+)",
}
# Words that appear where a slug should be. Each was a real false positive: __assets__ for
# three Jobvite companies, cdn for three Phenom ones, api for a Workable one and vs-errors
# for an Eightfold one, all in the 2026-10-14 territory discovery.
JUNK = {"embed", "job_board", "jobs", "careers", "board", "www", "search", "en",
        "company", "about", "index", "home", "apply", "static", "assets", "__assets__",
        "app", "gig", "api", "cdn", "vs-errors", "global", "main", "portal", "recruiting",
        "hcm", "j", "images", "img", "media", "login",
        # resources.bamboohr.com is BambooHR's own marketing site (Constella, 2026-10-14)
        "resources", "www2", "help", "support", "marketplace"}
JUNK_RE = re.compile(r"^(cdn|static|img|images)\d*$", re.I)
# A Workday "site" that is really a locale or a page name. Amgen's careers page carries a
# bare amgen.wd1.myworkdayjobs.com/en-US before the real site, Careers, 1,727 reqs.
WD_NOT_SITE = re.compile(r"^[a-z]{2}([-_][A-Za-z]{2})?$|^(login|job|jobs|search|apply|home|"
                         r"details)$", re.I)


def _junk(slug):
    return not slug or len(slug) < 2 or slug.lower() in JUNK or bool(JUNK_RE.match(slug))


def match_ats(html, final_url=None):
    """(provider, slug, extra) for the first readable platform link in a page.

    final_url is where the careers page actually landed. Phenom and SuccessFactors RMK are
    identified by that host, and a redirect leaves no trace of it in the page body.

    Every match of a fingerprint is tried, not only the first, because the first is often
    junk: an asset path, an employee-only board, a locale where a site name should be.

    The ONLY place the fingerprints are applied. The selftest calls this rather than
    re-implementing it: a shared rule with two entry points has been fixed twice in this
    setup while the two copies disagreed.
    """
    text = (final_url or "") + "\n" + html
    land = urlparse(final_url) if final_url else None
    for prov, pat in ATS.items():
        ms = list(re.finditer(pat, text, re.I))
        if prov == "icims":
            # The employee-only board is often the only one the corporate page names
            # (AMD: internal-amd), and it cannot be read. Prefer any public host.
            ms.sort(key=lambda m: m.group(1).lower().startswith("internal"))
        if prov == "taleo":
            # A login link names the host and no section; the section is what is readable.
            ms.sort(key=lambda m: not m.group(2))
        for m in ms:
            if prov == "workday":
                a, b, c = m.group(1), m.group(2), m.group(3)
                if not _junk(a) and not WD_NOT_SITE.match(c or ""):
                    return prov, a.lower(), {"server": b, "site": c}
                continue
            if prov == "oracle_hcm":
                if not _junk(m.group(1)):
                    return prov, m.group(1).lower(), {"pod": m.group(2), "site": m.group(3)}
                continue
            if prov == "taleo_be":
                tail = re.match(r"[^\"'\s<>]*", text[m.start():]).group(0)
                cws = re.search(r"cws=(\d+)", tail)
                return prov, m.group(3), {"host": f"{m.group(1)}.tbe.taleo.net",
                                          "code": m.group(2),
                                          "cws": cws.group(1) if cws else "37"}
            if prov == "taleo":
                if _junk(m.group(1)) or m.group(1).lower() == "tbe":
                    continue
                return prov, m.group(1).lower(), ({"section": m.group(2)} if m.group(2) else {})
            if prov == "successfactors":
                if m.group(4):                                  # an RMK site
                    if land and land.hostname:
                        return prov, land.hostname, {}
                    continue
                ex = {"tld": m.group(2)}
                if m.group(3):
                    ex["company"] = m.group(3)
                return prov, m.group(1).lower(), ex
            if prov == "phenom":
                if not (land and land.hostname):
                    continue
                loc = re.match(r"^/([a-z]{2,6})/([a-z]{2})(?:/|$)", land.path or "")
                return prov, land.hostname, {"path": f"{loc.group(1)}/{loc.group(2)}"
                                             if loc else "us/en", "refnum": m.group(1)}
            slug = (next((g for g in m.groups() if g), "") or "").strip()
            if not _junk(slug):
                return prov, slug, {}
    # A Teamtailor career site on the company's own host (careers.waitwhile.com,
    # jobs.spot.ai) names no *.teamtailor.com slug anywhere; its assets come from
    # teamtailor-cdn. The host itself serves /jobs.rss, so the host is the board.
    if "teamtailor-cdn.com" in html and land and land.hostname:
        return "teamtailor", land.hostname, {"host": land.hostname}
    return None, None, {}


def fetch_page(url, timeout=20):
    """(final_url, html). The final URL matters: a careers path that redirects to a
    Phenom or RMK host leaves nothing in the page body that names that host."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            # Some hosts send gzip to a client that never asked for it (Altametrics,
            # 2026-10-29); undecoded, the page reads as empty and the board as missing.
            if body[:2] == b"\x1f\x8b":
                import gzip
                body = gzip.decompress(body)
            return r.geturl(), body[:900000].decode("utf-8", "replace")
    except Exception:                                       # noqa: BLE001
        return url, ""


def fetch(url, timeout=20):
    return fetch_page(url, timeout)[1]


def discover(domain, paths=CAREERS_PATHS, pause=0.12):
    """(provider, slug, extra, evidence_url, readable) for one domain."""
    for path in paths:
        url = f"https://{domain}{path}"
        time.sleep(pause)
        final, html = fetch_page(url)
        if not html:
            continue
        prov, slug, extra = match_ats(html, final)
        if prov:
            return prov, slug, extra, url, prov in READABLE
    return None, None, {}, None, False


CONTROLS = [
    # (html, provider, slug). Each string is the shape found on a real careers page.
    ('<a href="https://jobs.ashbyhq.com/cybcube/x">Apply</a>', "ashby", "cybcube"),
    ('<a href="https://swishanalytics.na.teamtailor.com/">Jobs</a>', "teamtailor",
     "swishanalytics.na"),
    ('<a href="https://tibber.teamtailor.com/jobs">Jobs</a>', "teamtailor", "tibber"),
    # A job-alert sign-in link is the only place iTradeNetwork's page names its board.
    # A script that calls the boards API is the only place Wurl's page names its board.
    ('fetch("https://boards-api.greenhouse.io/v1/boards/wurljobs/jobs")', "greenhouse", "wurljobs"),
    ('<a href="https://my.greenhouse.io/users/sign_in?job_board=itradenetworkinc&amp;'
     'source=job_alert">', "greenhouse", "itradenetworkinc"),
    ('<iframe src="https://jobs.lever.co/miteksystems-2"></iframe>', "lever",
     "miteksystems-2"),
    ('<script src="https://boards.greenhouse.io/embed/job_board/js?for=rubrik">',
     "greenhouse", "rubrik"),
    ('<a href="https://boards.greenhouse.io/vectranetworks">Jobs</a>', "greenhouse",
     "vectranetworks"),
    ('window.location="https://ffive.wd5.myworkdayjobs.com/F5_Careers"', "workday",
     "ffive"),
    ('href="https://paloaltonetworks.wd5.myworkdayjobs.com/en-US/panwexternalcareers"',
     "workday", "paloaltonetworks"),
    ('<a href="https://apply.workable.com/anvilogic-inc/">Open roles</a>', "workable",
     "anvilogic-inc"),
    ('<a href="https://careers.smartrecruiters.com/Example">Careers</a>',
     "smartrecruiters", "Example"),
    # The 2026-10-14 platforms, each in the shape it took on a real careers page.
    ('href="https://jobs.gem.com/rootly"', "gem", "rootly"),
    ('<a href="https://h2oai.applytojob.com/apply">', "jazzhr", "h2oai"),
    ('href="https://ats.rippling.com/terraytx/jobs"', "rippling", "terraytx"),
    ('href="https://ats.rippling.com/en-GB/eridu/jobs"', "rippling", "eridu"),
    ('<a href="https://resources.bamboohr.com/x">x</a><a href="https://constella.bamboohr.com/'
     'careers">', "bamboohr", "constella"),
    ('href="https://careers-rambus.icims.com/jobs/intro"', "icims", "careers-rambus"),
    # AMD's corporate page names the employee board first; the public one must win.
    ('<a href="https://internal-amd.icims.com/">x</a><a href="https://careers-amd.icims.com/">y'
     '</a>', "icims", "careers-amd"),
    ('<link href="//d3ig.cloudfront.net/__assets__/x.css"><a href="https://jobs.jobvite.com/'
     '__assets__/a.js"></a><a href="https://jobs.jobvite.com/nuscale-power/jobs">',
     "jobvite", "nuscale-power"),
    ('href="https://apply.workable.com/api/v1/x"><a href="https://apply.workable.com/'
     'atec-spine/">', "workable", "atec-spine"),
    ('href="https://phg.tbe.taleo.net/phg04/ats/careers/v2/jobSearch?act=redirectCws&amp;'
     'cws=37&amp;org=NEKTAR"', "taleo_be", "NEKTAR"),
    ('href="https://weyerhaeuser.taleo.net/careersection/iam/accessmanagement/login.jsf">'
     '<a href="https://weyerhaeuser.taleo.net/careersection/10000/joblist.ftl">', "taleo",
     "weyerhaeuser"),
    ('href="https://career012.successfactors.eu/career?company=paccarinc&amp;site=V2"',
     "successfactors", "career012"),
    ('<script src="https://apply.workable.com/api/v1/widget/accounts/stellar-cyber?details=t'
     'rue">', "workable", "stellar-cyber"),
    ('<script src="https://jobs.jobvite.com/__assets__/scripts/careersite/public/iframe.js">'
     '</script><div class="jv-careersite" data-careersite="nlight"></div>', "jobvite", "nlight"),
    # Must find NOTHING rather than a junk slug.
    ('<a href="https://boards.greenhouse.io/embed/job_board">careers</a>', None, None),
    ('<a href="/careers">Careers</a><p>Email jobs@example.com</p>', None, None),
    ('<a href="https://www.linkedin.com/company/example/jobs/">LinkedIn</a>', None, None),
    ('<script src="https://jobs.jobvite.com/__assets__/x.js"></script>', None, None),
    ('<img src="https://vs-errors.eightfold.ai/x"><a href="https://app.eightfold.ai/c">',
     None, None),
    # Phenom with no landing host cannot be identified, so it must not guess one.
    ('<img src="https://cdn.phenompeople.com/CareerConnectResources/prod/YELPUS/images/a.png">',
     None, None),
    ('href="https://amgen.wd1.myworkdayjobs.com/en-US"', None, None),
    # Teamtailor's CDN with no landing host must not guess a board.
    ('<script src="https://assets-aws.teamtailor-cdn.com/assets/careersite-1.js">', None, None),
]
# (html, final_url, provider, slug, extra subset): fingerprints that need the landing URL.
LANDED = [
    ('<img src="https://cdn.phenompeople.com/CareerConnectResources/prod/YELPUS/images/a.png">',
     "https://www.yelp.careers/us/en", "phenom", "www.yelp.careers", {"path": "us/en"}),
    ('<img src="https://cdn.phenompeople.com/CareerConnectResources/CISCISGLOBAL/i/a.png">',
     "https://careers.cisco.com/global/en/splunk", "phenom", "careers.cisco.com",
     {"path": "global/en"}),
    ('<script src="https://rmkcdn.successfactors.com/x/y.js"></script>',
     "https://jobs.paccar.com/", "successfactors", "jobs.paccar.com", {}),
    ('<a href="https://amgen.wd1.myworkdayjobs.com/en-US">x</a><a href="https://amgen.wd1.'
     'myworkdayjobs.com/en-US/Careers/login">', None, "workday", "amgen", {"site": "Careers"}),
    # Teamtailor on the company's own host (Waitwhile, 2026-10-29).
    ('<script src="https://assets-aws.teamtailor-cdn.com/assets/careersite-1.js">',
     "https://careers.waitwhile.com/jobs", "teamtailor", "careers.waitwhile.com",
     {"host": "careers.waitwhile.com"}),
]


def selftest():
    bad = []
    for html, wp, ws in CONTROLS:
        gp, gs, _ = match_ats(html)
        if (gp, gs) != (wp, ws):
            bad.append(f"{html[:52]!r} -> {(gp, gs)}, wanted {(wp, ws)}")
    # Workday must yield its server and site, which cannot be guessed and without which
    # the board cannot be read at all.
    _, _, extra = match_ats(
        'https://paloaltonetworks.wd5.myworkdayjobs.com/en-US/panwexternalcareers')
    if extra.get("server") != "wd5" or extra.get("site") != "panwexternalcareers":
        bad.append(f"workday extra came back {extra}, wanted wd5/panwexternalcareers")
    # Oracle HCM must yield pod and site.
    _, _, ex2 = match_ats(
        'https://edel.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_2001')
    if ex2.get("pod") != "us2" or ex2.get("site") != "CX_2001":
        bad.append(f"oracle_hcm extra came back {ex2}, wanted us2/CX_2001")
    # Taleo Business Edition must carry the host, code and cws its reader needs.
    _, _, ex3 = match_ats('https://phf.tbe.taleo.net/phf03/ats/careers/v2/jobSearch?act='
                          'redirectCwsV2&cws=37&org=PUMABIOTECH')
    if ex3 != {"host": "phf.tbe.taleo.net", "code": "phf03", "cws": "37"}:
        bad.append(f"taleo_be extra came back {ex3}")
    for html, final, wp, ws, wex in LANDED:
        gp, gs, gex = match_ats(html, final)
        if (gp, gs) != (wp, ws) or any(gex.get(k) != v for k, v in wex.items()):
            bad.append(f"{html[:40]!r} at {final} -> {(gp, gs, gex)}, wanted {(wp, ws, wex)}")
    # Every readable or blocked provider must be a key, or discovery can find what cannot
    # be pulled, and the two lists must not overlap.
    for p in READABLE + BLOCKED:
        if p not in ATS:
            bad.append(f"{p} is listed as readable or blocked but has no fingerprint")
    if set(READABLE) & set(BLOCKED):
        bad.append(f"both readable and blocked: {set(READABLE) & set(BLOCKED)}")
    for b in bad:
        print("  " + b, file=sys.stderr)
    f = sum(1 for _, p, _ in CONTROLS if p)
    print(f"discover_board: {f} must-find, {len(CONTROLS) - f} must-miss, "
          f"{len(LANDED)} landing-URL checks, 3 extra-field checks, "
          f"{len(READABLE) + len(BLOCKED)} provider-list checks, {len(bad)} failure(s)")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("domains", nargs="*")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        rc = selftest()
        print("controls passed" if rc == 0 else "CONTROLS FAILED")
        sys.exit(rc)
    if selftest() != 0:
        sys.exit("FAILED: controls do not pass. Not fetching anything.")
    if not a.domains:
        ap.print_help()
        sys.exit(2)
    out = []
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for dom, res in zip(a.domains, ex.map(discover, a.domains)):
            prov, slug, extra, ev, readable = res
            out.append({"domain": dom, "provider": prov, "slug": slug, "extra": extra,
                        "evidence_url": ev, "readable_by_sweep_board": readable})
            if a.json:
                continue
            if prov:
                tag = ("" if readable else "   (detected, BLOCKS scripted reads)"
                       if prov in BLOCKED else "   (detected, sweep_board cannot pull it yet)")
                print(f"  {dom:30} {prov:16} {slug}"
                      f"{' ' + json.dumps(extra) if extra else ''}{tag}")
            else:
                print(f"  {dom:30} no ATS link on any careers path")
    if a.json:
        print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
