import uuid

from langchain_core.messages import HumanMessage
from langgraph.types import Send, interrupt
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.enums import ProcurementStage
from app.models.contract import Contract, ContractRevision
from app.models.procurement import Procurement
from app.models.proposal import SupplierProposal
from app.models.rfp import RFP
from app.schemas.ai.contract import ContractSection
from app.workflows.base import get_llm
from app.workflows.contract.state import CONTRACT_SECTIONS, ContractSectionState, ContractState

_SECTION_INSTRUCTIONS: dict[str, str] = {
    "scope": "Define the complete scope of work, deliverables, and acceptance criteria in precise legal terms.",
    "payment_terms": "Specify payment schedule, amounts, milestones that trigger payment, and invoice procedures.",
    "milestones": "List all project milestones with target dates, deliverables, and success criteria.",
    "legal_clauses": "Cover IP ownership, confidentiality, liability caps, indemnification, and governing law.",
    "termination_clauses": "Define conditions for termination by either party, notice periods, and obligations upon termination.",
}


async def validate_prerequisites(state: ContractState) -> dict:
    async with AsyncSessionLocal() as db:
        proc_result = await db.execute(
            select(Procurement).where(Procurement.id == uuid.UUID(state["procurement_id"]))
        )
        procurement = proc_result.scalar_one_or_none()
        if not procurement:
            return {"error": "Procurement not found", "status": "FAILED"}
        if procurement.stage != ProcurementStage.CONTRACT:
            return {"error": f"Expected CONTRACT stage, got {procurement.stage}", "status": "FAILED"}
        if not procurement.selected_proposal_id:
            return {"error": "No selected proposal — run Evaluation first", "status": "FAILED"}
    return {"status": "PREREQUISITES_OK", "sections_to_generate": CONTRACT_SECTIONS}


async def load_contract_context(state: ContractState) -> dict:
    async with AsyncSessionLocal() as db:
        proc_result = await db.execute(
            select(Procurement).where(Procurement.id == uuid.UUID(state["procurement_id"]))
        )
        procurement = proc_result.scalar_one()

        rfp_result = await db.execute(
            select(RFP).where(
                RFP.procurement_id == procurement.id,
                RFP.status == "APPROVED",
            ).order_by(RFP.version.desc()).limit(1)
        )
        rfp = rfp_result.scalar_one_or_none()
        if not rfp:
            return {"error": "No approved RFP found", "status": "FAILED"}

        proposal_result = await db.execute(
            select(SupplierProposal).where(
                SupplierProposal.id == procurement.selected_proposal_id
            )
        )
        proposal = proposal_result.scalar_one_or_none()
        if not proposal:
            return {"error": "Selected proposal not found", "status": "FAILED"}

    return {
        "approved_rfp": rfp.content,
        "selected_proposal": proposal.extracted_data or {},
        "supplier_name": proposal.supplier_name,
        "status": "CONTEXT_LOADED",
    }


def fan_out_sections(state: ContractState) -> list[Send]:
    sections = state.get("target_revision_sections") or state.get("sections_to_generate", CONTRACT_SECTIONS)
    return [
        Send(
            "generate_section",
            ContractSectionState(
                section_name=section,
                rfp_content=state["approved_rfp"],
                proposal_extraction=state["selected_proposal"],
                supplier_name=state["supplier_name"],
                model_id=state["model_id"],
                temperature=state.get("temperature", 0.3),
                section_content=None,
                validation_error=None,
                error=None,
            ),
        )
        for section in sections
    ]


async def generate_section(state: ContractSectionState) -> dict:
    """Generate one contract section. Send target — returns ContractState updates."""
    section = state["section_name"]
    instruction = _SECTION_INSTRUCTIONS.get(section, f"Draft the {section} section of the contract.")

    rfp_summary = str(state["rfp_content"])[:2000]
    proposal_summary = str(state["proposal_extraction"])[:2000]

    prompt = f"""You are a legal contract drafter. Generate the '{section}' section of a procurement contract.

Instruction: {instruction}

Context:
- Supplier: {state["supplier_name"]}
- RFP scope: {rfp_summary}
- Winning proposal: {proposal_summary}

Write professional, legally precise contract language. Be specific and avoid vague terms."""

    llm = get_llm(state["model_id"], state.get("temperature", 0.2))
    structured = llm.with_structured_output(ContractSection)

    try:
        result = await structured.ainvoke([HumanMessage(content=prompt)])
        return {"generated_sections": {section: result.content}}
    except Exception as e:
        # Fallback: use plain text response
        try:
            plain = await llm.ainvoke([HumanMessage(content=prompt)])
            content = plain.content if hasattr(plain, "content") else str(plain)
            return {"generated_sections": {section: content}}
        except Exception as e2:
            return {"generated_sections": {section: f"[Generation failed: {e2}]"}}


