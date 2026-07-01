#!/usr/bin/env bash
# Create the demo regression PR on GitHub: lowers POOL_MAX_SIZE 50→10 in pool.py.
#
# Does not merge — merge the PR manually on GitHub. When an alert fires and
# CAUSA_TRIAGE=mcp, GitHub MCP lists that merged PR in the investigation brief.
#
# Requires: gh auth login, clean working tree on main, main at pool default 50.
#
# Usage:
#   ./scripts/create-regression-pr.sh
#   DRAFT=0 ./scripts/create-regression-pr.sh   # ready-for-review PR (not draft)
set -euo pipefail
cd "$(dirname "$0")/.."

BRANCH="regression/lower-pool-size"
FILE="demo-app/payments/pool.py"
HEALTHY='"POOL_MAX_SIZE", "50"'
BROKEN='"POOL_MAX_SIZE", "10"'
COMMIT_MSG="Reduce payments connection pool to cut idle connections"
PR_TITLE="Reduce payments connection pool to cut idle connections"
PR_BODY="$(cat <<'EOF'
Lowers `POOL_MAX_SIZE` from 50 to 10 in `demo-app/payments/pool.py`.

Demo regression for Causa: merge this PR, then run the incident demo with
`CAUSA_TRIAGE=mcp` so GitHub MCP surfaces this change in triage when the alert fires.
EOF
)"
DRAFT="${DRAFT:-1}"

die() { echo "error: $*" >&2; exit 1; }

if [ -n "$(git status --porcelain)" ]; then
  die "working tree is not clean — commit or stash changes first"
fi

command -v gh >/dev/null || die "gh not found — install GitHub CLI and run: gh auth login"
gh auth status >/dev/null 2>&1 || die "gh not authenticated — run: gh auth login"

git switch main
git pull --ff-only origin main 2>/dev/null || true

if ! grep -q "$HEALTHY" "$FILE"; then
  if grep -q "$BROKEN" "$FILE"; then
    die "main already has the regression (pool default 10). Revert the merge or restore pool 50 on main first."
  fi
  die "expected $HEALTHY in $FILE"
fi

# Drop a stale local branch so we always branch fresh from main.
git branch -D "$BRANCH" 2>/dev/null || true
git switch -c "$BRANCH"

python3 - "$FILE" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
text = p.read_text()
old, new = '"POOL_MAX_SIZE", "50"', '"POOL_MAX_SIZE", "10"'
if old not in text:
    sys.exit(f"expected {old} in {p}")
p.write_text(text.replace(old, new))
print(f"edited {p}: pool default 50 -> 10")
PY

git add "$FILE"
git commit -m "$COMMIT_MSG"

echo "==> pushing $BRANCH"
git push -u origin "$BRANCH" --force-with-lease

EXISTING_URL="$(gh pr list --head "$BRANCH" --json url --jq '.[0].url' 2>/dev/null || true)"
if [ -n "$EXISTING_URL" ] && [ "$EXISTING_URL" != "null" ]; then
  echo "==> PR already open: $EXISTING_URL"
  PR_URL="$EXISTING_URL"
else
  echo "==> creating pull request"
  PR_ARGS=(pr create --base main --head "$BRANCH" --title "$PR_TITLE" --body "$PR_BODY")
  if [ "$DRAFT" = "1" ]; then
    PR_ARGS+=(--draft)
  fi
  PR_URL="$(gh "${PR_ARGS[@]}")"
  echo "==> $PR_URL"
fi

cat <<EOF

Next steps (merge triggers live GitHub triage):

  1. Merge the PR on GitHub: $PR_URL
  2. Rebuild the payments app (picks up the merged code):
       task substrate:up
     Or induce the incident via env override (works before merge too):
       task break
  3. Run the demo with live MCP triage:
       CAUSA_TRIAGE=mcp task demo
     Requires: mcp-grafana + github-mcp-server on PATH, tokens in .env
     See docs/mcp-triage.md

When PaymentsHighLatencyP99 fires, GitHub MCP lists your merged PR in the brief.
EOF
