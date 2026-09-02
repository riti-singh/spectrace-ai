import type { DashboardData } from "../types";

export const dashboardFixture: DashboardData = {
  requirements: [
    { id: "REQ-001", title: "Satellite acquisition", normative_text: "The terminal shall acquire the serving satellite within the specified interval.", requirement_type: "functional", priority: "critical", source_section: "3.1", verification_method: "test", component_ids: ["CMP-001"], risk_ids: ["RSK-001"], dependency_ids: [] },
    { id: "REQ-002", title: "Credential validation", normative_text: "The terminal shall validate credentials before enabling user traffic.", requirement_type: "security", priority: "high", source_section: "3.2", verification_method: "test", component_ids: ["CMP-001"], risk_ids: [], dependency_ids: ["REQ-001"] }
  ],
  components: [{ id: "CMP-001", name: "RF assembly", description: "Electronically steered radio frequency assembly." }],
  risks: [{ id: "RSK-001", title: "Acquisition delay", description: "A delayed acquisition interrupts service availability.", severity: "high", mitigation: "Use bounded scanning and recovery behavior." }],
  tests: [{ id: "TST-001", title: "Acquisition timing", objective: "Measure acquisition performance under controlled conditions.", requirement_ids: ["REQ-001"], status: "automated" }],
  uncovered: [{ id: "REQ-002", title: "Credential validation", normative_text: "The terminal shall validate credentials before enabling user traffic.", requirement_type: "security", priority: "high", source_section: "3.2", verification_method: "test", component_ids: ["CMP-001"], risk_ids: [], dependency_ids: ["REQ-001"] }],
  summary: { total_requirements: 2, covered_requirements: 1, uncovered_requirements: 1, coverage_percentage: 50, requirements_by_priority: { critical: 1, high: 1 }, requirements_by_type: { functional: 1, security: 1 } },
  evaluation: { benchmark: "asteria-hybrid-retrieval-v1", dataset: "Asteria synthetic traceability dataset", query_count: 8, k: 5, characterization: "Synthetic benchmark only.", metrics: [
    { mode: "lexical", precision_at_k: .6, recall_at_k: .7, mrr: .8, ndcg_at_k: .75 },
    { mode: "semantic", precision_at_k: .62, recall_at_k: .72, mrr: .9, ndcg_at_k: .8 },
    { mode: "graph", precision_at_k: .2, recall_at_k: .2, mrr: .5, ndcg_at_k: .15 },
    { mode: "hybrid", precision_at_k: .65, recall_at_k: .8, mrr: .93, ndcg_at_k: .84 }
  ] }
};
