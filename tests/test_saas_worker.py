from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from invplatform.saas.db import build_engine, build_session_factory
from invplatform.saas.models import (
    Base,
    FileStatus,
    InvoiceFile,
    InvoiceRecord,
    ParseJob,
    Report,
    ReportArtifact,
)
from invplatform.saas.queue import InMemoryJobQueue
from invplatform.saas.service import SaaSService
from invplatform.saas.storage import LocalStorageBackend
from invplatform.saas.worker import (
    run_parse_job,
    run_report_job,
    run_report_retention_cleanup,
)


class _PassthroughStorage:
    def save_bytes(self, key: str, data: bytes):
        raise NotImplementedError

    def read_bytes(self, key: str) -> bytes:
        return Path(key).read_bytes()

    def resolve_local_path(self, key: str) -> Path:
        return Path(key)

    def delete(self, key: str) -> None:
        path = Path(key)
        if path.exists():
            path.unlink()


def _service(tmp_path: Path) -> SaaSService:
    engine = build_engine(f"sqlite:///{tmp_path / 'saas-worker.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = build_session_factory(engine)
    return SaaSService(session_factory=session_factory, queue=InMemoryJobQueue())


def test_run_parse_job_succeeds_and_persists_records(tmp_path: Path) -> None:
    service = _service(tmp_path)
    tenant, _raw_key = service.bootstrap_tenant("Acme Ltd")
    pdf_path = tmp_path / "input.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    file_row = service.register_file(
        tenant_id=tenant.id, filename="input.pdf", storage_path=str(pdf_path)
    )
    job = service.create_parse_job(
        tenant_id=tenant.id, file_ids=[file_row.id], debug=False
    )

    def fake_parse(_paths: list[Path], _debug: bool) -> list[object]:
        return [
            SimpleNamespace(
                vendor="Partner",
                file_name="input.pdf",
                invoice_number="12345",
                invoice_total=100.0,
                invoice_vat=17.0,
                purpose="test",
            )
        ]

    status = run_parse_job(
        service.session_factory,
        job.id,
        parse_paths_fn=fake_parse,
        storage_backend=_PassthroughStorage(),
    )
    assert status.value == "succeeded"

    with service.session_factory() as session:
        db_job = session.execute(
            select(ParseJob).where(ParseJob.id == job.id)
        ).scalar_one()
        assert db_job.status == "succeeded"
        assert db_job.records_count == 1

        records = list(
            session.execute(
                select(InvoiceRecord).where(InvoiceRecord.parse_job_id == job.id)
            )
            .scalars()
            .all()
        )
        assert len(records) == 1
        assert records[0].vendor == "Partner"

        db_file = session.execute(
            select(InvoiceFile).where(InvoiceFile.id == file_row.id)
        ).scalar_one()
        assert db_file.status == FileStatus.PARSED.value

    listed, total = service.list_invoices(tenant_id=tenant.id)
    assert total == 1
    assert len(listed) == 1
    assert listed[0].vendor == "Partner"


def test_run_parse_job_marks_failed_on_exception(tmp_path: Path) -> None:
    service = _service(tmp_path)
    tenant, _raw_key = service.bootstrap_tenant("Acme Ltd")
    pdf_path = tmp_path / "bad-input.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    file_row = service.register_file(
        tenant_id=tenant.id, filename="bad-input.pdf", storage_path=str(pdf_path)
    )
    job = service.create_parse_job(
        tenant_id=tenant.id, file_ids=[file_row.id], debug=False
    )

    def failing_parse(_paths: list[Path], _debug: bool) -> list[object]:
        raise RuntimeError("parse boom")

    status = run_parse_job(
        service.session_factory,
        job.id,
        parse_paths_fn=failing_parse,
        storage_backend=_PassthroughStorage(),
    )
    assert status.value == "failed"

    with service.session_factory() as session:
        db_job = session.execute(
            select(ParseJob).where(ParseJob.id == job.id)
        ).scalar_one()
        assert db_job.status == "failed"
        assert "parse boom" in (db_job.error_message or "")


