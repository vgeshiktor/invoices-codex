import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from .db import build_engine, build_session_factory
from .metrics import MetricsRegistry
from .models import (
    ApiKey,
    Base,
    CollectionJob,
    InvoiceRecord,
    ParseJob,
    ProviderConfig,
    Report,
    ReportArtifact,
    Tenant,
    TenantMembership,
    User,
)
from .queue import build_queue
from .service import (
    AuthError,
    CollectionJobError,
    ProviderConfigError,
    SaaSService,
    ServiceConfig,
)
from .storage import StorageBackend, build_storage

logger = logging.getLogger(__name__)


@dataclass
class ApiAppConfig:
    database_url: str = "sqlite:///./invoices_saas.db"
    redis_url: str | None = None
    storage_url: str = "local://./data/saas_storage"
    control_plane_api_key: str | None = None
    auth_access_token_secret: str | None = None
    auth_access_token_ttl_seconds: int = 900
    auth_refresh_token_ttl_seconds: int = 30 * 24 * 60 * 60
    auth_cookie_secure: bool = True
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
    cors_allow_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    )


def _normalize_action(method: str, route_path: str) -> str:
    normalized = route_path.strip("/").replace("/", ".").replace("{", "").replace("}", "")
    if not normalized:
        normalized = "root"
    return f"{method.lower()}.{normalized}"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _api_key_to_dict(row: ApiKey) -> dict[str, object]:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "key_prefix": row.key_prefix,
        "revoked": bool(row.revoked),
        "created_at": _iso(row.created_at),
        "revoked_at": _iso(row.revoked_at),
    }


def _tenant_to_dict(row: Tenant) -> dict[str, object]:
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "created_at": _iso(row.created_at),
    }


def _user_to_dict(row: User) -> dict[str, object]:
    return {
        "id": row.id,
        "email": row.email,
        "full_name": row.full_name,
        "is_active": bool(row.is_active),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _membership_to_dict(row: TenantMembership) -> dict[str, object]:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "user_id": row.user_id,
        "role": row.role,
        "status": row.status,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _job_to_dict(job: ParseJob) -> dict[str, object]:
    return {
        "id": job.id,
        "tenant_id": job.tenant_id,
        "status": job.status,
        "idempotency_key": job.idempotency_key,
        "queue_job_id": job.queue_job_id,
        "debug": job.debug,
        "records_count": job.records_count,
        "failed_count": job.failed_count,
        "error_message": job.error_message,
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
    }


def _collection_job_to_dict(row: CollectionJob) -> dict[str, object]:
    providers: list[str] = []
    parse_job_ids: list[str] = []
    try:
        loaded_providers = json.loads(row.providers_json)
        if isinstance(loaded_providers, list):
            providers = [str(value) for value in loaded_providers]
    except json.JSONDecodeError:
        logger.warning(
            "Failed to decode providers_json for collection_job_id=%s tenant_id=%s",
            row.id,
            row.tenant_id,
            exc_info=True,
        )
    try:
        loaded_parse_job_ids = json.loads(row.parse_job_ids_json)
        if isinstance(loaded_parse_job_ids, list):
            parse_job_ids = [str(value) for value in loaded_parse_job_ids]
    except json.JSONDecodeError:
        logger.warning(
            "Failed to decode parse_job_ids_json for collection_job_id=%s tenant_id=%s",
            row.id,
            row.tenant_id,
            exc_info=True,
        )
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "status": row.status,
        "idempotency_key": row.idempotency_key,
        "providers": providers,
        "month_scope": row.month_scope,
        "queue_job_id": row.queue_job_id,
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "files_discovered": row.files_discovered,
        "files_downloaded": row.files_downloaded,
        "parse_job_ids": parse_job_ids,
        "error_message": row.error_message,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _build_service(config: ApiAppConfig) -> SaaSService:
    engine = build_engine(config.database_url)
    Base.metadata.create_all(bind=engine)
    session_factory: sessionmaker[Session] = build_session_factory(
        engine, enforce_tenant_guard=True
    )
    queue = build_queue(config.redis_url)
    service_config = ServiceConfig(
        auth_access_token_secret=config.auth_access_token_secret,
        auth_access_token_ttl_seconds=config.auth_access_token_ttl_seconds,
        auth_refresh_token_ttl_seconds=config.auth_refresh_token_ttl_seconds,
        provider_oauth_client_ids=dict(config.provider_oauth_client_ids),
        provider_oauth_scopes=dict(config.provider_oauth_scopes),
        provider_oauth_allowed_redirect_hosts=tuple(config.provider_oauth_allowed_redirect_hosts),
        provider_oauth_allow_insecure_local_redirect=config.provider_oauth_allow_insecure_local_redirect,
    )
    return SaaSService(session_factory=session_factory, queue=queue, config=service_config)


def _invoice_to_dict(row: InvoiceRecord) -> dict[str, object]:
    return {
        "id": row.id,
        "parse_job_id": row.parse_job_id,
        "vendor": row.vendor,
        "file_name": row.file_name,
        "invoice_number": row.invoice_number,
        "invoice_date": row.invoice_date.isoformat() if row.invoice_date else None,
        "invoice_total": row.invoice_total,
        "invoice_vat": row.invoice_vat,
        "currency": row.currency,
        "purpose": row.purpose,
    }


def _report_to_dict(row: Report, artifacts: list[ReportArtifact]) -> dict[str, object]:
    try:
        requested_formats = list(json.loads(row.requested_formats_json))
    except Exception:
        requested_formats = []
    try:
        filters = json.loads(row.filters_json)
    except Exception:
        filters = {}

    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "status": row.status,
        "idempotency_key": row.idempotency_key,
        "queue_job_id": row.queue_job_id,
        "error_message": row.error_message,
        "requested_formats": requested_formats,
        "filters": filters,
        "created_at": _iso(row.created_at),
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "artifacts": [
            {
                "id": artifact.id,
                "format": artifact.format,
                "storage_path": artifact.storage_path,
                "bytes": artifact.bytes,
            }
            for artifact in artifacts
        ],
    }


