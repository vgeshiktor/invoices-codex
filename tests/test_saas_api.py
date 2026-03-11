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
    assert "/v1/control-plane/tenants" in body["paths"]
    assert body["paths"]["/v1/files"]["post"]["security"] == [{"ApiKeyAuth": []}]
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
