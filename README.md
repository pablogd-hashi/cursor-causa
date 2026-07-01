# Causa

When an alert fires on the `payments` service, Causa gathers what it can from
metrics and recent deploys, hands a structured brief to a Cursor agent, and gets
back a validated root-cause analysis. The agent is meant to **investigate** the
codebase — read files, run tests, reason about blast radius — not silently open
a fix PR. The RCA is the product; a draft PR is optional and human-approved.

You need [Task](https://taskfile.dev) and Docker. Run `task` for commands.

**New to Cursor?** Read [docs/architecture.md](docs/architecture.md) — it explains
agents, the SDK, cloud vs local runs, and MCP without assuming prior knowledge.

## Quick start

```bash
task setup
task demo
```

Open http://localhost:8501. A real alert fires in about 90 seconds and starts an
investigation. Or click **Simulate payments alert** for an immediate one.
Ctrl-C stops the API and console; `task substrate:down` stops Docker.

Live Cursor agent (Pro plan, `CURSOR_API_KEY`):

```bash
CURSOR_RUNTIME=cloud CURSOR_TARGET_REF=regression/lower-pool-size \
  CURSOR_API_KEY=sk-... task demo:cursor
```

The agent clones via the **Cursor GitHub app** (authorise the repo in the Cursor
dashboard). A GitHub PAT is only needed for live **triage** (real merged PRs in
the brief); without it, GitHub triage uses mock data. Agent-side MCP:
`docs/agent-mcp.md`.

## What's in the repo

| Path | What it is |
|------|------------|
| `causa/` | Contract, triage, orchestration, API |
| `console/app.py` | Streamlit investigation UI |
| `sdk-runner/` | Node launcher for `@cursor/sdk` |
| `demo-app/` | Payments service + oracle test |
| `observability/` | Prometheus, Grafana, Alertmanager, OTel |
| `docs/architecture.md` | How it all fits together (start here) |
| `docs/mcp-triage.md` | Causa's Grafana/GitHub MCP triage |
| `docs/agent-mcp.md` | MCP tools on the agent itself |
| `docs/demo-storyline.md` | Demo script |
| `docs/troubleshooting.md` | When things break |

## Common tasks

```bash
task check              # validate fixture, schema, compose
task substrate:up       # stack + demo-app
task break / task fix   # induce / clear the incident
task mcp:demo           # watch triage MCP calls live
task regression:pr      # open the pool-regression PR on GitHub
```

Live triage after merging that PR: `CAUSA_TRIAGE=mcp task demo`

**URLs:** Prometheus http://localhost:9090/alerts · Grafana
http://localhost:3000/d/payments/payments · Console http://localhost:8501

## Conventions

British spelling. Causa is read-only against external systems and never commits
or pushes.
