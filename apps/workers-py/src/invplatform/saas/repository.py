from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


class TenantScopedRepository:
    """Repository guardrail enforcing tenant-scoped queries."""

    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def _tenant_clause(self, model: type[Any]) -> Any:
        tenant_column = getattr(model, "tenant_id", None)
        if tenant_column is None:
            raise ValueError(f"model {model.__name__} is missing tenant_id for scoped query")
        return tenant_column == self.tenant_id

    def one_or_none(self, model: type[Any], *filters: Any) -> Any | None:
        stmt = select(model).where(self._tenant_clause(model), *filters)
        return self.session.execute(stmt).scalar_one_or_none()

    def list(
        self,
        model: type[Any],
        *filters: Any,
        order_by: list[Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Any]:
        stmt = select(model).where(self._tenant_clause(model), *filters)
        if order_by:
            stmt = stmt.order_by(*order_by)
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def count(self, model: type[Any], *filters: Any) -> int:
        stmt = select(func.count()).select_from(model).where(self._tenant_clause(model), *filters)
        return int(self.session.execute(stmt).scalar_one())
