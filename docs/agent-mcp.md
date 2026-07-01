# Agent-side MCP

Causa uses MCP in two places. This doc is about the **second** one: tools the
**Cursor agent** can call while it investigates. Triage-side MCP (Causa calling
Grafana/GitHub before the agent runs) is in `docs/mcp-triage.md`.

## What this adds

During an investigation the agent can call the same read-only Grafana and GitHub
MCP servers you use for triage — e.g. `query_prometheus` to confirm p99 latency
matches what it sees in `pool.py`. That correlation is cited in the RCA.

- **`.cursor/mcp.json`** — declares Grafana and GitHub MCP servers for any
  Cursor agent working in this repo (IDE, local SDK run, or cloud run).
- **`brief.to_agent_prompt()`** — tells the agent to use those tools if
  available, and to fall back to the brief's `metric_signatures` if not.
- **`CURSOR_RUNTIME`** in `sdk-runner/run.mjs`:
  - `cloud` (default) — VM clones the repo; final RCA from `getRun().wait().result`.
  - `local` — agent runs on your machine against the repo root so MCP can reach
    `localhost:3000`.

## Networking

MCP servers run **where the agent runs**:

| Runtime | Reach `localhost:3000`? | Typical use |
|---------|-------------------------|-------------|
| `local` | Yes | Demo with local Grafana — works out of the box |
| `cloud` | No | VM cannot see your laptop; needs a public Grafana URL or tunnel |

For cloud + local Grafana you'd tunnel (`ngrok http 3000`) and point
`GRAFANA_URL` at the public URL, plus ensure `mcp-grafana` exists in the VM.

## Prerequisites

- `mcp-grafana` and `github-mcp-server` on the agent's PATH (`~/go/bin` is common).
- Grafana credentials (`GRAFANA_SERVICE_ACCOUNT_TOKEN` or admin/admin locally).
- `GITHUB_PERSONAL_ACCESS_TOKEN` for GitHub MCP.
- `pip install -r requirements-mcp.txt` for Causa's own triage client (separate).

## Example: local runtime

```bash
export PATH="$PATH:$HOME/go/bin"
export GRAFANA_URL=http://localhost:3000 GRAFANA_USERNAME=admin GRAFANA_PASSWORD=admin

CAUSA_TRIAGE=mcp \
CAUSA_INVESTIGATOR=cursor \
CURSOR_RUNTIME=local \
CURSOR_API_KEY=sk-... \
task demo
```

Watch the console feed for `query_prometheus` and `generate_deeplink`, not just
`read_file`.

## Status

Triage MCP is verified live. Agent-side MCP depends on a successful live agent
run; the event feed shows whether the agent actually called the tools.
