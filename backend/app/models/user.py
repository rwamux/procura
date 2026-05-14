import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="PROCUREMENT_OFFICER")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    procurements = relationship("Procurement", back_populates="created_by_user", foreign_keys="Procurement.created_by")
    approval_actions = relationship("ApprovalAction", back_populates="actor")
