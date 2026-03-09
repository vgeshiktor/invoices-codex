# PRD v1: Invoices Platform SaaS MVP

Date: 2026-03-08
Owner: Product + Engineering

## 1. Problem Statement

Finance operators and founders spend too much manual effort collecting invoice PDFs, extracting structured data, and producing monthly reports. Current scripts work for a single operator workflow, but are not packaged as a reusable multi-tenant product.

## 2. Target User (ICP)

- Primary: SMB finance operator or founder (1-20 finance users) handling recurring vendor invoices.
- Secondary: bookkeeping/accounting service teams managing multiple client entities.

## 3. Outcome and Success Metrics

Business outcomes:
- Reduce manual invoice processing and reporting time.
- Enable tenant onboarding without custom engineering.

MVP success metrics:
- Time to first report: <= 30 minutes from tenant creation.
- Parse success rate: >= 95% non-fatal completion per job.
- Accuracy proxy: <= 2% manual correction rate on sampled invoices.
- Reliability: failed job rate < 3% weekly.

## 4. Scope Box (8-week MVP)

In scope:
- Tenant + API key management (basic admin flow).
- Upload PDFs.
- Async parse jobs using existing parser domain.
- Invoice list/filter APIs.
- Async report generation (JSON/CSV/Summary CSV/PDF).
- Basic audit events and observability.

Out of scope:
- Billing/subscription engine.
- Rich web frontend (API-first MVP).
- Custom extraction rule editor.
- Complex OCR pipeline for poor scans.
- Multi-region or enterprise compliance programs.

Constraints:
- Keep CLI behavior backward compatible.
- Reuse existing parser/reporting usecases.
- Keep architecture simple: one API service + one worker + Postgres + Redis.

## 5. Functional Requirements

FR-1 Tenant bootstrap:
- Admin can create a tenant and issue API keys.

FR-2 File upload:
- Client uploads one or more PDF files; system validates and stores metadata.

FR-3 Parse submission:
- Client creates parse job from uploaded file IDs.

FR-4 Parse status:
- Client can retrieve parse job status and failure reasons.

FR-5 Invoice retrieval:
- Client can list invoice records with basic filters (date range, vendor, job).

FR-6 Report submission:
- Client creates report job using filters or parse-job scope.

FR-7 Report retrieval:
- Client reads report status and downloads generated artifacts.

FR-8 Auditing:
- Security-sensitive actions create audit events.

## 6. Non-Functional Requirements (NFR)

- Multi-tenancy: strict tenant data isolation.
- Performance: parse p95 <= 5 minutes for 100 typical PDFs.
- Reliability: retries for transient worker failures.
- Security: API keys hashed at rest; secrets never committed.
- Operability: health/readiness probes and structured logs.
- Compatibility: no behavioral regression for existing CLI report paths.

## 7. User Journeys + Acceptance Criteria

### Journey A: Upload and Parse

Given a valid tenant API key
When client uploads PDFs and submits a parse job
Then job transitions `queued -> running -> succeeded|failed`
And invoice records are queryable by tenant.

### Journey B: Generate Report

Given parsed invoice records exist
When client creates report job
Then JSON/CSV/Summary CSV/PDF artifacts are produced
And client can retrieve report metadata and download artifacts.

### Journey C: Tenant Isolation

Given two tenants exist
When tenant A calls any list/get endpoint
Then tenant A never sees tenant B records.

### Journey D: Failure Handling

Given malformed or unsupported PDFs in a parse job
When worker processes job
Then job records failures clearly without corrupting other records
And API returns actionable status details.

## 8. MVP Milestones

- M1 (Week 1): PRD/HLD/ADRs/OpenAPI skeleton approved.
- M2 (Weeks 2-3): Walking skeleton (`upload -> parse -> list`) in staging.
- M3 (Weeks 4-6): Report job pipeline + artifact download.
- M4 (Weeks 7-8): Hardening, observability, pilot onboarding.

## 9. Risks and Mitigations

- Parser edge cases degrade trust:
  - Mitigation: regression fixtures and deterministic tests per vendor class.
- Queue failures or stuck jobs:
  - Mitigation: retries, dead-letter policy, queue depth alerts.
- Tenant isolation bug:
  - Mitigation: mandatory tenant filter guardrails + integration tests.
