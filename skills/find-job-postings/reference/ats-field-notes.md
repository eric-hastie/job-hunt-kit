# ATS and job-board field notes

Per-platform mechanics: how to pull a board, how to prove a req is open, and the
control that separates a wrong slug from a real zero. Read the section for a
platform before writing a fetcher for it. Every note was proven against a real
posting and a planted fake one on 2026-09-16 (Reno mechanics search) unless
dated otherwise.

## Applicant tracking systems

**Paycom** (`paycomonline.net/v4/ats/web.php/jobs?clientkey=<KEY>`). Most common
dealership ATS in Northern Nevada. SPA; its preview API
(`portal-applicant-tracking.us-cent.paycomonline.net/api/ats/job-posting-previews/search`)
returns 401 without the Authorization header the page itself sends, so capture it
from the page's own request and page with `skip`/`take`, or render in Chrome and
read `a[href*="/jobs/"]` (10 per page, reconcile against the "N Results" count;
coordinate clicks work on the pager, JS `.click()` does not). Liveness, server-side:
the detail page `.../portal/<KEY>/jobs/<id>` carries `og:title` for a real job; a
fake id returns the same 200 shell without it.

**Hireology** (`careers.hireology.com/<slug>`). Bad slug returns 404 (clean
control). The listing needs rendering, but each `/<slug>/<id>/description` serves
JobPosting JSON-LD server-side and a bad id 404s. `validThrough` is often in the
past on reqs still listed: board membership decides. Vanity `*.hireology.careers`
sites may never render; per-store slugs found through search work.

**VeraHR / HR Drive** (`<org>.verahr-hiring.com`, formerly `hrdrivehiring.com`).
Server-rendered `/job/<id>/<slug>` links, JSON-LD per job. Bad subdomain redirects
to `login.verahr-hiring.com`.

**HotlinkHR** (`jobapp-new.hrhotlink.com/c/<id>/en-US/OpenPositions/Show`).
Server-rendered position list; no per-job URL exists, so link the list page.

**Phenom** (AutoNation, WM-style career sites). The SSR `search-results?keywords=`
and `phApp.ddo` location params are ignored or unreliable (a nonsense keyword
returned the same 892 hits; "Reno, NV" returned 0). POST `https://<host>/widgets`
with `ddoKey: refineSearch` plus `keywords` or `selected_fields:{"state":["Nevada"]}`;
a fake state returns 0. A pulled job page returns HTTP 410. The record's `applyUrl`
often leads to Workday, whose CXS endpoint gives full text and a 404 control.

**Workday.** A whole tenant can be down while Workday is up (Lithia, all day
2026-09-16): CXS returns 422 for any site name and the page redirects to
`community.workday.com/maintenance-page`. That is a closed door, not a wrong slug;
prove it by hitting another tenant. Location facets can omit the state
(Bridgestone: "010944 Auburn", and Auburn, Lincoln, Roseville, Quincy exist in
several states); settle it with the store number on the brand's store pages.

**iCIMS.** Host can differ by region within one brand (Discount Tire NV on
`jobs-discounttire.icims.com`, CA on `jobs-americastire.icims.com`). A closed or
fake req returns HTTP 410, so read the host off each posting's apply link before
calling a req dead.

**Oracle HCM Candidate Experience.**
`hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList.secondaryLocations&finder=findReqs;siteNumber=CX_n,limit=25,offset=N`
returns `TotalJobsCount`. Detail
`recruitingCEJobRequisitionDetails?expand=all&onlyData=true&finder=ById;Id="<id>",siteNumber=CX_n`
returns 0 items for a dead or fake id. The location/radius finder returned empty
for WM, so pull the whole board and filter. `siteNumber` is in the page markup.
Read the body: WM's Reno diesel posting carried a Bremerton, WA template.

**UKG.** Pro: POST `recruiting.ultipro.com/<tenant>/JobBoard/<boardId>/JobBoardView/LoadSearchResults`
with an empty QueryString returns the full board and `totalCount`. Ready
(entertimeonline): `/ta/rest/ui/recruitment/companies/%7C<companyId>/job-requisitions?offset=0&size=200`
returns `_paging.total` and full descriptions; a fake company id returns 410.

**Jibe.** `/api/jobs?location=...&stretch=100&stretchUnit=MILES` does a radius
search (Costco, Crash Champions, FedEx Freight). `/api/jobs/<id>` returns an
identical shell for fake ids, so verify through the Workday apply URL instead.
`careers.fedex.com` 403s its Jibe API even in the browser and its Workday board
reports 0 (disabled); only rendering with a category filter works there. FedEx
Ground mechanics work for contractors and never appear on FedEx's board.

