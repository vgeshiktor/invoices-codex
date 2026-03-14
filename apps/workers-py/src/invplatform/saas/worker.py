from __future__ import annotations

import csv
from dataclasses import dataclass
import json
import os
from collections.abc import Callable
from datetime import date
from datetime import datetime, timedelta, timezone
from io import StringIO
import uuid
from typing import cast
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from invplatform.usecases import report_pipeline

from .storage import StorageBackend, build_storage
from .models import (
    AuditEvent,
    CollectionJob,
    CollectionJobStatus,
    FileStatus,
    IdempotencyRecord,
    InvoiceFile,
    InvoiceRecord,
    ParseJob,
    ParseJobFile,
    ParseJobStatus,
    ProviderConfig,
    Report,
    ReportArtifact,
    ReportParseJob,
    ReportStatus,
)
from .queue import JobQueue, build_queue

_PARSE_JOB_TASK_NAME = "invplatform.saas.tasks.run_parse_job_task"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_parse_paths(paths: list[Path], debug: bool) -> list[object]:
    # Imported lazily to avoid CLI import costs for non-worker flows.
    from invplatform.cli import invoices_report

    parse_invoice_fn = cast(Callable[[Path, bool], object], invoices_report.parse_invoice)
    split_fn = cast(
        Callable[[Path, object, bool], list[object]],
        invoices_report.split_municipal_multi_invoice,
    )
    return report_pipeline.parse_paths(
        paths=paths,
        debug=debug,
        parse_invoice_fn=parse_invoice_fn,
        split_municipal_multi_invoice_fn=split_fn,
    )


def _to_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _invoice_to_export_row(record: InvoiceRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "parse_job_id": record.parse_job_id,
        "vendor": record.vendor,
        "file_name": record.file_name,
        "invoice_number": record.invoice_number,
        "invoice_date": record.invoice_date.isoformat() if record.invoice_date else None,
        "invoice_total": record.invoice_total,
        "invoice_vat": record.invoice_vat,
        "currency": record.currency,
        "purpose": record.purpose,
    }


def _write_json_report(path: Path, records: list[InvoiceRecord]) -> int:
    payload = [_invoice_to_export_row(item) for item in records]
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    return path.stat().st_size


def _json_report_bytes(records: list[InvoiceRecord]) -> bytes:
    payload = [_invoice_to_export_row(item) for item in records]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _write_csv_report(path: Path, records: list[InvoiceRecord]) -> int:
    columns = [
        "id",
        "parse_job_id",
        "vendor",
        "file_name",
        "invoice_number",
        "invoice_date",
        "invoice_total",
        "invoice_vat",
        "currency",
        "purpose",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in records:
            writer.writerow(_invoice_to_export_row(row))
    return path.stat().st_size


def _csv_report_bytes(records: list[InvoiceRecord]) -> bytes:
    buffer = StringIO()
    columns = [
        "id",
        "parse_job_id",
        "vendor",
        "file_name",
        "invoice_number",
        "invoice_date",
        "invoice_total",
        "invoice_vat",
        "currency",
        "purpose",
    ]
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for row in records:
        writer.writerow(_invoice_to_export_row(row))
    return buffer.getvalue().encode("utf-8")


def _write_summary_csv_report(path: Path, records: list[InvoiceRecord]) -> int:
    vendor_totals: dict[str, float] = {}
    for item in records:
        vendor = item.vendor or ""
        vendor_totals[vendor] = vendor_totals.get(vendor, 0.0) + float(item.invoice_total or 0.0)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["vendor", "invoice_total"])
        for vendor in sorted(vendor_totals):
            writer.writerow([vendor, f"{vendor_totals[vendor]:.2f}"])
    return path.stat().st_size


def _summary_csv_report_bytes(records: list[InvoiceRecord]) -> bytes:
    vendor_totals: dict[str, float] = {}
    for item in records:
        vendor = item.vendor or ""
        vendor_totals[vendor] = vendor_totals.get(vendor, 0.0) + float(item.invoice_total or 0.0)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["vendor", "invoice_total"])
    for vendor in sorted(vendor_totals):
        writer.writerow([vendor, f"{vendor_totals[vendor]:.2f}"])
    return buffer.getvalue().encode("utf-8")


