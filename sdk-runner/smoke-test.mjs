// Cursor Agent SDK smoke-test.
//
// Purpose: prove, end-to-end and before we build the real integration, that a
// Cursor *cloud* agent can clone the target repo, investigate the payments
// pool-exhaustion incident, run the oracle test, and return RCA JSON that
// matches our contract. This is intentionally throwaway — the Phase 3 runner
// will replace it with a streaming JSONL protocol Causa consumes.
//
// It also serves a second purpose on its first run: it prints every streamed
// event verbatim, so we can see the *actual* event shapes (the public-beta SDK
// does not document them exhaustively) and tune the real runner accordingly.
//
// Run:  cd sdk-runner && npm install && CURSOR_API_KEY=... node smoke-test.mjs
//
// Requires: a Pro plan, the Cursor GitHub app authorised on the target repo,
// and the repo actually pushed to GitHub (the cloud VM clones it from there).

import { Agent } from "@cursor/sdk";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));

const apiKey = process.env.CURSOR_API_KEY;
if (!apiKey) {
  console.error("error: set CURSOR_API_KEY (cursor.com -> Dashboard -> Integrations -> API Keys)");
  process.exit(1);
}
const repoUrl = process.env.CURSOR_TARGET_REPO ?? "https://github.com/pablogd-hashi/cursor-causa";
const ref = process.env.CURSOR_TARGET_REF ?? "main";
const model = process.env.CURSOR_MODEL ?? "composer-2";

// Hand the agent the exact contract it must return.
const schema = readFileSync(join(__dir, "..", "schema", "rca.schema.json"), "utf8");

const prompt = `You are a codebase investigator, not a code generator. Investigate a
production incident in the "payments" service in this repository.

Incident brief:
- Alert: payments p99 latency exceeded 1s (PaymentsHighLatencyP99).
- Suspected cause: connection-pool exhaustion. Look in demo-app/payments/.
- The relevant code path begins at the charge handler and goes through the
  connection pool's acquire().

Tasks:
1. Identify the implicated execution path (files + functions) and the single
   change that explains the latency.
2. Run the oracle test demo-app/tests/test_pool_exhaustion.py on the current code,
   then again with the pool size restored to its healthy value, and report both
   results (it should fail on the incident configuration and pass when healthy).
3. Decide whether rollback or a forward-fix is safer and explain why.

Return ONLY a single JSON object that validates against this JSON Schema. No prose,
no markdown code fences, JSON only:

${schema}`;

console.error(`launching cloud agent on ${repoUrl}@${ref} (model: ${model})`);

const agent = await Agent.create({
  apiKey,
  model: { id: model },
  cloud: {
    repos: [{ url: repoUrl, startingRef: ref }],
    autoCreatePR: false, // never auto-open a PR; the engineer decides.
  },
});

const run = await agent.send(prompt);

// Accumulate assistant text; print every event compactly so we learn the shapes.
let assistantText = "";
for await (const event of run.stream()) {
  const type = event?.type ?? "unknown";
  const text = event?.text ?? event?.delta ?? event?.content ?? "";
  if (type === "assistant" && typeof text === "string") assistantText += text;
  // One compact line per event — this is the bit that reveals the real schema.
  console.error(`[event] ${JSON.stringify(event).slice(0, 300)}`);
}

// Wait for the cloud run to finish and pull the final result.
const result = await (
  await Agent.getRun(run.id, { runtime: "cloud", agentId: run.agentId })
).wait();

console.error(`\nrun status: ${result?.status ?? "unknown"}`);
const prUrl = result?.git?.branches?.[0]?.prUrl;
if (prUrl) console.error(`PR (should be none, autoCreatePR=false): ${prUrl}`);

// Best-effort: carve the JSON object out of the final assistant text.
const t = assistantText.trim();
const a = t.indexOf("{");
const b = t.lastIndexOf("}");
const json = a >= 0 && b > a ? t.slice(a, b + 1) : t;
const outPath = join(__dir, "rca-output.json");
writeFileSync(outPath, json + "\n");
console.error(`\nwrote ${outPath} — validate it with:`);
console.error(
  `  ../.venv/bin/python -c "from causa.contract import RCA; RCA.model_validate_json(open('sdk-runner/rca-output.json').read()); print('RCA valid')"`
);
