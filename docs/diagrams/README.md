# Causa architecture diagrams (FigJam / Figma)

These Mermaid sources explain the [README](../../README.md) and
[architecture.md](../../architecture.md). Each file is ready to paste into a
FigJam board.

## Import into FigJam

1. Open [Figma](https://www.figma.com) and create a new **FigJam** file (or open
   an existing board).
2. Copy the contents of any `.mmd` file below.
3. Paste onto the canvas — FigJam renders Mermaid syntax as an editable diagram.
4. Arrange the six diagrams in a grid (suggested order left-to-right, top-to-bottom).

Alternatively, with the **Figma MCP** connected in Cursor Desktop, an agent can
call `generate_diagram` on each file and place them in one board automatically.

## Diagram index

| File | What it explains |
|------|------------------|
| [01-system-overview.mmd](./01-system-overview.mmd) | End-to-end system: observability stack, Causa platform, MCP subprocesses, investigators |
| [02-division-of-labour.mmd](./02-division-of-labour.mmd) | Cheap triage vs expensive investigation; brief-in / contract-out |
| [03-alert-to-rca-sequence.mmd](./03-alert-to-rca-sequence.mmd) | Sequence from metrics to validated RCA in the console |
| [04-repo-layout.mmd](./04-repo-layout.mmd) | Repository layout table from the README |
| [05-service-topology.mmd](./05-service-topology.mmd) | `topology.yaml` dependency graph and blast radius |
| [06-demo-flow.mmd](./06-demo-flow.mmd) | Demo storyline: break, alert, investigate, fix |
| [07-production-seams.mmd](./07-production-seams.mmd) | Prototype vs production swap points (TopologySource, Investigator, llm) |

## Suggested FigJam board layout

```
+---------------------------+---------------------------+
| 01 System Overview        | 02 Division of Labour     |
+---------------------------+---------------------------+
| 03 Alert-to-RCA Sequence  | 04 Repo Layout            |
+---------------------------+---------------------------+
| 05 Service Topology       | 06 Demo Flow              |
+---------------------------+---------------------------+
| 07 Production Seams (full width)                      |
+-------------------------------------------------------+
```

## Key URLs (from README)

- Console: http://localhost:8501
- Prometheus alerts: http://localhost:9090/alerts
- Alertmanager: http://localhost:9093
- Grafana payments dashboard: http://localhost:3000/d/payments/payments
- Jaeger: http://localhost:16686
