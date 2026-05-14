"use client";

export interface SSEHandlers {
  onNodeStart?: (data: { node: string }) => void;
  onNodeEnd?: (data: { node: string; latency_ms: number }) => void;
  onStreamChunk?: (data: { node: string; chunk: string }) => void;
  onInterrupt?: (data: { node: string; data: unknown }) => void;
  onWorkflowDone?: (data: { status: string; thread_id: string }) => void;
  onError?: (data: { message: string }) => void;
}

export function connectSSE(url: string, handlers: SSEHandlers): EventSource {
  const token = localStorage.getItem("procura_token");
  const fullUrl = token ? `${url}&token=${token}` : url;
  const source = new EventSource(fullUrl);

  source.addEventListener("node_start", (e) => {
    handlers.onNodeStart?.(JSON.parse(e.data));
  });
  source.addEventListener("node_end", (e) => {
    handlers.onNodeEnd?.(JSON.parse(e.data));
  });
  source.addEventListener("stream_chunk", (e) => {
    handlers.onStreamChunk?.(JSON.parse(e.data));
  });
  source.addEventListener("interrupt", (e) => {
    handlers.onInterrupt?.(JSON.parse(e.data));
    source.close();
  });
  source.addEventListener("workflow_done", (e) => {
    handlers.onWorkflowDone?.(JSON.parse(e.data));
    source.close();
  });
  source.addEventListener("error", (e) => {
    if ((e as MessageEvent).data) {
      handlers.onError?.(JSON.parse((e as MessageEvent).data));
    }
    source.close();
  });

  return source;
}

/**
 * Reads SSE events from a fetch Response body (for POST-based streams like /resume).
 * Non-blocking — starts reading and returns immediately. Call with the handlers you'd
 * pass to connectSSE; the same event names are dispatched.
 */
export function readSSEResponse(response: Response, handlers: SSEHandlers): void {
  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  function dispatch(eventType: string, rawData: string) {
    try {
      const data = JSON.parse(rawData);
      switch (eventType) {
        case "node_start": handlers.onNodeStart?.(data); break;
        case "node_end": handlers.onNodeEnd?.(data); break;
        case "stream_chunk": handlers.onStreamChunk?.(data); break;
        case "interrupt": handlers.onInterrupt?.(data); break;
        case "workflow_done": handlers.onWorkflowDone?.(data); break;
        case "error": handlers.onError?.(data); break;
      }
    } catch {
      // malformed event — skip
    }
  }

  async function pump() {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      // SSE blocks are separated by \n\n
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";

      for (const block of blocks) {
        if (!block.trim()) continue;
        const eventMatch = block.match(/^event: (.+)$/m);
        const dataMatch = block.match(/^data: (.+)$/m);
        if (dataMatch) {
          dispatch(eventMatch?.[1] ?? "message", dataMatch[1]);
        }
      }
    }
  }

  pump().catch((err) => handlers.onError?.({ message: String(err) }));
}