async def assemble_contract(state: ContractState) -> dict:
    sections = state.get("generated_sections", {})
    assembled = {
        "supplier_name": state["supplier_name"],
        **sections,
    }
    return {"assembled_contract": assembled, "validation_error": None}


async def validate_complete_contract(state: ContractState) -> dict:
    contract = state.get("assembled_contract", {})
    missing = [s for s in CONTRACT_SECTIONS if s not in contract]
    if missing:
        return {
            "validation_error": f"Missing sections: {missing}",
            "validation_attempts": state.get("validation_attempts", 0) + 1,
        }
    return {"validation_error": None}


async def escalate(state: ContractState) -> dict:
    return {"status": "ESCALATED", "error": f"Contract generation failed: {state.get('validation_error')}"}


async def human_review(state: ContractState) -> dict:
    # Persist draft as IN_REVIEW so the frontend can display it before the user decides
    async with AsyncSessionLocal() as db:
        procurement_id = uuid.UUID(state["procurement_id"])
        version = len(state.get("revision_history", [])) + 1
        existing = await db.execute(
            select(Contract)
            .where(Contract.procurement_id == procurement_id)
            .order_by(Contract.version.desc())
            .limit(1)
        )
        contract = existing.scalar_one_or_none()
        if contract and contract.status not in ("APPROVED", "REJECTED"):
            contract.draft_content = state.get("assembled_contract", {})
            contract.status = "IN_REVIEW"
            contract.model_id = state["model_id"]
        else:
            proc_result = await db.execute(
                select(Procurement).where(Procurement.id == procurement_id)
            )
            procurement = proc_result.scalar_one()
            contract = Contract(
                procurement_id=procurement_id,
                proposal_id=procurement.selected_proposal_id,
                supplier_name=state["supplier_name"],
                version=version,
                draft_content=state.get("assembled_contract", {}),
                status="IN_REVIEW",
                model_id=state["model_id"],
            )
            db.add(contract)
        await db.commit()

    decision = interrupt({
        "type": "contract_review",
        "assembled_contract": state.get("assembled_contract"),
        "supplier_name": state["supplier_name"],
        "revision_history_count": len(state.get("revision_history", [])),
    })
    return {
        "approval_action": decision.get("action"),
        "approval_comments": decision.get("comments"),
        "revision_request": decision.get("revision_request"),
        "target_revision_sections": decision.get("target_sections"),
    }


async def finalize_contract(state: ContractState) -> dict:
    async with AsyncSessionLocal() as db:
        proc_result = await db.execute(
            select(Procurement).where(Procurement.id == uuid.UUID(state["procurement_id"]))
        )
        procurement = proc_result.scalar_one()

        version = len(state.get("revision_history", [])) + 1
        existing = await db.execute(
            select(Contract).where(
                Contract.procurement_id == procurement.id,
                Contract.version == version,
            )
        )
        contract = existing.scalar_one_or_none()

        if contract:
            contract.draft_content = state["assembled_contract"]
            contract.status = "APPROVED"
        else:
            contract = Contract(
                procurement_id=procurement.id,
                proposal_id=procurement.selected_proposal_id,
                supplier_name=state["supplier_name"],
                version=version,
                draft_content=state["assembled_contract"],
                status="APPROVED",
                model_id=state["model_id"],
            )
            db.add(contract)

        procurement.stage = ProcurementStage.FINALIZED
        await db.commit()

    return {"status": "FINALIZED"}


async def store_revision(state: ContractState) -> dict:
    async with AsyncSessionLocal() as db:
        proc_result = await db.execute(
            select(Procurement).where(Procurement.id == uuid.UUID(state["procurement_id"]))
        )
        procurement = proc_result.scalar_one()
        version = len(state.get("revision_history", [])) + 1

        existing = await db.execute(
            select(Contract).where(Contract.procurement_id == procurement.id)
        )
        contract = existing.scalars().first()
        if not contract:
            contract = Contract(
                procurement_id=procurement.id,
                proposal_id=procurement.selected_proposal_id,
                supplier_name=state["supplier_name"],
                version=version,
                draft_content=state.get("assembled_contract", {}),
                status="DRAFT",
                model_id=state["model_id"],
            )
            db.add(contract)
            await db.flush()

        revision = ContractRevision(
            contract_id=contract.id,
            version=version,
            content=state.get("assembled_contract", {}),
            revision_request=state.get("revision_request", ""),
        )
        db.add(revision)
        await db.commit()

    entry = {
        "version": version,
        "content": state.get("assembled_contract"),
        "revision_request": state.get("revision_request", ""),
    }
    return {
        "revision_history": [entry],
        "assembled_contract": None,
        "generated_sections": {},
        "validation_error": None,
        "validation_attempts": 0,
        "target_revision_sections": None,
    }


async def mark_rejected(state: ContractState) -> dict:
    return {"status": "REJECTED"}