**SuccessFactors RMK.** Templates vary (Vail: `tr.data-row`; others: tiles).
`/sitemap.xml` lists every job URL regardless of template.

**ADP MyJobs.** `myjobs.adp.com/public/staffing/v1/career-site/<domain>` returns the
orgoid unauthenticated, but requisitions also need a `postingChannelId` not yet
found. Rendered, `?FIELD1=<State>` filters by state and location plus 100 mi works.

**Paradox career sites** (jobs.vioc.com, jobs.loves.com, avisbudgetgroup.jobs).
Server-rendered at `/<list>/page/N` with title link and street address per item.
A full crawl is cheap.

**CareerPlug brand boards** (`<brand>-careers.careerplug.com/jobs?page=N`). The
location parameter is ignored; sweep every page. A live req redirects to
`/apps/new`, a bad id to sign-in. Franchise boards keep evergreen reqs open for
years (Big O: 2020 to 2022 postings still accepting applications); show the date.

**Caliber Collision** publishes a full `rss.xml` (2,820 items), simpler than its
client-rendered search.

**Dayforce** candidate pages contain "Page not found!" in the i18n bundle on every
page, and **Rippling** pages carry "no longer available" in script text on live
jobs. Run dead-phrase checks on visible text with scripts stripped, or read the
embedded job record.

**DirectEmployers** `*.dejobs.org` / `*.jobs` pages are 2.8 KB Nuxt shells with no
title text. Use its Solr API; a wrong `x-origin` returns a 404 JSON error, which is
not a job absence.

## Public sector

**NEOGOV / GovernmentJobs.** `governmentjobs.com/careers/<bad-slug>` returns 200 and
redirects to the homepage: check that the final URL still contains
`/careers/<slug>`. Slugs are unguessable (Douglas County NV `douglasconv`, Nevada
County CA `mynevadacounty`, South Lake Tahoe `slaketahoe`). Board:
`GET /careers/home/index?agency=<slug>&page=N` with `X-Requested-With: XMLHttpRequest`,
10 per page, stop when a page adds no new ids. Liveness:
`/careers/<slug>/jobs/newprint/<id>` 404s for pulled or fake ids (the normal job
page returns 200 for fakes). Radius search `/jobs?keyword=&location=&distance=`
prints "N jobs found". Ids ending `-1` are syndicated copies from other systems and
outlive the source req; check the source board. State of Nevada moved from
careers.nv.gov (SuccessFactors) to NEOGOV agency `nv`.

**JobAps.** Bulletin pages render for closed recruitments with "Job Type: Open" in
the header. Membership in `JobBoard.asp` plus the Filing Deadline field is the test.

**CivicEngage (CivicPlus) Jobs.** Detail body loads only when rendered. The RSS
feed `RSSFeed.aspx?CommunityJobs=False&ModID=66&CID=All-0` is partial (Plumas: 11
items against 43 listings).

**EdJoin.** `Home/LoadJobs?rows=100&page=N&...&keywords=` returns JSON with
`totalRecords` only when every parameter from the site's own request is present;
a trimmed query returns 500. Posting pages 404 for bad ids.

**PowerSchool Applicant Tracking** (`<district>.atenterprise.powerschool.com/ats/job_board`).
JS shell; render, page with `start_index=100`, total from the header ("301-394").

**USAJOBS without a key.** POST `https://www.usajobs.gov/Search/ExecuteSearch` with
JSON (`Keyword`, `LocationName:[..]`, `Radius`, `Page`) returns Jobs, Total and
Pager. `/job/<id>` 404s for a bad id and shows "Accepting applications" when open.
National Guard technician reqs are usually restricted to current members.

**CalCareers.** ASP.NET postback; render, choose "100 Jobs", parse Job Control,
Location and Filing Deadline. Broad keywords hit the 100-row cap, so use narrow ones.

**Tyler MUNIS Self Service** needs a cookie jar kept from a first request to `/mss/`.

## Retail and brand sites

**Tesla.** Akamai-blocked server-side. From a Chrome tab on tesla.com,
`fetch('/cua-api/apps/careers/state')` returns every listing with location lookup
tables, and `/cua-api/careers/job/<id>` the full posting (404 for a fake id).

**Walmart.** `CP-<store>-<jobcode>` detail pages render with `active: true` for
pairs that are not open. Only membership in the Open roles list proves a req.

**Costco.** The jobs API returns evergreen example reqs, and Costco's own page says
a listing is not an opening. Always `unconfirmed`.

