import { BarChart3, Box, CircleHelp, FileSearch, LayoutDashboard, Menu, Network, Orbit, PanelLeftClose, ShieldCheck, TestTube2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { loadDashboard } from "./api/client";
import { ArtifactPanel } from "./components/ArtifactPanel";
import { AttentionViews } from "./components/AttentionViews";
import { EvaluationSummary } from "./components/EvaluationSummary";
import { MetricCard } from "./components/MetricCard";
import { RelationshipGraph } from "./components/RelationshipGraph";
import { SearchWorkspace } from "./components/SearchWorkspace";
import { ErrorState, LoadingState } from "./components/StateView";
import type { Artifact, DashboardData } from "./types";

const navItems = [
  { label: "Overview", icon: LayoutDashboard, target: "overview" },
  { label: "Trace search", icon: FileSearch, target: "search" },
  { label: "Graph explorer", icon: Network, target: "graph" },
  { label: "Coverage gaps", icon: ShieldCheck, target: "attention" },
  { label: "Evaluation", icon: BarChart3, target: "evaluation" }
];

function resolveArtifact(data: DashboardData, artifact: Artifact): Artifact {
  return [...data.requirements, ...data.components, ...data.risks, ...data.tests].find((item) => item.id === artifact.id) ?? artifact;
}

export default function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Artifact | null>(null);
  const [navOpen, setNavOpen] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try { setData(await loadDashboard()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "The API did not return dashboard data."); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  const select = useCallback((artifact: Artifact) => { if (data) setSelected(resolveArtifact(data, artifact)); }, [data]);
  const metrics = useMemo(() => {
    if (!data) return null;
    const criticalRisks = data.risks.filter((risk) => risk.severity === "critical" || risk.severity === "high").length;
    const automatedTests = data.tests.filter((test) => test.status === "automated").length;
    return { artifacts: data.requirements.length + data.components.length + data.risks.length + data.tests.length, criticalRisks, automatedTests };
  }, [data]);

  function navigate(target: string) {
    document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "start" });
    setNavOpen(false);
  }

  return <div className="app-shell">
    <aside className={`sidebar ${navOpen ? "open" : ""}`}>
      <div className="brand"><span><Orbit /></span><div><strong>Spectrace</strong><small>AI TRACEABILITY</small></div></div>
      <nav aria-label="Dashboard navigation">{navItems.map(({ label, icon: Icon, target }, index) => <button key={target} className={index === 0 ? "active" : ""} onClick={() => navigate(target)}><Icon size={18} /><span>{label}</span></button>)}</nav>
      <div className="sidebar-foot"><div className="system-state"><span /><div><strong>Asteria dataset</strong><small>deterministic reference</small></div></div><button aria-label="Help and limitations" onClick={() => navigate("limitations")}><CircleHelp size={18} /></button></div>
    </aside>
    <main>
      <header className="topbar"><button className="mobile-menu" aria-label="Open navigation" onClick={() => setNavOpen(!navOpen)}>{navOpen ? <PanelLeftClose /> : <Menu />}</button><div><span className="breadcrumb">Workspace <b>/</b> Asteria Terminal</span><h1>Traceability command center</h1></div><div className="top-actions"><span className="environment"><i /> LOCAL DATA</span><span className="avatar">SA</span></div></header>
      {error && <div className="page-state"><ErrorState message={`${error} Confirm the FastAPI server is running at port 8000.`} onRetry={() => void refresh()} /></div>}
      {!error && !data && <div className="page-state"><LoadingState /></div>}
      {data && metrics && <div className="content">
        <section id="overview" className="hero-section"><div><span className="eyebrow">Executive overview</span><h2>Evidence you can follow.</h2><p>A live, deterministic view of how system intent connects to implementation, risk, and verification.</p></div><div className="snapshot"><span>Dataset snapshot</span><strong>ASTERIA · V1</strong><small>Fictional engineering corpus</small></div></section>
        <section className="metric-grid" aria-label="Executive metrics">
          <MetricCard icon={ShieldCheck} label="Requirement coverage" value={`${data.summary.coverage_percentage.toFixed(0)}%`} detail={`${data.summary.covered_requirements} of ${data.summary.total_requirements} linked to tests`} tone="mint" />
          <MetricCard icon={Box} label="Trace artifacts" value={String(metrics.artifacts)} detail={`${data.components.length} components · ${data.requirements.length} requirements`} tone="blue" />
          <MetricCard icon={ShieldCheck} label="High-impact risks" value={String(metrics.criticalRisks)} detail={`${data.risks.length} risks tracked across the graph`} tone="rose" />
          <MetricCard icon={TestTube2} label="Automated tests" value={String(metrics.automatedTests)} detail={`${data.tests.length} total verification cases`} tone="amber" />
        </section>
        <div id="search"><SearchWorkspace onSelect={select} /></div>
        <div id="graph"><RelationshipGraph data={data} selectedId={selected?.id ?? "REQ-003"} onSelect={select} /></div>
        <div id="attention"><AttentionViews data={data} onSelect={select} /></div>
        <div id="evaluation"><EvaluationSummary evaluation={data.evaluation} /></div>
        <section id="limitations" className="limitations"><strong>Scope note</strong><p>This dashboard reports links in a synthetic dataset. Coverage is not proof of test execution, product readiness, safety, or flight qualification. Search quality values are benchmark observations, not production claims.</p></section>
        <footer><span>© Spectrace AI · Milestone 4</span><span>FastAPI · React · Neo4j</span></footer>
      </div>}
    </main>
    {navOpen && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
    {data && <ArtifactPanel artifact={selected} data={data} onClose={() => setSelected(null)} onSelect={select} />}
  </div>;
}
