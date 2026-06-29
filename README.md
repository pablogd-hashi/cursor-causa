# Causa

Causa is a Cursor-driven Root Cause Analysis console. When an alert fires for the
`payments` service, Causa does cheap, deterministic **triage** (pulling the metric
signature from Grafana and the candidate commits/PRs from GitHub, both over MCP),
assembles a structured **investigation brief**, and hands it to a **Cursor Cloud
Agent**. The Cloud Agent clones the repository, traces the implicated execution
path in the real code, runs the relevant tests in its VM, reasons about whether a
rollback or a forward-fix is safer (using a service dependency graph for blast
radius), and returns a strict, validated **RCA** that the console renders.

The point of the demo is that the Cursor Cloud Agent is a **codebase
investigator**, not a code generator. The product is the RCA; a draft PR is an
optional, engineer-approved downstream step.

## Status

Phases 0–5 complete. 0: scope + RCA contract. 1: demo substrate + a real alert
(p99 ~2.45s at pool 10, `PaymentsHighLatencyP99` to Alertmanager). 2: triage
(Grafana/GitHub adapters, `TopologySource`, brief assembler). 3: investigator
interface — `MockInvestigator` + `CursorInvestigator` (the latter verified against
a real cloud run that returned a contract-valid RCA). 4: FastAPI webhook + results
API + orchestration. 5: the Streamlit three-pane console. Phase 6 (demo.sh +
troubleshooting) remains. See [the plan](#phases) below and `architecture.md`.

## What is here after Phase 0

| Path | What it is |
|---|---|
| `causa/contract.py` | The RCA contract (Pydantic v2). The trust boundary. |
| `schema/rca.schema.json` | JSON Schema generated from the contract; handed to the agent. |
| `fixtures/rca_payments.json` | A valid, realistic RCA (feeds the MockInvestigator). |
| `docker-compose.yml` | The local stack topology (configs/apps arrive in Phase 1+). |
| `.mcp.json` | Read-only Grafana + GitHub MCP server definitions. |
| `.env.example` | Every token/env var, how to get it, least-privilege scope. |
| `topology.yaml` | Declared service dependency graph (blast radius). |
| `architecture.md` | Division of labour, seams, deferred scope. |
| `docs/decisions-and-fde-mapping.md` | Every decision, its tradeoff, and how it maps to the FDE challenge. |
| `demo-app/` | The instrumented `payments` service: `pool.py` (the regression), `api.py`, `telemetry.py`, and `tests/test_pool_exhaustion.py` (the oracle test). |
| `observability/` | Lifted OTel Collector, Prometheus + alert rule, Alertmanager, Loki, and Grafana provisioning + the Payments dashboard. |
| `break.sh` / `fix.sh` | Induce the pool-exhaustion incident / restore a healthy pool. |

## Quick check (Phase 0)

```bash
python3 -m venv .venv && ./.venv/bin/pip install "pydantic>=2,<3" pyyaml

# the fixture validates against the contract
./.venv/bin/python -c "from causa.contract import RCA; \
  RCA.model_validate_json(open('fixtures/rca_payments.json').read()); print('ok')"

# regenerate the JSON Schema from the model
./.venv/bin/python -m causa.contract > schema/rca.schema.json

# the compose topology lints
docker compose config --quiet && echo ok
```

## Run the substrate (Phase 1)

```bash
# bring up the observability stack + payments app
docker compose up -d --build otel-collector prometheus alertmanager loki jaeger grafana demo-app

# run the oracle test (passes healthy; fails at pool 10)
cd demo-app && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m pytest -q                 # PASS  (pool 50)
POOL_MAX_SIZE=10 ./.venv/bin/python -m pytest -q  # FAIL (pool 10)
cd ..

# induce the incident and watch the alert fire, then restore
./break.sh        # shrinks the pool to 10 and drives load
./fix.sh          # restores pool 50
```

URLs: Prometheus alerts http://localhost:9090/alerts · Alertmanager
http://localhost:9093 · Grafana http://localhost:3000/d/payments/payments ·
Jaeger http://localhost:16686 . Stop everything with `docker compose down`.

## Run the pipeline (Phases 2–3)

End to end, on mocks (no Grafana/GitHub/Cursor needed) — prints the triage brief,
the live investigation feed, and the validated RCA:

```bash
./.venv/bin/python -m causa.demo
```

Switch backends with env vars:
`CAUSA_TRIAGE=mcp` (read-only Grafana/GitHub MCP servers) and
`CAUSA_INVESTIGATOR=cursor` (a real Cursor cloud agent; needs `CURSOR_API_KEY`).

## Run the console (Phases 4–5)

```bash
./run-local.sh          # starts the FastAPI API (:8000) and the console (:8501)
```
Open http://localhost:8501 and click **Simulate payments alert**. Left pane =
alerts, centre = the live investigation feed, right = the RCA with deep-links and
the optional "Open Draft PR" button. Add `CAUSA_INVESTIGATOR=cursor` +
`CURSOR_API_KEY=...` before `./run-local.sh` to drive a real cloud agent.

## Phases

0. **Scope + contract** — done.
1. **Demo substrate** — done. Instrumented `payments` app with a pool-exhaustion
   path, the OTel pipeline, a Prometheus alert rule. A real alert fires first.
2. **Triage** — done. Grafana + GitHub source adapters (mock + MCP), the brief
   assembler, the `TopologySource` interface + declared-graph implementation.
3. **Investigator** — done. The interface, `MockInvestigator`, and the Node
   `@cursor/sdk` runner + `CursorInvestigator` with streaming.
4. **Orchestration** — done. FastAPI webhook + results API + background runner.
5. **Console** — done. The Streamlit three-pane investigation console.
6. End-to-end demo (`demo.sh`), docs, troubleshooting.

## Conventions

British spelling, no marketing language, clarity over cleverness. Causa is
read-only against every external system and never commits or pushes.
