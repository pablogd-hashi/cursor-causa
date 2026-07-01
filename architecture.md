# Architecture

The detailed architecture guide — including Cursor concepts (agents, cloud vs
local, SDK, MCP) and a full walkthrough of the pipeline — lives in
**[docs/architecture.md](docs/architecture.md)**.

This file is a short index for production seams and guardrails.

## Seams

Interfaces you could swap without rewriting the engine:

- **`TopologySource`** — `topology.yaml` today; Consul MCP or service mesh later.
- **`Investigator`** — `MockInvestigator` vs `CursorInvestigator` (`sdk-runner`).
- **`GrafanaSource` / `GitHubSource`** — mock vs MCP in `causa/sources/`.

## Guardrails

- RCA output validated against `causa/contract.py`; invalid JSON is rejected.
- Triage and agent MCP are read-only; `autoCreatePR: false` on cloud runs.
- Causa never commits or pushes.
- Partial triage failures are recorded on the brief; investigations still run.

## Deferred

Consul-backed topology, Vault-held credentials, Causa's own OTel traces for each
investigation run.
