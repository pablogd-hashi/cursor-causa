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

Phase 0 (scope, substrate proposal, and the RCA contract) is complete. The build
is phased; see [the plan](#phases) below and `architecture.md`.

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

## Phases

0. **Scope + contract** (this commit).
1. Demo substrate: instrumented `payments` app with a pool-exhaustion path, the
   OTel pipeline, a Prometheus alert rule. A real alert fires first.
2. Triage: Grafana + GitHub MCP-client adapters, the brief assembler, the
   `TopologySource` interface + declared-graph implementation.
3. Investigator: the interface, `MockInvestigator` first, then the Node
   `@cursor/sdk` runner + `CursorInvestigator` with streaming.
4. Orchestration: FastAPI webhook + results API.
5. Console: the Streamlit three-pane investigation console.
6. End-to-end demo, docs, troubleshooting.

## Conventions

British spelling, no marketing language, clarity over cleverness. Causa is
read-only against every external system and never commits or pushes.
