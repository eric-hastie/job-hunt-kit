# Sourcing: company-first

Use when the company universe is enumerable. A target account list, an ICP that
resolves to names, "every job at these companies", or a scored universe like
RepVue's ~15K.

The job is: for each company, find every posting. The eight routes below are the
canonical route list, and this file is how to execute it.

## Start from the route list, do not write a fresh crawler

`tools/discover_board.py` reads which job board a company uses off its own
careers page, and `tools/sweep_board.py` reads 21 board platforms and fails
loudly on a truncated pull. Together they cover routes 1 and 2 for most
companies; work the remaining routes by hand, in order, before calling a
company empty.

On 2026-08-11 a fresh script written from general knowledge, *after* the route
list existed, covered 3 of 8 routes fully and 2 not at all. Writing a new
discovery tool reintroduces the exact holes the list exists to close.

## The eight routes, in order

| # | Route | Notes |
| --- | --- | --- |
| 1 | Primary ATS APIs | Greenhouse, Ashby, Lever, SmartRecruiters, Workday |
| 2 | Secondary ATS | Rippling, Workable, BambooHR, JazzHR, Recruitee, Breezy, Personio, Teamtailor, Pinpoint, Gem, Paylocity, Dover, Notion, GreetingHR (KR) |
| 3 | YC Work at a Startup | any YC company; read the slug, never derive it from the domain |
| 4 | schema.org JobPosting JSON-LD | embedded in the careers page |
| 5 | Hydration payloads | `__NEXT_DATA__`, `window.__NUXT__`, Apollo state, `__INITIAL_STATE__` |
| 6 | **Follow the links** | scrape job hrefs, then FETCH EACH ONE |
| 7 | Render | Claude in Chrome or Playwright when the page is a JS shell |
| 8 | Off-site | Google, LinkedIn Jobs, Wellfound, HN Algolia. **8b**: a search filtered to ATS hosts, below |

**Route 1b, inserted 2026-10-02: a candidate slug the provider itself confirms.** Run it
before route 1's page crawl. Greenhouse, Ashby and Lever each publish the board owner's
own name, so a slug built from the company name can be *proven* against the provider
rather than guessed. This is the only route that reached Cloudflare and Asana, whose
careers pages name Greenhouse by component name and never print the slug anywhere in the
HTML, the JS bundles or search results. The mechanics, and the false positive that forces
a token-set comparison instead of a substring test, are in `ats-field-notes.md`.

On an enterprise list, route 8 underperforms badly: DuckDuckGo and Bing returned no ATS
URL at all for Cloudflare, Asana, Cisco or 8x8, and DuckDuckGo percent-encodes every
result link, so a provider pattern run on the raw results page cannot see a slug that is
sitting right there. URL-decode the results page twice before detecting.

**Run route 8 early, in parallel with route 1, not last.** Plain Google
`"<company> jobs"` is the highest-yield single request available and it is the
only route that finds postings hosted entirely off the company's property.
Jefit had no ATS and no board; its careers page was 288 words of marketing and
its only real requisition existed on LinkedIn, which Google indexes and expands
with comp, post date and full responsibilities. Routes 1 through 7 all search
the company's own surface, and a small company's reqs frequently do not live
there at all.

### Route 8b: a search restricted to ATS hosts

Run it for every company that routes 1, 1b and the careers-page crawl left without a board.
Search `<company> <what it does> jobs` with the search tool's domain filter
(`allowed_domains`), not with `site:` or `OR` operators, which the tool does not honour:

    jobs.ashbyhq.com, job-boards.greenhouse.io, boards.greenhouse.io, jobs.lever.co,
    apply.workable.com, ats.rippling.com, myworkdayjobs.com, jobs.gem.com,
    jobs.jobvite.com, careers.smartrecruiters.com

Adding what the company does to the query matters: a bare short name ("Bolt", "Brain")
returns namesakes. Filtering to ATS hosts removes the aggregator copies, so the board's
own URL, and its slug, is what comes back.

It finds the boards no other route can: slugs nobody would build from the name and
providers route 1b does not probe. Tested 2026-10-29 on nine companies whose careers pages
and route 1b had both come up empty. It found three live boards: Brain Corp as Greenhouse
`braincorporation`, Gravity Payments as Greenhouse `gravitypayments17`, and SoundHound on
Gem `soundhound`.

