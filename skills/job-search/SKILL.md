---
name: job-search
description: >-
  Run a personal job hunt: define the bar a role must clear, find matching
  openings at real companies, verify each posting is live, score and dedupe
  them, and keep a running list. Use when the user asks to set up or run their
  job search, find new roles, refresh or re-verify their list, qualify or score
  a set of postings, or decide what counts as a fit. Finding postings on job
  boards is a separate skill: invoke find-job-postings for that, it owns all
  ATS and discovery knowledge.
---

# Job search

The method in one line: **define the bar first, then find, verify and filter.**
Scrolling job listings buries a few real fits under hundreds of mismatches. This
skill inverts that, so only roles that clear the bar and are provably live reach
the list.

## The working folder

Everything for one person's hunt lives in `~/job-hunt/` (create it on the first
run). Never store it inside the skill folder.

| File | What it is |
| --- | --- |
| `bar.md` | The qualification bar, written with the user in the intake below. Every run reads it. |
| `roles.csv` | The list: every role that cleared the bar. Columns below. |
| `checked.csv` | Every company ever evaluated, hit or not: `company,domain,ats,slug,last_checked,result,notes`. The dedup set, so a company is not re-researched from scratch. It only grows. |
| `targets.csv` | Companies still to check: `company,domain,source,notes`. Optional; posting-first searches do not need it. |
| `resume-profile.md` | Used by the resume-tailor skill, not this one. |

`roles.csv` columns, in this order:
`company,domain,title,url,location,remote,segment,comp,posted,date_added,status,fit,notes`

- `url` is the posting's own page, copied verbatim from the board's API or page.
- `posted` is the posting's publish date from the board itself, blank if the board
  does not expose one. Never guessed.
- `date_added` is the date the row entered the list. Never changed afterwards.
- `status` is `Verified` (confirmed live against the board), `Needs check` (real
  but only seen on a mirror or aggregator) or `Closed`.
- `fit` is a short score or label against the bar, with the reason in `notes`.

Write CSVs with Python's `csv` module, never by hand-joining strings. Before
rewriting either CSV, count its rows; after, count again and confirm nothing
was lost that was not deliberately removed.

## Step 0, first run only: the intake interview

If `~/job-hunt/bar.md` does not exist, build it before searching anything. Ask
the user, a few questions at a time, and write their answers in their own words:

1. **Role and level.** Exact titles that count, titles that look close but do not
   (for example "Sales Engineer" when they want "Account Executive"), and the
   seniority band.
2. **Location and arrangement.** Remote, hybrid or onsite; which countries,
   states or cities; any state where they cannot work.
3. **Experience ceiling.** The most years a posting can demand before it is out of
   reach. Ask about a floor only if the user raises one.
4. **Company profile.** Industries, stages or sizes they want or refuse; specific
   companies they already know they want; companies to exclude (a current
   employer, places already applied to).
5. **Pay.** What they need. Recorded, never used to drop a role (see
   `reference/defining-the-bar.md`).
6. **Credentials** they hold that a posting might require.
7. **Starting list.** Any companies they want checked first.

Then read `reference/defining-the-bar.md` and show the user the bar as rules,
labelling which came from them and which you derived. Get a yes before the first
search. **A criterion inferred from their resume is a question, never a rule.**

## A run

1. **Read `bar.md`, `roles.csv` and `checked.csv`.** Say how many rows each holds.
2. **Re-verify the existing list first.** Run
   `python3 ~/.claude/skills/job-search/tools/verify_links.py ~/job-hunt/roles.csv`.
   Mark dead rows `Closed` (do not delete them), and check whether the same company
   has posted a replacement.
3. **Find new roles.** Invoke the `find-job-postings` skill. It decides whether to
   go company-first (a list of companies to check) or posting-first (search across
   boards), and how to read each board without false zeros.
4. **Qualify each posting against the bar.** Read the posting text, not just the
   title. Location and remote status come from the body, not the label. Record
   every company looked at in `checked.csv`, including the ones with nothing that
   qualified.
5. **Verify before adding.** Every new row's link goes through `verify_links.py`
   or the method in find-job-postings `reference/verify-postings.md`. A link that
   returns HTTP 200 is not proof the job is open.
6. **Dedupe.** One row per posting URL. Match companies by website domain, never by
   name alone.
7. **Report.** New roles added, roles closed, companies checked, and anything that
   could not be verified. Then show the top new rows and read each one: does it
   actually belong? Eyeballing the top ten has caught a wrong row more than once.

If the user wants a browsable page instead of the CSV, build a single HTML file
from `roles.csv` with search and sort, and regenerate it after every run.

## Standing rules for a qualified list

- **A bar the user set is not yours to move**, in either direction, and least of
  all to make a run look productive. A run that finds nothing new is a result to
  report, not a reason to loosen a filter.
- **Never turn a fact about the user's background into a filter.** State an
  inferred criterion as a question.
- **Never reject on posted pay.** Boards often publish base salary when the real
  number is on-target earnings or total comp. Record it, never drop on it.
- **Verify a company still exists and is independent** before spending effort on it.
- **Bind every record to a company by domain, never by name.**
- **Never apply, submit or contact anyone.** This skill finds and qualifies roles.

## Making it run on a schedule (optional)

Once a manual run works end to end, the same steps can run unattended as a
scheduled Claude Code job (the `/schedule` command). Before doing that, add a
check after each step that stops the run and reports when something looks wrong
(a source returned nothing, a CSV lost rows, links failed to verify), because a
silent failure in an unattended run produces a believable but wrong list and
nobody is watching to catch it.

## Reference

| File | When |
| --- | --- |
| `reference/defining-the-bar.md` | Before setting any filter. |
| `tools/verify_links.py` | Every run, on the existing list and on new rows. |

## Keeping this skill current

Lessons about the bar, scoring or the list go here. **Lessons about boards, ATSes
or discovery go in `find-job-postings`.** Keeping the two apart stops them
drifting into two half-correct copies. `find-job-postings/tools/check_no_drift.sh`
fails if ATS vocabulary leaks into this file outside the pointer lines.
