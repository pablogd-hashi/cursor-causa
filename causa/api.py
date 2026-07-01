"""FastAPI: the alert webhook, the results API, and the orchestration glue.

The webhook returns immediately and runs each investigation on a background
thread (a live cloud run takes minutes, so the request must not block). The
console reads investigations and their event streams from the results endpoints.
A manual trigger endpoint lets the demo start an investigation without a real
Alertmanager.
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from .brief import AlertContext, RepoTarget
from .orchestrator import run_investigation
from .store import STORE, InvestigationRecord

app = FastAPI(title="Causa API")

_DEFAULT_REPO = RepoTarget(
    # Cloud agents clone this URL; triage GitHub MCP searches the same repo.
    url=os.environ.get("CURSOR_TARGET_REPO", "https://github.com/pablogd-hashi/cursor-causa"),
    ref=os.environ.get("CURSOR_TARGET_REF", "main"),
    subpath="demo-app/",
)
_WEBHOOK_SECRET = os.environ.get("CAUSA_WEBHOOK_SECRET", "")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _spawn(investigation_id: str, alert: AlertContext, service: str) -> None:
    # A daemon thread keeps the event loop free during long (cloud) runs.
    threading.Thread(
        target=run_investigation,
        args=(investigation_id, alert, service, _DEFAULT_REPO),
        daemon=True,
    ).start()


def _start(alertname: str, service: str, alert: AlertContext) -> str:
    """Create a store record and kick off ``run_investigation`` on a worker thread."""
    investigation_id = f"inv-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    STORE.create(
        InvestigationRecord(id=investigation_id, alertname=alertname, service=service)
    )
    _spawn(investigation_id, alert, service)
    return investigation_id


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/webhook/alert")
async def webhook_alert(
    request: Request, authorization: str | None = Header(default=None)
):
    """Alertmanager webhook. Verifies the shared secret (if configured), then
    starts an investigation per firing alert."""
    if _WEBHOOK_SECRET and authorization != f"Bearer {_WEBHOOK_SECRET}":
        raise HTTPException(status_code=401, detail="bad or missing webhook secret")

    payload = await request.json()
    started: list[str] = []
    for alert in payload.get("alerts", []):
        if alert.get("status") != "firing":
            continue
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        alertname = labels.get("alertname", "UnknownAlert")
        service = labels.get("service", "payments")
        ctx = AlertContext(
            alertname=alertname,
            fired_at=alert.get("startsAt", _now()),
            expr=annotations.get("description"),
            severity=labels.get("severity"),
        )
        started.append(_start(alertname, service, ctx))
    return {"accepted": len(started), "investigation_ids": started}


class TriggerBody(BaseModel):
    alertname: str = "PaymentsHighLatencyP99"
    service: str = "payments"
    fired_at: str | None = None


@app.post("/investigations")
def trigger(body: TriggerBody):
    """Manually start an investigation (used by the console's simulate button)."""
    ctx = AlertContext(
        alertname=body.alertname,
        fired_at=body.fired_at or _now(),
        severity="page",
    )
    investigation_id = _start(body.alertname, body.service, ctx)
    return {"id": investigation_id}


@app.get("/investigations")
def list_investigations():
    # Lightweight list for the left pane.
    return [
        {
            "id": r.id,
            "alertname": r.alertname,
            "service": r.service,
            "status": r.status.value,
            "created_at": r.created_at,
        }
        for r in STORE.list()
    ]


@app.get("/investigations/{investigation_id}")
def get_investigation(investigation_id: str):
    record = STORE.get(investigation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="not found")
    return record
