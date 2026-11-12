#!/bin/bash
# Copies the three skills into ~/.claude/skills and creates ~/job-hunt.
# Refuses to overwrite a skill that already exists unless run with --force.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/skills"
mkdir -p "$DEST" "$HOME/job-hunt"
n=0
for s in find-job-postings job-search resume-tailor; do
  if [ -e "$DEST/$s" ] && [ "$1" != "--force" ]; then
    echo "SKIPPED $s: $DEST/$s already exists (re-run with --force to replace it)"
    continue
  fi
  rm -rf "$DEST/$s"
  cp -R "$HERE/skills/$s" "$DEST/$s"
  echo "installed $s -> $DEST/$s"
  n=$((n+1))
done
echo "$n of 3 skills installed. Working folder: $HOME/job-hunt"
python3 "$DEST/find-job-postings/tools/sweep_board.py" --selftest | tail -1
