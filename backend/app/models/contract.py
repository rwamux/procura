import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    procurement_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("procurements.id"), nullable=False)
    proposal_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("supplier_proposals.id"), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    draft_content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="DRAFT")
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    generation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    procurement = relationship("Procurement", back_populates="contracts")
    proposal = relationship("SupplierProposal")
    revisions = relationship("ContractRevision", back_populates="contract", cascade="all, delete-orphan")


class ContractRevision(Base):
    __tablename__ = "contract_revisions"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    revision_request: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contract = relationship("Contract", back_populates="revisions")
