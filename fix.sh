#!/usr/bin/env bash
# Restore a healthy connection pool. Usage: ./fix.sh [POOL_MAX_SIZE] (default 50)
set -euo pipefail
cd "$(dirname "$0")"

POOL="${1:-50}"
echo "==> Recreating demo-app with POOL_MAX_SIZE=${POOL}"
POOL_MAX_SIZE="${POOL}" docker compose up -d --force-recreate demo-app
curl -fsS localhost:8080/healthz && echo
