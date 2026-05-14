"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Procurement, WorkflowRun, STAGE_LABELS } from "@/types";
import { formatDate } from "@/lib/utils";

interface RunWithProcurement {
  run: WorkflowRun;
  procurement: Procurement;
}

const STATUS_COLORS: Record<string, string> = {
  RUNNING: "bg-blue-100 text-blue-700",
  INTERRUPTED: "bg-amber-100 text-amber-700",
  PENDING: "bg-slate-100 text-slate-600",
  COMPLETED: "bg-green-100 text-green-700",
  FAILED: "bg-red-100 text-red-700",
};

export default function WorkflowsPage() {
  const [items, setItems] = useState<RunWithProcurement[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.procurements.list({ limit: 50 }).then(async (res) => {
      const pairs: RunWithProcurement[] = [];
      await Promise.all(
        res.items.map(async (p) => {
          const stages = ["RFP", "PROPOSAL_INTAKE", "EVALUATION", "CONTRACT"] as const;
          await Promise.all(
            stages.map(async (wt) => {
              try {
                const run = await api.workflows.getActiveRun(p.id, wt);
                if (run) pairs.push({ run, procurement: p });
              } catch {
                // no run for this workflow type
              }
            })
          );
        })
      );
      pairs.sort((a, b) =>
        new Date(b.run.started_at).getTime() - new Date(a.run.started_at).getTime()
      );
      setItems(pairs);
    }).finally(() => setLoading(false));
  }, []);

  const active = items.filter((i) => ["RUNNING", "INTERRUPTED", "PENDING"].includes(i.run.status));
  const recent = items.filter((i) => ["COMPLETED", "FAILED"].includes(i.run.status));

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Active Workflows</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {active.length} active · {recent.length} recently completed
        </p>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-muted/50 rounded-lg animate-pulse" />)}
        </div>
      ) : items.length === 0 ? (
        <div className="border border-dashed rounded-lg p-16 text-center">
          <p className="text-muted-foreground text-sm">No workflow runs yet.</p>
          <Link href="/procurements" className="text-sm font-medium mt-2 inline-block hover:underline">
            Go to Procurements →
          </Link>
        </div>
      ) : (
        <div className="space-y-6">
          {active.length > 0 && (
            <section>
              <h2 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wide">In Progress</h2>
              <RunList items={active} />
            </section>
          )}
          {recent.length > 0 && (
            <section>
              <h2 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wide">Recent</h2>
              <RunList items={recent} />
            </section>
          )}
        </div>
      )}
    </div>
  );
}

function RunList({ items }: { items: RunWithProcurement[] }) {
  return (
    <div className="border rounded-lg divide-y overflow-hidden">
      {items.map(({ run, procurement }) => (
        <Link
          key={run.id}
          href={`/procurements/${procurement.id}`}
          className="flex items-center justify-between px-5 py-4 hover:bg-muted/30 transition-colors"
        >
          <div>
            <p className="text-sm font-medium">{procurement.title}</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {STAGE_LABELS[run.workflow_type as keyof typeof STAGE_LABELS]} · Started {formatDate(run.started_at)}
            </p>
          </div>
          <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${STATUS_COLORS[run.status] ?? "bg-muted"}`}>
            {run.status}
          </span>
        </Link>
      ))}
    </div>
  );
}