def _write_pdf_report(path: Path) -> int:
    try:
        from pypdf import PdfWriter  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        # Minimal valid single-page PDF placeholder for environments without pypdf.
        minimal_pdf = (
            b"%PDF-1.1\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000110 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n170\n%%EOF\n"
        )
        path.write_bytes(minimal_pdf)
        return path.stat().st_size
    else:
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with path.open("wb") as f:
            writer.write(f)
    return path.stat().st_size


def _pdf_report_bytes() -> bytes:
    try:
        from pypdf import PdfWriter  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return (
            b"%PDF-1.1\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000110 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n170\n%%EOF\n"
        )
    from io import BytesIO

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


@dataclass(frozen=True)
class CollectedProviderFile:
    filename: str
    content: bytes
    mime_type: str = "application/pdf"


CollectionProviderExecutor = Callable[[ProviderConfig, str, str], list[CollectedProviderFile]]


def _decode_collection_list(raw_json: str) -> list[str]:
    try:
        loaded = json.loads(raw_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    result: list[str] = []
    for value in loaded:
        normalized = str(value).strip().lower()
        if normalized:
            result.append(normalized)
    return result


def _default_provider_executor(
    provider: ProviderConfig, month_scope: str, collection_job_id: str
) -> list[CollectedProviderFile]:
    month_label = month_scope.replace("-", "")
    filename = f"{provider.provider_type}_invoice_{month_label}_{collection_job_id[:8]}.pdf"
    return [CollectedProviderFile(filename=filename, content=_pdf_report_bytes())]


def run_collection_job(
    session_factory: sessionmaker[Session],
    collection_job_id: str,
    *,
    storage_backend: StorageBackend | None = None,
    queue: JobQueue | None = None,
    parse_job_task_name: str = _PARSE_JOB_TASK_NAME,
    provider_executor: CollectionProviderExecutor | None = None,
) -> CollectionJobStatus:
    storage = storage_backend or build_storage(os.environ.get("SAAS_STORAGE_URL"))
    queue = queue or build_queue(os.environ.get("SAAS_REDIS_URL"))
    execute_provider = provider_executor or _default_provider_executor

    with session_factory() as session:
        session.info["disable_tenant_guard"] = True
        job = session.execute(
            select(CollectionJob).where(CollectionJob.id == collection_job_id)
        ).scalar_one_or_none()
        if job is None:
            raise ValueError(f"collection job not found: {collection_job_id}")
        if job.status in {
            CollectionJobStatus.SUCCEEDED.value,
            CollectionJobStatus.FAILED.value,
            CollectionJobStatus.RUNNING.value,
        }:
            return CollectionJobStatus(job.status)
        job.status = CollectionJobStatus.RUNNING.value
        job.started_at = _utcnow()
        job.updated_at = _utcnow()
        job.error_message = None
        session.add(
            AuditEvent(
                tenant_id=job.tenant_id,
                event_type="collection_job.run.started",
                payload_json=json.dumps({"collection_job_id": job.id}),
            )
        )
        session.commit()

    try:
        with session_factory() as session:
            session.info["disable_tenant_guard"] = True
            job = session.execute(
                select(CollectionJob).where(CollectionJob.id == collection_job_id)
            ).scalar_one()
            providers = _decode_collection_list(job.providers_json)
            if not providers:
                raise ValueError("collection job has no providers")

            provider_rows = list(
                session.execute(
                    select(ProviderConfig).where(
                        ProviderConfig.tenant_id == job.tenant_id,
                        ProviderConfig.provider_type.in_(providers),
                    )
                )
                .scalars()
                .all()
            )
            provider_by_type = {item.provider_type: item for item in provider_rows}

            failures: list[dict[str, str]] = []
            files_by_provider: dict[str, list[str]] = {}
            files_discovered = 0
            files_downloaded = 0

            for provider_name in providers:
                provider = provider_by_type.get(provider_name)
                if provider is None:
                    failures.append(
                        {
                            "provider": provider_name,
                            "code": "PROVIDER_NOT_FOUND",
                            "message": "provider config not found",
                        }
                    )
                    continue
                if provider.connection_status != "connected" or not provider.oauth_access_token_enc:
                    failures.append(
                        {
                            "provider": provider_name,
                            "code": "PROVIDER_NOT_CONNECTED",
                            "message": "provider is not connected",
                        }
                    )
                    continue

                try:
                    collected_files = execute_provider(
                        provider,
                        job.month_scope,
                        job.id,
                    )
                except Exception as exc:
                    failures.append(
                        {
                            "provider": provider_name,
                            "code": "PROVIDER_EXECUTOR_ERROR",
                            "message": str(exc),
                        }
                    )
                    continue

                files_discovered += len(collected_files)
                for idx, collected in enumerate(collected_files, start=1):
                    if not collected.content:
                        failures.append(
                            {
                                "provider": provider_name,
                                "code": "PROVIDER_FILE_EMPTY",
                                "message": f"provider returned empty file payload at index {idx}",
                            }
                        )
                        continue
                    filename = Path(collected.filename).name or f"{provider_name}-{idx}.pdf"
                    storage_key = (
                        f"uploads/{job.tenant_id}/collection_{job.id}/"
                        f"{provider_name}/{uuid.uuid4().hex}_{filename}"
                    )
                    stored = storage.save_bytes(storage_key, collected.content)
                    file_row = InvoiceFile(
                        tenant_id=job.tenant_id,
                        filename=filename,
                        storage_path=stored.key,
                        mime_type=collected.mime_type,
                        content_sha256=stored.sha256,
                        bytes=stored.size,
                        status=FileStatus.UPLOADED.value,
                    )
                    session.add(file_row)
                    session.flush()
                    files_downloaded += 1
                    files_by_provider.setdefault(provider_name, []).append(file_row.id)

            parse_job_ids: list[str] = []
            for provider_name, file_ids in files_by_provider.items():
                if not file_ids:
                    continue
                parse_idempotency_key = f"collection:{job.id}:{provider_name}"
                parse_job = ParseJob(
                    tenant_id=job.tenant_id,
                    debug=False,
                    idempotency_key=parse_idempotency_key,
                )
                session.add(parse_job)
                session.flush()
                for file_id in file_ids:
                    session.add(ParseJobFile(parse_job_id=parse_job.id, file_id=file_id))
                parse_queue_job_id = queue.enqueue(
                    parse_job_task_name,
                    {"parse_job_id": parse_job.id},
                )
                parse_job.queue_job_id = parse_queue_job_id
                session.add(
                    IdempotencyRecord(
                        tenant_id=job.tenant_id,
                        scope="parse_jobs.create",
                        idempotency_key=parse_idempotency_key,
                        resource_type="parse_job",
                        resource_id=parse_job.id,
                    )
                )
                session.add(
                    AuditEvent(
                        tenant_id=job.tenant_id,
                        event_type="parse_job.create",
                        payload_json=json.dumps(
                            {
                                "parse_job_id": parse_job.id,
                                "queue_job_id": parse_queue_job_id,
                                "file_ids": file_ids,
                                "idempotency_key": parse_idempotency_key,
                                "collection_job_id": job.id,
                                "provider": provider_name,
                            }
                        ),
                    )
                )
                parse_job_ids.append(parse_job.id)

            if files_downloaded == 0 and not failures:
                failures.append(
                    {
                        "provider": "all",
                        "code": "NO_FILES_DOWNLOADED",
                        "message": "collection completed without downloadable files",
                    }
                )

            status = CollectionJobStatus.SUCCEEDED if not failures else CollectionJobStatus.FAILED
            job.status = status.value
            job.files_discovered = files_discovered
            job.files_downloaded = files_downloaded
            job.parse_job_ids_json = json.dumps(parse_job_ids, sort_keys=True)
            job.error_message = (
                None
                if status == CollectionJobStatus.SUCCEEDED
                else json.dumps({"provider_failures": failures}, sort_keys=True)
            )
            job.finished_at = _utcnow()
            job.updated_at = _utcnow()
            session.add(
                AuditEvent(
                    tenant_id=job.tenant_id,
                    event_type=f"collection_job.run.{status.value}",
                    payload_json=json.dumps(
                        {
                            "collection_job_id": job.id,
                            "files_discovered": files_discovered,
                            "files_downloaded": files_downloaded,
                            "parse_job_ids": parse_job_ids,
                            "failure_count": len(failures),
                        }
                    ),
                )
            )
            session.commit()
            return status
    except Exception as exc:
        with session_factory() as session:
            session.info["disable_tenant_guard"] = True
            job = session.execute(
                select(CollectionJob).where(CollectionJob.id == collection_job_id)
            ).scalar_one_or_none()
            if job is None:
                raise ValueError(f"collection job not found: {collection_job_id}") from exc
            job.status = CollectionJobStatus.FAILED.value
            job.error_message = str(exc)
            job.finished_at = _utcnow()
            job.updated_at = _utcnow()
            session.add(
                AuditEvent(
                    tenant_id=job.tenant_id,
                    event_type="collection_job.run.failed",
                    payload_json=json.dumps(
                        {"collection_job_id": job.id, "error_message": str(exc)}
                    ),
                )
            )
            session.commit()
        return CollectionJobStatus.FAILED


def run_parse_job(
    session_factory: sessionmaker[Session],
    parse_job_id: str,
    parse_paths_fn: Callable[[list[Path], bool], list[object]] | None = None,
    storage_backend: StorageBackend | None = None,
) -> ParseJobStatus:
    parse_paths = parse_paths_fn or _default_parse_paths
    storage = storage_backend or build_storage(os.environ.get("SAAS_STORAGE_URL"))

    with session_factory() as session:
        session.info["disable_tenant_guard"] = True
        job = session.execute(
            select(ParseJob).where(ParseJob.id == parse_job_id)
        ).scalar_one_or_none()
        if job is None:
            raise ValueError(f"parse job not found: {parse_job_id}")

        job.status = ParseJobStatus.RUNNING.value
        job.started_at = _utcnow()
        session.commit()

    try:
        with session_factory() as session:
            session.info["disable_tenant_guard"] = True
            job = session.execute(select(ParseJob).where(ParseJob.id == parse_job_id)).scalar_one()
            links = list(
                session.execute(
                    select(ParseJobFile, InvoiceFile)
                    .join(InvoiceFile, ParseJobFile.file_id == InvoiceFile.id)
                    .where(ParseJobFile.parse_job_id == parse_job_id)
                ).all()
            )
            files: list[InvoiceFile] = [row[1] for row in links]
            if not files:
                raise ValueError(f"parse job has no files: {parse_job_id}")

            records = parse_paths(
                [storage.resolve_local_path(item.storage_path) for item in files],
                bool(job.debug),
            )
            for record in records:
                invoice_date = _to_date(getattr(record, "invoice_date", None))
                payload = {
                    "vendor": getattr(record, "vendor", "") or "",
                    "file_name": getattr(record, "file_name", "") or "",
                    "invoice_number": getattr(record, "invoice_number", None),
                    "invoice_date": invoice_date,
                    "invoice_total": _safe_float(getattr(record, "invoice_total", None)),
                    "invoice_vat": _safe_float(getattr(record, "invoice_vat", None)),
                    "purpose": getattr(record, "purpose", None),
                }
                session.add(
                    InvoiceRecord(
                        tenant_id=job.tenant_id,
                        parse_job_id=job.id,
                        vendor=payload["vendor"],
                        file_name=payload["file_name"],
                        invoice_number=payload["invoice_number"],
                        invoice_date=invoice_date,
                        invoice_total=payload["invoice_total"],
                        invoice_vat=payload["invoice_vat"],
                        purpose=payload["purpose"],
                        raw_json=json.dumps(
                            {
                                **payload,
                                "invoice_date": invoice_date.isoformat() if invoice_date else None,
                            }
                        ),
                    )
                )

            for file_row in files:
                file_row.status = FileStatus.PARSED.value

            job.records_count = len(records)
            job.failed_count = 0
            job.error_message = None
            job.status = ParseJobStatus.SUCCEEDED.value
            job.finished_at = _utcnow()
            session.commit()
            return ParseJobStatus.SUCCEEDED
    except Exception as exc:
        with session_factory() as session:
            session.info["disable_tenant_guard"] = True
            job = session.execute(select(ParseJob).where(ParseJob.id == parse_job_id)).scalar_one()
            job.status = ParseJobStatus.FAILED.value
            job.failed_count = 1
            job.error_message = str(exc)
            job.finished_at = _utcnow()
            session.commit()
        return ParseJobStatus.FAILED


def run_report_job(
    session_factory: sessionmaker[Session],
    report_id: str,
    storage_backend: StorageBackend | None = None,
) -> ReportStatus:
    storage = storage_backend or build_storage(os.environ.get("SAAS_STORAGE_URL"))
    with session_factory() as session:
        session.info["disable_tenant_guard"] = True
        report = session.execute(select(Report).where(Report.id == report_id)).scalar_one_or_none()
        if report is None:
            raise ValueError(f"report not found: {report_id}")
        report.status = ReportStatus.RUNNING.value
        report.started_at = _utcnow()
        session.commit()

    try:
        with session_factory() as session:
            session.info["disable_tenant_guard"] = True
            report = session.execute(select(Report).where(Report.id == report_id)).scalar_one()
            format_names = list(json.loads(report.requested_formats_json))
            if not format_names:
                format_names = ["json", "csv", "summary_csv"]

            parse_job_ids = list(
                session.execute(
                    select(ReportParseJob.parse_job_id).where(ReportParseJob.report_id == report.id)
                )
                .scalars()
                .all()
            )

            invoices_query = select(InvoiceRecord).where(
                InvoiceRecord.tenant_id == report.tenant_id
            )
            if parse_job_ids:
                invoices_query = invoices_query.where(InvoiceRecord.parse_job_id.in_(parse_job_ids))
            invoices = list(session.execute(invoices_query).scalars().all())

            session.query(ReportArtifact).filter(ReportArtifact.report_id == report.id).delete()
            artifacts: list[tuple[str, str, int]] = []
            for format_name in format_names:
                if format_name == "json":
                    key = f"artifacts/{report.tenant_id}/{report.id}/report.json"
                    stored = storage.save_bytes(key, _json_report_bytes(invoices))
                elif format_name == "csv":
                    key = f"artifacts/{report.tenant_id}/{report.id}/report.csv"
                    stored = storage.save_bytes(key, _csv_report_bytes(invoices))
                elif format_name == "summary_csv":
                    key = f"artifacts/{report.tenant_id}/{report.id}/report.summary.csv"
                    stored = storage.save_bytes(key, _summary_csv_report_bytes(invoices))
                elif format_name == "pdf":
                    key = f"artifacts/{report.tenant_id}/{report.id}/report.pdf"
                    stored = storage.save_bytes(key, _pdf_report_bytes())
                else:
                    raise ValueError(f"unsupported report format: {format_name}")
                artifacts.append((format_name, stored.key, stored.size))

            for format_name, artifact_path, size in artifacts:
                session.add(
                    ReportArtifact(
                        tenant_id=report.tenant_id,
                        report_id=report.id,
                        format=format_name,
                        storage_path=artifact_path,
                        bytes=size,
                    )
                )

            report.error_message = None
            report.status = ReportStatus.SUCCEEDED.value
            report.finished_at = _utcnow()
            session.commit()
            return ReportStatus.SUCCEEDED
    except Exception as exc:
        with session_factory() as session:
            session.info["disable_tenant_guard"] = True
            report = session.execute(select(Report).where(Report.id == report_id)).scalar_one()
            report.status = ReportStatus.FAILED.value
            report.error_message = str(exc)
            report.finished_at = _utcnow()
            session.commit()
        return ReportStatus.FAILED


def run_report_retention_cleanup(
    session_factory: sessionmaker[Session],
    retention_days: int = 30,
    storage_backend: StorageBackend | None = None,
) -> int:
    storage = storage_backend or build_storage(os.environ.get("SAAS_STORAGE_URL"))
    if retention_days < 1:
        raise ValueError("retention_days must be >= 1")

    cutoff = _utcnow() - timedelta(days=retention_days)
    deleted_reports = 0

    with session_factory() as session:
        session.info["disable_tenant_guard"] = True
        stale_reports = list(
            session.execute(
                select(Report).where(
                    Report.finished_at.is_not(None),
                    Report.finished_at < cutoff,
                )
            )
            .scalars()
            .all()
        )

        for report in stale_reports:
            artifacts = list(
                session.execute(select(ReportArtifact).where(ReportArtifact.report_id == report.id))
                .scalars()
                .all()
            )
            for artifact in artifacts:
                storage.delete(artifact.storage_path)

            session.query(ReportArtifact).filter(ReportArtifact.report_id == report.id).delete()
            session.query(ReportParseJob).filter(ReportParseJob.report_id == report.id).delete()
            session.query(IdempotencyRecord).filter(
                IdempotencyRecord.resource_type == "report",
                IdempotencyRecord.resource_id == report.id,
            ).delete()
            session.delete(report)
            deleted_reports += 1

        session.commit()

    return deleted_reports
