import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict


class RFPRequirements(TypedDict):
    procurement_id: str
    title: str
    business_objective: str
    scope: str
    budget_min: Optional[float]
    budget_max: Optional[float]
    budget_currency: str
    timeline: str
    evaluation_criteria: list[dict]
    compliance_requirements: Optional[str]


class RFPState(TypedDict):
    procurement_id: str
    thread_id: str
    model_id: str
    temperature: float
    requirements: Optional[RFPRequirements]
    rfp_draft: Optional[dict]
    validation_error: Optional[str]
    validation_attempts: int
    revision_history: Annotated[list[dict], operator.add]
    revision_request: Optional[str]
    approval_action: Optional[str]
    approval_comments: Optional[str]
    status: str
    error: Optional[str]
