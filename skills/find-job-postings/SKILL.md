---
name: find-job-postings
description: >-
  Find, verify and read job postings for a set of companies or a set of job
  titles. The job board (ATS) and careers page knowledge: the eight discovery
  routes, reading a board's slug off the careers page, aggregator harvest,
  proving a posting is actually live, and reading a posting without false
  positives. Use whenever the user asks to find, harvest, sweep, refresh or
  verify job postings, asks which companies are hiring for a role, or asks for
  jobs at a named list of companies. Invoked by the job-search skill for a hunt,
  or on its own.
---

# Find job postings

**This skill is the single home for everything about getting postings out of a
board.** The job-search skill covers the qualification bar and the deliverable and
calls this one for the finding. A new ATS lesson belongs here and nowhere else.

## Non-negotiables

1. **Never guess an ATS slug.** Read it out of the careers page HTML and
   `.strip()` it. A guessed slug fails silently and looks exactly like "not
   hiring". SmartRecruiters returns HTTP 200 with `totalFound: 0` for an org that
   does not exist. Known traps: Flywire1, Workday tenants, Ashby vapiai,
   cartesia-ai, decagonhq.
2. **Follow the links and fetch each one.** Anchor text is not a posting.
   Detecting a provider with no pull handler reports `0 jobs`, indistinguishable
   from a real zero.
3. **Never report "no jobs found"** until the routes are exhausted, and name which
   ones you tried. A target account's jobs are always findable. Naming a skipped
   route is not exhausting it, and stopping to ask permission to finish a standing
   instruction is the same miss in a better costume.
4. **HTTP 200 is not proof a posting is live.** ATS single-page apps serve a
   byte-identical shell for open and pulled reqs, and echo the request URL into the
   page, so even a title match passes on a dead link. See `reference/verify-postings.md`.
5. **A keyword hit is not a finding.** Print the matched context and read it. Every
   board swept so far has produced false positives.
6. **Capture the text before analyzing it.** Postings come down and are then
   unrecoverable. See `reference/read-postings.md`.
7. **Account for every target.** A crashed worker that drops an account looks
   identical to one never queued. Collect futures and re-raise.

## Pick the shape before writing anything

**Is the company universe knowable?** This is not the same question as purpose.

- **Yes, enumerable** to company-first. Read `reference/sourcing-company-first.md`.
  Fits a target account list, an ICP that resolves to names, "every job at these
  companies".
- **No** to posting-first. Read `reference/sourcing-posting-first.md`. Fits roles
  spread across every industry with an HR function. Here **freshness is the primary
  sort**: remote admin postings draw hundreds of applicants in days.

## A zero is a trigger, not a result

Any time a search returns 0 postings, or a harvest returns a suspiciously low
count, stop and re-read the relevant reference file before reporting anything.
Zero is the output shape every documented failure has produced.

Answer all six in writing before a zero leaves your hands:

1. Which of the eight routes did I run, and which did I skip?
2. Did I read the slug out of the markup, or derive it from the domain?
3. Did I detect a provider I have no pull handler for?
4. Did I follow the job hrefs and fetch each one, or only read anchor text?
5. Did the pull match the board's own reported total?
6. Did I run the control test with a nonsense slug, and did I run route 8 off-site?

If the search targets one industry and used only the general registry, the zero
means nothing. Read `reference/vertical-sources.md`.

## Record what you looked at

Every company checked goes into `~/job-hunt/checked.csv` (layout in the
job-search skill), including the ones with nothing that qualified, with the
board platform and slug you read. A verified zero must stay distinguishable from
never having looked.

**Save the text of every posting that makes the list** (`~/job-hunt/postings/`,
one file per posting). Postings come down and are then unrecoverable. See
`reference/read-postings.md`.

**Over 100 companies at once: stop and ask before reading every posting in
full.** Reading postings in depth costs roughly 5k tokens per company.

## Reference

| File | When |
| --- | --- |
| `reference/sourcing-company-first.md` | The universe is enumerable. The eight routes, provider table, control test. |
| `reference/sourcing-posting-first.md` | It is not. Aggregator harvest, source registry, family batching, title variants. |
| `reference/verify-postings.md` | Before shipping any list with links in it. |
| `reference/read-postings.md` | Turning postings into intelligence: titles, req age, tools, archiving. This is the prospecting and ICP path. |
| `reference/vertical-sources.md` | The search targets one industry. |
| `reference/ats-field-notes.md` | Before writing a fetcher for any named ATS, government board or brand site: pull method, liveness test, control. |

## Tooling, use it rather than hand rolling

All of it lives in this skill, so there is one copy to fix:

- `tools/discover_board.py` reads the slug off a company's own careers page across 25
  platform fingerprints. `READABLE` lists the 21 that can be pulled; `BLOCKED` lists
  Eightfold and Wellfound, which refuse scripted reads and are recorded, never worked
  around.
- `tools/sweep_board.py` reads those 21: Greenhouse, Ashby, Lever, SmartRecruiters,
  Workday, Workable, Gem, JazzHR, Pinpoint, Teamtailor, SuccessFactors, Rippling,
  BambooHR, Breezy, iCIMS, Oracle HCM, Jobvite, Phenom, Taleo, Taleo Business Edition and
  YC's Work at a Startup. `read(provider, slug, extra)` takes discover_board's output as
  it comes. Every reader returns (postings, total) with title, text, url, location,
  department and posted; **total is None when the platform says the board does not
  exist, 0 when it is real and empty**, and a 403, 429, 5xx or timeout raises
  `BoardClosed` rather than reaching a zero. Run `--selftest` (offline) and `--live`
  (two real boards and one invented slug per platform) after any change; the live run
  fails on a count that disagrees with the board's own page or on two postings sharing
  a URL. **Fix fetcher bugs here, never in a copy.**
- `tools/sources.json` is the aggregator registry, `tools/sources.py --probe` its
  drift alarm. Run the probe before trusting any harvest.
- `~/.claude/skills/job-search/tools/verify_links.py` re-checks a list's links.

Do not write a fresh crawler from general knowledge. On 2026-08-11 that covered 3
of 8 routes fully and 2 not at all, from a script written after the route list
already existed.

## Keeping this skill current

New boards, new ATSes and new failure modes land continuously. **When a run hits an
edge case these files do not cover, add it here in that same session, before calling
the task done.** Write the rule as it now stands, not as a history of what changed.
The exception is a cautionary precedent: when the war story is what makes the rule
stick, keep it.

**Everything about finding, verifying or reading a posting goes in this skill, never
in job-search.** That is what stops the two drifting. `tools/check_no_drift.sh`
fails if ATS vocabulary appears in job-search outside its pointer line.
