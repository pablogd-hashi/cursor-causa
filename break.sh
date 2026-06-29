#!/usr/bin/env bash
# Induce the payments incident: recreate the demo-app with a small connection
# pool, then drive concurrent load until PaymentsHighLatencyP99 fires.
# Reversible with ./fix.sh.
#
# Usage: ./break.sh [POOL_MAX_SIZE] [DURATION_SECONDS] [CONCURRENCY]
#   defaults: 10  180  40
set -euo pipefail
cd "$(dirname "$0")"

POOL="${1:-10}"
DURATION="${2:-180}"
CONC="${3:-150}"

echo "==> Recreating demo-app with POOL_MAX_SIZE=${POOL}"
POOL_MAX_SIZE="${POOL}" docker compose up -d --force-recreate demo-app

echo "==> Waiting for demo-app to come up"
for _ in $(seq 1 30); do
  if curl -fsS localhost:8080/healthz >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS localhost:8080/healthz && echo

echo "==> Driving ${CONC} concurrent charges for ${DURATION}s"
end=$((SECONDS + DURATION))
while [ "${SECONDS}" -lt "${end}" ]; do
  seq "${CONC}" | xargs -P "${CONC}" -I{} \
    curl -fsS -X POST "localhost:8080/charge?amount=1" -o /dev/null || true
done

echo "==> Load complete."
echo "    Alert:        http://localhost:9090/alerts"
echo "    Alertmanager: http://localhost:9093"
echo "    Dashboard:    http://localhost:3000/d/payments/payments"
echo "    Run ./fix.sh to restore a healthy pool."
