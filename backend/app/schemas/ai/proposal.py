from typing import Optional
from pydantic import BaseModel, Field


class PricingDetail(BaseModel):
    total_cost: Optional[float] = None
    currency: str = "USD"
    pricing_model: str = Field(description="e.g. fixed, time-and-materials, subscription")
    breakdown: list[str] = Field(description="Line items or cost components")
    payment_terms: str


class ProposalExtraction(BaseModel):
    supplier_name: str
    executive_summary: str = Field(description="Brief overview of the supplier's proposal")
    pricing: PricingDetail
    timeline: str = Field(description="Proposed delivery timeline")
    deliverables: list[str] = Field(description="What the supplier commits to delivering")
    assumptions: list[str] = Field(description="Assumptions the supplier has made")
    risks: list[str] = Field(description="Risks identified by the supplier")
    compliance_notes: str = Field(description="How the proposal addresses compliance requirements")
    differentiators: list[str] = Field(description="Key strengths or unique selling points")


class ProposalAIAssessment(BaseModel):
    overall_assessment: str = Field(description="Narrative evaluation of this proposal")
    strengths: list[str] = Field(description="Top strengths of this proposal")
    weaknesses: list[str] = Field(description="Notable weaknesses or concerns")
    criterion_scores: dict[str, float] = Field(
        description="Score 0-10 for each evaluation criterion; keys must match the procurement criteria names exactly"
    )
    recommendation: str = Field(description="Brief recommendation summary")
