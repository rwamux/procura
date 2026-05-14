import time
import uuid
from datetime import date

from langchain_core.messages import HumanMessage
from langgraph.types import interrupt
from pydantic import ValidationError
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.enums import ProcurementStage, RFPStatus
from app.models.procurement import Procurement
from app.models.rfp import RFP, RFPRevision
from app.schemas.ai.rfp import RFPContent
from app.workflows.base import get_llm
from app.workflows.rfp.state import RFPState

_RFP_PROMPT = """You are an expert procurement specialist. Generate a comprehensive, professional Request for Proposal (RFP) document.

## Procurement Details
Title: {title}
Business Objective: {business_objective}
Scope: {scope}
Budget: {budget}
Timeline: {timeline}
Evaluation Criteria: {criteria}
Compliance Requirements: {compliance}
Today's Date: {today}
{revision_section}

Generate a complete RFP with all required sections. Be specific, professional, and actionable.
Use formal business language appropriate for enterprise procurement.

IMPORTANT: For all milestone due_date fields, generate real calendar dates (e.g. "15 June 2026") calculated from today's date and the stated timeline. Never use placeholders like "[insert date]" or "TBD"."""


async def validate_prerequisites(state: RFPState) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Procurement).where(Procurement.id == uuid.UUID(state["procurement_id"])))
        procurement = result.scalar_one_or_none()

        if not procurement:
            return {"error": "Procurement not found", "status": "FAILED"}
        if procurement.stage != ProcurementStage.RFP:
            return {"error": f"Procurement is at stage {procurement.stage}, expected RFP", "status": "FAILED"}

        existing = await db.execute(
            select(RFP).where(
                RFP.procurement_id == procurement.id,
                RFP.status == RFPStatus.APPROVED,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "An approved RFP already exists for this procurement", "status": "FAILED"}

    return {"status": "PREREQUISITES_OK"}


async def load_requirements(state: RFPState) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Procurement).where(Procurement.id == uuid.UUID(state["procurement_id"])))
        p = result.scalar_one()

    requirements = {
        "procurement_id": str(p.id),
        "title": p.title,
        "business_objective": p.business_objective,
        "scope": p.scope,
        "budget_min": float(p.budget_min) if p.budget_min else None,
        "budget_max": float(p.budget_max) if p.budget_max else None,
        "budget_currency": p.budget_currency,
        "timeline": p.timeline,
        "evaluation_criteria": p.evaluation_criteria,
        "compliance_requirements": p.compliance_requirements,
    }
    return {"requirements": requirements}


async def generate_rfp(state: RFPState) -> dict:
    req = state["requirements"]
    revision_section = ""
    if state.get("revision_request") and state.get("revision_history"):
        last = state["revision_history"][-1]
        revision_section = f"\n## Revision Request\nPrevious draft was rejected. User requested: {state['revision_request']}\n\nPlease revise accordingly while maintaining all required sections."

    budget = "Not specified"
    if req.get("budget_min") or req.get("budget_max"):
        budget = f"{req.get('budget_min', 'TBD')} – {req.get('budget_max', 'TBD')} {req.get('budget_currency', 'USD')}"

    prompt = _RFP_PROMPT.format(
        title=req["title"],
        business_objective=req["business_objective"],
        scope=req["scope"],
        budget=budget,
        timeline=req["timeline"],
        criteria=req["evaluation_criteria"],
        compliance=req.get("compliance_requirements") or "None specified",
        today=date.today().strftime("%d %B %Y"),
        revision_section=revision_section,
    )

    llm = get_llm(state["model_id"], state.get("temperature", 0.3))
    structured_llm = llm.with_structured_output(RFPContent)

    start = time.monotonic()
    try:
        result = await structured_llm.ainvoke([HumanMessage(content=prompt)])
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "rfp_draft": result.model_dump(),
            "validation_error": None,
            "status": "DRAFT_READY",
        }
    except Exception as e:
        return {
            "validation_error": str(e),
            "validation_attempts": state.get("validation_attempts", 0) + 1,
        }


async def validate_rfp_structure(state: RFPState) -> dict:
    if state.get("validation_error"):
        attempts = state.get("validation_attempts", 0) + 1
        return {"validation_attempts": attempts}

    draft = state.get("rfp_draft")
    if not draft:
        return {"validation_error": "No draft produced", "validation_attempts": state.get("validation_attempts", 0) + 1}

    try:
        RFPContent.model_validate(draft)
        return {"validation_error": None}
    except ValidationError as e:
        return {
            "validation_error": str(e),
            "validation_attempts": state.get("validation_attempts", 0) + 1,
        }


