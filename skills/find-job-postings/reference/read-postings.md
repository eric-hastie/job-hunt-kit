# Reading a posting

Turning postings into intelligence. Applies to both purposes: the same mistakes
produce a wrong account score and a wrong job match.

## Capture the text before analyzing it

**Postings come down and are then unrecoverable.** Phonely's eval req, one of
only three eval-flagged and from a Hot account, was captured as metadata only,
was taken down, and is permanently gone.

Archive three files per posting:

| File | Why |
| --- | --- |
| `<slug>.source.json` | the ATS API record, **authoritative**, because Ashby and Lever posting pages are JS-rendered and the raw HTML contains no description at all |
| `<slug>.page.html` | the exact bytes served |
| `<slug>.snapshot.html` | standalone readable, printable to PDF |

Posted dates: Ashby `publishedAt`, Lever `createdAt` (epoch ms), otherwise scrape
`datePosted` from JSON-LD.

## Use a wide title filter

The original passes matched QA and test job **titles**, which made whole
categories structurally invisible: Sabre's Principal AI/ML Engineer establishing
evaluation harnesses, Duck Creek's VP of Agentic AI, Toast's Voice AI Platform
req.

`TITLE_WIDE` in `sweep_board.py:116` is deliberately over-inclusive. **The cost
of a false positive is one line of reading. The cost of a false negative is a
wrong score.**

Also include **packaged-app titles** when sweeping enterprises: Salesforce QA
Engineer, SAP Test Engineer, Workday, ServiceNow, Oracle. A search for SDET or
automation misses them entirely.

## A keyword hit is not a finding. Eyeball every match.

Print the matched context and read it. Keyword hits have produced false positives
on every board swept so far.

Real examples, all of which scored before someone looked:

- **Marqeta**: every posting contains "testing" via a boilerplate pre-employment
  line, so a keyword count reads 40. The real number is 0.
- **Fifth Third**: its only QA-titled req is a Mortgage Servicing Quality Control
  Analyst reviewing loan files. Its text says "test results" meaning loan files.
- **Visa**: "voice" was a contact-centre Client Care Quality Analyst plus office
  boilerplate about communicating by telephone. "eval" was manual call review and
  technical evaluations during procurement.
- **Affirm**: "Group PM, Agent Enablement" is contact-centre **human** agents.
- **"Go"** false-positives on "go live". Only count it as Golang. Same care for
  Linear, Vertex, Jest.
- **StradVision**: `svn` matched 31 times across 14 reqs and every single one was
  inside **SVNet**, the company's own product name. Standalone SVN: zero. A
  product name is the highest-risk substring on a board because it repeats in the
  boilerplate of every posting, so one unanchored pattern scores the whole board.
  Anchor the pattern (`\bsvn\b(?!et)`) and print the matched **token**, not just
  the surrounding window: the window looked plausible and hid the cause.
- **StradVision, opposite direction**: `generative ai`, `llm` and `codegen` all
  hit, but every match described the **product** (synthetic training data,
  LLM-generated edge cases, NPU codegen). None was a coding agent. When the
  company sells AI, its own AI vocabulary is boilerplate, and an
  agent-adoption signal read off that text is measuring the product.

That pass killed 6 false positives and found one real signal that had been
missed. Both directions.

**Every counted QA req must be confirmed software QA.** Large enterprises run
manufacturing, clinical and compliance "QA" that is not testing.

## Req age is a signal and it cuts both ways

**Never treat an undated req as fresh.**

- A **generic** req open for years is an evergreen ATS pipeline posting and
  should stop counting. ConverseNow's three QA reqs are 964 to 1,792 days old,
  one open since August 2021, and they were contributing +20 to its score.
- A **specialist** req open a long time means they cannot hire it, which is the
  strongest tool-versus-headcount opening available. Cartesia's Evaluations Lead
  at 280 days.

Working definition of hard-to-fill: a specialist role open 90 to 540 days, or one
observed taken down and reposted. Generic titles excluded. 90 sits above a normal
fill cycle; past 540 a posting stops being a real search.

## Record the tools named in every posting

What a team already runs is both the displacement angle and the vocabulary the
first email should borrow. Mine each archived posting
into a per-company tool map, grouped by category, with the count of postings
naming each tool.

## Segment is usually missing from the title, not from the market

61% of aggregator rows carry no segment word in the title. When agents actually
read the JD, about half resolve to mid-market (76 of 148 in one tranche).
Separately, 35 rows already recorded as Enterprise were re-read and corrected.

**When mid-market looks thin, suspect labelling and filtering before concluding
the market is thin.**

## Do not select a universe on a signal and then score that signal

The agentic enterprise board is known-broken for exactly this: accounts were
selected for having an eval req and then scored on having an eval req, so two of
five factors are near-constant and scores bunch at 65 to 100.

If the entry criterion is the signal, the score must come from something else:
req age, count of independent reqs, whether the agent touches money, whether they
are building their own platform (displacement, not greenfield).

## Publishing extracts, not full JDs

Republishing full third-party JD text is a copyright problem, and reformatting
does not fix it, because copyright is in the words. Only amount and purpose
matter.

If publishing, split each posting and publish only the
role, responsibilities, requirements, tech stack and stated pay, dropping company
marketing, benefits, perks, and visa/EEO/background boilerplate. Full verbatim
text stays private.

Verify the output: zero files matching
`equal opportunity|401(k)|visa sponsor|headquartered in|is the leading`.

Traps that cost time when writing that splitter: `[A-Z]` under `re.I` matches lowercase and
silently dropped every "About the Role"; it used to `continue` without writing
when nothing was kept, leaving stale files that looked like current output, so it
now clears the output directory first; Lever's `descriptionPlain` is one
paragraph with no blank lines, so section cleaning has to fall back to line level.
