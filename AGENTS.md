# AGENTS.md

## Cursor Cloud specific instructions

Causa is a working prototype (Phases 0–6 complete; see `README.md` and
`architecture.md`). The full pipeline is built: the `causa` RCA contract, the
`demo-app` payments service + oracle test, the Docker observability stack, the
triage sources (mock + live Grafana/GitHub MCP in `causa/sources/`), the
investigator interface (`MockInvestigator` + `CursorInvestigator` via
`sdk-runner`), the FastAPI orchestration API (`causa/api.py`), and the Streamlit
console (`console/app.py`). `Dockerfile.api` / `Dockerfile.console` exist, but the
documented way to run the API and console is on the host via `run-local.sh`
(`task run:local` / `task demo`). Do **not** run a bare `docker compose up` —
bring up the substrate subset explicitly (see `README.md`), since the app
services build images and expect host-side env.

### Python (causa contract + demo-app)

A single root virtualenv at `.venv` is created by the update script and holds
both the contract deps (`pydantic`, `pyyaml`) and the `demo-app` requirements,
so it serves both packages. Standard commands (from `README.md`):

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
