# Causa — decisions, tradeoffs, and how they map to the FDE challenge

This document exists for one purpose: so that in a panel interview I can explain
**every** non-trivial decision in Causa — what the options were, what the tradeoff
was, why I chose what I chose, and how it serves the original challenge. It grows
one section per phase. This is the Phase 0 set.

## The challenge, restated

> Demonstrate why the **Cursor Cloud Agent** and the **Cursor SDK** are valuable
> in an enterprise SDLC workflow.

The trap is to answer this by generating a pull request — "look, Cursor wrote the
fix". That is the commodity story and it undersells the product. The interesting,
defensible story is that Cursor **understands a codebase well enough to inform a
decision**: it clones the repo, traces real execution paths, runs real tests, and
reasons about consequences. Causa is built to make an interviewer conclude
*"Cursor understood the codebase and helped the engineer make the correct
decision"*, not *"Cursor wrote another PR"*.

Every decision below is in service of that sentence.

---

## 1. Cursor as a codebase *investigator*, not a code generator

- **Options.** (a) Cursor generates a fix PR from the alert. (b) Cursor
  investigates the incident and returns an analysis; a PR is optional and
  downstream.
- **Tradeoff.** (a) is the obvious, flashy demo but it is exactly what every code
  assistant claims, and it hides the unique capability. (b) is less flashy but
  showcases the moat: codebase indexing, semantic search, and real test execution
  in a VM.
- **Decision.** (b). The RCA is the product; the PR is an optional consequence.
- **FDE mapping.** Enterprises do not let an agent open PRs into `payments` on the
  strength of an alert. They *do* have a senior engineer paged at 02:14 who needs
  to decide rollback vs fix in minutes. Causa puts Cursor where the actual value
  and the actual trust boundary are: informing that decision.

## 2. Brief-in / contract-out (the strict RCA schema)

- **Options.** (a) A free-form "investigate this incident" prompt. (b) A
  structured brief in, and a strict JSON contract (`causa/contract.py`) out, with
  validation.
- **Tradeoff.** (a) is quick to build but the output is unrepeatable and
  un-renderable — different every run, impossible to put in a UI or trust. (b)
  costs an upfront schema and a validation step, but makes the system demoable,
  repeatable, and safe to render.
- **Decision.** (b). The contract is the trust boundary: invalid agent output is
  rejected and surfaced, never displayed as a finding. The JSON Schema generated
  from the model is handed to the agent so it targets the exact shape.
- **FDE mapping.** "Make the agent useful in *our* workflow" is the core FDE job.
  Real integrations need typed, validated I/O, not prose. This is the difference
  between a toy and something an enterprise would wire into an incident process.

## 3. Triage (Causa) vs investigation (Cursor) — the division of labour

- **Options.** (a) Have the Cloud Agent do everything, including pulling metrics
  and finding candidate commits. (b) Causa does cheap deterministic triage; the
  agent does the expensive semantic work.
- **Tradeoff.** (a) is simpler to wire but wastes the agent's (billed, slower) VM
  time on work a script does better and more cheaply, and it makes the demo
  non-deterministic from the first step. (b) needs two code paths but keeps each
  tool on the work it is best at.
- **Decision.** (b). Grafana/GitHub lookups are scripted; code-tracing and test
  execution go to the agent.
- **FDE mapping.** This is the honest enterprise pattern: use deterministic
  automation for the cheap 80%, reserve the expensive agent for the part only it
  can do. It also gives a crisp answer to "why not just an LLM with some scripts?"
  — because the agent's value is precisely the part the scripts cannot do.

## 4. Lift the observability substrate from the reference, don't rebuild

