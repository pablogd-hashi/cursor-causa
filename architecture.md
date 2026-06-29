# Causa — architecture

This document describes the shape of the system and, importantly, the **seams**
that keep the prototype honest about what would change in production. It is kept
current as the build progresses; Phase 0 establishes the skeleton.

## Division of labour

Causa is split along a single deliberate line: **cheap deterministic triage** vs
**expensive semantic investigation**.

- **Causa (triage).** Given an alert, narrow the search space using data that is
  cheap to fetch and needs no reasoning: the metric signature and incident window
  from Grafana, and the commits/PRs merged into the window from GitHub. Assemble a
  structured **investigation brief**. This is scripted and reproducible.
- **Cursor Cloud Agent (investigation).** Given the brief and the repository, do
  the part that scripts plus a stateless LLM cannot: clone the repo, use codebase
  indexing and semantic search to trace the implicated execution path, run the
  relevant tests in a real VM on current vs reverted code, and reason about
  rollback vs forward-fix and blast radius. Return a strict RCA.

The brief flows in, the RCA contract flows out. That `brief-in / contract-out`
discipline is what makes the demo repeatable rather than a one-off prompt.

## Components (target state)

```
alert ── Prometheus rule ──> Alertmanager ──(webhook)──> causa-api (FastAPI)
                                                              │
                          triage: MCP client ────────────────┤
                            ├── Grafana MCP  (read-only, --disable-write)
                            └── GitHub MCP   (read-only, --read-only)
                                                              │
                          TopologySource (declared topology.yaml) ── blast radius
                                                              │
                          investigation brief ───────────────┤
                                                              ▼
                          Investigator interface
                            ├── MockInvestigator  (fixtures -> valid RCA)
                            └── CursorInvestigator ── Node @cursor/sdk runner
                                     (streams JSONL events; one Cloud Agent/run)
                                                              │
                          RCA (validated against causa/contract.py) ── stored
                                                              ▼
                          causa-console (Streamlit, three panes) + deeplinks
```

The two MCP servers and the Node SDK runner are **subprocesses** of `causa-api`,
not long-running services: the MCP servers speak stdio to Causa's MCP client, and
the runner streams newline-delimited JSON events on stdout for the live feed.

## Seams (where production differs from the prototype)

These are the interfaces that let the prototype use a simple implementation now
and a production one later without touching the engine.

1. **`TopologySource`** (Phase 2). One method, `dependents(service) -> list[str]`.
   - *Prototype:* reads `topology.yaml`, a declared dependency graph.
   - *Production:* a Consul MCP implementation derives the live graph from the
     service mesh. **Declared graph for the prototype, Consul MCP in production.**
   - The blast-radius reasoning in the RCA does not change; only the data source.

2. **`Investigator`** (Phase 3). `investigate(brief) -> RCA`, plus an event
   stream.
   - `MockInvestigator` returns a canned-but-realistic RCA from `fixtures/`, so
     the whole pipeline and console run with no live Cursor calls. Built first;
     the demo's reliability depends on it.
   - `CursorInvestigator` shells out to the Node `@cursor/sdk` runner and streams
     the Cloud Agent's typed events back.

3. **`llm.py`** (narration only). A hosted API by default, with a documented
   Ollama swap for the air-gapped story. The LLM never decides the RCA — the
   contract, the evidence and the test results do.

## Reused from `smolagents-observability`

The OTel/Grafana substrate is lifted (config only) from the reference repository
`smolagents-observability/` (the brief's `../reference`; github
`pablogd-hashi/smolagents-otel-spiffe`): the OTel Collector pipeline, the Grafana
datasource/dashboard provisioning (including the Loki→Jaeger trace-link derived
field), the Loki and Prometheus configs, and the telemetry-init pattern from
`agents/shared/telemetry.py`. The reference's Vault/Consul/SPIFFE substrate and
its planner/executor multi-agent code are deliberately **left behind** — Causa is
a different system.

## Guardrails and failure modes

- **Least privilege, read-only everywhere.** Grafana MCP runs `--disable-write`
  with a Viewer service-account token; GitHub MCP runs `--read-only` with a
  fine-grained, single-repo PAT; the Cloud Agent's clone uses the Cursor GitHub
  app scoped to the one repo; the alert webhook is HMAC-verified. The demo can
  state exactly what Causa is permitted to touch — nothing it can write to.
- **Two distinct GitHub grants** by design: the triage PAT (Causa's MCP client)
  and the Cursor GitHub app (the agent's VM clone). Neither can write.
- **Degrade, never crash.** If a triage MCP source is unavailable, the brief
  records the gap ("grafana evidence unavailable") and the investigation still
  launches with a partial brief; the console shows a banner rather than failing.
- **Cloud-run failure or timeout** is caught: the investigation is marked FAILED
  with the error, the console keeps the partial event stream and offers a retry,
  and `MockInvestigator` remains available so a demo never hard-depends on a live
  run.
- **The contract is the trust boundary.** The agent's JSON is validated against
  `causa/contract.py`; invalid output is rejected with the validation errors
  surfaced, never rendered as if it were a real finding.
- **Causa never commits or pushes.** The Cloud Agent runs with
  `autoCreatePR: false`; a draft PR is only produced as an explicit,
  engineer-approved action from the console.

## Deferred scope (noted, not built)

Each of these has a published implementation in `smolagents-observability` that
Causa would draw on; the seams above are already in place so adding them does not
disturb the engine.

- **Consul MCP as the live `TopologySource`** — replaces the declared
  `topology.yaml`.
- **Vault / SPIFFE workload identity for Causa's own credentials** — Causa would
  obtain its MCP/Cursor tokens via Vault rather than from `.env`, with a SPIFFE
  identity per workload (cf. the reference's Vault PKI + Consul Connect substrate).
- **Causa's own OTel tracing of each investigation run** — Causa would emit its
  own traces/metrics for triage and investigation latency (the reference already
  instruments agent runs this way), making Causa observable by the same stack it
  reads from.
