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
    ProviderConfig,
    Report,
)
from invplatform.saas.queue import InMemoryJobQueue
from invplatform.saas.service import PARSE_JOB_TASK, ProviderConfigError, SaaSService


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


def test_provider_config_crud_and_tenant_isolation(tmp_path: Path) -> None:
    service, _queue = _build_service(tmp_path)
    tenant_a, _ = service.bootstrap_tenant("Tenant A")
    tenant_b, _ = service.bootstrap_tenant("Tenant B")

    created = service.create_provider_config(
        tenant_a.id,
        provider_type="GMAIL",
        display_name=" Ops Gmail ",
        config={"sync_window_days": 30},
        actor="ops-a",
    )
    assert created.provider_type == "gmail"
    assert created.display_name == "Ops Gmail"

    items_a, total_a = service.list_provider_configs(tenant_a.id)
    assert total_a == 1
    assert items_a[0].id == created.id
    assert items_a[0].provider_type == "gmail"

    items_b, total_b = service.list_provider_configs(tenant_b.id)
    assert total_b == 0
    assert items_b == []

    with pytest.raises(ValueError, match="already exists"):
        service.create_provider_config(tenant_a.id, provider_type="gmail")

    second_tenant_item = service.create_provider_config(
        tenant_b.id, provider_type="gmail"
    )
    assert second_tenant_item.id != created.id

    updated = service.update_provider_config(
        tenant_a.id,
        created.id,
        updates={
            "connection_status": "connected",
            "token_expires_at": datetime.now(timezone.utc),
            "last_error_code": None,
            "last_error_message": None,
        },
        actor="ops-a",
    )
    assert updated.connection_status == "connected"
    assert updated.token_expires_at is not None

    with pytest.raises(ValueError, match="provider config not found"):
        service.update_provider_config(
            tenant_b.id, created.id, updates={"connection_status": "error"}
        )

    service.delete_provider_config(tenant_a.id, created.id, actor="ops-a")
    items_after_delete, total_after_delete = service.list_provider_configs(tenant_a.id)
    assert total_after_delete == 0
    assert items_after_delete == []

    with service.session_factory() as session:
        session.info["tenant_id"] = tenant_a.id
        events = list(
            session.execute(
                select(AuditEvent).where(
                    AuditEvent.tenant_id == tenant_a.id,
                    AuditEvent.event_type.in_(
                        {"provider.create", "provider.update", "provider.delete"}
                    ),
                )
            )
            .scalars()
            .all()
        )
        assert [event.event_type for event in events] == [
            "provider.create",
            "provider.update",
            "provider.delete",
        ]
        rows = list(
            session.execute(
                select(ProviderConfig).where(ProviderConfig.tenant_id == tenant_a.id)
            )
            .scalars()
            .all()
        )
        assert rows == []


