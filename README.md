# Invoices Platform

Monorepo for invoice discovery, PDF collection, and invoice reporting across Gmail and Microsoft Graph.

## What Is Implemented

- Gmail invoice discovery and PDF download (`invplatform.cli.gmail_invoice_finder`)
- Microsoft Graph invoice discovery and PDF download (`invplatform.cli.graph_invoice_finder`)
- Monthly orchestration across providers with merge + dedup (`invplatform.cli.monthly_invoices`)
- PDF quarantine utility for non-invoice files (`invplatform.cli.quarantine_invoices`)
- Invoice parsing/report generation to JSON/CSV/Summary CSV/PDF (`invplatform.cli.invoices_report`)
- SaaS skeleton foundations (Week 2+): SQLAlchemy models, API/worker skeleton, Alembic baseline, and pluggable storage adapters (local/S3)
- SaaS control-plane demo endpoints for tenant bootstrap/listing (`/v1/control-plane/tenants`)
- PDF report enhancements:
  - bilingual-safe rendering (Hebrew + English)
  - vendor grouping and optional vendor subtotal rows
  - configurable subtotal behavior (on/off, skip single-invoice vendors)
- Duplicate removal utility script (`scripts/remove_duplicate_invoices.py`)
- Minimal Go API service (`/healthz`) in `apps/api-go`
- Local dev stack via Docker Compose including `api-go`, `workers-py`, `saas-api`, `saas-rq-worker`, `db`, `mq`, `redis`, and `n8n`

## Documentation Map

- `README.md` (this file): project overview + quick start + workflow map.
- `docs/USAGE.md`: full command reference and how-to usage for all current functionality.
- `docs/PRD_V1_SAAS.md`: Week 1 SaaS MVP product requirements and acceptance criteria.
- `docs/ARCHITECTURE.md`: Week 1 SaaS HLD, domain model, and component boundaries.
- `docs/FRONTEND_CONVERSION_BACKLOG.md`: KISS frontend conversion plan from epics to sprint-ready tasks.
- `docs/FRONTEND_GITHUB_ISSUES.md`: prefilled GitHub issue blocks for every FE/BE task in the frontend backlog.
- `docs/GITHUB_PROJECT_FIELD_MAPPING.md`: GitHub Project v2 field schema (`Status/Owner/Week`) and owner assignment mapping.
- `docs/FRONTEND_PARALLEL_EXECUTION_MATRIX.md`: resource-loaded 10-week parallel delivery matrix with day-level assignments by role.
- `docs/FRONTEND_WEEK1_EXECUTION_PLAN.md`: day-by-day Week 1 execution sequence with owners, checkpoints, and exit criteria.
- `docs/FRONTEND_WEEK2_EXECUTION_PLAN.md`: day-by-day Week 2 auth execution sequence (`BE-001`, `FE-101..FE-104`).
- `docs/FRONTEND_WEEK3_EXECUTION_PLAN.md`: day-by-day Week 3 provider execution sequence (`BE-101`, `BE-102`, `FE-201..FE-203`).
- `docs/FRONTEND_WEEK4_EXECUTION_PLAN.md`: day-by-day Week 4 collection run execution sequence (`BE-201`, `FE-301`, `FE-302`).
- `docs/FRONTEND_WEEK5_EXECUTION_PLAN.md`: day-by-day Week 5 orchestration/retry execution sequence (`BE-202`, `FE-303`, `FE-304`).
- `docs/FRONTEND_WEEK6_EXECUTION_PLAN.md`: day-by-day Week 6 report UX execution sequence (`FE-401..FE-405`).
- `docs/FRONTEND_WEEK7_EXECUTION_PLAN.md`: day-by-day Week 7 scheduling baseline execution sequence (`BE-301`, `FE-501`, `FE-502`).
- `docs/FRONTEND_WEEK8_EXECUTION_PLAN.md`: day-by-day Week 8 scheduling runtime execution sequence (`BE-302`, `FE-503`).
- `docs/FRONTEND_WEEK9_EXECUTION_PLAN.md`: day-by-day Week 9 observability/traceability execution sequence (`BE-401`, `FE-601..FE-605`).
- `docs/FRONTEND_WEEK10_EXECUTION_PLAN.md`: day-by-day Week 10 quality/release hardening execution sequence (`FE-701..FE-705`).
- `docs/STAKEHOLDER_DEMO_RUNBOOK.md`: complete script for stakeholder demo (control-plane + runtime alignment).
- `docs/ADR/`: architecture decision records for SaaS conversion path.
- `docs/META_BILLING_GRAPH_API_EXPLORER.md`: ready-to-paste Graph API Explorer URLs for Meta billing diagnostics.
- `integrations/openapi/invoices.yaml`: SaaS API v1 skeleton contract for files, parse jobs, invoices, and reports.
- `integrations/openapi/saas-openapi.v0.1.0.json`: generated OpenAPI snapshot from the current FastAPI SaaS app.

