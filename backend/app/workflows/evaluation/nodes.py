import json
import logging
import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from langgraph.types import Send, interrupt
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.enums import ProcurementStage
from app.models.evaluation import Evaluation, ProposalScore
from app.models.procurement import Procurement
from app.models.proposal import SupplierProposal
from app.schemas.ai.proposal import ProposalAIAssessment
from app.workflows.base import get_llm
from app.workflows.evaluation.state import (
    EvaluationState,
    ProposalScoringState,
    RankedProposal,
    ScoredProposal,
)

logger = logging.getLogger(__name__)


async def validate_prerequisites(state: EvaluationState) -> dict:
    async with AsyncSessionLocal() as db:
        proc_result = await db.execute(
            select(Procurement).where(Procurement.id == uuid.UUID(state["procurement_id"]))
        )
        procurement = proc_result.scalar_one_or_none()
        if not procurement:
            return {"error": "Procurement not found", "status": "FAILED"}
        if procurement.stage != ProcurementStage.EVALUATION:
            return {
                "error": f"Expected EVALUATION stage, got {procurement.stage}",
                "status": "FAILED",
            }

        proposals_result = await db.execute(
            select(SupplierProposal).where(
                SupplierProposal.procurement_id == procurement.id,
                SupplierProposal.extraction_status == "COMPLETED",
            )
        )
        proposals = proposals_result.scalars().all()
        if not proposals:
            return {"error": "No extracted proposals available for evaluation", "status": "FAILED"}

        criteria = procurement.evaluation_criteria or []
        weights = {c["criterion"]: float(c["weight"]) for c in criteria}
        if not weights:
            return {"error": "No evaluation criteria defined on procurement", "status": "FAILED"}

        eval_result = await db.execute(
            select(Evaluation).where(
                Evaluation.procurement_id == procurement.id,
                Evaluation.status == "PENDING",
            )
        )
        evaluation = eval_result.scalar_one_or_none()
        if not evaluation:
            evaluation = Evaluation(
                procurement_id=procurement.id,
                status="PENDING",
                evaluation_weights=weights,
                model_id=state["model_id"],
            )
            db.add(evaluation)
            await db.flush()

        proposal_summaries = [
            {
                "proposal_id": str(p.id),
                "supplier_name": p.supplier_name,
                "extracted_data": p.extracted_data or {},
            }
            for p in proposals
        ]

        evaluation_id = str(evaluation.id)
        await db.commit()

    return {
        "evaluation_id": evaluation_id,
        "evaluation_weights": weights,
        "proposals": proposal_summaries,
        "status": "PREREQUISITES_OK",
    }


async def load_extracted_proposals(state: EvaluationState) -> dict:
    # proposals are already loaded in validate_prerequisites; this node is a no-op pass-through
    return {"status": "PROPOSALS_LOADED"}


def fan_out_scoring(state: EvaluationState) -> list[Send]:
    return [
        Send(
            "score_proposal",
            ProposalScoringState(
                evaluation_id=state["evaluation_id"],
                proposal_id=p["proposal_id"],
                supplier_name=p["supplier_name"],
                proposal_summary=p["extracted_data"],
                evaluation_weights=state["evaluation_weights"],
                model_id=state["model_id"],
                temperature=state.get("temperature", 0.3),
            ),
        )
        for p in state["proposals"]
    ]


async def score_proposal(state: ProposalScoringState) -> dict:
    import re

    llm = get_llm(state["model_id"], state.get("temperature", 0.3))

    weights = state["evaluation_weights"]
    logger.debug("scoring %s | weights=%s", state["supplier_name"], list(weights.keys()))
    criteria_text = "\n".join(
        f"- {name} (weight {w:.0%})" for name, w in weights.items()
    )
    summary_text = json.dumps(state["proposal_summary"], indent=2)[:5000]
    criteria_keys_json = json.dumps(list(weights.keys()))

    prompt = f"""You are evaluating a supplier proposal for a procurement. Return ONLY valid JSON — no markdown fences, no explanation.

Supplier: {state["supplier_name"]}
Proposal summary:
{summary_text}

Evaluation criteria (score each 0–10, 10 = excellent):
{criteria_text}

Return this exact JSON structure:
{{
  "overall_assessment": "<narrative evaluation>",
  "strengths": ["<strength1>", "<strength2>"],
  "weaknesses": ["<weakness1>", "<weakness2>"],
  "criterion_scores": {{
    "<criterion name>": <score 0-10>
  }},
  "recommendation": "<brief recommendation>"
}}

The criterion_scores keys must be exactly: {criteria_keys_json}
Provide honest, detailed scores based on the proposal content."""

    assessment_dump: dict
    criterion_scores: dict[str, float]
    weighted_total: float

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content if hasattr(response, "content") else str(response)

        # Extract JSON even if the model wraps it in markdown fences
        json_match = re.search(r"\{[\s\S]*\}", content)
        if not json_match:
            raise ValueError(f"No JSON object found in LLM response: {content[:300]}")

        raw_data = json.loads(json_match.group())
        assessment = ProposalAIAssessment.model_validate(raw_data)
        criterion_scores = assessment.criterion_scores
        weighted_total = round(
            sum(criterion_scores.get(k, 5.0) * w for k, w in weights.items()), 2
        )
        assessment_dump = assessment.model_dump()
        logger.debug("scored %s → %.2f", state["supplier_name"], weighted_total)
    except Exception as e:
        logger.exception("scoring failed for %s", state["supplier_name"])
        criterion_scores = {}
        weighted_total = 0.0
        assessment_dump = {"error": str(e), "overall_assessment": "", "strengths": [], "weaknesses": [], "criterion_scores": {}, "recommendation": ""}

    # Derive the 4 fixed DB columns by fuzzy-matching criterion names
    def _find(keys: list[str]) -> float:
        for k in keys:
            for name, score in criterion_scores.items():
                if k.lower() in name.lower():
                    return float(score)
        return 5.0

    technical = _find(["technical", "tech"])
    cost = _find(["cost", "price", "financial"])
    timeline = _find(["timeline", "delivery", "schedule"])
    risk = _find(["risk"])

    # Always persist — even on LLM failure so the score row exists in the DB
    async with AsyncSessionLocal() as db:
        score_record = ProposalScore(
            evaluation_id=uuid.UUID(state["evaluation_id"]),
            proposal_id=uuid.UUID(state["proposal_id"]),
            technical_fit_score=technical,
            cost_score=cost,
            timeline_score=timeline,
            risk_score=risk,
            weighted_total=weighted_total,
            rank=0,
            ai_assessment=assessment_dump,
            model_id=state["model_id"],
        )
        db.add(score_record)
        await db.commit()

    return {
        "scored_proposals": [
            ScoredProposal(
                proposal_id=state["proposal_id"],
                supplier_name=state["supplier_name"],
                weighted_total=weighted_total,
                ai_assessment=assessment_dump,
            )
        ]
    }


