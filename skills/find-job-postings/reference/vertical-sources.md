# Vertical-specific sources

**Separable.** This is not part of the general aggregator registry and should not
be merged into it. It is the seed for a dedicated job-search-app skill, where the
input is one person's resume and one industry rather than a broad ICP. Fork it
out whenever that gets built.

## Why it is separate

The general registry (`tools/sources.json`) is horizontal: remote-first boards,
startup boards, broad aggregators. Every one of them skews toward engineering,
design, marketing and sales, because that is who they were built for.

Run a healthcare admin query against all six general feeds and you get **1 match
out of 390 rows**. That number is not a measurement of the healthcare job market.
It is a measurement of the wrong sources.

**When a search targets a vertical, the general registry is the wrong tool and a
near-zero result from it means nothing.** Find the vertical's own boards first.

## Finding the boards for a vertical

1. Seed candidates from general knowledge, then **verify every one by fetching
   it**. A seed list is a hypothesis, not a finding.
2. Probe for payload shape in this order: JSON API, RSS, `__NEXT_DATA__`,
   `apolloState`, `self.__next_f`, JSON-LD, `data-page`, then job-shaped hrefs.
3. **Do not conclude "no structured data" from one pass.** Checking four shapes
   and stopping is the same error as covering three of eight routes. A second
   pass looking for hydration globals, embedded JSON blobs and job hrefs moved
   several candidates from "html only" to viable.
4. Record status honestly: `feed`, `sample`, `extract`, `follow`, `render`,
   `blocked`. A blocked source is a finding worth writing down so nobody
   re-probes it naively.
5. Check whether the source carries a real ATS field and a real date field.
   Those two decide how useful it is downstream.

## Healthcare, verified 2026-08-11

| Source | Status | What the fetch proved |
| --- | --- | --- |
| `healthecareers.com` | **follow** | No payload, but 45 real job hrefs on the search page in the form `/job/<slug>/<id>`. Route 6 works. The best healthcare-specific source found. |
| `healthjobsnationwide.com` | **render** | 3.7KB, zero job hrefs. JS shell. Needs Playwright before any conclusion. |
| `nurse.com` | **blocked** | 403 server-side. Worth a Chrome retry if the family needs it. |

Search entry points that worked: `healthecareers.com/search-jobs?keywords=<term>`.

## The trap this vertical exposed

**A declared total is not an available total.** Himalayas advertises 100,618 jobs
and serves 20, ignoring `limit`, `page`, `offset`, `skip`, `start` and every
search spelling. Remotive is capped at 20 with all params ignored.

Both are in the general registry as `sample` rather than `feed` for that reason.
A pull of 20 rows that looks like a clean result off a claimed 100K universe is
the silent-truncation failure wearing a new costume, and it is exactly what
produced the misleading 1-of-390.

## Automotive trades, local radius, verified 2026-09-16

Search: auto mechanics within 100 miles of Reno. No vertical board carried
volume; the postings live on employer boards and general aggregators. What
produced rows, in four lanes run in parallel:

| Lane | Rows after verify | Where the rows came from |
| --- | --- | --- |
| Dealerships | 44 | Paycom, Hireology, Workday (CarMax, AutoNation), Tesla's in-tab API |
| Chains | 129 | Les Schwab, CareerPlug (Big O), Workday (Firestone), iCIMS (Discount Tire), Walmart, Carvana, Caliber RSS |
| Public and fleet | 43 | NEOGOV, JobAps, EdJoin, USAJOBS, Oracle HCM (WM), UPS, FedEx Freight |
| Aggregators | 178 | SimplyHired, HiringCafe (in Chrome), LinkedIn guest, Craigslist, CareerOneStop |

394 rows reduced to 309 after cross-lane dedupe, closed and restricted reqs, and
unconfirmed rows over a year old. Aggregator rows mis-geocode large reconditioning
centers (Carvana Rocklin appeared as Grass Valley and Auburn). Title-similarity
dedupe must refuse to merge rows whose titles carry different store numbers
(Les Schwab `#953` vs `#959`) and must not collapse two reqs from the same board.
Categories that worked: car mechanic, lube and tire, diesel and fleet, body shop.
