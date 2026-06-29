#!/usr/bin/env bash
# Run the Causa API and console locally (outside Docker) for the demo.
# Uses the project venv. Mock triage + mock investigator by default; set
# CAUSA_INVESTIGATOR=cursor (and CURSOR_API_KEY) for a live cloud run.
set -euo pipefail
cd "$(dirname "$0")"

PY=./.venv/bin/python
$PY -c "import fastapi, streamlit" 2>/dev/null || {
  echo "installing deps into .venv ..."
  $PY -m pip install -q -r requirements.txt
}

echo "==> Causa API on http://localhost:8000"
$PY -m uvicorn causa.api:app --host 0.0.0.0 --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

sleep 2
echo "==> Causa console on http://localhost:8501"
CAUSA_API_URL="http://localhost:8000" \
  ./.venv/bin/streamlit run console/app.py \
  --server.address=0.0.0.0 --server.port=8501 --server.headless=true
