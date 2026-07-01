# Giving the Cursor agent its own MCP tools

Causa now uses MCP at **two** layers:

1. **Triage-side** (`causa/sources/mcp.py`) — Causa queries Grafana/GitHub MCP and
   packs the result into the investigation brief. (Documented in `docs/mcp-triage.md`.)
2. **Agent-side** (`.cursor/mcp.json`, this doc) — the **Cursor agent** is handed
   the same read-only MCP servers, so during the investigation it confirms the
   metric signature *itself* — it calls `query_prometheus` and `generate_deeplink`,
   correlates the live telemetry with the code it reads, and cites what it saw.

That second layer is the fullest expression of the challenge: **Cursor SDK +
Cloud Agent + MCP + real telemetry** in one loop. The agent isn't just reading
code and running a test; it's using tools to check the running system.

## How it works

- **`.cursor/mcp.json`** (repo root) declares the read-only Grafana and GitHub MCP
  servers. Any Cursor agent that works on the repo — the IDE, a local SDK run, or
  a cloud run — picks this up automatically.
- **The prompt** (`brief.to_agent_prompt()` in `causa/brief.py`) tells the agent:
  "if Grafana/Prometheus MCP tools are available, use `query_prometheus` /
  `generate_deeplink` to confirm the metric signature and cite it in
  `supporting_telemetry`." If the tools aren't reachable, it falls back to the
  brief's metric signatures — so it degrades cleanly.
- **`sdk-runner/run.mjs`** gained a runtime switch (`CURSOR_RUNTIME`):
  - `cloud` (default) — VM clones the repo; final RCA from `getRun().wait().result`.
  - `local` — runs on this machine against the repo root, so the MCP servers reach
    your **localhost** Grafana/Prometheus.

## The networking reality (important)

MCP servers spawned by the agent run wherever the agent runs:

| Runtime | Can it reach your local Grafana? | Use |
|---|---|---|
| **local** (`CURSOR_RUNTIME=local`) | **Yes** — same machine, `localhost:3000` | The path that works today with zero extra infra |
| **cloud** | **No** — the VM can't see your `localhost` | Needs a *reachable* Grafana |

To use agent-side MCP on a **cloud** run you must either:
- expose the local stack with a tunnel (`ngrok http 3000` / `cloudflared`) and set
  `GRAFANA_URL` to the public URL, **and** install `mcp-grafana` in the VM via a
  custom environment / setup script; or
- point at a hosted Grafana (Grafana Cloud) that the VM can reach.

For the demo, **local runtime is the clean path**: the agent reaches your running
stack directly.

## Prerequisites

- `mcp-grafana` and `github-mcp-server` on the **agent's** PATH
  (`export PATH="$PATH:$HOME/go/bin"` for a local run).
- `GRAFANA_URL`, and `GRAFANA_USERNAME`/`GRAFANA_PASSWORD` (default `admin`/`admin`
  for the local stack) or `GRAFANA_SERVICE_ACCOUNT_TOKEN`.
- `GITHUB_PERSONAL_ACCESS_TOKEN` for the GitHub side.
- `pip install -r requirements-mcp.txt` (Causa's own MCP client, for triage).

## Run it (local — the working path)

```bash
export PATH="$PATH:$HOME/go/bin"
export GRAFANA_URL=http://localhost:3000 GRAFANA_USERNAME=admin GRAFANA_PASSWORD=admin
export GITHUB_PERSONAL_ACCESS_TOKEN=github_pat_...   # optional, for GitHub MCP

CAUSA_TRIAGE=mcp \
CAUSA_INVESTIGATOR=cursor \
CURSOR_RUNTIME=local \
CURSOR_API_KEY=sk-... \
task demo
```

In the console's live feed you'll then see the agent calling `query_prometheus`
and `generate_deeplink` — not just reading files.

## Run it (cloud with a tunnel)

```bash
ngrok http 3000                       # -> https://xxxx.ngrok.app
export GRAFANA_URL=https://xxxx.ngrok.app
# ensure the cloud VM has mcp-grafana (custom environment / setup script)
CAUSA_TRIAGE=mcp CAUSA_INVESTIGATOR=cursor CURSOR_RUNTIME=cloud CURSOR_API_KEY=sk-... task demo
```

## Verification status

- **Mechanism implemented**: `.cursor/mcp.json`, the prompt instruction, and the
  `local`/`cloud` runtime switch.
- **Causa-side MCP triage**: verified live (real `query_prometheus` +
  `generate_deeplink`).
- **Agent-side MCP call**: pending a Cursor API key to verify end-to-end (same as
  the rest of the live agent path). The first live run's event feed will show the
  agent's tool calls; adjust the prompt from there if needed.

## One-line framing for the room

> Causa uses MCP for its own triage, and hands the Cursor agent the *same*
> read-only MCP tools — so the agent confirms the live telemetry inside its own
> investigation. That's the SDK, the Cloud Agent, and MCP working as one loop.