**The search index is stale, so every hit is a lead, never a board.** Four of the seven
boards it returned were dead. Greenhouse `bolt42`, `soundhoundinc` and `lilyai` returned
404 from the boards API. Ashby `zippin` served the same bare `<title>Jobs</title>` as an
invented slug, while still-indexed posting URLs pointed at it. Prove each hit before using it:
- **Greenhouse:** the boards API `name` must match the company.
- **Ashby, Lever and Gem:** these publish no owner name. The board must read live through
  `sweep_board.read`, and its postings must name the company.
- **Every provider:** run an invented-slug control on the same provider.

**Run a second pass over the smaller platforms.** For the companies still without a board,
filter the search to `applytojob.com` (JazzHR), `breezy.hr`, `bamboohr.com`,
`recruiting.paylocity.com`, `workforcenow.adp.com`, `recruitingbypaycor.com`,
`app.trinethire.com`, `careers-page.com` (Manatal) and `wellfound.com`. In a board hunt over 34
companies on 2026-10-29, this pass found Cut+Dry on JazzHR, plus INTELITY's dead Breezy board
and Gr4vy's and Hyphen's Wellfound pages. The first host list found none of them.
- **Australia and New Zealand:** add `employmenthero.com`, `jobadder.com`,
  `pageuppeople.com`, `livehire.com` and `seek.com.au`.
- **Engineering hired in Ukraine or Eastern Europe:** add `jobs.dou.ua` and `djinni.co`.
  That is where Oro posts.

**Two fetch failures that look like "no careers page":**
- **A gzip body.** Sent to a client that never asked for one, it reads as binary. Altametrics
  did this, and `discover_board.fetch_page` decodes it since 2026-10-29.
- **A bot wall** (a 403 or a challenge page). Retry with WebFetch, which read Ovation's and
  Veeve's pages after curl was refused.

Wellfound-only hits (Spot AI) are recorded as blocked, never worked around.

**SEEK and Instahyre also count as blocked.** SEEK returns 403 to curl, to its own search API and
to WebFetch, and Instahyre sits behind Cloudflare. In both 2026-10-29 hunts, the second host pass
for Australian and New Zealand companies mostly turned up SEEK ads. Record a SEEK board and move on.

**Look under a related company.** In the Group 2 hunt (2026-10-29), four boards sat somewhere
other than the company's own name:
- **A rebranded domain:** Moises posts under music.ai/careers.
- **A sister company:** Kick posts on Easygo's Greenhouse board.
- **The maker's name:** HomeCourt posts on Greenhouse `nex`.
- **A parent's board, reached through the company's own API:** Stile.

A board belonging to a parent or sibling counts only for the postings that name this company.

**Where `discover_board.py` still misses a board**, so search every fetched page yourself:
- Workable job links written as `/j/<id>`, which carry no account name.
- A board address buried in a Next.js page bundle (Skool).
- Providers it does not detect at all: Paylocity, Dayforce, ADP, ELMO, ApplyFlow, Comeet,
  Bullhorn, and Greenhouse through its WordPress plugin.

Since 2026-10-29 it does read `boards-api.greenhouse.io/v1/boards/<slug>` (Wurl), and it does
fetch `/about` and `/company`.

**An empty board that a search turned up is usually a stale old board, not the answer.** In
the Group 3 hunt (2026-10-29) this happened 9 times, on Workable, Lever and Greenhouse. In 8
of them the live board was on a different provider, linked from the company's own careers
page. So when route 8b finds a real but empty board, go back to the careers page before
recording it.

**An acquired company's careers page often links straight to the new parent's board.** Seen
for Highspot (Seismic), Chatmeter (Alchemer), Jolt (Digi), Follow Up Boss (Zillow) and AroFlo
(Simpro). Read only the postings that name the company, and flag the company as acquired.

**Once you know the provider, search that provider's own site for the company name.** That
is how Crunchbase's Teamtailor board turned up, on a regional host.

**More providers that `discover_board.py` does not detect**, found by reading careers pages
and scripts by hand in the 2026-10-29 hunts:

