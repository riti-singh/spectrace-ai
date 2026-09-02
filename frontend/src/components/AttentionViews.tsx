import { AlertOctagon, ArrowUpRight, CheckCircle2, FileWarning } from "lucide-react";
import type { Artifact, DashboardData, Risk } from "../types";

export function AttentionViews({ data, onSelect }: { data: DashboardData; onSelect: (artifact: Artifact) => void }) {
  const testedRequirementIds = new Set(data.tests.flatMap((item) => item.requirement_ids));
  const unverifiedRisks = data.risks.filter((risk) => !data.requirements.some((req) => req.risk_ids.includes(risk.id) && testedRequirementIds.has(req.id)));
  return <section className="attention-grid" aria-labelledby="attention-heading">
    <div className="section-heading full"><div><span className="eyebrow">Coverage attention</span><h2 id="attention-heading">Close the evidence gaps</h2></div><p>Derived from current requirement-to-test and requirement-to-risk links.</p></div>
    <AttentionCard title="Uncovered requirements" count={data.uncovered.length} icon={FileWarning} tone="amber" empty="Every requirement has at least one linked test." items={data.uncovered} onSelect={onSelect} />
    <AttentionCard title="Unverified risks" count={unverifiedRisks.length} icon={AlertOctagon} tone="rose" empty="Every risk has a requirement-to-test verification path." items={unverifiedRisks} onSelect={onSelect} />
  </section>;
}

function AttentionCard({ title, count, icon: Icon, tone, empty, items, onSelect }: { title: string; count: number; icon: typeof FileWarning; tone: string; empty: string; items: Artifact[]; onSelect: (artifact: Artifact) => void }) {
  return <article className={`attention-card attention-${tone}`}><header><span><Icon size={18} /></span><div><h3>{title}</h3><p>{count} item{count === 1 ? "" : "s"} need review</p></div><strong>{count}</strong></header>
    <div className="attention-list">{items.length === 0 ? <div className="attention-empty"><CheckCircle2 />{empty}</div> : items.slice(0, 5).map((item) => <button key={item.id} aria-label={`${item.id} ${"name" in item ? item.name : item.title}`} onClick={() => onSelect(item)}><span><small>{item.id}</small><strong>{"name" in item ? item.name : item.title}</strong></span><ArrowUpRight size={15} /></button>)}</div>
  </article>;
}
