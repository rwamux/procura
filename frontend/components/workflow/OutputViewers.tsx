"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight, Clock, Download, FileText, BarChart2, FileCheck } from "lucide-react";
import { api } from "@/lib/api";
import { ContractResult, DocumentRevision, EvaluationResult, RFPDocument } from "@/types";

// ── Shared ────────────────────────────────────────────────────────────────────

function Section({
  icon,
  title,
  badge,
  children,
  defaultOpen = false,
}: {
  icon: React.ReactNode;
  title: string;
  badge?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3.5 bg-muted/20 hover:bg-muted/40 transition-colors text-left"
      >
        <div className="flex items-center gap-2.5">
          {icon}
          <span className="text-sm font-medium">{title}</span>
          {badge && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
              {badge}
            </span>
          )}
        </div>
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {open && <div className="px-5 py-4">{children}</div>}
    </div>
  );
}

// ── RFP Viewer ────────────────────────────────────────────────────────────────

export function RFPViewer({
  rfp,
  procurementId,
  revisions,
}: {
  rfp: RFPDocument;
  procurementId: string;
  revisions?: DocumentRevision[];
}) {
  const c = rfp.content;
  const isApproved = rfp.status === "APPROVED";
  return (
    <Section
      icon={<FileText className="h-4 w-4 text-blue-500" />}
      title={isApproved ? "Approved RFP" : "RFP Draft — Awaiting Review"}
      badge={`v${rfp.version}`}
      defaultOpen={!isApproved}
    >
      <div className="space-y-5">
        <div className="flex justify-end">
          <button
            onClick={() =>
              api.results.downloadRfp(procurementId, `RFP_v${rfp.version}.docx`).catch(console.error)
            }
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors font-medium"
          >
            <Download className="h-3.5 w-3.5" />
            Download .docx
          </button>
        </div>
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
            Executive Summary
          </h4>
          <p className="text-sm leading-relaxed">{c.executive_summary}</p>
        </div>

        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
            Scope of Work
          </h4>
          <p className="text-sm leading-relaxed whitespace-pre-line">{c.scope_of_work}</p>
        </div>

        {c.deliverables?.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
              Deliverables
            </h4>
            <ul className="space-y-1">
              {c.deliverables.map((d, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                  {d}
                </li>
              ))}
            </ul>
          </div>
        )}

        {c.evaluation_criteria?.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
              Evaluation Criteria
            </h4>
            <div className="space-y-1.5">
              {c.evaluation_criteria.map((ec, i) => (
                <div key={i} className="flex items-start gap-3 text-sm">
                  <span className="shrink-0 w-12 text-right font-mono text-xs text-primary font-semibold pt-0.5">
                    {Math.round(ec.weight * 100)}%
                  </span>
                  <div>
                    <span className="font-medium">{ec.criterion}</span>
                    {ec.description && (
                      <span className="text-muted-foreground ml-1.5">— {ec.description}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {c.timelines?.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
              Milestones
            </h4>
            <div className="space-y-1">
              {c.timelines.map((t, i) => (
                <div key={i} className="flex items-center gap-3 text-sm">
                  <span className="shrink-0 text-xs font-medium text-muted-foreground w-20 text-right">
                    {t.due_date}
                  </span>
                  <span>{t.description}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
            Submission Requirements
          </h4>
          <p className="text-sm leading-relaxed">{c.submission_requirements}</p>
        </div>

        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
            Legal &amp; Compliance
          </h4>
          <p className="text-sm leading-relaxed">{c.legal_compliance_notes}</p>
        </div>

        {revisions && revisions.length > 0 && (
          <RevisionTimeline revisions={revisions} />
        )}
      </div>
    </Section>
  );
}

// ── Revision Timeline ─────────────────────────────────────────────────────────

function RevisionTimeline({ revisions }: { revisions: DocumentRevision[] }) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1.5">
        <Clock className="h-3.5 w-3.5" />
        Revision History ({revisions.length})
      </h4>
      <div className="space-y-2">
        {revisions.map((r) => (
          <div key={r.id} className="flex gap-3 text-sm">
            <span className="shrink-0 text-xs font-mono text-muted-foreground/60 mt-0.5">v{r.version}</span>
            <div className="flex-1 border-l pl-3 pb-2">
              <p className="text-xs text-muted-foreground italic">"{r.revision_request}"</p>
              {r.created_at && (
                <p className="text-xs text-muted-foreground/50 mt-0.5">
                  {new Date(r.created_at).toLocaleString()}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Evaluation Viewer ─────────────────────────────────────────────────────────

export function EvaluationViewer({ evaluation }: { evaluation: EvaluationResult }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const criteriaEntries = Object.entries(evaluation.evaluation_weights ?? {});

  return (
    <Section
      icon={<BarChart2 className="h-4 w-4 text-purple-500" />}
      title="Evaluation Results"
      badge={`${evaluation.scores.length} proposals`}
      defaultOpen
    >
      <div className="space-y-4">
        {evaluation.recommendation_rationale && (
          <div className="bg-purple-50 border border-purple-100 rounded-md px-4 py-3">
            <p className="text-xs font-semibold text-purple-700 mb-1">AI Recommendation</p>
            <p className="text-sm text-purple-900">{evaluation.recommendation_rationale}</p>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="py-2 pr-3 text-left font-medium w-8">#</th>
                <th className="py-2 pr-3 text-left font-medium">Supplier</th>
                <th className="py-2 pr-3 text-right font-medium">Total&nbsp;/10</th>
                {criteriaEntries.map(([name, weight]) => (
                  <th key={name} className="py-2 px-2 text-right font-medium">
                    <div>{name}</div>
                    <div className="text-muted-foreground/60 font-normal">
                      {Math.round(weight * 100)}%
                    </div>
                  </th>
                ))}
                <th className="py-2 pl-3" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {evaluation.scores.map((s) => (
                <React.Fragment key={s.proposal_id}>
                  <tr
                    className="hover:bg-muted/30 cursor-pointer"
                    onClick={() =>
                      setExpanded(expanded === s.proposal_id ? null : s.proposal_id)
                    }
                  >
                    <td className="py-2.5 pr-3 font-semibold text-muted-foreground">
                      {s.rank === 1 ? "🥇" : s.rank === 2 ? "🥈" : s.rank === 3 ? "🥉" : s.rank}
                    </td>
                    <td className="py-2.5 pr-3 font-medium">{s.supplier_name}</td>
                    <td className="py-2.5 pr-3 text-right font-mono font-semibold text-primary">
                      {s.weighted_total.toFixed(1)}
                    </td>
                    {criteriaEntries.map(([name]) => (
                      <td key={name} className="py-2.5 px-2 text-right text-muted-foreground">
                        {(s.ai_assessment?.criterion_scores?.[name] ?? 0).toFixed(1)}
                      </td>
                    ))}
                    <td className="py-2.5 pl-3 text-muted-foreground">
                      {expanded === s.proposal_id ? (
                        <ChevronDown className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5" />
                      )}
                    </td>
                  </tr>
                  {expanded === s.proposal_id && (
                    <tr>
                      <td colSpan={99} className="pb-3 pt-1 px-0">
                        <div className="bg-muted/20 rounded-md p-4 space-y-4">
                          <p className="text-sm">{s.ai_assessment?.overall_assessment}</p>

                          {/* Score bar chart */}
                          {Object.keys(s.ai_assessment?.criterion_scores ?? {}).length > 0 && (
                            <div>
                              <p className="text-xs font-semibold text-muted-foreground mb-2">Scores by Criterion</p>
                              <div className="space-y-1.5">
                                {criteriaEntries.map(([name]) => {
                                  const score = s.ai_assessment?.criterion_scores?.[name] ?? 0;
                                  const pct = (score / 10) * 100;
                                  const color =
                                    score >= 7 ? "bg-green-500" : score >= 5 ? "bg-amber-400" : "bg-red-400";
                                  return (
                                    <div key={name} className="flex items-center gap-2">
                                      <span className="text-xs text-muted-foreground w-28 truncate shrink-0">{name}</span>
                                      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                                        <div
                                          className={`h-full rounded-full ${color} transition-all`}
                                          style={{ width: `${pct}%` }}
                                        />
                                      </div>
                                      <span className="text-xs font-mono font-semibold w-8 text-right">{score.toFixed(1)}</span>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          <div className="grid grid-cols-2 gap-4">
                            {s.ai_assessment?.strengths?.length > 0 && (
                              <div>
                                <p className="text-xs font-semibold text-green-700 mb-1">Strengths</p>
                                <ul className="space-y-0.5">
                                  {s.ai_assessment.strengths.map((str, i) => (
                                    <li key={i} className="text-xs text-muted-foreground flex gap-1.5">
                                      <span className="text-green-500 mt-0.5">+</span>
                                      {str}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {s.ai_assessment?.weaknesses?.length > 0 && (
                              <div>
                                <p className="text-xs font-semibold text-red-700 mb-1">Weaknesses</p>
                                <ul className="space-y-0.5">
                                  {s.ai_assessment.weaknesses.map((w, i) => (
                                    <li key={i} className="text-xs text-muted-foreground flex gap-1.5">
                                      <span className="text-red-500 mt-0.5">−</span>
                                      {w}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                          {s.ai_assessment?.recommendation && (
                            <p className="text-xs italic text-muted-foreground border-t pt-2">
                              {s.ai_assessment.recommendation}
                            </p>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Section>
  );
}

// ── Contract Viewer ───────────────────────────────────────────────────────────

const CONTRACT_SECTION_LABELS: Record<string, string> = {
  scope: "Scope of Work",
  payment_terms: "Payment Terms",
  milestones: "Milestones",
  legal_clauses: "Legal Clauses",
  termination_clauses: "Termination",
};

export function ContractViewer({ contract, procurementId, revisions }: { contract: ContractResult; procurementId: string; revisions?: DocumentRevision[] }) {
  const sections = Object.entries(contract.draft_content).filter(
    ([k]) => k !== "supplier_name"
  );
  const [activeSection, setActiveSection] = useState(sections[0]?.[0] ?? "");
  const [downloading, setDownloading] = useState(false);

  async function handleDownload() {
    setDownloading(true);
    const safe = contract.supplier_name.replace(/\s+/g, "_").replace(/\//g, "_");
    const filename = `contract_${safe}_v${contract.version}.docx`;
    try {
      await api.results.downloadContract(procurementId, filename);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Section
      icon={<FileCheck className="h-4 w-4 text-green-600" />}
      title={`Contract — ${contract.supplier_name}`}
      badge={contract.status === "APPROVED" ? "Approved" : contract.status}
      defaultOpen
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex gap-1 flex-wrap">
            {sections.map(([key]) => (
              <button
                key={key}
                onClick={() => setActiveSection(key)}
                className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                  activeSection === key
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                }`}
              >
                {CONTRACT_SECTION_LABELS[key] ?? key}
              </button>
            ))}
          </div>
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            {downloading ? "Downloading…" : "Download DOCX"}
          </button>
        </div>

        {sections.map(([key, content]) =>
          activeSection === key ? (
            <div key={key} className="bg-muted/20 rounded-md p-4">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                {CONTRACT_SECTION_LABELS[key] ?? key}
              </h4>
              <div className="text-sm leading-relaxed whitespace-pre-line prose-sm max-w-none">
                {typeof content === "string" ? content : JSON.stringify(content, null, 2)}
              </div>
            </div>
          ) : null
        )}

        {revisions && revisions.length > 0 && (
          <RevisionTimeline revisions={revisions} />
        )}
      </div>
    </Section>
  );
}