## Documentation Approach

The docs structure in this repo follows these principles:

- Quick orientation in `README.md`, detailed how-to/reference in `docs/USAGE.md`.
- Task-first command examples (copy/paste ready).
- Explicitly separate current behavior from future/planned API scope.

References used for this structure:

- Diataxis framework: <https://diataxis.fr/>
- Google developer documentation style guide: <https://developers.google.com/style>
- Write the Docs style/principles:
  - <https://www.writethedocs.org/guide/writing/style-guides.html>
  - <https://www.writethedocs.org/guide/writing/docs-principles.html>

## Quick Start

### Prerequisites

- Python 3.11+
- Go 1.22+ (for `api-go`)
- Docker + Docker Compose (optional, for full local stack)

### Install dependencies (local Python workflow)

```bash
pip install -r requirements.txt
```

### Run tests

```bash
make test
```

### Run main workflows

```bash
# Gmail finder
make run-gmail START_DATE=2026-01-01 END_DATE=2026-02-01

# Graph finder
make run-graph START_DATE=2026-01-01 END_DATE=2026-02-01 GRAPH_CLIENT_ID=<your-client-id>

# Monthly orchestration (current month by default)
make run-monthly GRAPH_CLIENT_ID=<your-client-id>

# Parse invoices + build reports (JSON/CSV/summary/PDF)
make run-report REPORT_INPUT_DIR=invoices/invoices_01_2026

# Quarantine likely non-invoice PDFs
make quarantine
```

For complete options and examples, use `docs/USAGE.md`.

## Key Outputs

- Provider fetch outputs:
  - `invoices/invoices_gmail_MM_YYYY`
  - `invoices/invoices_outlook_MM_YYYY`
- Consolidated monthly outputs:
  - `invoices/invoices_MM_YYYY`
  - `invoices/invoices_MM_YYYY/run_summary.json`
- Report outputs:
  - `report-*.json`, `report-*.csv`, `report-*.summary.csv`, `report-*.pdf` (or custom output paths)

## API Status (Current)

- Implemented in Go:
  - `GET /healthz` -> `200 ok`
- Implemented in Python SaaS API (`make run-saas-api`):
  - `GET /swagger` -> interactive Swagger UI
  - `GET /openapi.json` -> generated OpenAPI schema
  - `make run-saas-openapi-export` -> versioned schema snapshot on disk
  - `GET/POST /v1/control-plane/tenants` -> platform bootstrap/list tenants (requires `X-Control-Plane-Key`)
  - `GET /dashboard` -> tenant-aware summary dashboard UI
  - `GET /metrics` -> Prometheus text metrics
- Not yet implemented in current Go handler:
  - the full invoice CRUD suggested by `integrations/openapi/invoices.yaml`

## Repo Layout

```text
invoices-platform/
├─ apps/
│  ├─ api-go/
│  └─ workers-py/
├─ docs/
│  └─ USAGE.md
├─ deploy/
├─ integrations/
├─ scripts/
├─ invoices/
└─ README.md
```

## Notes

- `archive/` contains historical finder scripts kept for comparison/debugging. Current supported entry points are under `apps/workers-py/src/invplatform/cli`.
- `docs/ONBOARDING.md`, `docs/ARCHITECTURE.md`, and `docs/CONTRIBUTING.md` are currently placeholders.
