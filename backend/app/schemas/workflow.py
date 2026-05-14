import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class WorkflowStartRequest(BaseModel):
    model_id: str
    model_label: str
    temperature: float = 0.3


class WorkflowResumeRequest(BaseModel):
    thread_id: str
    action: str
    comments: Optional[str] = None
    revision_request: Optional[str] = None
    manual_override_proposal_id: Optional[str] = None
    reprocess_ids: Optional[list[str]] = None
    target_sections: Optional[list[str]] = None


class ReplayRequest(BaseModel):
    thread_id: str
    checkpoint_id: str


class WorkflowRunOut(BaseModel):
    id: uuid.UUID
    procurement_id: uuid.UUID
    workflow_type: str
    thread_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class WorkflowEventOut(BaseModel):
    id: uuid.UUID
    thread_id: str
    node_name: str
    event_type: str
    payload: Optional[Any]
    model_id: Optional[str]
    tokens_used: Optional[int]
    latency_ms: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowModelConfigOut(BaseModel):
    id: uuid.UUID
    procurement_id: uuid.UUID
    workflow_type: str
    model_id: str
    model_label: str
    temperature: float

    model_config = {"from_attributes": True}


class WorkflowModelConfigUpdate(BaseModel):
    model_id: str
    model_label: str
    temperature: float = 0.3
