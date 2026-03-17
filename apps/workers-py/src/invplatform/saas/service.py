from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import secrets
import re
from datetime import date
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import NoReturn, cast
from urllib.parse import urlencode, urlparse

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from . import auth
from .models import (
    ApiKey,
    AuthSession,
    AuditEvent,
    CollectionJob,
    CollectionJobStatus,
    FileStatus,
    IdempotencyRecord,
    InvoiceFile,
    InvoiceRecord,
    ParseJob,
    ParseJobFile,
    ProviderConfig,
    Report,
    ReportArtifact,
    ReportParseJob,
    Tenant,
    TenantMembership,
    User,
)
from .queue import JobQueue
from .repository import TenantScopedRepository

PARSE_JOB_TASK = "invplatform.saas.tasks.run_parse_job_task"
REPORT_JOB_TASK = "invplatform.saas.tasks.run_report_job_task"
REPORT_CLEANUP_TASK = "invplatform.saas.tasks.run_report_retention_cleanup_task"
COLLECTION_JOB_TASK = "invplatform.saas.tasks.run_collection_job_task"
_REPORT_ALLOWED_FORMATS = {"json", "csv", "summary_csv", "pdf"}
_PROVIDER_ALLOWED_TYPES = {"gmail", "outlook"}
_PROVIDER_ALLOWED_STATUSES = {"connected", "disconnected", "error"}
_PROVIDER_OAUTH_STATE_HASH_KEY = "_oauth_state_hash"
_PROVIDER_OAUTH_STATE_EXPIRES_AT_KEY = "_oauth_state_expires_at"
_PROVIDER_OAUTH_REDIRECT_URI_KEY = "_oauth_redirect_uri"
_PROVIDER_OAUTH_STATE_TTL_SECONDS = 10 * 60
_PROVIDER_ACCESS_TOKEN_TTL_SECONDS = 60 * 60
_COLLECTION_ALLOWED_STATUSES = {status.value for status in CollectionJobStatus}
_MONTH_SCOPE_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class AuthSessionResult:
    access_token: str
    refresh_token: str
    expires_in: int
    user: User
    tenant: Tenant
    membership: TenantMembership
    session: AuthSession


@dataclass(frozen=True)
class AuthMeResult:
    user: User
    tenant: Tenant
    membership: TenantMembership
    session: AuthSession


@dataclass(frozen=True)
class ProviderOAuthStartResult:
    provider: ProviderConfig
    authorization_url: str
    state: str
    state_expires_at: datetime


@dataclass(frozen=True)
class ProviderConnectionTestResult:
    provider: ProviderConfig
    status: str
    message: str
    tested_at: datetime


