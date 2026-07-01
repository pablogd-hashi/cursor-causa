# How Causa works

This document explains the whole system for someone who has never used Cursor
before. If you only want to run the demo, start with the README. Come here when
you want to understand what the pieces are and how they connect.

---

## What problem Causa solves

Something breaks in production. An alert fires. An engineer needs to know: what
changed, what code path is involved, whether to roll back or patch forward, and
who else might be affected.

Causa automates the first pass of that work. It does not auto-fix anything. It
produces a structured **root cause analysis (RCA)** — evidence, test results, a
recommended action — that a human can trust or challenge.

The demo uses a toy `payments` service with a deliberate regression: someone
lowered the database connection pool from 50 to 10. Under load, requests queue,
latency spikes, and Prometheus fires `PaymentsHighLatencyP99`.

---

## Cursor concepts (the bits that confuse people)

### Cursor the product

**Cursor** is a code editor built on VS Code with AI built in. You may already
know it from chat, autocomplete, or the Agent panel in the sidebar. Causa uses
a different slice of Cursor: **programmatic agents** launched over the network,
not the chat you type into while editing.

### Agent vs Cloud Agent vs local agent

These terms get mixed up. In Causa:

| Term | What it actually is |
|------|---------------------|
| **Cursor Agent** | The general idea: an AI that can read files, run commands, use tools, and reason over a codebase. |
| **IDE Agent** | The agent you drive from the Cursor desktop app (Composer / Agent mode). Same family of capability, different entry point. |
| **Cloud Agent** | An agent run that happens on **Cursor's infrastructure**: a VM is provisioned, your repo is cloned there, the agent works in isolation for minutes. You need a Pro plan and an API key. This is what Causa uses by default for investigations. |
| **Local agent** | An agent run on **your machine**, against a directory on disk (`CURSOR_RUNTIME=local`). Same SDK, no remote VM. Useful when the agent needs to reach `localhost` (e.g. your local Grafana). |

Causa does not require you to sit in the Cursor UI during a demo. The console
shows the agent's progress. You *can* open [cursor.com/agents](https://cursor.com/agents)
to watch the same cloud run if you want.

### The Cursor SDK (`@cursor/sdk`)

The **SDK** is a Node library that lets **your code** start and control agents.
Causa does not call Cursor's HTTP API by hand; `sdk-runner/run.mjs` uses:

```javascript
import { Agent } from "@cursor/sdk";

const agent = await Agent.create({ apiKey, model, cloud: { repos: [...] } });
const run = await agent.send(prompt);
for await (const event of run.stream()) { /* live feed */ }
```

So the chain is: **Causa (Python)** → spawns **sdk-runner (Node)** → SDK talks to
**Cursor's cloud** → agent works in a **VM** → events and final JSON stream back.

`CURSOR_API_KEY` authenticates these runs. The repo clone uses the **Cursor
GitHub app** (authorise it on your repo in the Cursor dashboard) — that is
separate from any GitHub token you use for triage.

### MCP (Model Context Protocol)

**MCP** is a standard way for an AI system to call **tools** on other systems
(metrics, GitHub, databases) through small server processes.

Causa uses MCP in **two places**, and they are easy to confuse:

| Layer | Who calls MCP | Config | Purpose |
|-------|---------------|--------|---------|
| **Triage** | Causa itself (`causa/sources/mcp.py`) | env vars + binaries on your machine | Before the agent runs: pull live metrics from Grafana and merged PRs from GitHub into the **investigation brief**. |
| **Agent-side** | The Cursor agent during investigation | `.cursor/mcp.json` in the repo | The agent can re-query Prometheus and GitHub itself while reading code. |

`.mcp.json` at the repo root is for **Cursor IDE and SDK agents**. It does not
configure Causa's triage client. See `docs/mcp-triage.md` and `docs/agent-mcp.md`.

Default demo mode (`CAUSA_TRIAGE=mock`) skips live MCP for triage and uses
canned data so nothing external is required.

---

## The two halves: triage and investigation

Causa splits work on purpose:

1. **Triage (cheap, deterministic)** — scripts and MCP calls. No deep reasoning.
   Output: an **investigation brief** (alert, time window, metric observations,
   candidate PRs, blast-radius hint).

2. **Investigation (expensive, semantic)** — a Cursor agent. Clones the repo,
   reads code, runs tests, judges rollback vs forward-fix. Output: an **RCA**
   JSON document validated against `causa/contract.py`.

That boundary is **brief in, contract out**. The agent does not invent its own
output shape; it must return JSON matching the schema in `schema/rca.schema.json`.
Invalid JSON is rejected and shown as an error — never rendered as a finding.

---

## End-to-end flow

```
  payments app                observability              Causa                    Cursor
  ────────────                ─────────────              ─────                    ──────

  POST /charge  ──metrics──►  Prometheus
                              │
                              ▼
                         alert rule fires
                              │
                              ▼
                         Alertmanager ──webhook──►  causa/api.py
                                                    │
                                                    ├─► triage (mock or MCP)
                                                    │     Grafana: metric signatures
                                                    │     GitHub: merged PRs
                                                    │     topology.yaml: dependents
                                                    │
                                                    ├─► investigation brief
                                                    │
                                                    ├─► investigator
                                                    │     mock: replay fixture
                                                    │     cursor: sdk-runner ──► Cloud Agent
                                                    │                              │
                                                    │                              ├ read pool.py
                                                    │                              ├ run pytest
                                                    │                              └ return RCA JSON
                                                    │
                                                    ├─► validate RCA (Pydantic)
                                                    │
                                                    ▼
                                              console (Streamlit)
                                              three panes: list / feed / RCA
```

