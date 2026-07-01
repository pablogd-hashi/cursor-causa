#!/bin/sh
# Local Consul client agent + service registration + Connect Envoy sidecar.
set -eu

SERVICE_ID="${SERVICE_ID:?SERVICE_ID required}"
ADMIN_PORT="${ADMIN_PORT:-19000}"
DATA_DIR="/tmp/consul-sidecar-data"
CONFIG_DIR="/consul/config"

rm -rf "${DATA_DIR}"
mkdir -p "${DATA_DIR}"

cat > "${DATA_DIR}/agent.hcl" <<EOF
ports {
  grpc = 8502
}
EOF

NODE_NAME="${SERVICE_ID}-mesh-$(cat /proc/sys/kernel/random/uuid 2>/dev/null | cut -c1-8 || echo $$)"

consul agent \
  -config-file="${DATA_DIR}/agent.hcl" \
  -retry-join=consul \
  -bind=0.0.0.0 \
  -client=127.0.0.1 \
  -data-dir="${DATA_DIR}" \
  -node="${NODE_NAME}" \
  -log-level=error &

AGENT_PID=$!
trap 'kill "${AGENT_PID}" 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
  if consul members 2>/dev/null | grep -q "server"; then
    break
  fi
  sleep 1
done

# Wait for global proxy-defaults (consul-init) before registering Connect services.
for _ in $(seq 1 30); do
  if consul config read -kind proxy-defaults -name global >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

consul services register "${CONFIG_DIR}/services/${SERVICE_ID%%-*}.hcl"

exec consul connect envoy \
  -sidecar-for "${SERVICE_ID}" \
  -admin-bind "0.0.0.0:${ADMIN_PORT}" \
  -grpc-addr 127.0.0.1:8502 \
  -ignore-envoy-compatibility
