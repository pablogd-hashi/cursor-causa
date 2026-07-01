"""Causa MCP server — exposes investigation data as tools Cursor can call.

Run with:
    python -m causa.mcp_server          # stdio (default, for Cursor MCP)
    python -m causa.mcp_server --port   # not used; stdio is the Cursor transport

Add to .cursor/mcp.json:
    "causa": {
      "command": "python",
      "args": ["-m", "causa.mcp_server"],
      "cwd": "<repo-root>"
    }

The server queries the Causa API (CAUSA_API_URL, default http://localhost:8000)
so the API must be running.  All tools are read-only.
"""

from __future__ import annotations

import os
import sys

import httpx
from mcp.server.fastmcp import FastMCP

API = os.environ.get("CAUSA_API_URL", "http://localhost:8000")

mcp = FastMCP(
    "causa",
    instructions=(
        "Tools for inspecting live Causa incident investigations. "
        "Always call list_investigations first to find the relevant investigation ID, "
        "then use get_investigation or get_rca for details."
    ),
)

_client = httpx.Client(base_url=API, timeout=10)


def _get(path: str) -> dict | list | None:
    try:
        r = _client.get(path)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def list_investigations() -> list[dict]:
    """Return all investigations (newest first) with their current status.

    Each item contains: id, alertname, service, status, created_at.
    Status values: queued | triaging | investigating | complete | failed.
    """
    result = _get("/investigations")
    if isinstance(result, dict) and "error" in result:
        return [result]
    return result or []


@mcp.tool()
def get_investigation(investigation_id: str) -> dict:
    """Return the full investigation record including events, brief, and RCA.

    Args:
        investigation_id: The investigation ID (e.g. inv-20240101-120000-abc123).
            Use list_investigations() to find available IDs.
    """
    return _get(f"/investigations/{investigation_id}") or {}


@mcp.tool()
def get_rca(investigation_id: str) -> dict:
    """Return just the root-cause analysis for a completed investigation.

    Returns the RCA fields: summary, confidence, recommended_action,
    blast_radius, code_path, supporting_telemetry, evidence, tests, draft_pr.
    Returns {"status": "pending", "message": "..."} if not complete yet.

    Args:
        investigation_id: The investigation ID. Use list_investigations() to find IDs.
    """
    rec = _get(f"/investigations/{investigation_id}")
    if not rec:
        return {"error": "investigation not found"}
    if isinstance(rec, dict) and rec.get("error"):
        return {"error": rec["error"]}
    rca = rec.get("rca")
    if rca:
        return rca
    status = rec.get("status", "unknown")
    return {"status": status, "message": f"RCA not available yet (status: {status})"}


@mcp.tool()
def get_latest_investigation() -> dict:
    """Return the most recent investigation record (newest by creation time).

    Convenience wrapper around list_investigations + get_investigation.
    Returns the full record including events and RCA.
    """
    all_inv = _get("/investigations")
    if not all_inv or (isinstance(all_inv, dict) and "error" in all_inv):
        return all_inv or {"error": "no investigations found"}
    if isinstance(all_inv, list) and all_inv:
        return _get(f"/investigations/{all_inv[0]['id']}") or {}
    return {"error": "no investigations found"}


@mcp.tool()
def get_investigation_summary() -> str:
    """Return a human-readable summary of all investigations.

    Useful for a quick status overview without needing to process JSON.
    """
    all_inv = _get("/investigations")
    if not all_inv or (isinstance(all_inv, dict) and "error" in all_inv):
        err = all_inv.get("error", "unknown error") if isinstance(all_inv, dict) else "API error"
        return f"Could not reach Causa API ({API}): {err}"
    if not isinstance(all_inv, list) or not all_inv:
        return "No investigations found."

    lines = [f"Causa — {len(all_inv)} investigation(s)\n"]
    for inv in all_inv:
        status = inv["status"]
        running = status in {"queued", "triaging", "investigating"}
        indicator = "🔄" if running else ("✅" if status == "complete" else "❌")
        lines.append(
            f"{indicator} [{inv['created_at'][11:19]}] {inv['alertname']}"
            f" ({inv['service']}) — {status}  id={inv['id']}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
