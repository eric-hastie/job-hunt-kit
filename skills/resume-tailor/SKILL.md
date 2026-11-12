---
name: resume-tailor
description: >-
  Tailor the user's one-page resume to a specific job posting, end to end: fetch
  the JD, extract its vocabulary, generate exact find/replace edits against the
  local master resume, apply them to a copy of the Google Doc in Chrome, export
  the PDF, and file it in the company folder. Use whenever the user types
  "resume: <job posting URL>", pastes a JD and asks for a tailored resume, or
  asks to tailor or customize their resume for a role or company.
---

# Resume tailoring (Claude Code + Chrome)

Trigger: `resume: <job posting URL>`. That single line means run this whole
workflow. Also fires on a pasted JD plus "tailor my resume".

The output is a company-tailored one-page PDF, produced by editing a copy of the
master Google Doc, never by rebuilding the document. Every past formatting
failure came from regenerating the resume in a new file. Editing in place
inherits all character and paragraph formatting (Cambria 10.5pt body, Georgia
name line, borderless split-column tables), so it cannot break.

**Non-goal:** no restructuring, redesign, or reformatting. This workflow only
swaps text inside existing lines.

## Settings live in the profile, not here

Everything personal (file paths, the Google Doc, the file naming pattern, who the
user is, their own extra rules) is in **`~/job-hunt/resume-profile.md`**. Read it
at the start of every run. If it does not exist, stop and build it with the user
first by copying `reference/resume-profile.template.md` and filling each field in
with them. Never guess a field.

Below, `<MASTER_PDF>`, `<DOC_URL>`, `<OUTPUT_ROOT>` and `<FILENAME>` mean the
values from the profile.

Month and year are the current ones at tailoring time, not the month in the
master file's name. Paths often contain spaces: quote them in every shell command.

**Check the export name every time.** If the master in Drive is a `.docx` rather
than a native Google Doc, Chrome writes `<FILENAME>.docx.pdf` with `.docx` stuck
in the middle. Strip it during the move at Cc2.

Never read a resume from Google Drive. The local PDF is the reference; the Doc
copy is the workpiece.

**Sync invariant.** The local PDF and the Google Doc must be the same content. If
several FIND strings *generated from the PDF this run* miss against the Doc copy,
that is drift between the two. Say so, and have the user re-export the Doc to PDF
over the local file rather than improvising replacements.

Only a live miss at C4 is evidence of drift. A stored example disagreeing with the
PDF is not, and must never be reported as a sync problem.

## Who the user is

Read the "Who I am" section of the profile: title, years, domains, the buyers
they sell or work with, and the vocabulary they use. It decides which way to dial
the wording. Two patterns from real runs worth knowing:

- **Overqualification is a common tension.** Seniority vocabulary can trip a
  screen for a more junior seat. When the role sits below the user's level,
  foreground hands-on, individual ownership language, not orchestration language.
- **Domain gaps are not fixable on the resume.** If the role sits in a domain the
  user has not worked in, note the gap and move on. It gets handled in outreach
  and interviews, which are out of scope here.

## Hard rules (a violation makes the output unusable)

1. **One page. Non-negotiable.** Every edit is a swap, never a net addition.
   Target character-neutral; anything past roughly +25 characters on a line needs
   a compensating cut. Verify page count visually before export.
2. **Never invent, round, or adjust a metric.** Quota figures, attainment
   percentages, ACV, rankings, dates: frozen exactly as written. Tailor emphasis,
   framing, and terminology only.
3. **No dashes as punctuation, no em dashes anywhere.** Plain hyphens only in
   numeric or date ranges. Recast any dash as a period, comma, colon, or
   parenthesis. The autocorrect preflight below is the most likely way one slips
   in.
4. **The user's own rules in the profile are hard rules too.** For example "never
   mention X" or "never reference the gap in 2024". Read them every run.
5. **Never manufacture experience.** No invented role, no explanatory line, no
   date fudging.
