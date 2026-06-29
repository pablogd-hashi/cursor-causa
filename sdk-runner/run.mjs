// Production Cursor runner for Causa (Phase 3).
//
// Reads a JSON payload {prompt} on stdin, launches a cloud agent on the target
// repo, and emits NORMALISED events as JSONL on stdout — one object per line —
// which CursorInvestigator (Python) forwards to the console's live feed:
//
//   {"type":"status","status":"...","text":"<agent url>"}
//   {"type":"thinking","text":"..."}
//   {"type":"tool_call","name":"read_file","status":"running"}
//   {"type":"assistant","text":"..."}
//   {"type":"rca","data":{...}}        <- final, the contract object
//   {"type":"error","text":"..."}
//
// The final RCA is taken from getRun().wait().result (a JSON string), which the
// smoke-test established is the canonical place for the agent's structured output.
//
// Repo/ref/model and CURSOR_API_KEY come from the environment.

import { Agent } from "@cursor/sdk";
import { readFileSync } from "node:fs";

function emit(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
}

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

const apiKey = process.env.CURSOR_API_KEY;
if (!apiKey) {
  emit({ type: "error", text: "CURSOR_API_KEY not set" });
  process.exit(1);
}

let payload = {};
try {
  payload = JSON.parse(readFileSync(0, "utf8") || "{}");
} catch (e) {
  emit({ type: "error", text: `could not parse stdin payload: ${e}` });
  process.exit(1);
}
const prompt = payload.prompt;
if (!prompt) {
  emit({ type: "error", text: "no prompt provided on stdin" });
  process.exit(1);
}

const repoUrl = process.env.CURSOR_TARGET_REPO ?? "https://github.com/pablogd-hashi/cursor-causa";
const ref = process.env.CURSOR_TARGET_REF ?? "main";
const model = process.env.CURSOR_MODEL ?? "composer-2";

try {
  const agent = await Agent.create({
    apiKey,
    model: { id: model },
    cloud: { repos: [{ url: repoUrl, startingRef: ref }], autoCreatePR: false },
  });
  emit({ type: "status", status: "launched", text: agent?.url ?? "" });

  const run = await agent.send(prompt);
  for await (const event of run.stream()) {
    const type = event?.type ?? "unknown";
    if (type === "assistant") emit({ type: "assistant", text: extractText(event) });
    else if (type === "thinking") emit({ type: "thinking", text: event?.text ?? "" });
    else if (type === "tool_call")
      emit({ type: "tool_call", name: event?.name, status: event?.status });
    else if (type === "status") emit({ type: "status", status: event?.status });
    // other event types are ignored for the feed
  }

  const result = await (
    await Agent.getRun(run.id, { runtime: "cloud", agentId: run.agentId })
  ).wait();

  const raw =
    typeof result?.result === "string" ? result.result : extractText(result);
  const a = raw.indexOf("{");
  const b = raw.lastIndexOf("}");
  const jsonStr = a >= 0 && b > a ? raw.slice(a, b + 1) : raw;
  let data;
  try {
    data = JSON.parse(jsonStr);
  } catch (e) {
    emit({ type: "error", text: `could not parse RCA JSON from result: ${e}` });
    process.exit(1);
  }
  emit({ type: "rca", data });
} catch (e) {
  emit({ type: "error", text: String(e?.message ?? e) });
  process.exit(1);
}