def test_list_invoices_is_tenant_scoped(tmp_path: Path) -> None:
    service = _service(tmp_path)
    tenant_a, _key_a = service.bootstrap_tenant("Tenant A")
    tenant_b, _key_b = service.bootstrap_tenant("Tenant B")

    with service.session_factory() as session:
        session.add(
            InvoiceRecord(
                tenant_id=tenant_a.id,
                parse_job_id="job-a",
                vendor="Alpha Vendor",
                file_name="a.pdf",
                invoice_number="a1",
                invoice_total=10.0,
                invoice_vat=1.7,
                purpose="A",
                raw_json="{}",
            )
        )
        session.add(
            InvoiceRecord(
                tenant_id=tenant_b.id,
                parse_job_id="job-b",
                vendor="Beta Vendor",
                file_name="b.pdf",
                invoice_number="b1",
                invoice_total=20.0,
                invoice_vat=3.4,
                purpose="B",
                raw_json="{}",
            )
        )
        session.commit()

    items_a, total_a = service.list_invoices(tenant_id=tenant_a.id)
    items_b, total_b = service.list_invoices(tenant_id=tenant_b.id)
    assert total_a == 1 and len(items_a) == 1 and items_a[0].vendor == "Alpha Vendor"
    assert total_b == 1 and len(items_b) == 1 and items_b[0].vendor == "Beta Vendor"


def test_run_report_job_generates_artifacts(tmp_path: Path) -> None:
    service = _service(tmp_path)
    tenant, _key = service.bootstrap_tenant("Acme Ltd")
    with service.session_factory() as session:
        session.add(
            InvoiceRecord(
                tenant_id=tenant.id,
                parse_job_id="parse-1",
                vendor="Vendor A",
                file_name="a.pdf",
                invoice_number="a1",
                invoice_total=120.0,
                invoice_vat=20.4,
                purpose="A",
                raw_json="{}",
            )
        )
        session.add(
            InvoiceRecord(
                tenant_id=tenant.id,
                parse_job_id="parse-1",
                vendor="Vendor B",
                file_name="b.pdf",
                invoice_number="b1",
                invoice_total=80.0,
                invoice_vat=13.6,
                purpose="B",
                raw_json="{}",
            )
        )
        session.commit()

    report = service.create_report_job(
        tenant_id=tenant.id,
        formats=["json", "csv", "summary_csv", "pdf"],
        idempotency_key="report-run",
    )
    storage = LocalStorageBackend(tmp_path / "storage")
    status = run_report_job(
        session_factory=service.session_factory,
        report_id=report.id,
        storage_backend=storage,
    )
    assert status.value == "succeeded"

    with service.session_factory() as session:
        artifacts = list(
            session.execute(
                select(ReportArtifact).where(ReportArtifact.report_id == report.id)
            )
            .scalars()
            .all()
        )
        formats = sorted(item.format for item in artifacts)
        assert formats == ["csv", "json", "pdf", "summary_csv"]
        for artifact in artifacts:
            assert storage.resolve_local_path(artifact.storage_path).exists()


def test_run_report_retention_cleanup_deletes_old_reports_and_files(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    tenant, _key = service.bootstrap_tenant("Acme Ltd")
    report = service.create_report_job(
        tenant_id=tenant.id,
        formats=["json"],
        idempotency_key="cleanup-old-report",
    )
    storage = LocalStorageBackend(tmp_path / "storage-cleanup")
    status = run_report_job(
        session_factory=service.session_factory,
        report_id=report.id,
        storage_backend=storage,
    )
    assert status.value == "succeeded"

    with service.session_factory() as session:
        db_report = session.execute(
            select(Report).where(Report.id == report.id)
        ).scalar_one()
        db_report.finished_at = datetime.now(timezone.utc) - timedelta(days=45)
        session.commit()
        artifact = session.execute(
            select(ReportArtifact).where(ReportArtifact.report_id == report.id)
        ).scalar_one()
        artifact_path = storage.resolve_local_path(artifact.storage_path)
        assert artifact_path.exists()

    deleted = run_report_retention_cleanup(
        session_factory=service.session_factory,
        retention_days=30,
        storage_backend=storage,
    )
    assert deleted == 1
    assert not artifact_path.exists()

    with service.session_factory() as session:
        assert (
            session.execute(
                select(Report).where(Report.id == report.id)
            ).scalar_one_or_none()
            is None
        )
        assert (
            session.execute(
                select(ReportArtifact).where(ReportArtifact.report_id == report.id)
            ).scalar_one_or_none()
            is None
        )