6. **Flag accuracy checks rather than asserting.** If an edit would make the
   resume claim something it does not currently claim (a named tool, cloud, or
   process), surface it to the user first: "confirm you actually used ZoomInfo at
   <that company> before this goes in."
7. **Stop on ambiguity. Do not improvise.** See the mismatch protocol at C4.

## Lane A: Claude Code, before the browser

**A1. Read the local generic PDF.** Every run. This is the only valid source of
FIND strings.

Never lift a FIND string from the reference files, from an earlier run, from a
prior conversation, or from any document that claims to quote the resume. Stored
strings go stale silently, and a stale FIND either misses at C4 or, worse, half
matches. If a stored example disagrees with the PDF, the PDF is right and the
example is stale. That is not a sync problem, and it says nothing about the
Google Doc.

**A2. Fetch and analyze the JD.** Research scope is only what informs wording. No
founder research, no values research, no company research beyond product
category.

If the fetch fails, or the returned content does not clearly contain the actual
role (title, responsibilities, requirements), STOP and ask the user to paste the
text. Do not substitute a generic careers page and do not guess.

*Fetch behavior:* Ashby (`jobs.ashbyhq.com`) and Workable
(`apply.workable.com`) are JavaScript-rendered and fail on direct fetch; use a
Built In or Jobgether mirror, open the posting in a Chrome tab, or ask for a
paste. Oracle careers blocks everything: paste only. Greenhouse and Lever are
generally fetchable directly. With Chrome available, opening the posting in a tab
is often fastest.

