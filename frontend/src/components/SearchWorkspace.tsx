import { ChevronDown, Search, Sparkles } from "lucide-react";
import { FormEvent, useState } from "react";
import { ApiError, searchTraceability } from "../api/client";
import type { Artifact, RetrievalMode, RetrievalResponse } from "../types";
import { EmptyState, ErrorState } from "./StateView";
import { ModeSelector } from "./ModeSelector";

const starterQueries = ["thermal protection verification", "tampered firmware recovery", "REQ-002 downstream impact"];

export function SearchWorkspace({ onSelect }: { onSelect: (artifact: Artifact) => void }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<RetrievalMode>("hybrid");
  const [response, setResponse] = useState<RetrievalResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event?: FormEvent, nextQuery = query) {
    event?.preventDefault();
    const normalized = nextQuery.trim();
    if (normalized.length < 2) return;
    setQuery(normalized);
    setLoading(true);
    setError(null);
    try {
      setResponse(await searchTraceability(normalized, mode));
    } catch (reason) {
      const apiError = reason as ApiError;
      setResponse(null);
      setError(apiError.code === "neo4j_backend_required"
        ? "Retrieval needs the Neo4j-backed local stack. Start the documented Docker Compose workflow to enable all four modes."
        : apiError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="search-workspace" aria-labelledby="search-heading">
      <div className="section-heading">
        <div><span className="eyebrow">Trace intelligence</span><h2 id="search-heading">Search across the system</h2><p>Query requirements, components, risks, and verification evidence with a transparent retrieval path.</p></div>
        <span className="live-chip"><span /> deterministic index</span>
      </div>
      <form className="search-form" onSubmit={submit}>
        <Search aria-hidden="true" />
        <label className="sr-only" htmlFor="trace-search">Traceability query</label>
        <input id="trace-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ask about a requirement, failure mode, or verification path…" />
        <button className="button primary" disabled={loading || query.trim().length < 2}>{loading ? "Searching…" : "Search"}<Sparkles size={15} /></button>
      </form>
      <div className="query-row" aria-label="Example queries">{starterQueries.map((item) => <button key={item} onClick={() => void submit(undefined, item)}>{item}</button>)}</div>
      <ModeSelector value={mode} onChange={setMode} />
      <div className="results-region" aria-live="polite">
        {error && <ErrorState message={error} />}
        {!error && !response && !loading && <EmptyState title="Ready for a traceability question" detail="Try a suggested query or search by an artifact ID such as REQ-003." />}
        {!error && response?.results.length === 0 && <EmptyState title="No traceable matches" detail="Try broader terms or another retrieval mode." />}
        {response && response.results.length > 0 && <>
          <div className="result-summary"><strong>{response.result_count} ranked artifacts</strong><span>{response.mode} retrieval · explainable scoring</span></div>
          <div className="result-list">{response.results.map((result, index) => {
            const channels = (["lexical", "semantic", "graph"] as const).filter((name) => result.explanation[name]);
            return <article className="result-card" key={result.id}>
              <button className="result-main" onClick={() => onSelect({ id: result.id, title: result.title, description: result.text } as Artifact)}>
                <span className="result-rank">{String(index + 1).padStart(2, "0")}</span>
                <span><span className="artifact-meta"><span className={`type-dot type-${result.entity_type.toLowerCase()}`} />{result.entity_type} · {result.id}</span><strong>{result.title}</strong><p>{result.text}</p></span>
                <span className="score"><strong>{result.score.toFixed(3)}</strong><small>fused score</small></span>
              </button>
              <details className="score-details"><summary><ChevronDown size={14} /> Why this result</summary>
                <div className="score-grid">{channels.map((name) => {
                  const score = result.explanation[name]!;
                  return <div key={name}><span>{name}<small>rank #{score.rank}</small></span><div className="mini-bar"><i style={{ width: `${score.normalized_score * 100}%` }} /></div><strong>{score.contribution.toFixed(4)}</strong></div>;
                })}</div>
                {result.explanation.anchor_ids.length > 0 && <p className="anchor-note">Graph evidence via {result.explanation.anchor_ids.join(", ")} · {result.explanation.graph_distance} hop{result.explanation.graph_distance === 1 ? "" : "s"}</p>}
              </details>
            </article>;
          })}</div>
        </>}
      </div>
    </section>
  );
}
