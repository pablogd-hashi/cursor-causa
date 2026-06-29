"""Causa console — the three-pane investigation view (Phase 5).

LEFT: alerts / investigations (click to select; a button simulates an alert).
CENTRE: the incident picture + the live investigation feed (the streamed events).
RIGHT: the RCA — confidence, evidence, code path, telemetry, blast radius,
recommended action, tests, and an optional "Open Draft PR" button.

It reads everything from the Causa API (CAUSA_API_URL); it holds no state of its
own. Deep-links are rendered as clickable links straight into Grafana/Jaeger/GitHub.
"""

from __future__ import annotations

import os
import time

import requests
import streamlit as st

API = os.environ.get("CAUSA_API_URL", "http://localhost:8000")
RUNNING = {"queued", "triaging", "investigating"}

st.set_page_config(page_title="Causa", layout="wide")


def api_get(path: str):
    try:
        r = requests.get(f"{API}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.session_state["api_error"] = str(exc)
        return None


def api_post(path: str, body: dict | None = None):
    try:
        r = requests.post(f"{API}{path}", json=body or {}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.error(f"API error: {exc}")
        return None


st.title("Causa — incident investigation console")
st.caption(f"API: {API}")

left, centre, right = st.columns([1, 2, 2], gap="large")

# --- LEFT: alerts -----------------------------------------------------------
with left:
    st.subheader("Alerts")
    if st.button("Simulate payments alert", use_container_width=True):
        res = api_post("/investigations")
        if res:
            st.session_state["selected"] = res["id"]
    auto = st.checkbox("Live refresh", value=True)

    investigations = api_get("/investigations") or []
    for rec in investigations:
        flag = "running" if rec["status"] in RUNNING else rec["status"]
        if st.button(
            f"{rec['alertname']}\n({flag})", key=rec["id"], use_container_width=True
        ):
            st.session_state["selected"] = rec["id"]
    if st.session_state.get("api_error"):
        st.caption(f"last API error: {st.session_state['api_error']}")

selected = st.session_state.get("selected")
record = api_get(f"/investigations/{selected}") if selected else None

# --- CENTRE: incident picture + live feed -----------------------------------
with centre:
    st.subheader("Incident")
    if not record:
        st.info("Select an alert on the left, or simulate one.")
    else:
        st.markdown(f"**{record['alertname']}** — status `{record['status']}`")
        brief = record.get("brief")
        if brief:
            st.caption(
                f"window {brief['window']['start']} -> {brief['window']['end']}"
            )
            if brief["candidate_changes"]:
                st.markdown("**Candidate changes**")
                for c in brief["candidate_changes"]:
                    st.markdown(f"- [{c['ref']}]({c['url']}) {c['title']}")
            if brief.get("degraded"):
                st.warning("Triage degraded: " + "; ".join(brief["degraded"]))

        st.markdown("**Live investigation feed**")
        feed = st.container(height=360)
        for e in record.get("events", []):
            if e["type"] == "rca":
                feed.markdown("RCA returned and validated against the contract.")
                continue
            bits = [b for b in (e.get("name"), e.get("status"), e.get("text")) if b]
            feed.markdown(f"`{e['type']}` " + " ".join(bits))
        if record["status"] == "failed" and record.get("error"):
            st.error(record["error"])

# --- RIGHT: the RCA ---------------------------------------------------------
with right:
    st.subheader("Root cause analysis")
    rca = record.get("rca") if record else None
    if not rca:
        st.info("The RCA appears here once the investigation completes.")
    else:
        c1, c2 = st.columns(2)
        c1.metric("Confidence", f"{rca['confidence']['score']:.2f}")
        c2.metric("Recommended", rca["recommended_action"]["action"])
        st.write(rca["summary"])
        st.caption(rca["confidence"]["rationale"])

        with st.expander("Recommended action", expanded=True):
            st.write(rca["recommended_action"]["reasoning"])

        with st.expander("Blast radius"):
            st.write("Affected if rolled back: " + ", ".join(rca["blast_radius"]["if_rolled_back"]))
            st.caption(f"source: {rca['blast_radius']['graph_source']}")
            st.caption(rca["blast_radius"]["note"])

        with st.expander("Code path"):
            st.write(rca["code_path"]["summary"])
            for n in rca["code_path"]["nodes"]:
                st.markdown(f"- `{n['file']}` :: `{n.get('function') or ''}` — {n.get('note') or ''}")

        with st.expander("Tests"):
            for t in rca["tests"]["executed"]:
                st.markdown(
                    f"- `{t['name']}` — current **{t['result_on_current']}**, "
                    f"revert **{t['result_on_revert']}**"
                )

        with st.expander("Supporting telemetry"):
            for s in rca["supporting_telemetry"]:
                link = f" — [panel]({s['deeplink']})" if s.get("deeplink") else ""
                st.markdown(f"- **{s['signal']}**: {s['observation']}{link}")

        with st.expander("Evidence"):
            for ev in rca["evidence"]:
                link = f" — [link]({ev['deeplink']})" if ev.get("deeplink") else ""
                st.markdown(f"- `{ev['source']}` {ev['detail']}{link}")

        if rca.get("draft_pr"):
            st.link_button("Open Draft PR", rca["draft_pr"]["url"])
        else:
            st.caption("No draft PR — the RCA is the product; a PR is opt-in.")

# Auto-refresh only while an investigation is still running.
if record and record["status"] in RUNNING and st.session_state.get("selected"):
    if auto:
        time.sleep(1.5)
        st.rerun()
