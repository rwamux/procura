export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

export interface Procurement {
  id: string;
  title: string;
  business_objective: string;
  scope: string;
  budget_min: number | null;
  budget_max: number | null;
  budget_currency: string;
  timeline: string;
  evaluation_criteria: EvaluationCriterion[];
  compliance_requirements: string | null;
  stage: ProcurementStage;
  status: ProcurementStatus;
  created_by: string;
  selected_proposal_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvaluationCriterion {
  criterion: string;
  weight: number;
}

export type ProcurementStage = "RFP" | "PROPOSAL_INTAKE" | "EVALUATION" | "CONTRACT" | "FINALIZED";
export type ProcurementStatus = "ACTIVE" | "COMPLETED" | "CANCELLED";
export type WorkflowType = "RFP" | "PROPOSAL_INTAKE" | "EVALUATION" | "CONTRACT";

export interface SupplierProposal {
  id: string;
  procurement_id: string;
  supplier_name: string;
  original_filename: string;
  file_size_bytes: number | null;
  mime_type: string | null;
  extraction_status: "SUBMITTED" | "COMPLETED" | "FAILED";
  status: string;
  upload_timestamp: string;
  extracted_data: Record<string, unknown> | null;
}

export interface WorkflowRun {
  id: string;
  procurement_id: string;
  workflow_type: WorkflowType;
  thread_id: string;
  status: "PENDING" | "RUNNING" | "INTERRUPTED" | "COMPLETED" | "FAILED";
  started_at: string;
  completed_at: string | null;
}

export interface WorkflowEvent {
  id: string;
  thread_id: string;
  node_name: string;
  event_type: string;
  payload: {
    node?: string;
    latency_ms?: number;
    tokens_used?: number;
    langsmith_run_id?: string;
    langsmith_url?: string;
    [key: string]: unknown;
  } | null;
  model_id: string | null;
  tokens_used: number | null;
  latency_ms: number | null;
  created_at: string;
}

export interface CheckpointItem {
  checkpoint_id: string;
  step: number;
  source: string;
  node: string | null;
  next: string[];
  created_at: string | null;
}

export interface DocumentRevision {
  id: string;
  version: number;
  revision_request: string;
  created_at: string | null;
}

export interface WorkflowModelConfig {
  id: string;
  procurement_id: string;
  workflow_type: WorkflowType;
  model_id: string;
  model_label: string;
  temperature: number;
}

export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

export interface RFPDocument {
  id: string;
  version: number;
  status: string;
  content: {
    executive_summary: string;
    scope_of_work: string;
    deliverables: string[];
    submission_requirements: string;
    evaluation_criteria: { criterion: string; weight: number; description: string }[];
    timelines: { description: string; due_date: string }[];
    legal_compliance_notes: string;
  };
  model_id: string;
  created_at: string;
}

export interface ProposalScoreItem {
  proposal_id: string;
  supplier_name: string;
  weighted_total: number;
  rank: number;
  ai_assessment: {
    overall_assessment: string;
    strengths: string[];
    weaknesses: string[];
    criterion_scores: Record<string, number>;
    recommendation: string;
  };
}

export interface EvaluationResult {
  id: string;
  status: string;
  evaluation_weights: Record<string, number>;
  recommendation_proposal_id: string | null;
  recommendation_rationale: string | null;
  scores: ProposalScoreItem[];
}

export interface ContractResult {
  id: string;
  supplier_name: string;
  version: number;
  draft_content: Record<string, string>;
  status: string;
  model_id: string;
  created_at: string;
}

export const OPENROUTER_MODELS = [
  { id: "anthropic/claude-haiku-4.5", label: "Claude Haiku 4.5" },
  { id: "openai/gpt-4o", label: "GPT-4o" },
  { id: "openai/gpt-4o-mini", label: "GPT-4o Mini (Fast)" },
  { id: "google/gemini-2.5-flash-lite", label: "Gemini 2.5 Flash Lite" },
  { id: "meta-llama/llama-3.1-70b-instruct", label: "Llama 3.1 70B" },
];

export const STAGE_LABELS: Record<ProcurementStage, string> = {
  RFP: "RFP Creation",
  PROPOSAL_INTAKE: "Proposal Intake",
  EVALUATION: "Evaluation",
  CONTRACT: "Contract Drafting",
  FINALIZED: "Finalized",
};

export const STAGE_WORKFLOW: Partial<Record<ProcurementStage, WorkflowType>> = {
  RFP: "RFP",
  PROPOSAL_INTAKE: "PROPOSAL_INTAKE",
  EVALUATION: "EVALUATION",
  CONTRACT: "CONTRACT",
};
