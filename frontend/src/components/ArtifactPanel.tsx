import { Box, CheckCircle2, FileText, ShieldAlert, TestTube2, X } from "lucide-react";
import type { Artifact, Component, DashboardData, Requirement, Risk, TestCase } from "../types";

function entityType(artifact: Artifact): "Requirement" | "Component" | "Risk" | "Test case" {
  if (artifact.id.startsWith("REQ")) return "Requirement";
  if (artifact.id.startsWith("CMP")) return "Component";
  if (artifact.id.startsWith("RSK")) return "Risk";
  return "Test case";
}

export function ArtifactPanel({ artifact, data, onClose, onSelect }: { artifact: Artifact | null; data: DashboardData; onClose: () => void; onSelect: (artifact: Artifact) => void }) {
  if (!artifact) return null;
  const type = entityType(artifact);
  const requirement = type === "Requirement" ? artifact as Requirement : null;
  const linkedRequirements = requirement ? [requirement] : data.requirements.filter((item) => {
    if (type === "Component") return item.component_ids.includes(artifact.id);
    if (type === "Risk") return item.risk_ids.includes(artifact.id);
    return (artifact as TestCase).requirement_ids.includes(item.id);
  });
  const components = requirement ? data.components.filter((item) => requirement.component_ids.includes(item.id)) : type === "Component" ? [artifact as Component] : [];
  const risks = requirement ? data.risks.filter((item) => requirement.risk_ids.includes(item.id)) : type === "Risk" ? [artifact as Risk] : [];
  const tests = data.tests.filter((item) => linkedRequirements.some((req) => item.requirement_ids.includes(req.id)));
  const title = "name" in artifact ? artifact.name : artifact.title;
  const body = "normative_text" in artifact ? artifact.normative_text : "objective" in artifact ? artifact.objective : artifact.description;
  return <div className="panel-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="artifact-panel" role="dialog" aria-modal="true" aria-labelledby="artifact-title">
      <div className="panel-header"><div><span className="artifact-meta"><span className={`type-dot type-${type.toLowerCase().replace(" ", "")}`} />{type} · {artifact.id}</span><h2 id="artifact-title">{title}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close artifact details"><X /></button></div>
      <div className="panel-body"><p className="normative-text">{body}</p>
        {requirement && <div className="detail-facts"><div><small>Priority</small><strong className={`status-${requirement.priority}`}>{requirement.priority}</strong></div><div><small>Type</small><strong>{requirement.requirement_type}</strong></div><div><small>Verification</small><strong>{requirement.verification_method}</strong></div><div><small>Source</small><strong>{requirement.source_section}</strong></div></div>}
        <RelationGroup icon={FileText} title="Requirements" items={linkedRequirements} onSelect={onSelect} />
        <RelationGroup icon={Box} title="Components" items={components} onSelect={onSelect} />
        <RelationGroup icon={ShieldAlert} title="Risks" items={risks} onSelect={onSelect} />
        <RelationGroup icon={TestTube2} title="Verification tests" items={tests} onSelect={onSelect} />
      </div>
      <div className="panel-footer"><CheckCircle2 size={16} /><span>Relationships are resolved from the validated backend dataset.</span></div>
    </aside>
  </div>;
}

function RelationGroup({ icon: Icon, title, items, onSelect }: { icon: typeof FileText; title: string; items: Artifact[]; onSelect: (artifact: Artifact) => void }) {
  return <section className="relation-group"><h3><Icon size={16} />{title}<span>{items.length}</span></h3>{items.length === 0 ? <p className="relation-empty">No linked artifacts</p> : items.map((item) => <button key={item.id} onClick={() => onSelect(item)}><span>{item.id}</span><strong>{"name" in item ? item.name : item.title}</strong></button>)}</section>;
}
