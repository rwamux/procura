"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, GitBranch, RotateCcw } from "lucide-react";
import { CheckpointItem } from "@/types";
import { formatDateTime } from "@/lib/utils";

const SOURCE_LABELS: Record<string, { label: string; className: string }> = {
  loop:   { label: "Executed",      className: "bg-slate-100 text-slate-600" },
  fork:   { label: "Replay branch", className: "bg-indigo-100 text-indigo-700" },
  update: { label: "Updated",       className: "bg-amber-100 text-amber-700" },
};

function nodeLabel(name: string | null | undefined): string {
  if (!name) return null as unknown as string;
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function CheckpointHistory({
  checkpoints,
  onReplay,
}: {
  checkpoints: CheckpointItem[];
  onReplay?: (checkpointId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [replayingId, setReplayingId] = useState<string | null>(null);

  if (checkpoints.length === 0) return null;

  const replayable = checkpoints.filter((cp) => cp.next.length > 0 && cp.checkpoint_id);
  const newest = checkpoints[checkpoints.length - 1];

  async function handleReplay(cpId: string) {
    if (!onReplay) return;
    setReplayingId(cpId);
    try {
      await onReplay(cpId);
    } finally {
      setReplayingId(null);
    }
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-muted/20 hover:bg-muted/40 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4 text-indigo-500" />
          <span className="text-sm font-medium">Execution History</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-medium">
            {checkpoints.length} checkpoints
          </span>
          {onReplay && replayable.length > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">
              {replayable.length} replayable
            </span>
          )}
        </div>
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {open && (
        <div className="max-h-96 overflow-y-auto">
          {onReplay && replayable.length > 0 && (
            <p className="px-4 py-2 text-xs text-muted-foreground bg-indigo-50/60 border-b">
              LangGraph time travel — click <strong>Replay</strong> to re-run the workflow from any past checkpoint.
            </p>
          )}

          <div className="divide-y">
            {/* Display oldest-first (index 0 = first step executed) */}
            {[...checkpoints].reverse().map((cp, i, arr) => {
              const isNewest = cp === newest;
              const label = nodeLabel(cp.node);
              const src = SOURCE_LABELS[cp.source] ?? { label: cp.source, className: "bg-muted text-muted-foreground" };
              const canReplay = onReplay && cp.checkpoint_id && cp.next.length > 0;

              return (
                <div key={cp.checkpoint_id || i} className={`px-4 py-3 flex items-start gap-3 ${isNewest ? "bg-muted/10" : ""}`}>
                  {/* Timeline connector */}
                  <div className="flex flex-col items-center pt-1 shrink-0" style={{ width: 20 }}>
                    <div className={`h-2 w-2 rounded-full border-2 ${isNewest ? "border-indigo-500 bg-indigo-500" : "border-border bg-background"}`} />
                    {i < arr.length - 1 && <div className="w-px flex-1 bg-border mt-1" style={{ minHeight: 20 }} />}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium">
                          {label ?? <span className="text-muted-foreground italic">Unknown node</span>}
                        </span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${src.className}`}>
                          {src.label}
                        </span>
                        {isNewest && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500 text-white font-medium">
                            latest
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs text-muted-foreground">
                          {cp.created_at ? formatDateTime(cp.created_at) : "—"}
                        </span>
                        {canReplay && (
                          <button
                            onClick={() => handleReplay(cp.checkpoint_id)}
                            disabled={replayingId === cp.checkpoint_id}
                            title="Re-run the workflow from this point"
                            className="flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded border border-indigo-200 text-indigo-600 hover:bg-indigo-50 disabled:opacity-50 transition-colors"
                          >
                            <RotateCcw className="h-2.5 w-2.5" />
                            {replayingId === cp.checkpoint_id ? "Running…" : "Replay"}
                          </button>
                        )}
                      </div>
                    </div>

                    <p className="text-xs text-muted-foreground mt-0.5">
                      Step {cp.step}
                      {cp.source === "fork" && " · branched from replay"}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
