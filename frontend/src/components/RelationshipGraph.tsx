import { Maximize2, MousePointer2 } from "lucide-react";
import { useMemo, useState } from "react";
import type { Artifact, DashboardData, EntityType } from "../types";

interface GraphNode { id: string; label: string; type: EntityType; x: number; y: number; artifact: Artifact }
interface GraphEdge { source: string; target: string; label: string }

function graphFor(data: DashboardData, focusId: string): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const focus = data.requirements.find((item) => item.id === focusId) ?? data.requirements[0];
  if (!focus) return { nodes: [], edges: [] };
  const relatedRequirements = data.requirements.filter((item) => focus.dependency_ids.includes(item.id) || item.dependency_ids.includes(focus.id)).slice(0, 4);
  const relatedComponents = data.components.filter((item) => focus.component_ids.includes(item.id)).slice(0, 3);
  const relatedRisks = data.risks.filter((item) => focus.risk_ids.includes(item.id)).slice(0, 2);
  const relatedTests = data.tests.filter((item) => item.requirement_ids.includes(focus.id)).slice(0, 2);
  const artifacts: Array<{ artifact: Artifact; type: EntityType; label: string }> = [
    { artifact: focus, type: "Requirement", label: focus.title },
    ...relatedRequirements.map((artifact) => ({ artifact, type: "Requirement" as const, label: artifact.title })),
    ...relatedComponents.map((artifact) => ({ artifact, type: "Component" as const, label: artifact.name })),
    ...relatedRisks.map((artifact) => ({ artifact, type: "Risk" as const, label: artifact.title })),
    ...relatedTests.map((artifact) => ({ artifact, type: "TestCase" as const, label: artifact.title }))
  ];
  const nodes = artifacts.map((entry, index) => {
    if (index === 0) return { ...entry, id: entry.artifact.id, x: 360, y: 210 };
    const angle = ((index - 1) / Math.max(1, artifacts.length - 1)) * Math.PI * 2 - Math.PI / 2;
    return { ...entry, id: entry.artifact.id, x: 360 + Math.cos(angle) * 245, y: 210 + Math.sin(angle) * 145 };
  });
  const edges: GraphEdge[] = nodes.slice(1).map((node) => ({
    source: focus.id,
    target: node.id,
    label: node.type === "Component" ? "APPLIES TO" : node.type === "Risk" ? "ADDRESSES" : node.type === "TestCase" ? "VERIFIED BY" : "DEPENDS ON"
  }));
  return { nodes, edges };
}

export function RelationshipGraph({ data, selectedId, onSelect }: { data: DashboardData; selectedId: string; onSelect: (artifact: Artifact) => void }) {
  const [focusId, setFocusId] = useState(selectedId.startsWith("REQ-") ? selectedId : "REQ-003");
  const [typeFilter, setTypeFilter] = useState<EntityType | "All">("All");
  const graph = useMemo(() => graphFor(data, focusId), [data, focusId]);
  const visibleIds = new Set(graph.nodes.filter((node, index) => index === 0 || typeFilter === "All" || node.type === typeFilter).map((node) => node.id));
  const nodes = graph.nodes.filter((node) => visibleIds.has(node.id));
  const edges = graph.edges.filter((edge) => visibleIds.has(edge.target));

  return (
    <section className="graph-card" aria-labelledby="graph-heading">
      <div className="card-heading"><div><span className="eyebrow">Relationship explorer</span><h2 id="graph-heading">System trace graph</h2></div><button className="icon-button" aria-label="Fit graph to view"><Maximize2 size={17} /></button></div>
      <div className="graph-toolbar">
        <span><MousePointer2 size={14} /> Select a node to inspect</span>
        <div>{(["All", "Requirement", "Component", "Risk", "TestCase"] as const).map((type) => <button className={typeFilter === type ? "active" : ""} key={type} onClick={() => setTypeFilter(type)}>{type === "TestCase" ? "Tests" : type}</button>)}</div>
      </div>
      <div className="graph-canvas">
        <svg viewBox="0 0 720 420" role="img" aria-label={`Trace relationships centered on ${focusId}`}>
          <defs><filter id="glow"><feGaussianBlur stdDeviation="5" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter></defs>
          {edges.map((edge) => {
            const source = graph.nodes.find((node) => node.id === edge.source)!;
            const target = graph.nodes.find((node) => node.id === edge.target)!;
            return <g key={`${edge.source}-${edge.target}`}><line className="graph-edge" x1={source.x} y1={source.y} x2={target.x} y2={target.y} /><text className="edge-label" x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 7}>{edge.label}</text></g>;
          })}
          {nodes.map((node) => <g className={`graph-node node-${node.type.toLowerCase()} ${node.id === focusId ? "focus" : ""}`} key={node.id} transform={`translate(${node.x}, ${node.y})`} role="button" tabIndex={0} aria-label={`${node.type} ${node.id}: ${node.label}`} onClick={() => { onSelect(node.artifact); if (node.type === "Requirement") setFocusId(node.id); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(node.artifact); if (node.type === "Requirement") setFocusId(node.id); } }}>
            <circle r={node.id === focusId ? 34 : 27} /><text className="node-id" textAnchor="middle" y="4">{node.id}</text><text className="node-label" textAnchor="middle" y={node.id === focusId ? 52 : 44}>{node.label.length > 26 ? `${node.label.slice(0, 24)}…` : node.label}</text>
          </g>)}
        </svg>
      </div>
      <div className="graph-legend">{[["Requirement", "mint"], ["Component", "blue"], ["Risk", "rose"], ["Test case", "amber"]].map(([label, tone]) => <span key={label}><i className={`legend-${tone}`} />{label}</span>)}<strong>{nodes.length} nodes · {edges.length} relationships</strong></div>
    </section>
  );
}
