from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class ParseJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class FileStatus(str, Enum):
    UPLOADED = "uploaded"
    VALIDATED = "validated"
    PARSED = "parsed"
    REJECTED = "rejected"


class ReportStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Tenant(Base):
    __tablename__ = "saas_tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ApiKey(Base):
    __tablename__ = "saas_api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_tenants.id"), nullable=False, index=True
    )
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InvoiceFile(Base):
    __tablename__ = "saas_invoice_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_tenants.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), default="application/pdf", nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    bytes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(32), default=FileStatus.UPLOADED.value, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ParseJob(Base):
    __tablename__ = "saas_parse_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_saas_parse_jobs_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_tenants.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default=ParseJobStatus.QUEUED.value, nullable=False, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    queue_job_id: Mapped[str | None] = mapped_column(String(64))
    debug: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    records_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ParseJobFile(Base):
    __tablename__ = "saas_parse_job_files"

    parse_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_parse_jobs.id"), primary_key=True
    )
    file_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_invoice_files.id"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ReportParseJob(Base):
    __tablename__ = "saas_report_parse_jobs"

    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_reports.id"), primary_key=True
    )
    parse_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_parse_jobs.id"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class InvoiceRecord(Base):
    __tablename__ = "saas_invoice_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_tenants.id"), nullable=False, index=True
    )
    parse_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_parse_jobs.id"), nullable=False, index=True
    )
    vendor: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    file_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    invoice_number: Mapped[str | None] = mapped_column(String(128))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    invoice_total: Mapped[float | None] = mapped_column(Float)
    invoice_vat: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="ILS", nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class Report(Base):
    __tablename__ = "saas_reports"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_saas_reports_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_tenants.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default=ReportStatus.QUEUED.value, nullable=False, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    queue_job_id: Mapped[str | None] = mapped_column(String(64))
    requested_formats_json: Mapped[str] = mapped_column(
        Text, default='["json","csv","summary_csv"]', nullable=False
    )
    filters_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReportArtifact(Base):
    __tablename__ = "saas_report_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_tenants.id"), nullable=False, index=True
    )
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_reports.id"), nullable=False, index=True
    )
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    bytes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "saas_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_tenants.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(255))
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class IdempotencyRecord(Base):
    __tablename__ = "saas_idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "scope", "idempotency_key", name="uq_saas_idempotency_scope_key"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("saas_tenants.id"), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
