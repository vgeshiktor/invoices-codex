from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria


class TenantGuardError(RuntimeError):
    """Raised when tenant-scoped reads execute without tenant context."""


@lru_cache(maxsize=1)
def _tenant_scoped_models() -> tuple[type[object], ...]:
    from .models import (
        AuthSession,
        AuditEvent,
        IdempotencyRecord,
        InvoiceFile,
        InvoiceRecord,
        ParseJob,
        ProviderConfig,
        Report,
        ReportArtifact,
        TenantMembership,
    )

    return (
        InvoiceFile,
        ParseJob,
        InvoiceRecord,
        ProviderConfig,
        Report,
        ReportArtifact,
        AuditEvent,
        IdempotencyRecord,
        TenantMembership,
        AuthSession,
    )


@lru_cache(maxsize=1)
def _tenant_guard_listener_installed() -> bool:
    @event.listens_for(Session, "do_orm_execute", propagate=True)
    def _enforce_tenant_scope(orm_execute_state):  # type: ignore[no-untyped-def]
        if not orm_execute_state.is_select:
            return

        session = orm_execute_state.session
        if not session.info.get("enforce_tenant_guard", False):
            return
        if session.info.get("disable_tenant_guard", False):
            return
        if orm_execute_state.execution_options.get("skip_tenant_guard", False):
            return

        statement = orm_execute_state.statement
        model_entities: list[type[object]] = []
        for desc in getattr(statement, "column_descriptions", []):
            entity = desc.get("entity")
            if isinstance(entity, type):
                model_entities.append(entity)

        tenant_models = _tenant_scoped_models()
        touches_tenant_model = any(entity in tenant_models for entity in model_entities)
        if not touches_tenant_model:
            return

        tenant_id = session.info.get("tenant_id")
        if not tenant_id:
            raise TenantGuardError(
                "Tenant context required for tenant-scoped query. "
                "Set session.info['tenant_id'] or disable guard explicitly."
            )

        filtered_stmt = statement
        for model in tenant_models:
            filtered_stmt = filtered_stmt.options(
                with_loader_criteria(
                    model,
                    lambda cls: cls.tenant_id == tenant_id,
                    include_aliases=True,
                )
            )
        orm_execute_state.statement = filtered_stmt

    return True


def build_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def build_session_factory(
    engine: Engine, enforce_tenant_guard: bool = False
) -> sessionmaker[Session]:
    _tenant_guard_listener_installed()
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
        info={"enforce_tenant_guard": enforce_tenant_guard},
    )


def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
