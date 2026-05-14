from pydantic import BaseModel, Field


class Milestone(BaseModel):
    description: str
    due_date: str


class EvaluationCriterionDetail(BaseModel):
    criterion: str
    weight: float
    description: str


class RFPContent(BaseModel):
    executive_summary: str = Field(description="High-level summary of the procurement and its goals")
    scope_of_work: str = Field(description="Detailed description of what is required")
    deliverables: list[str] = Field(description="Specific, measurable deliverables expected")
    submission_requirements: str = Field(description="How and when proposals should be submitted")
    evaluation_criteria: list[EvaluationCriterionDetail] = Field(description="How proposals will be scored")
    timelines: list[Milestone] = Field(description="Key dates and milestones")
    legal_compliance_notes: str = Field(description="Legal requirements, compliance obligations, and terms")
