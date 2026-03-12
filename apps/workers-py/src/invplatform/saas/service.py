from __future__ import annotations

from contextlib import contextmanager
import json
from datetime import date
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Any, NoReturn, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from . import auth
from .models import (
    ApiKey,
    AuthSession,
    AuditEvent,
    FileStatus,
    IdempotencyRecord,
    InvoiceFile,
    InvoiceRecord,
    ParseJob,
    ParseJobFile,
    ProviderConfig,
    ProviderConnectionStatus,
    ProviderType,
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
_REPORT_ALLOWED_FORMATS = {"json", "csv", "summary_csv", "pdf"}
_PROVIDER_ALLOWED_TYPES = {ProviderType.GMAIL.value, ProviderType.OUTLOOK.value}
_PROVIDER_ALLOWED_CONNECTION_STATUSES = {
    ProviderConnectionStatus.CONNECTED.value,
    ProviderConnectionStatus.DISCONNECTED.value,
    ProviderConnectionStatus.ERROR.value,
}


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


class AuthError(RuntimeError):
    def __init__(self, *, code: str, message: str, status_code: int = 401):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass
class ServiceConfig:
    parse_job_task_name: str = PARSE_JOB_TASK
    report_job_task_name: str = REPORT_JOB_TASK
    report_cleanup_task_name: str = REPORT_CLEANUP_TASK
    auth_access_token_secret: str | None = None
    auth_access_token_ttl_seconds: int = 900
    auth_refresh_token_ttl_seconds: int = 30 * 24 * 60 * 60


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

    def list_provider_configs(self, tenant_id: str) -> list[ProviderConfig]:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                return list(
                    session.execute(
                        select(ProviderConfig)
                        .where(ProviderConfig.tenant_id == tenant_id)
                        .order_by(ProviderConfig.created_at.desc(), ProviderConfig.id.desc())
                    )
                    .scalars()
                    .all()
                )

    def create_provider_config(
        self,
        tenant_id: str,
        *,
        provider_type: str,
        display_name: str | None = None,
        actor: str | None = None,
    ) -> ProviderConfig:
        normalized_provider_type = provider_type.strip().lower()
        if normalized_provider_type not in _PROVIDER_ALLOWED_TYPES:
            raise ValueError(
                f"provider_type must be one of: {', '.join(sorted(_PROVIDER_ALLOWED_TYPES))}"
            )
        normalized_display_name = (display_name or "").strip() or None

        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                existing = session.execute(
                    select(ProviderConfig).where(
                        ProviderConfig.tenant_id == tenant_id,
                        ProviderConfig.provider_type == normalized_provider_type,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    raise ValueError(
                        f"provider {normalized_provider_type} already configured for tenant"
                    )

                provider = ProviderConfig(
                    tenant_id=tenant_id,
                    provider_type=normalized_provider_type,
                    display_name=normalized_display_name,
                    connection_status=ProviderConnectionStatus.DISCONNECTED.value,
                )
                session.add(provider)
                session.flush()
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="provider.create",
                        actor=actor,
                        payload_json=json.dumps(
                            {
                                "provider_id": provider.id,
                                "provider_type": provider.provider_type,
                                "connection_status": provider.connection_status,
                            }
                        ),
                    )
                )
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    existing = session.execute(
                        select(ProviderConfig).where(
                            ProviderConfig.tenant_id == tenant_id,
                            ProviderConfig.provider_type == normalized_provider_type,
                        )
                    ).scalar_one_or_none()
                    if existing is not None:
                        raise ValueError(
                            f"provider {normalized_provider_type} already configured for tenant"
                        )
                    raise
                session.refresh(provider)
                return provider

    def update_provider_config(
        self,
        tenant_id: str,
        provider_id: str,
        *,
        updates: dict[str, Any],
        actor: str | None = None,
    ) -> ProviderConfig:
        if not updates:
            raise ValueError("at least one field must be provided")
        allowed_fields = {
            "display_name",
            "connection_status",
            "token_expires_at",
            "last_successful_sync_at",
            "last_error_code",
            "last_error_message",
        }
        unsupported_fields = sorted(set(updates) - allowed_fields)
        if unsupported_fields:
            raise ValueError(f"unsupported fields: {', '.join(unsupported_fields)}")

        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                provider = session.execute(
                    select(ProviderConfig).where(
                        ProviderConfig.tenant_id == tenant_id,
                        ProviderConfig.id == provider_id,
                    )
                ).scalar_one_or_none()
                if provider is None:
                    raise LookupError("provider not found")

                payload_updates: dict[str, Any] = {}
                if "display_name" in updates:
                    raw_display_name = updates["display_name"]
                    if raw_display_name is not None and not isinstance(raw_display_name, str):
                        raise ValueError("display_name must be a string or null")
                    provider.display_name = (
                        raw_display_name.strip() if isinstance(raw_display_name, str) else None
                    ) or None
                    payload_updates["display_name"] = provider.display_name

                if "connection_status" in updates:
                    raw_connection_status = updates["connection_status"]
                    if not isinstance(raw_connection_status, str):
                        raise ValueError("connection_status must be a string")
                    normalized_connection_status = raw_connection_status.strip().lower()
                    if normalized_connection_status not in _PROVIDER_ALLOWED_CONNECTION_STATUSES:
                        raise ValueError(
                            "connection_status must be one of: "
                            + ", ".join(sorted(_PROVIDER_ALLOWED_CONNECTION_STATUSES))
                        )
                    provider.connection_status = normalized_connection_status
                    payload_updates["connection_status"] = provider.connection_status
                    if provider.connection_status != ProviderConnectionStatus.ERROR.value:
                        provider.last_error_code = None
                        provider.last_error_message = None
                        payload_updates["last_error_code"] = None
                        payload_updates["last_error_message"] = None

                if "token_expires_at" in updates:
                    raw_token_expires_at = updates["token_expires_at"]
                    if raw_token_expires_at is not None and not isinstance(
                        raw_token_expires_at, datetime
                    ):
                        raise ValueError("token_expires_at must be a datetime or null")
                    provider.token_expires_at = (
                        _coerce_utc(raw_token_expires_at)
                        if isinstance(raw_token_expires_at, datetime)
                        else None
                    )
                    payload_updates["token_expires_at"] = (
                        provider.token_expires_at.isoformat()
                        if provider.token_expires_at is not None
                        else None
                    )

                if "last_successful_sync_at" in updates:
                    raw_last_successful_sync_at = updates["last_successful_sync_at"]
                    if raw_last_successful_sync_at is not None and not isinstance(
                        raw_last_successful_sync_at, datetime
                    ):
                        raise ValueError("last_successful_sync_at must be a datetime or null")
                    provider.last_successful_sync_at = (
                        _coerce_utc(raw_last_successful_sync_at)
                        if isinstance(raw_last_successful_sync_at, datetime)
                        else None
                    )
                    payload_updates["last_successful_sync_at"] = (
                        provider.last_successful_sync_at.isoformat()
                        if provider.last_successful_sync_at is not None
                        else None
                    )

                if "last_error_code" in updates:
                    raw_last_error_code = updates["last_error_code"]
                    if raw_last_error_code is not None and not isinstance(raw_last_error_code, str):
                        raise ValueError("last_error_code must be a string or null")
                    provider.last_error_code = (
                        raw_last_error_code.strip()
                        if isinstance(raw_last_error_code, str)
                        else None
                    ) or None
                    payload_updates["last_error_code"] = provider.last_error_code

                if "last_error_message" in updates:
                    raw_last_error_message = updates["last_error_message"]
                    if raw_last_error_message is not None and not isinstance(
                        raw_last_error_message, str
                    ):
                        raise ValueError("last_error_message must be a string or null")
                    provider.last_error_message = (
                        raw_last_error_message.strip()
                        if isinstance(raw_last_error_message, str)
                        else None
                    ) or None
                    payload_updates["last_error_message"] = provider.last_error_message

                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        event_type="provider.update",
                        actor=actor,
                        payload_json=json.dumps(
                            {"provider_id": provider.id, "updates": payload_updates}
                        ),
                    )
                )
                session.commit()
                session.refresh(provider)
                return provider

    def delete_provider_config(
        self, tenant_id: str, provider_id: str, *, actor: str | None = None
    ) -> None:
        with self.session_factory() as session:
            with self._tenant_scope(session, tenant_id):
                provider = session.execute(
                    select(ProviderConfig).where(
                        ProviderConfig.tenant_id == tenant_id,
                        ProviderConfig.id == provider_id,
                    )
                ).scalar_one_or_none()
                if provider is None:
                    raise LookupError("provider not found")
                provider_type = provider.provider_type
                session.delete(provider)
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
