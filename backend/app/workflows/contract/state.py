import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict

CONTRACT_SECTIONS = ["scope", "payment_terms", "milestones", "legal_clauses", "termination_clauses"]


def _merge_sections(a: dict, b: dict) -> dict:
    return {**a, **b}


class ContractState(TypedDict):
    procurement_id: str
    thread_id: str
    model_id: str
    temperature: float
    approved_rfp: dict
    selected_proposal: dict
    supplier_name: str
    sections_to_generate: list[str]
    generated_sections: Annotated[dict, _merge_sections]
    assembled_contract: Optional[dict]
    validation_error: Optional[str]
    validation_attempts: int
    revision_history: Annotated[list[dict], operator.add]
    revision_request: Optional[str]
    target_revision_sections: Optional[list[str]]
    approval_action: Optional[str]
    approval_comments: Optional[str]
    status: str
    error: Optional[str]


class ContractSectionState(TypedDict):
    section_name: str
    rfp_content: dict
    proposal_extraction: dict
    supplier_name: str
    model_id: str
    temperature: float
    section_content: Optional[str]
    validation_error: Optional[str]
    error: Optional[str]
