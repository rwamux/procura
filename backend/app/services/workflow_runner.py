import json
import time
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import datetime, timezone
from typing import Any

from langgraph.graph.state import CompiledStateGraph as CompiledGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.enums import WorkflowEventType, WorkflowRunStatus
from app.models.workflow import WorkflowEvent, WorkflowRun


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _persist_event(
    db: AsyncSession,
    run: WorkflowRun,
    node_name: str,
    event_type: str,
    payload: dict | None = None,
    latency_ms: int | None = None,
    tokens_used: int | None = None,
) -> None:
    evt = WorkflowEvent(
        procurement_id=run.procurement_id,
        run_id=run.id,
        workflow_type=run.workflow_type,
        thread_id=run.thread_id,
        node_name=node_name,
        event_type=event_type,
        payload=payload,
        latency_ms=latency_ms,
        tokens_used=tokens_used,
    )
    db.add(evt)
    await db.commit()


def _extract_interrupt(output: Any) -> dict | None:
    if not isinstance(output, dict):
        return None
    items = output.get("__interrupt__")
    if not items:
        return None
    first = items[0]
    return first.value if hasattr(first, "value") else (first if isinstance(first, dict) else {})


def _extract_tokens(output: Any) -> int | None:
    if output is None:
        return None
    if hasattr(output, "usage_metadata") and output.usage_metadata:
        um = output.usage_metadata
        return um.get("total_tokens") if isinstance(um, dict) else getattr(um, "total_tokens", None)
    if hasattr(output, "response_metadata") and output.response_metadata:
        tu = output.response_metadata.get("token_usage") or output.response_metadata.get("usage", {})
        if isinstance(tu, dict):
            return tu.get("total_tokens")
    return None


async def _check_state_interrupt(graph: CompiledGraph, config: dict) -> dict | None:
    try:
        snapshot = await graph.aget_state(config)
        if not snapshot.next:
            return None
        interrupt_value: dict = {}
        node_name = snapshot.next[0]
        if snapshot.tasks:
            for task in snapshot.tasks:
                interrupts = getattr(task, "interrupts", None)
                if interrupts:
                    iv = interrupts[0]
                    interrupt_value = iv.value if hasattr(iv, "value") else {}
                    break
        return {"node": node_name, "data": interrupt_value}
    except Exception:
        return None


def _build_node_end_payload(
    name: str,
    latency: int | None,
    tokens: int | None,
    llm_run_id: str | None,
) -> dict:
    payload: dict = {"node": name, "latency_ms": latency}
    if tokens:
        payload["tokens_used"] = tokens
    if llm_run_id and settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
        payload["langsmith_run_id"] = llm_run_id
        payload["langsmith_url"] = (
            f"https://smith.langchain.com/projects/p/{settings.LANGCHAIN_PROJECT}/runs/{llm_run_id}"
        )
    return payload


