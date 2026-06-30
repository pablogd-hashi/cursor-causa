# Causa — demo storyline

A ~6–8 minute narrated demo: a code change ships, the metrics break, the alert
fires, and a Cursor Cloud Agent investigates the real code and tells the engineer
what to do. You drive it all from Cursor's integrated terminal and a browser tab;
you never have to navigate Cursor's agent UI (that's the point).

Each beat has **SAY** (what you narrate), **DO** (what you run/click), **SEE**
(what the audience sees).

---

## Before the room (off-screen setup)

- Create the regression PR (merge it manually before or during the demo):
  `task regression:pr` — then merge on GitHub. With `CAUSA_TRIAGE=mcp`, GitHub MCP
  surfaces that merged PR when the alert fires. See `docs/mcp-triage.md`.
- `CURSOR_API_KEY` is from the **same Cursor account** you're signed into, so the
  run shows at cursor.com/agents. Confirm:
  `curl -s https://api.cursor.com/v1/agents -u "$CURSOR_API_KEY:" | head`
- Have four things ready to show (tabs/windows):
  1. Cursor's integrated terminal,
  2. the Causa console (Simple Browser → http://localhost:8501),
  3. Grafana (http://localhost:3000/d/payments/payments),
  4. cursor.com/agents (optional flourish).
- Pre-pull images once so the demo isn't waiting on Docker:
  `docker compose pull`.

## Start it (one command, in Cursor's terminal)

**DO:**
```bash
CAUSA_INVESTIGATOR=cursor \
CURSOR_TARGET_REF=regression/lower-pool-size \
CURSOR_API_KEY=sk-...your-key... \
./demo.sh
```
This brings up the stack, ships the bad change as load (the alert fires in ~90s),
and launches the console. Open the console in Simple Browser.

**SAY:** "Causa watches a fintech `payments` service. Everything you'll see is
real — real metrics, a real alert, and a real Cursor agent reading the code."

---

## Act 1 — the change that shipped

**SAY:** "Someone merged a small change to `payments`: it lowered the database
connection pool from 50 to 10. Looks harmless."

**DO:** Show the diff — the PR, or
`https://github.com/pablogd-hashi/cursor-causa/blob/main/demo-app/payments/pool.py`
(`POOL_MAX_SIZE`).

**SEE:** A one-line change. The audience files it away as innocent.

## Act 2 — the symptom (Prometheus → Grafana)

**SAY:** "Under normal load that pool saturates. Requests queue, latency climbs."

**DO:** Open Grafana → the Payments dashboard.

**SEE:** p99 latency spiking to seconds; **pool in-use pinned at 10**; pool wait
time climbing in lockstep. This is the live data from the running service.

**SAY:** "Prometheus is evaluating a rule against this."

**DO:** Open http://localhost:9090/alerts.

**SEE:** `PaymentsHighLatencyP99` goes **pending → firing**. A real alert from real
metrics, not a script.

## Act 3 — Causa triages (cheap, deterministic)

**SAY:** "Alertmanager calls Causa. Before spending an agent, Causa does cheap
triage — it pulls the metric signature and the changes merged in the window."

**DO:** Switch to the console. Point at the centre pane.

**SEE:** A new investigation. The incident window, the **candidate changes**
(`pool.py`, and the unrelated pytest bump it will have to rule out), and the
timeline.

## Act 4 — Cursor investigates (the star)

**SAY:** "Now the part only Cursor can do. Causa hands the brief and the repo to a
Cursor Cloud Agent. It clones the repo into a VM and investigates the real code —
this isn't a chatbot guessing, it runs the tests."

**DO:** Watch the **live investigation feed** stream in the console.

**SEE:** `cloning repository` → `read_file pool.py` → `run_test
test_pool_exhaustion (current)` → fails → `(revert)` → passes.

**DO (optional flourish):** Flip to cursor.com/agents (or click *Watch this run in
Cursor*).

**SAY:** "Same run, inside Cursor — but my engineer never has to live in this UI;
Causa surfaces it for them."

## Act 5 — the answer (the RCA)

**SAY:** "A few minutes later, a structured, validated analysis."

**DO:** Point at the right pane.

**SEE:**
- **Confidence ~92%**, root cause: `POOL_MAX_SIZE` 50→10.
- **Tests**: `test_pool_exhaustion` — current **fail**, revert **pass** (run for
  real in the VM, not asserted).
- **Blast radius**: checkout, refunds, invoice, ledger (ledger transitively).
- **Recommended: forward-fix**, not rollback.

**SAY:** "And the judgement: it recommends restoring the pool, not a blunt
rollback — because a rollback would hit four downstream services and also remove
the instrumentation that made this diagnosable. That's an engineer's reasoning."

## Act 6 — the decision (close)

**SAY:** "The product is the analysis. The engineer decides; a pull request is an
optional, approved follow-up — Causa never opens one itself."

**DO:** Point at the "No draft PR — the RCA is the product" line.

**SAY (close):** "Causa is deterministic triage plus the Cursor Cloud Agent as a
codebase *investigator*. Cursor understood the codebase and helped the engineer
make the correct decision — that's the value in an enterprise SDLC."

---

## If something misbehaves (fallback)

- **Live run too slow / fails:** restart with `CAUSA_INVESTIGATOR=mock ./demo.sh`.
  The console is identical and returns instantly. Say: "Same pipeline, a recorded
  investigation, for reliability."
- **Grafana shows no data:** the background load needs ~30–60s; or the panel time
  range — the deep-links use `now-1h`.
- **Run not at cursor.com/agents:** the API key is a different account than the
  desktop app (it still works; it just won't show in that UI).

## What this would be in production (one line if asked)

The declared `topology.yaml` becomes a Consul query; Causa's own credentials come
from Vault; Causa emits its own traces. The seams are already in place — see
`architecture.md`.
