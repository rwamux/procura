import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SupplierProposal(Base):
    __tablename__ = "supplier_proposals"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    procurement_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("procurements.id"), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    extraction_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String, nullable=False, default="SUBMITTED")
    status: Mapped[str] = mapped_column(String, nullable=False, default="SUBMITTED")
    upload_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    extraction_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    procurement = relationship("Procurement", back_populates="proposals")
    scores = relationship("ProposalScore", back_populates="proposal", cascade="all, delete-orphan")
