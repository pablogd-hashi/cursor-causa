#!/usr/bin/env bash
# Prepare the demo "regression": a branch that lowers the payments connection
# pool from 50 to 10 — the change the Cursor agent investigates and recommends
# reverting. This keeps `main` healthy (pool 50); the regression lives on a
# branch / PR.
#
# This script creates the branch and makes the one-line edit, then STOPS and
# prints the commit / push / PR commands for YOU to run. It does not commit or
# push.
#
# Run it only after your work is committed to main (it needs a clean tree).
set -euo pipefail
cd "$(dirname "$0")/.."

BRANCH="regression/lower-pool-size"
FILE="demo-app/payments/pool.py"

if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree is not clean. Commit your work to main first, then re-run." >&2
  exit 1
fi

git switch -c "$BRANCH" 2>/dev/null || git switch "$BRANCH"

python3 - "$FILE" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
text = p.read_text()
old, new = '"POOL_MAX_SIZE", "50"', '"POOL_MAX_SIZE", "10"'
if old not in text:
    sys.exit(f"expected {old} in {p}; not found (already changed?)")
p.write_text(text.replace(old, new))
print(f"edited {p}: pool default 50 -> 10")
PY

git add "$FILE"

cat <<EOF

Branch '$BRANCH' created and the change staged. To finish (you run these):

  git commit -m "Reduce payments connection pool to cut idle connections"
  git push -u origin $BRANCH
  gh pr create --base main --head $BRANCH --draft \\
    --title "Reduce payments connection pool to cut idle connections" \\
    --body "Lowers POOL_MAX_SIZE from 50 to 10 in demo-app/payments/pool.py."

Then investigate the regression live (main stays healthy at pool 50):

  CAUSA_INVESTIGATOR=cursor CURSOR_TARGET_REF=$BRANCH CURSOR_API_KEY=... ./demo.sh

The agent investigates the branch, runs the test (fails at 10), and recommends
reverting to 50.
EOF