**Dealer.com and DealerInspire** dealer sites 403 every server-side fetch (Akamai)
and many are not permitted in the Chrome extension; WebFetch got through some.
**DealerFire / Dealer eProcess** `careers.aspx` pages can hold postings inside
`<!-- -->`; strip HTML comments before reading self-hosted dealer postings.

## Tooling limits met

- Chrome `javascript_tool` truncates results near 1,000 characters and blocks output
  containing query-string ids (ZipRecruiter `jid`, Indeed `jk`). Stash text in
  `window._t` and read slices.
- `chrome-headless-shell --dump-dom` hangs on some sites (jobs.ryder.com). Wrap
  every render in a subprocess timeout; `timeout` is not installed on this Mac.
- A 404 to curl on a link the site's own nav points at is a render trigger, not a
  zero (truckeetahoeairport.com).
- Search-engine results were dead in 5 of 5 spot checks. Use them to find the ATS,
  never as evidence a req is open.

## Route 1b: a candidate slug the provider itself confirms

Added 2026-10-02 (sweep of 127 public West Coast companies).

**Large companies' careers pages frequently name the ATS and never print the slug.**
`cloudflare.com/careers` references `BladeGenericGreenhouseJobsApi`; `asana.com/jobs`
carries `greenhouse_jobs_list.filters.label`. No slug appears in the HTML, in any JS
bundle reachable from it, or in search results, and both companies read as boardless
through markup detection and route 8 while running live Greenhouse boards (Cloudflare
405 open reqs, Asana live).

Three providers publish the board owner's **own name**, so a candidate slug can be
*proven* rather than guessed. This is not slug guessing: the provider states whose
board it is, and a wrong candidate is rejected by the name, not by an empty result.

```
greenhouse  GET boards-api.greenhouse.io/v1/boards/<slug>   -> {"name": "Cloudflare"}
            fake slug: HTTP 404
ashby       GET jobs.ashbyhq.com/<slug>                      -> <title>Ramp Jobs</title>
            fake slug: HTTP 200 with the bare title "Jobs"   (the API 404s)
lever       GET jobs.lever.co/<slug>                         -> <title>Highspot</title>
            fake slug: HTTP 404
```

Generate candidates from the company's distinctive tokens (joined, hyphenated, first
token, first two) and accept only on a name match. Run it **before** crawling the
careers page: it is a handful of API calls against ~20 page fetches and it is no less
authoritative.

**A substring name test is not enough.** `"alpha" in "alphaomegasemiconductor"` matched
an unrelated and empty Ashby board called "Alpha" to ALPHA & OMEGA SEMICONDUCTOR, which
would have been filed as a verified-empty board: a false zero wearing a finding's
clothes. Compare token sets instead. One token standing in for a multi-token company
name is accepted only when it is the company's first token, at least six characters,
**and** a second distinctive company token appears in the board's own text.

## Workday: the locale segment and the three-digit pod

Both of these produce a wrong site name, which 422s, which reads as an empty board.

- **`re.search` returns the first match, and the first Workday URL on the page is often
  the useless one.** Amgen's careers page carries a bare
  `amgen.wd1.myworkdayjobs.com/en-US` before the real
  `amgen.wd1.myworkdayjobs.com/en-US/Careers/login`. A single-match pattern captured
  `en-US` as the site name; the real site is `Careers`, with 1,727 open requisitions.
  Collect **every** Workday URL in the markup, discard the ones whose site name is
  really a locale (`^[a-z]{2}([-_][A-Za-z]{2})?$`) or a page name (`login`, `job`,
  `jobs`, `search`, `apply`, `home`, `details`), and verify each survivor.
- **Pods are not single-digit.** `wd[0-9]` misses `wd108` (Ambarella) and `wd503`
  (A10 Networks). Use `wd[0-9]+`.
- **Do not screen a Workday site name against a generic bad-slug list.** The common
  list contains `careers`, and a Workday site is very often named exactly `Careers`.
  Screening Amgen's board out this way discarded 1,727 reqs.
- **A 422 on every site name of one tenant is a dead tenant, not a wrong slug**, and it
  is only provable with a control. A10 Networks returns 422 on CXS and HTTP 500 on its
  board page for every pod in its own markup, while `duckcreek/duckcreekcareers/wd1`
  answers 200 with 37 reqs from the same code in the same run. Record that as blocked.
  Without the control it is indistinguishable from a slug error.

## iCIMS lists the employee-only board first

AMD's `amd.com/en/corporate/careers.html` names `internal-amd.icims.com` and nothing
else; the public board is `careers-amd.icims.com`, reachable only from
`careers.amd.com`. Collect every iCIMS host and prefer one without `internal` in it.
An internal board cannot be read at all, so taking the first match yields a provider
that is correct and a board that is unreadable.

