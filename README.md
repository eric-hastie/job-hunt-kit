# Job Hunt Kit for Claude Code

Three Claude Code skills that run a job search the way a good researcher would:
write down exactly what a role has to look like, check real companies' own job
boards for matches, prove every posting is still open, and keep a running list.
A fourth step tailors your resume to any posting you pick.

Most job boards show you hundreds of listings and leave the filtering to you.
This works the other way round: nothing reaches your list unless it clears your
bar and the link is confirmed live on the company's own hiring system.

## What is in it

| Skill | What it does |
| --- | --- |
| `job-search` | Interviews you once to write down your bar, then runs each search: re-checks your existing list, finds new roles, scores them, removes duplicates, keeps `~/job-hunt/roles.csv` current. |
| `find-job-postings` | The know-how for getting postings out of company hiring systems (Greenhouse, Ashby, Lever, Workday and 17 others) without being fooled by a blank page or a dead link. Includes the scripts below. |
| `resume-tailor` | Given a posting link, proposes four to six exact word swaps to your resume, waits for your yes, applies them to a copy of your Google Doc in Chrome, and files the PDF in a folder per company. |

Scripts (plain Python 3, nothing to install):

| Script | Job |
| --- | --- |
| `find-job-postings/tools/discover_board.py` | Reads a company's careers page and works out which hiring system it uses and its board name. `python3 discover_board.py stripe.com` |
| `find-job-postings/tools/sweep_board.py` | Pulls every open posting from that board, across 21 hiring systems. Refuses to report zero when the real answer is "blocked". |
| `find-job-postings/tools/sources.py` | Checks the public remote-job feeds are still behaving before you trust a pull from them (`--probe`). |
| `job-search/tools/verify_links.py` | Re-checks every link in your list against the hiring system itself and suggests the replacement posting when one has closed. |

## Install

You need Claude Code and Python 3. The resume step also needs the Claude in
Chrome extension and your resume as a Google Doc.

```
git clone <this repo> job-hunt-kit
cd job-hunt-kit
./install.sh
```

Then open Claude Code anywhere and paste the prompt in `START_HERE.md`.

## Where your data lives

Everything personal stays in `~/job-hunt/` on your machine: your bar, your list,
every company checked, and your resume settings. The skills themselves hold no
personal data, so you can update them by pulling this repo and re-running
`./install.sh --force` without touching your list.

## Things worth knowing

- **A page that loads is not proof a job is open.** Many hiring systems show the
  same page whether the role is live or gone. That is why every link is checked
  against the system's own data rather than by opening it.
- **"No jobs found" is usually a broken search, not an empty market.** The skill
  is written to treat a zero as something to prove, and to say which routes it
  tried before reporting one.
- **Pay is recorded, never used to filter.** Boards often post base salary when
  the real number is on-target earnings, so a pay filter quietly drops good roles.
- **Nothing gets sent.** The skills never apply, upload or contact anyone.
- Some sources block automated reads (Wellfound, Eightfold, and as of November
  2026 The Muse). The skills record those as blocked rather than working around
  them.
- After a few manual runs, the same steps can run on a schedule with Claude
  Code's `/schedule` command. The job-search skill says what to add first.
