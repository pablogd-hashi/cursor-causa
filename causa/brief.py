"""The investigation brief: the structured input Causa hands to the investigator.

This is the "brief-in" half of brief-in / contract-out. Triage (Grafana + GitHub
+ topology) produces this; the investigator (mock or Cursor) consumes it. Keeping
it a typed model means the prompt the agent receives is reproducible rather than
hand-written, and the console can render the same brief the agent saw.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel


class MetricSignature(BaseModel):
    name: str
    query: str
    observation: str
    deeplink: str | None = None


class CandidateChange(BaseModel):
    ref: str  # commit sha or PR ref like "#482"
    title: str
    merged_at: str
    url: str
    files: list[str] = []


class AlertContext(BaseModel):
    alertname: str
    fired_at: str  # ISO-8601
    expr: str | None = None
    severity: str | None = None


class IncidentWindow(BaseModel):
    start: str  # ISO-8601
    end: str


class RepoTarget(BaseModel):
    url: str
    ref: str = "main"
    subpath: str | None = None  # where the implicated service lives in the repo


class InvestigationBrief(BaseModel):
    investigation_id: str
    service: str
    alert: AlertContext
    window: IncidentWindow
    metric_signatures: list[MetricSignature]
    candidate_changes: list[CandidateChange]
    blast_radius_hint: list[str]  # from topology; the agent confirms/uses it
    repo: RepoTarget
    degraded: list[str] = []  # triage sources that were unavailable

    def to_agent_prompt(self, rca_schema: str) -> str:
        """Render the brief into the prompt the cloud agent receives. Requires the
        contract back as JSON — this is what makes the output validatable."""
        return (
            "You are a codebase investigator, not a code generator. Investigate "
            f"the following production incident in the '{self.service}' service.\n\n"
            "INVESTIGATION BRIEF (JSON):\n"
            f"{self.model_dump_json(indent=2)}\n\n"
            "Tasks:\n"
            "1. Identify the implicated execution path (files + functions) and the "
            "single change that explains the telemetry.\n"
            "2. Run the recommended test(s) on the current code and on the reverted "
            "code, and report both results.\n"
            "3. Use blast_radius_hint to reason about whether rollback or a "
            "forward-fix is safer.\n\n"
            "If read-only Grafana/Prometheus MCP tools are available to you "
            "(query_prometheus, generate_deeplink), use them to confirm the "
            "incident's metric signature yourself: query the p99 of "
            "payments_request_duration_seconds and payments_pool_inuse over the "
            "incident window, correlate the live telemetry with the code you find, "
            "and cite what you observed in supporting_telemetry (with deeplinks). "
            "If the MCP tools are unavailable, proceed from the brief's "
            "metric_signatures instead.\n\n"
            "Return ONLY a single JSON object that validates against this JSON "
            "Schema. No prose, no markdown fences, JSON only:\n\n"
            f"{rca_schema}"
        )


def incident_window(fired_at: str, lookback_minutes: int = 30) -> IncidentWindow:
    """The window triage searches: from ``lookback_minutes`` before the alert to
    the alert time. Candidate changes and the metric inflection live in here."""
    end = datetime.fromisoformat(fired_at.replace("Z", "+00:00"))
    start = end - timedelta(minutes=lookback_minutes)
    return IncidentWindow(
        start=start.isoformat().replace("+00:00", "Z"),
        end=end.isoformat().replace("+00:00", "Z"),
    )


def assemble_brief(
    *,
    investigation_id: str,
    service: str,
    alert: AlertContext,
    repo: RepoTarget,
    grafana,  # GrafanaSource
    github,  # GitHubSource
    topology,  # TopologySource
    lookback_minutes: int = 30,
) -> InvestigationBrief:
    """Run triage and assemble the brief. Each source is isolated so that one
    being unavailable degrades the brief (recorded in ``degraded``) rather than
    crashing the investigation."""
    window = incident_window(alert.fired_at, lookback_minutes)
    degraded: list[str] = []

    try:
        signatures = grafana.metric_signatures(service, window)
    except Exception as exc:  # degrade, never crash
        signatures = []
        degraded.append(f"grafana unavailable: {exc}")

    try:
        changes = github.candidate_changes(repo, window)
    except Exception as exc:
        changes = []
        degraded.append(f"github unavailable: {exc}")

    return InvestigationBrief(
        investigation_id=investigation_id,
        service=service,
        alert=alert,
        window=window,
        metric_signatures=signatures,
        candidate_changes=changes,
        blast_radius_hint=topology.dependents(service),
        repo=repo,
        degraded=degraded,
    )
