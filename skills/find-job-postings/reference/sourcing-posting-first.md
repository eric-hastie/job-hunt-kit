# Sourcing: posting-first

Use when the company universe is **not** knowable. Healthcare, ops and admin
roles are spread across payers, health systems, ABA providers, digital health
startups, staffing firms and every company with an HR function. There is no list
to enumerate, so you search the postings themselves and let the companies fall
out.

**In posting-first, freshness is the primary sort, not a nice-to-have.** Remote
admin postings pull hundreds of applicants within days, so a two-week-old row is
close to worthless even when it is a perfect fit.

A curated company-first batch can be bolted on as a supplement.

## Transport: fetch server-side first

Verified 2026-08-11: both HiringCafe and Wellfound return their full payload to
a plain request carrying a browser User-Agent.

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 \
(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
curl -s -A "$UA" https://hiringcafe.com/
```

**WebFetch is what gets blocked, not server-side HTTP.** Wellfound 403s WebFetch
and there is no point retrying it, but curl works.

Volume behaviour is untested: one page was fetched, not forty. If Cloudflare or
rate limiting appears at scale, fall back to the in-browser path documented in
`hiringcafe-harvest-method.md` and `wellfound-harvest-method.md`, which is proven
at 42 pages with zero failures. That fallback is expensive: per-origin clipboard
permission, an injected gesture-click button, `javascript_tool` output truncating
at ~1KB, and a 45-second CDP eval timeout. Do not start there.

Never POST to a local `127.0.0.1` receiver from the page. It hangs silently on
Chrome's private-network block and freezes the eval for 45s. A CORS receiver with
`Access-Control-Allow-Private-Network: true` does not help.

## The source registry

Sources are data, not code. One entry per board, so adding a source is filling in
a template and the health probe covers it for free.

`tools/sources.json` is the registry. `python3 tools/sources.py --probe` asserts
every feed still returns its required fields and its recorded row cap, and
`--pull <terms>` harvests across all of them. Vertical-specific sources are
deliberately **not** in there; see `vertical-sources.md`.

Status values, which record what a fetch proved rather than what the site claims:

| Status | Meaning |
| --- | --- |
| `feed` | clean JSON or RSS, pull directly |
| `sample` | serves a fixed recent slice and is **not** queryable |
| `extract` | structured payload inside HTML, needs a parser |
| `follow` | no payload, but real job hrefs to fetch (route 6) |
| `render` | JS shell, needs route 7 |
| `blocked` | 403 or bot challenge to server-side requests |

**A declared total is not an available total.** Himalayas advertises 100,618 jobs
and serves 20, ignoring `limit`, `page`, `offset`, `skip`, `start` and every
search spelling. Remotive is capped at 20 with all params ignored and declares a
total of 20. Both are `sample`, not `feed`.

This is the silent-truncation failure in a new place: 20 rows come back cleanly,
nothing errors, and a query that finds nothing reads as "the market is empty"
when you have seen 0.02% of it. **Record the served cap and assert it on every
run.** A source that quietly changes its cap has drifted.

Each entry records:

| Field | Meaning |
| --- | --- |
| `entry_url` | a page whose payload contains listings |
| `payload` | where the data sits (`__NEXT_DATA__.props.pageProps.ssrHits`) |
| `pagination` | how to advance, and how to know you are done |
| `required_fields` | assert these exist; their absence means the method drifted |
| `id_field` | for dedup across pages and across sources |
| `date_field` | for the freshness sort |
| `ats_field` | if present, the company's real ATS, which is gold |
| `volatile` | values that rotate and must be re-read, never hardcoded |

## The Muse

The largest no-key **general-market** source. Not remote-only, which is what
separates it from most of the registry.

- **Endpoint:** `https://www.themuse.com/api/public/jobs?page=N`, 20 per page,
  results in `results`.
- **Key:** optional, and it raises the rate limit from 500 to 3,600 requests per
  hour. It does **not** raise the depth cap.
- **Pages are numbered from 0.** `page=0` is the first 20 rows. Starting at
  `page=1` silently drops them; `harvest_muse.py` did this until 2026-09-16 and
  now fails when rows pulled differ from the response's `total`.
- **HARD DEPTH CAP AT PAGE 99** (100 pages, indices 0 to 99). Page 100 returns HTTP 400. It declares 407,252
  jobs across 20,363 pages and will serve you at most 2,000 per query. Another
  declared-total-is-not-available-total case.
- **Therefore: partition until `page_count` is 100 or less, then walk each slice.**
  Axes are `category`, `location` and `level`.

**Read the taxonomy, never guess it.** `category=Accounting` returns 0 rows
because the real name is `Accounting and Finance`. Harvest the vocabulary from
live results (`results[].categories[].name` and `.levels[].name`) rather than
inventing values. This is never-guess-a-slug applied to a controlled vocabulary.

21 categories observed, 4 levels (Entry, Mid, Senior, Internship). Volume is very
uneven, so measure `page_count` before planning a walk:

| Category | Pages | Approx jobs |
| --- | --- | --- |
| Software Engineering | 5,025 | 100,500 |
| Food and Hospitality | 1,864 | 37,280 |
| Retail | 1,180 | 23,600 |
| Healthcare | 1,061 | 21,220 |
| Data and Analytics | 899 | 17,980 |
| Business Operations | 881 | 17,620 |
| Sales | 447 | 8,940 |
| Account Management | 270 | 5,400 |
| Computer and IT | 77 | 1,540 (walkable as-is) |

Category page counts sum to ~307,480 against a declared 407,252. That ~100K gap
is unexplained; do not assume the two reconcile.

Worked example, Software Engineering in three metros: NYC 107 pages, SF 75, LA 69.
Only NYC exceeds the cap, and splitting by level clears it (Senior 76, Mid 29,
Entry 2, Internship 1). All twelve slices total ~256 requests, about 4 minutes at
the keyed rate, for roughly 5,020 postings.

## HiringCafe

**Server-side fetches are Cloudflare-challenged (403) as of 2026-09-16.** Run the
same requests as a same-origin `fetch()` from a hiringcafe.com tab in Chrome and
move rows out through the gesture-click clipboard button (660 KB in one copy
worked). `ssrHits` no longer carry `job_information.description`: take text from
the employer `apply_url`, falling back to `v5_processed_job_data.requirements_summary`.
The parse-filters location object defaults to `options.radius: 50`; overwrite it.

Highest yield of the two: 316 net-new companies versus Wellfound's 140, with
only 9 overlapping. **The sources are nearly disjoint, so run both.**

`hiring.cafe` redirects to `hiringcafe.com`. Next.js pages-router. Scale as of
2026-08-11: `ssrTotalCount` 3,696,556.

- **Payload:** `__NEXT_DATA__.props.pageProps.ssrHits`, alongside `ssrTotalCount`,
  `ssrCompanyCount`, `ssrPageSize`, `ssrIsLastPage`, `ssrPage`.
- **Query:** `GET /_next/data/{buildId}/index.json?searchState={urlencoded}&page={N}`
- **`buildId` rotates on every deploy.** Read it from `__NEXT_DATA__.buildId`
  every run. Never hardcode.
- **Pagination is the `&page=N` query param, not a key inside searchState.**
  Putting `page` or `currentPage` in searchState silently returns page 0 forever.
  Check `ssrPage` in the response to confirm the page actually advanced.
- Loop until `ssrIsLastPage`. Per-page hit counts vary (40 to 72) because of
  unpacked job cards.

**Let their AI build the filter object.** `GET /api/ai-search/parse-filters?query=<natural language>`
returns `suggestedFilters`, a ready-to-use searchState. Feed it the bar in plain
English. Then **overwrite the fields you care about**, because the parser fills
them from your prompt text and will drift. See `defining-the-bar.md` for which
filters to delete and why.

Per-job fields, far richer than Wellfound:

- top level: `source` (the real ATS), `board_token`, `apply_url`, `is_expired`
- `v5_processed_job_data`: `core_job_title`, `seniority_level`, `role_type`,
  `min_industry_and_role_yoe`, `workplace_type`, `yearly_min/max_compensation`,
  `estimated_publish_date_millis`, `requirements_summary`, `technical_tools`
- `enriched_company_data`: `nb_employees`, `year_founded`, `industries`,
  `latest_funding_type/year/amount/investors`

That company block fills funding, industry and HQ columns with no extra research.

## Wellfound

- **No login needed.** Everything is in the server-rendered payload, logged out.
- **Payload:** `__NEXT_DATA__.props.pageProps.apolloState.data`, holding
  `JobListingSearchResult:<id>`, `StartupResult:<id>`, and `ROOT_QUERY.talent[...]`
  which carries `pageCount` so you know how deep to paginate.
- **`atsSource`** (e.g. `AtsIntegration::Ashby::Listing`) names the company's real
  ATS directly. That is the single highest-value field here, because wrong-ATS is
  the blind spot that causes false "no roles" results everywhere else.
- **`liveStartAt`** is a unix timestamp and the true posting recency.
- URL patterns, all take `?page=N`: `/role/r/<role>` remote, `/role/l/<role>/<city>`
  city, `/role/<role>` everything.
- `StartupResult.highlightedJobListings` caps at 3 jobs per company, which is why
  980 "total jobs" yields ~666 rows.
- Dedup by accumulating keyed on apollo id; it dedups automatically.
- Sleep ~220ms between pages.

**Wellfound is a LEAD source, not a posting source.** Never record a Wellfound
URL as the posting; verify against the real ATS first. Watch for stale listings:
rows dated 2022 and 2025 sit in current results, so always check the date. It
skews early-stage founding-AE.

Comp strings use en dashes. Normalize to hyphens on export.

## Other general boards, as of 2026-09-16

| Board | What works |
| --- | --- |
| SimplyHired | curl only (Python urllib 403s after a few requests). Radius is `sr=100`; `mi=` and `distance=` are ignored. Page with `pageCursors[str(page+1)]` as `&cursor=`. `/job/<jobKey>` holds `expired` and `jobFound`. The employer apply URL needs a session, so rows stay unconfirmed until matched to an employer board. Highest raw yield on a local trades search. |
| LinkedIn guest API | `jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=&location=&distance=` works. Detail pages no longer expose `applyUrl`; closed banner is `closed-job__flavor--closed`. Search results exclude closed jobs. |
| CareerOneStop Job Finder (NLx) | `pagesize` max 250; **`pagesize=500` silently returns 0**. Page with `&curpage=N`; total in `id="lbltotalRecors"`. |
| Craigslist | `reno.craigslist.org/search/jjj` 302s to `www.craigslist.org/search/area/reno?cat=jjj`, static cards server-side. The ad is the primary posting for small shops. |
| Craigslist, radius search | `www.craigslist.org/search/city/gardnerville-nv?cat=ggg&postal=89410&radius=25`. The static HTML is capped: it returned 40 of 53 gigs on 2026-09-30, with no dates. Take the id list from the rendered page in Chrome (`.cl-search-result`, `data-pid`), then fetch each post from the shell at `www.craigslist.org/view/d/x/<id>` (any slug resolves). Jobs filter by type with `&employment_type=2` (part-time) and `=3` (contract). The `compensation` attr carries employment type and job title concatenated; split on the known keys. Map pins are unreliable for national ads (Wayfair, Grubhub, LawnStarter, property inspection) and sometimes wrong for local ones: trust a town named in the title. Craigslist's CSP blocks posting data to localhost from the page. |
| Facebook Marketplace | Not a job source. Jobs were removed in 2022; "job" returned "No listings found" within 20 miles of Gardnerville on 2026-09-30, and "help wanted" returned only people selling services. Local job posts on Facebook live in community groups. |
| Blocked | Indeed, ZipRecruiter, Glassdoor, Snagajob, Jooble, Jobright. |
| Shells or gone | us.jobs / usnlx, AutoJobs, EmployNV (needs session), WrenchWay (now ASE Connects), automotivetechnicianjobs.com. |

**The Muse returns the remote-only set for a location it does not recognize**
(`Carson City, NV` and `Sparks, NV` each returned 6,212), not zero. Assert that at
least one row carries the requested location.

## Batch by role family, not by row count

In a posting-first harvest the rows go source to disk and only aggregate counts
print, so **the rows never enter context and pulling 3,000 costs about what
pulling 300 costs.** Row-count batching is meaningless.

Family batching is what shows yield per family and lets you kill the ones that do
not produce. Expect cost to land almost entirely in batch 1, writing the scripts
and fighting transport. Later batches are much cheaper.

## Expand title variants before opening new families

Narrow exact-title queries tap out fast. Batch 1 of a healthcare operations search hit
`ssrIsLastPage` after two pages on most queries. That is not the source being
small, it is high precision leaving the shoulders of each family unpicked.

**Expanding variants inside a family that already proved out beats opening a new
family.** Credentialing alone had a dozen unqueried variants: Provider Data
Specialist, Medical Staff Coordinator, Licensing Specialist, Enrollment
Coordinator, CVO Specialist. Prior auth had Precert, Pre-Service, UM Coordinator,
Benefits Investigation.

## Adding a new source

1. Fetch one page with curl and a browser UA. Confirm the payload is there.
2. Find the listing array and record its path.
3. Identify pagination, the terminator, and anything volatile that rotates.
4. Note whether it carries a real-ATS field and a real date field. Those two
   determine how useful the source is downstream.
5. Write the registry entry with assertions on the required fields.
6. Run one family end to end before scaling. Record yield.

Every aggregator row still has to clear `verify-postings.md` before it ships.
About 10% of them are dead on arrival, every batch.