@pytest.mark.parametrize("invalid_provider_type", [None, "", "  ", "dropbox", 123])
def test_create_provider_config_invalid_provider_type(
    tmp_path: Path, invalid_provider_type: object
) -> None:
    service, _queue = _build_service(tmp_path)
    tenant, _ = service.bootstrap_tenant("Tenant")

    with pytest.raises(ValueError, match="provider_type"):
        service.create_provider_config(
            tenant.id,
            provider_type=invalid_provider_type,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("invalid_status", [None, "", "  ", "unknown", 123])
def test_create_provider_config_invalid_connection_status(
    tmp_path: Path, invalid_status: object
) -> None:
    service, _queue = _build_service(tmp_path)
    tenant, _ = service.bootstrap_tenant("Tenant")

    with pytest.raises(ValueError, match="connection_status"):
        service.create_provider_config(
            tenant.id,
            provider_type="gmail",
            connection_status=invalid_status,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("invalid_config", [[], "not-a-dict", 123])
def test_create_provider_config_non_dict_config(
    tmp_path: Path, invalid_config: object
) -> None:
    service, _queue = _build_service(tmp_path)
    tenant, _ = service.bootstrap_tenant("Tenant")

    with pytest.raises(ValueError, match="config must be an object"):
        service.create_provider_config(
            tenant.id,
            provider_type="gmail",
            config=invalid_config,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("limit, offset", [(0, 0), (-1, 0), (1, -1)])
def test_list_provider_configs_invalid_pagination(
    tmp_path: Path, limit: int, offset: int
) -> None:
    service, _queue = _build_service(tmp_path)
    tenant, _ = service.bootstrap_tenant("Tenant")

    with pytest.raises(ValueError):
        service.list_provider_configs(tenant.id, limit=limit, offset=offset)


def test_update_provider_config_empty_updates(tmp_path: Path) -> None:
    service, _queue = _build_service(tmp_path)
    tenant, _ = service.bootstrap_tenant("Tenant")
    row = service.create_provider_config(tenant.id, provider_type="gmail")

    with pytest.raises(ValueError, match="at least one field must be provided"):
        service.update_provider_config(tenant.id, row.id, updates={})


def test_update_provider_config_unknown_field(tmp_path: Path) -> None:
    service, _queue = _build_service(tmp_path)
    tenant, _ = service.bootstrap_tenant("Tenant")
    row = service.create_provider_config(tenant.id, provider_type="gmail")

    with pytest.raises(ValueError, match="unknown provider fields"):
        service.update_provider_config(
            tenant.id, row.id, updates={"not_real_field": True}
        )


def test_update_provider_config_duplicate_provider_type_for_tenant(
    tmp_path: Path,
) -> None:
    service, _queue = _build_service(tmp_path)
    tenant, _ = service.bootstrap_tenant("Tenant")
    first = service.create_provider_config(tenant.id, provider_type="gmail")
    second = service.create_provider_config(tenant.id, provider_type="outlook")

    with pytest.raises(ValueError, match="already exists"):
        service.update_provider_config(
            tenant.id,
            second.id,
            updates={"provider_type": first.provider_type},
        )


def test_update_provider_config_type_checks_and_normalization(tmp_path: Path) -> None:
    service, _queue = _build_service(tmp_path)
    tenant, _ = service.bootstrap_tenant("Tenant")
    row = service.create_provider_config(tenant.id, provider_type="gmail")

    bad_updates: tuple[dict[str, object], ...] = (
        {"provider_type": 123},
        {"connection_status": 123},
        {"display_name": 123},
        {"config": []},
        {"token_expires_at": "not-a-datetime"},
        {"last_successful_sync_at": "not-a-datetime"},
        {"last_error_code": 123},
        {"last_error_message": 123},
    )
    for updates in bad_updates:
        with pytest.raises(ValueError):
            service.update_provider_config(tenant.id, row.id, updates=updates)

    updated = service.update_provider_config(
        tenant.id,
        row.id,
        updates={
            "display_name": "  New Name  ",
            "token_expires_at": datetime(2030, 1, 1, 0, 0, 0),
            "last_successful_sync_at": datetime(2030, 1, 2, 0, 0, 0),
            "last_error_code": "   ",
            "last_error_message": "   ",
        },
    )
    assert updated.display_name == "New Name"
    assert updated.last_error_code is None
    assert updated.last_error_message is None
    assert updated.token_expires_at is not None
    assert updated.token_expires_at.tzinfo is not None
    assert updated.token_expires_at.tzinfo.utcoffset(
        updated.token_expires_at
    ) == timezone.utc.utcoffset(updated.token_expires_at)
    assert updated.last_successful_sync_at is not None
    assert updated.last_successful_sync_at.tzinfo is not None


def test_provider_oauth_lifecycle_and_errors(tmp_path: Path) -> None:
    service, _queue = _build_service(tmp_path)
    tenant, _ = service.bootstrap_tenant("Tenant")
    provider = service.create_provider_config(tenant.id, provider_type="gmail")

    with pytest.raises(ProviderConfigError, match="redirect_uri"):
        service.start_provider_oauth(
            tenant.id,
            provider.id,
            redirect_uri="invalid-uri",
        )

    start = service.start_provider_oauth(
        tenant.id,
        provider.id,
        redirect_uri="https://app.example.test/oauth/callback",
        actor="ops",
        request_id="req-1",
    )
    assert start.provider.id == provider.id
    assert start.state
    assert "accounts.google.com" in start.authorization_url

    with pytest.raises(ProviderConfigError, match="oauth state is missing or invalid"):
        service.complete_provider_oauth_callback(
            tenant.id,
            provider.id,
            state="wrong-state",
            code="auth-code",
            actor="ops",
            request_id="req-2",
        )

    connected = service.complete_provider_oauth_callback(
        tenant.id,
        provider.id,
        state=start.state,
        code="auth-code",
        actor="ops",
        request_id="req-3",
    )
    assert connected.connection_status == "connected"
    assert connected.oauth_access_token_enc
    assert connected.oauth_refresh_token_enc
    assert connected.token_expires_at is not None

    refreshed = service.refresh_provider_oauth(
        tenant.id,
        provider.id,
        actor="ops",
        request_id="req-4",
    )
    assert refreshed.connection_status == "connected"
    assert refreshed.oauth_access_token_enc
    assert refreshed.oauth_refresh_token_enc
    assert refreshed.token_expires_at is not None

    revoked = service.revoke_provider_oauth(
        tenant.id,
        provider.id,
        actor="ops",
        request_id="req-5",
    )
    assert revoked.connection_status == "disconnected"
    assert revoked.oauth_access_token_enc is None
    assert revoked.oauth_refresh_token_enc is None
    assert revoked.token_expires_at is None

    with pytest.raises(ProviderConfigError, match="provider is not connected"):
        service.refresh_provider_oauth(
            tenant.id,
            provider.id,
            actor="ops",
            request_id="req-6",
        )


def test_create_provider_config_maps_db_unique_conflict(tmp_path: Path) -> None:
    service, _queue = _build_service(tmp_path)
    tenant, _ = service.bootstrap_tenant("Tenant")
    service.create_provider_config(tenant.id, provider_type="gmail")

    def _skip_unique_check(*_args: object, **_kwargs: object) -> None:
        return None

    service._ensure_unique_provider_type = _skip_unique_check  # type: ignore[method-assign]
    with pytest.raises(ProviderConfigError, match="already exists") as exc:
        service.create_provider_config(tenant.id, provider_type="gmail")
    assert exc.value.code == "PROVIDER_CONFLICT"


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