Extract and report:
- **The JD's own vocabulary.** Highest-value output of this step. The stakeholder
  list (if the JD names "data science, engineering, infrastructure, and
  operations," those four words belong in the summary verbatim). Named motions
  and skills: technical discovery, pipeline generation, forecasting, full-cycle
  ownership, co-sell, POC, land-and-expand. Named internal org units ("Solutions
  Engineering" vs "Solutions Architects"): match their name, not the
  industry-generic one. Named tools (Salesforce, ZoomInfo, Outreach, Gong):
  candidates for an accuracy-check edit, never an assumed one. The product
  category in their language.
- **Deal-size verbiage, verbatim.** If the JD states an ACV or deal-size range,
  quote it exactly. If the JD is silent, say so explicitly rather than staying
  silent. This decides whether the user's own deal-size figures read as fit or as
  overqualification.
- **Segment and seniority read.** One or two lines, enough to know whether to dial
  enterprise language up or down.
- Optional, only if the JD is thin: one search of the company site to get the
  product-category language right.

**A3. Generate the edit set** from the local PDF, as exact find/replace pairs, not
prose suggestions:

```
EDIT [n]: [target, which line or bullet]
FIND:    [exact current string]
REPLACE: [exact new string]
DELTA:   [+/- N characters]
WHY:     [the specific JD line or requirement this serves, one sentence]
CHECK:   [accuracy question for the user, or "none"]
```

- Highest-value target is usually the professional summary, specifically the
  stakeholder list and the closing methods clause. First thing a screener reads,
  cheapest place to mirror JD language.
- Preserve high-value bullets untouched. Metric lines (attainment, ACV, rankings)
  and the strongest narrative bullets generally should not be edited at all.
  Tailoring lands on framing lines, not proof lines.
- Pay for additions with cuts in the same line. Dropping "Consistently" and
  "solution selling" buys "forecasting." Show the arithmetic in DELTA.
- **DELTA is not the real constraint. Line wrap is.** A +16 character edit on a
  bullet already near the right margin costs a whole line; a +40 character edit
  mid-paragraph can cost nothing. Before committing, ask of each edited line: how
  close to the margin does it already sit? Bullets that currently end past roughly
  three quarters of the line width are the dangerous ones. Flag those in the edit
  set as wrap risks so the C7 outcome is predicted, not discovered.
- Aim for four to six edits. More is churn and raises the odds of a formatting
  incident for diminishing screening benefit.

**Present the edit set to the user and wait.** This is a hard gate. Every CHECK must
be resolved or its edit dropped. Never carry an unresolved CHECK into the
browser.

**A4. Create the company folder** once the set is approved:

```
mkdir -p "<OUTPUT_ROOT>/<Company>"
```

Use an existing folder if there is one. Do not create a variant spelling of a
folder that already exists (check the listing first).

## Lane B: Chrome, the document work

Requires the Claude in Chrome extension. Load the browser tools in one
ToolSearch call before starting. If Chrome is not connected, stop and tell the user,
and hand them the edit set to apply by hand.

**C1.** Open `<DOC_URL>` from the profile.

**C2. File > Make a copy.** Name it exactly `<FILENAME>` with the month, year and
company filled in. Leave the copy in the default Drive location unless the user says
otherwise. Work only in the copy. Never edit the original.

**C3. Read the copy's actual text before touching anything.** The document in
front of you is the truth for what is on the page.

**C4. Reconcile, and stop on mismatch.** If a FIND string does not appear in the
copy exactly:
- STOP. No partial match, no fuzzy match, no retyping the line from scratch, no
  applying the intent to whatever line looks closest.
- Report the FIND that missed, the actual text on that line, and the proposed
  REPLACE.
- Wait for the user's call. A wrong guess here corrupts a resume that gets sent to an
  employer.
- Several misses at once is the sync problem. Say so and recommend re-exporting
  the local PDF.

**C5. Apply each edit with find-and-replace** (Cmd + Shift + H), never by clicking
into the line and retyping. Find-and-replace is atomic and leaves character
formatting untouched.

Cmd + H is the macOS hide-application shortcut, not find-and-replace. Sending it
hides Chrome and stalls the run. Edit > Find and replace does the same job from
the menu if the shortcut does not land.

**C6. Report the match count for every replacement.** "EDIT 3: 1 match replaced."
A zero-match replacement is the quiet failure mode; any zero goes to C4.

**C7. Verify one page visually.** If content spilled to a second page, do not fix
it by shrinking margins, reducing font size, or deleting a bullet on your own
initiative.

**Default resolution: drop the edit on the oldest role first.** Work backwards up
the resume from the oldest role to the newest, dropping edits until it fits on
one page. Recency carries more screening weight, so the oldest role is the cheapest place to give something up. Apply this
default and report what was dropped and why. Only stop to ask when the default
would strip the single edit that mirrors the JD's most important requirement, or
when dropping every old-role edit still leaves it over.

Report the overflow, the edit that caused it, and the resolution either way.

**C8. Verify the hard rules on the changed lines only.** Scan for any em dash or
dash-as-punctuation introduced by autocorrect. Confirm no number changed.

**C9. Export.** File > Download > PDF Document (.pdf).

## Lane C: Claude Code, filing

**Cc1.** Locate the export. It lands in `~/Downloads/` named after the Doc copy,
possibly with `.docx` in the middle. A `(1)` suffix means a prior file of that
name exists: resolve it rather than filing a duplicate.

**Cc2.** Move and rename in one step, dropping any `.docx`:

```
mv "$HOME/Downloads/<FILENAME>.docx.pdf" "<OUTPUT_ROOT>/<Company>/<FILENAME>.pdf"
```

Check the destination does not already exist before moving, and refuse rather than
overwrite a previously filed resume.

**Cc3.** Verify the file exists at the destination, is non-zero, and is named
correctly. Report the full final path.

## What never happens here

- No restructuring, template changes, or font, margin, and spacing changes.
- No editing the original Google Doc. Only the copy.
- No submitting an application, no uploading the resume anywhere, no sending
  anything. Export, file, stop.
- No filling in an unanswered accuracy CHECK by assumption.
- No reading any resume from Google Drive.

## Out of scope

Deciding whether a role is worth pursuing at all (that is the job-search skill),
company research, outreach messages, and interview prep. If asked for those here,
do them as a separate task rather than folding them into the resume run.

## References

- `reference/resume-profile.template.md`: the profile to copy and fill in on the
  first run.
- `reference/preflight.md`: the one-time Google Docs autocorrect and Chrome
  download settings. Read it if a stray em dash appears or the download path
  behaves unexpectedly.
