// Cursor Agent SDK smoke-test.
//
// Purpose: prove, end-to-end and before we build the real integration, that a
// Cursor *cloud* agent can clone the target repo, investigate the payments
// pool-exhaustion incident, run the oracle test, and return RCA JSON that
// matches our contract. Throwaway: the Phase 3 runner replaces it with a
// streaming JSONL protocol Causa consumes.
//
// It captures the ground truth we need to build that runner:
//   events.jsonl  - every streamed event, verbatim (the real event schema)
//   result.json   - the full final run object from getRun().wait()
//   rca-output.json - best-effort extraction of the agent's RCA JSON
//
// Run:  cd sdk-runner && npm install && CURSOR_API_KEY=... node smoke-test.mjs
//
// Requires: Pro plan, the Cursor GitHub app authorised on the target repo, and
// the repo pushed to GitHub (the cloud VM clones it from there).

import { Agent } from "@cursor/sdk";
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
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

// Pull any text-like payload out of an event/message of unknown shape.
function extractText(node) {
  if (!node) return "";
  if (typeof node === "string") return node;
  if (typeof node.text === "string") return node.text;
  if (typeof node.delta === "string") return node.delta;
  if (typeof node.content === "string") return node.content;
  if (Array.isArray(node.content)) return node.content.map(extractText).join("");
  if (node.message) return extractText(node.message);
  return "";
}

console.error(`launching cloud agent on ${repoUrl}@${ref} (model: ${model})`);

const agent = await Agent.create({
  apiKey,
  model: { id: model },
  cloud: { repos: [{ url: repoUrl, startingRef: ref }], autoCreatePR: false },
});

// The web link to watch this same run inside Cursor (cursor.com/agents).
console.error(`agent id: ${agent?.id ?? "?"}`);
console.error(`view in Cursor: ${agent?.url ?? "https://cursor.com/agents"}`);

const run = await agent.send(prompt);

const eventsPath = join(__dir, "events.jsonl");
writeFileSync(eventsPath, ""); // truncate from any previous run

let assistantText = "";
for await (const event of run.stream()) {
  appendFileSync(eventsPath, JSON.stringify(event) + "\n");
  if ((event?.type ?? "") === "assistant") assistantText += extractText(event);
  console.error(`[event ${event?.type ?? "unknown"}] ${JSON.stringify(event).slice(0, 200)}`);
}

const result = await (
  await Agent.getRun(run.id, { runtime: "cloud", agentId: run.agentId })
).wait();
writeFileSync(join(__dir, "result.json"), JSON.stringify(result, null, 2) + "\n");
console.error(`\nrun status: ${result?.status ?? "unknown"}`);

// Prefer the final text off the result object; fall back to streamed assistant text.
const finalText = (extractText(result?.messages?.at?.(-1)) || extractText(result) || assistantText).trim();
const a = finalText.indexOf("{");
const b = finalText.lastIndexOf("}");
const json = a >= 0 && b > a ? finalText.slice(a, b + 1) : finalText;
writeFileSync(join(__dir, "rca-output.json"), json + "\n");

console.error("\nwrote events.jsonl, result.json, rca-output.json");
console.error("validate the RCA with:");
console.error(
  `  ../.venv/bin/python -c "from causa.contract import RCA; RCA.model_validate_json(open('sdk-runner/rca-output.json').read()); print('RCA valid')"`
);