**iCIMS search is a client-rendered shell and its size does not vary.**
`careers-amd.icims.com/jobs/search?searchKeyword=X` returned 50,925 / 50,937 / 50,961 /
50,957 bytes for an empty query, "FinOps", "Site Reliability" and a nonsense term, with
zero job hrefs in any of them. A near-constant byte count across a real and an invented
query is the tell. Route 7.

## A bare User-Agent earns a 429 from Akamai-fronted corporate sites

`10xgenomics.com` and `8x8.com` returned HTTP 429 to every attempt with a User-Agent
header alone, including retries, and both read as "no domain, no board". The full
browser header set cleared both on the first try:

```
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8
Accept-Language: en-US,en;q=0.9
Accept-Encoding: identity
Upgrade-Insecure-Requests: 1
Sec-Fetch-Dest: document / Sec-Fetch-Mode: navigate / Sec-Fetch-Site: none
```

A 429 or a 5xx is a closed door. It is never evidence of absence, and it must not be
allowed to reach a zero.

## Two self-inflicted traps worth naming

- **A read cap corrupts board JSON.** Reading only the first 1.2 MB of
  `boards-api.greenhouse.io/v1/boards/cloudflare/jobs?content=true` truncated it
  mid-string. The pull reported 0 roles. Never cap a response you are going to parse
  as JSON; cap HTML fetches only.
- **Detection cost, not network latency, can be the whole runtime.** Running ~50
  provider regexes over every fetched page cost 0.85s per 280 KB page, which at ~20
  pages a company is GIL-serialised CPU and starved the network entirely. Almost every
  page contains none of the provider literals, so gate the regex list behind a
  substring scan for them: 0.85s to 0.007s, a 120x cut, with planted-positive controls
  proving the gate does not suppress a real match.

## Domain resolution: the hostname is not its own evidence

Verifying a guessed company domain by looking for the company's name in
`title + host + body` lets any lookalike certify itself. `10xgenomics.ai` is a
Squarespace "Coming Soon" page and it passed, because the token being checked for was
sitting in the hostname being checked. Match on title and body text only, and reject
placeholder titles (`Coming Soon`, `Under Construction`) alongside the parked-domain
patterns. A one-token company name such as `8x8` can never reach a two-hit threshold,
so one hit has to be enough for it.

## Public-company universes, proven 2026-10-02 on a 127-company SEC EDGAR chunk

**The registrant's own 10-K is the authoritative domain source.** Guessing a domain
from the company name and verifying it by looking for the name on the page produces
confident wrong answers that no page-level test can catch: `harmonic.com` is J&J's
scalpel brand and its `<title>` carries the word "Harmonic", so Harmonic Inc (HLIT)
resolved to `jnjmedtech.com`. Adding an industry suffix is worse, because typosquat
pages echo the queried name back: that route returned `nvidiainc.com` for NVIDIA and
`navanbio.com` for Navan. Strip tags from the 10-K, collect `www.<x>.<tld>` matches,
drop filing boilerplate (XBRL namespaces, auditors, transfer agents, exchanges,
proxy hosts, social links) and rank by token overlap with the registrant name. That
returned `harmonicinc.com`, `mazetx.com` and `kyvernatx.com` correctly. Then fetch
the result, because a filing can name a domain the company has since dropped.

**A blank-check SPAC's filing names its merger target, so the probe lands on the
target's board.** Two GigCapital shells resolved to BigBear.ai's iCIMS board and
Launchpad Cadenza resolved to Together AI's Greenhouse board with 77 requisitions.
A blank-check registrant has no employees and no board; reject the match on SIC code
rather than recording the target's reqs against the shell. The same shape appears
after an acquisition: Matterport's board is now CoStar's Eightfold board, so the
roles are the acquirer's.

**Oracle HCM ignores `siteNumber`.** A planted `CX_9999` returned the same 976
requisitions as Fortinet's real `CX_2001`. The **host** is the tenant identifier and
the only thing worth controlling on; `siteNumber` cannot be used as a control. Read
both off the careers page: the markup carries the full
`https://<pod>.fa.<region>.oraclecloud.com/hcmUI/CandidateExperience/en/sites/<CX_n>`.
Confirmed on Fortinet `edel.fa.us2`, Glaukos `ekpl.fa.us6`, Harmonic `egmn.fa.us2`,
ICU Medical `eduu.fa.us2`.

