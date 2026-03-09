from __future__ import annotations

from pathlib import Path

import pytest

from invplatform.saas.db import build_engine, build_session_factory
from invplatform.saas.models import Base, InvoiceRecord, ParseJobFile
from invplatform.saas.repository import TenantScopedRepository
from invplatform.saas.service import SaaSService
from invplatform.saas.queue import InMemoryJobQueue


def _service(tmp_path: Path) -> SaaSService:
    engine = build_engine(f"sqlite:///{tmp_path / 'saas-repo.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = build_session_factory(engine)
    return SaaSService(session_factory=session_factory, queue=InMemoryJobQueue())


def test_repository_enforces_tenant_filter(tmp_path: Path) -> None:
    service = _service(tmp_path)
    tenant_a, _ = service.bootstrap_tenant("Tenant A")
    tenant_b, _ = service.bootstrap_tenant("Tenant B")

    with service.session_factory() as session:
        session.add(
            InvoiceRecord(
                tenant_id=tenant_a.id,
                parse_job_id="a-job",
                vendor="A",
                file_name="a.pdf",
                invoice_number="a1",
                invoice_total=1.0,
                invoice_vat=0.17,
                purpose="A",
                raw_json="{}",
            )
        )
        session.add(
            InvoiceRecord(
                tenant_id=tenant_b.id,
                parse_job_id="b-job",
                vendor="B",
                file_name="b.pdf",
                invoice_number="b1",
                invoice_total=2.0,
                invoice_vat=0.34,
                purpose="B",
                raw_json="{}",
            )
        )
        session.commit()

    with service.session_factory() as session:
        repo_a = TenantScopedRepository(session, tenant_a.id)
        rows_a = repo_a.list(InvoiceRecord)
        assert len(rows_a) == 1
        assert rows_a[0].vendor == "A"

        repo_b = TenantScopedRepository(session, tenant_b.id)
        rows_b = repo_b.list(InvoiceRecord)
        assert len(rows_b) == 1
        assert rows_b[0].vendor == "B"


def test_repository_raises_for_models_without_tenant_id(tmp_path: Path) -> None:
    service = _service(tmp_path)
    tenant, _ = service.bootstrap_tenant("Tenant A")
    with service.session_factory() as session:
        repo = TenantScopedRepository(session, tenant.id)
        with pytest.raises(ValueError):
            repo.list(ParseJobFile)
