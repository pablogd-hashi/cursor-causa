"""Service dependency graph behind blast-radius reasoning.

The seam: ``TopologySource`` has a single method, ``dependents()``. The prototype
implements it by reading the declared ``topology.yaml``; with ``CAUSA_TOPOLOGY=consul``
a live graph is derived from mesh trace metrics (servicegraph). Either way the
brief assembler and orchestrator see the same interface.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent


class TopologySource(ABC):
    @property
    def graph_source(self) -> str:
        """Provenance string recorded on the brief / RCA blast radius."""
        return "declared:topology.yaml"

    @abstractmethod
    def dependents(self, service: str) -> list[str]:
        """Return every service that depends on ``service``, directly or
        transitively — i.e. who would be affected if ``service`` were rolled
        back. This is the blast radius."""


class DeclaredTopologySource(TopologySource):
    """Reads a declared dependency graph from a YAML file shaped like
    ``{services: {name: {depends_on: [...]}}}``."""

    def __init__(self, path: str | Path) -> None:
        data = yaml.safe_load(Path(path).read_text()) or {}
        self._services: dict[str, dict] = data.get("services", {})

    def _direct_dependents(self, service: str) -> list[str]:
        return [
            name
            for name, meta in self._services.items()
            if service in (meta or {}).get("depends_on", [])
        ]

    def dependents(self, service: str) -> list[str]:
        # Breadth-first transitive closure over the reverse-dependency edges.
        seen: set[str] = set()
        stack = [service]
        while stack:
            current = stack.pop()
            for dependent in self._direct_dependents(current):
                if dependent not in seen:
                    seen.add(dependent)
                    stack.append(dependent)
        return sorted(seen)


def get_topology(path: str | Path | None = None) -> TopologySource:
    """``CAUSA_TOPOLOGY=declared`` (default) or ``consul`` for live servicegraph."""
    declared_path = Path(path or _ROOT / "topology.yaml")
    fallback = DeclaredTopologySource(declared_path)
    mode = os.environ.get("CAUSA_TOPOLOGY", "declared").lower()
    if mode == "consul":
        from .topology_consul import ConsulTopologySource

        return ConsulTopologySource(fallback=fallback)
    return fallback