async def rank_proposals(state: EvaluationState) -> dict:
    scored = sorted(
        state.get("scored_proposals", []),
        key=lambda x: x["weighted_total"],
        reverse=True,
    )
    rankings: list[RankedProposal] = [
        RankedProposal(rank=i + 1, **s) for i, s in enumerate(scored)
    ]

    async with AsyncSessionLocal() as db:
        for rp in rankings:
            score_result = await db.execute(
                select(ProposalScore).where(
                    ProposalScore.evaluation_id == uuid.UUID(state["evaluation_id"]),
                    ProposalScore.proposal_id == uuid.UUID(rp["proposal_id"]),
                )
            )
            score = score_result.scalar_one_or_none()
            if score:
                score.rank = rp["rank"]
        await db.commit()

    recommendation_id = rankings[0]["proposal_id"] if rankings else None
    return {"rankings": rankings, "recommendation_proposal_id": recommendation_id}


async def generate_recommendation_rationale(state: EvaluationState) -> dict:
    if not state.get("rankings"):
        return {"status": "AWAITING_APPROVAL"}

    llm = get_llm(state["model_id"], state.get("temperature", 0.3))
    top = state["rankings"][0]
    all_ranked = "\n".join(
        f"{r['rank']}. {r['supplier_name']} — score {r['weighted_total']:.1f}/10"
        for r in state["rankings"]
    )

    prompt = f"""Write a concise procurement recommendation (3-4 sentences) explaining why {top['supplier_name']}
is the recommended supplier.

Rankings:
{all_ranked}

Top supplier assessment:
{json.dumps(top['ai_assessment'], indent=2)[:2000]}

Focus on the key differentiators and business value."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    rationale = response.content if hasattr(response, "content") else str(response)

    async with AsyncSessionLocal() as db:
        eval_result = await db.execute(
            select(Evaluation).where(Evaluation.id == uuid.UUID(state["evaluation_id"]))
        )
        evaluation = eval_result.scalar_one()
        evaluation.recommendation_rationale = rationale
        evaluation.recommendation_proposal_id = uuid.UUID(state["recommendation_proposal_id"])
        evaluation.status = "EVALUATED"
        evaluation.evaluated_at = datetime.now(timezone.utc)
        await db.commit()

    return {"recommendation_rationale": rationale, "status": "AWAITING_APPROVAL"}


async def human_review(state: EvaluationState) -> dict:
    decision = interrupt({
        "type": "evaluation_review",
        "rankings": state.get("rankings", []),
        "recommendation_proposal_id": state.get("recommendation_proposal_id"),
        "recommendation_rationale": state.get("recommendation_rationale"),
    })
    return {
        "approval_action": decision.get("action"),
        "approval_comments": decision.get("comments"),
        "manual_override_proposal_id": decision.get("manual_override_proposal_id"),
    }


async def apply_override(state: EvaluationState) -> dict:
    return {"recommendation_proposal_id": state["manual_override_proposal_id"]}


async def finalize_selection(state: EvaluationState) -> dict:
    proposal_id = state.get("recommendation_proposal_id")
    if not proposal_id:
        return {"error": "No proposal selected", "status": "FAILED"}

    async with AsyncSessionLocal() as db:
        proc_result = await db.execute(
            select(Procurement).where(Procurement.id == uuid.UUID(state["procurement_id"]))
        )
        procurement = proc_result.scalar_one()
        procurement.selected_proposal_id = uuid.UUID(proposal_id)
        procurement.stage = ProcurementStage.CONTRACT

        eval_result = await db.execute(
            select(Evaluation).where(Evaluation.id == uuid.UUID(state["evaluation_id"]))
        )
        evaluation = eval_result.scalar_one()
        evaluation.status = "APPROVED"
        evaluation.approved_at = datetime.now(timezone.utc)

        await db.commit()

    return {"status": "COMPLETED"}
