// Production Cursor runner for Causa.
//
// Reads a JSON payload {prompt} on stdin, launches a Cursor agent, streams
// NORMALISED events as JSONL on stdout (forwarded to the console's live feed),
// and emits the final RCA:
//
//   {"type":"status","status":"...","text":"<agent url>"}
//   {"type":"thinking","text":"..."}
//   {"type":"tool_call","name":"read_file","status":"running"}
//   {"type":"assistant","text":"..."}
//   {"type":"rca","data":{...}}        <- final, the contract object
//   {"type":"error","text":"..."}
//
// Runtime (CURSOR_RUNTIME):
//   cloud (default) — a dedicated VM clones the repo; strong isolation. The final
//                     RCA comes from getRun().wait().result.
//   local           — runs on this machine against CURSOR_LOCAL_CWD (the repo
//                     root). Use this when you want the agent to reach the
//                     localhost Grafana/Prometheus MCP servers from .cursor/mcp.json.
//
// The agent picks up read-only Grafana/GitHub MCP from the repo's .cursor/mcp.json
// (see docs/agent-mcp.md), so it can confirm the metric signature itself.

import { Agent } from "@cursor/sdk";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

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

const runtime = (process.env.CURSOR_RUNTIME ?? "cloud").toLowerCase();
const repoUrl = process.env.CURSOR_TARGET_REPO ?? "https://github.com/pablogd-hashi/cursor-causa";
const ref = process.env.CURSOR_TARGET_REF ?? "main";
const model = process.env.CURSOR_MODEL ?? "composer-2";
const localCwd = process.env.CURSOR_LOCAL_CWD ?? REPO_ROOT;

try {
  const agent = await Agent.create({
    apiKey,
    model: { id: model },
    ...(runtime === "local"
      ? { local: { cwd: localCwd } }
      : { cloud: { repos: [{ url: repoUrl, startingRef: ref }], autoCreatePR: false } }),
  });
  emit({ type: "status", status: `launched (${runtime})`, text: agent?.url ?? "" });

  const run = await agent.send(prompt);

  let assistantText = "";
  for await (const event of run.stream()) {
    const type = event?.type ?? "unknown";
    if (type === "assistant") {
      const t = extractText(event);
      assistantText += t;
      emit({ type: "assistant", text: t });
    } else if (type === "thinking") {
      emit({ type: "thinking", text: event?.text ?? "" });
    } else if (type === "tool_call") {
      emit({ type: "tool_call", name: event?.name, status: event?.status });
    } else if (type === "status") {
      emit({ type: "status", status: event?.status });
    }
  }

  // Cloud runs expose the final structured output on getRun().wait().result;
  // local runs stream it as assistant text. Prefer result, fall back to stream.
  let raw = assistantText;
  if (runtime === "cloud") {
    try {
      const result = await (
        await Agent.getRun(run.id, { runtime: "cloud", agentId: run.agentId })
      ).wait();
      if (typeof result?.result === "string") raw = result.result;
    } catch {
      /* fall back to streamed assistant text */
    }
  }

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