| Provider | Where it showed up |
|---|---|
| Kula | `careers.kula.ai/<slug>` (Invoca, CleverTap, Avoma) |
| Pinpoint | a widget attribute, `data-pinpoint-subdomain` (Marchex) |
| iCIMS Jibe | on the company's own host (Xactly) |
| SuccessFactors RMK | on the company's own host, with a plain-list sitemap (Responsive) |
| Rippling | named only in a `data-job-board-id` attribute (Foundant) |
| Others | TriNet Hire, Keka, UKG, Paycor, ApplicantPro, Paylocity v2, Comeet, Trakstar Hire, LiveHire, Darwinbox, Notion |

`sweep_board.py` has no reader for Kula yet. Its SuccessFactors reader expects the RSS-style
sitemap, so a plain URL-list sitemap reads as "no such board" (SIG-84).

## Endpoints

```
Greenhouse       boards-api.greenhouse.io/v1/boards/<org>/jobs?content=true
                 body is in `content`, HTML-escaped
Ashby            api.ashbyhq.com/posting-api/job-board/<org>        date: publishedAt
Lever            api.lever.co/v0/postings/<org>?mode=json           date: createdAt (epoch ms)
SmartRecruiters  api.smartrecruiters.com/v1/companies/<org>/postings
Workday          POST <tenant>.wdN.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs
                 {"limit":20,"offset":0,"searchText":"","appliedFacets":{}}
                 then GET base + each externalPath
Workable         apply.workable.com/api/v1/widget/accounts/<org>?details=true
                 (v3/accounts/<org>/jobs 404s for real boards; one row per LOCATION)
Recruitee        <org>.recruitee.com/api/offers/
Breezy           <org>.breezy.hr/json, body from each job page's JSON-LD
BambooHR         <org>.bamboohr.com/careers/list, then /careers/<id>/detail
Rippling         api.rippling.com/platform/api/ats/v1/board/<org>/jobs (one row per LOCATION),
                 body from each job page's __NEXT_DATA__
Pinpoint         <org>.pinpointhq.com/postings.json
Gem              api.gem.com/job_board/v0/<org>/job_posts/
JazzHR           app.jazz.co/feeds/export/jobs/<org>          (XML, full bodies)
Teamtailor       <org>.teamtailor.com/jobs.rss                 (full bodies, owner name)
iCIMS            <host>.icims.com/sitemap.xml + /jobs/search?pr=N&in_iframe=1, JSON-LD per job
Jobvite          jobs.jobvite.com/<org>/jobs/positions, JSON-LD per job
Oracle HCM       see reference/ats-field-notes.md; two calls, body per posting
Phenom           POST <careers host>/widgets {"ddoKey":"refineSearch",...}, JSON-LD per job
Taleo            <slug>.taleo.net/careersection/sitemap.jss?portalCode=<section>&lang=en
Taleo BE         <x>.tbe.taleo.net/<code>/ats/careers/v2/searchResults?org=<ORG>&cws=37
                 (paging needs the session cookie)
SuccessFactors   <RMK host>/sitemap.xml is an RSS feed of every posting with its body
Work at a Startup  www.ycombinator.com/companies/<slug>/jobs, JSON-LD per job
Personio         <org>.jobs.personio.de/xml
GreetingHR (KR)  <org>.career.greetinghr.com          job page: /o/<id>, /ko/o/<id>
Wanted (KR)      wanted.co.kr/api/chaos/companies/v1/<companyId>/jobs?limit=200&offset=0
                 detail: wanted.co.kr/api/chaos/jobs/v1/<jobId>/details
                 no auth, no key, full JD text in job.detail
HN Algolia       hn.algolia.com/?query=<domain>&type=comment&dateRange=pastYear
```

Also cracked and available if you meet them: UKG/UltiPro POST.

`tools/sweep_board.py` reads every platform in the table above except Recruitee,
Personio and the Korean boards; `sweep_board.read(provider, slug, extra)` takes
`discover_board.py`'s output as it comes.

## Never guess the slug

Fetch the homepage, follow any href containing career/job/hiring/join, and regex
the resulting HTML for a provider URL. `PROV` in `discover_jobs.py:37` is the
maintained pattern list. Always `.strip()` the result: a trailing space produced
`URL can't contain control characters` and silently discarded Confido's board.

