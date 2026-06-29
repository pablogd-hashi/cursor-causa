"""Triage source selection.

``CAUSA_TRIAGE=mock`` (default) uses the deterministic mock sources, so the demo
runs with no live dependencies. ``CAUSA_TRIAGE=mcp`` uses the read-only Grafana
and GitHub MCP servers. Either way the brief assembler sees the same interfaces.
"""

from __future__ import annotations

import os

from .base import GitHubSource, GrafanaSource


def get_sources() -> tuple[GrafanaSource, GitHubSource]:
    mode = os.environ.get("CAUSA_TRIAGE", "mock").lower()
    if mode in ("mcp", "mcp-all"):
        from .mcp import McpGrafanaSource

        grafana = McpGrafanaSource()  # live: spawns read-only mcp-grafana
        if mode == "mcp-all":
            from .mcp import McpGitHubSource

            return grafana, McpGitHubSource()  # needs github-mcp-server on PATH
        # GitHub MCP binary isn't installed in the prototype, so pair the live
        # Grafana MCP with the mock GitHub source.
        from .mock import MockGitHubSource

        return grafana, MockGitHubSource()
    from .mock import MockGitHubSource, MockGrafanaSource

    return MockGrafanaSource(), MockGitHubSource()


__all__ = ["GrafanaSource", "GitHubSource", "get_sources"]
