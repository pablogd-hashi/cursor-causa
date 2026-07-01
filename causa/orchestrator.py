"""Ties triage to investigation and records the result.

``run_investigation`` is the function the API runs on a background thread: it
assembles the brief, runs the selected investigator, and streams events into the
store as they arrive. It never raises into the caller — any failure is recorded
on the record so the console can show it (degrade, never crash).
"""

from __future__ import annotations

from pathlib import Path

from .brief import AlertContext, RepoTarget, assemble_brief
from .investigator import get_investigator
from .sources import get_sources
from .store import STORE, InvestigationStatus
from .topology import DeclaredTopologySource

_ROOT = Path(__file__).resolve().parent.parent


def run_investigation(
    investigation_id: str,
    alert: AlertContext,
    service: str,
    repo: RepoTarget,
) -> None:
    """Full pipeline for one alert: triage → investigate → store.

    Called from a background thread in ``causa/api.py`` so webhooks return
    immediately. Never raises — failures land on the investigation record."""
    try:
        # --- Triage: cheap lookups (mock or Grafana/GitHub MCP) ---
        grafana, github = get_sources()
        topology = DeclaredTopologySource(_ROOT / "topology.yaml")

        STORE.update(investigation_id, status=InvestigationStatus.triaging)
        brief = assemble_brief(
            investigation_id=investigation_id,
            service=service,
            alert=alert,
            repo=repo,
            grafana=grafana,
            github=github,
            topology=topology,
        )
        # Brief is stored so the console can show what the agent will receive.
        STORE.update(
            investigation_id, brief=brief, status=InvestigationStatus.investigating
        )

        # --- Investigation: mock replay or Cursor SDK (minutes for cloud) ---
        investigator = get_investigator()
        produced_rca = False
        for event in investigator.investigate(brief):
            STORE.append_event(investigation_id, event)
            if event.type == "rca" and event.rca is not None:
                STORE.update(investigation_id, rca=event.rca)
                produced_rca = True
            elif event.type == "error":
                STORE.update(investigation_id, error=event.text)

        STORE.update(
            investigation_id,
            status=InvestigationStatus.complete
            if produced_rca
            else InvestigationStatus.failed,
        )
    except Exception as exc:  # never let the worker thread crash silently
        STORE.update(
            investigation_id, status=InvestigationStatus.failed, error=str(exc)
        )
