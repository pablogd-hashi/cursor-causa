"""MCP-backed triage sources (the production path).

Causa acts as an MCP client, spawning the read-only Grafana and GitHub MCP
servers over stdio per ``.mcp.json`` and calling their tools. This is the
faithful "MCP-driven triage" implementation; the Grafana server's
``generate_deeplink`` tool is what builds the console's panel links.

Status: this requires the ``mcp`` Python package and the ``mcp-grafana`` /
``github-mcp-server`` binaries on PATH (baked into the causa-api image in a
later phase). Until then it raises on use and the brief assembler degrades
gracefully to whatever sources are available. Tool names below match the
servers' documented tools but should be confirmed against ``session.list_tools()``
on first wiring — that is why ``_call`` looks tools up before calling.
"""

from __future__ import annotations

import asyncio
import json
import os

from ..brief import CandidateChange, IncidentWindow, MetricSignature, RepoTarget
from .base import GitHubSource, GrafanaSource


async def _call(command: str, args: list[str], env: dict, tool: str, params: dict):
    """Spawn an MCP server over stdio, initialise, and call one tool."""
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:  # package not installed yet
        raise RuntimeError(f"mcp client not installed: {exc}") from exc

    server = StdioServerParameters(command=command, args=args, env={**os.environ, **env})
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            available = {t.name for t in (await session.list_tools()).tools}
            if tool not in available:
                raise RuntimeError(f"tool '{tool}' not offered by {command}; saw {sorted(available)}")
            result = await session.call_tool(tool, params)
            # MCP returns content blocks; the first text block carries the payload.
            for block in result.content:
                if getattr(block, "type", None) == "text":
                    return json.loads(block.text)
            return None


def _run(coro):
    return asyncio.run(coro)


class McpGrafanaSource(GrafanaSource):
    def __init__(self) -> None:
        self._env = {
            "GRAFANA_URL": os.environ.get("GRAFANA_URL", "http://localhost:3000"),
            "GRAFANA_SERVICE_ACCOUNT_TOKEN": os.environ.get(
                "GRAFANA_SERVICE_ACCOUNT_TOKEN", ""
            ),
        }

    def metric_signatures(
        self, service: str, window: IncidentWindow
    ) -> list[MetricSignature]:
        # Query the incident's headline metric, then ask Grafana for a deeplink.
        query = (
            "histogram_quantile(0.99, sum by (le) "
            "(rate(payments_request_duration_seconds_bucket[1m])))"
        )
        data = _run(
            _call(
                "mcp-grafana",
                ["--disable-write"],
                self._env,
                "query_prometheus",
                {"query": query, "start": window.start, "end": window.end},
            )
        )
        deeplink = _run(
            _call(
                "mcp-grafana",
                ["--disable-write"],
                self._env,
                "generate_deeplink",
                {"dashboardUid": "payments", "panelId": 1,
                 "from": window.start, "to": window.end},
            )
        )
        return [
            MetricSignature(
                name="payments_request_duration_seconds",
                query=query,
                observation=f"p99 series during the window: {json.dumps(data)[:200]}",
                deeplink=deeplink if isinstance(deeplink, str) else None,
            )
        ]


class McpGitHubSource(GitHubSource):
    def __init__(self) -> None:
        self._env = {
            "GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get(
                "GITHUB_PERSONAL_ACCESS_TOKEN", ""
            )
        }

    def candidate_changes(
        self, repo: RepoTarget, window: IncidentWindow
    ) -> list[CandidateChange]:
        owner, name = repo.url.rstrip("/").split("/")[-2:]
        prs = _run(
            _call(
                "github-mcp-server",
                ["stdio", "--read-only", "--toolsets", "repos,pull_requests"],
                self._env,
                "list_pull_requests",
                {"owner": owner, "repo": name, "state": "closed"},
            )
        )
        changes: list[CandidateChange] = []
        for pr in prs or []:
            merged = pr.get("merged_at") or pr.get("mergedAt")
            if merged and window.start <= merged <= window.end:
                changes.append(
                    CandidateChange(
                        ref=f"#{pr.get('number')}",
                        title=pr.get("title", ""),
                        merged_at=merged,
                        url=pr.get("html_url", ""),
                    )
                )
        return changes