async def _process_events(
    events_iter: AsyncIterator,
    graph: CompiledGraph,
    config: dict,
    run: WorkflowRun,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    node_start_times: dict[str, float] = {}
    run_id_to_node: dict[str, str] = {}
    node_tokens: dict[str, int] = {}
    node_llm_run_ids: dict[str, str] = {}
    interrupted = False

    try:
        async for event in events_iter:
            kind = event.get("event", "")
            name = event.get("name", "unknown")
            data = event.get("data", {})
            event_run_id = event.get("run_id", "")
            parent_ids: list[str] = event.get("parent_ids", [])

            if kind == "on_chain_start" and name not in ("LangGraph", "__start__"):
                node_start_times[name] = time.monotonic()
                run_id_to_node[event_run_id] = name
                payload = {"node": name}
                await _persist_event(db, run, name, WorkflowEventType.NODE_START, payload)
                yield _sse("node_start", payload)

            elif kind == "on_chain_end":
                output = data.get("output", {})

                if name not in ("LangGraph", "__start__"):
                    latency = None
                    if name in node_start_times:
                        latency = int((time.monotonic() - node_start_times.pop(name)) * 1000)
                    tokens = node_tokens.pop(name, None)
                    llm_run_id = node_llm_run_ids.pop(name, None)
                    node_payload = _build_node_end_payload(name, latency, tokens, llm_run_id)
                    await _persist_event(db, run, name, WorkflowEventType.NODE_END, node_payload, latency, tokens)
                    yield _sse("node_end", node_payload)

                interrupt_value = _extract_interrupt(output)
                if interrupt_value is not None and not interrupted:
                    interrupt_node = name if name not in ("LangGraph", "__start__") else "workflow"
                    interrupt_payload = {"node": interrupt_node, "data": interrupt_value}
                    run.status = WorkflowRunStatus.INTERRUPTED
                    await db.commit()
                    await _persist_event(db, run, interrupt_node, WorkflowEventType.INTERRUPT, interrupt_payload)
                    yield _sse("interrupt", interrupt_payload)
                    interrupted = True
                    return

            elif kind == "on_chat_model_stream":
                chunk = data.get("chunk", {})
                content = getattr(chunk, "content", "") if hasattr(chunk, "content") else ""
                if content:
                    yield _sse("stream_chunk", {"node": name, "chunk": content})

            elif kind == "on_chat_model_end":
                output = data.get("output")
                tokens = _extract_tokens(output)
                parent_node = next(
                    (run_id_to_node[pid] for pid in parent_ids if pid in run_id_to_node), None
                )
                if parent_node:
                    if tokens:
                        node_tokens[parent_node] = node_tokens.get(parent_node, 0) + tokens
                    node_llm_run_ids[parent_node] = event_run_id

        interrupt_info = await _check_state_interrupt(graph, config)
        if interrupt_info:
            run.status = WorkflowRunStatus.INTERRUPTED
            await db.commit()
            await _persist_event(db, run, interrupt_info["node"], WorkflowEventType.INTERRUPT, interrupt_info)
            yield _sse("interrupt", interrupt_info)
        else:
            run.status = WorkflowRunStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await _persist_event(db, run, "workflow", WorkflowEventType.WORKFLOW_COMPLETE, {"status": "COMPLETED"})
            yield _sse("workflow_done", {"status": "COMPLETED", "thread_id": run.thread_id})

    except Exception as e:
        run.status = WorkflowRunStatus.FAILED
        await db.commit()
        await _persist_event(db, run, "workflow", WorkflowEventType.ERROR, {"error": str(e)})
        yield _sse("error", {"message": str(e)})


async def stream_graph_run(
    graph: CompiledGraph,
    initial_input: dict,
    run: WorkflowRun,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    config = {"configurable": {"thread_id": run.thread_id}}
    run.status = WorkflowRunStatus.RUNNING
    await db.commit()

    events_iter = graph.astream_events(initial_input, config=config, version="v2")
    async for chunk in _process_events(events_iter, graph, config, run, db):
        yield chunk


async def _resume_stream(
    graph: CompiledGraph,
    command: Any,
    config: dict,
    run: WorkflowRun,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    run.status = WorkflowRunStatus.RUNNING
    await db.commit()
    await _persist_event(db, run, "workflow", WorkflowEventType.RESUME, {})

    events_iter = graph.astream_events(command, config=config, version="v2")
    async for chunk in _process_events(events_iter, graph, config, run, db):
        yield chunk


async def stream_graph_replay(
    graph: CompiledGraph,
    thread_id: str,
    checkpoint_id: str,
    run: WorkflowRun,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    config = {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}
    run.status = WorkflowRunStatus.RUNNING
    await db.commit()
    await _persist_event(db, run, "workflow", "REPLAY", {"checkpoint_id": checkpoint_id})
    yield _sse("replay_start", {"checkpoint_id": checkpoint_id, "thread_id": thread_id})

    events_iter = graph.astream_events(None, config=config, version="v2")
    async for chunk in _process_events(events_iter, graph, config, run, db):
        yield chunk
