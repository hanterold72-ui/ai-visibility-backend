from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str] = mapped_column(String(255), unique=True)
    cms_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Audit(Base):
    __tablename__ = "audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    audit_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Optimization(Base):
    __tablename__ = "optimizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    page_url: Mapped[str] = mapped_column(String(500))
    optimization_type: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    changes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    applied_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class CitationTracking(Base):
    __tablename__ = "citation_tracking"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    query: Mapped[str] = mapped_column(String(500))
    engine: Mapped[str] = mapped_column(String(50))
    is_cited: Mapped[bool] = mapped_column(Boolean, default=False)
    citation_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class SearchEngine(str, Enum):
    PERPLEXITY = "perplexity"

class GeoCheckRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    target_domain: str
    engine: SearchEngine = SearchEngine.PERPLEXITY

class AuditRequest(BaseModel):
    domain: str

class ApplyOptimizationRequest(BaseModel):
    optimization_id: int