def _provider_to_dict(row: ProviderConfig) -> dict[str, object]:
    try:
        config = json.loads(row.config_json)
    except json.JSONDecodeError:
        logger.warning(
            "Failed to decode provider config JSON for provider_id=%s tenant_id=%s; falling back to empty config.",
            row.id,
            row.tenant_id,
            exc_info=True,
        )
        config = {}
    if isinstance(config, dict):
        config = {
            key: value
            for key, value in config.items()
            if not (isinstance(key, str) and key.startswith("_oauth_"))
        }
    else:
        config = {}

    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "provider_type": row.provider_type,
        "display_name": row.display_name,
        "connection_status": row.connection_status,
        "config": config,
        "token_expires_at": _iso(row.token_expires_at),
        "last_successful_sync_at": _iso(row.last_successful_sync_at),
        "last_error_code": row.last_error_code,
        "last_error_message": row.last_error_message,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def create_app(config: ApiAppConfig | None = None):
    try:
        from fastapi import (  # type: ignore[import-not-found]
            Cookie,
            Depends,
            FastAPI,
            File,
            Header,
            HTTPException,
            Query,
            Request,
            Response,
            Security,
            UploadFile,
        )
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import (
            HTMLResponse,
            JSONResponse,
            PlainTextResponse,
            RedirectResponse,
        )
        from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
        from pydantic import BaseModel
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "FastAPI stack is not installed. Install fastapi and uvicorn to run the SaaS API."
        ) from exc

    cfg = config or ApiAppConfig()
    if not cfg.auth_access_token_secret:
        raise RuntimeError("auth_access_token_secret must be configured.")
    service = _build_service(cfg)
    storage = build_storage(cfg.storage_url)
    metrics = MetricsRegistry()
    app = FastAPI(
        title="Invoices SaaS API",
        version="0.1.0",
        docs_url="/swagger",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    if cfg.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cfg.cors_allow_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )
    app.state.config = asdict(cfg)
    app.state.service = service
    app.state.storage = storage
    app.state.metrics = metrics

    class ParseJobRequest(BaseModel):
        file_ids: list[str]
        debug: bool = False

    class CollectionJobCreateRequest(BaseModel):
        providers: list[str]
        month_scope: str

    class ReportRequest(BaseModel):
        parse_job_ids: list[str] | None = None
        formats: list[str] | None = None
        filters: dict[str, object] | None = None

    class TenantBootstrapRequest(BaseModel):
        name: str

    class TenantFirstUserBootstrapRequest(BaseModel):
        email: str
        password: str
        full_name: str | None = None

    class AuthLoginRequest(BaseModel):
        email: str
        password: str
        tenant_slug: str

    class ProviderCreateRequest(BaseModel):
        provider_type: str
        display_name: str | None = None
        connection_status: str = "disconnected"
        config: object | None = None

    class ProviderUpdateRequest(BaseModel):
        provider_type: str | None = None
        display_name: str | None = None
        connection_status: str | None = None
        config: object | None = None
        token_expires_at: datetime | None = None
        last_successful_sync_at: datetime | None = None
        last_error_code: str | None = None
        last_error_message: str | None = None

    class ProviderOAuthStartRequest(BaseModel):
        redirect_uri: str

    def get_service() -> SaaSService:
        return app.state.service  # type: ignore[no-any-return]

    def get_storage() -> StorageBackend:
        return app.state.storage  # type: ignore[no-any-return]

    def get_metrics() -> MetricsRegistry:
        return app.state.metrics  # type: ignore[no-any-return]

    def get_actor(x_actor: str | None = Header(default=None, alias="X-Actor")) -> str | None:
        return x_actor

    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="ApiKeyAuth")
    bearer_header = HTTPBearer(auto_error=False, scheme_name="BearerAuth")
    control_plane_key_header = APIKeyHeader(
        name="X-Control-Plane-Key",
        auto_error=False,
        scheme_name="ControlPlaneKeyAuth",
    )
    control_plane_api_key = (cfg.control_plane_api_key or "").strip() or None

    def require_control_plane_access(
        x_control_plane_key: str | None = Security(control_plane_key_header),
    ) -> None:
        if control_plane_api_key is None:
            raise HTTPException(status_code=503, detail="control plane is disabled")
        if x_control_plane_key != control_plane_api_key:
            raise HTTPException(status_code=401, detail="invalid control plane key")

    def _auth_error_response(
        request: Request,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": request_id,
                    "details": details or {},
                }
            },
        )

    def _provider_http_exception(exc: ProviderConfigError) -> HTTPException:
        status_by_code = {
            "PROVIDER_NOT_FOUND": 404,
            "PROVIDER_CONFLICT": 409,
            "PROVIDER_VALIDATION_ERROR": 400,
            "PROVIDER_OAUTH_NOT_CONNECTED": 409,
            "PROVIDER_OAUTH_STATE_INVALID": 400,
            "PROVIDER_OAUTH_STATE_EXPIRED": 400,
            "PROVIDER_OAUTH_CONFIG_ERROR": 503,
            "PROVIDER_CONFIG_ERROR": 500,
        }
        return HTTPException(status_code=status_by_code.get(exc.code, 400), detail=exc.message)

    def _collection_http_exception(exc: CollectionJobError) -> HTTPException:
        status_by_code = {
            "COLLECTION_NOT_FOUND": 404,
            "COLLECTION_CONFLICT": 409,
            "COLLECTION_VALIDATION_ERROR": 400,
        }
        return HTTPException(status_code=status_by_code.get(exc.code, 400), detail=exc.message)

    def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
        response.set_cookie(
            key="inv_refresh",
            value=refresh_token,
            httponly=True,
            secure=cfg.auth_cookie_secure,
            samesite="lax",
            path="/auth",
            max_age=cfg.auth_refresh_token_ttl_seconds,
        )

    def _clear_refresh_cookie(response: Response) -> None:
        response.delete_cookie(
            key="inv_refresh",
            path="/auth",
            secure=cfg.auth_cookie_secure,
            httponly=True,
            samesite="lax",
        )

    def _extract_bearer_token(raw_authorization: str | None) -> str | None:
        if raw_authorization is None:
            return None
        scheme, separator, token = raw_authorization.partition(" ")
        if separator != " " or scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="invalid bearer token")
        normalized_token = token.strip()
        if not normalized_token:
            raise HTTPException(status_code=401, detail="missing bearer token")
        return normalized_token

    def _resolve_runtime_tenant_id(
        request: Request,
        *,
        x_api_key: str | None,
        service: SaaSService,
    ) -> str | None:
        api_key_tenant_id: str | None = None
        if x_api_key:
            tenant = service.get_tenant_by_api_key(x_api_key)
            if tenant is None:
                raise HTTPException(status_code=401, detail="invalid API key")
            api_key_tenant_id = tenant.id

        bearer_tenant_id: str | None = None
        access_token = _extract_bearer_token(request.headers.get("Authorization"))
        if access_token is not None:
            try:
                auth_result = service.get_current_user(access_token=access_token)
            except AuthError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
            bearer_tenant_id = auth_result.tenant.id

        if (
            api_key_tenant_id is not None
            and bearer_tenant_id is not None
            and api_key_tenant_id != bearer_tenant_id
        ):
            raise HTTPException(
                status_code=403,
                detail="tenant mismatch between API key and bearer token",
            )
        return bearer_tenant_id or api_key_tenant_id

    def get_tenant_id(
        request: Request,
        x_api_key: str | None = Security(api_key_header),
        service: SaaSService = Depends(get_service),
    ) -> str:
        cached_tenant_id = getattr(request.state, "tenant_id", None)
        if isinstance(cached_tenant_id, str) and cached_tenant_id:
            return cached_tenant_id
        tenant_id = _resolve_runtime_tenant_id(
            request,
            x_api_key=x_api_key,
            service=service,
        )
        if tenant_id is None:
            raise HTTPException(status_code=401, detail="missing API key or bearer token")
        request.state.tenant_id = tenant_id
        return tenant_id

    @app.middleware("http")
    async def request_audit_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        actor = request.headers.get("X-Actor")
        start = time.perf_counter()

        tenant_id: str | None = None
        if request.url.path.startswith("/v1"):
            api_key = request.headers.get("X-API-Key")
            try:
                tenant_id = _resolve_runtime_tenant_id(
                    request,
                    x_api_key=api_key,
                    service=service,
                )
            except HTTPException:
                tenant_id = None
            if tenant_id is not None:
                request.state.tenant_id = tenant_id

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)
            metrics.observe_http(request.method, route_path, 500, duration_ms)

            if tenant_id is not None and request.url.path.startswith("/v1"):
                route = request.scope.get("route")
                route_path = getattr(route, "path", request.url.path)
                event_type = f"api.{_normalize_action(request.method, route_path)}"
                try:
                    service.record_audit_event(
                        tenant_id=tenant_id,
                        event_type=event_type,
                        actor=actor,
                        payload={
                            "request_id": request_id,
                            "method": request.method,
                            "path": request.url.path,
                            "route": route_path,
                            "query": str(request.url.query),
                            "status_code": 500,
                            "duration_ms": duration_ms,
                            "error": exc.__class__.__name__,
                        },
                    )
                except Exception:
                    pass
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        metrics.observe_http(request.method, route_path, response.status_code, duration_ms)

        if tenant_id is not None and request.url.path.startswith("/v1"):
            event_type = f"api.{_normalize_action(request.method, route_path)}"
            try:
                service.record_audit_event(
                    tenant_id=tenant_id,
                    event_type=event_type,
                    actor=actor,
                    payload={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "route": route_path,
                        "query": str(request.url.query),
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    },
                )
            except Exception:
                pass

        return response

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/docs", include_in_schema=False)
    def docs_redirect():
        return RedirectResponse(url="/swagger")

    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint(metrics_registry: MetricsRegistry = Depends(get_metrics)):
        return PlainTextResponse(
            metrics_registry.render_prometheus(), media_type="text/plain; version=0.0.4"
        )

    @app.post("/auth/login")
    def auth_login(
        payload: AuthLoginRequest,
        request: Request,
        response: Response,
        service: SaaSService = Depends(get_service),
    ):
        try:
            auth_result = service.authenticate_user(
                tenant_slug=payload.tenant_slug,
                email=payload.email,
                password=payload.password,
                request_id=getattr(request.state, "request_id", None),
                remote_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("User-Agent"),
            )
        except AuthError as exc:
            return _auth_error_response(
                request,
                status_code=exc.status_code,
                code=exc.code,
                message=exc.message,
            )

        _set_refresh_cookie(response, auth_result.refresh_token)
        return {
            "access_token": auth_result.access_token,
            "token_type": "Bearer",
            "expires_in": auth_result.expires_in,
            "user": {
                "id": auth_result.user.id,
                "email": auth_result.user.email,
                "full_name": auth_result.user.full_name,
                "role": auth_result.membership.role,
                "status": "active" if auth_result.user.is_active else "disabled",
            },
            "tenant": _tenant_to_dict(auth_result.tenant),
            "session": {
                "session_id": auth_result.session.id,
                "access_expires_at": _iso(auth_result.session.access_expires_at),
                "refresh_expires_at": _iso(auth_result.session.refresh_expires_at),
            },
        }

    @app.post("/auth/refresh")
    def auth_refresh(
        request: Request,
        response: Response,
        refresh_token: str | None = Cookie(default=None, alias="inv_refresh"),
        service: SaaSService = Depends(get_service),
    ):
        try:
            auth_result = service.refresh_session(
                refresh_token=refresh_token or "",
                request_id=getattr(request.state, "request_id", None),
            )
        except AuthError as exc:
            return _auth_error_response(
                request,
                status_code=exc.status_code,
                code=exc.code,
                message=exc.message,
            )

        _set_refresh_cookie(response, auth_result.refresh_token)
        return {
            "access_token": auth_result.access_token,
            "token_type": "Bearer",
            "expires_in": auth_result.expires_in,
            "session": {
                "session_id": auth_result.session.id,
                "access_expires_at": _iso(auth_result.session.access_expires_at),
                "refresh_expires_at": _iso(auth_result.session.refresh_expires_at),
            },
        }

    @app.post("/auth/logout", status_code=204)
    def auth_logout(
        request: Request,
        response: Response,
        refresh_token: str | None = Cookie(default=None, alias="inv_refresh"),
        service: SaaSService = Depends(get_service),
    ) -> Response:
        service.revoke_session(
            refresh_token=refresh_token,
            request_id=getattr(request.state, "request_id", None),
        )
        _clear_refresh_cookie(response)
        response.status_code = 204
        return response

    @app.get("/v1/me")
    def get_me(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Security(bearer_header),
        service: SaaSService = Depends(get_service),
    ):
        access_token = credentials.credentials if credentials else ""
        try:
            auth_result = service.get_current_user(access_token=access_token)
        except AuthError as exc:
            return _auth_error_response(
                request,
                status_code=exc.status_code,
                code=exc.code,
                message=exc.message,
            )

        return {
            "user": {
                "id": auth_result.user.id,
                "email": auth_result.user.email,
                "full_name": auth_result.user.full_name,
                "role": auth_result.membership.role,
                "status": "active" if auth_result.user.is_active else "disabled",
            },
            "tenant": _tenant_to_dict(auth_result.tenant),
            "session": {
                "session_id": auth_result.session.id,
                "access_expires_at": _iso(auth_result.session.access_expires_at),
                "refresh_expires_at": _iso(auth_result.session.refresh_expires_at),
            },
        }

    @app.get("/v1/providers")
    def list_providers(
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        items, total = service.list_provider_configs(
            tenant_id=tenant_id, limit=limit, offset=offset
        )
        return {
            "items": [_provider_to_dict(item) for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.post("/v1/providers", status_code=201)
    def create_provider(
        payload: ProviderCreateRequest,
        tenant_id: str = Depends(get_tenant_id),
        actor: str | None = Depends(get_actor),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            item = service.create_provider_config(
                tenant_id=tenant_id,
                provider_type=payload.provider_type,
                display_name=payload.display_name,
                connection_status=payload.connection_status,
                config=payload.config,
                actor=actor,
            )
        except ProviderConfigError as exc:
            raise _provider_http_exception(exc) from exc
        return _provider_to_dict(item)

    @app.patch("/v1/providers/{provider_id}")
    def update_provider(
        provider_id: str,
        payload: ProviderUpdateRequest,
        tenant_id: str = Depends(get_tenant_id),
        actor: str | None = Depends(get_actor),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        updates = payload.model_dump(exclude_unset=True)
        try:
            item = service.update_provider_config(
                tenant_id=tenant_id,
                provider_id=provider_id,
                updates=updates,
                actor=actor,
            )
        except ProviderConfigError as exc:
            raise _provider_http_exception(exc) from exc
        return _provider_to_dict(item)

    @app.delete("/v1/providers/{provider_id}", status_code=204)
    def delete_provider(
        provider_id: str,
        tenant_id: str = Depends(get_tenant_id),
        actor: str | None = Depends(get_actor),
        service: SaaSService = Depends(get_service),
    ) -> Response:
        try:
            service.delete_provider_config(
                tenant_id=tenant_id, provider_id=provider_id, actor=actor
            )
        except ProviderConfigError as exc:
            raise _provider_http_exception(exc) from exc
        return Response(status_code=204)

    @app.post("/v1/providers/{provider_id}/oauth/start")
    def start_provider_oauth(
        provider_id: str,
        payload: ProviderOAuthStartRequest,
        request: Request,
        tenant_id: str = Depends(get_tenant_id),
        actor: str | None = Depends(get_actor),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            result = service.start_provider_oauth(
                tenant_id=tenant_id,
                provider_id=provider_id,
                redirect_uri=payload.redirect_uri,
                actor=actor,
                request_id=getattr(request.state, "request_id", None),
            )
        except ProviderConfigError as exc:
            raise _provider_http_exception(exc) from exc
        return {
            "provider": _provider_to_dict(result.provider),
            "authorization_url": result.authorization_url,
            "state": result.state,
            "state_expires_at": _iso(result.state_expires_at),
        }

    @app.get("/v1/providers/{provider_id}/oauth/callback")
    def complete_provider_oauth_callback(
        provider_id: str,
        request: Request,
        state: str = Query(default=""),
        code: str = Query(default=""),
        tenant_id: str = Depends(get_tenant_id),
        actor: str | None = Depends(get_actor),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            item = service.complete_provider_oauth_callback(
                tenant_id=tenant_id,
                provider_id=provider_id,
                state=state,
                code=code,
                actor=actor,
                request_id=getattr(request.state, "request_id", None),
            )
        except ProviderConfigError as exc:
            raise _provider_http_exception(exc) from exc
        return _provider_to_dict(item)

    @app.post("/v1/providers/{provider_id}/oauth/refresh")
    def refresh_provider_oauth(
        provider_id: str,
        request: Request,
        tenant_id: str = Depends(get_tenant_id),
        actor: str | None = Depends(get_actor),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            item = service.refresh_provider_oauth(
                tenant_id=tenant_id,
                provider_id=provider_id,
                actor=actor,
                request_id=getattr(request.state, "request_id", None),
            )
        except ProviderConfigError as exc:
            raise _provider_http_exception(exc) from exc
        return _provider_to_dict(item)

    @app.post("/v1/providers/{provider_id}/oauth/revoke")
    def revoke_provider_oauth(
        provider_id: str,
        request: Request,
        tenant_id: str = Depends(get_tenant_id),
        actor: str | None = Depends(get_actor),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            item = service.revoke_provider_oauth(
                tenant_id=tenant_id,
                provider_id=provider_id,
                actor=actor,
                request_id=getattr(request.state, "request_id", None),
            )
        except ProviderConfigError as exc:
            raise _provider_http_exception(exc) from exc
        return _provider_to_dict(item)

    @app.post("/v1/providers/{provider_id}/test-connection")
    def test_provider_connection(
        provider_id: str,
        request: Request,
        tenant_id: str = Depends(get_tenant_id),
        actor: str | None = Depends(get_actor),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        request_id = getattr(request.state, "request_id", None)
        try:
            result = service.test_provider_connection(
                tenant_id=tenant_id,
                provider_id=provider_id,
                actor=actor,
                request_id=request_id,
            )
        except ProviderConfigError as exc:
            raise _provider_http_exception(exc) from exc
        return {
            "provider": _provider_to_dict(result.provider),
            "status": result.status,
            "message": result.message,
            "tested_at": _iso(result.tested_at),
            "request_id": request_id,
        }

    @app.post("/v1/collection-jobs", status_code=201)
    def create_collection_job(
        payload: CollectionJobCreateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        tenant_id: str = Depends(get_tenant_id),
        actor: str | None = Depends(get_actor),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            row = service.create_collection_job(
                tenant_id=tenant_id,
                providers=payload.providers,
                month_scope=payload.month_scope,
                idempotency_key=idempotency_key,
                actor=actor,
            )
        except CollectionJobError as exc:
            raise _collection_http_exception(exc) from exc
        return _collection_job_to_dict(row)

    @app.get("/v1/collection-jobs")
    def list_collection_jobs(
        status: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            items, total = service.list_collection_jobs(
                tenant_id=tenant_id,
                status=status,
                limit=limit,
                offset=offset,
            )
        except CollectionJobError as exc:
            raise _collection_http_exception(exc) from exc
        return {
            "items": [_collection_job_to_dict(item) for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.get("/v1/collection-jobs/{collection_job_id}")
    def get_collection_job(
        collection_job_id: str,
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        row = service.get_collection_job(tenant_id=tenant_id, collection_job_id=collection_job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="collection job not found")
        return _collection_job_to_dict(row)

    @app.get("/dashboard", include_in_schema=False)
    def dashboard_page():
        html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Invoices SaaS Dashboard</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; color: #111; }
    h1 { margin: 0 0 12px; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; }
    code { background: #f5f5f5; padding: 2px 4px; border-radius: 4px; }
    .muted { color: #666; font-size: 14px; }
    button { padding: 8px 12px; cursor: pointer; }
    input { padding: 8px; width: 320px; max-width: 100%; }
  </style>
</head>
<body>
  <h1>Invoices SaaS Dashboard</h1>
  <p class="muted">Use your tenant API key to load live summary. API docs: <a href="/swagger">/swagger</a></p>
  <div class="card">
    <input id="apiKey" placeholder="X-API-Key" />
    <button onclick="loadSummary()">Load</button>
    <div id="status" class="muted"></div>
  </div>
  <div id="content"></div>
  <script>
    async function loadSummary() {
      const key = document.getElementById('apiKey').value.trim();
      const status = document.getElementById('status');
      const content = document.getElementById('content');
      if (!key) { status.textContent = 'Missing API key'; return; }
      status.textContent = 'Loading...';
      const res = await fetch('/v1/dashboard/summary', { headers: { 'X-API-Key': key } });
      if (!res.ok) {
        status.textContent = 'Request failed: ' + res.status;
        content.innerHTML = '';
        return;
      }
      const data = await res.json();
      status.textContent = 'OK. Request ID: ' + (res.headers.get('X-Request-ID') || '(none)');
      content.innerHTML = `
        <div class="grid">
          <div class="card"><b>Files</b><div>${data.totals.files}</div></div>
          <div class="card"><b>Parse Jobs</b><div>${data.totals.parse_jobs}</div></div>
          <div class="card"><b>Invoices</b><div>${data.totals.invoices}</div></div>
          <div class="card"><b>Reports</b><div>${data.totals.reports}</div></div>
        </div>
        <div class="card"><b>Parse Status</b><pre>${JSON.stringify(data.parse_jobs_by_status, null, 2)}</pre></div>
        <div class="card"><b>Report Status</b><pre>${JSON.stringify(data.reports_by_status, null, 2)}</pre></div>
        <div class="card"><b>Recent Parse Jobs</b><pre>${JSON.stringify(data.recent_parse_jobs, null, 2)}</pre></div>
        <div class="card"><b>Recent Reports</b><pre>${JSON.stringify(data.recent_reports, null, 2)}</pre></div>
      `;
    }
  </script>
</body>
</html>"""
        return HTMLResponse(html)

    @app.post("/v1/files", status_code=201)
    async def register_file(
        file: UploadFile = File(...),
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
        storage: StorageBackend = Depends(get_storage),
    ) -> dict[str, object]:
        filename = Path(file.filename or "").name
        if not filename:
            raise HTTPException(status_code=400, detail="filename is required")
        mime_type = file.content_type or "application/pdf"
        if "pdf" not in mime_type.lower() and not filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="only PDF uploads are supported")

        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="uploaded file is empty")

        stored_name = f"{uuid4().hex}_{filename}"
        storage_key = f"uploads/{tenant_id}/{stored_name}"
        stored = storage.save_bytes(storage_key, data)

        file_row = service.register_file(
            tenant_id=tenant_id,
            filename=filename,
            storage_path=stored.key,
            mime_type=mime_type,
            content_sha256=stored.sha256,
            bytes_size=stored.size,
        )
        return {
            "id": file_row.id,
            "tenant_id": file_row.tenant_id,
            "filename": file_row.filename,
            "mime_type": file_row.mime_type,
            "bytes": file_row.bytes,
            "content_sha256": file_row.content_sha256,
            "storage_path": file_row.storage_path,
            "status": file_row.status,
        }

    @app.post("/v1/parse-jobs", status_code=202)
    def create_parse_job(
        request: ParseJobRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            job = service.create_parse_job(
                tenant_id=tenant_id,
                file_ids=request.file_ids,
                debug=request.debug,
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _job_to_dict(job)

    @app.get("/v1/parse-jobs/{parse_job_id}")
    def get_parse_job(
        parse_job_id: str,
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        job = service.get_parse_job(tenant_id=tenant_id, parse_job_id=parse_job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="parse job not found")
        return _job_to_dict(job)

    @app.get("/v1/invoices")
    def list_invoices(
        parse_job_id: str | None = Query(default=None),
        vendor: str | None = Query(default=None),
        from_date: date | None = Query(default=None),
        to_date: date | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        items, total = service.list_invoices(
            tenant_id=tenant_id,
            parse_job_id=parse_job_id,
            vendor=vendor,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [_invoice_to_dict(item) for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.get("/v1/invoices/{invoice_id}")
    def get_invoice(
        invoice_id: str,
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        invoice = service.get_invoice(tenant_id=tenant_id, invoice_id=invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="invoice not found")
        return _invoice_to_dict(invoice)

    @app.get("/v1/control-plane/tenants")
    def list_control_plane_tenants(
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        _control_plane: None = Depends(require_control_plane_access),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        tenants, total = service.list_tenants(limit=limit, offset=offset)
        return {
            "items": [_tenant_to_dict(item) for item in tenants],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.post("/v1/control-plane/tenants", status_code=201)
    def create_control_plane_tenant(
        request: TenantBootstrapRequest,
        actor: str | None = Depends(get_actor),
        _control_plane: None = Depends(require_control_plane_access),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        tenant_name = request.name.strip()
        if not tenant_name:
            raise HTTPException(status_code=400, detail="tenant name is required")
        tenant, plain_text_key = service.bootstrap_tenant(name=tenant_name, actor=actor)
        return {
            "tenant": _tenant_to_dict(tenant),
            "api_key": {"plain_text": plain_text_key},
        }

    @app.post("/v1/control-plane/tenants/{tenant_id}/bootstrap-user", status_code=201)
    def bootstrap_control_plane_first_user(
        tenant_id: str,
        request: TenantFirstUserBootstrapRequest,
        actor: str | None = Depends(get_actor),
        _control_plane: None = Depends(require_control_plane_access),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        email = request.email.strip()
        if not email:
            raise HTTPException(status_code=400, detail="email is required")
        if not request.password:
            raise HTTPException(status_code=400, detail="password is required")
        try:
            user, membership = service.bootstrap_tenant_admin_user(
                tenant_id=tenant_id,
                email=email,
                password=request.password,
                full_name=request.full_name,
                actor=actor,
            )
        except ValueError as exc:
            message = str(exc)
            if message == "tenant not found":
                raise HTTPException(status_code=404, detail=message) from exc
            if message == "tenant already has users":
                raise HTTPException(status_code=409, detail=message) from exc
            if message == "password does not match existing user":
                raise HTTPException(status_code=409, detail=message) from exc
            raise HTTPException(status_code=400, detail=message) from exc
        return {
            "tenant_id": tenant_id,
            "user": _user_to_dict(user),
            "membership": _membership_to_dict(membership),
        }

    @app.get("/v1/dashboard/summary")
    def dashboard_summary(
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        return service.dashboard_summary(tenant_id=tenant_id)

    @app.get("/v1/admin/api-keys")
    def list_api_keys(
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        items = service.list_api_keys(tenant_id=tenant_id)
        return {"items": [_api_key_to_dict(item) for item in items], "total": len(items)}

    @app.post("/v1/admin/api-keys", status_code=201)
    def create_api_key(
        tenant_id: str = Depends(get_tenant_id),
        actor: str | None = Depends(get_actor),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        item, plain_text = service.create_api_key(tenant_id=tenant_id, actor=actor)
        return {"api_key": _api_key_to_dict(item), "plain_text": plain_text}

    @app.post("/v1/admin/api-keys/{api_key_id}/rotate")
    def rotate_api_key(
        api_key_id: str,
        tenant_id: str = Depends(get_tenant_id),
        actor: str | None = Depends(get_actor),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            item, plain_text = service.rotate_api_key(
                tenant_id=tenant_id, api_key_id=api_key_id, actor=actor
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"api_key": _api_key_to_dict(item), "plain_text": plain_text}

    @app.post("/v1/admin/api-keys/{api_key_id}/revoke")
    def revoke_api_key(
        api_key_id: str,
        tenant_id: str = Depends(get_tenant_id),
        actor: str | None = Depends(get_actor),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            item = service.revoke_api_key(tenant_id=tenant_id, api_key_id=api_key_id, actor=actor)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"api_key": _api_key_to_dict(item)}

    @app.post("/v1/reports", status_code=202)
    def create_report(
        request: ReportRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            report = service.create_report_job(
                tenant_id=tenant_id,
                parse_job_ids=request.parse_job_ids,
                formats=request.formats,
                filters=request.filters,
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        artifacts = service.list_report_artifacts(tenant_id=tenant_id, report_id=report.id)
        return _report_to_dict(report, artifacts)

    @app.get("/v1/reports")
    def list_reports(
        status: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        reports, total = service.list_reports(
            tenant_id=tenant_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        items = [
            _report_to_dict(
                report, service.list_report_artifacts(tenant_id=tenant_id, report_id=report.id)
            )
            for report in reports
        ]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.get("/v1/reports/{report_id}")
    def get_report(
        report_id: str,
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        report = service.get_report(tenant_id=tenant_id, report_id=report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="report not found")
        artifacts = service.list_report_artifacts(tenant_id=tenant_id, report_id=report.id)
        return _report_to_dict(report, artifacts)

    @app.get("/v1/reports/{report_id}/download")
    def download_report(
        report_id: str,
        format: str = Query(...),
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
        storage: StorageBackend = Depends(get_storage),
    ):
        report = service.get_report(tenant_id=tenant_id, report_id=report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="report not found")
        artifacts = service.list_report_artifacts(tenant_id=tenant_id, report_id=report.id)
        artifact = next((item for item in artifacts if item.format == format), None)
        if artifact is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        from fastapi.responses import FileResponse  # type: ignore[import-not-found]

        artifact_path = storage.resolve_local_path(artifact.storage_path)
        return FileResponse(path=str(artifact_path), filename=artifact_path.name)

    @app.post("/v1/reports/{report_id}/retry", status_code=202)
    def retry_report(
        report_id: str,
        tenant_id: str = Depends(get_tenant_id),
        service: SaaSService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            report = service.retry_report_job(tenant_id=tenant_id, report_id=report_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        artifacts = service.list_report_artifacts(tenant_id=tenant_id, report_id=report.id)
        return _report_to_dict(report, artifacts)

    return app
