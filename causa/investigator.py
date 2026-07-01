"""The investigator seam: brief in, a stream of events out, ending in a validated
RCA.

Two implementations behind one interface:
- ``MockInvestigator`` replays a realistic investigation from a fixture, so the
  pipeline and console run with no live Cursor calls. The demo's reliability
  rests on this.
- ``CursorInvestigator`` shells out to the Node ``sdk-runner`` (the official
  ``@cursor/sdk``), forwarding the agent's streamed events and validating the
  final RCA against the contract.

Both yield ``InvestigationEvent``s. The terminal event is either ``type="rca"``
(carrying a validated ``RCA``) or ``type="error"``.
"""

from __future__ import annotations

import json
import os
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, ValidationError

from .brief import InvestigationBrief
from .contract import RCA, GeneratedBy

_ROOT = Path(__file__).resolve().parent.parent


class InvestigationEvent(BaseModel):
    """One item in the live feed. ``rca`` is set only on the terminal event."""

    type: str  # status | thinking | tool_call | assistant | rca | error
    name: str | None = None  # tool name, for tool_call
    status: str | None = None
    text: str | None = None
    rca: RCA | None = None


class Investigator(ABC):
    @abstractmethod
    def investigate(self, brief: InvestigationBrief) -> Iterator[InvestigationEvent]:
        ...


class MockInvestigator(Investigator):
    """Replays a canned-but-realistic investigation from a fixture RCA."""

    def __init__(self, fixture_path: str | Path | None = None) -> None:
        self.fixture = Path(fixture_path or _ROOT / "fixtures" / "rca_payments.json")

    def investigate(self, brief: InvestigationBrief) -> Iterator[InvestigationEvent]:
        yield InvestigationEvent(type="status", status="cloning repository")
        for change in brief.candidate_changes:
            yield InvestigationEvent(
                type="thinking",
                text=f"Considering candidate {change.ref}: {change.title}",
            )
        for path in ("demo-app/payments/api.py", "demo-app/payments/pool.py"):
            yield InvestigationEvent(type="tool_call", name="read_file", status=path)
        yield InvestigationEvent(
            type="tool_call", name="run_test", status="test_pool_exhaustion (current)"
        )
        yield InvestigationEvent(
            type="assistant",
            text="test_pool_exhaustion fails on current code (pool=10).",
        )
        yield InvestigationEvent(
            type="tool_call", name="run_test", status="test_pool_exhaustion (reverted)"
        )
        yield InvestigationEvent(
            type="assistant",
            text="test_pool_exhaustion passes when the pool is restored (pool=50).",
        )

        try:
            rca = RCA.model_validate_json(self.fixture.read_text())
        except (OSError, ValidationError) as exc:
            yield InvestigationEvent(type="error", text=f"fixture invalid: {exc}")
            return
        rca.generated_by = GeneratedBy.mock
        rca.investigation_id = brief.investigation_id
        rca.service = brief.service
        rca.blast_radius.if_rolled_back = brief.blast_radius_hint
        rca.blast_radius.graph_source = brief.blast_radius_graph_source
        yield InvestigationEvent(type="rca", rca=rca)


class CursorInvestigator(Investigator):
    """Runs a real Cursor cloud agent via the Node sdk-runner and streams it back.

    The runner emits normalised JSONL on stdout (one event per line), ending with
    a ``{"type":"rca","data":{...}}`` line. The brief is passed to the runner on
    stdin. We validate the final RCA against the contract here — the trust
    boundary — and surface validation failures as an error event."""

    def __init__(
        self,
        runner_dir: str | Path | None = None,
        repo_url: str | None = None,
        repo_ref: str | None = None,
        model: str | None = None,
    ) -> None:
        self.runner_dir = Path(runner_dir or _ROOT / "sdk-runner")
        self.repo_url = repo_url or os.environ.get(
            "CURSOR_TARGET_REPO", "https://github.com/pablogd-hashi/cursor-causa"
        )
        self.repo_ref = repo_ref or os.environ.get("CURSOR_TARGET_REF", "main")
        self.model = model or os.environ.get("CURSOR_MODEL", "composer-2")

    def investigate(self, brief: InvestigationBrief) -> Iterator[InvestigationEvent]:
        env = {
            **os.environ,
            "CURSOR_TARGET_REPO": self.repo_url,
            "CURSOR_TARGET_REF": self.repo_ref,
            "CURSOR_MODEL": self.model,
        }
        try:
            proc = subprocess.Popen(
                ["node", "run.mjs"],
                cwd=self.runner_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                env=env,
            )
        except FileNotFoundError as exc:
            yield InvestigationEvent(type="error", text=f"node/runner not found: {exc}")
            return

        assert proc.stdin and proc.stdout
        # Prompt construction lives in one place (brief.to_agent_prompt); the
        # runner is a generic launcher that just receives the finished prompt.
        schema = (_ROOT / "schema" / "rca.schema.json").read_text()
        proc.stdin.write(json.dumps({"prompt": brief.to_agent_prompt(schema)}))
        proc.stdin.close()

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if evt.get("type") == "rca":
                try:
                    rca = RCA.model_validate(evt["data"])
                except ValidationError as exc:
                    yield InvestigationEvent(
                        type="error", text=f"agent RCA failed contract validation: {exc}"
                    )
                    continue
                rca.generated_by = GeneratedBy.cursor
                yield InvestigationEvent(type="rca", rca=rca)
            else:
                yield InvestigationEvent(
                    type=evt.get("type", "status"),
                    name=evt.get("name"),
                    status=evt.get("status"),
                    text=evt.get("text"),
                )
        proc.wait()


def get_investigator() -> Investigator:
    """``CAUSA_INVESTIGATOR=cursor`` for the live agent; mock by default."""
    if os.environ.get("CAUSA_INVESTIGATOR", "mock").lower() == "cursor":
        return CursorInvestigator()
    return MockInvestigator()