**An Ashby slug can contain a space.** Grindr's is the legal entity name `Grindr LLC`.
Unencoded it raises `InvalidURL: URL can't contain control characters`, which reads as
a bad slug; `urllib.parse.quote` it. Both `grindr` and `Grindr` 404.

**Workday: filter the `wdN` token before picking the site, and allow three digits.**
A slug written `tenant/wd5/site` parsed positionally takes `wd5` as the site name and
404s, which looks exactly like a wrong slug. That rejected Guidewire, Illumina and
Intapp. Defaulting to `wd1` 422s on tenants that are not there: MiniMed is `wd108`
(tenant `mdtkangaroo`, Medtronic's internal code name for the diabetes spin-off, which
no name-derived guess reaches) and Halozyme is `wd115`. Parse the canonical board URL
when one exists rather than the free-text slug.

**SmartRecruiters `totalFound: 0` is genuinely ambiguous**, not a failure. A real but
empty board and a nonexistent org both return it. The separator is the page title: a
nonexistent org serves the generic `<title>SmartRecruiters Job Search</title>` and a
real one serves a branded title. Record it as unknown, never as a rejected slug.

**Reject these as slugs, in addition to the existing list:** `app`, `__assets__`,
`gig`, and anything that is a static-asset or generic path segment. `jobs.jobvite.com/__assets__/`
produced `__assets__` as an org for two companies, and `app.teamtailor.com` produced `app`.

**Providers met here with no handler in the route 1-2 table**, all recorded rather
than reported as zero:

- **ADP WorkforceNow** (Energous, Lantronix, Emerald, Modular Medical).
  `workforcenow.adp.com/mascsr/default/careercenter/public/events/staffing/v1/job-requisitions?cid=<GUID>`
  returns titles, post dates and pay bands unauthenticated. The `cid` is the tenant
  GUID and a nonsense one 404s. Emerald's cid is valid but its endpoint returns an
  empty list while aggregators show ~37 roles, so an empty list there is not a zero.
- **Paycom portal** (LENZ) `paycomonline.net/v4/ats/web.php/portal/<32-hex>/career-page`.
- **BrightMove** (Iridex), white-labelled onto the company's own domain.
- **CATS (catsone.com)** (Healthcare Triangle).
- **Avature** (Intuit), **Eightfold** (Netflix `netflix`, CoStar `costar`). Eightfold's
  `domain=` query parameter is the company's public web domain, not the slug: passing
  `netflix.net` returned nothing while `netflix.com` returned 111 hits, and a board
  reporting zero that way is a parameter bug, not an empty board.
- **Getro** (`jobs.generalcatalyst.com`) is a VC job aggregator rather than an ATS, but
  it preserves outbound ATS URLs and was the route that found Maze Therapeutics.

**Two false-zero shapes worth knowing.** A careers page can print "no open positions"
as stale static text directly above a live requisition (LENZ). And a client-rendered
careers page can contain the ATS name nowhere in its HTML at all: Maze renders
Greenhouse client-side, Grindr's page renders "0 jobs total" to any non-JS reader while
27 roles are live, and Fastly and Lyft both hide Greenhouse boards (`fastly`, `lyft`)
behind shells. All four were findable only off-site, which is why route 8 runs early.

**`curl` needs `--compressed`** on hosts that serve compressed bytes regardless
(inhibrx.com). Without it the body is binary garbage and a grep over it reads as a
clean zero.

## Workday, two fetcher defects found 2026-10-02 on a public-company sweep

Both are fixed in `tools/sweep_board.py`. They are recorded because each one is silent.

- **The posting URL came from the wrong field.** `workday()` read `externalPath` out of
  the job DETAIL payload, which does not have it. Every requisition therefore got the
  bare board URL (`https://visa.wd5.myworkdayjobs.com/Visa`) and no req could be
  re-verified or handed to anyone. The detail payload carries **`externalUrl`**, already
  absolute. The stub's `externalPath` joined to the board base is the fallback, so the
  URL is never just the board root.
- **`workday()` now takes `title_filter`.** It fetches one detail request per
  requisition, and Visa's board is 786 reqs while Workday's own is 374, so a whole-board
  pull does not finish inside a caller's timeout. The STUB list already carries the
  title, so pass a predicate and only the survivors cost a fetch. The board's own
  reported total still comes back unchanged, every stub is still pulled and still
  reconciled against that total, and the count that passed the filter is printed, so a
  too-narrow filter is loud instead of a silent zero. **Make the predicate the union of
  every title pattern you might keep**, because a decision that needs the body cannot be
  made at the stub stage.