Order the patterns most-specific first. The `greenhouse.io/embed/job_board/js?for=`
script-embed form is common on marketing sites and a generic pattern captures the
literal path segment `embed`, which silently broke Medallion, Siteline and FERMAT.

Reject these as slugs: `www`, `api`, `jobs`, `embed`, `job-board`, `companies`.

**Never leave the company's own domain while crawling.** A crawl that wandered
onto ycombinator.com returned `openphone` as GETASAP's board.

Known slug traps:

- **SmartRecruiters returns HTTP 200 with `totalFound: 0` for an org that does
  not exist.** A 200 alone is a false positive; always check the count. Flywire
  is `Flywire1`; `flywire` returns zero and reads as an empty board.
- **Workday** tenant and site must both be scraped. Duck Creek is `duckcreek` /
  `duckcreekcareers`; `duckcreektechnologies` 422s. Visa needs the `wd5` tenant
  because the public usa.visa.com path returns a Cloudflare challenge.
- **Ashby slugs frequently differ from the domain**: Vapi is `vapiai`, Cartesia
  is `cartesia-ai`, Decagon is `decagonhq`.

## Detection without extraction is a silent miss

Matching a provider and having no `pull()` handler for it reports `0 jobs`,
which is indistinguishable from "not hiring." That cost Photon Health (Gem, 10
real roles including Head of Engineering), Deepline (Gem) and String (Notion).

**Every provider in the detection regex needs a fetch handler, or it must not be
in the regex.** Raise rather than returning zero, and send the client-rendered
ones (Notion, Dover, Paylocity) to route 7. Gem's page is client-rendered but its
API is public, so `sweep_board.gem()` reads it. Wellfound refuses scripted reads
(`sweep_board.BLOCKED`).

## Prove a zero before recording it

A verified empty board is a legitimate finding. Prove it with a control test:
query a nonsense slug and compare. Stainless's Ashby board `stainlessapi` really
is empty, established because the nonsense slug returned `Not Found` while the
real one returned `{"jobs":[]}`.

Prove the pull was complete, too. A Workday pull once read `total` as 0 and
returned 40 of 121 postings, which would have "confirmed" a board was clean off
a third of it. `sweep_board.py` returns the board's own reported total and fails
loudly when the counts disagree.

## The board can lie by omission

Some Ashby companies publish roles on their careers page and at live direct
`jobs.ashbyhq.com/{slug}/{uuid}` URLs while excluding them from the public
posting-api feed. Linear, RepVue 97, was missed this way twice.

Round two found the more common cause is simply the **wrong ATS**: companies run
a different provider than the guessed one, so an Ashby-only check finds nothing.
Fetching `/careers` (which links the real ATS) fixes both. Two blind-spot sweeps
over 160 high-score no-AE companies found ~28 hidden roles, an 18% hit rate.

## A careers page that is not the careers page

`/careers` is frequently not where the board lives, and three separate shapes of
this all report the same false zero:

- **A redirect stub.** `modal.com/careers` is 110 bytes and bounces to
  `/company#careers`, where a full Ashby board (`modal`, 31 reqs including an
  Enterprise AE) is linked. The crawler read the stub, found no provider, and
  filed Modal as a self-hosted careers page with no roles.
- **A bot wall.** `vultr.com/careers` returns HTTP 403 with a Cloudflare
  challenge to any server-side fetch. Vultr runs Ashby `vultr` with 61 reqs and
  2 remote-US AE roles.
- **A JS shell.** `openrouter.ai/careers` returns 155KB of Next.js scaffolding
  with zero job hrefs and no hydration payload carrying reqs. OpenRouter runs
  Ashby `openrouter` with 23 reqs including two remote-US AE roles.

In all three the board existed under an unremarkable slug. **When the careers
page yields no provider, that is a signal to keep going, not a conclusion**:
follow the redirect target, try `/company` and `/about`, and check whether an
already-published row for that company records the ATS URL. Do not guess the
slug, but do read it off whatever surface actually has it.

## Non-US boards: the domestic ATS is the board

