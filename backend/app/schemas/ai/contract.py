from pydantic import BaseModel, Field


class ContractMilestone(BaseModel):
    milestone: str
    due_date: str
    payment_trigger: str = Field(description="What triggers payment for this milestone")


class ContractContent(BaseModel):
    contract_summary: str = Field(description="Executive summary of the contract")
    scope: str = Field(description="Detailed scope of work and obligations")
    payment_terms: str = Field(description="Payment schedule, amounts, and conditions")
    milestones: list[ContractMilestone]
    legal_clauses: str = Field(description="Standard legal clauses, IP rights, confidentiality")
    obligations: str = Field(description="Obligations of both parties")
    termination_clauses: str = Field(description="Conditions and procedures for contract termination")


class ContractSection(BaseModel):
    section_name: str
    content: str