**A title filter passing zero is not an empty board.** With a filter in play, `len(jobs)
== 0` and `total > 0` means the board is full of reqs that did not match. Reporting that
as an empty board, and then "failing" a nonsense-slug control, said Veritone's 7 live
reqs were a wrong slug.

**Controls exist for more than the big four.** A nonsense slug on `bamboohr` returns
HTTP 200 serving BambooHR's own marketing homepage, and on `pinpoint` it returns 404,
while the real empty boards return `{"meta":{"totalCount":0},"result":[]}` and
`{"data":[]}`. Without those two controls, Galaxy Gaming and Everi both read as wrong
slugs when both are genuinely empty.

## Shazamme, a careers platform with no readable feed

Zoom Communications runs **Shazamme** at `www.careers.zoom.us`. It is a careers-site
platform, not an ATS, and its job list is a client-rendered widget backed by Firebase.
There is no JSON feed, no `JobPosting` JSON-LD, and `/feed/rss2` carries blog posts
only, while `/sitemap.xml` lists marketing pages and no requisitions. It is route 7 and
nothing else. There is no fetch handler for it.

## Probing the conventional portal hosts is worth one round of requests

A careers path that redirects off-domain leaves nothing behind to detect:
`veeva.com/careers` lands on `careers.veeva.com` and `remitly.com/careers` on
`careers.remitly.com`, and neither landing page's HTML contains its own absolute URL, so
a crawler scanning page bodies sees no portal. Two fixes together closed it: put each
page's FINAL URL into the text you scan, and probe `careers.<domain>`, `jobs.<domain>`,
`<label>.jobs`, `apply.`, `talent.`, `recruiting.`, `join.`, `work.` and `career.`
directly. `<label>.jobs` is how `amazon.jobs` is found.

When excluding the company's own host from portal candidates, exclude **only the exact
host**. Excluding every subdomain of it is what hid `careers.veeva.com` in the first
place.

## Enterprise vendor hosts that are not tenant slugs

`app.eightfold.ai` is Eightfold's own application host, and reading `app` off it as
Microsoft's slug produced a board URL belonging to nobody. So did `vs-errors.eightfold.ai`,
which is a telemetry host. Reject `app`, `global`, `main`, `portal`, `recruiting` and
`hcm` as slugs and fall back to the company's own portal URL.

**Workable has two public endpoints and they disagree.** `apply.workable.com/api/v3/accounts/<org>/jobs`
returns 404 for orgs that `apply.workable.com/api/v1/widget/accounts/<org>` serves normally:
`identiv` 404s on v3 and returns its one live requisition on v1/widget. Checking only v3
rejected a real board as a wrong slug. Try both before calling a Workable slug wrong; the
nonsense-slug control 404s on v1/widget too, so the check still fails correctly.

**An existence check is not an ownership check, and this is the expensive one.** Every
provider test in this file answers "does this board exist", and a wrong slug can pass all
of them while belonging to a different company. Four did here, each returning HTTP 200
with real requisitions: Eventbrite resolved to Ashby `andera`, a seed-stage startup whose
reqs are "Founding AI Engineer"; Life360 to Greenhouse `placerlabs`, the location-analytics
company Placer Labs; Honest Company to Greenhouse `phxpreview`, an empty staging board; and
Masimo to Workday `danaher/DanaherJobs`, where Workday's fuzzy `searchText` even returned 84
hits for "Masimo" although Danaher does not own it. Three came from a same-domain crawl
picking a provider URL out of third-party content on the page, which the never-leave-the-domain
rule does not prevent, because the foreign URL was embedded in the company's own page.

The check that catches it: **compare the slug and the board's own job titles against the
company.** Flag every accepted board whose slug shares no token with the company name, then
clear each one by hand into exactly three buckets, and reject anything that fits none:

- an **opaque tenant identifier** (Oracle pod `edel.fa.us2`, an ADP GUID, a Paycom 32-hex
  portal id, a BrightMove `portalGK`), where no overlap is expected;
- a **verified rename**, where the old name is the slug (`tripactions` for Navan,
  `purestorage` for Everpure, `instacart` for Maplebear, `identiv` for INVE);
- an **acquirer or parent board**, which is a real finding but has to be labelled, because
  the requisitions are the larger company's. Juniper is on `hpe/Jobsathpe`, Infinera on
  Nokia's Oracle HCM, Matterport on CoStar's Eightfold `costar`. Nevro is the good case:
  `globusmedical` tenant but the site is `NVRO_Careers`, so those reqs really are Nevro's.
  Workday's site name, not just the tenant, is what tells the two apart.

On a 127-company run this review flagged 21 boards and rejected 4, a 19% error rate among
boards whose slug did not match the company name.

