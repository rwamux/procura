import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, get_current_user_sse
from app.database import get_db
from app.enums import WorkflowRunStatus, WorkflowType
from app.models.procurement import Procurement
from app.models.user import User
from app.models.workflow import WorkflowEvent, WorkflowModelConfig, WorkflowRun
from app.schemas.workflow import (
    ReplayRequest,
    WorkflowEventOut,
    WorkflowModelConfigOut,
    WorkflowModelConfigUpdate,
    WorkflowResumeRequest,
    WorkflowRunOut,
    WorkflowStartRequest,
)
from app.workflows.checkpointer import get_checkpointer
from app.workflows.rfp.graph import build_rfp_graph
from app.workflows.rfp.state import RFPState
from app.workflows.proposal_intake.graph import build_proposal_intake_graph
from app.workflows.proposal_intake.state import ProposalIntakeState
from app.workflows.evaluation.graph import build_evaluation_graph
from app.workflows.evaluation.state import EvaluationState
from app.workflows.contract.graph import build_contract_graph
from app.workflows.contract.state import CONTRACT_SECTIONS, ContractState
from app.services.workflow_runner import (
    _check_state_interrupt,
    _resume_stream,
    stream_graph_replay,
    stream_graph_run,
)

router = APIRouter(prefix="/procurements/{procurement_id}/workflows", tags=["workflows"])

_WORKFLOW_BUILDERS = {
    WorkflowType.RFP: build_rfp_graph,
    WorkflowType.PROPOSAL_INTAKE: build_proposal_intake_graph,
    WorkflowType.EVALUATION: build_evaluation_graph,
    WorkflowType.CONTRACT: build_contract_graph,
}


def _get_graph(workflow_type: str):
    builder_fn = _WORKFLOW_BUILDERS.get(WorkflowType(workflow_type))
    if not builder_fn:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_type}' not found")
    return builder_fn().compile(checkpointer=get_checkpointer())


def _build_initial_state(
    workflow_type: str,
    procurement_id: uuid.UUID,
    thread_id: str,
    model_id: str,
    temperature: float,
) -> dict:
    pid = str(procurement_id)
    if workflow_type == WorkflowType.RFP:
        return RFPState(
            procurement_id=pid,
            thread_id=thread_id,
            model_id=model_id,
            temperature=temperature,
            requirements=None,
            rfp_draft=None,
            validation_error=None,
            validation_attempts=0,
            revision_history=[],
            revision_request=None,
            approval_action=None,
            approval_comments=None,
            status="STARTED",
            error=None,
        )
    if workflow_type == WorkflowType.PROPOSAL_INTAKE:
        return ProposalIntakeState(
            procurement_id=pid,
            thread_id=thread_id,
            model_id=model_id,
            temperature=temperature,
            proposals_to_process=[],
            extracted_proposals=[],
            failed_extractions=[],
            reprocess_ids=None,
            review_approved=None,
            status="STARTED",
            error=None,
        )
    if workflow_type == WorkflowType.EVALUATION:
        return EvaluationState(
            procurement_id=pid,
            evaluation_id="",
            thread_id=thread_id,
            model_id=model_id,
            temperature=temperature,
            evaluation_weights={},
            proposals=[],
            scored_proposals=[],
            rankings=None,
            recommendation_proposal_id=None,
            recommendation_rationale=None,
            approval_action=None,
            approval_comments=None,
            manual_override_proposal_id=None,
            status="STARTED",
            error=None,
        )
    if workflow_type == WorkflowType.CONTRACT:
        return ContractState(
            procurement_id=pid,
            thread_id=thread_id,
            model_id=model_id,
            temperature=temperature,
            approved_rfp={},
            selected_proposal={},
            supplier_name="",
            sections_to_generate=CONTRACT_SECTIONS,
            generated_sections={},
            assembled_contract=None,
            validation_error=None,
            validation_attempts=0,
            revision_history=[],
            revision_request=None,
            target_revision_sections=None,
            approval_action=None,
            approval_comments=None,
            status="STARTED",
            error=None,
        )
    raise HTTPException(status_code=400, detail=f"Unsupported workflow type: {workflow_type}")


