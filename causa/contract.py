"""The RCA contract: the strict schema the investigator returns and Causa renders.

This module is the trust boundary of the whole system. The Cursor Cloud Agent is
prompted to return JSON matching ``RCA`` exactly; Causa validates that JSON against
this model before anything is stored or rendered. Invalid output is rejected and
surfaced as an error rather than displayed as if it were a real finding.

Design note (for a HashiCorp infra reader): this is "brief-in / contract-out".
A loose "investigate this" prompt produces unusable, unrepeatable output. By
pinning the *shape* of the answer here and generating a JSON Schema from it
(``schema/rca.schema.json``), we can hand the agent an exact target and fail
closed when it deviates. Pydantic v2 gives us both runtime validation and the
JSON Schema export from one definition.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EvidenceSource(str, Enum):
    """Where a piece of evidence came from. Drives the icon/colour in the console."""

    grafana = "grafana"
    github = "github"
    code = "code"
    test = "test"


class TimelineKind(str, Enum):
    """The type of a timeline event, so the console can style the incident timeline."""

    alert = "alert"
    deploy = "deploy"
    pr = "pr"
    metric_inflection = "metric_inflection"
    note = "note"


class Action(str, Enum):
    """The recommended remediation. ``staged_rollout`` exists because a blunt
    rollback can have a wide blast radius (see ``BlastRadius``)."""

    rollback = "rollback"
    forward_fix = "forward_fix"
    staged_rollout = "staged_rollout"
    investigate_more = "investigate_more"


class TestResult(str, Enum):
    """Outcome of a single test execution in the agent's VM."""

    passed = "pass"
    failed = "fail"
    skipped = "skipped"
    error = "error"


class GeneratedBy(str, Enum):
    """Which investigator produced this RCA. ``mock`` keeps the demo reliable
    without a live Cursor run; ``cursor`` is a real Cloud Agent investigation."""

    mock = "mock"
    cursor = "cursor"


class Confidence(BaseModel):
    """A bounded confidence score plus a short human rationale. The score is
    constrained to 0..1 so the console can render it as a gauge without clamping."""

    score: float = Field(ge=0.0, le=1.0)
    rationale: str


class TimelineEvent(BaseModel):
    """One ordered event on the incident timeline (Causa's own synthesis)."""

    timestamp: str  # ISO-8601
    kind: TimelineKind
    label: str
    deeplink: str | None = None


class Evidence(BaseModel):
    """A single supporting fact, tagged by source and optionally deep-linked
    into Grafana/Jaeger/GitHub so the engineer can verify it in one click."""

    source: EvidenceSource
    detail: str
    deeplink: str | None = None


class CodePathNode(BaseModel):
    """One node in the implicated execution path. ``note`` records *why* this
    file/function participates, which is the whole point of the Cursor demo."""

    file: str
    function: str | None = None
    note: str | None = None


class CodePath(BaseModel):
    """The implicated execution path: a one-line summary plus the ordered nodes."""

    summary: str
    nodes: list[CodePathNode]


class TelemetrySignal(BaseModel):
    """A metric or log signal that supports the conclusion, with the query that
    produced it and a deeplink to the exact panel/trace. ``deeplink`` is required
    here (unlike on ``Evidence``) because supporting telemetry must be verifiable."""

    signal: str  # e.g. "payments_pool_inuse"
    query: str | None = None  # PromQL / LogQL
    observation: str
    deeplink: str


class BlastRadius(BaseModel):
    """Downstream impact of rolling back. ``graph_source`` records provenance so
    the demo can show this came from the declared topology now, and would come
    from Consul in production (the seam is deliberate)."""

    if_rolled_back: list[str]
    graph_source: str  # "declared:topology.yaml" | "consul-mcp"
    note: str


class RecommendedAction(BaseModel):
    """The recommendation plus its reasoning, e.g. 'rollback undoes Checkout and
    Refunds; recommend a staged rollout instead.'"""

    action: Action
    reasoning: str


class TestExecution(BaseModel):
    """A test the agent actually ran, on current code and on reverted code. The
    current-vs-revert pair is what turns a hypothesis into a demonstrated cause."""

    name: str
    result_on_current: TestResult
    result_on_revert: TestResult


class Tests(BaseModel):
    """Tests the agent recommends, and the ones it executed with their results."""

    recommended: list[str]
    executed: list[TestExecution]


class DraftPR(BaseModel):
    """An optional draft PR. Only ever populated when the engineer approves a fix;
    Causa never opens this automatically."""

    url: str
    summary: str


class RCA(BaseModel):
    """The root-cause-analysis contract. This is the product of an investigation.

    ``draft_pr`` is optional and only present when a fix has been approved — the
    RCA stands on its own without it.
    """

    schema_version: str = "1.0"
    investigation_id: str
    service: str = "payments"
    generated_by: GeneratedBy
    summary: str  # one-line headline
    confidence: Confidence
    timeline: list[TimelineEvent]
    evidence: list[Evidence]
    code_path: CodePath
    supporting_telemetry: list[TelemetrySignal]
    blast_radius: BlastRadius
    recommended_action: RecommendedAction
    tests: Tests
    draft_pr: DraftPR | None = None


if __name__ == "__main__":
    # Convenience: ``python -m causa.contract`` prints the JSON Schema to stdout.
    import json

    print(json.dumps(RCA.model_json_schema(), indent=2))
