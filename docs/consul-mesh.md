# Consul Connect mesh demo

Causa can run the payments incident demo on a **real Consul Connect mesh** with
trace-derived blast radius, while keeping the offline path (`CAUSA_TOPOLOGY=declared`,
`CAUSA_INVESTIGATOR=mock`) unchanged.

## Topology

```
web → api → payments (demo-app) → currency → rates (external via terminating gateway)
              └→ cache
```

- **payments** is this repo's `demo-app` (connection pool regression), registered
  in Consul with a Connect sidecar.
- **web / api / cache / currency** are `fake-service` containers with Envoy sidecars.
- **rates** sits outside the mesh; **currency** reaches it through the terminating
  gateway.
- Traces flow to the unified OTel Collector (OTLP from payments, Zipkin from
  fake-services and Envoy). The **servicegraph** connector emits
  `traces_service_graph_request_total{client,server}` for Prometheus.

ACLs are **off** in this demo. Production hardening (not implemented here):

- Enable Consul ACLs and least-privilege tokens per service
- mTLS via Connect with a proper CA (Vault PKI or Consul's built-in CA with
  auto-encrypt)
- Narrow service intentions instead of the permissive `*` allow rule

## Quick start

```bash
# 1. Observability + mesh (one stack, one of each backend)
task mesh:up

# 2. Wait ~30s for loadgen + service graph metrics, then verify Consul UI
open http://localhost:8500          # web, api, payments, … with sidecars healthy

# 3. Live blast radius from the mesh graph
CAUSA_TOPOLOGY=consul .venv/bin/python -c "
from causa.topology import get_topology
t = get_topology()
print(t.graph_source, t.dependents('payments'))
"

# 4. Fire the incident through mesh traffic
./break.sh    # detects :21000 and drives load via Envoy → web → api → payments

# 5. Run Causa with live topology
CAUSA_TOPOLOGY=consul task run:local
```

## Endpoints

| URL | Purpose |
|-----|---------|
| http://localhost:8500 | Consul UI (mesh health, sidecars) |
| http://localhost:21000/ | Mesh ingress (Envoy → web) |
| http://localhost:3000/d/service-to-service | Service dependency graph |
| http://localhost:3000/d/payments/payments | Payments latency dashboard |
| http://localhost:9090 | Prometheus (`traces_service_graph_request_total`) |
| http://localhost:16686 | Jaeger |

## Environment flags

| Variable | Default | Meaning |
|----------|---------|---------|
| `CAUSA_TOPOLOGY` | `declared` | `consul` queries Prometheus servicegraph metrics |
| `CAUSA_INVESTIGATOR` | `mock` | Unchanged; mesh does not require live Cursor |
| `PROMETHEUS_URL` | `http://localhost:9090` | Override for topology queries on the host |
| `POOL_MAX_SIZE` | `50` | Break with `./break.sh` (recreates demo-app at `10`) |

## Offline demo (unchanged)

```bash
task demo
# or
task substrate:up && task run:local
```

No Consul services are started (`docker compose` profile `mesh` is not active).
`CAUSA_TOPOLOGY=declared` reads `topology.yaml` for blast radius.

## Layout

```
mesh/
  consul/           # Server HCL, proxy-defaults, intentions, service-defaults
  envoy/            # Access log, API gateway, terminating gateway JSON
  scripts/          # consul-init.sh — applies config entries on boot
```

Mesh services use the Compose profile `mesh` so `task substrate:up` stays
lightweight. `task mesh:up` starts substrate **and** mesh.

## Verification checklist

1. Consul UI shows **web, api, payments, currency, cache, rates** passing checks;
   Connect sidecars appear for mesh services.
2. Grafana **service-to-service** dashboard shows **web → api → payments**.
3. `traces_service_graph_request_total{server="payments"}` is non-empty in Prometheus.
4. `CAUSA_TOPOLOGY=consul` → `dependents('payments')` returns live clients (e.g.
   `api`, `web`).
5. `./break.sh` fires `PaymentsHighLatencyP99`; brief `blast_radius_hint` matches
   the live set with `graph_source` **consul-mesh (servicegraph)**.
6. `CAUSA_TOPOLOGY=declared task demo` still runs fully offline.
