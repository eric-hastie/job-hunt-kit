#!/bin/bash
# Fails when ATS or discovery vocabulary appears in the job-search skill.
#
# The two skills share one body of posting knowledge, and it lives in
# find-job-postings. A convention alone gets broken, so this complains.
# Prints how many files it scanned and refuses to pass on zero.
SK="${SKILLS_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
files=$(find "$SK/job-search" -name '*.md' 2>/dev/null)
n=$(printf '%s' "$files" | grep -c . || true)
echo "scanned $n file(s) under $SK/job-search"
if [ "$n" -eq 0 ]; then
  echo "FAIL: no job-search files found; nothing was checked"; exit 2
fi
BAD='greenhouse|ashby|lever\b|smartrecruiters|workday|ats slug|careers page|eight routes|totalFound|job board'
hits=$(grep -inE "$BAD" $files \
       | grep -viE 'find-job-postings|invoke it before|owns all ATS' || true)
if [ -n "$hits" ]; then
  echo "DRIFT: ATS knowledge has leaked into the job-search skill."
  echo "It belongs in find-job-postings. Offending lines:"
  echo "$hits" | sed 's|'"$SK"'/||'
  exit 1
fi
echo "no drift: job-search carries no ATS knowledge"
