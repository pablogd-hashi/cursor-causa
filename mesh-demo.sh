#!/usr/bin/env bash
# Interactive mesh demo — step through Consul, service graph, and Causa triage.
#
# Usage:  ./mesh-demo.sh          (pauses at each step; press Enter)
#         ./mesh-demo.sh -y       (auto-advance, 5s per step)
set -euo pipefail
cd "$(dirname "$0")"

AUTO=false
[[ "${1:-}" == "-y" ]] && AUTO=true

DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  DOCKER="sudo docker"
fi

PY=./.venv/bin/python
step() {
  local title="$1"
  local body="$2"
  echo
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  $title"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "$body" | sed 's/^/  /'
  echo
  if $AUTO; then
    sleep 5
  else
    read -r -p "  Press Enter to continue… "
  fi
}

wait_healthy() {
  local url="$1" label="$2" tries="${3:-30}"
  for _ in $(seq 1 "$tries"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "  ✓ $label"
      return 0
    fi
    sleep 2
  done
  echo "  ✗ $label (timed out)"
  return 1
}

show_consul() {
  curl -fsS 'http://localhost:8500/v1/health/state/passing' 2>/dev/null | \
    $PY -c "
import json,sys
seen=set()
for x in json.load(sys.stdin):
    s=x.get('ServiceName','')
    if s and s not in seen:
        seen.add(s)
        print(f'  ✓ {s}')
" 2>/dev/null || echo "  (Consul not ready)"
}

show_graph() {
  local tries="${1:-5}"
  for _ in $(seq 1 "$tries"); do
    if out=$(curl -fsS 'http://localhost:9090/api/v1/query?query=traces_service_graph_request_total' 2>/dev/null); then
      echo "$out" | $PY -c "
import json,sys
d=json.load(sys.stdin)
edges=set()
for r in d.get('data',{}).get('result',[]):
    m=r.get('metric',{})
    c,s=m.get('client','?'),m.get('server','?')
    if c and s:
        edges.add(f'{c} → {s}')
if edges:
    for e in sorted(edges):
        print(f'  {e}')
else:
    print('  (no edges yet)')
    sys.exit(1)
" && return 0
    fi
    sleep 5
  done
  echo "  (Prometheus not ready — open http://localhost:9090/graph)"
}

wait_mesh_services() {
  local want="api api-sidecar-proxy payments payments-sidecar-proxy web web-sidecar-proxy"
  for _ in $(seq 1 30); do
    local have
    have=$(curl -fsS 'http://localhost:8500/v1/health/state/passing' 2>/dev/null | \
      $PY -c "
import json,sys
print(' '.join(sorted({x.get('ServiceName','') for x in json.load(sys.stdin) if x.get('ServiceName')})))
" 2>/dev/null || echo "")
    local ok=true
    for s in $want; do
      echo "$have" | grep -qw "$s" || ok=false
    done
    if $ok; then
      echo "  ✓ all 6 mesh services passing"
      return 0
    fi
    sleep 2
  done
  echo "  ⚠ not all mesh services passing yet (sidecars may still be starting)"
  return 1
}

show_topology() {
  CAUSA_TOPOLOGY=consul $PY -c "
from causa.topology import get_topology
t=get_topology()
deps=t.dependents('payments')
print(f'  graph_source : {t.graph_source}')
print(f'  dependents   : {deps}')
" 2>/dev/null || echo "  (topology query failed)"
}

# ── Step 0: prerequisites ────────────────────────────────────────────────────
step "0 · Prerequisites" \
"Checks Docker and the Python venv. The mesh demo needs both.

  task setup          # if you have not run this yet"

if ! $DOCKER info >/dev/null 2>&1; then
  echo "  Docker is not running. Start dockerd and retry."
  exit 1
fi
test -x "$PY" || { echo "  Run: task setup"; exit 1; }
echo "  ✓ Docker and venv OK"

# ── Step 1: bring up stack ───────────────────────────────────────────────────
step "1 · Start the mesh stack" \
"Brings up observability + a minimal Consul Connect mesh:

  web (:9080) → api (:9091) → payments/demo-app (:8080)

Each mesh service has an Envoy sidecar. Consul catalog starts fresh
(old ghost nodes are wiped). Loadgen drives steady traffic."

echo "  Starting…"
$DOCKER volume rm causa_consul-data 2>/dev/null || true
$DOCKER compose --profile mesh up -d --build \
  otel-collector prometheus alertmanager loki jaeger grafana demo-app \
  consul consul-init api api-sidecar web web-sidecar payments-sidecar loadgen \
  >/dev/null

wait_healthy http://localhost:8500/v1/status/leader "Consul server"
wait_healthy http://localhost:8080/healthz "payments (demo-app)"
wait_healthy http://localhost:9080/health "web (mesh entry)"
wait_mesh_services || true

# ── Step 2: Consul UI ────────────────────────────────────────────────────────
step "2 · Consul UI — mesh health" \
"Open:  http://localhost:8500

You should see exactly three mesh services + three sidecar proxies,
all passing (no red ghost nodes from prior runs):

  web, api, payments
  web-sidecar-proxy, api-sidecar-proxy, payments-sidecar-proxy

Click a service → Instances to see the Connect sidecar."

echo "  Passing checks:"
show_consul

# ── Step 3: trace the request path ───────────────────────────────────────────
step "3 · Follow one request" \
"The loadgen hits web:9090/. That fans out:

  curl http://localhost:9080/
    → web (fake-service)
      → api (fake-service, Zipkin trace)
        → payments (demo-app GET /, OTLP trace)
          → connection pool acquire + simulated work

Open Jaeger:  http://localhost:16686
  Service: payments   Look for spans from the mesh path."

echo "  Sample request:"
curl -fsS http://localhost:9080/ | $PY -c "import json,sys; d=json.load(sys.stdin); print(f'  web response: {d.get(\"name\",\"?\")} upstream_ok={\"upstream_uris\" in d}')" 2>/dev/null || echo "  (request failed)"

# ── Step 4: service graph ────────────────────────────────────────────────────
step "4 · Service graph (live topology)" \
"The OTel servicegraph connector derives edges from Zipkin/OTLP traces
and exposes traces_service_graph_request_total in Prometheus.

Open Grafana:  http://localhost:3000/d/service-to-service
  You should see:  web → api → payments

Prometheus:  http://localhost:9090/graph
  Query: traces_service_graph_request_total"

echo "  Waiting 20s for servicegraph metrics…"
sleep 20
echo "  Edges:"
show_graph 6

# ── Step 5: Causa topology source ────────────────────────────────────────────
step "5 · Live blast radius (CAUSA_TOPOLOGY=consul)" \
"Causa queries Prometheus for who depends on payments, then walks
the reverse graph (BFS) for transitive dependents.

Compare with the offline declared graph:
  CAUSA_TOPOLOGY=declared  → reads topology.yaml (checkout, refunds…)
  CAUSA_TOPOLOGY=consul    → reads live servicegraph metrics"

echo "  Declared (offline):"
CAUSA_TOPOLOGY=declared $PY -c "from causa.topology import get_topology; t=get_topology(); print(f'    {t.graph_source}: {t.dependents(\"payments\")}')"
echo "  Live (mesh):"
show_topology

# ── Step 6: start Causa API ──────────────────────────────────────────────────
step "6 · Start Causa API" \
"Launches the API on :8000 with CAUSA_TOPOLOGY=consul so triage uses
the live mesh graph. The console is optional — this step uses curl.

If the API is already running, we reuse it."

API_PID=""
if curl -fsS http://localhost:8000/healthz >/dev/null 2>&1; then
  echo "  ✓ API already running on :8000"
else
  echo "  Starting API (CAUSA_TOPOLOGY=consul)…"
  CAUSA_TOPOLOGY=consul $PY -m uvicorn causa.api:app --host 0.0.0.0 --port 8000 &
  API_PID=$!
  sleep 2
  wait_healthy http://localhost:8000/healthz "Causa API"
fi

# ── Step 7: trigger triage ───────────────────────────────────────────────────
step "7 · Trigger triage" \
"Fires a simulated PaymentsHighLatencyP99 alert. Causa will:
  1. Query Prometheus servicegraph → blast_radius_hint
  2. Run mock Grafana/GitHub triage
  3. Run the mock investigator → RCA

Same as clicking 'Simulate payments alert' in the console."

RESP=$(curl -fsS -X POST http://localhost:8000/investigations \
  -H 'Content-Type: application/json' \
  -d '{"alertname":"PaymentsHighLatencyP99","service":"payments"}')
INV_ID=$(echo "$RESP" | $PY -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "  Investigation: $INV_ID"
echo "  Waiting for triage…"
sleep 4

RECORD=$(curl -fsS "http://localhost:8000/investigations/${INV_ID}")
echo "$RECORD" | $PY -c "
import json,sys
r=json.load(sys.stdin)
b=r.get('brief') or {}
print(f\"  status              : {r.get('status')}\")
print(f\"  blast_radius_hint   : {b.get('blast_radius_hint')}\")
print(f\"  graph_source        : {b.get('blast_radius_graph_source')}\")
print(f\"  metric_signatures   : {len(b.get('metric_signatures',[]))} from Grafana mock\")
print(f\"  candidate_changes   : {len(b.get('candidate_changes',[]))} from GitHub mock\")
rca=r.get('rca') or {}
if rca:
    br=rca.get('blast_radius',{})
    print(f\"  RCA blast_radius    : {br.get('if_rolled_back')}\")
    print(f\"  RCA graph_source    : {br.get('graph_source')}\")
"

# ── Step 8: console (optional) ───────────────────────────────────────────────
step "8 · Console (optional)" \
"For the full three-pane UI:

  CAUSA_TOPOLOGY=consul ./run-local.sh
  Open:  http://localhost:8501

Select the investigation on the left. The RCA pane shows blast radius
with graph_source 'consul-mesh (servicegraph)'.

To fire a real alert from mesh traffic:
  ./break.sh          (detects :9080 mesh entry automatically)"

# ── Step 9: break (optional) ─────────────────────────────────────────────────
step "9 · Break the pool (optional)" \
"Recreates payments at POOL_MAX_SIZE=10 and drives mesh load until
PaymentsHighLatencyP99 fires (~90s). Skip if you are done.

  ./break.sh"

if $AUTO; then
  echo "  (auto mode — skipping break)"
else
  read -r -p "  Run ./break.sh now? [y/N] " ans
  if [[ "${ans,,}" == "y" ]]; then
    ./break.sh 10 120 200
  fi
fi

# cleanup API if we started it
if [[ -n "$API_PID" ]]; then
  kill "$API_PID" 2>/dev/null || true
fi

echo
echo "Done. Useful URLs:"
echo "  Consul   http://localhost:8500"
echo "  Mesh     http://localhost:9080/"
echo "  Grafana  http://localhost:3000/d/service-to-service"
echo "  Console  http://localhost:8501  (run: CAUSA_TOPOLOGY=consul ./run-local.sh)"
