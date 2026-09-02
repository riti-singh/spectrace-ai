import { FlaskConical } from "lucide-react";
import type { EvaluationSummary as Evaluation } from "../types";

const labels = { precision_at_k: "Precision", recall_at_k: "Recall", mrr: "MRR", ndcg_at_k: "nDCG" } as const;

export function EvaluationSummary({ evaluation }: { evaluation: Evaluation }) {
  return <section className="evaluation-card" aria-labelledby="evaluation-heading">
    <div className="section-heading"><div><span className="eyebrow">Retrieval quality</span><h2 id="evaluation-heading">Evaluation snapshot</h2><p>{evaluation.query_count} judged synthetic queries · K={evaluation.k} · deterministic local encoder</p></div><span className="evaluation-icon"><FlaskConical /></span></div>
    <div className="evaluation-table" role="table" aria-label="Retrieval evaluation metrics">
      <div className="evaluation-row evaluation-header" role="row"><span>Mode</span>{Object.values(labels).map((label) => <span key={label}>{label}{label === "MRR" ? "" : `@${evaluation.k}`}</span>)}</div>
      {evaluation.metrics.map((metric) => <div className={`evaluation-row mode-${metric.mode}`} role="row" key={metric.mode}><strong>{metric.mode}</strong>{(Object.keys(labels) as Array<keyof typeof labels>).map((key) => <span key={key}><i style={{ width: `${metric[key] * 100}%` }} /><b>{metric[key].toFixed(3)}</b></span>)}</div>)}
    </div>
    <p className="benchmark-note">{evaluation.characterization}</p>
  </section>;
}
