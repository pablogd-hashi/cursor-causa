# Demo storyline

Roughly six to eight minutes: a change ships, metrics go wrong, an alert fires,
Causa triages, a Cursor agent investigates, you get an RCA. You run everything
from the terminal and a browser — the audience does not need the Cursor app open.

Each beat: **SAY** / **DO** / **SEE**.

---

## Before you start

- `task regression:pr` — opens the pool-regression PR; merge it on GitHub when
  you want live GitHub triage (`CAUSA_TRIAGE=mcp`). See `docs/mcp-triage.md`.
- `CURSOR_API_KEY` from the same account you use at cursor.com/agents (optional).
- Tabs ready: terminal, console (:8501), Grafana, optionally cursor.com/agents.
- `docker compose pull` once so the demo does not wait on images.

## Start

```bash
CAUSA_INVESTIGATOR=cursor \
CURSOR_TARGET_REF=regression/lower-pool-size \
CURSOR_API_KEY=sk-... \
task demo
```

**SAY:** "Real metrics, real alert, real agent reading the repo."

---

## Act 1 — the change

**SAY:** "Someone merged a one-liner: connection pool 50 → 10."

**DO:** Show the PR or `demo-app/payments/pool.py` (`POOL_MAX_SIZE`).

## Act 2 — the symptom

**SAY:** "Under load the pool saturates; latency climbs."

**DO:** Grafana Payments dashboard → Prometheus alerts (`PaymentsHighLatencyP99` firing).

## Act 3 — triage

**SAY:** "Before spending an agent, Causa pulls metrics and recent merges."

**DO:** Console — incident window, candidate changes, timeline.

## Act 4 — investigation

**SAY:** "Causa hands the brief to a Cursor agent. It clones the repo and runs tests."

**DO:** Live feed — `read_file pool.py`, `run_test`, fail then pass on revert.

Optional: cursor.com/agents for the same run.

## Act 5 — the RCA

**DO:** Right pane — confidence, root cause, test results, blast radius, forward-fix.

**SAY:** "Restore the pool, not a blunt rollback — rollback hits downstream services
and removes the metrics that made this diagnosable."

## Act 6 — close

**SAY:** "The RCA is the product. Causa does not open PRs."

---

## Fallbacks

- Slow or failed cloud run: `CAUSA_INVESTIGATOR=mock task demo` — same UI, instant.
- Empty Grafana panels: wait for load (~60s) or check time range (`now-1h` on deeplinks).
- Run missing at cursor.com/agents: API key may be a different account (still works).

## Production-shaped version (if asked)

Live topology from a service mesh, credentials from Vault, Causa emitting its own
traces. The interfaces are already there — see `docs/architecture.md`.
