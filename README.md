# Causa

Causa is a root cause analysis console. When an alert fires for the `payments`
service, Causa does cheap, deterministic triage and then hands a structured brief
to a **Cursor Cloud Agent**, which clones the repository, traces the implicated
code, runs the relevant tests, and returns a validated root cause analysis that
the console renders.

The idea is to use the Cursor Cloud Agent as a codebase **investigator**, not a
code generator: the product is the analysis. Any pull request is an optional,
engineer-approved follow-up.

Causa is read-only against every external system and never commits or pushes.

## How it works

1. A Prometheus rule (`PaymentsHighLatencyP99`) fires and Alertmanager calls
   Causa's webhook.
2. **Triage** (deterministic): pull the metric signature from Grafana, the
   candidate commits/PRs from GitHub, and the service dependency graph.
3. Causa assembles an **investigation brief**.
4. **Investigation**: a Cursor Cloud Agent gets the brief and the repo,
   investigates the real code, runs the test on the current and reverted code,
   and returns an RCA that matches a strict schema.
5. The **console** shows the alert, the live investigation feed, and the RCA with
   deep-links into Grafana, Jaeger and GitHub.

```
alert ─▶ triage (Grafana + GitHub + topology) ─▶ brief ─▶ Cursor agent ─▶ RCA ─▶ console
```

## Run it

```bash
./demo.sh
```

This brings up the stack, fires a real incident in the background (the alert
fires in about 90 seconds and auto-starts an investigation), and launches the API
and console. Open <http://localhost:8501> and click **Simulate payments alert**
for an instant one, or wait for the real alert. Ctrl-C stops it; `docker compose
down` stops the stack.

By default the investigation is **mocked** (a fixture RCA), so the demo runs with
no external dependencies. For a real Cursor Cloud Agent:

```bash
CAUSA_INVESTIGATOR=cursor CURSOR_API_KEY=... ./demo.sh
```

### Inside Cursor

Cursor is a VS Code fork, so you can run it all in the IDE: Command Palette →
*Tasks: Run Task* → `Causa: demo (end-to-end)`, then *Simple Browser: Show* →
<http://localhost:8501>. A live cloud run also shows at <https://cursor.com/agents>
(under the account that owns the API key).

## The console

- **Left** — alerts; click one, or simulate.
- **Centre** — the incident timeline and the live investigation feed.
- **Right** — the RCA: confidence, recommended action, blast radius, code path,
  test results (current vs revert), and evidence/telemetry as deep-links.

## Where things are

| Path | What it is |
|---|---|
| `causa/contract.py` | The RCA schema the investigator must return; Causa validates against it. |
| `demo-app/` | The instrumented `payments` service with the pool-exhaustion bug and its test. |
| `causa/sources/` | Triage adapters for Grafana and GitHub (mock, or read-only MCP). |
| `causa/topology.py` | The service dependency graph behind blast-radius reasoning. |
| `causa/investigator.py` | The investigator interface: mock, or a real Cursor agent. |
| `sdk-runner/` | The Node launcher that drives the Cursor Agent SDK. |
| `causa/api.py`, `console/app.py` | The FastAPI backend and the Streamlit console. |
| `observability/` | OTel Collector, Prometheus + the alert rule, Alertmanager, Loki, Grafana. |
| `architecture.md` | Design, the seams, and what is deferred to production. |
| `docs/troubleshooting.md` | Common snags. |

## Configuration

| Variable | Purpose |
|---|---|
| `CAUSA_INVESTIGATOR` | `mock` (default) or `cursor` (live cloud agent). |
| `CAUSA_TRIAGE` | `mock` (default) or `mcp` (read-only Grafana/GitHub MCP servers). |
| `CURSOR_API_KEY` | Required for a live cloud run (Cursor Pro). |

See `.env.example` for the full list and how to obtain each value.
