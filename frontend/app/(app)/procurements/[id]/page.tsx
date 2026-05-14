"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Download, Play, RotateCcw, Trash2, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { connectSSE, readSSEResponse } from "@/lib/sse";
import {
  CheckpointItem,
  ContractResult,
  DocumentRevision,
  EvaluationResult,
  OPENROUTER_MODELS,
  Procurement,
  RFPDocument,
  STAGE_LABELS,
  STAGE_WORKFLOW,
  SupplierProposal,
  WorkflowEvent,
  WorkflowRun,
} from "@/types";
import { WorkflowStepper } from "@/components/workflow/WorkflowStepper";
import { WorkflowExecutionViewer } from "@/components/workflow/WorkflowExecutionViewer";
import { CheckpointHistory } from "@/components/workflow/CheckpointHistory";
import { ContractViewer, EvaluationViewer, RFPViewer } from "@/components/workflow/OutputViewers";
import { formatDate } from "@/lib/utils";

export default function ProcurementDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [procurement, setProcurement] = useState<Procurement | null>(null);
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [proposals, setProposals] = useState<SupplierProposal[]>([]);
  const [liveNode, setLiveNode] = useState<string | undefined>();
  const [streamedText, setStreamedText] = useState("");
  const [interruptData, setInterruptData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [modelId, setModelId] = useState(OPENROUTER_MODELS[2].id);
  const [modelLabel, setModelLabel] = useState(OPENROUTER_MODELS[2].label);
  const [starting, setStarting] = useState(false);
  const [approvalAction, setApprovalAction] = useState("APPROVED");
  const [revisionRequest, setRevisionRequest] = useState("");
  const [approvalComments, setApprovalComments] = useState("");
  const [overrideProposalId, setOverrideProposalId] = useState("");
  const [resuming, setResuming] = useState(false);
  const [replaying, setReplaying] = useState(false);
  const [targetSections, setTargetSections] = useState<string[]>([]);
  const sseRef = useRef<EventSource | null>(null);

  // Output viewer state
  const [rfpData, setRfpData] = useState<RFPDocument | null>(null);
  const [evaluationData, setEvaluationData] = useState<EvaluationResult | null>(null);
  const [contractData, setContractData] = useState<ContractResult | null>(null);
  const [checkpoints, setCheckpoints] = useState<CheckpointItem[]>([]);
  const [checkpointCtx, setCheckpointCtx] = useState<{ wt: string; threadId: string } | null>(null);
  const [rfpRevisions, setRfpRevisions] = useState<DocumentRevision[]>([]);
  const [contractRevisions, setContractRevisions] = useState<DocumentRevision[]>([]);

  // Proposal upload state
  const [supplierName, setSupplierName] = useState("");
  const [proposalText, setProposalText] = useState("");
  const [uploadMode, setUploadMode] = useState<"text" | "file">("text");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const workflowType = procurement ? (STAGE_WORKFLOW[procurement.stage] ?? null) : null;

  function loadResults(procurementId: string, stage: string) {
    const stagesWithRfp = ["RFP", "PROPOSAL_INTAKE", "EVALUATION", "CONTRACT", "FINALIZED"];
    const stagesWithEval = ["EVALUATION", "CONTRACT", "FINALIZED"];
    if (stagesWithRfp.includes(stage)) {
      api.results.rfp(procurementId).then(setRfpData).catch(() => {});
      api.revisions.rfp(procurementId).then(setRfpRevisions).catch(() => {});
    }
    if (stagesWithEval.includes(stage)) {
      api.results.evaluation(procurementId).then(setEvaluationData).catch(() => {});
    }
    if (["CONTRACT", "FINALIZED"].includes(stage)) {
      api.results.contract(procurementId).then(setContractData).catch(() => {});
      api.revisions.contract(procurementId).then(setContractRevisions).catch(() => {});
    }
  }

  function loadCheckpoints(procurementId: string, wt: string, threadId: string) {
    api.workflows.getCheckpoints(procurementId, wt, threadId).then((cps) => {
      if (cps.length > 0) {
        setCheckpoints(cps);
        setCheckpointCtx({ wt, threadId });
      }
    }).catch(() => {});
  }

  function loadCheckpointsFromHistory(procurementId: string) {
    const ALL_WTS = ["CONTRACT", "EVALUATION", "PROPOSAL_INTAKE", "RFP"] as const;
    (async () => {
      for (const wt of ALL_WTS) {
        try {
          const r = await api.workflows.getActiveRun(procurementId, wt);
          if (r?.thread_id) {
            loadCheckpoints(procurementId, wt, r.thread_id);
            return;
          }
        } catch {}
      }
    })();
  }

  useEffect(() => {
    if (!id) return;
    Promise.all([api.procurements.get(id), api.proposals.list(id)])
      .then(([p, props]) => {
        setProcurement(p);
        setProposals(props);
        loadResults(id, p.stage);
        const wt = STAGE_WORKFLOW[p.stage];
        if (wt) {
          api.workflows.getActiveRun(id, wt).then((r) => {
            setRun(r);
            if (r) {
              api.workflows.getEvents(id, wt, r.thread_id).then(setEvents);
              loadCheckpoints(id, wt, r.thread_id);
              if (r.status === "INTERRUPTED") {
                api.workflows.getInterrupt(id, wt, r.thread_id)
                  .then((info) => setInterruptData(info.data))
                  .catch(() => {});
              }
            } else {
              loadCheckpointsFromHistory(id);
            }
          });
        } else {
          loadCheckpointsFromHistory(id);
        }
      })
      .finally(() => setLoading(false));
  }, [id]);

  function unwrapInterrupt(data: unknown): Record<string, unknown> {
    const d = data as { node?: string; data?: Record<string, unknown> };
    return d.data ?? (data as Record<string, unknown>);
  }

  function makeSSEHandlers(
    threadId: string,
    wt: string,
    onDone: () => void,
  ) {
    return {
      onNodeStart: ({ node }: { node: string }) => setLiveNode(node),
      onNodeEnd: ({ node, latency_ms }: { node: string; latency_ms: number }) => {
        setLiveNode(undefined);
        setEvents((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            thread_id: threadId,
            node_name: node,
            event_type: "NODE_END",
            payload: { latency_ms },
            model_id: null,
            tokens_used: null,
            latency_ms,
            created_at: new Date().toISOString(),
          },
        ]);
      },
      onStreamChunk: ({ chunk }: { chunk: string }) => setStreamedText((t) => t + chunk),
      onInterrupt: (data: unknown) => {
        setInterruptData(unwrapInterrupt(data));
        setStreamedText("");
        api.workflows.getEvents(id, wt, threadId).then(setEvents);
        loadCheckpoints(id, wt, threadId);
        setRun((r) => (r ? { ...r, status: "INTERRUPTED" } : r));
        if (procurement) loadResults(id, procurement.stage);
      },
      onWorkflowDone: () => {
        setLiveNode(undefined);
        setStreamedText("");
        loadCheckpoints(id, wt, threadId);
        onDone();
      },
      onError: ({ message }: { message: string }) => {
        setLiveNode(undefined);
        console.error("Workflow error:", message);
      },
    };
  }

  function openStream(threadId: string, wt: string) {
    sseRef.current?.close();
    const source = connectSSE(
      api.workflows.streamUrl(id, wt, threadId),
      makeSSEHandlers(threadId, wt, () => {
        api.procurements.get(id).then((p) => {
          setProcurement(p);
          loadResults(id, p.stage);
          const newWt = STAGE_WORKFLOW[p.stage];
          if (newWt) api.workflows.getActiveRun(id, newWt).then(setRun);
        });
        api.workflows.getEvents(id, wt, threadId).then(setEvents);
        if (wt === "PROPOSAL_INTAKE") api.proposals.list(id).then(setProposals);
      }),
    );
    sseRef.current = source;
  }

  async function handleStart() {
    if (!workflowType) return;
    setStarting(true);
    setEvents([]);
    setInterruptData(null);
    setStreamedText("");
    try {
      const newRun = await api.workflows.start(id, workflowType, {
        model_id: modelId,
        model_label: modelLabel,
        temperature: 0.3,
      });
      setRun(newRun);
      openStream(newRun.thread_id, workflowType);
    } finally {
      setStarting(false);
    }
  }

  async function handleResume() {
    if (!run || !workflowType) return;
    setResuming(true);
    setInterruptData(null);
    setStreamedText("");
    const resumeData = {
      thread_id: run.thread_id,
      action: approvalAction,
      comments: approvalComments || null,
      revision_request: approvalAction === "REVISION_REQUESTED" ? revisionRequest : null,
      manual_override_proposal_id: approvalAction === "MANUAL_OVERRIDE" ? overrideProposalId || null : null,
      target_sections: approvalAction === "REVISION_REQUESTED" && workflowType === "CONTRACT" && targetSections.length > 0
        ? targetSections
        : null,
    };
    try {
      const res = await fetch(api.workflows.resumeUrl(id, workflowType), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("procura_token")}`,
        },
        body: JSON.stringify(resumeData),
      });
      if (!res.ok) return;

      const threadId = run.thread_id;
      const wt = workflowType;
      setRun((r) => (r ? { ...r, status: "RUNNING" } : r));

      readSSEResponse(res, makeSSEHandlers(threadId, wt, () => {
        api.procurements.get(id).then((p) => {
          setProcurement(p);
          loadResults(id, p.stage);
          const newWt = STAGE_WORKFLOW[p.stage];
          if (newWt) api.workflows.getActiveRun(id, newWt).then(setRun);
        });
        api.workflows.getEvents(id, wt, threadId).then(setEvents);
        if (wt === "PROPOSAL_INTAKE") api.proposals.list(id).then(setProposals);
      }));
    } finally {
      setResuming(false);
    }
  }

  async function handleReplay(checkpointId: string) {
    if (!checkpointCtx) return;
    setReplaying(true);
    setStreamedText("");
    setInterruptData(null);
    const { wt, threadId } = checkpointCtx;
    try {
      const res = await fetch(api.workflows.replayUrl(id, wt), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("procura_token")}`,
        },
        body: JSON.stringify({ thread_id: threadId, checkpoint_id: checkpointId }),
      });
      if (!res.ok) return;
      setRun((r) => (r ? { ...r, status: "RUNNING" } : r));
      readSSEResponse(res, makeSSEHandlers(threadId, wt, () => {
        api.procurements.get(id).then((p) => {
          setProcurement(p);
          loadResults(id, p.stage);
        });
        api.workflows.getEvents(id, wt, threadId).then(setEvents);
      }));
    } finally {
      setReplaying(false);
    }
  }

  async function handleUploadProposal(e: React.FormEvent) {
    e.preventDefault();
    if (!supplierName.trim()) return;
    setUploading(true);
    setUploadError("");
    try {
      let proposal: SupplierProposal;
      if (uploadMode === "text") {
        proposal = await api.proposals.uploadText(id, supplierName, proposalText);
      } else if (uploadFile) {
        proposal = await api.proposals.uploadFile(id, supplierName, uploadFile);
      } else {
        setUploadError("Please select a file");
        return;
      }
      setProposals((prev) => [...prev, proposal]);
      setSupplierName("");
      setProposalText("");
      setUploadFile(null);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleDeleteProposal(proposalId: string) {
    await api.proposals.delete(id, proposalId);
    setProposals((prev) => prev.filter((p) => p.id !== proposalId));
  }

  if (loading) {
    return (
      <div className="p-8">
        <div className="h-8 w-48 bg-muted/50 rounded animate-pulse" />
      </div>
    );
  }
  if (!procurement) {
    return <div className="p-8 text-muted-foreground">Procurement not found.</div>;
  }

  const canStart = !run || run.status === "COMPLETED" || run.status === "FAILED";
  const isInterrupted = run?.status === "INTERRUPTED";
  const isRunning = run?.status === "RUNNING" || run?.status === "PENDING";
  const isFinalized = procurement.stage === "FINALIZED";

  return (
    <div className="p-8 max-w-5xl">
      <Link
        href="/procurements"
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Procurements
      </Link>

      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{procurement.title}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Created {formatDate(procurement.created_at)}
          </p>
        </div>
        <span
          className={`text-xs px-2.5 py-1 rounded-full font-medium ${
            procurement.status === "ACTIVE"
              ? "bg-emerald-100 text-emerald-700"
              : "bg-muted text-muted-foreground"
          }`}
        >
          {procurement.status}
        </span>
      </div>

      <div className="mb-8 overflow-x-auto">
        <WorkflowStepper currentStage={procurement.stage} />
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Main column */}
        <div className="col-span-2 space-y-5">
          {isFinalized && (
            <div className="flex items-center gap-2 px-4 py-3 bg-green-50 border border-green-200 rounded-lg">
              <span className="h-2 w-2 rounded-full bg-green-500" />
              <p className="text-sm font-medium text-green-800">
                Procurement complete — contract finalized with {contractData?.supplier_name ?? "selected supplier"}.
              </p>
            </div>
          )}

          {/* Proposal Intake: upload form */}
          {procurement.stage === "PROPOSAL_INTAKE" && (
            <ProposalUploadPanel
              proposals={proposals}
              supplierName={supplierName}
              setSupplierName={setSupplierName}
              proposalText={proposalText}
              setProposalText={setProposalText}
              uploadMode={uploadMode}
              setUploadMode={setUploadMode}
              uploadFile={uploadFile}
              setUploadFile={setUploadFile}
              uploading={uploading}
              uploadError={uploadError}
              onSubmit={handleUploadProposal}
              onDelete={handleDeleteProposal}
            />
          )}

          {/* Workflow controls */}
          {!isFinalized && workflowType && (
            <div className="border rounded-lg p-5">
              <h2 className="text-sm font-medium mb-4">
                {STAGE_LABELS[procurement.stage]} Workflow
              </h2>

              {canStart && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                      AI Model
                    </label>
                    <select
                      value={modelId}
                      onChange={(e) => {
                        setModelId(e.target.value);
                        setModelLabel(
                          OPENROUTER_MODELS.find((m) => m.id === e.target.value)?.label ??
                            e.target.value
                        );
                      }}
                      className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      {OPENROUTER_MODELS.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    onClick={handleStart}
                    disabled={starting}
                    className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                  >
                    {run?.status === "FAILED" ? (
                      <RotateCcw className="h-4 w-4" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    {starting
                      ? "Starting..."
                      : run?.status === "FAILED"
                      ? "Retry Workflow"
                      : "Run Workflow"}
                  </button>
                </div>
              )}

              {(isRunning || replaying) && (
                <div className="flex items-center gap-2 text-sm text-blue-600">
                  <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
                  {replaying ? "Replaying from checkpoint…" : "Workflow is running…"}
                </div>
              )}

              {isInterrupted && interruptData && (
                <ApprovalPanel
                  interruptData={interruptData}
                  workflowType={workflowType}
                  approvalAction={approvalAction}
                  setApprovalAction={setApprovalAction}
                  revisionRequest={revisionRequest}
                  setRevisionRequest={setRevisionRequest}
                  approvalComments={approvalComments}
                  setApprovalComments={setApprovalComments}
                  overrideProposalId={overrideProposalId}
                  setOverrideProposalId={setOverrideProposalId}
                  targetSections={targetSections}
                  setTargetSections={setTargetSections}
                  resuming={resuming}
                  replaying={replaying}
                  onResume={handleResume}
                />
              )}
            </div>
          )}

          {/* Output viewers — shown before execution log for easy review */}
          {rfpData && <RFPViewer rfp={rfpData} procurementId={id} revisions={rfpRevisions} />}
          {evaluationData && <EvaluationViewer evaluation={evaluationData} />}
          {contractData && <ContractViewer contract={contractData} procurementId={id} revisions={contractRevisions} />}

          {checkpoints.length > 0 && (
            <CheckpointHistory
              checkpoints={checkpoints}
              onReplay={checkpointCtx ? handleReplay : undefined}
            />
          )}

          {!isFinalized && (
            <WorkflowExecutionViewer
              events={events}
              liveNode={liveNode}
              streamedText={streamedText}
            />
          )}
        </div>

        {/* Right panel */}
        <div className="space-y-4">
          <div className="border rounded-lg p-4">
            <h3 className="text-sm font-medium mb-3">Details</h3>
            <dl className="space-y-2 text-sm">
              <Row label="Timeline" value={procurement.timeline} />
              <Row
                label="Budget"
                value={
                  procurement.budget_min || procurement.budget_max
                    ? `${procurement.budget_min ?? "—"} – ${procurement.budget_max ?? "—"} ${procurement.budget_currency}`
                    : "Not specified"
                }
              />
              <Row label="Criteria" value={`${procurement.evaluation_criteria.length} defined`} />
              {proposals.length > 0 && (
                <Row label="Proposals" value={String(proposals.length)} />
              )}
            </dl>
          </div>

          {run && !isFinalized && (
            <div className="border rounded-lg p-4">
              <h3 className="text-sm font-medium mb-3">Workflow Run</h3>
              <dl className="space-y-2 text-sm">
                <Row label="Status" value={run.status} />
                <Row label="Events" value={String(events.length)} />
                <Row label="Started" value={formatDate(run.started_at)} />
              </dl>
            </div>
          )}

          {procurement.evaluation_criteria.length > 0 && (
            <div className="border rounded-lg p-4">
              <h3 className="text-sm font-medium mb-3">Eval Criteria</h3>
              <div className="space-y-1.5">
                {procurement.evaluation_criteria.map((c) => (
                  <div key={c.criterion} className="flex justify-between text-sm">
                    <span className="text-muted-foreground truncate mr-2">{c.criterion}</span>
                    <span className="font-medium shrink-0">
                      {Math.round(c.weight * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="border rounded-lg p-4">
            <h3 className="text-sm font-medium mb-3">Audit Log</h3>
            <p className="text-xs text-muted-foreground mb-3">
              Export all workflow events as CSV for compliance and review.
            </p>
            <button
              onClick={() => api.workflows.downloadAuditLog(id).catch(console.error)}
              className="flex items-center gap-2 w-full px-3 py-2 border rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors"
            >
              <Download className="h-3.5 w-3.5" />
              Export Audit Log
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ProposalUploadPanel({
  proposals,
  supplierName, setSupplierName,
  proposalText, setProposalText,
  uploadMode, setUploadMode,
  uploadFile, setUploadFile,
  uploading, uploadError,
  onSubmit, onDelete,
}: {
  proposals: SupplierProposal[];
  supplierName: string; setSupplierName: (v: string) => void;
  proposalText: string; setProposalText: (v: string) => void;
  uploadMode: "text" | "file"; setUploadMode: (v: "text" | "file") => void;
  uploadFile: File | null; setUploadFile: (v: File | null) => void;
  uploading: boolean; uploadError: string;
  onSubmit: (e: React.FormEvent) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="border rounded-lg p-5 space-y-4">
      <h2 className="text-sm font-medium">Supplier Proposals</h2>

      {proposals.length > 0 && (
        <div className="divide-y border rounded-md overflow-hidden">
          {proposals.map((p) => (
            <div key={p.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
              <div>
                <span className="font-medium">{p.supplier_name}</span>
                <span className="text-xs text-muted-foreground ml-2">{p.original_filename}</span>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    p.extraction_status === "COMPLETED"
                      ? "bg-green-100 text-green-700"
                      : p.extraction_status === "FAILED"
                      ? "bg-red-100 text-red-700"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {p.extraction_status}
                </span>
                <button
                  onClick={() => onDelete(p.id)}
                  className="text-muted-foreground hover:text-destructive transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1">
            Supplier Name
          </label>
          <input
            value={supplierName}
            onChange={(e) => setSupplierName(e.target.value)}
            required
            placeholder="e.g. Acme Corp"
            className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div className="flex gap-2">
          {(["text", "file"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setUploadMode(mode)}
              className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${
                uploadMode === mode
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {mode === "text" ? "Paste Text" : "Upload File"}
            </button>
          ))}
        </div>

        {uploadMode === "text" ? (
          <textarea
            value={proposalText}
            onChange={(e) => setProposalText(e.target.value)}
            required
            rows={6}
            placeholder="Paste proposal content here…"
            className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        ) : (
          <label className="flex flex-col items-center justify-center border-2 border-dashed rounded-md p-6 cursor-pointer hover:bg-muted/30 transition-colors">
            <Upload className="h-5 w-5 text-muted-foreground mb-2" />
            <span className="text-sm text-muted-foreground">
              {uploadFile ? uploadFile.name : "Click to select PDF or DOCX"}
            </span>
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              className="sr-only"
              onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
            />
          </label>
        )}

        {uploadError && (
          <p className="text-xs text-destructive bg-destructive/10 px-3 py-2 rounded-md">
            {uploadError}
          </p>
        )}

        <button
          type="submit"
          disabled={uploading}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Upload className="h-3.5 w-3.5" />
          {uploading ? "Uploading…" : "Add Proposal"}
        </button>
      </form>
    </div>
  );
}

const CONTRACT_SECTIONS = [
  { id: "scope", label: "Scope of Work" },
  { id: "payment_terms", label: "Payment Terms" },
  { id: "milestones", label: "Milestones" },
  { id: "legal_clauses", label: "Legal Clauses" },
  { id: "termination_clauses", label: "Termination Clauses" },
];

function ApprovalPanel({
  interruptData, workflowType,
  approvalAction, setApprovalAction,
  revisionRequest, setRevisionRequest,
  approvalComments, setApprovalComments,
  overrideProposalId, setOverrideProposalId,
  targetSections, setTargetSections,
  resuming, replaying, onResume,
}: {
  interruptData: Record<string, unknown>;
  workflowType: string;
  approvalAction: string; setApprovalAction: (v: string) => void;
  revisionRequest: string; setRevisionRequest: (v: string) => void;
  approvalComments: string; setApprovalComments: (v: string) => void;
  overrideProposalId: string; setOverrideProposalId: (v: string) => void;
  targetSections: string[]; setTargetSections: (v: string[]) => void;
  resuming: boolean;
  replaying: boolean;
  onResume: () => void;
}) {
  const type = interruptData.type as string | undefined;
  const rankings = (interruptData.rankings ?? []) as { proposal_id: string; supplier_name: string; rank: number }[];
  const isContractReview = type === "contract_review";

  function toggleSection(sectionId: string) {
    setTargetSections(
      targetSections.includes(sectionId)
        ? targetSections.filter((s) => s !== sectionId)
        : [...targetSections, sectionId]
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-amber-50 border border-amber-200 rounded-md p-4">
        <p className="text-sm font-medium text-amber-800 mb-1">Awaiting your decision</p>
        {type === "proposal_intake_review" && (
          <p className="text-xs text-amber-700">
            {String(interruptData.extracted_count ?? 0)} proposals extracted,{" "}
            {String(interruptData.failed_count ?? 0)} failed.
          </p>
        )}
        {type === "evaluation_review" && rankings.length > 0 && (
          <div className="mt-2 space-y-1">
            {rankings.map((r) => (
              <p key={r.proposal_id} className="text-xs text-amber-700">
                {r.rank}. {r.supplier_name}
              </p>
            ))}
          </div>
        )}
        {isContractReview && (
          <p className="text-xs text-amber-700">Contract draft is ready for review.</p>
        )}
        {(type === "rfp_review" || !type) && (
          <p className="text-xs text-amber-700">
            The AI has generated a draft. Please review and take action.
          </p>
        )}
      </div>

      <div>
        <label className="block text-xs font-medium text-muted-foreground mb-1.5">
          Action
        </label>
        <select
          value={approvalAction}
          onChange={(e) => setApprovalAction(e.target.value)}
          className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="APPROVED">Approve</option>
          {(type === "rfp_review" || isContractReview || !type) && (
            <option value="REVISION_REQUESTED">Request Revision</option>
          )}
          {type === "evaluation_review" && (
            <option value="MANUAL_OVERRIDE">Override Winner</option>
          )}
          <option value="REJECTED">Reject</option>
        </select>
      </div>

      {approvalAction === "MANUAL_OVERRIDE" && rankings.length > 0 && (
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Select Winner
          </label>
          <select
            value={overrideProposalId}
            onChange={(e) => setOverrideProposalId(e.target.value)}
            className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">— pick a supplier —</option>
            {rankings.map((r) => (
              <option key={r.proposal_id} value={r.proposal_id}>
                {r.rank}. {r.supplier_name}
              </option>
            ))}
          </select>
        </div>
      )}

      {approvalAction === "REVISION_REQUESTED" && (
        <>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              Revision Notes
            </label>
            <textarea
              value={revisionRequest}
              onChange={(e) => setRevisionRequest(e.target.value)}
              rows={3}
              placeholder="What needs to change…"
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {isContractReview && (
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                Sections to regenerate
                <span className="ml-1 font-normal text-muted-foreground/60">(leave empty to regenerate all)</span>
              </label>
              <div className="space-y-1.5">
                {CONTRACT_SECTIONS.map((s) => (
                  <label key={s.id} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={targetSections.includes(s.id)}
                      onChange={() => toggleSection(s.id)}
                      className="h-3.5 w-3.5 rounded border-border"
                    />
                    <span className="text-sm">{s.label}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <div>
        <label className="block text-xs font-medium text-muted-foreground mb-1.5">
          Comments (optional)
        </label>
        <textarea
          value={approvalComments}
          onChange={(e) => setApprovalComments(e.target.value)}
          rows={2}
          className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      <button
        onClick={onResume}
        disabled={resuming || replaying}
        className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
      >
        {resuming ? "Submitting…" : "Submit Decision"}
      </button>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-muted-foreground shrink-0">{label}</dt>
      <dd className="text-right font-medium truncate">{value}</dd>
    </div>
  );
}
