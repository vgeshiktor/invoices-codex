# Missing Capabilities + Execution Backlog

## Summary of Missing Pieces
- No production API layer for invoice domain operations
- No tenant/auth model
- No persistent invoice/document storage model
- No queue-driven job processing despite queue infra presence
- No robust CI quality gates for the real runtime/test matrix
- No explicit observability, SLOs, or incident/runbook model
- No billing/metering
- No compliance controls (audit, retention, access review)

## Prioritized Backlog

1. P0 - Implement domain persistence schema (Postgres + migrations)
- Outcome: invoices/documents/jobs become queryable and durable
- Acceptance:
  - Migrations for `tenants`, `mail_connections`, `documents`, `invoices`, `ingest_jobs`
  - Worker writes records transactionally with idempotency keys

2. P0 - Build minimal control-plane API in `api-go`
- Outcome: external system can create jobs and retrieve invoices
- Acceptance:
  - `POST /v1/jobs/invoice-ingest`
  - `GET /v1/jobs/{id}`
  - `GET /v1/invoices`
  - `GET /v1/invoices/{id}`

3. P0 - Refactor provider CLIs into reusable services
- Outcome: same logic callable by queue workers and CLI wrappers
- Acceptance:
  - Shared provider interfaces in `usecases/` and `adapters/`
  - CLI files become thin argument/IO adapters

4. P0 - Fix CI and dependency determinism
- Outcome: trustworthy green builds
- Acceptance:
  - CI fails on dependency install errors
  - CI runs root `tests/`
  - One dependency source-of-truth with pinned lock file
  - Lint runs without auto-fix in CI

5. P1 - Queue-native execution
- Outcome: scalable retries and backpressure handling
- Acceptance:
  - RabbitMQ queue + DLQ for ingest/parse stages
  - Retry policy with max attempts and reason codes

6. P1 - Observability baseline
- Outcome: measurable reliability and diagnosability
- Acceptance:
  - Structured logs with correlation IDs
  - Metrics dashboard for ingest success, retries, parser confidence
  - Alerting for sustained job failure or DLQ growth

7. P1 - Tenant identity and authorization
- Outcome: secure multi-tenant SaaS foundation
- Acceptance:
  - Workspace membership model
  - API auth middleware (JWT/session)
  - Tenant isolation checks for all read/write paths

8. P2 - Human-in-the-loop review queue
- Outcome: safe handling of low-confidence parsing
- Acceptance:
  - Mark records as `needs_review` based on confidence/rules
  - Reviewer can correct fields and approve
  - Audit trail captures change history

9. P2 - Metering and billing integration
- Outcome: monetization and plan enforcement
- Acceptance:
  - Usage events emitted per processed invoice
  - Plan limits and overage policy enforced

10. P2 - Compliance controls
- Outcome: enterprise onboarding readiness
- Acceptance:
  - Data retention settings per tenant
  - Export/delete workflows
  - Immutable audit logs for high-risk actions

## What Was Added in This Review
- A complete dated review package:
  - `project_reviews/2026_03_08/task.md`
  - `project_reviews/2026_03_08/review.md`
  - `project_reviews/2026_03_08/saas_blueprint.md`
  - `project_reviews/2026_03_08/missing_capabilities_backlog.md`
