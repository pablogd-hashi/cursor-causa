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

For a live Cursor Cloud Agent (Pro plan):

```bash
CURSOR_RUNTIME=cloud CURSOR_TARGET_REF=regression/lower-pool-size \
  CURSOR_API_KEY=sk-... task demo:cursor
```

The agent clones the repo via the **Cursor GitHub app** (authorise it on the repo
in the Cursor dashboard) — no GitHub token is needed for the investigation. A
`GITHUB_PERSONAL_ACCESS_TOKEN` is only needed for live GitHub triage (real merged
PRs in the brief); without it, GitHub triage uses the mock source. Point
`CURSOR_TARGET_REF` at a ref where the bug exists. Giving the agent its own MCP
tools: see `docs/agent-mcp.md`.

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
| `.mcp.json` | Read-only Grafana + GitHub MCP definitions (Cursor IDE) |
| `.cursor/mcp.json` | MCP servers offered to the Cursor agent (agent-side tools) |
| `causa/sources/` | Triage adapters: mock + live Grafana/GitHub MCP |
| `requirements-mcp.txt` | Python MCP client deps (for `CAUSA_TRIAGE=mcp`) |
| `.env.example` | Tokens and env vars |
| `topology.yaml` | Service dependency graph (blast radius) |
| `scripts/` | Regression PR, MCP demo, and metric warm-up helpers |
| `architecture.md` | Division of labour, seams, deferred scope |
| `docs/mcp-triage.md` | When Grafana/GitHub MCP run; merge → triage flow |
| `docs/agent-mcp.md` | Giving the agent its own MCP tools; local vs cloud |
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
task mcp:demo           # watch the Grafana/GitHub MCP tool calls happen live
task regression:pr      # open regression PR on GitHub (merge manually for live triage)
```

Live MCP triage (Grafana + GitHub): see `docs/mcp-triage.md`; the agent's own MCP
tools are in `docs/agent-mcp.md`.

```bash
CAUSA_TRIAGE=mcp task demo   # Grafana MCP live; GitHub MCP live with a token
```

URLs: Prometheus http://localhost:9090/alerts · Alertmanager
http://localhost:9093 · Grafana http://localhost:3000/d/payments/payments ·
Jaeger http://localhost:16686 · Console http://localhost:8501

## Conventions

British spelling, no marketing language, clarity over cleverness. Causa is
read-only against every external system and never commits or pushes.
