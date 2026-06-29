# AGENTS.md

## Cursor Cloud specific instructions

Causa is a phased prototype (Phases 0–5 complete, Phase 6 pending; see
`README.md` and `architecture.md`). The whole product now runs locally **on
mocks with no secrets**: the `causa` RCA contract, the triage → brief →
investigation → RCA pipeline (`python -m causa.demo`), the FastAPI results API
+ Streamlit three-pane console (`./run-local.sh`), the `demo-app` payments
service + oracle test, the Docker observability stack, and the `sdk-runner`
Cursor SDK smoke-test.

`Dockerfile.api` / `Dockerfile.console` now exist, so the `causa-api` /
`causa-console` images are buildable. Note their build runs `apt`/`npm` and so
needs network egress, and the live MCP/Cursor paths still need secrets at
runtime. For day-to-day development of the Causa app prefer `./run-local.sh`
(API on `:8000`, console on `:8501`, mock triage + mock investigator). For the
observability substrate, bring up the explicit service list documented in the
"Run the substrate" section of `README.md` rather than a bare
`docker compose up`.

### Causa app (API + console, runs on mocks)

- End-to-end mock pipeline (prints triage brief, live feed, validated RCA):
  `./.venv/bin/python -m causa.demo`.
- API + console together: `./run-local.sh`. Open the console at
  `http://localhost:8501` and click **Simulate payments alert**; the right pane
  fills with a contract-valid RCA (confidence ~0.86, action `staged_rollout`).
  Needs no secrets — `CAUSA_TRIAGE`/`CAUSA_INVESTIGATOR` default to mocks. Set
  `CAUSA_INVESTIGATOR=cursor` + `CURSOR_API_KEY` only for a real cloud run.
- The investigation runs on a background thread and the mock completes in well
  under a second, so the console shows it already `complete` after the first
  ~1.5s auto-refresh — you will rarely catch a visible "running" state.
- No dedicated Python linter is configured; the contract/schema/compile "Quick
  check" block in `README.md` is the lightweight gate.

### Python (causa contract + demo-app)

A single root virtualenv at `.venv` is created by the update script and holds
the full root `requirements.txt` (contract + API + console: `pydantic`,
`pyyaml`, `fastapi`, `uvicorn`, `streamlit`, `requests`) plus the `demo-app`
requirements, so it serves every Python package here. Standard commands (from
`README.md`):

- Validate fixture / regenerate schema: see the "Quick check" block in `README.md`.
- Oracle test: from `demo-app/`, `../.venv/bin/python -m pytest -q`. It is
  expected to **pass at the default pool 50 and fail under `POOL_MAX_SIZE=10`** —
  the failure is the demo's regression, not a broken environment.
- Run the payments app standalone: from `demo-app/`,
  `../.venv/bin/python -m uvicorn payments.api:app --host 0.0.0.0 --port 8080`.

Gotcha: when the payments app runs **without** the OTel collector (e.g.
standalone, not via Docker), it logs repeated `Transient error
StatusCode.UNAVAILABLE ... exporting ... to otel-collector:4317` lines. These
are harmless — the app still serves `/healthz` and `/charge`. The errors stop
once the collector is up (via the Docker stack).

### Docker observability stack

Docker (engine + compose plugin, fuse-overlayfs storage driver, iptables-legacy)
is pre-installed in the VM image, and the `ubuntu` user is in the `docker`
group. Two non-obvious startup caveats:

- **The Docker daemon is not auto-started.** Start it once per session, e.g.
  `sudo dockerd` (run it in a background/tmux session; it stays in the
  foreground). Verify with `sudo docker info`.
- **`docker` without sudo needs a fresh login shell** for the `docker` group to
  apply. In the same shell that started `dockerd`, either open a new login
  shell or wrap script calls, e.g. `sg docker -c "./break.sh"`. `sudo docker ...`
  always works.

Bring up the substrate (observability backends + payments app) exactly as the
"Run the substrate" section of `README.md` documents — list the services
explicitly; do **not** run a bare `docker compose up`.

The incident demo works end-to-end: `./break.sh` recreates `demo-app` at
`POOL_MAX_SIZE=10` and drives load until `PaymentsHighLatencyP99` fires
(p99 ~2.45s; the alert needs p99 > 1s sustained `for: 1m`, so allow ~90s of
load before it flips to firing). `./fix.sh` restores pool 50. After load stops,
p99 recovers and the alert auto-resolves (Alertmanager clears it) — that is
expected. URLs: Prometheus `:9090`, Alertmanager `:9093`, Grafana `:3000`
(anonymous Viewer), Jaeger `:16686`.

If `demo-app`'s host port `8080` fails to bind, a standalone uvicorn from the
section above is probably still holding it — stop that first. If a `demo-app`
container was created during a failed `compose up`, it may run without its port
mapping; `docker compose up -d --force-recreate demo-app` fixes it.

### sdk-runner (Cursor Agent SDK smoke-test)

`npm install` (in `sdk-runner/`) is handled by the update script. The smoke-test
itself (`node smoke-test.mjs`) launches a **real Cursor Cloud Agent** and
requires `CURSOR_API_KEY`, a Pro plan, and the Cursor GitHub app authorised on
the target repo (see `sdk-runner/README.md`). It cannot run without those
secrets and incurs token cost, so it is out of scope for a default local setup.
