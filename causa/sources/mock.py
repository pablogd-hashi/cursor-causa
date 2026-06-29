"""Mock triage sources: realistic, deterministic data for the payments incident.

These let the whole pipeline and console run with no live Grafana/GitHub/MCP. The
data mirrors what the live sources would return for the 02:14 pool-exhaustion
incident, so a demo driven by mocks looks identical to one driven live."""

from __future__ import annotations

from ..brief import CandidateChange, IncidentWindow, MetricSignature, RepoTarget
from .base import GitHubSource, GrafanaSource

_GRAFANA = "http://localhost:3000/d/payments/payments"


class MockGrafanaSource(GrafanaSource):
    def metric_signatures(
        self, service: str, window: IncidentWindow
    ) -> list[MetricSignature]:
        return [
            MetricSignature(
                name="payments_pool_inuse",
                query="max(payments_pool_inuse)",
                observation="Saturates at 10 (== max) from the inflection point; "
                "the pool is fully checked out.",
                deeplink=f"{_GRAFANA}?viewPanel=4",
            ),
            MetricSignature(
                name="payments_request_duration_seconds",
                query="histogram_quantile(0.99, sum by (le) "
                "(rate(payments_request_duration_seconds_bucket[1m])))",
                observation="p99 rises from ~0.18s to >2s, tripping "
                "PaymentsHighLatencyP99.",
                deeplink=f"{_GRAFANA}?viewPanel=1",
            ),
            MetricSignature(
                name="payments_pool_wait_seconds",
                query="histogram_quantile(0.99, sum by (le) "
                "(rate(payments_pool_wait_seconds_bucket[1m])))",
                observation="Wait-to-acquire p99 climbs in lockstep with request "
                "latency — the queueing is on the pool.",
                deeplink=f"{_GRAFANA}?viewPanel=3",
            ),
        ]


class MockGitHubSource(GitHubSource):
    def candidate_changes(
        self, repo: RepoTarget, window: IncidentWindow
    ) -> list[CandidateChange]:
        base = repo.url.rstrip("/")
        return [
            CandidateChange(
                ref="#482",
                title="tune pool sizing",
                merged_at=window.end,
                url=f"{base}/pull/482",
                files=["demo-app/payments/pool.py"],
            ),
            # A genuine but irrelevant change in the window — triage surfaces it,
            # the agent should rule it out. (Mirrors the real Dependabot PR.)
            CandidateChange(
                ref="#2",
                title="Bump pytest from 8.3.4 to 9.0.3",
                merged_at=window.start,
                url=f"{base}/pull/2",
                files=["demo-app/requirements.txt"],
            ),
        ]
