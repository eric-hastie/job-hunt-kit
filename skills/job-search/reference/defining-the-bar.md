# Defining the bar

The bar is what a posting must clear to make the list. Read this before setting
a single filter. Every lesson here came from a real search that went wrong.

## Every bar failure so far has been the same failure

Look at them together:

- A **4-year experience floor** invented from the candidate's own tenure, never
  asked for, and the main reason results were thin for weeks.
- A **comp floor** screening a posted base figure against an OTE threshold. For
  an AE, base is typically ~50% of OTE, so a posted "$80-90K" is usually a
  $160-180K OTE role. It silently dropped good fits.
- **`companyKeywords:["B2B","SaaS"]` with AND**, which matched literal company
  description text: 45 jobs with it, 850 without.
- A **clinical-credential exclusion** that would have dropped a genuine fit,
  because it did not account for credentials the candidate actually holds.

One failure, four costumes: **criteria invented or mis-specified, then trusted
without measuring what they cost.**

## Rules

**Never invent a criterion from the person's background.** A fact about someone's
resume is not a screening rule. If it seems like one, state it as a question, not
a rule, and label which constraints came from them versus which you derived.

**No floors unless the person asked for one.** Experience: test the ceiling only.
Reject a posting for demanding *more* than the ceiling, never for demanding less.
Early-career, associate-level and unstated-experience roles qualify.

**Never reject on posted comp.** Boards publish base, not OTE. Record the number,
note base-versus-OTE if the posting says which, and never drop on it. Both floor
and ceiling have the identical defect.

**Exclusion rules must respect credentials the person does hold.** A posting
asking for "MA / LPN / CNA / EMT / Pharmacy Tech" is a genuine fit when they hold
one of those, not a drop. A BCBA-required role scored 86 and sat near the top
because "Active BCBA" slipped past the exclusion, which is the same rule failing
in the other direction.

## Measure what a filter costs before trusting it

This is the discipline that catches all of the above. Run the search with and
without each filter and record the difference in rows. A real example, from one
listing site's search API:

From an 850-row baseline:

| Filter removed | Rows |
| --- | --- |
| `companyKeywords` AND | 850 (with it: 45) |
| comp | +84 |
| YOE | +64 |
| industries | +65 |

Removing the comp filter took a full pull from 1,807 to 2,479 jobs. Widening the
bar roughly tripled the useful yield, and the finding was that **the 4-year floor
was the expensive filter, not comp.**

Nobody would have guessed that ordering. Measure it.

## Eyeball the top of the scored output before shipping

Read the top ~10 rows and ask whether each one belongs. Both kinds of mistake get
caught this way: a row that should not be at the top, and a good role wrongly
dismissed because its title looked off.

## What a job-hunt bar is made of

Role and level (for a sales search: is this an individual-contributor closing
role, not SDR or Director). Location and work arrangement, verified against the
posting body rather than the label. Credentials, both required and held.
Experience ceiling. Segment or seniority, tagged rather than filtered, because it
is usually absent from the title. Pay recorded, never screened.

The person's own bar lives in `~/job-hunt/bar.md`, never in this file.