- **Options.** (a) Build the OTel/Grafana stack fresh. (b) Lift the proven config
  from `smolagents-observability` (the brief's `../reference`).
- **Tradeoff.** (a) is cleaner but spends the whole budget on plumbing. (b) is
  faster and lower-risk, at the cost of carrying a little shape I did not design
  from scratch.
- **Decision.** (b), config only — OTel Collector pipeline, Grafana provisioning
  (including the Loki→Jaeger trace-link derived field), Loki/Prometheus configs,
  and the telemetry-init pattern. I deliberately leave behind the reference's
  Vault/Consul/SPIFFE substrate and its multi-agent code.
- **FDE mapping.** FDEs land in a customer's existing stack and integrate, they do
  not greenfield everything. Reusing a real pipeline and being explicit about what
  I left behind *is* the FDE skill.

## 5. Triage over MCP, not direct REST APIs

- **Options.** (a) Causa calls Grafana's HTTP API and GitHub's REST API directly.
  (b) Causa is an MCP client driving the read-only Grafana and GitHub MCP servers.
- **Tradeoff.** (a) is simpler and has fewer moving parts. (b) adds two
  subprocesses, but it is faithful to the MCP-driven story, gives uniform
  read-only enforcement at the server (`--disable-write`, `--read-only`), and
  yields the Grafana `generate_deeplink` tool for free — which is exactly how the
  console builds its Grafana/Jaeger deep-links.
- **Decision.** (b). Causa hosts the MCP servers as stdio subprocesses.
- **FDE mapping.** MCP is the integration substrate Cursor (and the wider
  ecosystem) is standardising on. Showing Causa *and* the Cloud Agent consuming
  the same `.mcp.json` demonstrates that the customer's MCP investment is reusable
  across both the deterministic and the agentic halves of the workflow.

## 6. Alertmanager, not Grafana-managed alerting

- **Options.** (a) Grafana alerting fires the webhook. (b) A Prometheus alerting
  rule routes through Alertmanager to Causa's webhook.
- **Tradeoff.** (a) is one fewer container. (b) matches how the metric-based alert
  actually originates (a PromQL rule) and is the more common enterprise topology.
- **Decision.** (b). One Alertmanager with a single webhook receiver. The brief's
  requirement is "a real alert fires before anything reacts", and this makes that
  literally true end-to-end.
- **FDE mapping.** Grounding the demo in a realistic alerting path (rule →
  Alertmanager → webhook) is more credible to an infra audience than a bespoke
  trigger.

## 7. Monorepo investigation target, not a split repo

- **Options.** (a) The `payments` demo-app in its own repo. (b) One repo
  (`pablogd-hashi/cursor-causa`) holding Causa and `demo-app/`; the agent clones
  it and scopes investigation to `demo-app/`.
- **Tradeoff.** (a) is a cleaner separation of orchestrator and target. (b) is one
  repo to manage and demo, and the Cloud Agent's "one repo per run" constraint is
  satisfied by pointing it at a subdirectory.
- **Decision.** (b) for the prototype, behind a single `CURSOR_TARGET_REPO`
  config so splitting later is one value change.
- **FDE mapping.** Mirrors the reality that enterprise services live in large
  repos/monorepos; "investigate this path within a big repo" is the realistic ask,
  and it exercises Cursor's indexing on more than a toy tree.

## 8. Blast radius from a declared graph now, Consul later (but in the MVP)

- **Options.** (a) Defer blast-radius reasoning. (b) Require a live Consul mesh
  now. (c) A declared `topology.yaml` behind a `TopologySource` seam, with Consul
  MCP as a drop-in later.
- **Tradeoff.** (a) drops the single most valuable piece of reasoning in the demo.
  (b) is heavy infra for a prototype and couples the engine to Consul. (c) keeps
  the reasoning in the MVP while staying one interface away from production.
- **Decision.** (c). `TopologySource.dependents()` feeds the RCA's `blast_radius`;
  the architecture states plainly "declared graph for the prototype, Consul MCP in
  production".
- **FDE mapping.** "Rolling back `payments` also breaks Checkout, Refunds, Invoice
  and Ledger — recommend a staged rollout" is the reasoning a staff engineer pays
  for. Keeping it in the MVP, while showing I know exactly where the production
  data comes from, is the whole pitch in one sentence.

## 9. Mock investigator first, real Cursor second

- **Options.** (a) Build only the live `CursorInvestigator`. (b) Build a
  `MockInvestigator` (fixtures → valid RCA) first, behind the same interface.
- **Tradeoff.** (a) is less code. (b) costs an extra implementation but means the
  entire pipeline and console are demoable with zero live cloud calls, and a live
  run failing never takes the demo down.
- **Decision.** (b), first. The fixture (`fixtures/rca_payments.json`) already
  validates against the contract.
- **FDE mapping.** Demo reliability is a deployment concern, and handling it
  gracefully (with a deterministic fallback) is exactly the production-mindedness
  an FDE is hired for. It also de-risks the interview itself.

## 10. Least-privilege, read-only token model

- **Options.** (a) A broad PAT and admin Grafana key for convenience. (b)
  Fine-grained, single-repo, read-only GitHub PAT; Grafana Viewer token; both MCP
  servers forced read-only; two distinct GitHub grants (triage PAT vs Cursor
  GitHub app); HMAC-verified webhook.
- **Tradeoff.** (a) is faster to set up. (b) is a little more ceremony but means I
  can state on a slide exactly what Causa can touch — and that it can write to
  nothing.
- **Decision.** (b). Documented per-variable in `.env.example`.
- **FDE mapping.** Enterprise adoption lives or dies on the security review.
  Leading with least privilege answers the first question a platform team asks
  about letting an agent near `payments`.

## 11. Never auto-commit, never auto-push (and no auto-PR)

- **Options.** (a) Let the Cloud Agent open a PR automatically (`autoCreatePR:
  true`). (b) Keep all version-control writes in human hands; PR creation is an
  explicit, engineer-approved action.
- **Tradeoff.** (a) is a slicker single-click demo. (b) keeps the human in the
  loop and matches both the user's hard rule and the "RCA is the product" framing.
- **Decision.** (b). `autoCreatePR: false`; the console's "Open Draft PR" button
  hands control to the engineer. Causa itself issues no git writes.
- **FDE mapping.** Reinforces the core thesis (decision support, not autonomous
  change) and is the posture an enterprise will actually accept for a payments
  service.

## 12. A Node SDK runner, not direct REST calls to Cursor

- **Options.** (a) Causa (Python) calls the Cursor Cloud Agents REST API directly.
  (b) A small Node `sdk-runner/` using the official `@cursor/sdk`, which Causa
  shells out to.
- **Tradeoff.** (a) avoids a second language. (b) uses the official, supported SDK
  surface (the SDK is TypeScript-only), which is cleaner and tracks the product as
  it evolves in beta — at the cost of bundling Node.
- **Decision.** (b). The runner streams the agent's typed events as newline-
  delimited JSON on stdout, which Causa forwards to the console's live feed.
- **FDE mapping.** Using the product's own SDK the way a customer would — and
  bridging it cleanly into a Python shop — is a direct demonstration of the SDK's
  integration story, which is half the challenge.

## 13. Stream the investigation, don't just show the result

- **Options.** (a) Run the agent, show the final RCA. (b) Stream the agent's steps
  ("cloning repo… reading payments/pool.py… running test_pool_exhaustion… failed
  on current, passed on revert") into a live feed, with the RCA at the end.
- **Tradeoff.** (a) is simpler. (b) is more work (event plumbing) but is what
  actually makes "Cursor understood the codebase" *visible* rather than asserted.
- **Decision.** (b), with a post-run replay as the fallback if live streaming is
  fiddly for the MVP.
- **FDE mapping.** The live feed is the demo's emotional core: the interviewer
  watches Cursor reason through real code and tests. That is the moment the thesis
  lands.

## 14. The LLM narrates; it never decides

- **Options.** (a) Let a general LLM summarise and effectively make the call. (b)
  Confine any LLM to light narration behind `llm.py`; the decision rests on the
  contract, the evidence, and the test results.
- **Tradeoff.** (a) is less structure. (b) keeps the system's conclusions
  grounded in verifiable artifacts rather than model prose.
- **Decision.** (b), with a documented hosted-API-default / Ollama-swap so the
  air-gapped story is credible.
- **FDE mapping.** It keeps the trustworthy part of the system (evidence + tests)
  separate from the persuasive part (narration), which is the right architecture
  to defend in front of a security-minded panel.

---

## Phase 1 — substrate decisions

These concern the demo substrate: the instrumented `payments` app, the OTel
pipeline, and the alert. Verified end-to-end — p99 climbed to ~2.45s at pool 10
and `PaymentsHighLatencyP99` reached Alertmanager.

### 1.1 The regression is the pool size, nothing else

- **Options.** Make the incident from (a) a slow downstream call, (b) the pool
  size, (c) several changes at once.
- **Decision.** Exactly one variable, `POOL_MAX_SIZE`. Normal service time
  (~100ms: a DB write plus a card-processor call) is steady-state, not part of
  the regression; the high latency emerges purely from requests queueing on an
  undersized pool.
- **FDE mapping.** A single, clean cause is what lets the investigation produce a
  crisp current-vs-revert result. It also makes the Cursor agent's job legible:
  one line in `pool.py` explains the whole incident.

### 1.2 Runtime env knob now, committed regression for the Cursor demo

- **Options.** Induce the incident via (a) a committed code change to the default,
  (b) the `POOL_MAX_SIZE` env var at runtime.
- **Tradeoff.** (a) gives the Cloud Agent a real git diff to revert — needed for
  the Phase 3 current-vs-revert story — but means committing a "bad" change. (b)
  is instantly reversible (`break.sh` / `fix.sh`) and needs no commit, which suits
  the live alert demo and the no-commit rule.
- **Decision.** Use (b) for the live alert (Phase 1). For the full Cursor
  investigation, the regression should also exist as a committed change lowering
  the default to 10, which the engineer commits. The oracle test is written to
  flip on *either* lever, so both stories work.
- **FDE mapping.** Separating "reproduce the symptom" (cheap, reversible) from
  "the change under investigation" (a real commit) mirrors how an on-call
  engineer actually works an incident.

### 1.3 The oracle test is pool-size-agnostic

- **Decision.** `test_pool_exhaustion` instantiates `ConnectionPool()` with no
  argument, so its size follows whatever produced the incident (env override or
  committed default). It asserts a p95 latency ceiling under fixed concurrency.
- **FDE mapping.** This is the artifact that turns a hypothesis into proof: the
  Cloud Agent runs it on current code (fails) and reverted code (passes), and the
  RCA carries both results. Verified locally: pass at pool 50, fail at pool 10.

### 1.4 Alertmanager delivery target is wired but not yet consumed

- **Decision.** The Alertmanager webhook points at `causa-api:8000/webhook/alert`,
  which does not exist until Phase 4. In Phase 1 delivery simply retries; the
  alert still fires and is visible in Prometheus and Alertmanager.
- **FDE mapping.** The requirement was "a real alert fires before anything
  reacts". Decoupling the firing of the alert from its consumer keeps each phase
  independently verifiable and avoids a big-bang integration.

### 1.5 Two non-obvious instrumentation choices

- **Second-scale histogram buckets via OTel Views.** The SDK's default buckets are
  millisecond-tuned; our durations are in seconds, so without explicit boundaries
  `histogram_quantile` returns nonsense. The Views in `telemetry.py` fix this.
- **Observable gauges for the pool.** `payments_pool_inuse` / `payments_pool_max`
  are read at collection time, which is the correct instrument for "current
  value" and makes the dashboard show the pool pinned at its ceiling during the
  incident.
- **FDE mapping.** Getting the telemetry *correct* (not just present) is what lets
  the agent cite a metric as evidence with confidence — the difference between a
  dashboard that looks busy and one an engineer can reason from.

---

## Phase 2 — triage decisions

### 2.1 Prompt construction lives in one place
The brief is a typed model (`InvestigationBrief`) and `brief.to_agent_prompt()`
renders it plus the JSON Schema. The hand-written prompt from the smoke-test is
gone. **FDE mapping:** the agent receives a reproducible, auditable input, not an
ad-hoc string — the prerequisite for putting this in a real workflow.

### 2.2 Per-source graceful degradation
Each triage source is wrapped independently; a failure is recorded in the brief's
`degraded` list and the investigation still launches with a partial brief.
**FDE mapping:** at 02:14 a flaky Grafana must not block the investigation. This
is the "degrade, never crash" guardrail made concrete.

### 2.3 Triage surfaces noise on purpose
The mock GitHub source returns both the real culprit (`#482`) and an irrelevant
change in the window (`#2`, the pytest bump — the actual Dependabot PR). **FDE
mapping:** the value of the Cloud Agent is *discrimination* — it must rule the
noise out by reading code and running tests, not just list what changed. Handing
it a clean single suspect would hide the capability being sold.

### 2.4 Mocks mirror live output
`MockGrafanaSource` / `MockGitHubSource` return the same shapes (and deep-links)
the MCP path would. **FDE mapping:** a mock-driven demo looks identical to a live
one, so reliability never costs fidelity.

## Phase 3 — investigator decisions

### 3.1 Normalised JSONL between Node and Python
The Node runner translates the SDK's events into a small, stable JSONL vocabulary
(`status/thinking/tool_call/assistant/rca/error`) that Causa consumes. **FDE
mapping:** the beta SDK's event shapes can change without touching Causa or the
console; the integration is insulated at one seam.

### 3.2 The RCA comes from `result.result`, not the stream
The smoke-test showed the final contract object lives in
`getRun().wait().result`. The runner reads it there and emits one `rca` event;
the streamed deltas drive only the live feed. **FDE mapping:** separating "what to
show live" from "the authoritative result" avoids reconstructing structured output
from token deltas — a real robustness win observed from real data.

### 3.3 Contract validation is enforced on the Python side
`CursorInvestigator` validates the agent's JSON against `causa.contract.RCA`;
failure becomes an `error` event, never a rendered finding. **FDE mapping:** the
trust boundary sits in Causa, not in the agent's goodwill — exactly where an
enterprise needs it.

### 3.4 One interface, env-selected backend
`get_investigator()` returns `MockInvestigator` by default and
`CursorInvestigator` under `CAUSA_INVESTIGATOR=cursor`; likewise `CAUSA_TRIAGE`
for sources. **FDE mapping:** the same code path demos offline and runs live, and
the live pieces can be enabled one at a time.

---

## Phase 4–5 — orchestration and console decisions

### 4.1 Webhook returns immediately; the investigation runs on a thread
A live cloud run takes minutes, so `/webhook/alert` starts a daemon thread and
returns. **FDE mapping:** Alertmanager (and any real caller) gets a fast ack; the
slow work happens out of band, as a production webhook consumer must behave.

### 4.2 A manual trigger endpoint alongside the webhook
`POST /investigations` starts an investigation without Alertmanager, so the demo
can begin on a button press. **FDE mapping:** removes a live-infra dependency from
the riskiest moment of the demo while keeping the real webhook path intact.

### 4.3 The store is the event log the console reads
Events are appended to an in-memory record as they stream; the console polls the
record. **FDE mapping:** the same shape as a durable event log + database in
production; swapping the store out doesn't touch the orchestrator or console.

### 5.1 The console holds no state; it renders the API
Streamlit reads investigations and events from the API and renders three panes.
**FDE mapping:** the UI is a thin view over the contract — the valuable, testable
part is the API and the RCA, not the front-end.

### 5.2 Deep-links, not embedded dashboards
Evidence and telemetry render as links into Grafana/Jaeger/GitHub. **FDE mapping:**
the console is an investigation surface, not a dashboard; one click takes the
engineer to the authoritative view to verify a claim.

### 5.3 The "Open Draft PR" button is opt-in and usually absent
It shows only when the RCA carries a `draft_pr`; otherwise the console states the
RCA is the product. **FDE mapping:** reinforces decision-support over autonomous
change, and honours the no-auto-PR rule end to end.

---

## One-line summary to carry into the room

Causa uses deterministic triage to frame an incident, then uses the Cursor Cloud
Agent to do the one thing scripts and a stateless LLM cannot — understand the real
codebase, run the real tests, and reason about consequences — and returns a
validated analysis a senior engineer can act on. Every choice above protects that
story or makes it safe to run in front of an enterprise.
