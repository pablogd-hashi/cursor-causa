# Consul Connect mesh demo

Causa can run the payments incident demo on a **minimal Consul Connect mesh**
with trace-derived blast radius. The offline path (`CAUSA_TOPOLOGY=declared`) is
unchanged.

## Topology (simplified)

```
web (:9080) → api (:9091) → payments/demo-app (:8080)
```

Three mesh services, three Envoy sidecars, one loadgen. No gateways, cache,
currency, or rates — enough to demonstrate live blast radius from traces.

## Quick start — interactive walkthrough

```bash
task setup
task mesh:demo          # pauses at each step; press Enter
# or
./mesh-demo.sh -y       # auto-advance (5s per step)
```

The script walks through:

1. Start stack (fresh Consul catalog — no ghost nodes)
2. Consul UI — verify web / api / payments + sidecars
3. Trace one request through the mesh
4. Service graph in Grafana / Prometheus
5. `CAUSA_TOPOLOGY=consul` vs `declared` blast radius
6. Start Causa API
7. **Trigger triage** (`POST /investigations`) and show live `blast_radius_hint`
8. Optional console + break steps

## Manual commands

```bash
task mesh:up            # wipes consul-data volume, starts fresh

open http://localhost:8500                          # Consul UI
curl http://localhost:9080/                         # mesh entry
open http://localhost:3000/d/service-to-service     # Grafana graph

CAUSA_TOPOLOGY=consul ./run-local.sh                # API + console
# Console → "Simulate payments alert"  OR:
curl -X POST http://localhost:8000/investigations \
  -H 'Content-Type: application/json' \
  -d '{"alertname":"PaymentsHighLatencyP99","service":"payments"}'

./break.sh              # pool=10, mesh load via :9080
```

## Endpoints

| URL | Purpose |
|-----|---------|
| http://localhost:8500 | Consul UI |
| http://localhost:9080/ | Mesh entry (web → api → payments) |
| http://localhost:9091/ | api directly (debug) |
| http://localhost:8080/healthz | payments directly |
| http://localhost:3000/d/service-to-service | Service dependency graph |
| http://localhost:8501 | Causa console |

## Environment flags

| Variable | Default | Meaning |
|----------|---------|---------|
| `CAUSA_TOPOLOGY` | `declared` | `consul` = live servicegraph |
| `CAUSA_INVESTIGATOR` | `mock` | Unchanged |
| `PROMETHEUS_URL` | `http://localhost:9090` | Topology queries on host |

## Why Consul looked “half down”

Sidecars used ephemeral node names; each restart left orphan catalog entries
showing as critical (“Agent not live”). `task mesh:up` now wipes the
`consul-data` volume, and sidecars use stable `${SERVICE_ID}-node` names with
`leave_on_terminate`.

## Production hardening (not implemented)

ACLs off in this demo. Future work: mTLS, Consul ACLs, Vault PKI Connect CA.
