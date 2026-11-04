from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from pgvector.sqlalchemy import Vector
from typing import Optional, Any
from app.database import Base

class ClinicalDocument(Base):
    __tablename__ = "clinical_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")
    upload_time: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    extracted_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True) 

    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384), nullable=True)