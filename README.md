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

Requires [Task](https://taskfile.dev) and Docker. Run `task` to list commands.

## Quick start

```bash
task setup
task demo
```

Open http://localhost:8501 (Cursor Simple Browser). A real alert fires in ~90s
and auto-starts an investigation. Click **Simulate payments alert** for an instant
one. Ctrl-C stops the API and console; `task substrate:down` stops Docker.

For a live Cursor Cloud Agent:

```bash
CAUSA_INVESTIGATOR=cursor CURSOR_API_KEY=sk-... task demo:cursor
```

## Layout

| Path | What it is |
|---|---|
| `causa/contract.py` | The RCA contract (Pydantic v2). The trust boundary. |
| `schema/rca.schema.json` | JSON Schema generated from the contract; handed to the agent. |
| `fixtures/rca_payments.json` | A valid, realistic RCA (feeds the MockInvestigator). |
| `causa/api.py` | FastAPI orchestration API |
| `console/app.py` | Streamlit investigation console |
| `sdk-runner/` | Node `@cursor/sdk` runner for live investigations |
| `demo-app/` | Instrumented `payments` service and oracle test |
| `observability/` | OTel, Prometheus, Alertmanager, Loki, Grafana |
| `docker-compose.yml` | Local stack topology |
| `.mcp.json` | Read-only Grafana + GitHub MCP server definitions |
| `.env.example` | Tokens and env vars |
| `topology.yaml` | Service dependency graph (blast radius) |
| `architecture.md` | Division of labour, seams, deferred scope |
| `docs/mcp-triage.md` | When Grafana/GitHub MCP run; merge → triage flow |
| `docs/demo-storyline.md` | Narrated demo script |
| `docs/troubleshooting.md` | Failure modes and fixes |

## Common tasks

```bash
task check              # validate fixture, regen schema, lint compose
task substrate:up       # observability stack + demo-app only
task test:oracle        # oracle test — pass at pool 50
task break              # induce the incident
task fix                # restore healthy pool
task run:local          # API + console without full demo
task regression:pr      # open regression PR on GitHub (merge manually for live triage)
```

Live MCP triage (Grafana + GitHub): see `docs/mcp-triage.md`.

```bash
CAUSA_TRIAGE=mcp task demo   # after merging the regression PR
```

URLs: 
· Prometheus http://localhost:9090/alerts 
· Alertmanager http://localhost:9093 
· Grafana http://localhost:3000/d/payments/payments 
· Jaeger http://localhost:16686 
· Console http://localhost:8501

