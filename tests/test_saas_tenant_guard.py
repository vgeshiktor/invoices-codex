from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from invplatform.saas.db import TenantGuardError, build_engine, build_session_factory
from invplatform.saas.models import Base, InvoiceRecord, Tenant


def test_tenant_guard_blocks_tenantless_scoped_select(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'guard.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = build_session_factory(engine, enforce_tenant_guard=True)

    with session_factory() as session:
        t1 = Tenant(name="A")
        t2 = Tenant(name="B")
        session.add(t1)
        session.add(t2)
        session.flush()
        session.add(
            InvoiceRecord(
                tenant_id=t1.id,
                parse_job_id="p1",
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
                tenant_id=t2.id,
                parse_job_id="p2",
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

    with session_factory() as session:
        with pytest.raises(TenantGuardError):
            session.execute(select(InvoiceRecord)).scalars().all()


def test_tenant_guard_auto_filters_by_session_tenant(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'guard2.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = build_session_factory(engine, enforce_tenant_guard=True)

    with session_factory() as session:
        t1 = Tenant(name="A")
        t2 = Tenant(name="B")
        session.add(t1)
        session.add(t2)
        session.flush()
        session.add(
            InvoiceRecord(
                tenant_id=t1.id,
                parse_job_id="p1",
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
                tenant_id=t2.id,
                parse_job_id="p2",
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
        session.info["tenant_id"] = t1.id
        rows = list(session.execute(select(InvoiceRecord)).scalars().all())
        assert len(rows) == 1
        assert rows[0].vendor == "A"
