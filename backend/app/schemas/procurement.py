import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class EvaluationCriterion(BaseModel):
    criterion: str
    weight: float


class ProcurementCreate(BaseModel):
    title: str
    business_objective: str
    scope: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    budget_currency: str = "USD"
    timeline: str
    evaluation_criteria: list[EvaluationCriterion]
    compliance_requirements: Optional[str] = None

    @field_validator("evaluation_criteria")
    @classmethod
    def criteria_weights_sum(cls, v: list[EvaluationCriterion]) -> list[EvaluationCriterion]:
        total = sum(c.weight for c in v)
        if not (0.99 <= total <= 1.01):
            raise ValueError("Evaluation criteria weights must sum to 1.0")
        return v


class ProcurementUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


class ProcurementOut(BaseModel):
    id: uuid.UUID
    title: str
    business_objective: str
    scope: str
    budget_min: Optional[float]
    budget_max: Optional[float]
    budget_currency: str
    timeline: str
    evaluation_criteria: list
    compliance_requirements: Optional[str]
    stage: str
    status: str
    created_by: uuid.UUID
    selected_proposal_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProcurementList(BaseModel):
    items: list[ProcurementOut]
    total: int
