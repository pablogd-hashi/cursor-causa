"""Triage source interfaces. Two narrow read-only ports, each with a mock
implementation (for the reliable demo) and an MCP-backed implementation (the
production path). The brief assembler depends only on these abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..brief import CandidateChange, IncidentWindow, MetricSignature, RepoTarget


class GrafanaSource(ABC):
    @abstractmethod
    def metric_signatures(
        self, service: str, window: IncidentWindow
    ) -> list[MetricSignature]:
        """The metric signature of the incident, with deep-links into the panels."""


class GitHubSource(ABC):
    @abstractmethod
    def candidate_changes(
        self, repo: RepoTarget, window: IncidentWindow
    ) -> list[CandidateChange]:
        """Commits/PRs merged into the incident window — the change suspects."""
