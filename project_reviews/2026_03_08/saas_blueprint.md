# SaaS Conversion Blueprint (Target State)

## Product Goal
Convert the current local invoice extraction toolchain into a multi-tenant SaaS with:
- Secure mailbox integrations
- Reliable asynchronous processing
- Searchable invoice system of record
- API + UI product surfaces
- Billing, observability, and compliance-ready controls

## Target Architecture

## 1) Control Plane (Go)
- Responsibilities:
  - Tenant/workspace lifecycle
  - OAuth connection management (Gmail/Graph)
  - User authn/authz + RBAC
  - Job submission/status APIs
  - Webhooks/API tokens/integration settings
- Initial APIs:
  - `POST /v1/connections/google`
  - `POST /v1/connections/microsoft`
  - `POST /v1/jobs/invoice-ingest`
  - `GET /v1/jobs/{id}`
  - `GET /v1/invoices`
  - `GET /v1/invoices/{id}`

## 2) Data Plane (Python Workers)
- Responsibilities:
  - Pull provider messages incrementally
  - Download attachments/linked PDFs
  - Parse and normalize invoice fields
  - Emit confidence + validation signals
  - Persist outputs/events
- Execution model:
  - Queue-driven jobs (RabbitMQ) with explicit retries and dead-letter queues
  - Idempotent stage transitions keyed by `(tenant_id, provider_message_id, attachment_hash)`

## 3) Data Layer
- Postgres as canonical invoice metadata store.
- Object storage (S3-compatible) for raw PDFs + parsing artifacts.
- Suggested core tables:
  - `tenants`, `users`, `memberships`
  - `mail_connections`
  - `ingest_jobs`, `ingest_attempts`
  - `documents`
  - `invoices`
  - `invoice_line_items` (optional phase 2)
  - `audit_log`

## 4) Multi-Tenancy Model
- Phase 1: Shared database with strict `tenant_id` boundaries at every table.
- Enforce at API/service layer first; add Postgres RLS once query paths are stable.
- Phase 2: Optional tenant-level data partitioning for enterprise workloads.

## 5) Security + Compliance Baseline
- Encrypt OAuth refresh tokens and secrets (KMS-backed key wrapping).
- Signed, time-bound download URLs for stored artifacts.
- Audit log for critical actions:
  - Connection create/revoke
  - Manual edits
  - Exports/webhook deliveries
- Compliance-ready controls:
  - Data retention policies
  - Soft delete + purge jobs
  - Access review trails

## 6) Observability + Reliability
- SLOs:
  - Ingest success rate
  - Job latency (P50/P95)
  - Parse confidence distribution
- Instrumentation:
  - Structured logs with `tenant_id`, `job_id`, `message_id`
  - Metrics for retries, DLQ counts, parse failures
  - Trace IDs propagated across control/data plane boundaries

## Migration Strategy (Non-Big-Bang)

## Phase A - Harden Existing Monolith CLIs
- Refactor shared logic into composable services without changing behavior.
- Keep CLI entrypoints as adapters.

## Phase B - Introduce Persistence and Job Queue
- Store outputs to DB/object storage in parallel with filesystem outputs.
- Route monthly orchestrations through queue jobs.

## Phase C - Activate Product APIs
- Expose read APIs over persisted data.
- Add dashboard MVP (invoice list/detail/filter/export).

## Phase D - SaaS Features
- Tenant billing + plan limits.
- Webhooks and ERP connectors.
- Human-in-the-loop review queue for low-confidence parses.

## Non-Goals for Initial SaaS Cut
- Perfect parser generalization across all vendor formats.
- Full ERP connector catalog.
- Cross-region active/active deployment.