A Korean, Japanese or European company frequently runs no provider in the route
1-2 table, and every US-shaped check then returns a clean zero. StradVision
looked boardless through all eight routes until the homepage nav was read: it
runs **GreetingHR**, `stradvision.career.greetinghr.com`. The detection regex had
no pattern for it, so there was nothing to find and nothing to report.

**When a non-US company returns zero, read the homepage nav before concluding
anything.** The careers link is the fastest route to a domestic ATS name, and the
answer is usually a provider you have not met yet. Add it to `PROV` with a fetch
handler in the same session, because detection without extraction reports zero.

Korean specifics, all confirmed on StradVision:

- **`www.stradvision.com` serves a 763-byte JS cookie wall to every path.** It
  returns HTTP 200 with a `slowAES` script that sets a `CUPID` cookie and
  reloads. Real paths and invented ones are byte-identical, so `/careers`,
  `/recruit` and `/en/careers` all "exist" at 200. This is route 7 territory:
  rendering in Chrome cleared the cookie in one navigation and exposed
  `/careers` as a genuine 404. **A near-constant byte count across invented
  paths is the tell**, and it is a stronger check than the status code.
- **GreetingHR takes scheduled maintenance windows** and returns HTTP 401 with a
  redirect to `inspection.greetinghr.com` across the whole service, API included.
  A 401 there is a closed door, not an empty board, and never a verified zero.
- **`wanted.co.kr` is the fallback and it is a good one.** Its API needs no auth,
  serves full JD text, and its per-company total is printed in the page title
  (`채용 21건`), which gives a count to reconcile the pull against. It carried all
  21 live StradVision reqs while the primary board was down.
- Other Korean aggregators: `rocketpunch.com`, `jobkorea.co.kr`, `incruit.com`,
  `jobplanet.co.kr`. RocketPunch and TheVC 403 server-side fetch, so render them.

**An aggregator is a floor, not the board.** Google had indexed GreetingHR reqs
that Wanted did not carry (`Engineering Productivity Manager`, `Senior
Requirement Engineer`, `Parking Product Integration Engineer`). Report an
aggregator count as what it is, and say the primary board was unread.

## Every provider handler must carry the posting URL forward

An earlier puller built Ashby records without `jobUrl`, so 359 reqs were
archived with an empty `url`. Nothing failed: the pull reported the right
count, the text was complete, and the store looked healthy. But a req with no
link cannot be re-verified, cannot be deduped against a published list, and
cannot be handed to anyone. The same defect was present in the workable,
recruitee, breezy, rippling and pinpoint branches. All six now map a URL.

**When adding a provider handler, the record is not complete until it carries
title, text, url and posted.** A store keyed by posting URL makes a URL-less row
is also unmergeable: re-running after the fix appended a second copy rather
than updating the first.

## Self-hosted careers pages are a real category

Small startups publish roles as ordinary page text with no board at all: TextQL
12 roles, Foam 4, micro1 4, Warp 2, Aeqium 2. "No ATS" never means "no jobs."

**But the false-positive direction is just as wrong as a false zero.** A careers
page yields buyer personas ("VP of Supply Chain Operations") and testimonial
bylines ("Ben Cook, Area Operations Manager") that look exactly like job titles,
and no text pattern separates them. Require **structural** evidence: accept a
title only when it is the anchor text of a link pointing at a job URL.

## Building the universe

For a sales job hunt, RepVue (a sales-org rating site, about 15,000 companies)
makes a good company universe. Keep any export private: it is RepVue's data. It 429-blocks server-side fetch, but its own JSON API works from a
logged-in browser console. Loop
`repvue.com/api/companies?sort_key=repvue_score&sort_direction=desc&per_page=300&page=N`
with `{credentials:"include"}`, ~52 pages. The `/api/` prefix is the key; bare
`/companies` returns HTML.

`has_active_jobs` is reference-only and **never a filter**. RepVue's job data is
stale, which is the gap this pipeline fills.

## Account for every target

A bare `ex.submit()` in a ThreadPoolExecutor swallows every exception, so a
crashing worker drops its account with no trace, indistinguishable from one that
was never queued. Stainless went missing exactly this way. Collect futures,
re-raise, record the crash, and print anything unaccounted for at the end.
