# sdk-runner

Small Node program that starts a Cursor agent and streams its output back to
Causa as JSON lines on stdout. `causa/investigator.py` shells out to `run.mjs`;
you can also run `smoke-test.mjs` directly to test the integration.

## Before you run

1. **Push your branch to GitHub.** Cloud agents clone from GitHub, not your laptop.
2. **Pro plan** — cloud runs need it.
3. **Cursor GitHub app** — grant access to this repo (Cursor dashboard → Integrations).
4. **`CURSOR_API_KEY`** — Cursor dashboard → Integrations → API Keys.
5. **Node 18+**

Cloud runs cost tokens.

## Smoke test

```bash
cd sdk-runner
npm install
CURSOR_API_KEY=sk-... node smoke-test.mjs
```

Optional env: `CURSOR_TARGET_REPO`, `CURSOR_TARGET_REF`, `CURSOR_MODEL`,
`CURSOR_RUNTIME` (`cloud` or `local`).

Events go to stderr; the final RCA JSON lands in `rca-output.json`.

## Check the output

```bash
cd ..
./.venv/bin/python -c "from causa.contract import RCA; \
  RCA.model_validate_json(open('sdk-runner/rca-output.json').read()); print('ok')"
```

## Notes

- `autoCreatePR` is always `false`.
- `run.mjs` is what production uses; see comments at the top of that file for
  the event format and runtime modes.
