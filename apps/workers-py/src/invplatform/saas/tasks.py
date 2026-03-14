from __future__ import annotations

import os

from .db import build_engine, build_session_factory
from .models import Base
from .worker import (
    run_collection_job,
    run_parse_job,
    run_report_job,
    run_report_retention_cleanup,
)


def _session_factory_from_env(database_url: str | None = None):
    url = database_url or os.environ.get("SAAS_DATABASE_URL") or "sqlite:///./invoices_saas.db"
    engine = build_engine(url)
    Base.metadata.create_all(bind=engine)
    return build_session_factory(engine)


def run_parse_job_task(payload: dict[str, str], database_url: str | None = None) -> str:
    parse_job_id = payload["parse_job_id"]
    session_factory = _session_factory_from_env(database_url)
    status = run_parse_job(session_factory=session_factory, parse_job_id=parse_job_id)
    return status.value


def run_collection_job_task(payload: dict[str, str], database_url: str | None = None) -> str:
    collection_job_id = payload["collection_job_id"]
    session_factory = _session_factory_from_env(database_url)
    status = run_collection_job(
        session_factory=session_factory,
        collection_job_id=collection_job_id,
    )
    return status.value


def run_report_job_task(payload: dict[str, str], database_url: str | None = None) -> str:
    report_id = payload["report_id"]
    session_factory = _session_factory_from_env(database_url)
    status = run_report_job(session_factory=session_factory, report_id=report_id)
    return status.value


def run_report_retention_cleanup_task(
    payload: dict[str, str] | None = None,
    database_url: str | None = None,
) -> int:
    session_factory = _session_factory_from_env(database_url)
    payload = payload or {}
    retention_days = int(payload.get("retention_days", "30"))
    return run_report_retention_cleanup(
        session_factory=session_factory, retention_days=retention_days
    )
