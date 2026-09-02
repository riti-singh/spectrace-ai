import { Braces, Combine, Network, WholeWord } from "lucide-react";
import type { RetrievalMode } from "../types";

const modes = [
  { id: "lexical" as const, label: "Lexical", detail: "Exact terms", icon: WholeWord },
  { id: "semantic" as const, label: "Semantic", detail: "Concept match", icon: Braces },
  { id: "graph" as const, label: "Graph", detail: "Relationships", icon: Network },
  { id: "hybrid" as const, label: "Hybrid", detail: "Fused rank", icon: Combine }
];

export function ModeSelector({ value, onChange }: { value: RetrievalMode; onChange: (mode: RetrievalMode) => void }) {
  return (
    <div className="mode-selector" role="radiogroup" aria-label="Retrieval mode">
      {modes.map(({ id, label, detail, icon: Icon }) => (
        <button key={id} role="radio" aria-checked={value === id} className={value === id ? "active" : ""} onClick={() => onChange(id)}>
          <Icon size={16} /><span><strong>{label}</strong><small>{detail}</small></span>
        </button>
      ))}
    </div>
  );
}
