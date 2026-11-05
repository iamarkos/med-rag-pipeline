import uuid
from sqlalchemy import String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from pgvector.sqlalchemy import Vector
from typing import Optional, Any
from app.database import Base

class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    documents: Mapped[list["ClinicalDocument"]] = relationship(back_populates="patient")


class ClinicalDocument(Base):
    __tablename__ = "clinical_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")
    upload_time: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Only stores UUID, no id
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    
    extracted_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True) 
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="documents")