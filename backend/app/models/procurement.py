import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Procurement(Base):
    __tablename__ = "procurements"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String, nullable=False)
    business_objective: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    budget_min: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    budget_max: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    budget_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    timeline: Mapped[str] = mapped_column(String, nullable=False)
    evaluation_criteria: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    compliance_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(String, nullable=False, default="RFP")
    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")
    created_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    selected_proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    created_by_user = relationship("User", back_populates="procurements", foreign_keys=[created_by])
    rfps = relationship("RFP", back_populates="procurement", cascade="all, delete-orphan")
    proposals = relationship("SupplierProposal", back_populates="procurement", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="procurement", cascade="all, delete-orphan")
    contracts = relationship("Contract", back_populates="procurement", cascade="all, delete-orphan")
    approval_actions = relationship("ApprovalAction", back_populates="procurement", cascade="all, delete-orphan")
    workflow_runs = relationship("WorkflowRun", back_populates="procurement", cascade="all, delete-orphan")
    workflow_events = relationship("WorkflowEvent", back_populates="procurement", cascade="all, delete-orphan")
    workflow_model_configs = relationship("WorkflowModelConfig", back_populates="procurement", cascade="all, delete-orphan")