async def _get_procurement(
    procurement_id: uuid.UUID, user: User, db: AsyncSession
) -> Procurement:
    result = await db.execute(
        select(Procurement).where(
            Procurement.id == procurement_id,
            Procurement.created_by == user.id,
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    return p


@router.post("/{workflow_type}/start", response_model=WorkflowRunOut)
async def start_workflow(
    procurement_id: uuid.UUID,
    workflow_type: str,
    payload: WorkflowStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_procurement(procurement_id, current_user, db)

    existing = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.procurement_id == procurement_id,
            WorkflowRun.workflow_type == workflow_type,
            WorkflowRun.status.in_(["PENDING", "RUNNING", "INTERRUPTED"]),
        )
    )
    for old_run in existing.scalars().all():
        old_run.status = WorkflowRunStatus.FAILED

    mc_result = await db.execute(
        select(WorkflowModelConfig).where(
            WorkflowModelConfig.procurement_id == procurement_id,
            WorkflowModelConfig.workflow_type == workflow_type,
        )
    )
    mc = mc_result.scalar_one_or_none()
    if mc:
        mc.model_id = payload.model_id
        mc.model_label = payload.model_label
        mc.temperature = payload.temperature
    else:
        mc = WorkflowModelConfig(
            procurement_id=procurement_id,
            workflow_type=workflow_type,
            model_id=payload.model_id,
            model_label=payload.model_label,
            temperature=payload.temperature,
        )
        db.add(mc)

    run = WorkflowRun(
        procurement_id=procurement_id,
        workflow_type=workflow_type,
        thread_id=str(uuid.uuid4()),
        status=WorkflowRunStatus.PENDING,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return WorkflowRunOut.model_validate(run)


@router.get("/{workflow_type}/stream")
async def stream_workflow(
    procurement_id: uuid.UUID,
    workflow_type: str,
    thread_id: str = Query(...),
    current_user: User = Depends(get_current_user_sse),
    db: AsyncSession = Depends(get_db),
):
    await _get_procurement(procurement_id, current_user, db)

    result = await db.execute(select(WorkflowRun).where(WorkflowRun.thread_id == thread_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    mc_result = await db.execute(
        select(WorkflowModelConfig).where(
            WorkflowModelConfig.procurement_id == procurement_id,
            WorkflowModelConfig.workflow_type == workflow_type,
        )
    )
    mc = mc_result.scalar_one_or_none()
    model_id = mc.model_id if mc else "anthropic/claude-3.5-sonnet"
    temperature = mc.temperature if mc else 0.3

    graph = _get_graph(workflow_type)
    initial_input = _build_initial_state(workflow_type, procurement_id, thread_id, model_id, temperature)

    async def generate():
        async for chunk in stream_graph_run(graph, initial_input, run, db):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{workflow_type}/resume")
async def resume_workflow(
    procurement_id: uuid.UUID,
    workflow_type: str,
    payload: WorkflowResumeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_procurement(procurement_id, current_user, db)

    result = await db.execute(select(WorkflowRun).where(WorkflowRun.thread_id == payload.thread_id))
    run = result.scalar_one_or_none()
    if not run or run.status != WorkflowRunStatus.INTERRUPTED:
        raise HTTPException(status_code=400, detail="No interrupted run found for this thread")

    graph = _get_graph(workflow_type)
    config = {"configurable": {"thread_id": payload.thread_id}}
    resume_data = {
        "action": payload.action,
        "comments": payload.comments,
        "revision_request": payload.revision_request,
        "manual_override_proposal_id": payload.manual_override_proposal_id,
        "reprocess_ids": payload.reprocess_ids,
        "target_sections": payload.target_sections,
    }

    async def generate():
        async for chunk in _resume_stream(graph, Command(resume=resume_data), config, run, db):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{workflow_type}/run", response_model=Optional[WorkflowRunOut])
async def get_active_run(
    procurement_id: uuid.UUID,
    workflow_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_procurement(procurement_id, current_user, db)
    result = await db.execute(
        select(WorkflowRun)
        .where(
            WorkflowRun.procurement_id == procurement_id,
            WorkflowRun.workflow_type == workflow_type,
        )
        .order_by(WorkflowRun.started_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    return WorkflowRunOut.model_validate(run) if run else None


@router.get("/{workflow_type}/events", response_model=list[WorkflowEventOut])
async def get_workflow_events(
    procurement_id: uuid.UUID,
    workflow_type: str,
    thread_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_procurement(procurement_id, current_user, db)
    query = select(WorkflowEvent).where(
        WorkflowEvent.procurement_id == procurement_id,
        WorkflowEvent.workflow_type == workflow_type,
    )
    if thread_id:
        query = query.where(WorkflowEvent.thread_id == thread_id)
    result = await db.execute(query.order_by(WorkflowEvent.created_at.asc()))
    return [WorkflowEventOut.model_validate(e) for e in result.scalars().all()]


@router.get("/{workflow_type}/interrupt")
async def get_interrupt_state(
    procurement_id: uuid.UUID,
    workflow_type: str,
    thread_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_procurement(procurement_id, current_user, db)
    graph = _get_graph(workflow_type)
    config = {"configurable": {"thread_id": thread_id}}
    interrupt_info = await _check_state_interrupt(graph, config)
    if not interrupt_info:
        raise HTTPException(status_code=404, detail="No pending interrupt found")
    return interrupt_info


@router.get("/{workflow_type}/checkpoints")
async def get_checkpoints(
    procurement_id: uuid.UUID,
    workflow_type: str,
    thread_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_procurement(procurement_id, current_user, db)

    # Load our own NODE_END events for this thread — used to label checkpoints
    # since LangGraph 1.x stores writes in a separate table, not in metadata
    events_result = await db.execute(
        select(WorkflowEvent)
        .where(
            WorkflowEvent.thread_id == thread_id,
            WorkflowEvent.event_type == "NODE_END",
        )
        .order_by(WorkflowEvent.created_at.asc())
    )
    node_events = [
        (e.created_at, e.node_name)
        for e in events_result.scalars().all()
        if e.node_name
    ]

    def node_for_timestamp(ts_str: str | None) -> str | None:
        if not ts_str or not node_events:
            return None
        try:
            cp_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            return None
        # Last NODE_END event that completed at or before the checkpoint was saved
        preceding = [(t, n) for t, n in node_events if t <= cp_ts]
        return preceding[-1][1] if preceding else None

    checkpointer = get_checkpointer()
    config = {"configurable": {"thread_id": thread_id}}
    raw = []
    try:
        async for cp_tuple in checkpointer.alist(config):
            cp_id = (cp_tuple.config or {}).get("configurable", {}).get("checkpoint_id", "")
            metadata = cp_tuple.metadata or {}
            source = metadata.get("source", "")
            if source == "input":
                continue
            ts = (cp_tuple.checkpoint or {}).get("ts")
            raw.append({
                "checkpoint_id": cp_id,
                "step": metadata.get("step", 0),
                "source": source,
                "node": node_for_timestamp(ts),
                "created_at": ts,
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load checkpoints: {e}")

    raw.sort(key=lambda c: c["step"])
    return [
        {**cp, "next": [] if i == len(raw) - 1 else ["continue"]}
        for i, cp in enumerate(raw)
    ]


@router.post("/{workflow_type}/replay")
async def replay_from_checkpoint(
    procurement_id: uuid.UUID,
    workflow_type: str,
    payload: ReplayRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_procurement(procurement_id, current_user, db)

    result = await db.execute(select(WorkflowRun).where(WorkflowRun.thread_id == payload.thread_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    graph = _get_graph(workflow_type)

    async def generate():
        async for chunk in stream_graph_replay(graph, payload.thread_id, payload.checkpoint_id, run, db):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/audit-log")
async def export_audit_log(
    procurement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_procurement(procurement_id, current_user, db)

    result = await db.execute(
        select(WorkflowEvent)
        .where(WorkflowEvent.procurement_id == procurement_id)
        .order_by(WorkflowEvent.created_at.asc())
    )
    events = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "workflow_type", "thread_id", "node_name", "event_type", "latency_ms", "tokens_used", "model_id"])
    for e in events:
        writer.writerow([
            e.created_at.isoformat() if e.created_at else "",
            e.workflow_type,
            e.thread_id,
            e.node_name,
            e.event_type,
            e.latency_ms if e.latency_ms is not None else "",
            e.tokens_used if e.tokens_used is not None else "",
            e.model_id or "",
        ])

    csv_bytes = output.getvalue().encode()
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=\"procura-audit-log-{procurement_id}.csv\""},
    )


@router.get("/model-config", response_model=list[WorkflowModelConfigOut])
async def get_model_configs(
    procurement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_procurement(procurement_id, current_user, db)
    result = await db.execute(
        select(WorkflowModelConfig).where(WorkflowModelConfig.procurement_id == procurement_id)
    )
    return [WorkflowModelConfigOut.model_validate(c) for c in result.scalars().all()]
