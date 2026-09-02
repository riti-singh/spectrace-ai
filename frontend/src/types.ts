export type EntityType = "Requirement" | "Component" | "Risk" | "TestCase";
export type RetrievalMode = "lexical" | "semantic" | "graph" | "hybrid";

export interface Requirement {
  id: string;
  title: string;
  normative_text: string;
  requirement_type: string;
  priority: "critical" | "high" | "medium" | "low";
  source_section: string;
  verification_method: string;
  component_ids: string[];
  risk_ids: string[];
  dependency_ids: string[];
}

export interface Component { id: string; name: string; description: string }
export interface Risk { id: string; title: string; description: string; severity: string; mitigation: string }
export interface TestCase { id: string; title: string; objective: string; requirement_ids: string[]; status: string }

export interface TraceabilitySummary {
  total_requirements: number;
  covered_requirements: number;
  uncovered_requirements: number;
  coverage_percentage: number;
  requirements_by_priority: Record<string, number>;
  requirements_by_type: Record<string, number>;
}

export interface ScoreComponent {
  raw_score: number;
  normalized_score: number;
  rank: number;
  contribution: number;
}

export interface RetrievalResult {
  id: string;
  entity_type: EntityType;
  title: string;
  text: string;
  score: number;
  explanation: {
    fusion_method: string;
    lexical: ScoreComponent | null;
    semantic: ScoreComponent | null;
    graph: ScoreComponent | null;
    graph_distance: number | null;
    anchor_ids: string[];
  };
}

export interface RetrievalResponse { query: string; mode: RetrievalMode; result_count: number; results: RetrievalResult[] }
export interface EvaluationMetric { mode: RetrievalMode; precision_at_k: number; recall_at_k: number; mrr: number; ndcg_at_k: number }
export interface EvaluationSummary { benchmark: string; dataset: string; query_count: number; k: number; characterization: string; metrics: EvaluationMetric[] }

export interface DashboardData {
  requirements: Requirement[];
  components: Component[];
  risks: Risk[];
  tests: TestCase[];
  uncovered: Requirement[];
  summary: TraceabilitySummary;
  evaluation: EvaluationSummary;
}

export type Artifact = Requirement | Component | Risk | TestCase;
