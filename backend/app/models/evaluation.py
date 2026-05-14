import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    procurement_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("procurements.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    evaluation_weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recommendation_proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("supplier_proposals.id"), nullable=True)
    recommendation_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    procurement = relationship("Procurement", back_populates="evaluations")
    scores = relationship("ProposalScore", back_populates="evaluation", cascade="all, delete-orphan")
    recommended_proposal = relationship("SupplierProposal", foreign_keys=[recommendation_proposal_id])
    approver = relationship("User", foreign_keys=[approved_by])


class ProposalScore(Base):
    __tablename__ = "proposal_scores"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("evaluations.id"), nullable=False)
    proposal_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("supplier_proposals.id"), nullable=False)
    technical_fit_score: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    cost_score: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    timeline_score: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    risk_score: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    weighted_total: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_assessment: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)

    evaluation = relationship("Evaluation", back_populates="scores")
    proposal = relationship("SupplierProposal", back_populates="scores")
