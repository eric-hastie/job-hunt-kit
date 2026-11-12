# Verifying a posting is actually live

Read this before shipping any list that has links in it.

**~10% of aggregator rows are dead on arrival, every batch.** It is a steady tax,
not a one-time artifact: batch 1 lost 20 of 209, batch 2 lost another ~75 of 756.
It was caught by clicking the very first row on a page that had just shipped.

These pages go to a real person who applies to what is on them. A dead link costs
them an application slot and costs the page its credibility.

## Every obvious check lies

Major ATSes are JS single-page apps that return **HTTP 200 with a byte-identical
empty shell for both open and pulled requisitions**. One dead req: 200, 6.4KB,
empty body.

Worse, **the shell echoes the request URL back into the page**, so "does the job
title appear on this page?" passes on dead postings, because the title is sitting
in the URL string.

Status code lies. Body length lies. Title match lies.

Two more, from the Greenhouse side:

- **Dead Greenhouse postings return HTTP 200 and silently redirect to the full
  board** with `?error=true`, serving a page full of "Account Executive" text. So
  fetch-the-posting verification passes on a dead link. **Only ID-present-in-board-JSON
  counts as a pass.**
- **A thin response body does not mean dead.** `careers.toasttab.com` renders
  client-side, and the first version of the checker called four Toast URLs dead
  including one it had passed minutes earlier under lighter load.

## Check in this order

**1. ATS-native APIs.** Deterministic where they exist.

- **Workday CXS returns 403 for a pulled requisition** and 200 with live data for
  an open one. Clean binary signal.
- Greenhouse, Lever and Ashby have equivalents. For Greenhouse the test is
  membership in the board JSON, not the posting page.
- An empty board API is UNKNOWN, not dead. Deel disables theirs.

**2. Headless Chromium (Playwright)** for platforms with no usable API: ADP,
Paycom, iCIMS, Dayforce, UltiPro, Oracle Cloud, SuccessFactors, Taleo, Workable.

Installing a renderer beat reverse-engineering a dozen vendor APIs and made every
later batch cheap. It resolved 165 ambiguous links in one pass. Budget real
wall-clock: ~600 pages took roughly 45 minutes. **Start it in the background and
do other work while it runs.** Browsers are already downloaded at
`~/Library/Caches/ms-playwright`.

**3. Mark the rest unconfirmed.** Do not guess.

## Three states, never two

`live` / `dead` / **`unconfirmed`**.

A page that renders genuinely empty, or a known Ashby feed omission, is marked
unconfirmed on the page rather than silently presented as good or silently thrown
away. Both of those are worse than saying you do not know.

## Two self-inflicted traps from the same pass

- **Over-aggressive URL stripping created 41 false "dead" alarms.** Check what
  your normalizer did to the URL before believing the verdict.
- **Buffered pipe output made a background run look hung.** It was working fine.
  Flush, or check for progress another way, before killing and restarting.

## Never let a model retype an identifier

An LLM-based re-verify pass **hallucinated job IDs** while "fixing" URLs. It
overwrote Highspot's still-live Lever URL with a nonexistent UUID and relinked
Accrue to the wrong, more senior role.

Replacement URLs come from the board API verbatim, copied not retyped. Use the
LLM only for the UNKNOWN stragglers after the deterministic pass has run.

## Read the location field with suspicion

Ashby `(Remote)` location labels can mean hybrid with two days in office once you
read the JD body. Leapsome and Ironclad both did this. If remote is part of the
bar, the JD text is the authority, not the label.

## Existing tooling

- `~/.claude/skills/job-search/tools/verify_links.py` checks every row's ID
  against the Greenhouse, Ashby and Lever board APIs and prints replacement
  candidates with API-verbatim URLs. Exit 1 on any broken link, 2 when nothing
  was checked, `--json` for machine use.
- Ashby orgs running embed-only have a dead `jobs.ashbyhq.com` shell; the real
  board lives on the company's own site (Lemonade's is `makers.lemonade.com`,
  public URL `/role/<slug>-<first 8 chars of the Ashby UUID>`), so match on the
  UUID, not the title.

Run the link check after **every** capture pass, before rebuilding anything.

## Audit results, for calibration

Of 76 MM rows audited: 19 URLs re-pointed, 12 rows dropped, 1 reclassified. The
list went 175 to 163. Assume roughly a quarter of any unaudited set is wrong.
