# One-time preflight

Do these once, before the first run. They are per-document and per-browser
settings, not per-role steps.

## 1. Google Docs autocorrect (the em dash trap)

Open the master Doc (`<DOC_URL>` in `~/job-hunt/resume-profile.md`).

**Tools > Preferences**, uncheck **automatic substitution** and **smart quotes**.

Google Docs silently converts a double hyphen into an em dash and straight quotes
into curly ones. This is the single most likely way a hard-rule violation reaches
the final PDF, and it happens without any visible signal. Preferences are stored
per document, so doing it once on the master is enough; copies inherit it.

If a stray em dash shows up in a finished PDF, this is the first thing to
re-check on the master.

## 2. Chrome download behavior

Two workable setups, pick one:

- **Leave Chrome downloading to `~/Downloads`** (what the workflow assumes).
  Claude Code moves the file into the company folder at step Cc2.
- **Enable Chrome's "Ask where to save each file"** setting. Chrome can then be
  pointed straight at the company folder and step Cc2 becomes unnecessary. The
  folder must already exist, so step A4 still runs first.

Chrome cannot choose a save path unless "ask where to save" is enabled, so
without it there is no way to skip the move.

## 3. The sync invariant

The local generic PDF and the master Google Doc must hold the same content. FIND
strings are generated from the PDF and applied to a copy of the Doc; if the two
have drifted, every FIND returns zero matches and the run stalls at C4.

The fix is not to improvise replacements. The user re-exports the Doc to PDF, replaces
the local generic file, and the run restarts. A systematic zero-match across
multiple edits is a sync problem, not an editing problem, and should be named as
such immediately.
