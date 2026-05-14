"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, TrendingUp, Clock, CheckCircle2, ArrowRight, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/components/providers";
import { Procurement, STAGE_LABELS } from "@/types";
import { formatDate } from "@/lib/utils";

const STAGE_COLORS: Record<string, string> = {
  RFP: "bg-blue-100 text-blue-700 ring-blue-200",
  PROPOSAL_INTAKE: "bg-violet-100 text-violet-700 ring-violet-200",
  EVALUATION: "bg-amber-100 text-amber-700 ring-amber-200",
  CONTRACT: "bg-orange-100 text-orange-700 ring-orange-200",
  FINALIZED: "bg-emerald-100 text-emerald-700 ring-emerald-200",
};

const STAGE_DOT: Record<string, string> = {
  RFP: "bg-blue-500",
  PROPOSAL_INTAKE: "bg-violet-500",
  EVALUATION: "bg-amber-500",
  CONTRACT: "bg-orange-500",
  FINALIZED: "bg-emerald-500",
};

export default function DashboardPage() {
  const { user } = useAuth();
  const [procurements, setProcurements] = useState<Procurement[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.procurements.list({ limit: 6 }).then((res) => {
      setProcurements(res.items);
      setTotal(res.total);
    }).finally(() => setLoading(false));
  }, []);

  const active = procurements.filter((p) => p.status === "ACTIVE").length;
  const completed = procurements.filter((p) => p.status === "COMPLETED" || p.stage === "FINALIZED").length;

  const firstName = user?.name?.split(" ")[0] ?? "there";

  return (
    <div className="p-8 max-w-6xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold">
            Good day, {firstName} 👋
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Here&apos;s what&apos;s happening with your procurement pipeline.
          </p>
        </div>
        <Link
          href="/procurements/new"
          className="flex items-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors shadow-sm"
        >
          <Plus className="h-4 w-4" />
          New Procurement
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard
          icon={<TrendingUp className="h-5 w-5" />}
          label="Total Procurements"
          value={total}
          color="indigo"
          description="All time"
        />
        <StatCard
          icon={<Zap className="h-5 w-5" />}
          label="In Progress"
          value={active}
          color="amber"
          description="Currently active"
        />
        <StatCard
          icon={<CheckCircle2 className="h-5 w-5" />}
          label="Completed"
          value={completed}
          color="emerald"
          description="Successfully closed"
        />
      </div>

      {/* Recent procurements */}
      <div className="bg-card border rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b bg-muted/20">
          <h2 className="text-sm font-semibold">Recent Procurements</h2>
          <Link
            href="/procurements"
            className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 font-medium transition-colors"
          >
            View all <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {loading ? (
          <div className="p-4 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 bg-muted/40 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : procurements.length === 0 ? (
          <div className="p-16 text-center">
            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-3">
              <TrendingUp className="h-6 w-6 text-primary" />
            </div>
            <p className="text-sm font-medium mb-1">No procurements yet</p>
            <p className="text-xs text-muted-foreground mb-4">
              Start an AI-powered procurement workflow
            </p>
            <Link
              href="/procurements/new"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary/80"
            >
              Create your first <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        ) : (
          <div className="divide-y">
            {procurements.map((p) => (
              <Link
                key={p.id}
                href={`/procurements/${p.id}`}
                className="flex items-center justify-between px-6 py-4 hover:bg-muted/20 transition-colors group"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`h-2 w-2 rounded-full shrink-0 ${STAGE_DOT[p.stage] ?? "bg-muted-foreground"}`} />
                  <div className="min-w-0">
                    <p className="text-sm font-medium group-hover:text-primary transition-colors truncate">
                      {p.title}
                    </p>
                    <p className="text-xs text-muted-foreground">{formatDate(p.created_at)}</p>
                  </div>
                </div>
                <span className={`text-xs px-2.5 py-1 rounded-full font-medium ring-1 shrink-0 ml-4 ${STAGE_COLORS[p.stage] ?? "bg-muted text-muted-foreground ring-border"}`}>
                  {STAGE_LABELS[p.stage]}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon, label, value, color, description,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: "indigo" | "amber" | "emerald";
  description: string;
}) {
  const styles = {
    indigo: {
      bg: "bg-indigo-50 border-indigo-100",
      icon: "bg-indigo-100 text-indigo-600",
      value: "text-indigo-700",
    },
    amber: {
      bg: "bg-amber-50 border-amber-100",
      icon: "bg-amber-100 text-amber-600",
      value: "text-amber-700",
    },
    emerald: {
      bg: "bg-emerald-50 border-emerald-100",
      icon: "bg-emerald-100 text-emerald-600",
      value: "text-emerald-700",
    },
  }[color];

  return (
    <div className={`border rounded-xl p-5 ${styles.bg}`}>
      <div className="flex items-start justify-between mb-3">
        <div className={`h-9 w-9 rounded-lg flex items-center justify-center ${styles.icon}`}>
          {icon}
        </div>
      </div>
      <p className={`text-3xl font-bold mb-0.5 ${styles.value}`}>{value}</p>
      <p className="text-sm font-medium text-foreground/80">{label}</p>
      <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
    </div>
  );
}
