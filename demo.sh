#!/usr/bin/env bash
# Causa — one-command end-to-end demo.
#
# Brings up the observability stack, fires a REAL pool-exhaustion incident in the
# background (PaymentsHighLatencyP99 fires in ~90s and Alertmanager posts it to
# Causa, auto-starting an investigation), and launches the Causa API + console.
# Ends in the running console; Ctrl-C stops the API/console and the load.
#
# Mock investigator by default (reliable). For a live Cursor cloud agent:
#   CAUSA_INVESTIGATOR=cursor CURSOR_API_KEY=... ./demo.sh
set -euo pipefail
cd "$(dirname "$0")"

SUBSTRATE="otel-collector prometheus alertmanager loki jaeger grafana demo-app"

echo "==> 1/4 observability stack"
docker compose up -d $SUBSTRATE >/dev/null
# Pick up the host.docker.internal webhook target.
docker compose up -d --force-recreate alertmanager >/dev/null

echo "==> 2/4 firing a real incident in the background (alert in ~90s)"
./break.sh 10 300 150 >/tmp/causa_demo_break.log 2>&1 &
cleanup() {
  echo "stopping demo load..."
  pkill -f "break.sh" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> 3/4 endpoints"
echo "    Console      : http://localhost:8501   (open in Cursor: Simple Browser)"
echo "    Prometheus   : http://localhost:9090/alerts"
echo "    Alertmanager : http://localhost:9093"
echo "    Grafana      : http://localhost:3000/d/payments/payments"
echo "    Cursor agents: https://cursor.com/agents"
echo
echo "    The real alert auto-starts an investigation when it fires. You can also"
echo "    click 'Simulate payments alert' in the console for an instant one."
echo

echo "==> 4/4 launching Causa API + console (Ctrl-C to stop)"
# Not exec'd, so the EXIT trap fires and stops the background load on Ctrl-C.
./run-local.sh
