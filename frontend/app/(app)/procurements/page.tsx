"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { api } from "@/lib/api";
import { Procurement, STAGE_LABELS } from "@/types";
import { formatDate } from "@/lib/utils";

const STAGE_COLORS: Record<string, string> = {
  RFP: "bg-blue-100 text-blue-700 ring-1 ring-blue-200",
  PROPOSAL_INTAKE: "bg-violet-100 text-violet-700 ring-1 ring-violet-200",
  EVALUATION: "bg-amber-100 text-amber-700 ring-1 ring-amber-200",
  CONTRACT: "bg-orange-100 text-orange-700 ring-1 ring-orange-200",
  FINALIZED: "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200",
};

const STAGE_DOT: Record<string, string> = {
  RFP: "bg-blue-500",
  PROPOSAL_INTAKE: "bg-violet-500",
  EVALUATION: "bg-amber-500",
  CONTRACT: "bg-orange-500",
  FINALIZED: "bg-emerald-500",
};

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200",
  COMPLETED: "bg-slate-100 text-slate-600 ring-1 ring-slate-200",
  CANCELLED: "bg-red-100 text-red-700 ring-1 ring-red-200",
};

export default function ProcurementsPage() {
  const [items, setItems] = useState<Procurement[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.procurements.list({ limit: 50 }).then((res) => {
      setItems(res.items);
      setTotal(res.total);
    }).finally(() => setLoading(false));
  }, []);

  const filtered = items.filter((p) =>
    p.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">Procurements</h1>
          <p className="text-sm text-muted-foreground mt-1">{total} total</p>
        </div>
        <Link
          href="/procurements/new"
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Procurement
        </Link>
      </div>

      <div className="relative mb-4">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search procurements..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-20 bg-muted/40 rounded-xl animate-pulse" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="border border-dashed rounded-xl p-16 text-center bg-card">
          <p className="text-muted-foreground text-sm">
            {search ? "No procurements match your search." : "No procurements yet."}
          </p>
          {!search && (
            <Link href="/procurements/new" className="text-sm font-medium text-primary mt-2 inline-block hover:text-primary/80">
              Create your first procurement →
            </Link>
          )}
        </div>
      ) : (
        <div className="bg-card border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/20">
                <th className="text-left px-5 py-3.5 font-medium text-muted-foreground text-xs uppercase tracking-wide">Title</th>
                <th className="text-left px-5 py-3.5 font-medium text-muted-foreground text-xs uppercase tracking-wide">Stage</th>
                <th className="text-left px-5 py-3.5 font-medium text-muted-foreground text-xs uppercase tracking-wide">Status</th>
                <th className="text-left px-5 py-3.5 font-medium text-muted-foreground text-xs uppercase tracking-wide">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filtered.map((p) => (
                <tr key={p.id} className="hover:bg-muted/20 transition-colors group">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-2.5">
                      <span className={`h-2 w-2 rounded-full shrink-0 ${STAGE_DOT[p.stage] ?? "bg-muted-foreground"}`} />
                      <div>
                        <Link href={`/procurements/${p.id}`} className="font-medium hover:text-primary transition-colors">
                          {p.title}
                        </Link>
                        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{p.business_objective}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${STAGE_COLORS[p.stage] ?? "bg-muted text-muted-foreground"}`}>
                      {STAGE_LABELS[p.stage]}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${STATUS_COLORS[p.status] ?? "bg-muted text-muted-foreground"}`}>
                      {p.status}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-muted-foreground text-xs">{formatDate(p.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
