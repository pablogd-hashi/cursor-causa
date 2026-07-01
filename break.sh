#!/usr/bin/env bash
# Induce the payments incident: recreate demo-app with a small connection pool,
# then drive concurrent load until PaymentsHighLatencyP99 fires.
#
# With the mesh profile up (task mesh:up), load goes through Envoy → web → api
# → payments so traces populate the service graph. Without mesh, hits :8080 directly.
#
# Usage: ./break.sh [POOL_MAX_SIZE] [DURATION_SECONDS] [CONCURRENCY]
set -euo pipefail
cd "$(dirname "$0")"

POOL="${1:-10}"
DURATION="${2:-180}"
CONC="${3:-150}"

DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  DOCKER="sudo docker"
fi

echo "==> Recreating demo-app with POOL_MAX_SIZE=${POOL}"
POOL_MAX_SIZE="${POOL}" ${DOCKER} compose up -d --force-recreate demo-app

echo "==> Waiting for demo-app to come up"
for _ in $(seq 1 30); do
  if curl -fsS localhost:8080/healthz >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS localhost:8080/healthz && echo

MESH_ENTRY=""
if curl -fsS localhost:21000/ >/dev/null 2>&1; then
  MESH_ENTRY="http://localhost:21000/"
  echo "==> Mesh entry detected — driving load through ${MESH_ENTRY}"
else
  echo "==> No mesh entry on :21000 — driving load directly to :8080/charge"
fi

echo "==> Driving ${CONC} concurrent requests for ${DURATION}s"
end=$((SECONDS + DURATION))
while [ "${SECONDS}" -lt "${end}" ]; do
  if [ -n "${MESH_ENTRY}" ]; then
    seq "${CONC}" | xargs -P "${CONC}" -I{} \
      curl -fsS "${MESH_ENTRY}" -o /dev/null || true
  else
    seq "${CONC}" | xargs -P "${CONC}" -I{} \
      curl -fsS -X POST "localhost:8080/charge?amount=1" -o /dev/null || true
  fi
done

echo "==> Load complete."
echo "    Alert:        http://localhost:9090/alerts"
echo "    Alertmanager: http://localhost:9093"
echo "    Dashboard:    http://localhost:3000/d/payments/payments"
echo "    Service graph: http://localhost:3000/d/service-to-service"
echo "    Run ./fix.sh to restore a healthy pool."