### Step by step

1. **Load** — `break.sh` or sustained traffic recreates `demo-app` with a small
   pool and drives concurrent `/charge` requests.

2. **Alert** — Prometheus evaluates `PaymentsHighLatencyP99` (p99 > 1s for 1m).
   Alertmanager POSTs to `http://host.docker.internal:8000/webhook/alert`.

3. **Ack fast** — The API returns immediately and starts `run_investigation()` on
   a background thread. Cloud runs take minutes; the webhook must not block.

4. **Triage** — `assemble_brief()` calls Grafana and GitHub sources (mock or MCP),
   plus `DeclaredTopologySource` reading `topology.yaml`.

5. **Investigate** — `get_investigator()` picks `MockInvestigator` or
   `CursorInvestigator`. The latter pipes the brief (as a prompt + JSON schema)
   to `node sdk-runner/run.mjs`, which streams normalised events on stdout.

6. **Validate** — The final `{"type":"rca","data":{...}}` event is parsed and
   checked against the Pydantic `RCA` model.

7. **Display** — The console polls `GET /investigations/{id}` and renders the
   brief, live event feed, and RCA with deeplinks back to Grafana/GitHub.

You can skip the real alert with **Simulate payments alert** in the console —
same pipeline, instant start.

---

## Repository map

| Path | Role |
|------|------|
| `demo-app/payments/` | The service under investigation. `pool.py` holds the regression knob. |
| `demo-app/tests/test_pool_exhaustion.py` | Oracle test the agent is asked to run. |
| `observability/` | OTel Collector, Prometheus, Alertmanager, Grafana, Loki, Jaeger. |
| `causa/contract.py` | RCA data model — the trust boundary. |
| `causa/brief.py` | Brief model and `assemble_brief()`. |
| `causa/sources/` | Triage: `mock.py` and `mcp.py`. |
| `causa/topology.py` | Blast radius from `topology.yaml`. |
| `causa/investigator.py` | Mock vs Cursor investigator. |
| `causa/orchestrator.py` | Wires triage → investigate → store. |
| `causa/api.py` | FastAPI webhook + REST API. |
| `causa/store.py` | In-memory investigation records (prototype). |
| `sdk-runner/run.mjs` | Node SDK launcher; JSONL events on stdout. |
| `console/app.py` | Streamlit UI. |
| `fixtures/rca_payments.json` | Realistic RCA for mock mode. |
| `.cursor/mcp.json` | MCP tools offered to the agent. |

---

## Mock vs live: what to turn on

| Env var | Default | Live option |
|---------|---------|-------------|
| `CAUSA_TRIAGE` | `mock` | `mcp` — Grafana/GitHub MCP for triage |
| `CAUSA_INVESTIGATOR` | `mock` | `cursor` — real Cursor agent via SDK |
| `CURSOR_RUNTIME` | `cloud` | `local` — agent on your machine (for localhost MCP) |
| `CURSOR_API_KEY` | — | Required for `CAUSA_INVESTIGATOR=cursor` |
| `CURSOR_TARGET_REF` | `main` | e.g. `regression/lower-pool-size` where the bug lives |

Reliable demo with no keys: `task demo` (mock triage + mock investigator).

Full live path: stack up, merge the regression PR (`task regression:pr`), set
`CAUSA_TRIAGE=mcp` and `CAUSA_INVESTIGATOR=cursor`, run `task demo:cursor`.

---

## Design choices worth knowing

**Investigator, not code generator.** The agent is prompted to analyse and
recommend. `autoCreatePR: false` in the SDK config — Causa never opens a PR.

**Mock investigator first.** `MockInvestigator` replays `fixtures/rca_payments.json`
with a synthetic event stream so the console always works, even if the cloud run
fails or you have no API key.

**Degrade, never crash.** If Grafana MCP is down, the brief records
`degraded: ["grafana unavailable: …"]` and the investigation continues with
whatever evidence it has.

**Read-only everywhere.** Grafana MCP runs with `--disable-write`. GitHub MCP
runs `--read-only`. Triage PAT and Cursor GitHub app are separate grants; neither
writes to your repo from Causa.

**Declared topology.** `topology.yaml` lists which services depend on `payments`.
In production you might swap `TopologySource` for a live service-mesh query; the
RCA shape does not change.

**Substrate borrowed.** The OTel/Grafana stack is adapted from an earlier
reference project. Vault, Consul, and SPIFFE from that reference are intentionally
not part of Causa.

---

## What is not built

- `causa/llm.py` — optional narration layer (env vars exist; code does not).
- Persistent store — investigations live in a process-local dict.
- HMAC webhook verification wired in Alertmanager YAML (documented, not connected).
- MCP server binaries inside Docker images — run triage on the host or install
  `mcp-grafana` / `github-mcp-server` locally.

---

## Further reading

- `docs/mcp-triage.md` — when Causa's triage layer calls Grafana/GitHub MCP.
- `docs/agent-mcp.md` — giving the Cursor agent its own MCP tools; cloud vs local.
- `docs/demo-storyline.md` — narrated walkthrough for presenting the demo.
- `docs/troubleshooting.md` — when something does not come up.
