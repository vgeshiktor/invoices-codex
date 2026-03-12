from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

import pytest
from sqlalchemy import select

from invplatform.saas.db import build_engine, build_session_factory
from invplatform.saas.models import (
    AuditEvent,
    Base,
    IdempotencyRecord,
    ParseJob,
    Report,
)
from invplatform.saas.queue import InMemoryJobQueue
from invplatform.saas.service import PARSE_JOB_TASK, SaaSService


def _build_service(tmp_path: Path) -> tuple[SaaSService, InMemoryJobQueue]:
    engine = build_engine(f"sqlite:///{tmp_path / 'saas.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = build_session_factory(engine)
    queue = InMemoryJobQueue()
    return SaaSService(session_factory=session_factory, queue=queue), queue


def test_bootstrap_tenant_and_api_key_resolution(tmp_path: Path) -> None:
    service, _queue = _build_service(tmp_path)
    tenant, raw_key = service.bootstrap_tenant("Acme Ltd")

    assert tenant.id
    assert raw_key

    resolved = service.get_tenant_by_api_key(raw_key)
    assert resolved is not None
    assert resolved.id == tenant.id


def test_list_tenants_returns_newest_first(tmp_path: Path) -> None:
    service, _queue = _build_service(tmp_path)
    first, _ = service.bootstrap_tenant("First")
    second, _ = service.bootstrap_tenant("Second", actor="platform-admin")

    items, total = service.list_tenants(limit=10, offset=0)
    assert total >= 2
    assert items[0].id == second.id
    assert items[1].id == first.id


def test_bootstrap_tenant_slug_is_normalized_and_unique(tmp_path: Path) -> None:
    service, _queue = _build_service(tmp_path)
    first, _ = service.bootstrap_tenant("Acme !!! Ltd")
    second, _ = service.bootstrap_tenant("Acme !!! Ltd")

    assert first.slug == "acme-ltd"
    assert second.slug.startswith("acme-ltd-")
    assert first.slug != second.slug
    assert re.match(r"^[a-z0-9-]{2,64}$", first.slug)
    assert re.match(r"^[a-z0-9-]{2,64}$", second.slug)


def test_create_tenant_user_existing_user_requires_password_match(
    tmp_path: Path,
) -> None:
    service, _queue = _build_service(tmp_path)
    tenant_a, _ = service.bootstrap_tenant("Tenant A")
    tenant_b, _ = service.bootstrap_tenant("Tenant B")
    service.create_tenant_user(
        tenant_id=tenant_a.id,
        email="ops@example.test",
        password="secret-123",
        role="admin",
    )

    with pytest.raises(ValueError, match="password does not match existing user"):
        service.create_tenant_user(
            tenant_id=tenant_b.id,
            email="ops@example.test",
            password="wrong-pass",
            role="viewer",
        )


def test_provider_config_crud_is_tenant_scoped(tmp_path: Path) -> None:
    service, _queue = _build_service(tmp_path)
    tenant_a, _ = service.bootstrap_tenant("Tenant A")
    tenant_b, _ = service.bootstrap_tenant("Tenant B")

    created = service.create_provider_config(
        tenant_id=tenant_a.id,
        provider_type="gmail",
        display_name="Finance Gmail",
        actor="ops-user",
    )
    service.create_provider_config(
        tenant_id=tenant_b.id,
        provider_type="gmail",
        display_name="Other Gmail",
        actor="ops-user",
    )

    list_a = service.list_provider_configs(tenant_id=tenant_a.id)
    assert len(list_a) == 1
    assert list_a[0].id == created.id
    assert list_a[0].provider_type == "gmail"
    assert list_a[0].display_name == "Finance Gmail"

    updated = service.update_provider_config(
        tenant_id=tenant_a.id,
        provider_id=created.id,
        updates={
            "connection_status": "error",
            "last_error_code": "OAUTH_REFRESH_FAILED",
            "last_error_message": "refresh token revoked",
            "token_expires_at": datetime(2030, 1, 1, tzinfo=timezone.utc),
        },
        actor="ops-user",
    )
    assert updated.connection_status == "error"
    assert updated.last_error_code == "OAUTH_REFRESH_FAILED"
    assert updated.last_error_message == "refresh token revoked"
    assert updated.token_expires_at is not None

    service.delete_provider_config(
        tenant_id=tenant_a.id, provider_id=created.id, actor="ops-user"
    )
    assert service.list_provider_configs(tenant_id=tenant_a.id) == []
    assert len(service.list_provider_configs(tenant_id=tenant_b.id)) == 1

    with service.session_factory() as session:
        session.info["disable_tenant_guard"] = True
        events = list(
            session.execute(
                select(AuditEvent)
                .where(AuditEvent.tenant_id == tenant_a.id)
                .order_by(AuditEvent.created_at.asc())
            )
            .scalars()
            .all()
        )
        event_types = [item.event_type for item in events]
        assert "provider.create" in event_types
        assert "provider.update" in event_types
        assert "provider.delete" in event_types


def test_provider_config_rejects_invalid_updates_and_cross_tenant_access(
    tmp_path: Path,
) -> None:
    service, _queue = _build_service(tmp_path)
    tenant_a, _ = service.bootstrap_tenant("Tenant A")
    tenant_b, _ = service.bootstrap_tenant("Tenant B")
    created = service.create_provider_config(
        tenant_id=tenant_a.id,
        provider_type="outlook",
        display_name="Ops Outlook",
    )

    with pytest.raises(ValueError, match="provider_type must be one of"):
        service.create_provider_config(tenant_id=tenant_a.id, provider_type="imap")

    with pytest.raises(ValueError, match="already configured"):
        service.create_provider_config(tenant_id=tenant_a.id, provider_type="outlook")

    with pytest.raises(ValueError, match="at least one field must be provided"):
        service.update_provider_config(
            tenant_id=tenant_a.id,
            provider_id=created.id,
            updates={},
        )

    with pytest.raises(ValueError, match="unsupported fields"):
        service.update_provider_config(
            tenant_id=tenant_a.id,
            provider_id=created.id,
            updates={"unexpected_field": "value"},
        )

    with pytest.raises(ValueError, match="connection_status must be one of"):
        service.update_provider_config(
            tenant_id=tenant_a.id,
            provider_id=created.id,
            updates={"connection_status": "broken"},
        )

    with pytest.raises(LookupError, match="provider not found"):
        service.update_provider_config(
            tenant_id=tenant_b.id,
            provider_id=created.id,
            updates={"display_name": "hijack"},
        )

    with pytest.raises(LookupError, match="provider not found"):
        service.delete_provider_config(tenant_id=tenant_b.id, provider_id=created.id)


def test_register_file_and_create_parse_job_enqueues_task(tmp_path: Path) -> None:
    service, queue = _build_service(tmp_path)
    tenant, _raw_key = service.bootstrap_tenant("Acme Ltd")
    file_row = service.register_file(
        tenant_id=tenant.id,
        filename="inv-001.pdf",
        storage_path=str(tmp_path / "inv-001.pdf"),
    )
    job = service.create_parse_job(
        tenant_id=tenant.id,
        file_ids=[file_row.id],
        debug=True,
        idempotency_key="abc-123",
    )

    assert job.status == "queued"
    assert job.queue_job_id
    assert job.idempotency_key == "abc-123"
    assert len(queue.jobs) == 1
    task_name, payload, _queue_job_id = queue.jobs[0]
    assert task_name == PARSE_JOB_TASK
    assert payload["parse_job_id"] == job.id

    with service.session_factory() as session:
        db_job = session.execute(
            select(ParseJob).where(ParseJob.id == job.id)
        ).scalar_one()
        assert db_job.debug is True
        assert db_job.idempotency_key == "abc-123"
        assert db_job.queue_job_id


def test_create_parse_job_is_idempotent_per_tenant(tmp_path: Path) -> None:
    service, queue = _build_service(tmp_path)
    tenant, _raw_key = service.bootstrap_tenant("Acme Ltd")
    file_row = service.register_file(
        tenant_id=tenant.id,
        filename="inv-001.pdf",
        storage_path=str(tmp_path / "inv-001.pdf"),
    )

    first = service.create_parse_job(
        tenant_id=tenant.id,
        file_ids=[file_row.id],
        debug=False,
        idempotency_key="same-key",
    )
    second = service.create_parse_job(
        tenant_id=tenant.id,
        file_ids=[file_row.id],
        debug=True,
        idempotency_key="same-key",
    )

    assert first.id == second.id
    assert len(queue.jobs) == 1

    with service.session_factory() as session:
        keys = list(session.execute(select(IdempotencyRecord)).scalars().all())
        assert len(keys) == 1
        assert keys[0].scope == "parse_jobs.create"


def test_create_report_is_idempotent_per_tenant(tmp_path: Path) -> None:
    service, queue = _build_service(tmp_path)
    tenant, _raw_key = service.bootstrap_tenant("Acme Ltd")
    file_row = service.register_file(
        tenant_id=tenant.id,
        filename="inv-001.pdf",
        storage_path=str(tmp_path / "inv-001.pdf"),
    )
    parse_job = service.create_parse_job(
        tenant_id=tenant.id, file_ids=[file_row.id], debug=False
    )

    first = service.create_report_job(
        tenant_id=tenant.id,
        parse_job_ids=[parse_job.id],
        formats=["json"],
        idempotency_key="report-key",
    )
    second = service.create_report_job(
        tenant_id=tenant.id,
        parse_job_ids=[parse_job.id],
        formats=["json", "csv"],
        idempotency_key="report-key",
    )

    assert first.id == second.id
    assert len(queue.jobs) == 2  # one parse task + one report task

    with service.session_factory() as session:
        db_report = session.execute(
            select(Report).where(Report.id == first.id)
        ).scalar_one()
        assert db_report.queue_job_id
        keys = list(
            session.execute(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.scope == "reports.create"
                )
            )
            .scalars()
            .all()
        )
        assert len(keys) == 1

    reports, total = service.list_reports(tenant_id=tenant.id)
    assert total == 1
    assert len(reports) == 1
    assert reports[0].id == first.id


def test_enqueue_report_cleanup_pushes_queue_job(tmp_path: Path) -> None:
    service, queue = _build_service(tmp_path)
    job_id = service.enqueue_report_cleanup(retention_days=15)
    assert job_id
    assert len(queue.jobs) == 1
    task_name, payload, queued_job_id = queue.jobs[0]
    assert task_name == "invplatform.saas.tasks.run_report_retention_cleanup_task"
    assert payload["retention_days"] == "15"
    assert queued_job_id == job_id