async def escalate_to_human(state: RFPState) -> dict:
    return {"status": "ESCALATED", "error": f"RFP generation failed after max retries: {state.get('validation_error')}"}


async def human_review(state: RFPState) -> dict:
    # Persist draft as IN_REVIEW so the frontend can display it before the user decides
    async with AsyncSessionLocal() as db:
        procurement_id = uuid.UUID(state["procurement_id"])
        version = len(state.get("revision_history", [])) + 1
        existing = await db.execute(
            select(RFP)
            .where(RFP.procurement_id == procurement_id)
            .order_by(RFP.version.desc())
            .limit(1)
        )
        rfp = existing.scalar_one_or_none()
        if rfp and rfp.status not in (RFPStatus.APPROVED, RFPStatus.REJECTED):
            rfp.content = state["rfp_draft"]
            rfp.status = RFPStatus.IN_REVIEW
            rfp.model_id = state["model_id"]
        else:
            rfp = RFP(
                procurement_id=procurement_id,
                version=version,
                content=state["rfp_draft"],
                status=RFPStatus.IN_REVIEW,
                model_id=state["model_id"],
            )
            db.add(rfp)
        await db.commit()

    human_decision = interrupt({
        "type": "rfp_review",
        "rfp_draft": state["rfp_draft"],
        "revision_history_count": len(state.get("revision_history", [])),
        "procurement_id": state["procurement_id"],
    })
    return {
        "approval_action": human_decision["action"],
        "approval_comments": human_decision.get("comments"),
        "revision_request": human_decision.get("revision_request"),
        "status": "HUMAN_REVIEWED",
    }


async def persist_approved_rfp(state: RFPState) -> dict:
    async with AsyncSessionLocal() as db:
        procurement_id = uuid.UUID(state["procurement_id"])
        version = len(state.get("revision_history", [])) + 1

        existing = await db.execute(
            select(RFP).where(RFP.procurement_id == procurement_id, RFP.version == version)
        )
        rfp = existing.scalar_one_or_none()

        if rfp:
            rfp.content = state["rfp_draft"]
            rfp.status = RFPStatus.APPROVED
            rfp.model_id = state["model_id"]
        else:
            rfp = RFP(
                procurement_id=procurement_id,
                version=version,
                content=state["rfp_draft"],
                status=RFPStatus.APPROVED,
                model_id=state["model_id"],
                prompt_metadata={"model_id": state["model_id"]},
            )
            db.add(rfp)

        result = await db.execute(select(Procurement).where(Procurement.id == procurement_id))
        procurement = result.scalar_one()
        procurement.stage = ProcurementStage.PROPOSAL_INTAKE

        await db.commit()

    return {"status": "APPROVED"}


async def store_revision(state: RFPState) -> dict:
    async with AsyncSessionLocal() as db:
        procurement_id = uuid.UUID(state["procurement_id"])
        version = len(state.get("revision_history", [])) + 1

        existing_rfp = await db.execute(
            select(RFP).where(RFP.procurement_id == procurement_id)
        )
        rfp = existing_rfp.scalars().first()

        if not rfp:
            rfp = RFP(
                procurement_id=procurement_id,
                version=version,
                content=state["rfp_draft"],
                status=RFPStatus.DRAFT,
                model_id=state["model_id"],
            )
            db.add(rfp)
            await db.flush()

        revision = RFPRevision(
            rfp_id=rfp.id,
            version=version,
            content=state["rfp_draft"],
            revision_request=state.get("revision_request", ""),
        )
        db.add(revision)
        await db.commit()

    revision_entry = {
        "version": version,
        "content": state["rfp_draft"],
        "revision_request": state.get("revision_request", ""),
    }
    return {
        "revision_history": [revision_entry],
        "rfp_draft": None,
        "validation_error": None,
        "validation_attempts": 0,
        "status": "REVISION_STORED",
    }


async def mark_rejected(state: RFPState) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RFP).where(RFP.procurement_id == uuid.UUID(state["procurement_id"]))
        )
        rfp = result.scalars().first()
        if rfp:
            rfp.status = RFPStatus.REJECTED
            await db.commit()

    return {"status": "REJECTED"}
