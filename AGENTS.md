# AGENTS.md

## Cursor Cloud specific instructions

Causa is a phased prototype (Phases 0–5 complete; see `README.md` and
`architecture.md`). The whole pipeline runs on **mocks by default**, so the core
product — alert → triage → investigation → validated RCA, rendered in the
Streamlit console — needs **no external services, secrets, or Docker** to demo.
The optional live paths (`CAUSA_TRIAGE=mcp`, `CAUSA_INVESTIGATOR=cursor`, the
Docker observability stack, the `sdk-runner` smoke-test) need extra binaries
and/or secrets and are out of scope for a default local setup.

There is **no linter configured** (no ruff/flake8/pyproject); `./.venv/bin/python
-m py_compile <files>` is the closest syntax check.

`Dockerfile.api` / `Dockerfile.console` now exist, but building the full
`docker compose` stack pulls Node + the MCP binaries and is only needed for the
containerised/live path. For day-to-day dev, run the console outside Docker with
`./run-local.sh` (below); do **not** run a bare `docker compose up` (the
observability services still need an explicit service list — see below).

### Python (causa orchestrator/console + demo-app)

A single root virtualenv at `.venv` is created by the update script. It holds the
root `requirements.txt` (pydantic, pyyaml, fastapi, uvicorn, streamlit, requests)
**and** the `demo-app/requirements.txt` (payments service + OTel + pytest), so it
serves both packages. (`run-local.sh` will auto-`pip install -r requirements.txt`
into `.venv` if fastapi/streamlit are missing, but the update script already does
this.)

- Run the API + console (the core demo): `./run-local.sh` — starts the FastAPI
 API on `:8000` and the Streamlit console on `:8501`. Open `:8501`, click
 **Simulate payments alert**: the centre pane streams the live investigation feed
 and the right pane renders the validated RCA (confidence ~0.86, recommended
 `staged_rollout`, root cause = PR #482 shrinking the pool 50→10). Runs entirely
 on mocks.
- Run the pipeline in the terminal (no UI): `./.venv/bin/python -m causa.demo` —
 prints triage brief, the live feed, and the RCA.
- Validate fixture / regenerate schema: see the "Quick check" block in `README.md`.
- Oracle test: from `demo-app/`, `../.venv/bin/python -m pytest -q`. It is
 expected to **pass at the default pool 50 and fail under `POOL_MAX_SIZE=10`** —
 the failure is the demo's regression, not a broken environment.
- Run the payments app standalone: from `demo-app/`,
 `../.venv/bin/python -m uvicorn payments.api:app --host 0.0.0.0 --port 8080`.

Gotcha: the manual-trigger endpoint `POST /investigations` requires a JSON body
(`-H 'Content-Type: application/json' -d '{}'`); a bodyless POST returns 422. The
console sends the body for you.

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
