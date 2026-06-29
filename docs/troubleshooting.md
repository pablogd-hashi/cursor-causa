# Troubleshooting

## The stack

**`docker compose up` fails / daemon not running.** Start Docker Desktop, wait
for the whale icon, then retry. Check status with `docker compose ps`.

**A port is already in use (8000, 8501, 3000, 9090, 9093, 16686).** Something else
is bound. Find it with `lsof -i :8000` and stop it, or stop a previous Causa run
(`docker compose down`, and Ctrl-C any `run-local.sh`/`demo.sh`).

**Only some services should start.** `causa-api`/`causa-console` build from
Dockerfiles; for local dev run those two with `./run-local.sh` and only the
observability services in compose:
`docker compose up -d otel-collector prometheus alertmanager loki jaeger grafana demo-app`.

## The alert

**The alert never fires.** It needs sustained load. `./break.sh` drives 150
concurrent charges; give it ~90s (the rule is `for: 1m` after p99 crosses 1s).
Watch it at http://localhost:9090/alerts (pending -> firing).

**p99 stays low.** Confirm the pool is actually small: `curl localhost:8080/healthz`
should show `pool_max: 10` during the incident. `./break.sh` recreates the
container with `POOL_MAX_SIZE=10`.

**No `payments_*` metrics in Prometheus.** Metrics flow demo-app -> OTel Collector
-> Prometheus remote-write. Check the collector is up (`docker compose ps`) and
that the demo-app's `OTEL_EXPORTER_OTLP_ENDPOINT` points at `otel-collector:4317`.
(The Prometheus scrape of the collector's *own* `:8888` self-metrics may show
`down`; that is cosmetic and unrelated to the payments metric path.)

## The webhook -> Causa

**The firing alert doesn't auto-start an investigation.** Alertmanager posts to
`http://host.docker.internal:8000/webhook/alert`, so `causa-api` must be running
on the host (`./run-local.sh` or `./demo.sh`) and reachable on :8000. On Linux,
`host.docker.internal` needs `extra_hosts: ["host.docker.internal:host-gateway"]`
on the alertmanager service. Either way you can always trigger manually with the
console's "Simulate payments alert" button or `POST /investigations`.

**401 from the webhook.** A `CAUSA_WEBHOOK_SECRET` is set but Alertmanager isn't
sending the matching Bearer. Unset it for the demo, or wire the token into
`alertmanager.yml`.

## The console

**Console shows "API error".** `causa-api` isn't reachable. Check
`curl localhost:8000/healthz` and that `CAUSA_API_URL` (default
`http://localhost:8000`) is right.

**A headless screenshot of the console is blank.** Streamlit renders client-side
over a websocket; headless screenshotters often capture before it hydrates. Open
it in a real browser (or Cursor's Simple Browser) instead.

## Cursor (live investigator)

**`CURSOR_API_KEY` not picked up.** It must be *exported* (`export CURSOR_API_KEY=...`)
or prefixed on the command; `VAR=value` on its own line in zsh is not exported to
child processes. Verify with `printenv CURSOR_API_KEY`.

**The run doesn't appear in the Cursor agents window.** The run is tied to the
account that owns the API key. If your desktop Cursor is signed into a different
account, it won't show there — generate the key from the same account, or check
`GET https://api.cursor.com/v1/agents -u "$CURSOR_API_KEY:"` (each agent has a
`url`). The console also shows a "Watch this run in Cursor" link.

**The agent's RCA fails contract validation.** `CursorInvestigator` rejects output
that doesn't match `causa/contract.py` and emits an `error` event rather than
rendering it. Re-run; if it persists, inspect `sdk-runner/result.json` from a
`smoke-test.mjs` run to see what the agent returned.

**SDK method errors (`Agent.create`/`run.stream`/`getRun`).** `@cursor/sdk` is a
public beta; method names can drift. Run `sdk-runner/smoke-test.mjs`, inspect the
`events.jsonl` it writes, and adjust `run.mjs` to the observed shapes.

## Triage over MCP

**`CAUSA_TRIAGE=mcp` errors.** It needs the `mcp` Python package plus the
`mcp-grafana` and `github-mcp-server` binaries on PATH, and the relevant tokens.
Until those are present, leave the default `CAUSA_TRIAGE=mock`; triage degrades
gracefully and records the gap in the brief's `degraded` list.
