"""Live topology from the mesh service graph (Prometheus servicegraph metrics)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from .topology import DeclaredTopologySource, TopologySource

log = logging.getLogger(__name__)

_GRAPH_SOURCE_LIVE = "consul-mesh (servicegraph)"
_GRAPH_SOURCE_FALLBACK = "declared:topology.yaml"


class ConsulTopologySource(TopologySource):
    """Derives blast radius from ``traces_service_graph_request_total`` edges.

    Queries Prometheus for direct dependents (``client`` labels where
    ``server="<svc>"``), then applies the same breadth-first transitive closure
    as ``DeclaredTopologySource``. On any Prometheus error, degrades to the
    declared fallback graph.
    """

    def __init__(
        self,
        *,
        fallback: DeclaredTopologySource,
        prometheus_url: str | None = None,
        metric: str = "traces_service_graph_request_total",
    ) -> None:
        self._fallback = fallback
        self._prometheus_url = (
            prometheus_url or os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
        ).rstrip("/")
        self._metric = metric
        self._live = True

    @property
    def graph_source(self) -> str:
        return _GRAPH_SOURCE_LIVE if self._live else _GRAPH_SOURCE_FALLBACK

    def _direct_dependents(self, service: str) -> list[str]:
        query = f'{self._metric}{{server="{service}"}}'
        url = (
            f"{self._prometheus_url}/api/v1/query?"
            + urllib.parse.urlencode({"query": query})
        )
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                payload = json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"prometheus query failed: {exc}") from exc

        if payload.get("status") != "success":
            raise RuntimeError(f"prometheus error: {payload.get('error', payload)}")

        clients: set[str] = set()
        for series in payload.get("data", {}).get("result", []):
            client = (series.get("metric") or {}).get("client")
            if client:
                clients.add(client)
        return sorted(clients)

    def dependents(self, service: str) -> list[str]:
        try:
            seen: set[str] = set()
            stack = [service]
            while stack:
                current = stack.pop()
                for dependent in self._direct_dependents(current):
                    if dependent not in seen:
                        seen.add(dependent)
                        stack.append(dependent)
            return sorted(seen)
        except Exception as exc:
            log.warning("ConsulTopologySource degraded to declared graph: %s", exc)
            self._live = False
            return self._fallback.dependents(service)
