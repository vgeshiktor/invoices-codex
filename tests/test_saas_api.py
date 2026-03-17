from __future__ import annotations
# ruff: noqa: E402

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import select

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
try:  # package import path differs across python-multipart versions
    import python_multipart  # type: ignore[import-not-found]  # noqa: F401
except ModuleNotFoundError:
    pytest.importorskip("multipart")

from fastapi.testclient import TestClient  # type: ignore[import-not-found]

from invplatform.saas import auth as saas_auth
from invplatform.saas.api import ApiAppConfig, create_app
from invplatform.saas.models import AuditEvent, AuthSession, InvoiceRecord, Tenant


def _client(
    tmp_path: Path,
    *,
    control_plane_api_key: str | None = None,
) -> tuple[TestClient, str, str]:
    app = create_app(
        ApiAppConfig(
            database_url=f"sqlite:///{tmp_path / 'saas-api.db'}",
            storage_url=f"local://{tmp_path / 'storage'}",
            control_plane_api_key=control_plane_api_key,
            auth_access_token_secret="test-auth-secret",
            auth_cookie_secure=False,
        )
    )
    tenant, api_key = app.state.service.bootstrap_tenant("API Tenant")
    client = TestClient(app)
    return client, api_key, tenant.id


def test_file_upload_and_parse_job_idempotency(tmp_path: Path) -> None:
    client, api_key, _tenant_id = _client(tmp_path)
    headers = {"X-API-Key": api_key}

    upload = client.post(
        "/v1/files",
        headers=headers,
        files={"file": ("inv.pdf", b"%PDF-1.4\n", "application/pdf")},
    )
    assert upload.status_code == 201
    assert upload.headers.get("x-request-id")
    file_id = upload.json()["id"]
    assert file_id

    first = client.post(
        "/v1/parse-jobs",
        headers={**headers, "Idempotency-Key": "same-key"},
        json={"file_ids": [file_id], "debug": False},
    )
    second = client.post(
        "/v1/parse-jobs",
        headers={**headers, "Idempotency-Key": "same-key"},
        json={"file_ids": [file_id], "debug": True},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.headers.get("x-request-id")
    assert second.headers.get("x-request-id")
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["queue_job_id"] == second.json()["queue_job_id"]


def test_list_invoices_tenant_scoped_and_filtered(tmp_path: Path) -> None:
    client, api_key, tenant_id = _client(tmp_path)
    app = cast(Any, client.app)
    other_tenant, other_key = app.state.service.bootstrap_tenant("Other Tenant")

    with app.state.service.session_factory() as session:
        session.add(
            InvoiceRecord(
                tenant_id=tenant_id,
                parse_job_id="job-1",
                vendor="Partner Israel",
                file_name="a.pdf",
                invoice_number="1",
                invoice_total=100.0,
                invoice_vat=17.0,
                purpose="main",
                raw_json="{}",
            )
        )
        session.add(
            InvoiceRecord(
                tenant_id=other_tenant.id,
                parse_job_id="job-2",
                vendor="Other Vendor",
                file_name="b.pdf",
                invoice_number="2",
                invoice_total=200.0,
                invoice_vat=34.0,
                purpose="other",
                raw_json="{}",
            )
        )
        session.commit()

    mine = client.get("/v1/invoices?vendor=partner", headers={"X-API-Key": api_key})
    assert mine.status_code == 200
    mine_body = mine.json()
    assert mine_body["total"] == 1
    first_invoice_id = mine_body["items"][0]["id"]
    assert mine_body["items"][0]["vendor"] == "Partner Israel"

    invoice_detail = client.get(
        f"/v1/invoices/{first_invoice_id}", headers={"X-API-Key": api_key}
    )
    assert invoice_detail.status_code == 200
    assert invoice_detail.json()["vendor"] == "Partner Israel"

    other = client.get("/v1/invoices", headers={"X-API-Key": other_key})
    assert other.status_code == 200
    other_body = other.json()
    assert other_body["total"] == 1
    assert other_body["items"][0]["vendor"] == "Other Vendor"


def test_report_endpoints_scaffolding_and_download(tmp_path: Path) -> None:
    client, api_key, tenant_id = _client(tmp_path)
    app = cast(Any, client.app)

    with app.state.service.session_factory() as session:
        session.add(
            InvoiceRecord(
                tenant_id=tenant_id,
                parse_job_id="parse-r1",
                vendor="Vendor Report",
                file_name="r.pdf",
                invoice_number="r1",
                invoice_total=42.0,
                invoice_vat=7.14,
                purpose="report",
                raw_json="{}",
            )
        )
        session.commit()

    create = client.post(
        "/v1/reports",
        headers={"X-API-Key": api_key, "Idempotency-Key": "report-1"},
        json={"formats": ["json", "csv"]},
    )
    assert create.status_code == 202
    report_id = create.json()["id"]

    second = client.post(
        "/v1/reports",
        headers={"X-API-Key": api_key, "Idempotency-Key": "report-1"},
        json={"formats": ["json"]},
    )
    assert second.status_code == 202
    assert second.json()["id"] == report_id

    # Run queued report task directly for integration test determinism.
    from invplatform.saas.worker import run_report_job

    status = run_report_job(
        session_factory=app.state.service.session_factory,
        report_id=report_id,
        storage_backend=app.state.storage,
    )
    assert status.value == "succeeded"

    details = client.get(f"/v1/reports/{report_id}", headers={"X-API-Key": api_key})
    assert details.status_code == 200
    body = details.json()
    assert body["status"] == "succeeded"
    assert len(body["artifacts"]) == 2

    listing = client.get(
        "/v1/reports?status=succeeded&limit=10&offset=0", headers={"X-API-Key": api_key}
    )
    assert listing.status_code == 200
    listing_body = listing.json()
    assert listing_body["total"] == 1
    assert listing_body["items"][0]["id"] == report_id

    download = client.get(
        f"/v1/reports/{report_id}/download?format=json",
        headers={"X-API-Key": api_key},
    )
    assert download.status_code == 200

    retry = client.post(
        f"/v1/reports/{report_id}/retry", headers={"X-API-Key": api_key}
    )
    assert retry.status_code == 202
    retry_body = retry.json()
    assert retry_body["status"] == "queued"
    assert retry_body["queue_job_id"]


def test_api_middleware_emits_audit_event_and_request_id(tmp_path: Path) -> None:
    client, api_key, tenant_id = _client(tmp_path)
    app = cast(Any, client.app)
    request_id = "req-test-123"
    response = client.get(
        "/v1/reports?limit=5&offset=0",
        headers={
            "X-API-Key": api_key,
            "X-Actor": "integration-test",
            "X-Request-ID": request_id,
        },
    )
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == request_id

    with app.state.service.session_factory() as session:
        session.info["tenant_id"] = tenant_id
        events = list(
            session.query(AuditEvent)
            .filter(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.event_type == "api.get.v1.reports",
            )
            .all()
        )
        assert events
        payload = json.loads(events[-1].payload_json)
        assert payload["request_id"] == request_id
        assert payload["status_code"] == 200
        assert events[-1].actor == "integration-test"


def test_swagger_dashboard_and_metrics_endpoints(tmp_path: Path) -> None:
    client, api_key, _tenant_id = _client(tmp_path)
    swagger = client.get("/swagger")
    assert swagger.status_code == 200
    assert "Swagger UI" in swagger.text

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Invoices SaaS Dashboard" in dashboard.text

    # Generate at least one tracked API request for metrics output.
    client.get("/v1/reports?limit=1&offset=0", headers={"X-API-Key": api_key})
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "invplatform_http_requests_total" in metrics.text


def test_openapi_exposes_api_key_security_scheme(tmp_path: Path) -> None:
    client, _api_key, _tenant_id = _client(
        tmp_path, control_plane_api_key="cp-docs-key"
    )
    response = client.get("/openapi.json")
    assert response.status_code == 200
    body = response.json()
    assert body["components"]["securitySchemes"]["ApiKeyAuth"]["type"] == "apiKey"
    assert body["components"]["securitySchemes"]["ApiKeyAuth"]["name"] == "X-API-Key"
    assert (
        body["components"]["securitySchemes"]["ControlPlaneKeyAuth"]["type"] == "apiKey"
    )
    assert (
        body["components"]["securitySchemes"]["ControlPlaneKeyAuth"]["name"]
        == "X-Control-Plane-Key"
    )
    assert "/v1/invoices" in body["paths"]
    assert "/v1/providers" in body["paths"]
    assert "/v1/providers/{provider_id}/oauth/start" in body["paths"]
    assert "/v1/providers/{provider_id}/oauth/callback" in body["paths"]
    assert "/v1/providers/{provider_id}/oauth/refresh" in body["paths"]
    assert "/v1/providers/{provider_id}/oauth/revoke" in body["paths"]
    assert "/v1/providers/{provider_id}/test-connection" in body["paths"]
    assert "/v1/collection-jobs" in body["paths"]
    assert "/v1/control-plane/tenants" in body["paths"]
    assert body["paths"]["/v1/files"]["post"]["security"] == [{"ApiKeyAuth": []}]
    assert body["paths"]["/v1/providers"]["get"]["security"] == [{"ApiKeyAuth": []}]
    assert body["paths"]["/v1/providers/{provider_id}/oauth/start"]["post"][
        "security"
    ] == [{"ApiKeyAuth": []}]
    assert body["paths"]["/v1/providers/{provider_id}/oauth/callback"]["get"][
        "security"
    ] == [{"ApiKeyAuth": []}]
    assert body["paths"]["/v1/providers/{provider_id}/oauth/refresh"]["post"][
        "security"
    ] == [{"ApiKeyAuth": []}]
    assert body["paths"]["/v1/providers/{provider_id}/oauth/revoke"]["post"][
        "security"
    ] == [{"ApiKeyAuth": []}]
    assert body["paths"]["/v1/providers/{provider_id}/test-connection"]["post"][
        "security"
    ] == [{"ApiKeyAuth": []}]
    assert body["paths"]["/v1/collection-jobs"]["get"]["security"] == [
        {"ApiKeyAuth": []}
    ]
    assert body["paths"]["/v1/control-plane/tenants"]["get"]["security"] == [
        {"ControlPlaneKeyAuth": []}
    ]


def test_admin_api_key_management_and_dashboard_summary(tmp_path: Path) -> None:
    client, api_key, _tenant_id = _client(tmp_path)
    headers = {"X-API-Key": api_key, "X-Actor": "owner-user"}

    listing = client.get("/v1/admin/api-keys", headers=headers)
    assert listing.status_code == 200
    before_total = listing.json()["total"]
    assert before_total >= 1

    created = client.post("/v1/admin/api-keys", headers=headers)
    assert created.status_code == 201
    created_body = created.json()
    created_id = created_body["api_key"]["id"]
    created_plain = created_body["plain_text"]
    assert created_plain

    rotate = client.post(f"/v1/admin/api-keys/{created_id}/rotate", headers=headers)
    assert rotate.status_code == 200
    rotated_plain = rotate.json()["plain_text"]
    assert rotated_plain and rotated_plain != created_plain

    revoke = client.post(f"/v1/admin/api-keys/{created_id}/revoke", headers=headers)
    assert revoke.status_code == 200
    assert revoke.json()["api_key"]["revoked"] is True

    summary = client.get("/v1/dashboard/summary", headers={"X-API-Key": api_key})
    assert summary.status_code == 200
    body = summary.json()
    assert "totals" in body
    assert "parse_jobs_by_status" in body
    assert "reports_by_status" in body


def test_provider_crud_and_tenant_isolation(tmp_path: Path) -> None:
    client, api_key, tenant_id = _client(tmp_path)
    app = cast(Any, client.app)
    _other_tenant, other_key = app.state.service.bootstrap_tenant("Other Tenant")

    def _assert_provider_response_omits_encrypted_tokens(
        provider_body: dict[str, object],
    ) -> None:
        assert "oauth_access_token_enc" not in provider_body
        assert "oauth_refresh_token_enc" not in provider_body

    created = client.post(
        "/v1/providers",
        headers={"X-API-Key": api_key, "X-Actor": "owner"},
        json={
            "provider_type": "gmail",
            "display_name": "Ops Gmail",
            "connection_status": "disconnected",
            "config": {"sync_window_days": 30},
        },
    )
    assert created.status_code == 201
    provider = created.json()
    provider_id = provider["id"]
    assert provider["provider_type"] == "gmail"
    assert provider["tenant_id"] == tenant_id
    _assert_provider_response_omits_encrypted_tokens(provider)

    duplicate = client.post(
        "/v1/providers",
        headers={"X-API-Key": api_key},
        json={"provider_type": "gmail"},
    )
    assert duplicate.status_code == 409

    listed = client.get(
        "/v1/providers?limit=10&offset=0", headers={"X-API-Key": api_key}
    )
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["total"] == 1
    assert listed_body["items"][0]["id"] == provider_id
    _assert_provider_response_omits_encrypted_tokens(listed_body["items"][0])

    other_listed = client.get("/v1/providers", headers={"X-API-Key": other_key})
    assert other_listed.status_code == 200
    assert other_listed.json()["total"] == 0

    updated = client.patch(
        f"/v1/providers/{provider_id}",
        headers={"X-API-Key": api_key},
        json={
            "connection_status": "connected",
            "token_expires_at": "2030-01-01T00:00:00+00:00",
            "last_error_code": None,
            "last_error_message": None,
        },
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["connection_status"] == "connected"
    assert updated_body["token_expires_at"].startswith("2030-01-01T00:00:00")
    assert updated_body["last_error_code"] is None
    _assert_provider_response_omits_encrypted_tokens(updated_body)

    denied_update = client.patch(
        f"/v1/providers/{provider_id}",
        headers={"X-API-Key": other_key},
        json={"connection_status": "error"},
    )
    assert denied_update.status_code == 404

    denied_delete = client.delete(
        f"/v1/providers/{provider_id}", headers={"X-API-Key": other_key}
    )
    assert denied_delete.status_code == 404

    deleted = client.delete(
        f"/v1/providers/{provider_id}", headers={"X-API-Key": api_key}
    )
    assert deleted.status_code == 204

    after_delete = client.get("/v1/providers", headers={"X-API-Key": api_key})
    assert after_delete.status_code == 200
    assert after_delete.json()["total"] == 0


def test_provider_create_validation_error_mapping(tmp_path: Path) -> None:
    client, api_key, _tenant_id = _client(tmp_path)
    headers = {"X-API-Key": api_key}

    invalid_provider = client.post(
        "/v1/providers",
        headers=headers,
        json={"provider_type": "dropbox"},
    )
    assert invalid_provider.status_code == 400
    assert "provider_type" in invalid_provider.json()["detail"]

    invalid_status = client.post(
        "/v1/providers",
        headers=headers,
        json={"provider_type": "gmail", "connection_status": "invalid-status"},
    )
    assert invalid_status.status_code == 400
    assert "connection_status" in invalid_status.json()["detail"]

    invalid_config = client.post(
        "/v1/providers",
        headers=headers,
        json={"provider_type": "gmail", "config": "not-an-object"},
    )
    assert invalid_config.status_code == 400
    assert invalid_config.json()["detail"] == "config must be an object"


def test_provider_update_validation_conflict_and_not_found_mapping(
    tmp_path: Path,
) -> None:
    client, api_key, _tenant_id = _client(tmp_path)
    headers = {"X-API-Key": api_key}

    gmail = client.post(
        "/v1/providers", headers=headers, json={"provider_type": "gmail"}
    )
    assert gmail.status_code == 201
    gmail_id = gmail.json()["id"]

    outlook = client.post(
        "/v1/providers",
        headers=headers,
        json={"provider_type": "outlook"},
    )
    assert outlook.status_code == 201
    outlook_id = outlook.json()["id"]

    empty_patch = client.patch(f"/v1/providers/{gmail_id}", headers=headers, json={})
    assert empty_patch.status_code == 400
    assert empty_patch.json()["detail"] == "at least one field must be provided"

    invalid_patch = client.patch(
        f"/v1/providers/{gmail_id}",
        headers=headers,
        json={"connection_status": "not-real"},
    )
    assert invalid_patch.status_code == 400
    assert "connection_status" in invalid_patch.json()["detail"]

    invalid_config_patch = client.patch(
        f"/v1/providers/{gmail_id}",
        headers=headers,
        json={"config": []},
    )
    assert invalid_config_patch.status_code == 400
    assert invalid_config_patch.json()["detail"] == "config must be an object or null"

    duplicate_provider_type = client.patch(
        f"/v1/providers/{outlook_id}",
        headers=headers,
        json={"provider_type": "gmail"},
    )
    assert duplicate_provider_type.status_code == 409
    assert "already exists" in duplicate_provider_type.json()["detail"]

    missing_provider = client.patch(
        "/v1/providers/missing-provider-id",
        headers=headers,
        json={"connection_status": "error"},
    )
    assert missing_provider.status_code == 404
    assert missing_provider.json()["detail"] == "provider config not found"


def test_provider_oauth_lifecycle_endpoints(tmp_path: Path) -> None:
    client, api_key, _tenant_id = _client(tmp_path)
    headers = {"X-API-Key": api_key, "X-Actor": "owner"}

    created = client.post(
        "/v1/providers", headers=headers, json={"provider_type": "gmail"}
    )
    assert created.status_code == 201
    provider_id = created.json()["id"]

    invalid_start = client.post(
        f"/v1/providers/{provider_id}/oauth/start",
        headers=headers,
        json={"redirect_uri": "not-a-url"},
    )
    assert invalid_start.status_code == 400
    assert "redirect_uri" in invalid_start.json()["detail"]

    start = client.post(
        f"/v1/providers/{provider_id}/oauth/start",
        headers=headers,
        json={"redirect_uri": "https://app.example.test/oauth/callback"},
    )
    assert start.status_code == 200
    start_body = start.json()
    assert start_body["provider"]["id"] == provider_id
    assert "oauth_access_token_enc" not in start_body["provider"]
    assert "oauth_refresh_token_enc" not in start_body["provider"]
    assert start_body["authorization_url"].startswith("https://accounts.google.com/")
    state = start_body["state"]
    assert state
    assert start_body["state_expires_at"]

    bad_callback = client.get(
        f"/v1/providers/{provider_id}/oauth/callback?state=wrong-state&code=code-1",
        headers=headers,
    )
    assert bad_callback.status_code == 400
    assert bad_callback.json()["detail"] == "oauth state is missing or invalid"

    empty_state_callback = client.get(
        f"/v1/providers/{provider_id}/oauth/callback?state=&code=code-1",
        headers=headers,
    )
    assert empty_state_callback.status_code == 400
    assert empty_state_callback.json()["detail"] == "state is required"

    empty_code_callback = client.get(
        f"/v1/providers/{provider_id}/oauth/callback?state={state}&code=",
        headers=headers,
    )
    assert empty_code_callback.status_code == 400
    assert empty_code_callback.json()["detail"] == "code is required"

    callback = client.get(
        f"/v1/providers/{provider_id}/oauth/callback?state={state}&code=code-1",
        headers=headers,
    )
    assert callback.status_code == 200
    callback_body = callback.json()
    assert callback_body["connection_status"] == "connected"
    assert callback_body["token_expires_at"] is not None
    assert "oauth_access_token_enc" not in callback_body
    assert "oauth_refresh_token_enc" not in callback_body

    refreshed = client.post(
        f"/v1/providers/{provider_id}/oauth/refresh", headers=headers
    )
    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    assert refreshed_body["connection_status"] == "connected"
    assert refreshed_body["token_expires_at"] is not None
    assert "oauth_access_token_enc" not in refreshed_body
    assert "oauth_refresh_token_enc" not in refreshed_body

    revoked = client.post(f"/v1/providers/{provider_id}/oauth/revoke", headers=headers)
    assert revoked.status_code == 200
    revoked_body = revoked.json()
    assert revoked_body["connection_status"] == "disconnected"
    assert revoked_body["token_expires_at"] is None
    assert "oauth_access_token_enc" not in revoked_body
    assert "oauth_refresh_token_enc" not in revoked_body

    refresh_after_revoke = client.post(
        f"/v1/providers/{provider_id}/oauth/refresh", headers=headers
    )
    assert refresh_after_revoke.status_code == 409
    assert refresh_after_revoke.json()["detail"] == "provider is not connected"

    revoke_missing = client.post(
        "/v1/providers/missing-provider-id/oauth/revoke", headers=headers
    )
    assert revoke_missing.status_code == 404
    assert revoke_missing.json()["detail"] == "provider config not found"


def test_provider_test_connection_endpoint(tmp_path: Path) -> None:
    client, api_key, _tenant_id = _client(tmp_path)
    app = cast(Any, client.app)
    _other_tenant, other_key = app.state.service.bootstrap_tenant("Other Tenant")
    headers = {"X-API-Key": api_key, "X-Actor": "owner"}

    created = client.post(
        "/v1/providers", headers=headers, json={"provider_type": "gmail"}
    )
    assert created.status_code == 201
    provider_id = created.json()["id"]

    disconnected_result = client.post(
        f"/v1/providers/{provider_id}/test-connection", headers=headers
    )
    assert disconnected_result.status_code == 200
    assert disconnected_result.headers.get("x-request-id")
    disconnected_body = disconnected_result.json()
    assert disconnected_body["status"] == "failure"
    assert disconnected_body["message"] == "provider is not connected"
    assert disconnected_body["tested_at"]
    assert disconnected_body["request_id"] == disconnected_result.headers.get("x-request-id")
    assert disconnected_body["provider"]["id"] == provider_id
    assert disconnected_body["provider"]["last_error_code"] == "PROVIDER_TEST_CONNECTION_FAILED"

    start = client.post(
        f"/v1/providers/{provider_id}/oauth/start",
        headers=headers,
        json={"redirect_uri": "https://app.example.test/oauth/callback"},
    )
    assert start.status_code == 200
    state = start.json()["state"]
    assert state

    callback = client.get(
        f"/v1/providers/{provider_id}/oauth/callback?state={state}&code=code-1",
        headers=headers,
    )
    assert callback.status_code == 200

    connected_result = client.post(
        f"/v1/providers/{provider_id}/test-connection", headers=headers
    )
    assert connected_result.status_code == 200
    connected_body = connected_result.json()
    assert connected_body["status"] == "success"
    assert connected_body["message"] == "provider connection verified"
    assert connected_body["tested_at"]
    assert connected_body["provider"]["id"] == provider_id
    assert connected_body["provider"]["connection_status"] == "connected"

    cross_tenant = client.post(
        f"/v1/providers/{provider_id}/test-connection",
        headers={"X-API-Key": other_key},
    )
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["detail"] == "provider config not found"


def test_collection_jobs_create_list_get_and_tenant_isolation(tmp_path: Path) -> None:
    client, api_key, _tenant_id = _client(tmp_path)
    app = cast(Any, client.app)
    _other_tenant, other_key = app.state.service.bootstrap_tenant("Other Tenant")
    headers = {"X-API-Key": api_key, "X-Actor": "owner"}

    created = client.post(
        "/v1/collection-jobs",
        headers={**headers, "Idempotency-Key": "collect-1"},
        json={"providers": ["gmail", "outlook"], "month_scope": "2026-04"},
    )
    assert created.status_code == 201
    body = created.json()
    collection_job_id = body["id"]
    assert body["status"] == "queued"
    assert body["month_scope"] == "2026-04"
    assert body["providers"] == ["gmail", "outlook"]
    assert body["queue_job_id"]
    assert body["files_discovered"] == 0
    assert body["files_downloaded"] == 0
    assert body["parse_job_ids"] == []

    idempotent = client.post(
        "/v1/collection-jobs",
        headers={**headers, "Idempotency-Key": "collect-1"},
        json={"providers": ["gmail"], "month_scope": "2026-05"},
    )
    assert idempotent.status_code == 201
    assert idempotent.json()["id"] == collection_job_id
    assert idempotent.json()["queue_job_id"] == body["queue_job_id"]

    listing = client.get(
        "/v1/collection-jobs?status=queued&limit=10&offset=0",
        headers={"X-API-Key": api_key},
    )
    assert listing.status_code == 200
    list_body = listing.json()
    assert list_body["total"] == 1
    assert list_body["items"][0]["id"] == collection_job_id

    details = client.get(
        f"/v1/collection-jobs/{collection_job_id}",
        headers={"X-API-Key": api_key},
    )
    assert details.status_code == 200
    assert details.json()["id"] == collection_job_id

    other_listing = client.get("/v1/collection-jobs", headers={"X-API-Key": other_key})
    assert other_listing.status_code == 200
    assert other_listing.json()["total"] == 0

    other_details = client.get(
        f"/v1/collection-jobs/{collection_job_id}",
        headers={"X-API-Key": other_key},
    )
    assert other_details.status_code == 404
    assert other_details.json()["detail"] == "collection job not found"


def test_collection_jobs_validation_and_not_found(tmp_path: Path) -> None:
    client, api_key, _tenant_id = _client(tmp_path)
    headers = {"X-API-Key": api_key}

    invalid_providers = client.post(
        "/v1/collection-jobs",
        headers=headers,
        json={"providers": [], "month_scope": "2026-04"},
    )
    assert invalid_providers.status_code == 400
    assert "providers" in invalid_providers.json()["detail"]

    invalid_provider_entry = client.post(
        "/v1/collection-jobs",
        headers=headers,
        json={"providers": ["gmail", "dropbox"], "month_scope": "2026-04"},
    )
    assert invalid_provider_entry.status_code == 400
    assert "providers must only contain" in invalid_provider_entry.json()["detail"]

    invalid_month_scope = client.post(
        "/v1/collection-jobs",
        headers=headers,
        json={"providers": ["gmail"], "month_scope": "2026-13"},
    )
    assert invalid_month_scope.status_code == 400
    assert invalid_month_scope.json()["detail"] == "month_scope must match YYYY-MM"

    invalid_status = client.get(
        "/v1/collection-jobs?status=not-real",
        headers=headers,
    )
    assert invalid_status.status_code == 400
    assert "status must be one of" in invalid_status.json()["detail"]

    missing = client.get("/v1/collection-jobs/not-found", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "collection job not found"


def test_control_plane_tenant_bootstrap_and_listing(tmp_path: Path) -> None:
    client, _api_key, _tenant_id = _client(
        tmp_path, control_plane_api_key="cp-demo-key"
    )
    headers = {"X-Control-Plane-Key": "cp-demo-key", "X-Actor": "platform-admin"}

    create = client.post(
        "/v1/control-plane/tenants", headers=headers, json={"name": "Demo Tenant"}
    )
    assert create.status_code == 201
    body = create.json()
    assert body["tenant"]["id"]
    assert body["tenant"]["name"] == "Demo Tenant"
    assert body["api_key"]["plain_text"]

    listing = client.get("/v1/control-plane/tenants?limit=10&offset=0", headers=headers)
    assert listing.status_code == 200
    listing_body = listing.json()
    assert listing_body["total"] >= 2
    names = [item["name"] for item in listing_body["items"]]
    assert "Demo Tenant" in names


def test_control_plane_key_enforcement(tmp_path: Path) -> None:
    enabled_client, _api_key, _tenant_id = _client(
        tmp_path, control_plane_api_key="cp-secret"
    )
    unauthorized = enabled_client.get(
        "/v1/control-plane/tenants",
        headers={"X-Control-Plane-Key": "wrong-secret"},
    )
    assert unauthorized.status_code == 401

    disabled_client, _api_key_disabled, _tenant_id_disabled = _client(tmp_path)
    disabled = disabled_client.get("/v1/control-plane/tenants")
    assert disabled.status_code == 503


def test_auth_login_me_refresh_logout_flow(tmp_path: Path) -> None:
    client, _api_key, tenant_id = _client(tmp_path)
    app = cast(Any, client.app)
    app.state.service.create_tenant_user(
        tenant_id=tenant_id,
        email="ops@example.test",
        password="secret-123",
        full_name="Ops User",
        role="admin",
    )
    with app.state.service.session_factory() as session:
        session.info["disable_tenant_guard"] = True
        tenant = session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        ).scalar_one()

    login = client.post(
        "/auth/login",
        json={
            "email": "ops@example.test",
            "password": "secret-123",
            "tenant_slug": tenant.slug,
        },
    )
    assert login.status_code == 200
    assert login.headers.get("x-request-id")
    login_body = login.json()
    access_token = login_body["access_token"]
    assert access_token
    assert login_body["user"]["email"] == "ops@example.test"
    assert login_body["tenant"]["slug"] == tenant.slug
    assert login.cookies.get("inv_refresh")

    me = client.get("/v1/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.status_code == 200
    assert me.json()["tenant"]["id"] == tenant_id
    assert me.json()["user"]["role"] == "admin"

    refreshed = client.post("/auth/refresh")
    assert refreshed.status_code == 200
    refreshed_token = refreshed.json()["access_token"]
    assert refreshed_token and refreshed_token != access_token

    logout = client.post("/auth/logout")
    assert logout.status_code == 204
    logout_again = client.post("/auth/logout")
    assert logout_again.status_code == 204

    denied = client.get(
        "/v1/me", headers={"Authorization": f"Bearer {refreshed_token}"}
    )
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "AUTH_ACCESS_INVALID"


def test_auth_login_invalid_credentials_returns_envelope(tmp_path: Path) -> None:
    client, _api_key, tenant_id = _client(tmp_path)
    app = cast(Any, client.app)
    app.state.service.create_tenant_user(
        tenant_id=tenant_id,
        email="ops2@example.test",
        password="secret-123",
    )
    with app.state.service.session_factory() as session:
        session.info["disable_tenant_guard"] = True
        tenant = session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        ).scalar_one()

    login = client.post(
        "/auth/login",
        json={
            "email": "ops2@example.test",
            "password": "bad-password",
            "tenant_slug": tenant.slug,
        },
    )
    assert login.status_code == 401
    assert login.headers.get("x-request-id")
    body = login.json()
    assert body["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
    assert body["error"]["request_id"]


def test_auth_refresh_missing_cookie_returns_envelope(tmp_path: Path) -> None:
    client, _api_key, _tenant_id = _client(tmp_path)
    response = client.post("/auth/refresh")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REFRESH_MISSING"


def test_auth_refresh_invalid_cookie_returns_envelope(tmp_path: Path) -> None:
    client, _api_key, _tenant_id = _client(tmp_path)
    response = client.post(
        "/auth/refresh", cookies={"inv_refresh": "invalid-refresh-token"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REFRESH_INVALID"


def test_auth_refresh_expired_session_returns_envelope(tmp_path: Path) -> None:
    client, _api_key, tenant_id = _client(tmp_path)
    app = cast(Any, client.app)
    app.state.service.create_tenant_user(
        tenant_id=tenant_id,
        email="ops-expired@example.test",
        password="secret-123",
        role="admin",
    )
    with app.state.service.session_factory() as session:
        session.info["disable_tenant_guard"] = True
        tenant = session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        ).scalar_one()

    login = client.post(
        "/auth/login",
        json={
            "email": "ops-expired@example.test",
            "password": "secret-123",
            "tenant_slug": tenant.slug,
        },
    )
    assert login.status_code == 200
    refresh_cookie = login.cookies.get("inv_refresh")
    assert refresh_cookie

    with app.state.service.session_factory() as session:
        session.info["disable_tenant_guard"] = True
        auth_session = session.execute(
            select(AuthSession).where(
                AuthSession.refresh_token_hash
                == saas_auth.hash_refresh_token(refresh_cookie)
            )
        ).scalar_one()
        auth_session.refresh_expires_at = datetime.now(timezone.utc) - timedelta(
            seconds=1
        )
        session.commit()

    response = client.post("/auth/refresh", cookies={"inv_refresh": refresh_cookie})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_SESSION_EXPIRED"


def test_auth_me_missing_access_token_returns_envelope(tmp_path: Path) -> None:
    client, _api_key, _tenant_id = _client(tmp_path)
    response = client.get("/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_ACCESS_MISSING"


def test_auth_me_invalid_access_token_returns_envelope(tmp_path: Path) -> None:
    client, _api_key, _tenant_id = _client(tmp_path)
    response = client.get("/v1/me", headers={"Authorization": "Bearer malformed-token"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_ACCESS_INVALID"


def test_auth_login_wrong_tenant_slug_returns_invalid_credentials(
    tmp_path: Path,
) -> None:
    client, _api_key, tenant_id = _client(tmp_path)
    app = cast(Any, client.app)
    app.state.service.create_tenant_user(
        tenant_id=tenant_id,
        email="ops-wrong-tenant@example.test",
        password="secret-123",
    )
    response = client.post(
        "/auth/login",
        json={
            "email": "ops-wrong-tenant@example.test",
            "password": "secret-123",
            "tenant_slug": "wrong-tenant",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


def test_auth_login_validation_error_returns_envelope(tmp_path: Path) -> None:
    client, _api_key, _tenant_id = _client(tmp_path)
    response = client.post(
        "/auth/login",
        json={
            "email": "bad-email",
            "password": "secret-123",
            "tenant_slug": "INVALID_SLUG",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
