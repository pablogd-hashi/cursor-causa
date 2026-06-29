"""End-to-end pipeline demo: alert -> triage -> brief -> investigation -> RCA.

This wires Phases 2 and 3 together and prints the flow the Streamlit console
(Phase 5) will render. It runs entirely on mocks by default, so it needs no live
Grafana/GitHub/Cursor:

    python -m causa.demo

Switch backends with env vars:
    CAUSA_TRIAGE=mcp          use the read-only Grafana/GitHub MCP servers
    CAUSA_INVESTIGATOR=cursor use a real Cursor cloud agent (needs CURSOR_API_KEY)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .brief import AlertContext, RepoTarget, assemble_brief
from .investigator import get_investigator
from .sources import get_sources
from .topology import DeclaredTopologySource

_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    grafana, github = get_sources()
    topology = DeclaredTopologySource(_ROOT / "topology.yaml")

    fired_at = "2026-06-29T02:14:00Z"
    investigation_id = "inv-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-payments"

    alert = AlertContext(
        alertname="PaymentsHighLatencyP99",
        fired_at=fired_at,
        expr="histogram_quantile(0.99, sum by (le) "
        "(rate(payments_request_duration_seconds_bucket[1m]))) > 1",
        severity="page",
    )
    repo = RepoTarget(
        url="https://github.com/pablogd-hashi/cursor-causa",
        ref="main",
        subpath="demo-app/",
    )

    print("== TRIAGE ==")
    brief = assemble_brief(
        investigation_id=investigation_id,
        service="payments",
        alert=alert,
        repo=repo,
        grafana=grafana,
        github=github,
        topology=topology,
    )
    print(f"  alert        : {brief.alert.alertname} @ {brief.alert.fired_at}")
    print(f"  window       : {brief.window.start} -> {brief.window.end}")
    print(f"  metrics      : {[m.name for m in brief.metric_signatures]}")
    print(f"  candidates   : {[c.ref + ' ' + c.title for c in brief.candidate_changes]}")
    print(f"  blast radius : {brief.blast_radius_hint}")
    if brief.degraded:
        print(f"  degraded     : {brief.degraded}")

    print("\n== INVESTIGATION (live feed) ==")
    investigator = get_investigator()
    final_rca = None
    for event in investigator.investigate(brief):
        if event.type == "rca":
            final_rca = event.rca
        elif event.type == "error":
            print(f"  ERROR: {event.text}")
        else:
            bits = [b for b in (event.name, event.status, event.text) if b]
            print(f"  [{event.type}] " + " ".join(bits))

    print("\n== RCA ==")
    if final_rca is None:
        print("  no RCA produced")
        return 1
    print(f"  generated_by : {final_rca.generated_by.value}")
    print(f"  summary      : {final_rca.summary}")
    print(f"  confidence   : {final_rca.confidence.score}")
    print(f"  action       : {final_rca.recommended_action.action.value}")
    print(f"  blast radius : {final_rca.blast_radius.if_rolled_back}")
    for t in final_rca.tests.executed:
        print(f"  test         : {t.name} current={t.result_on_current.value} revert={t.result_on_revert.value}")
    print("\n  RCA validates against causa.contract.RCA (it is an RCA instance).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