class AuthError(RuntimeError):
    def __init__(self, *, code: str, message: str, status_code: int = 401):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProviderConfigError(ValueError):
    def __init__(self, *, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class CollectionJobError(ValueError):
    def __init__(self, *, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ServiceConfig:
    parse_job_task_name: str = PARSE_JOB_TASK
    report_job_task_name: str = REPORT_JOB_TASK
    report_cleanup_task_name: str = REPORT_CLEANUP_TASK
    collection_job_task_name: str = COLLECTION_JOB_TASK
    auth_access_token_secret: str | None = None
    auth_access_token_ttl_seconds: int = 900
    auth_refresh_token_ttl_seconds: int = 30 * 24 * 60 * 60
    provider_oauth_client_ids: dict[str, str] = field(
        default_factory=lambda: {
            "gmail": "invoices-codex-local",
            "outlook": "invoices-codex-local",
        }
    )
    provider_oauth_scopes: dict[str, str] = field(
        default_factory=lambda: {
            "gmail": "openid email https://www.googleapis.com/auth/gmail.readonly",
            "outlook": "offline_access User.Read Mail.Read",
        }
    )
    provider_oauth_allowed_redirect_hosts: tuple[str, ...] = (
        "app.example.test",
        "localhost",
        "127.0.0.1",
    )
    provider_oauth_allow_insecure_local_redirect: bool = True


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

    def _resolve_idempotent_collection_job(
        self, session: Session, tenant_id: str, idempotency_key: str
    ) -> CollectionJob | None:
        record = session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == tenant_id,
                IdempotencyRecord.scope == "collection_jobs.create",
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if record is None:
            return None
        return session.execute(
            select(CollectionJob).where(
                CollectionJob.tenant_id == tenant_id,
                CollectionJob.id == record.resource_id,
            )
        ).scalar_one_or_none()

    def _next_unique_tenant_slug(self, session: Session, name: str) -> str:
        return auth.unique_tenant_slug(
            name,
            lambda candidate: (
                session.execute(
                    select(Tenant.id).where(Tenant.slug == candidate)
                ).scalar_one_or_none()
                is not None
            ),
        )

    def _issue_access_token(
        self,
        *,
        user_id: str,
        tenant_id: str,
        membership_id: str,
        session_id: str,
        expires_at: datetime,
    ) -> str:
        if not self.config.auth_access_token_secret:
            raise RuntimeError("auth access token secret is not configured")
        return auth.issue_access_token(
            secret=self.config.auth_access_token_secret,
            user_id=user_id,
            tenant_id=tenant_id,
            membership_id=membership_id,
            session_id=session_id,
            expires_at=expires_at,
        )

    def _auth_fail(
        self,
        session: Session,
        *,
        tenant_id: str,
        event_type: str,
        error_code: str,
        message: str,
        status_code: int,
        request_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        reason_code: str | None = None,
    ) -> NoReturn:
        self._emit_auth_event(
            session,
            tenant_id=tenant_id,
            event_type=event_type,
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            status_code=status_code,
            reason_code=reason_code,
        )
        session.commit()
        raise AuthError(code=error_code, message=message, status_code=status_code)

    def _get_active_principals(
        self,
        session: Session,
        *,
        tenant_id: str,
        user_id: str,
        membership_id: str,
    ) -> tuple[User, TenantMembership, Tenant] | None:
        user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        membership = session.execute(
            select(TenantMembership).where(TenantMembership.id == membership_id)
        ).scalar_one_or_none()
        tenant = session.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one_or_none()
        if (
            user is None
            or membership is None
            or tenant is None
            or not user.is_active
            or membership.status != "active"
        ):
            return None
        return user, membership, tenant

    def _normalize_provider_type(self, provider_type: object) -> str:
        if not isinstance(provider_type, str):
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR", message="provider_type must be a string"
            )
        normalized = provider_type.strip().lower()
        if normalized not in _PROVIDER_ALLOWED_TYPES:
            allowed = ", ".join(sorted(_PROVIDER_ALLOWED_TYPES))
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR",
                message=f"provider_type must be one of: {allowed}",
            )
        return normalized

    def _normalize_provider_status(self, connection_status: object) -> str:
        if not isinstance(connection_status, str):
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR", message="connection_status must be a string"
            )
        normalized = connection_status.strip().lower()
        if normalized not in _PROVIDER_ALLOWED_STATUSES:
            allowed = ", ".join(sorted(_PROVIDER_ALLOWED_STATUSES))
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR",
                message=f"connection_status must be one of: {allowed}",
            )
        return normalized

    def _normalize_collection_status(self, status: object) -> str:
        if not isinstance(status, str):
            raise CollectionJobError(
                code="COLLECTION_VALIDATION_ERROR", message="status must be a string"
            )
        normalized = status.strip().lower()
        if normalized not in _COLLECTION_ALLOWED_STATUSES:
            allowed = ", ".join(sorted(_COLLECTION_ALLOWED_STATUSES))
            raise CollectionJobError(
                code="COLLECTION_VALIDATION_ERROR",
                message=f"status must be one of: {allowed}",
            )
        return normalized

    def _normalize_collection_month_scope(self, month_scope: object) -> str:
        if not isinstance(month_scope, str):
            raise CollectionJobError(
                code="COLLECTION_VALIDATION_ERROR", message="month_scope must be a string"
            )
        normalized = month_scope.strip()
        if not _MONTH_SCOPE_PATTERN.match(normalized):
            raise CollectionJobError(
                code="COLLECTION_VALIDATION_ERROR",
                message="month_scope must match YYYY-MM",
            )
        return normalized

    def _normalize_collection_providers(self, providers: object) -> list[str]:
        if not isinstance(providers, list) or not providers:
            raise CollectionJobError(
                code="COLLECTION_VALIDATION_ERROR",
                message="providers must be a non-empty list",
            )
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_provider in providers:
            if not isinstance(raw_provider, str):
                raise CollectionJobError(
                    code="COLLECTION_VALIDATION_ERROR",
                    message="provider entries must be strings",
                )
            provider = raw_provider.strip().lower()
            if provider not in _PROVIDER_ALLOWED_TYPES:
                allowed = ", ".join(sorted(_PROVIDER_ALLOWED_TYPES))
                raise CollectionJobError(
                    code="COLLECTION_VALIDATION_ERROR",
                    message=f"providers must only contain: {allowed}",
                )
            if provider not in seen:
                seen.add(provider)
                normalized.append(provider)
        if not normalized:
            raise CollectionJobError(
                code="COLLECTION_VALIDATION_ERROR",
                message="providers must be a non-empty list",
            )
        return normalized

    def _str_or_none(self, value: object, field_name: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR",
                message=f"{field_name} must be a string or null",
            )
        return value.strip() or None

    def _nullable_datetime(self, value: object, field_name: str) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR",
                message=f"{field_name} must be a datetime or null",
            )
        return _coerce_utc(value)

    def _config_to_json(self, value: object, *, allow_null: bool) -> str:
        if value is None:
            if allow_null:
                return "{}"
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR", message="config must be an object"
            )
        if not isinstance(value, dict):
            suffix = " or null" if allow_null else ""
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR",
                message=f"config must be an object{suffix}",
            )
        return json.dumps(value, sort_keys=True)

    def _ensure_unique_provider_type(
        self,
        session: Session,
        *,
        tenant_id: str,
        provider_type: str,
        exclude_id: str | None = None,
    ) -> None:
        stmt = select(ProviderConfig.id).where(
            ProviderConfig.tenant_id == tenant_id,
            ProviderConfig.provider_type == provider_type,
        )
        if exclude_id is not None:
            stmt = stmt.where(ProviderConfig.id != exclude_id)
        duplicate = session.execute(stmt).scalar_one_or_none()
        if duplicate is not None:
            raise ProviderConfigError(
                code="PROVIDER_CONFLICT",
                message="provider config already exists for provider_type",
            )

    def _is_provider_unique_violation(self, exc: IntegrityError) -> bool:
        raw_message = str(getattr(exc, "orig", exc)).lower()
        return (
            "uq_saas_provider_configs_tenant_provider" in raw_message
            or "saas_provider_configs.tenant_id, saas_provider_configs.provider_type" in raw_message
        )

    def _normalize_provider_row_datetimes(self, row: ProviderConfig) -> None:
        if row.token_expires_at is not None:
            row.token_expires_at = _coerce_utc(row.token_expires_at)
        if row.last_successful_sync_at is not None:
            row.last_successful_sync_at = _coerce_utc(row.last_successful_sync_at)

    def _provider_config_payload(self, row: ProviderConfig) -> dict[str, object]:
        try:
            payload = json.loads(row.config_json)
        except json.JSONDecodeError as exc:
            raise ProviderConfigError(
                code="PROVIDER_CONFIG_ERROR",
                message="config_json must be valid JSON",
            ) from exc
        if not isinstance(payload, dict):
            raise ProviderConfigError(
                code="PROVIDER_CONFIG_ERROR",
                message="config_json must be a JSON object",
            )
        return cast(dict[str, object], payload)

    def _set_provider_config_payload(self, row: ProviderConfig, payload: dict[str, object]) -> None:
        row.config_json = json.dumps(payload, sort_keys=True)

    def _validate_oauth_redirect_uri(self, redirect_uri: object) -> str:
        if not isinstance(redirect_uri, str):
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR",
                message="redirect_uri must be a string",
            )
        normalized = redirect_uri.strip()
        parsed = urlparse(normalized)
        host = (parsed.hostname or "").strip().lower()
        if not host or not parsed.netloc or parsed.fragment:
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR",
                message="redirect_uri must be an absolute http(s) URL",
            )
        is_local_host = host in {"localhost", "127.0.0.1"}
        if parsed.scheme == "https":
            pass
        elif (
            parsed.scheme == "http"
            and self.config.provider_oauth_allow_insecure_local_redirect
            and is_local_host
        ):
            pass
        else:
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR",
                message="redirect_uri must use https (http is allowed only for localhost)",
            )
        allowed_hosts = {
            item.strip().lower()
            for item in self.config.provider_oauth_allowed_redirect_hosts
            if item.strip()
        }
        if allowed_hosts and host not in allowed_hosts:
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR",
                message="redirect_uri host is not allowed",
            )
        return normalized

    def _state_hash(self, state: str) -> str:
        return hashlib.sha256(state.encode("utf-8")).hexdigest()

    def _seal_provider_token(self, raw_token: str) -> str:
        return f"sha256:{hashlib.sha256(raw_token.encode('utf-8')).hexdigest()}"

    def _provider_oauth_authorization_url(
        self, *, provider_type: str, redirect_uri: str, state: str
    ) -> str:
        base_urls = {
            "gmail": "https://accounts.google.com/o/oauth2/v2/auth",
            "outlook": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        }
        base_url = base_urls.get(provider_type)
        if not base_url:
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR",
                message="provider_type does not support oauth",
            )
        client_id = self.config.provider_oauth_client_ids.get(provider_type, "").strip()
        if not client_id:
            raise ProviderConfigError(
                code="PROVIDER_OAUTH_CONFIG_ERROR",
                message=f"oauth client_id is not configured for provider_type={provider_type}",
            )
        scope = self.config.provider_oauth_scopes.get(provider_type, "").strip()
        if not scope:
            raise ProviderConfigError(
                code="PROVIDER_OAUTH_CONFIG_ERROR",
                message=f"oauth scope is not configured for provider_type={provider_type}",
            )
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
        }
        return f"{base_url}?{urlencode(params)}"

    def _clear_provider_oauth_state(self, payload: dict[str, object]) -> None:
        payload.pop(_PROVIDER_OAUTH_STATE_HASH_KEY, None)
        payload.pop(_PROVIDER_OAUTH_STATE_EXPIRES_AT_KEY, None)
        payload.pop(_PROVIDER_OAUTH_REDIRECT_URI_KEY, None)

    def _provider_not_found_error(self) -> ProviderConfigError:
        return ProviderConfigError(code="PROVIDER_NOT_FOUND", message="provider config not found")

    def _provider_row_or_error(
        self, session: Session, *, tenant_id: str, provider_id: str
    ) -> ProviderConfig:
        row = session.execute(
            select(ProviderConfig).where(
                ProviderConfig.tenant_id == tenant_id,
                ProviderConfig.id == provider_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise self._provider_not_found_error()
        return row

    def _emit_auth_event(
        self,
        session: Session,
        *,
        tenant_id: str,
        event_type: str,
        request_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        status_code: int | None = None,
        reason_code: str | None = None,
    ) -> None:
        payload: dict[str, object] = {}
        if request_id is not None:
            payload["request_id"] = request_id
        if user_id is not None:
            payload["user_id"] = user_id
        if session_id is not None:
            payload["session_id"] = session_id
        if status_code is not None:
            payload["status_code"] = status_code
        if reason_code is not None:
            payload["reason_code"] = reason_code
        session.add(
            AuditEvent(
                tenant_id=tenant_id,
                event_type=event_type,
                actor=user_id,
                payload_json=json.dumps(payload),
            )
        )

    def create_tenant_user(
        self,
        *,
        tenant_id: str,
        email: str,
        password: str,
        full_name: str | None = None,
        role: str = "admin",
        status: str = "active",
    ) -> tuple[User, TenantMembership]:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise ValueError("email is required")
        if not password:
            raise ValueError("password is required")
        if status not in {"active", "disabled", "invited"}:
            raise ValueError("invalid membership status")
        with self.session_factory() as session:
            session.info["disable_tenant_guard"] = True
            tenant = session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            ).scalar_one_or_none()
            if tenant is None:
                raise ValueError("tenant not found")

            user = session.execute(
                select(User).where(User.email_normalized == normalized_email)
            ).scalar_one_or_none()
            if user is None:
                user = User(
                    email=email.strip(),
                    email_normalized=normalized_email,
                    password_hash=auth.hash_password(password),
                    full_name=(full_name or "").strip() or None,
                    is_active=True,
                )
                session.add(user)
                session.flush()
            elif not auth.verify_password(password, user.password_hash):
                raise ValueError("password does not match existing user")

            membership = session.execute(
                select(TenantMembership).where(
                    TenantMembership.tenant_id == tenant_id,
                    TenantMembership.user_id == user.id,
                )
            ).scalar_one_or_none()
            if membership is None:
                membership = TenantMembership(
                    tenant_id=tenant_id,
                    user_id=user.id,
                    role=role,
                    status=status,
                )
                session.add(membership)
            else:
                membership.role = role
                membership.status = status
                membership.updated_at = _utcnow()

            session.commit()
            session.refresh(user)
            session.refresh(membership)
            return user, membership

    def authenticate_user(
        self,
        *,
        tenant_slug: str,
        email: str,
        password: str,
        request_id: str | None = None,
        remote_ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSessionResult:
        normalized_email = email.strip().lower()
        normalized_slug = tenant_slug.strip().lower()
        if not normalized_email or not password or not normalized_slug:
            raise AuthError(
                code="VALIDATION_ERROR",
                message="email, password, and tenant_slug are required.",
                status_code=400,
            )
        if not auth.is_valid_email(normalized_email):
            raise AuthError(
                code="VALIDATION_ERROR",
                message="email format is invalid.",
                status_code=400,
            )
        if not auth.is_valid_tenant_slug(normalized_slug):
            raise AuthError(
                code="VALIDATION_ERROR",
                message="tenant_slug format is invalid.",
                status_code=400,
            )

        now = _utcnow()
        access_expires_at = now + timedelta(seconds=self.config.auth_access_token_ttl_seconds)
        refresh_expires_at = now + timedelta(seconds=self.config.auth_refresh_token_ttl_seconds)

        with self.session_factory() as session:
            session.info["disable_tenant_guard"] = True

            tenant = session.execute(
                select(Tenant).where(Tenant.slug == normalized_slug)
            ).scalar_one_or_none()
            user = session.execute(
                select(User).where(User.email_normalized == normalized_email)
            ).scalar_one_or_none()
            if (
                tenant is None
                or user is None
                or not auth.verify_password(password, user.password_hash)
            ):
                if tenant is not None:
                    self._auth_fail(
                        session,
                        tenant_id=tenant.id,
                        event_type="auth.login.failed",
                        error_code="AUTH_INVALID_CREDENTIALS",
                        message="Email or password is incorrect.",
                        status_code=401,
                        request_id=request_id,
                        reason_code="AUTH_INVALID_CREDENTIALS",
                    )
                raise AuthError(
                    code="AUTH_INVALID_CREDENTIALS",
                    message="Email or password is incorrect.",
                    status_code=401,
                )

            membership = session.execute(
                select(TenantMembership).where(
                    TenantMembership.tenant_id == tenant.id,
                    TenantMembership.user_id == user.id,
                )
            ).scalar_one_or_none()
            if membership is None or membership.status != "active" or not user.is_active:
                self._auth_fail(
                    session,
                    tenant_id=tenant.id,
                    event_type="auth.login.failed",
                    error_code="AUTH_MEMBERSHIP_INACTIVE",
                    message="User membership is inactive for this tenant.",
                    status_code=403,
                    request_id=request_id,
                    user_id=user.id,
                    reason_code="AUTH_MEMBERSHIP_INACTIVE",
                )

            refresh_token = auth.generate_refresh_token()
            auth_session = AuthSession(
                tenant_id=tenant.id,
                user_id=user.id,
                membership_id=membership.id,
                refresh_token_hash=auth.hash_refresh_token(refresh_token),
                access_expires_at=access_expires_at,
                refresh_expires_at=refresh_expires_at,
                created_ip=remote_ip,
                created_user_agent=(user_agent or "")[:512] or None,
            )
            session.add(auth_session)
            user.last_login_at = now
            session.flush()

            self._emit_auth_event(
                session,
                tenant_id=tenant.id,
                event_type="auth.login.succeeded",
                request_id=request_id,
                user_id=user.id,
                session_id=auth_session.id,
                status_code=200,
            )
            session.commit()
            session.refresh(auth_session)
            session.refresh(user)
            session.refresh(membership)
            session.refresh(tenant)

            access_token = self._issue_access_token(
                user_id=user.id,
                tenant_id=tenant.id,
                membership_id=membership.id,
                session_id=auth_session.id,
                expires_at=access_expires_at,
            )
            return AuthSessionResult(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=self.config.auth_access_token_ttl_seconds,
                user=user,
                tenant=tenant,
                membership=membership,
                session=auth_session,
            )

    def refresh_session(
        self, *, refresh_token: str, request_id: str | None = None
    ) -> AuthSessionResult:
        if not refresh_token:
            raise AuthError(
                code="AUTH_REFRESH_MISSING",
                message="Refresh token is required.",
                status_code=401,
            )
        now = _utcnow()
        with self.session_factory() as session:
            session.info["disable_tenant_guard"] = True

            existing = session.execute(
                select(AuthSession).where(
                    AuthSession.refresh_token_hash == auth.hash_refresh_token(refresh_token)
                )
            ).scalar_one_or_none()
            if existing is None:
                raise AuthError(
                    code="AUTH_REFRESH_INVALID",
                    message="Refresh token is invalid.",
                    status_code=401,
                )
            if existing.revoked_at is not None:
                self._auth_fail(
                    session,
                    tenant_id=existing.tenant_id,
                    event_type="auth.refresh.failed",
                    error_code="AUTH_SESSION_REVOKED",
                    message="Session has been revoked.",
                    status_code=401,
                    request_id=request_id,
                    user_id=existing.user_id,
                    session_id=existing.id,
                    reason_code="AUTH_SESSION_REVOKED",
                )
            if _coerce_utc(existing.refresh_expires_at) <= now:
                self._auth_fail(
                    session,
                    tenant_id=existing.tenant_id,
                    event_type="auth.refresh.failed",
                    error_code="AUTH_SESSION_EXPIRED",
                    message="Session refresh window has expired.",
                    status_code=401,
                    request_id=request_id,
                    user_id=existing.user_id,
                    session_id=existing.id,
                    reason_code="AUTH_SESSION_EXPIRED",
                )

            principals = self._get_active_principals(
                session,
                tenant_id=existing.tenant_id,
                user_id=existing.user_id,
                membership_id=existing.membership_id,
            )
            if principals is None:
                existing.revoked_at = now
                existing.revoke_reason = "inactive_membership"
                self._auth_fail(
                    session,
                    tenant_id=existing.tenant_id,
                    event_type="auth.refresh.failed",
                    error_code="AUTH_SESSION_REVOKED",
                    message="Session has been revoked.",
                    status_code=401,
                    request_id=request_id,
                    user_id=existing.user_id,
                    session_id=existing.id,
                    reason_code="AUTH_SESSION_REVOKED",
                )
            user, membership, tenant = principals

            new_refresh_token = auth.generate_refresh_token()
            access_expires_at = now + timedelta(seconds=self.config.auth_access_token_ttl_seconds)
            existing.refresh_token_hash = auth.hash_refresh_token(new_refresh_token)
            existing.access_expires_at = access_expires_at
            existing.last_seen_at = now
            existing.updated_at = now

            self._emit_auth_event(
                session,
                tenant_id=existing.tenant_id,
                event_type="auth.refresh.succeeded",
                request_id=request_id,
                user_id=existing.user_id,
                session_id=existing.id,
                status_code=200,
            )
            session.commit()
            session.refresh(existing)

            access_token = self._issue_access_token(
                user_id=existing.user_id,
                tenant_id=existing.tenant_id,
                membership_id=existing.membership_id,
                session_id=existing.id,
                expires_at=access_expires_at,
            )
            return AuthSessionResult(
                access_token=access_token,
                refresh_token=new_refresh_token,
                expires_in=self.config.auth_access_token_ttl_seconds,
                user=user,
                tenant=tenant,
                membership=membership,
                session=existing,
            )

    def revoke_session(self, *, refresh_token: str | None, request_id: str | None = None) -> None:
        if not refresh_token:
            return
        now = _utcnow()
        with self.session_factory() as session:
            session.info["disable_tenant_guard"] = True
            existing = session.execute(
                select(AuthSession).where(
                    AuthSession.refresh_token_hash == auth.hash_refresh_token(refresh_token)
                )
            ).scalar_one_or_none()
            if existing is None:
                return
            if existing.revoked_at is None:
                existing.revoked_at = now
                existing.revoke_reason = "logout"
                existing.updated_at = now
            self._emit_auth_event(
                session,
                tenant_id=existing.tenant_id,
                event_type="auth.logout.succeeded",
                request_id=request_id,
                user_id=existing.user_id,
                session_id=existing.id,
                status_code=204,
            )
            session.commit()

    def get_current_user(self, *, access_token: str) -> AuthMeResult:
        if not self.config.auth_access_token_secret:
            raise RuntimeError("auth access token secret is not configured")
        claims, token_error = auth.decode_access_token(
            access_token, secret=self.config.auth_access_token_secret
        )
        if token_error == "missing":
            raise AuthError(
                code="AUTH_ACCESS_MISSING",
                message="Access token is missing.",
                status_code=401,
            )
        if token_error == "expired":
            raise AuthError(
                code="AUTH_ACCESS_EXPIRED",
                message="Access token has expired.",
                status_code=401,
            )
        if claims is None:
            raise AuthError(
                code="AUTH_ACCESS_INVALID",
                message="Access token is invalid.",
                status_code=401,
            )

        with self.session_factory() as session:
            session.info["disable_tenant_guard"] = True
            auth_session = session.execute(
                select(AuthSession).where(
                    AuthSession.id == claims.session_id,
                    AuthSession.tenant_id == claims.tenant_id,
                    AuthSession.user_id == claims.user_id,
                )
            ).scalar_one_or_none()
            if auth_session is None or auth_session.revoked_at is not None:
                raise AuthError(
                    code="AUTH_ACCESS_INVALID",
                    message="Access token is invalid.",
                    status_code=401,
                )
            principals = self._get_active_principals(
                session,
                tenant_id=claims.tenant_id,
                user_id=claims.user_id,
                membership_id=claims.membership_id,
            )
            if principals is None:
                raise AuthError(
                    code="AUTH_ACCESS_INVALID",
                    message="Access token is invalid.",
                    status_code=401,
                )
            user, membership, tenant = principals
            return AuthMeResult(
                user=user,
                tenant=tenant,
                membership=membership,
                session=auth_session,
            )

    def bootstrap_tenant(self, name: str, actor: str | None = None) -> tuple[Tenant, str]:
        api_key_material = auth.generate_api_key()
        with self.session_factory() as session:
            session.info["disable_tenant_guard"] = True
            tenant = Tenant(name=name, slug=self._next_unique_tenant_slug(session, name))
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

    def list_provider_configs(
        self, tenant_id: str, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[ProviderConfig], int]:
        if limit < 1:
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR", message="limit must be >= 1"
            )
        if offset < 0:
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR", message="offset must be >= 0"
            )
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                repo = TenantScopedRepository(session, tenant_id)
                total = repo.count(ProviderConfig)
                items = cast(
                    list[ProviderConfig],
                    repo.list(
                        ProviderConfig,
                        order_by=[ProviderConfig.created_at.desc(), ProviderConfig.id.desc()],
                        limit=limit,
                        offset=offset,
                    ),
                )
                return items, total

    def create_provider_config(
        self,
        tenant_id: str,
        *,
        provider_type: str,
        display_name: str | None = None,
        connection_status: str = "disconnected",
        config: object | None = None,
        actor: str | None = None,
    ) -> ProviderConfig:
        normalized_type = self._normalize_provider_type(provider_type)
        normalized_status = self._normalize_provider_status(connection_status)
        config_json = self._config_to_json(config if config is not None else {}, allow_null=False)
        normalized_display_name = self._str_or_none(display_name, "display_name")

        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                self._ensure_unique_provider_type(
                    session,
                    tenant_id=tenant_id,
                    provider_type=normalized_type,
                )

                row = ProviderConfig(
                    tenant_id=tenant_id,
                    provider_type=normalized_type,
                    display_name=normalized_display_name,
                    connection_status=normalized_status,
                    config_json=config_json,
                )
                session.add(row)
                try:
                    session.flush()
                except IntegrityError as exc:
                    session.rollback()
                    if self._is_provider_unique_violation(exc):
                        raise ProviderConfigError(
                            code="PROVIDER_CONFLICT",
                            message="provider config already exists for provider_type",
                        ) from exc
                    raise
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="provider.create",
                        actor=actor,
                        payload_json=json.dumps(
                            {
                                "provider_id": row.id,
                                "provider_type": row.provider_type,
                                "connection_status": row.connection_status,
                            }
                        ),
                    )
                )
                try:
                    session.commit()
                except IntegrityError as exc:
                    session.rollback()
                    if self._is_provider_unique_violation(exc):
                        raise ProviderConfigError(
                            code="PROVIDER_CONFLICT",
                            message="provider config already exists for provider_type",
                        ) from exc
                    raise
                session.refresh(row)
                self._normalize_provider_row_datetimes(row)
                return row

    def update_provider_config(
        self,
        tenant_id: str,
        provider_id: str,
        *,
        updates: dict[str, object],
        actor: str | None = None,
    ) -> ProviderConfig:
        if not updates:
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR",
                message="at least one field must be provided",
            )
        allowed_fields = {
            "provider_type",
            "display_name",
            "connection_status",
            "config",
            "token_expires_at",
            "last_successful_sync_at",
            "last_error_code",
            "last_error_message",
        }
        unknown_fields = sorted(set(updates) - allowed_fields)
        if unknown_fields:
            raise ProviderConfigError(
                code="PROVIDER_VALIDATION_ERROR",
                message=f"unknown provider fields: {', '.join(unknown_fields)}",
            )

        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                row = session.execute(
                    select(ProviderConfig).where(
                        ProviderConfig.tenant_id == tenant_id,
                        ProviderConfig.id == provider_id,
                    )
                ).scalar_one_or_none()
                if row is None:
                    raise ProviderConfigError(
                        code="PROVIDER_NOT_FOUND", message="provider config not found"
                    )

                if "provider_type" in updates:
                    normalized_type = self._normalize_provider_type(updates["provider_type"])
                    if normalized_type != row.provider_type:
                        self._ensure_unique_provider_type(
                            session,
                            tenant_id=tenant_id,
                            provider_type=normalized_type,
                            exclude_id=provider_id,
                        )
                    row.provider_type = normalized_type

                if "display_name" in updates:
                    row.display_name = self._str_or_none(updates["display_name"], "display_name")

                if "connection_status" in updates:
                    row.connection_status = self._normalize_provider_status(
                        updates["connection_status"]
                    )

                if "config" in updates:
                    row.config_json = self._config_to_json(updates["config"], allow_null=True)

                if "token_expires_at" in updates:
                    row.token_expires_at = self._nullable_datetime(
                        updates["token_expires_at"], "token_expires_at"
                    )

                if "last_successful_sync_at" in updates:
                    row.last_successful_sync_at = self._nullable_datetime(
                        updates["last_successful_sync_at"], "last_successful_sync_at"
                    )

                if "last_error_code" in updates:
                    row.last_error_code = self._str_or_none(
                        updates["last_error_code"], "last_error_code"
                    )

                if "last_error_message" in updates:
                    row.last_error_message = self._str_or_none(
                        updates["last_error_message"], "last_error_message"
                    )

                row.updated_at = _utcnow()
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="provider.update",
                        actor=actor,
                        payload_json=json.dumps(
                            {
                                "provider_id": row.id,
                                "provider_type": row.provider_type,
                                "updated_fields": sorted(updates.keys()),
                            }
                        ),
                    )
                )
                try:
                    session.commit()
                except IntegrityError as exc:
                    session.rollback()
                    if self._is_provider_unique_violation(exc):
                        raise ProviderConfigError(
                            code="PROVIDER_CONFLICT",
                            message="provider config already exists for provider_type",
                        ) from exc
                    raise
                session.refresh(row)
                self._normalize_provider_row_datetimes(row)
                return row

    def delete_provider_config(
        self,
        tenant_id: str,
        provider_id: str,
        *,
        actor: str | None = None,
    ) -> None:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                row = session.execute(
                    select(ProviderConfig).where(
                        ProviderConfig.tenant_id == tenant_id,
                        ProviderConfig.id == provider_id,
                    )
                ).scalar_one_or_none()
                if row is None:
                    raise ProviderConfigError(
                        code="PROVIDER_NOT_FOUND", message="provider config not found"
                    )
                provider_type = row.provider_type
                session.delete(row)
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="provider.delete",
                        actor=actor,
                        payload_json=json.dumps(
                            {"provider_id": provider_id, "provider_type": provider_type}
                        ),
                    )
                )
                session.commit()

    def create_collection_job(
        self,
        tenant_id: str,
        *,
        providers: list[str],
        month_scope: str,
        idempotency_key: str | None = None,
        actor: str | None = None,
    ) -> CollectionJob:
        normalized_providers = self._normalize_collection_providers(providers)
        normalized_month_scope = self._normalize_collection_month_scope(month_scope)
        normalized_key = (idempotency_key or "").strip() or None

        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                if normalized_key is not None:
                    existing = self._resolve_idempotent_collection_job(
                        session, tenant_id, normalized_key
                    )
                    if existing is not None:
                        return existing

                row = CollectionJob(
                    tenant_id=tenant_id,
                    status=CollectionJobStatus.QUEUED.value,
                    idempotency_key=normalized_key,
                    providers_json=json.dumps(normalized_providers),
                    month_scope=normalized_month_scope,
                    parse_job_ids_json="[]",
                    files_discovered=0,
                    files_downloaded=0,
                )
                session.add(row)
                session.flush()
                queue_job_id = self.queue.enqueue(
                    self.config.collection_job_task_name,
                    {"collection_job_id": row.id},
                )
                row.queue_job_id = queue_job_id

                if normalized_key is not None:
                    session.add(
                        IdempotencyRecord(
                            tenant_id=tenant_id,
                            scope="collection_jobs.create",
                            idempotency_key=normalized_key,
                            resource_type="collection_job",
                            resource_id=row.id,
                        )
                    )
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="collection_job.create",
                        actor=actor,
                        payload_json=json.dumps(
                            {
                                "collection_job_id": row.id,
                                "providers": normalized_providers,
                                "month_scope": normalized_month_scope,
                                "status": row.status,
                                "idempotency_key": normalized_key,
                                "queue_job_id": queue_job_id,
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
                    existing = self._resolve_idempotent_collection_job(
                        session, tenant_id, normalized_key
                    )
                    if existing is None:
                        raise
                    return existing
                session.refresh(row)
                return row

    def list_collection_jobs(
        self,
        tenant_id: str,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[CollectionJob], int]:
        if limit < 1:
            raise CollectionJobError(
                code="COLLECTION_VALIDATION_ERROR", message="limit must be >= 1"
            )
        if offset < 0:
            raise CollectionJobError(
                code="COLLECTION_VALIDATION_ERROR", message="offset must be >= 0"
            )

        normalized_status = self._normalize_collection_status(status) if status else None

        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                repo = TenantScopedRepository(session, tenant_id)
                filters: list[object] = []
                if normalized_status is not None:
                    filters.append(CollectionJob.status == normalized_status)
                total = repo.count(CollectionJob, *filters)
                items = cast(
                    list[CollectionJob],
                    repo.list(
                        CollectionJob,
                        *filters,
                        order_by=[CollectionJob.created_at.desc(), CollectionJob.id.desc()],
                        limit=limit,
                        offset=offset,
                    ),
                )
                return items, total

    def get_collection_job(self, tenant_id: str, collection_job_id: str) -> CollectionJob | None:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                repo = TenantScopedRepository(session, tenant_id)
                return cast(
                    CollectionJob | None,
                    repo.one_or_none(CollectionJob, CollectionJob.id == collection_job_id),
                )

    def start_provider_oauth(
        self,
        tenant_id: str,
        provider_id: str,
        *,
        redirect_uri: str,
        actor: str | None = None,
        request_id: str | None = None,
    ) -> ProviderOAuthStartResult:
        normalized_redirect_uri = self._validate_oauth_redirect_uri(redirect_uri)
        now = _utcnow()
        state = secrets.token_urlsafe(24)
        state_expires_at = now + timedelta(seconds=_PROVIDER_OAUTH_STATE_TTL_SECONDS)
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                row = self._provider_row_or_error(
                    session, tenant_id=tenant_id, provider_id=provider_id
                )
                payload = self._provider_config_payload(row)
                payload[_PROVIDER_OAUTH_STATE_HASH_KEY] = self._state_hash(state)
                payload[_PROVIDER_OAUTH_STATE_EXPIRES_AT_KEY] = state_expires_at.isoformat()
                payload[_PROVIDER_OAUTH_REDIRECT_URI_KEY] = normalized_redirect_uri
                self._set_provider_config_payload(row, payload)
                row.updated_at = now
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="provider.oauth.start",
                        actor=actor,
                        payload_json=json.dumps(
                            {
                                "provider_id": row.id,
                                "provider_type": row.provider_type,
                                "request_id": request_id,
                                "state_expires_at": state_expires_at.isoformat(),
                            }
                        ),
                    )
                )
                session.commit()
                session.refresh(row)
                authorization_url = self._provider_oauth_authorization_url(
                    provider_type=row.provider_type,
                    redirect_uri=normalized_redirect_uri,
                    state=state,
                )
                return ProviderOAuthStartResult(
                    provider=row,
                    authorization_url=authorization_url,
                    state=state,
                    state_expires_at=state_expires_at,
                )

    def complete_provider_oauth_callback(
        self,
        tenant_id: str,
        provider_id: str,
        *,
        state: str,
        code: str,
        actor: str | None = None,
        request_id: str | None = None,
    ) -> ProviderConfig:
        normalized_state = state.strip()
        normalized_code = code.strip()
        if not normalized_state:
            raise ProviderConfigError(code="PROVIDER_VALIDATION_ERROR", message="state is required")
        if not normalized_code:
            raise ProviderConfigError(code="PROVIDER_VALIDATION_ERROR", message="code is required")

        now = _utcnow()
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                row = self._provider_row_or_error(
                    session, tenant_id=tenant_id, provider_id=provider_id
                )
                payload = self._provider_config_payload(row)
                expected_hash = payload.get(_PROVIDER_OAUTH_STATE_HASH_KEY)
                expires_at_raw = payload.get(_PROVIDER_OAUTH_STATE_EXPIRES_AT_KEY)
                if not isinstance(expected_hash, str) or not isinstance(expires_at_raw, str):
                    raise ProviderConfigError(
                        code="PROVIDER_OAUTH_STATE_INVALID",
                        message="oauth state is missing or invalid",
                    )
                try:
                    expires_at = _coerce_utc(datetime.fromisoformat(expires_at_raw))
                except ValueError as exc:
                    raise ProviderConfigError(
                        code="PROVIDER_OAUTH_STATE_INVALID",
                        message="oauth state is missing or invalid",
                    ) from exc

                if expires_at <= now:
                    self._clear_provider_oauth_state(payload)
                    self._set_provider_config_payload(row, payload)
                    row.connection_status = "error"
                    row.last_error_code = "OAUTH_STATE_EXPIRED"
                    row.last_error_message = "OAuth state has expired. Restart provider connect."
                    row.updated_at = now
                    session.add(
                        AuditEvent(
                            tenant_id=tenant_id,
                            event_type="provider.oauth.callback.failed",
                            actor=actor,
                            payload_json=json.dumps(
                                {
                                    "provider_id": row.id,
                                    "provider_type": row.provider_type,
                                    "request_id": request_id,
                                    "reason": "state_expired",
                                }
                            ),
                        )
                    )
                    session.commit()
                    raise ProviderConfigError(
                        code="PROVIDER_OAUTH_STATE_EXPIRED",
                        message="oauth state has expired",
                    )

                if not secrets.compare_digest(expected_hash, self._state_hash(normalized_state)):
                    session.add(
                        AuditEvent(
                            tenant_id=tenant_id,
                            event_type="provider.oauth.callback.failed",
                            actor=actor,
                            payload_json=json.dumps(
                                {
                                    "provider_id": row.id,
                                    "provider_type": row.provider_type,
                                    "request_id": request_id,
                                    "reason": "state_invalid",
                                }
                            ),
                        )
                    )
                    session.commit()
                    raise ProviderConfigError(
                        code="PROVIDER_OAUTH_STATE_INVALID",
                        message="oauth state is missing or invalid",
                    )

                self._clear_provider_oauth_state(payload)
                self._set_provider_config_payload(row, payload)

                row.oauth_access_token_enc = self._seal_provider_token(
                    f"{row.provider_type}:access:{secrets.token_urlsafe(32)}"
                )
                row.oauth_refresh_token_enc = self._seal_provider_token(
                    f"{row.provider_type}:refresh:{secrets.token_urlsafe(40)}"
                )
                row.connection_status = "connected"
                row.token_expires_at = now + timedelta(seconds=_PROVIDER_ACCESS_TOKEN_TTL_SECONDS)
                row.last_successful_sync_at = now
                row.last_error_code = None
                row.last_error_message = None
                row.updated_at = now

                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="provider.oauth.callback.succeeded",
                        actor=actor,
                        payload_json=json.dumps(
                            {
                                "provider_id": row.id,
                                "provider_type": row.provider_type,
                                "request_id": request_id,
                            }
                        ),
                    )
                )
                session.commit()
                session.refresh(row)
                self._normalize_provider_row_datetimes(row)
                return row

    def refresh_provider_oauth(
        self,
        tenant_id: str,
        provider_id: str,
        *,
        actor: str | None = None,
        request_id: str | None = None,
    ) -> ProviderConfig:
        now = _utcnow()
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                row = self._provider_row_or_error(
                    session, tenant_id=tenant_id, provider_id=provider_id
                )
                if not row.oauth_refresh_token_enc:
                    session.add(
                        AuditEvent(
                            tenant_id=tenant_id,
                            event_type="provider.oauth.refresh.failed",
                            actor=actor,
                            payload_json=json.dumps(
                                {
                                    "provider_id": row.id,
                                    "provider_type": row.provider_type,
                                    "request_id": request_id,
                                    "reason": "not_connected",
                                }
                            ),
                        )
                    )
                    session.commit()
                    raise ProviderConfigError(
                        code="PROVIDER_OAUTH_NOT_CONNECTED",
                        message="provider is not connected",
                    )

                row.oauth_access_token_enc = self._seal_provider_token(
                    f"{row.provider_type}:access:{secrets.token_urlsafe(32)}"
                )
                row.oauth_refresh_token_enc = self._seal_provider_token(
                    f"{row.provider_type}:refresh:{secrets.token_urlsafe(40)}"
                )
                row.connection_status = "connected"
                row.token_expires_at = now + timedelta(seconds=_PROVIDER_ACCESS_TOKEN_TTL_SECONDS)
                row.last_successful_sync_at = now
                row.last_error_code = None
                row.last_error_message = None
                row.updated_at = now

                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="provider.oauth.refresh.succeeded",
                        actor=actor,
                        payload_json=json.dumps(
                            {
                                "provider_id": row.id,
                                "provider_type": row.provider_type,
                                "request_id": request_id,
                            }
                        ),
                    )
                )
                session.commit()
                session.refresh(row)
                self._normalize_provider_row_datetimes(row)
                return row

    def revoke_provider_oauth(
        self,
        tenant_id: str,
        provider_id: str,
        *,
        actor: str | None = None,
        request_id: str | None = None,
    ) -> ProviderConfig:
        now = _utcnow()
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                row = self._provider_row_or_error(
                    session, tenant_id=tenant_id, provider_id=provider_id
                )
                payload = self._provider_config_payload(row)
                self._clear_provider_oauth_state(payload)
                self._set_provider_config_payload(row, payload)

                had_tokens = bool(row.oauth_access_token_enc or row.oauth_refresh_token_enc)
                row.oauth_access_token_enc = None
                row.oauth_refresh_token_enc = None
                row.connection_status = "disconnected"
                row.token_expires_at = None
                row.last_error_code = None
                row.last_error_message = None
                row.updated_at = now

                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="provider.oauth.revoke.succeeded",
                        actor=actor,
                        payload_json=json.dumps(
                            {
                                "provider_id": row.id,
                                "provider_type": row.provider_type,
                                "request_id": request_id,
                                "had_tokens": had_tokens,
                            }
                        ),
                    )
                )
                session.commit()
                session.refresh(row)
                self._normalize_provider_row_datetimes(row)
                return row

    def test_provider_connection(
        self,
        tenant_id: str,
        provider_id: str,
        *,
        actor: str | None = None,
        request_id: str | None = None,
    ) -> ProviderConnectionTestResult:
        now = _utcnow()
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                row = self._provider_row_or_error(
                    session, tenant_id=tenant_id, provider_id=provider_id
                )
                is_disconnected = row.connection_status == "disconnected"
                is_missing_token = not row.oauth_access_token_enc
                token_expires_at = _coerce_utc(row.token_expires_at) if row.token_expires_at else None
                is_token_expired = bool(token_expires_at and token_expires_at <= now)

                if is_disconnected or is_missing_token or is_token_expired:
                    if is_disconnected:
                        message = "provider is not connected"
                        reason = "not_connected"
                    elif is_token_expired:
                        message = "provider access token has expired"
                        reason = "token_expired"
                        row.connection_status = "error"
                    else:
                        message = "provider credentials are missing; reconnect provider"
                        reason = "missing_access_token"
                        row.connection_status = "error"

                    row.last_error_code = "PROVIDER_TEST_CONNECTION_FAILED"
                    row.last_error_message = message
                    row.updated_at = now
                    session.add(
                        AuditEvent(
                            tenant_id=tenant_id,
                            event_type="provider.test_connection.failed",
                            actor=actor,
                            payload_json=json.dumps(
                                {
                                    "provider_id": row.id,
                                    "provider_type": row.provider_type,
                                    "request_id": request_id,
                                    "reason": reason,
                                    "tested_at": now.isoformat(),
                                }
                            ),
                        )
                    )
                    session.commit()
                    session.refresh(row)
                    self._normalize_provider_row_datetimes(row)
                    return ProviderConnectionTestResult(
                        provider=row,
                        status="failure",
                        message=message,
                        tested_at=now,
                    )

                row.connection_status = "connected"
                row.last_successful_sync_at = now
                row.last_error_code = None
                row.last_error_message = None
                row.updated_at = now
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="provider.test_connection.succeeded",
                        actor=actor,
                        payload_json=json.dumps(
                            {
                                "provider_id": row.id,
                                "provider_type": row.provider_type,
                                "request_id": request_id,
                                "tested_at": now.isoformat(),
                            }
                        ),
                    )
                )
                session.commit()
                session.refresh(row)
                self._normalize_provider_row_datetimes(row)
                return ProviderConnectionTestResult(
                    provider=row,
                    status="success",
                    message="provider connection verified",
                    tested_at=now,
                )

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