**Correction to the Oracle HCM note above: `siteNumber` validation is pod-dependent, so
neither field is a portable control.** Two pods were tested against a planted
`siteNumber=CX_ZZZNOPE`:

- Fortinet's `edel.fa.us2`: the bogus site returns `TotalJobsCount` 976 **and** a 5-entry
  `requisitionList`, identical to the real `CX_2001`. Both fields are useless here.
- Nokia's pod: the bogus site returns the same `TotalJobsCount` (571) but an **empty**
  `requisitionList`, so there the list length does discriminate.

So do not rely on either field alone. **The host is the tenant identifier and the only
thing worth controlling on.** If the site number has to be verified, check
`requisitionList` and treat a non-empty list as inconclusive rather than as a pass, because
one of the two pods tested blesses any invented site. Nokia also 302s away from
`jobs.nokia.com/hcmRestApi/...`, so the API must be called against the Fusion pod hostname.

**A real ATS org can be an abandoned one, so count is not recency.** SmartRecruiters'
`Masimo` org returns `totalFound: 1` with a correct company field, which passes a
`totalFound != 0` check, but the single requisition is an Android Developer req released
2016-12-14 against 40-plus live openings elsewhere. Read `releasedDate` before treating a
low non-zero count as the company's hiring picture.

**A shared enterprise tenant needs a company filter, or the parent's reqs become the
subsidiary's.** Masimo is a Danaher operating company and its board is
`danaher/DanaherJobs`, which serves 15-plus brands and 1,420 requisitions. Filing that
whole board under Masimo overstates it by a factor of thirty. Post-filtering a Workday pull
does not work, because the list endpoint carries no body text and fetching a posting URL
returns the SPA shell; **push the company name into `searchText`** instead and let Workday's
own full-text index filter, which cut it to 52 Masimo reqs. The ownership evidence is in the
posting body: it opens "At Masimo, one of Danaher's 15+ operating companies".

**The inverse error is as expensive as the false positive, and I made it.** Having caught
four wrong slugs by checking ownership, I then rejected `danaher/DanaherJobs` for Masimo
because I believed Danaher did not own it. That belief was reasoning, not evidence, and it
was wrong. **Resolve an ownership question by reading the posting body or the board's own
company field, never from recollection**; an acquisition inside the last year or two is
exactly the fact least likely to be remembered correctly, and it is the single most common
reason a board legitimately sits under another company's name.

**Scratch files belong in an isolated directory, never a bare `/tmp` path.** With four
agents running in parallel, a `curl -o /tmp/lx.html` that failed with HTTP 000 and wrote
zero bytes left the file holding another agent's markup, and the grep over it returned
content for a page that was never fetched. A failed fetch leaving a stale file in place is
the same false-answer shape as a false zero, and here it produced a false positive instead.
Two defences, both cheap: write scratch files under a per-task directory, and `rm -f` the
target immediately before every fetch so a failed download cannot be read as a successful
one. Watch the bytes-downloaded counter against the parsed result; a non-empty parse from a
zero-byte download is the tell.

## Sixteen more platforms, readable since 2026-10-14

`tools/sweep_board.py` reads all of them; `--live` runs two real boards and one invented
slug per platform against the live sites, and `--live <provider> --plant-failure` proves
the checker fires. What each platform does that a naive reader gets wrong:

**Two platforms return one row per job per LOCATION.** Rippling's board API returned 34
rows for Emerald's 20 jobs, and Workable's widget 40 rows for Alphatec's 29. Counting rows
overstated both boards by 40 to 70 percent. The reader merges on the job id (Rippling
`uuid`, Workable `shortcode`) and joins the locations. The live controls now fail on any
two postings sharing a URL, which is how both were caught.

**A wrong slug looks different on each platform, and three of them answer HTTP 200:**

| Platform | Wrong slug | Real but empty board |
| --- | --- | --- |
| BambooHR | redirects to www.bamboohr.com, 200 | `{"meta":{"totalCount":0}}` |
| JazzHR | HTML board redirects to jazzhr.com, 200; the XML export 404s | |
| Jobvite | redirects to jobvite.com support page with `?invalid=1`, 200 | |
| Taleo Business Edition | 200, page titled "Taleo Business Edition", no requisitions | |
| Workable, Gem, Pinpoint, Teamtailor, Breezy, Rippling, iCIMS, Work at a Startup | 404 | Pinpoint `{"data":[]}` |
| Taleo Enterprise, Oracle-style vendor subdomains | DNS does not resolve | |
| Phenom | 404 or 405 on `/widgets` | |
| Oracle HCM | **no answer**: the edge holds the request about a minute, then 504 | |

