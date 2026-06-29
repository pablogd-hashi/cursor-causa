# sdk-runner

A standalone smoke-test for the Cursor Agent SDK + Cloud Agent, used to de-risk
the integration before Phase 3 builds the real streaming runner.

## Prerequisites

1. **The repo must be pushed to GitHub.** The cloud agent clones
   `pablogd-hashi/cursor-causa` from GitHub, so the `demo-app/` code and the
   oracle test must be present at the ref you target. Commit and push first.
2. **Pro plan** — cloud runs require it.
3. **Cursor GitHub app** authorised on the target repo (Cursor dashboard →
   Integrations → GitHub → grant access to `cursor-causa` only).
4. **API key** — `CURSOR_API_KEY` (Cursor dashboard → Integrations → API Keys).
5. Node 18+ (you have v22).

Cloud runs consume tokens (token-based pricing), so each smoke run has a small cost.

## Run

```bash
cd sdk-runner
npm install
CURSOR_API_KEY=...your-key... node smoke-test.mjs
# optional overrides:
#   CURSOR_TARGET_REPO=https://github.com/pablogd-hashi/cursor-causa
#   CURSOR_TARGET_REF=main
#   CURSOR_MODEL=composer-2
```

It streams every event to stderr (so you can see the real event shapes), waits
for the run to finish, and writes the agent's RCA JSON to `rca-output.json`.

## Verify the contract

```bash
cd ..
./.venv/bin/python -c "from causa.contract import RCA; \
  RCA.model_validate_json(open('sdk-runner/rca-output.json').read()); print('RCA valid')"
```

A passing validation is the proof point: the Cloud Agent investigated real code,
ran the real test, and returned output that fits Causa's contract.

## Notes

- `autoCreatePR` is hard-set to `false` — the agent never opens a PR.
- This script has not been run against a live key here, so the SDK method names
  (`Agent.create` / `run.stream` / `Agent.getRun().wait`) match the public-beta
  launch docs but may have drifted. The first run's event dump tells us the
  truth; the Phase 3 runner is built from that.
```
