import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), default="DevPilot Engineer")
    role = Column(String(50), default="DEVELOPER", nullable=False)  # ADMIN, DEVELOPER, VIEWER
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="refresh_tokens")


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    owner = Column(String(255), default="local")
    clone_url = Column(String(500), nullable=True)
    local_path = Column(String(500), nullable=True)
    branch = Column(String(100), default="main")
    status = Column(String(50), default="idle")  # idle, cloning, indexing, ready, error
    total_files = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    files = relationship("CodeFile", back_populates="repository", cascade="all, delete-orphan")
    chunks = relationship("CodeChunk", back_populates="repository", cascade="all, delete-orphan")


class CodeFile(Base):
    __tablename__ = "code_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    language = Column(String(50), default="unknown")
    size_bytes = Column(Integer, default=0)
    total_lines = Column(Integer, default=0)
    symbols_summary = Column(Text, nullable=True)  # JSON summary of classes/functions
    created_at = Column(DateTime, default=utc_now)

    repository = relationship("Repository", back_populates="files")
    chunks = relationship("CodeChunk", back_populates="code_file", cascade="all, delete-orphan")


class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_id = Column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(String(36), ForeignKey("code_files.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, default=0)
    file_path = Column(String(500), nullable=False)
    symbol_name = Column(String(255), nullable=True)
    symbol_type = Column(String(50), default="code_block")  # function, class, module, block
    start_line = Column(Integer, default=1)
    end_line = Column(Integer, default=1)
    content = Column(Text, nullable=False)
    embedding_json = Column(Text, nullable=True)  # JSON string representation of vector for dual SQLite/Postgres
    created_at = Column(DateTime, default=utc_now)

    repository = relationship("Repository", back_populates="chunks")
    code_file = relationship("CodeFile", back_populates="chunks")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type = Column(String(100), nullable=False)  # repository_ingestion, issue_analysis, pr_review, agent_workflow
    status = Column(String(50), default="queued")   # queued, processing, completed, failed
    progress = Column(Integer, default=0)           # 0 to 100%
    result_json = Column(Text, nullable=True)       # serialized payload
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    faithfulness_score = Column(Float, default=0.0)
    answer_relevance_score = Column(Float, default=0.0)
    retrieval_recall_score = Column(Float, default=0.0)
    avg_latency_sec = Column(Float, default=0.0)
    total_samples = Column(Integer, default=0)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
