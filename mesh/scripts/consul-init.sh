#!/usr/bin/env sh
# Apply Connect config entries once Consul is healthy. Idempotent on re-run.
set -eu

CONSUL_HTTP_ADDR="${CONSUL_HTTP_ADDR:-http://consul:8500}"
CONFIG_DIR="${CONFIG_DIR:-/consul/config}"

echo "waiting for Consul at ${CONSUL_HTTP_ADDR}..."
for _ in $(seq 1 60); do
  if wget -q -O /dev/null "${CONSUL_HTTP_ADDR}/v1/status/leader" 2>/dev/null; then
    break
  fi
  sleep 2
done

consul config write "${CONFIG_DIR}/proxy-defaults.hcl"
consul config write "${CONFIG_DIR}/service-defaults.hcl"
consul config write "${CONFIG_DIR}/intentions-allow.hcl"

echo "Consul config entries applied."
