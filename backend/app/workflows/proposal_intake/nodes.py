import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.types import Send, interrupt
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.enums import ProcurementStage
from app.models.procurement import Procurement
from app.models.proposal import SupplierProposal
from app.schemas.ai.proposal import ProposalExtraction
from app.workflows.base import get_llm
from app.workflows.proposal_intake.state import (
    ExtractedProposal,
    FailedExtraction,
    ProposalExtractionState,
    ProposalIntakeState,
    ProposalToProcess,
)

logger = logging.getLogger(__name__)


async def validate_prerequisites(state: ProposalIntakeState) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Procurement).where(Procurement.id == uuid.UUID(state["procurement_id"]))
        )
        procurement = result.scalar_one_or_none()
        if not procurement:
            return {"error": "Procurement not found", "status": "FAILED"}
        if procurement.stage != ProcurementStage.PROPOSAL_INTAKE:
            return {
                "error": f"Expected PROPOSAL_INTAKE stage, got {procurement.stage}",
                "status": "FAILED",
            }
        count = await db.execute(
            select(SupplierProposal).where(SupplierProposal.procurement_id == procurement.id)
        )
        if not count.scalars().all():
            return {"error": "No proposals submitted for this procurement", "status": "FAILED"}
    return {"status": "PREREQUISITES_OK"}


async def load_proposals(state: ProposalIntakeState) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SupplierProposal).where(
                SupplierProposal.procurement_id == uuid.UUID(state["procurement_id"]),
                SupplierProposal.extraction_status.in_(["SUBMITTED", "FAILED"]),
            )
        )
        proposals = result.scalars().all()

    to_process = [
        ProposalToProcess(
            proposal_id=str(p.id),
            file_path=p.file_path,
            mime_type=p.mime_type or "text/plain",
            supplier_name=p.supplier_name,
        )
        for p in proposals
    ]
    return {"proposals_to_process": to_process}


def fan_out_process_proposals(state: ProposalIntakeState) -> list[Send]:
    reprocess = set(state.get("reprocess_ids") or [])
    pool = state["proposals_to_process"]
    targets = [p for p in pool if not reprocess or p["proposal_id"] in reprocess]
    return [
        Send(
            "process_proposal",
            ProposalExtractionState(
                procurement_id=state["procurement_id"],
                proposal_id=p["proposal_id"],
                file_path=p["file_path"],
                mime_type=p["mime_type"],
                supplier_name=p["supplier_name"],
                model_id=state["model_id"],
                temperature=state.get("temperature", 0.3),
                raw_text=None,
                text_quality_ok=None,
                extracted_data=None,
                extraction_attempts=0,
                error=None,
            ),
        )
        for p in targets
    ]


def _read_file(file_path: str, mime: str) -> str:
    path = Path(file_path)
    if "pdf" in mime or path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if "word" in mime or path.suffix.lower() == ".docx":
        from docx import Document
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    return path.read_text(encoding="utf-8", errors="replace")


async def process_proposal(state: ProposalExtractionState) -> dict:
    proposal_id = state["proposal_id"]

    raw_text: str | None = state.get("raw_text")
    if not raw_text:
        async with AsyncSessionLocal() as db:
            row = await db.execute(
                select(SupplierProposal).where(SupplierProposal.id == uuid.UUID(proposal_id))
            )
            p = row.scalar_one_or_none()
            if p and p.raw_text:
                raw_text = p.raw_text

    if not raw_text and state.get("file_path"):
        try:
            raw_text = _read_file(state["file_path"], state.get("mime_type", ""))
        except Exception as e:
            await _mark_failed(proposal_id)
            return {
                "failed_extractions": [
                    FailedExtraction(proposal_id=proposal_id, error=f"File read failed: {e}")
                ]
            }

    if not raw_text or len(raw_text.strip()) < 50:
        await _mark_failed(proposal_id)
        return {
            "failed_extractions": [
                FailedExtraction(proposal_id=proposal_id, error="Insufficient text content")
            ]
        }

    llm = get_llm(state["model_id"], state.get("temperature", 0.3))
    structured = llm.with_structured_output(ProposalExtraction)
    prompt = f"""Extract structured procurement information from this supplier proposal.

Supplier: {state["supplier_name"]}

Proposal content:
{raw_text[:8000]}

Extract all relevant procurement details following the schema exactly."""

    extracted_data: dict | None = None
    last_exc: Exception | None = None
    for _ in range(3):
        try:
            result = await structured.ainvoke([HumanMessage(content=prompt)])
            extracted_data = result.model_dump()
            break
        except Exception as e:
            last_exc = e

    if extracted_data is None:
        logger.warning("AI extraction failed after 3 attempts for proposal %s: %s", proposal_id, last_exc)
        await _mark_failed(proposal_id)
        return {
            "failed_extractions": [
                FailedExtraction(proposal_id=proposal_id, error=f"AI extraction failed after 3 attempts: {last_exc}")
            ]
        }
    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(SupplierProposal).where(SupplierProposal.id == uuid.UUID(proposal_id))
        )
        proposal = row.scalar_one()
        proposal.extracted_data = extracted_data
        proposal.raw_text = raw_text
        proposal.extraction_model = state["model_id"]
        proposal.extraction_status = "COMPLETED"
        proposal.extraction_timestamp = datetime.now(timezone.utc)
        await db.commit()

    return {
        "extracted_proposals": [
            ExtractedProposal(
                proposal_id=proposal_id,
                extracted_data=extracted_data,
                model_id=state["model_id"],
            )
        ]
    }


async def _mark_failed(proposal_id: str) -> None:
    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(SupplierProposal).where(SupplierProposal.id == uuid.UUID(proposal_id))
        )
        p = row.scalar_one_or_none()
        if p:
            p.extraction_status = "FAILED"
            await db.commit()


async def aggregate_extractions(state: ProposalIntakeState) -> dict:
    ok = len(state.get("extracted_proposals", []))
    failed = len(state.get("failed_extractions", []))
    return {"status": f"EXTRACTIONS_COMPLETE ({ok} ok, {failed} failed)"}


async def human_review(state: ProposalIntakeState) -> dict:
    decision = interrupt({
        "type": "proposal_intake_review",
        "extracted_count": len(state.get("extracted_proposals", [])),
        "failed_count": len(state.get("failed_extractions", [])),
        "extracted_proposals": [
            {
                "proposal_id": e["proposal_id"],
                "supplier_name": e["extracted_data"].get("supplier_name", ""),
            }
            for e in state.get("extracted_proposals", [])
        ],
        "failed_extractions": state.get("failed_extractions", []),
    })
    return {
        "review_approved": decision.get("action") == "APPROVED",
        "reprocess_ids": decision.get("reprocess_ids"),
    }


async def mark_intake_complete(state: ProposalIntakeState) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Procurement).where(Procurement.id == uuid.UUID(state["procurement_id"]))
        )
        procurement = result.scalar_one()
        procurement.stage = ProcurementStage.EVALUATION
        await db.commit()
    return {"status": "COMPLETED"}
