"use client";

import { AlertCircle, CheckCircle2, Circle, ExternalLink, Layers, PauseCircle, Zap } from "lucide-react";
import { WorkflowEvent } from "@/types";
import { formatDateTime } from "@/lib/utils";

// Nodes that fan-out in parallel via the Send API
const FANOUT_NODES = new Set(["score_proposal", "generate_section", "extract_proposal"]);

interface EventGroup {
  node_name: string;
  events: WorkflowEvent[];
  isParallel: boolean;
}

function groupEvents(events: WorkflowEvent[]): EventGroup[] {
  // Collapse consecutive events with the same node_name into groups
  const groups: EventGroup[] = [];
  for (const evt of events) {
    const last = groups[groups.length - 1];
    if (last && last.node_name === evt.node_name) {
      last.events.push(evt);
    } else {
      groups.push({ node_name: evt.node_name, events: [evt], isParallel: false });
    }
  }
  // Mark groups with more than one event on a fanout node as parallel
  for (const g of groups) {
    if (FANOUT_NODES.has(g.node_name) && g.events.length > 1) {
      g.isParallel = true;
    }
  }
  return groups;
}

function nodeLabel(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function GroupRow({ group }: { group: EventGroup }) {
  const starts = group.events.filter((e) => e.event_type === "NODE_START");
  const ends = group.events.filter((e) => e.event_type === "NODE_END");

  if (group.isParallel) {
    const totalTokens = ends.reduce((sum, e) => sum + (e.payload?.tokens_used ?? 0), 0);
    const totalLatency = ends.reduce((sum, e) => sum + (e.latency_ms ?? 0), 0);
    const langsmithUrls = ends
      .map((e) => e.payload?.langsmith_url)
      .filter(Boolean) as string[];

    return (
      <div className="px-4 py-2.5 bg-violet-50 border-l-2 border-violet-400">
        <div className="flex items-center gap-2 mb-1">
          <Layers className="h-3.5 w-3.5 text-violet-500 shrink-0" />
          <span className="text-sm font-medium text-violet-800">{nodeLabel(group.node_name)}</span>
          <span className="text-xs px-1.5 py-0.5 rounded-full bg-violet-200 text-violet-700 font-medium">
            × {starts.length} parallel
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground ml-6">
          {totalLatency > 0 && <span>{totalLatency}ms total</span>}
          {totalTokens > 0 && <span>{totalTokens.toLocaleString()} tokens</span>}
          {langsmithUrls.length > 0 && (
            <span className="flex gap-1">
              {langsmithUrls.map((url, i) => (
                <a
                  key={i}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-0.5 text-blue-500 hover:text-blue-700"
                >
                  <ExternalLink className="h-3 w-3" />
                  {i + 1}
                </a>
              ))}
            </span>
          )}
        </div>
      </div>
    );
  }

  // Single event or non-fanout group — render each event individually
  return (
    <>
      {group.events.map((e) => (
        <SingleEventRow key={e.id} event={e} />
      ))}
    </>
  );
}

const EVENT_ICONS: Record<string, React.ReactNode> = {
  NODE_START: <Circle className="h-3.5 w-3.5 text-blue-400" />,
  NODE_END: <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />,
  INTERRUPT: <PauseCircle className="h-3.5 w-3.5 text-amber-500" />,
  RESUME: <Zap className="h-3.5 w-3.5 text-purple-500" />,
  ERROR: <AlertCircle className="h-3.5 w-3.5 text-destructive" />,
  WORKFLOW_COMPLETE: <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />,
};

function SingleEventRow({ event: e }: { event: WorkflowEvent }) {
  const tokens = e.payload?.tokens_used ?? e.tokens_used;
  const langsmithUrl = e.payload?.langsmith_url;
  const isEnd = e.event_type === "NODE_END";

  return (
    <div className="flex items-start gap-3 px-4 py-2.5">
      <div className="mt-0.5 shrink-0">
        {EVENT_ICONS[e.event_type] ?? <Circle className="h-3.5 w-3.5 text-muted-foreground" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium truncate">{nodeLabel(e.node_name)}</span>
          <div className="flex items-center gap-2 shrink-0">
            {isEnd && tokens != null && tokens > 0 && (
              <span className="text-xs text-muted-foreground/70">{tokens.toLocaleString()} tok</span>
            )}
            {isEnd && langsmithUrl && (
              <a
                href={langsmithUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500 hover:text-blue-700"
                title="View in LangSmith"
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
            <span className="text-xs text-muted-foreground">
              {e.latency_ms != null ? `${e.latency_ms}ms` : formatDateTime(e.created_at)}
            </span>
          </div>
        </div>
        <span className="text-xs text-muted-foreground">{e.event_type.replace(/_/g, " ")}</span>
      </div>
    </div>
  );
}

export function WorkflowExecutionViewer({
  events,
  liveNode,
  streamedText,
}: {
  events: WorkflowEvent[];
  liveNode?: string;
  streamedText?: string;
}) {
  const groups = groupEvents(events);

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/30 flex items-center justify-between">
        <h3 className="text-sm font-medium">Execution Trace</h3>
        {liveNode && (
          <span className="flex items-center gap-1.5 text-xs text-blue-600">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
            Running: {nodeLabel(liveNode)}
          </span>
        )}
      </div>

      <div className="divide-y max-h-80 overflow-y-auto">
        {groups.length === 0 && !liveNode ? (
          <p className="text-sm text-muted-foreground px-4 py-6 text-center">No events yet</p>
        ) : (
          <>
            {groups.map((g, i) => (
              <GroupRow key={i} group={g} />
            ))}
            {streamedText && (
              <div className="px-4 py-3 bg-blue-50">
                <p className="text-xs text-muted-foreground mb-1">Generating...</p>
                <p className="text-sm font-mono whitespace-pre-wrap line-clamp-6">{streamedText}</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
