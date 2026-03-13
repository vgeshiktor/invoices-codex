# Invoices Platform SaaS Architecture (Week 1 HLD)

## 1. Objective

Convert the existing invoice automation toolchain into a multi-tenant SaaS service while preserving current parsing behavior and CLI compatibility.

This document is the Week 1 High-Level Design (HLD) baseline for MVP implementation.

## 2. Scope Boundary (8-week MVP)

In scope:
- Tenant-scoped API access via API keys
- File upload, parse jobs, invoice listing, report generation
- Async processing for parsing and report builds
- JSON/CSV/Summary CSV/PDF artifacts
- Audit events and basic operational telemetry

Out of scope:
- Self-serve billing and subscription management
- Advanced OCR for low-quality scans
- Custom rule-builder UI per customer
- Multi-region deployment

## 3. Domain Model

### 3.1 Core Entities

- `Tenant`: organization boundary for all data and quotas.
- `ApiKey`: tenant-scoped credentials (hashed at rest).
- `InvoiceFile`: uploaded file metadata and storage location.
- `ParseJob`: async request to parse one or more files.
- `InvoiceRecord`: normalized invoice row produced by parser domain.
- `Report`: async generated artifact bundle from selected records/jobs.
- `AuditEvent`: immutable security and product audit trail.

### 3.2 Relationships

- One `Tenant` owns many `ApiKey`, `InvoiceFile`, `ParseJob`, `InvoiceRecord`, `Report`, `AuditEvent`.
- One `ParseJob` references many `InvoiceFile`; produces many `InvoiceRecord`.
- One `Report` references a set of invoice records (directly or by filter scope).

### 3.3 Lifecycles

- `ParseJob.status`: `queued -> running -> succeeded | failed`.
- `Report.status`: `queued -> running -> succeeded | failed`.
- `InvoiceFile.status`: `uploaded -> validated -> parsed | rejected`.

## 4. System Components

1. `API Service` (FastAPI):
   - Authentication and authorization
   - Request validation
   - Job submission and status/read APIs
   - Signed/authenticated artifact download orchestration

2. `Worker Service` (Python worker with Redis queue):
   - Executes parse and report jobs
   - Reuses `invplatform.usecases` domain modules
   - Persists outputs to DB and artifact storage

3. `Postgres`:
   - Multi-tenant metadata and business records
   - Job states and idempotency records
   - Audit events

4. `Redis`:
   - Queue broker and transient coordination

5. `Object Storage`:
   - Raw uploaded PDFs
   - Generated report artifacts
   - Local filesystem in dev, S3-compatible in production

## 5. Request and Processing Flows

### 5.1 Parse Flow (Happy Path)

1. Client uploads PDFs (`POST /v1/files`).
2. Client requests parse (`POST /v1/parse-jobs`).
3. API validates request, writes `ParseJob(queued)`, enqueues task.
4. Worker loads files, calls `report_pipeline.parse_paths(...)`.
5. Worker stores `InvoiceRecord` rows and marks job `succeeded`.
6. Client polls `GET /v1/parse-jobs/{id}` and fetches `GET /v1/invoices`.

### 5.2 Report Flow

1. Client requests report (`POST /v1/reports`) using filters or job IDs.
2. API creates `Report(queued)` and enqueues report task.
3. Worker generates JSON/CSV/Summary CSV/PDF outputs.
4. Worker writes artifact metadata and marks report `succeeded`.
5. Client fetches metadata (`GET /v1/reports/{id}`) and downloads artifact.

## 6. Security Model (MVP)

- Auth: tenant-scoped API key in `X-API-Key`.
- Authorization: all DB queries must include `tenant_id`.
- Runtime guard: API DB sessions enforce tenant context at ORM level; tenant-scoped reads without context raise errors.
- Secrets: no plaintext keys in DB; store only key hashes and prefixes.
- Auditing: upload, job submit, report create/download, key lifecycle actions.

## 6.1 Provider OAuth Lifecycle (Week 3 Extension)

- Provider integrations are tenant-scoped records (`saas_provider_configs`) with one row per `(tenant_id, provider_type)`.
- OAuth lifecycle endpoints are tenant-scoped:
  - `POST /v1/providers/{provider_id}/oauth/start`
  - `GET /v1/providers/{provider_id}/oauth/callback`
  - `POST /v1/providers/{provider_id}/oauth/refresh`
  - `POST /v1/providers/{provider_id}/oauth/revoke`
- Temporary OAuth callback state is persisted in internal provider config keys and consumed during callback.
- OAuth token fields are stored only in encrypted-token columns and never returned via API responses.
- OAuth state transitions emit audit events with request metadata for traceability.

## 7. NFR Baseline

- Availability target: 99.5% monthly (MVP).
- Parse latency target: p95 <= 5 minutes for 100 typical PDFs per parse job.
- Data durability: DB backups daily, artifact storage versioning enabled.
- Observability: structured logs and metrics for request/job lifecycle.

## 8. Key Tradeoffs

- Single backend + worker keeps complexity low; defer microservices split.
- API key auth is fastest MVP path; defer SSO/OIDC to v2.
- Shared DB with strict tenant filters is simpler than DB-per-tenant.
- Async jobs for heavy parsing/reporting avoid API timeouts and retries storms.

## 9. Implementation Boundaries

- Domain parsing behavior remains in `apps/workers-py/src/invplatform/usecases`.
- CLI remains supported and backward compatible.
- New SaaS modules should call usecases, not duplicate parser logic.
