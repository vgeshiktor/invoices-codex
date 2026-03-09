# ADR 0002: Shared Postgres with `tenant_id` Isolation

- Status: Accepted
- Date: 2026-03-08

## Context

SaaS MVP needs multi-tenancy without high infrastructure complexity. DB-per-tenant increases operational overhead and migration complexity early.

## Decision

Use one shared Postgres database. Every tenant-owned table includes `tenant_id`, with:
- Required tenant filters in repository/data-access layer.
- Composite indexes that start with `tenant_id` for high-cardinality queries.
- Automated tests for cross-tenant isolation.

## Consequences

Positive:
- Simple operations and migrations.
- Faster MVP delivery.
- Lower infra costs in early stages.

Negative:
- Isolation relies on application correctness.
- Requires strict query review discipline and test coverage.
