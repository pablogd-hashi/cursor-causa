"""MCP-backed triage sources.

``McpGrafanaSource`` is live: it spawns the read-only ``mcp-grafana`` server over
stdio (the Python ``mcp`` client) and calls its real tools — ``query_prometheus``
for the metric signature and ``generate_deeplink`` for the panel links. This is
genuine MCP, not a stub.

``McpGitHubSource`` is the same pattern for ``github-mcp-server``; it needs that
binary on PATH and a token. Until that is set up, the factory pairs the live
Grafana source with the mock GitHub source, and the brief assembler degrades any
source that is unavailable.

Selected via ``CAUSA_TRIAGE=mcp``.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import shutil

from ..brief import CandidateChange, IncidentWindow, MetricSignature, RepoTarget
from .base import GitHubSource, GrafanaSource

_PROM_UID = os.environ.get("GRAFANA_PROM_UID", "prometheus")
_DASHBOARD = os.environ.get("GRAFANA_DASHBOARD_UID", "payments")
_WINDOW = "&from=now-1h&to=now"

# PromQL the triage runs. p99 of the charge handler, and pool saturation.
_P99_EXPR = (
    "histogram_quantile(0.99, sum by (le) "
    "(rate(payments_request_duration_seconds_bucket[5m])))"
)
_INUSE_EXPR = "max(payments_pool_inuse)"


def _grafana_bin() -> str:
    return (
        os.environ.get("GRAFANA_MCP_BIN")
        or shutil.which("mcp-grafana")
        or os.path.expanduser("~/go/bin/mcp-grafana")
    )


def _grafana_env() -> dict:
    env = {**os.environ, "GRAFANA_URL": os.environ.get("GRAFANA_URL", "http://localhost:3000")}
    # Prefer a service-account token; fall back to basic auth (local Grafana).
    if not os.environ.get("GRAFANA_SERVICE_ACCOUNT_TOKEN"):
        env.setdefault("GRAFANA_USERNAME", os.environ.get("GRAFANA_USERNAME", "admin"))
        env.setdefault("GRAFANA_PASSWORD", os.environ.get("GRAFANA_PASSWORD", "admin"))
    return env


def _first_text(result) -> str:
    for block in result.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def _scalar(result) -> float | None:
    """Pull the single value out of a query_prometheus instant result."""
    try:
        data = json.loads(_first_text(result)).get("data", [])
        return float(data[0]["value"][1])
    except (json.JSONDecodeError, IndexError, KeyError, ValueError, TypeError):
        return None


def _fmt(value: float | None, unit: str = "") -> str:
    if value is None or math.isnan(value):
        return "no data in window"
    return f"{value:.2f}{unit}"


class McpGrafanaSource(GrafanaSource):
    def metric_signatures(
        self, service: str, window: IncidentWindow
    ) -> list[MetricSignature]:
        return asyncio.run(self._collect())

    async def _collect(self) -> list[MetricSignature]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=_grafana_bin(), args=["--disable-write"], env=_grafana_env()
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                async def query(expr: str) -> float | None:
                    res = await session.call_tool(
                        "query_prometheus",
                        {
                            "datasourceUid": _PROM_UID,
                            "expr": expr,
                            "queryType": "instant",
                            "endTime": "now",
                        },
                    )
                    return _scalar(res)

                async def panel_link(panel_id: int) -> str:
                    res = await session.call_tool(
                        "generate_deeplink",
                        {
                            "resourceType": "panel",
                            "dashboardUid": _DASHBOARD,
                            "panelId": panel_id,
                        },
                    )
                    return _first_text(res) + _WINDOW

                p99 = await query(_P99_EXPR)
                inuse = await query(_INUSE_EXPR)
                return [
                    MetricSignature(
                        name="payments_request_duration_seconds",
                        query=_P99_EXPR,
                        observation=f"p99 = {_fmt(p99, 's')} (live, via Grafana MCP)",
                        deeplink=await panel_link(1),
                    ),
                    MetricSignature(
                        name="payments_pool_inuse",
                        query=_INUSE_EXPR,
                        observation=f"in-use = {_fmt(inuse)} (live, via Grafana MCP)",
                        deeplink=await panel_link(4),
                    ),
                ]


class McpGitHubSource(GitHubSource):
    """Live GitHub triage over github-mcp-server. Requires that binary on PATH
    and GITHUB_PERSONAL_ACCESS_TOKEN; raises (and the brief degrades) otherwise."""

    def candidate_changes(
        self, repo: RepoTarget, window: IncidentWindow
    ) -> list[CandidateChange]:
        return asyncio.run(self._collect(repo, window))

    async def _collect(self, repo: RepoTarget, window: IncidentWindow):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        binary = shutil.which("github-mcp-server")
        if not binary:
            raise RuntimeError("github-mcp-server not installed")
        owner, name = repo.url.rstrip("/").split("/")[-2:]
        params = StdioServerParameters(
            command=binary,
            args=["stdio", "--read-only", "--toolsets", "repos,pull_requests"],
            env={**os.environ},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                res = await session.call_tool(
                    "list_pull_requests",
                    {"owner": owner, "repo": name, "state": "closed"},
                )
                prs = json.loads(_first_text(res)) or []
                out: list[CandidateChange] = []
                for pr in prs:
                    merged = pr.get("merged_at") or pr.get("mergedAt")
                    if merged and window.start <= merged <= window.end:
                        out.append(
                            CandidateChange(
                                ref=f"#{pr.get('number')}",
                                title=pr.get("title", ""),
                                merged_at=merged,
                                url=pr.get("html_url", ""),
                            )
                        )
                return out
