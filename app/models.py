import uuid
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.status import DocumentStatus


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    documents: Mapped[list["ClinicalDocument"]] = relationship(back_populates="patient")


class ClinicalDocument(Base):
    __tablename__ = "clinical_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default=DocumentStatus.PENDING)
    # Set only when status is "failed": a short code from app.status.ErrorCode
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    upload_time: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    # Only stores UUID, no id
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id"), nullable=False
    )

    extracted_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="documents")
