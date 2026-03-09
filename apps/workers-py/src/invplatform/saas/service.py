from __future__ import annotations

from contextlib import contextmanager
import json
from datetime import date
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from . import auth
from .models import (
    ApiKey,
    AuditEvent,
    FileStatus,
    IdempotencyRecord,
    InvoiceFile,
    InvoiceRecord,
    ParseJob,
    ParseJobFile,
    Report,
    ReportArtifact,
    ReportParseJob,
    Tenant,
)
from .queue import JobQueue
from .repository import TenantScopedRepository

PARSE_JOB_TASK = "invplatform.saas.tasks.run_parse_job_task"
REPORT_JOB_TASK = "invplatform.saas.tasks.run_report_job_task"
REPORT_CLEANUP_TASK = "invplatform.saas.tasks.run_report_retention_cleanup_task"
_REPORT_ALLOWED_FORMATS = {"json", "csv", "summary_csv", "pdf"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ServiceConfig:
    parse_job_task_name: str = PARSE_JOB_TASK
    report_job_task_name: str = REPORT_JOB_TASK
    report_cleanup_task_name: str = REPORT_CLEANUP_TASK


@dataclass
class SaaSService:
    session_factory: sessionmaker[Session]
    queue: JobQueue
    config: ServiceConfig = field(default_factory=ServiceConfig)

    @contextmanager
    def _tenant_scope(self, session: Session, tenant_id: str):
        previous_tenant = session.info.get("tenant_id")
        session.info["tenant_id"] = tenant_id
        try:
            yield
        finally:
            if previous_tenant is None:
                session.info.pop("tenant_id", None)
            else:
                session.info["tenant_id"] = previous_tenant

    def _resolve_idempotent_parse_job(
        self, session: Session, tenant_id: str, idempotency_key: str
    ) -> ParseJob | None:
        record = session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == tenant_id,
                IdempotencyRecord.scope == "parse_jobs.create",
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if record is None:
            return None
        return session.execute(
            select(ParseJob).where(
                ParseJob.tenant_id == tenant_id, ParseJob.id == record.resource_id
            )
        ).scalar_one_or_none()

    def _resolve_idempotent_report(
        self, session: Session, tenant_id: str, idempotency_key: str
    ) -> Report | None:
        record = session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == tenant_id,
                IdempotencyRecord.scope == "reports.create",
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if record is None:
            return None
        return session.execute(
            select(Report).where(Report.tenant_id == tenant_id, Report.id == record.resource_id)
        ).scalar_one_or_none()

    def bootstrap_tenant(self, name: str, actor: str | None = None) -> tuple[Tenant, str]:
        api_key_material = auth.generate_api_key()
        with self.session_factory() as session:
            tenant = Tenant(name=name)
            session.add(tenant)
            session.flush()

            api_key = ApiKey(
                tenant_id=tenant.id,
                key_prefix=api_key_material.key_prefix,
                key_hash=api_key_material.key_hash,
            )
            session.add(api_key)
            session.add(
                AuditEvent(
                    tenant_id=tenant.id,
                    event_type="tenant.bootstrap",
                    actor=actor,
                    payload_json=json.dumps({"tenant_name": name}),
                )
            )
            session.commit()
            session.refresh(tenant)
            return tenant, api_key_material.plain_text

    def list_tenants(self, limit: int = 100, offset: int = 0) -> tuple[list[Tenant], int]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if offset < 0:
            raise ValueError("offset must be >= 0")

        with self.session_factory() as session:
            session.info["disable_tenant_guard"] = True
            total = int(session.execute(select(func.count()).select_from(Tenant)).scalar_one())
            tenants = list(
                session.execute(
                    select(Tenant)
                    .order_by(Tenant.created_at.desc(), Tenant.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
                .scalars()
                .all()
            )
            return tenants, total

    def list_api_keys(self, tenant_id: str) -> list[ApiKey]:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                return list(
                    session.execute(
                        select(ApiKey)
                        .where(ApiKey.tenant_id == tenant_id)
                        .order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
                    )
                    .scalars()
                    .all()
                )

    def create_api_key(self, tenant_id: str, actor: str | None = None) -> tuple[ApiKey, str]:
        material = auth.generate_api_key()
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                api_key = ApiKey(
                    tenant_id=tenant_id,
                    key_prefix=material.key_prefix,
                    key_hash=material.key_hash,
                )
                session.add(api_key)
                session.flush()
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="api_key.create",
                        actor=actor,
                        payload_json=json.dumps(
                            {"api_key_id": api_key.id, "key_prefix": api_key.key_prefix}
                        ),
                    )
                )
                session.commit()
                session.refresh(api_key)
                return api_key, material.plain_text

    def rotate_api_key(
        self, tenant_id: str, api_key_id: str, actor: str | None = None
    ) -> tuple[ApiKey, str]:
        material = auth.generate_api_key()
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                key_row = session.execute(
                    select(ApiKey).where(ApiKey.tenant_id == tenant_id, ApiKey.id == api_key_id)
                ).scalar_one_or_none()
                if key_row is None:
                    raise ValueError("api key not found")
                if key_row.revoked:
                    raise ValueError("cannot rotate revoked api key")
                key_row.key_prefix = material.key_prefix
                key_row.key_hash = material.key_hash
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="api_key.rotate",
                        actor=actor,
                        payload_json=json.dumps(
                            {"api_key_id": key_row.id, "key_prefix": key_row.key_prefix}
                        ),
                    )
                )
                session.commit()
                session.refresh(key_row)
                return key_row, material.plain_text

    def revoke_api_key(self, tenant_id: str, api_key_id: str, actor: str | None = None) -> ApiKey:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                key_row = session.execute(
                    select(ApiKey).where(ApiKey.tenant_id == tenant_id, ApiKey.id == api_key_id)
                ).scalar_one_or_none()
                if key_row is None:
                    raise ValueError("api key not found")
                key_row.revoked = True
                key_row.revoked_at = _utcnow()
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="api_key.revoke",
                        actor=actor,
                        payload_json=json.dumps({"api_key_id": key_row.id}),
                    )
                )
                session.commit()
                session.refresh(key_row)
                return key_row

    def register_file(
        self,
        tenant_id: str,
        filename: str,
        storage_path: str,
        mime_type: str = "application/pdf",
        content_sha256: str | None = None,
        bytes_size: int | None = None,
    ) -> InvoiceFile:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                file_row = InvoiceFile(
                    tenant_id=tenant_id,
                    filename=filename,
                    storage_path=storage_path,
                    mime_type=mime_type,
                    content_sha256=content_sha256,
                    bytes=bytes_size,
                    status=FileStatus.UPLOADED.value,
                )
                session.add(file_row)
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="file.register",
                        payload_json=json.dumps({"filename": filename}),
                    )
                )
                session.commit()
                session.refresh(file_row)
                return file_row

    def create_parse_job(
        self,
        tenant_id: str,
        file_ids: list[str],
        debug: bool = False,
        idempotency_key: str | None = None,
    ) -> ParseJob:
        if not file_ids:
            raise ValueError("file_ids cannot be empty")
        normalized_key = (idempotency_key or "").strip() or None

        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                if normalized_key is not None:
                    existing_job = self._resolve_idempotent_parse_job(
                        session, tenant_id, normalized_key
                    )
                    if existing_job is not None:
                        return existing_job

                files = list(
                    session.execute(
                        select(InvoiceFile).where(
                            InvoiceFile.tenant_id == tenant_id,
                            InvoiceFile.id.in_(file_ids),
                        )
                    )
                    .scalars()
                    .all()
                )
                found_ids = {item.id for item in files}
                missing_ids = sorted(set(file_ids) - found_ids)
                if missing_ids:
                    raise ValueError(f"unknown file ids for tenant: {', '.join(missing_ids)}")

                job = ParseJob(tenant_id=tenant_id, debug=debug, idempotency_key=normalized_key)
                session.add(job)
                session.flush()

                for file_id in file_ids:
                    session.add(ParseJobFile(parse_job_id=job.id, file_id=file_id))

                queue_job_id = self.queue.enqueue(
                    self.config.parse_job_task_name,
                    {"parse_job_id": job.id},
                )
                job.queue_job_id = queue_job_id
                if normalized_key is not None:
                    session.add(
                        IdempotencyRecord(
                            tenant_id=tenant_id,
                            scope="parse_jobs.create",
                            idempotency_key=normalized_key,
                            resource_type="parse_job",
                            resource_id=job.id,
                        )
                    )
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="parse_job.create",
                        payload_json=json.dumps(
                            {
                                "parse_job_id": job.id,
                                "queue_job_id": queue_job_id,
                                "file_ids": file_ids,
                                "idempotency_key": normalized_key,
                            }
                        ),
                    )
                )
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    if normalized_key is None:
                        raise
                    existing_job = self._resolve_idempotent_parse_job(
                        session, tenant_id, normalized_key
                    )
                    if existing_job is None:
                        raise
                    return existing_job
                session.refresh(job)
                return job

    def get_parse_job(self, tenant_id: str, parse_job_id: str) -> ParseJob | None:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                repo = TenantScopedRepository(session, tenant_id)
                return cast(
                    ParseJob | None, repo.one_or_none(ParseJob, ParseJob.id == parse_job_id)
                )

    def get_tenant_by_api_key(self, raw_api_key: str) -> Tenant | None:
        with self.session_factory() as session:
            tenant_id = auth.resolve_tenant_id_from_api_key(session, raw_api_key)
            if tenant_id is None:
                return None
            tenant = session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            ).scalar_one_or_none()
            return cast(Tenant | None, tenant)

    def get_invoice(self, tenant_id: str, invoice_id: str) -> InvoiceRecord | None:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                repo = TenantScopedRepository(session, tenant_id)
                return cast(
                    InvoiceRecord | None,
                    repo.one_or_none(InvoiceRecord, InvoiceRecord.id == invoice_id),
                )

    def list_invoices(
        self,
        tenant_id: str,
        parse_job_id: str | None = None,
        vendor: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[InvoiceRecord], int]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if offset < 0:
            raise ValueError("offset must be >= 0")

        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                repo = TenantScopedRepository(session, tenant_id)
                filters: list[object] = []
                if parse_job_id:
                    filters.append(InvoiceRecord.parse_job_id == parse_job_id)
                if vendor:
                    filters.append(func.lower(InvoiceRecord.vendor).like(f"%{vendor.lower()}%"))
                if from_date:
                    filters.append(InvoiceRecord.invoice_date >= from_date)
                if to_date:
                    filters.append(InvoiceRecord.invoice_date <= to_date)

                total = repo.count(InvoiceRecord, *filters)
                items = cast(
                    list[InvoiceRecord],
                    repo.list(
                        InvoiceRecord,
                        *filters,
                        order_by=[InvoiceRecord.created_at.desc(), InvoiceRecord.id.desc()],
                        limit=limit,
                        offset=offset,
                    ),
                )
                return items, total

    def create_report_job(
        self,
        tenant_id: str,
        parse_job_ids: list[str] | None = None,
        formats: list[str] | None = None,
        filters: dict[str, object] | None = None,
        idempotency_key: str | None = None,
    ) -> Report:
        requested_formats = formats or ["json", "csv", "summary_csv"]
        invalid_formats = sorted(set(requested_formats) - _REPORT_ALLOWED_FORMATS)
        if invalid_formats:
            raise ValueError(f"unsupported report formats: {', '.join(invalid_formats)}")
        normalized_key = (idempotency_key or "").strip() or None
        filters = filters or {}
        parse_job_ids = parse_job_ids or []

        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                if normalized_key is not None:
                    existing_report = self._resolve_idempotent_report(
                        session, tenant_id, normalized_key
                    )
                    if existing_report is not None:
                        return existing_report

                if parse_job_ids:
                    jobs = list(
                        session.execute(
                            select(ParseJob).where(
                                ParseJob.tenant_id == tenant_id,
                                ParseJob.id.in_(parse_job_ids),
                            )
                        )
                        .scalars()
                        .all()
                    )
                    found_ids = {item.id for item in jobs}
                    missing_ids = sorted(set(parse_job_ids) - found_ids)
                    if missing_ids:
                        raise ValueError(
                            f"unknown parse_job ids for tenant: {', '.join(missing_ids)}"
                        )

                report = Report(
                    tenant_id=tenant_id,
                    idempotency_key=normalized_key,
                    requested_formats_json=json.dumps(requested_formats),
                    filters_json=json.dumps(filters),
                )
                session.add(report)
                session.flush()

                for parse_job_id in parse_job_ids:
                    session.add(ReportParseJob(report_id=report.id, parse_job_id=parse_job_id))

                queue_job_id = self.queue.enqueue(
                    self.config.report_job_task_name,
                    {"report_id": report.id},
                )
                report.queue_job_id = queue_job_id
                if normalized_key is not None:
                    session.add(
                        IdempotencyRecord(
                            tenant_id=tenant_id,
                            scope="reports.create",
                            idempotency_key=normalized_key,
                            resource_type="report",
                            resource_id=report.id,
                        )
                    )
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="report.create",
                        payload_json=json.dumps(
                            {
                                "report_id": report.id,
                                "queue_job_id": queue_job_id,
                                "parse_job_ids": parse_job_ids,
                                "formats": requested_formats,
                                "idempotency_key": normalized_key,
                            }
                        ),
                    )
                )
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    if normalized_key is None:
                        raise
                    existing_report = self._resolve_idempotent_report(
                        session, tenant_id, normalized_key
                    )
                    if existing_report is None:
                        raise
                    return existing_report
                session.refresh(report)
                return report

    def get_report(self, tenant_id: str, report_id: str) -> Report | None:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                repo = TenantScopedRepository(session, tenant_id)
                return cast(Report | None, repo.one_or_none(Report, Report.id == report_id))

    def list_report_artifacts(self, tenant_id: str, report_id: str) -> list[ReportArtifact]:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                repo = TenantScopedRepository(session, tenant_id)
                return cast(
                    list[ReportArtifact],
                    repo.list(
                        ReportArtifact,
                        ReportArtifact.report_id == report_id,
                        order_by=[ReportArtifact.created_at.desc(), ReportArtifact.id.desc()],
                    ),
                )

    def list_reports(
        self,
        tenant_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Report], int]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if offset < 0:
            raise ValueError("offset must be >= 0")

        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                repo = TenantScopedRepository(session, tenant_id)
                filters: list[object] = []
                if status:
                    filters.append(Report.status == status)
                total = repo.count(Report, *filters)
                reports = cast(
                    list[Report],
                    repo.list(
                        Report,
                        *filters,
                        order_by=[Report.created_at.desc(), Report.id.desc()],
                        limit=limit,
                        offset=offset,
                    ),
                )
                return reports, total

    def retry_report_job(self, tenant_id: str, report_id: str) -> Report:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                repo = TenantScopedRepository(session, tenant_id)
                report = cast(Report | None, repo.one_or_none(Report, Report.id == report_id))
                if report is None:
                    raise ValueError("report not found")

                queue_job_id = self.queue.enqueue(
                    self.config.report_job_task_name,
                    {"report_id": report.id},
                )
                report.queue_job_id = queue_job_id
                report.status = "queued"
                report.error_message = None
                report.started_at = None
                report.finished_at = None
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="report.retry",
                        payload_json=json.dumps(
                            {"report_id": report.id, "queue_job_id": queue_job_id}
                        ),
                    )
                )
                session.commit()
                session.refresh(report)
                return report

    def enqueue_report_cleanup(self, retention_days: int) -> str:
        if retention_days < 1:
            raise ValueError("retention_days must be >= 1")
        return self.queue.enqueue(
            self.config.report_cleanup_task_name,
            {"retention_days": str(retention_days)},
        )

    def record_audit_event(
        self,
        tenant_id: str,
        event_type: str,
        payload: dict[str, object],
        actor: str | None = None,
    ) -> None:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type=event_type,
                        actor=actor,
                        payload_json=json.dumps(payload),
                    )
                )
                session.commit()

    def dashboard_summary(self, tenant_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                repo = TenantScopedRepository(session, tenant_id)
                parse_jobs_total = repo.count(ParseJob)
                reports_total = repo.count(Report)
                invoices_total = repo.count(InvoiceRecord)
                files_total = repo.count(InvoiceFile)

                parse_by_status = {
                    "queued": repo.count(ParseJob, ParseJob.status == "queued"),
                    "running": repo.count(ParseJob, ParseJob.status == "running"),
                    "succeeded": repo.count(ParseJob, ParseJob.status == "succeeded"),
                    "failed": repo.count(ParseJob, ParseJob.status == "failed"),
                }
                reports_by_status = {
                    "queued": repo.count(Report, Report.status == "queued"),
                    "running": repo.count(Report, Report.status == "running"),
                    "succeeded": repo.count(Report, Report.status == "succeeded"),
                    "failed": repo.count(Report, Report.status == "failed"),
                }
                recent_parse_jobs = repo.list(
                    ParseJob,
                    order_by=[ParseJob.created_at.desc(), ParseJob.id.desc()],
                    limit=10,
                    offset=0,
                )
                recent_reports = repo.list(
                    Report,
                    order_by=[Report.created_at.desc(), Report.id.desc()],
                    limit=10,
                    offset=0,
                )

                def _to_iso(value: object) -> str | None:
                    if isinstance(value, datetime):
                        return value.isoformat()
                    return None

                return {
                    "totals": {
                        "files": files_total,
                        "parse_jobs": parse_jobs_total,
                        "invoices": invoices_total,
                        "reports": reports_total,
                    },
                    "parse_jobs_by_status": parse_by_status,
                    "reports_by_status": reports_by_status,
                    "recent_parse_jobs": [
                        {
                            "id": item.id,
                            "status": item.status,
                            "records_count": item.records_count,
                            "failed_count": item.failed_count,
                            "created_at": _to_iso(item.created_at),
                            "finished_at": _to_iso(item.finished_at),
                        }
                        for item in cast(list[ParseJob], recent_parse_jobs)
                    ],
                    "recent_reports": [
                        {
                            "id": item.id,
                            "status": item.status,
                            "created_at": _to_iso(item.created_at),
                            "finished_at": _to_iso(item.finished_at),
                        }
                        for item in cast(list[Report], recent_reports)
                    ],
                }
