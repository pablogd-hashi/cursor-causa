"""Triage source selection.

``CAUSA_TRIAGE=mock`` (default) uses the deterministic mock sources, so the demo
runs with no live dependencies. ``CAUSA_TRIAGE=mcp`` uses the read-only Grafana
and GitHub MCP servers. Either way the brief assembler sees the same interfaces.
"""

from __future__ import annotations

import os

from .base import GitHubSource, GrafanaSource


def get_sources() -> tuple[GrafanaSource, GitHubSource]:
    """Pick triage backends from ``CAUSA_TRIAGE``.

    mock  — deterministic fixtures, no external deps (default).
    mcp   — live Grafana MCP; GitHub MCP when binary + token are present.
    mcp-all — both MCP sources required (no GitHub mock fallback).
    """
    mode = os.environ.get("CAUSA_TRIAGE", "mock").lower()
    if mode in ("mcp", "mcp-all"):
        import shutil

        from .mcp import McpGrafanaSource

        grafana = McpGrafanaSource()  # live: spawns read-only mcp-grafana

        gh_bin = (
            os.environ.get("GITHUB_MCP_BIN")
            or shutil.which("github-mcp-server")
            or os.path.expanduser("~/go/bin/github-mcp-server")
        )
        gh_ready = os.path.exists(gh_bin) and os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
        # "mcp-all" forces live GitHub; "mcp" uses it when the binary + token are
        # present, otherwise falls back to the mock so the demo stays clean.
        if mode == "mcp-all" or gh_ready:
            from .mcp import McpGitHubSource

            return grafana, McpGitHubSource()
        from .mock import MockGitHubSource

        return grafana, MockGitHubSource()
    from .mock import MockGitHubSource, MockGrafanaSource

    return MockGrafanaSource(), MockGitHubSource()


__all__ = ["GrafanaSource", "GitHubSource", "get_sources"]