Oracle is the only platform that cannot say "no such tenant", so its reader raises
`BoardClosed` there instead of returning nothing. Every other reader returns
`([], None)` for a board that does not exist and `([], 0)` for one that is real and empty.

**A DNS failure means a missing tenant only if the vendor's own domain still resolves.**
Otherwise the network is down, and a run would record every board as a wrong slug. During
one live run on 2026-10-14 the network dropped for a minute: a Taleo detail page timed out
and `taleo.net` itself stopped resolving, and both came back as closed doors, not zeros.

**Never `html.unescape` a URL.** Browsers accept legacy entities with no semicolon, so it
turned Taleo's `&currentTime=` into `¤tTime=` and would turn `&section=` into `§ion=`.
Replace `&amp;` and nothing else.

**Per platform:**

- **iCIMS.** `/sitemap.xml` lists every posting; `/jobs/search?pr=N&in_iframe=1` is the
  server-rendered list at 20 a page with titles. Rambus 66 and Exponent 244 matched
  between the two. JSON-LD per posting names the employer. iCIMS writes the literal
  `UNAVAILABLE` where a region is missing.
- **Oracle HCM.** The careers page shows the same count the API's `TotalJobsCount` gives
  (Infoblox 89). Infoblox posts one title as separate requisitions per city; those are
  distinct ids and are not duplicates.
- **Phenom.** The search endpoint ignores the tenant code (`refNum`), so the board is the
  HOST the careers page lands on, plus the locale path (`us/en`, `global/en`). Splunk lands
  on Cisco's board, `careers.cisco.com/global/en`, which is the acquirer's. ThredUp's
  JSON-LD publishes an empty employer name.
- **Taleo Enterprise.** The search page is client-rendered; `careersection/sitemap.jss`
  lists every posting, and its count matched the page (Weyerhaeuser 168). The sitemap has
  no titles, so a title filter cannot save requests there.
- **Taleo Business Edition.** A different product on `<x>.tbe.taleo.net`, identified by
  `org=` in the link, never by the host label (which is always `tbe`). The next-page link
  works only with the first page's session cookie. Each row links twice, once on a "View"
  button.
- **SuccessFactors.** The classic link `career012.successfactors.eu/career?company=X`
  redirects to the company's RMK site only when sent with
  `&career_ns=job_listing_summary&navBarLevel=JOB_SEARCH`. The RMK `/sitemap.xml` is an RSS
  feed of every posting in every language; the site's search shows one language at a time
  (PACCAR: 207 in US English, 240 in the feed, the rest live Portuguese and UK postings).
- **Jobvite.** `/jobs/positions` is the full list; `/jobs` is a landing page on some boards
  (loanDepot: 0 there, 34 here). An embed names its board only in `data-careersite`.
  Some boards redirect `/jobs/positions` and every job page to the company's own site
  (Kodiak Sciences): `/search?nl=1` lists them and `/job/ID?nl=1` serves the page.
  `sweep_board.jobvite` switches to that when the list redirects off jobvite.com.
- **Workable.** An embed names its board in the widget address,
  `/api/v1/widget/accounts/<slug>`; read naively that yields `api`.
- **Work at a Startup.** It belongs: for a YC company with no ATS it is the board, and the
  company's own careers page links to it. Read it through
  `www.ycombinator.com/companies/<slug>/jobs`, whose job pages carry JSON-LD.
- **Eightfold and Wellfound refuse scripted reads** (`sweep_board.BLOCKED`). Eightfold
  answered 403 `Not authorized for PCSX` on the first request for PayPal and Starbucks;
  Wellfound 403 on the first request. Recorded and not worked around.

**Three more, from the first harvest through these readers (2026-10-14):**

- **An iCIMS host can forward to an iCIMS Career Site** on the company's own domain and
  403 its sitemap. PDF Solutions (`careers-pdf` to `careers.pdf.com`) and Rivian
  (`us-careers-rivian` to `careers.rivian.com`, 809 postings) do. The list page carries a
  `window.top.location.href` script redirect naming the site, and that site's
  `/api/jobs?page=N&limit=100` returns every posting with its body and `totalCount`.
  `sweep_board.icims()` follows it. A host that redirects to a LOGIN instead (McGraw Hill's
  `mheducation`) is an employee board, like AMD's `internal-amd`.
- **Rippling links can carry a locale before the slug**, `ats.rippling.com/en-GB/<slug>/`.
  Read naively the slug is `en-GB` (Eridu).
- **`resources.bamboohr.com` is BambooHR's marketing site**, linked from customers' pages;
  it is never a board (Constella).
