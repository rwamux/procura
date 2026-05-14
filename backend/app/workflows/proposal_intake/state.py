import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict


class ProposalToProcess(TypedDict):
    proposal_id: str
    file_path: str
    mime_type: str
    supplier_name: str


class ExtractedProposal(TypedDict):
    proposal_id: str
    extracted_data: dict
    model_id: str


class FailedExtraction(TypedDict):
    proposal_id: str
    error: str


class ProposalIntakeState(TypedDict):
    procurement_id: str
    thread_id: str
    model_id: str
    temperature: float
    proposals_to_process: list[ProposalToProcess]
    extracted_proposals: Annotated[list[ExtractedProposal], operator.add]
    failed_extractions: Annotated[list[FailedExtraction], operator.add]
    reprocess_ids: Optional[list[str]]
    review_approved: Optional[bool]
    status: str
    error: Optional[str]


class ProposalExtractionState(TypedDict):
    procurement_id: str
    proposal_id: str
    file_path: str
    mime_type: str
    supplier_name: str
    model_id: str
    temperature: float
    raw_text: Optional[str]
    text_quality_ok: Optional[bool]
    extracted_data: Optional[dict]
    extraction_attempts: int
    error: Optional[str]
