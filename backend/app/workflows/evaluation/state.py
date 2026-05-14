import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict


class ScoredProposal(TypedDict):
    proposal_id: str
    supplier_name: str
    weighted_total: float
    ai_assessment: dict


class RankedProposal(TypedDict):
    rank: int
    proposal_id: str
    supplier_name: str
    weighted_total: float
    ai_assessment: dict


class EvaluationState(TypedDict):
    procurement_id: str
    evaluation_id: str
    thread_id: str
    model_id: str
    temperature: float
    evaluation_weights: dict
    proposals: list[dict]
    scored_proposals: Annotated[list[ScoredProposal], operator.add]
    rankings: Optional[list[RankedProposal]]
    recommendation_proposal_id: Optional[str]
    recommendation_rationale: Optional[str]
    approval_action: Optional[str]
    approval_comments: Optional[str]
    manual_override_proposal_id: Optional[str]
    status: str
    error: Optional[str]


class ProposalScoringState(TypedDict):
    evaluation_id: str
    proposal_id: str
    supplier_name: str
    proposal_summary: dict
    evaluation_weights: dict
    model_id: str
    temperature: float
