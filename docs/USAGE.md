# Usage Guide

This guide documents all currently implemented user-facing functionality in this repository.

## 1. Setup

### 1.1 Python dependencies

```bash
pip install -r requirements.txt
```

### 1.2 Optional: run full local stack

```bash
make dev
```

Services in `deploy/compose/docker-compose.dev.yml`:
- `api-go` on `:8080`
- `workers-py`
- `db` (Postgres) on `:5432`
- `mq` (RabbitMQ) on `:5672` and management UI on `:15672`
- `n8n` on `:5678`

### 1.3 Authentication files

- Gmail finder expects OAuth files:
  - `credentials.json`
  - `token.json` (created after first auth flow)
- Graph finder requires `--client-id` (or `GRAPH_CLIENT_ID` for monthly orchestration).

## 2. Command Matrix

| Goal | Make target | Direct CLI |
|---|---|---|
| Find/download Gmail invoices | `make run-gmail ...` | `python -m invplatform.cli.gmail_invoice_finder ...` |
| Find/download Outlook/Graph invoices | `make run-graph ...` | `python -m invplatform.cli.graph_invoice_finder ...` |
| Run both providers for one month + consolidate | `make run-monthly ...` | `python -m invplatform.cli.monthly_invoices ...` |
| Parse PDFs and generate report files | `make run-report ...` | `python -m invplatform.cli.invoices_report ...` |
| Move likely non-invoice PDFs to quarantine | `make quarantine` | `python -m invplatform.cli.quarantine_invoices ...` |
| Remove duplicate invoice files by hash | none | `python scripts/remove_duplicate_invoices.py ...` |
| Start local n8n | `make run-n8n` | docker compose directly |

## 3. Gmail Invoice Finder

Entry point:

```bash
PYTHONPATH=apps/workers-py/src python -m invplatform.cli.gmail_invoice_finder --help
```

Typical run:

```bash
make run-gmail START_DATE=2026-01-01 END_DATE=2026-02-01
```

Key functionality:
- Builds Gmail search query from date range (unless `--gmail-query` is provided).
- Finds invoice-like messages using keyword + sender heuristics.
- Downloads attachment PDFs and link-based PDFs (including provider-specific flows such as Bezeq).
- Optional candidate/non-match dumps and debug explainability.
- Optional verification against PDF text heuristics.

Useful flags:
- `--gmail-query`, `--start-date`, `--end-date`, `--exclude-sent`
- `--invoices-dir`, `--keep-quarantine`
- `--save-json`, `--save-csv`, `--save-candidates`, `--save-nonmatches`
- `--verify`, `--explain`, `--debug`

## 4. Microsoft Graph Invoice Finder

Entry point:

```bash
PYTHONPATH=apps/workers-py/src python -m invplatform.cli.graph_invoice_finder --help
```

Typical run:

```bash
make run-graph START_DATE=2026-01-01 END_DATE=2026-02-01 GRAPH_CLIENT_ID=<client-id>
```

Key functionality:
- Reads messages from Graph over date range.
- Filters and scores messages using invoice heuristics and context checks.
- Downloads attachments and link-based PDFs.
- Optional threshold sweep and explainability output for tuning.
- Optional exclusion of Sent Items.

Useful flags:
- `--client-id`, `--authority`, `--start-date`, `--end-date`
- `--interactive-auth`, `--token-cache-path`
- `--invoices-dir`, `--keep-quarantine`
- `--save-json`, `--save-csv`, `--save-candidates`, `--save-nonmatches`, `--download-report`
- `--exclude-sent`, `--threshold-sweep`, `--verify`, `--explain`, `--debug`

Unattended scheduling tip (n8n/cron):
- first bootstrap run once with `--interactive-auth` and a persistent `--token-cache-path`
- scheduled runs should omit `--interactive-auth` and reuse the same cache path
- if cache is missing/expired, CLI exits fast with `AUTH_REQUIRED` instead of waiting for input

## 5. Monthly Orchestration

Entry point:

```bash
PYTHONPATH=apps/workers-py/src python -m invplatform.cli.monthly_invoices --help
```

Typical runs:

```bash
# current month, both providers
make run-monthly GRAPH_CLIENT_ID=<client-id>

# specific month
MONTH=1 YEAR=2026 make run-monthly GRAPH_CLIENT_ID=<client-id>

# only Gmail
MONTHLY_PROVIDERS=gmail make run-monthly

# Outlook/Gmail with persisted Graph token cache (seamless after bootstrap)
make run-monthly GRAPH_CLIENT_ID=<client-id> GRAPH_TOKEN_CACHE_PATH=./.msal_token_cache.bin

# one-time Graph bootstrap auth for monthly flow (interactive device code)
make run-monthly GRAPH_CLIENT_ID=<client-id> GRAPH_INTERACTIVE_AUTH=1 GRAPH_TOKEN_CACHE_PATH=./.msal_token_cache.bin
```

Behavior:
- Computes monthly range `[start_date, end_date)`.
- Runs Gmail/Graph fetchers (parallel by default).
- Deduplicates PDFs inside provider folders.
- Consolidates all provider PDFs into `invoices/invoices_MM_YYYY`.
- Writes run metadata to `run_summary.json`.

Important flags:
- `--providers`, `--month`, `--year`, `--base-dir`
- `--gmail-extra-args`, `--graph-extra-args`
- `--graph-client-id`
- `--sequential`

## 6. Invoice Report Generator

Entry point:

```bash
PYTHONPATH=apps/workers-py/src python -m invplatform.cli.invoices_report --help
```

Typical run:

```bash
make run-report REPORT_INPUT_DIR=invoices/invoices_01_2026
```

Outputs:
- JSON report
- CSV report
- Summary CSV totals
- PDF report

Parsing/report functionality:
- Extracts invoice fields from PDFs (id, date, vendor, purpose, totals, VAT, period, refs, etc.).
- Includes vendor/category heuristics and vendor-specific parsing logic.
- PDF report supports Hebrew/English text and vendor sorting.
- PDF report can include vendor subtotal rows and a grand total row.

Main flags:
- `--input-dir`, `--files`
- `--json-output`, `--csv-output`, `--summary-csv-output`, `--pdf-output`
- `--pdf-vendor-subtotals` / `--no-pdf-vendor-subtotals`
- `--pdf-skip-single-vendor-subtotals`
- `--debug`

Examples:

```bash
# disable vendor subtotals in PDF
PYTHONPATH=apps/workers-py/src python -m invplatform.cli.invoices_report \
  --input-dir invoices/invoices_01_2026 \
  --json-output report-01-2026.json \
  --csv-output report-01-2026.csv \
  --no-pdf-vendor-subtotals

# keep subtotals but skip vendors that appear once
PYTHONPATH=apps/workers-py/src python -m invplatform.cli.invoices_report \
  --input-dir invoices/invoices_01_2026 \
  --json-output report-01-2026.json \
  --csv-output report-01-2026.csv \
  --pdf-skip-single-vendor-subtotals
```

## 7. Quarantine Non-Invoice PDFs

Entry point:

```bash
PYTHONPATH=apps/workers-py/src python -m invplatform.cli.quarantine_invoices --help
```

Typical usage:

```bash
make quarantine
```

Direct examples:

```bash
PYTHONPATH=apps/workers-py/src python -m invplatform.cli.quarantine_invoices \
  --input-dir invoices/invoices_01_2026 --dry-run
```

Behavior:
- Scans PDFs recursively (skips `_tmp`, `quarantine`, `duplicates`).
- Moves files failing invoice heuristics into quarantine.

## 8. Remove Duplicate Invoices Script

Entry point:

```bash
python scripts/remove_duplicate_invoices.py --help
```

Examples:

```bash
# dry-run by default
python scripts/remove_duplicate_invoices.py invoices

# apply deletion
python scripts/remove_duplicate_invoices.py invoices --apply

# move duplicates instead of deleting
python scripts/remove_duplicate_invoices.py invoices --apply --move-to invoices/duplicates_review
```

Behavior:
- SHA-256 hash-based duplicate detection.
- Can operate on `.pdf` (default) or custom extensions via repeated `--ext`.

## 9. n8n Local Scheduler

Start n8n:

```bash
make run-n8n
```

Suggested workflow:
- Trigger: Cron
- Action: Execute Command
- Daily command: `make -C /workspace run-monthly MONTHLY_PROVIDERS=gmail,outlook GRAPH_TOKEN_CACHE_PATH=/home/node/.n8n/msal_graph_invoice_cache.bin`
- One-time/bootstrap command (manual): `make -C /workspace run-monthly MONTHLY_PROVIDERS=outlook GRAPH_INTERACTIVE_AUTH=1 GRAPH_TOKEN_CACHE_PATH=/home/node/.n8n/msal_graph_invoice_cache.bin`

Notes:

## 10. SaaS API Skeleton (Week 2)

The repo now includes a Week 2 SaaS skeleton:
- SQLAlchemy models for tenant/files/parse jobs/reports/audit events
- service layer with API-key resolution and parse-job creation
- worker runner for parse-job execution
- OpenAPI v1 skeleton in `integrations/openapi/invoices.yaml`
- API middleware adds:
  - `X-Request-ID` response header for every request
  - automatic tenant-scoped `api.*` audit events
  - optional `X-Actor` attribution in audit events

Run API (requires `fastapi` + `uvicorn`):

```bash
make run-saas-api SAAS_DATABASE_URL=sqlite:///./invoices_saas.db SAAS_STORAGE_URL=local://./data/saas_storage
```

Enable control-plane endpoints (tenant bootstrap/list):

```bash
make run-saas-api \
  SAAS_DATABASE_URL=sqlite:///./invoices_saas.db \
  SAAS_STORAGE_URL=local://./data/saas_storage \
  SAAS_CONTROL_PLANE_API_KEY=dev-control-plane-key
```

After startup:
- Swagger UI: `http://127.0.0.1:8080/swagger`
- OpenAPI JSON: `http://127.0.0.1:8080/openapi.json`
- Dashboard UI: `http://127.0.0.1:8080/dashboard`
- Prometheus metrics: `http://127.0.0.1:8080/metrics`

Swagger auth:
- Click `Authorize` in Swagger UI and set the `X-API-Key` value.
- Use the same tenant key used for curl examples below.
- For control-plane endpoints, set `X-Control-Plane-Key`.

Control-plane endpoints:
- `GET /v1/control-plane/tenants`
- `POST /v1/control-plane/tenants`

Export a versioned OpenAPI snapshot (for release pinning):

```bash
make run-saas-openapi-export
```

Optional custom output path:

```bash
make run-saas-openapi-export SAAS_OPENAPI_OUTPUT=integrations/openapi/saas-openapi.custom.json
```

S3-compatible storage example:

```bash
make run-saas-api \
  SAAS_DATABASE_URL=sqlite:///./invoices_saas.db \
  SAAS_STORAGE_URL='s3://my-bucket/invoices?region=us-east-1&endpoint_url=https://s3.amazonaws.com'
```

Run one worker job by id:

```bash
make run-saas-worker SAAS_DATABASE_URL=sqlite:///./invoices_saas.db PARSE_JOB_ID=<job-id>
```

Run background queue worker loop (Redis + RQ):

```bash
make run-saas-rq-worker \
  SAAS_DATABASE_URL=sqlite:///./invoices_saas.db \
  SAAS_STORAGE_URL=local://./data/saas_storage \
  SAAS_REDIS_URL=redis://127.0.0.1:6379/0
```

Control plane + runtime alignment demo (Docker Compose with Redis/RQ):

```bash
# 1) choose control-plane key in your shell
export SAAS_CONTROL_PLANE_API_KEY=dev-control-plane-key

# 2) start redis + saas api + rq worker
make run-saas-demo-up

# 3) create tenant and first API key (safe bootstrap)
BASE_URL=http://127.0.0.1:8081
until curl -fsS "$BASE_URL/healthz" >/dev/null; do sleep 1; done

RESP=$(curl -sS -X POST "$BASE_URL/v1/control-plane/tenants" \
  -H "X-Control-Plane-Key: $SAAS_CONTROL_PLANE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Tenant"}' \
  -w $'\n%{http_code}')

HTTP_CODE="${RESP##*$'\n'}"
BOOTSTRAP_JSON="${RESP%$'\n'*}"

if [ "$HTTP_CODE" != "201" ]; then
  echo "bootstrap failed (HTTP $HTTP_CODE)"
  echo "$BOOTSTRAP_JSON"
else
  echo "$BOOTSTRAP_JSON"
  TENANT_API_KEY=$(jq -r '.api_key.plain_text' <<<"$BOOTSTRAP_JSON")
  echo "TENANT_API_KEY=$TENANT_API_KEY"
fi

# 4) open docs and dashboard for demo stack
# http://127.0.0.1:8081/swagger
# http://127.0.0.1:8081/dashboard

# 5) tail logs (optional)
make run-saas-demo-logs
```

Run retention cleanup for stale reports/artifacts:

```bash
make run-saas-cleanup \
  SAAS_DATABASE_URL=sqlite:///./invoices_saas.db \
  SAAS_STORAGE_URL=local://./data/saas_storage \
  SAAS_RETENTION_DAYS=30
```

Enqueue cleanup to RQ (for cron/scheduler workflows):

```bash
make run-saas-enqueue-cleanup \
  SAAS_DATABASE_URL=sqlite:///./invoices_saas.db \
  SAAS_REDIS_URL=redis://127.0.0.1:6379/0 \
  SAAS_RETENTION_DAYS=30
```

Run migrations (requires `alembic`):

```bash
cd apps/workers-py
alembic upgrade head
```

Minimal local API flow:

```bash
# 1) bootstrap tenant and API key from Python REPL
PYTHONPATH=apps/workers-py/src python - <<'PY'
from invplatform.saas.api import ApiAppConfig, create_app
app = create_app(ApiAppConfig(database_url="sqlite:///./invoices_saas.db"))
tenant, key = app.state.service.bootstrap_tenant("Local Tenant")
print("TENANT_ID=", tenant.id)
print("API_KEY=", key)
PY

# 2) upload PDF
curl -s -X POST http://127.0.0.1:8080/v1/files \
  -H "X-API-Key: <API_KEY>" \
  -F "file=@/absolute/path/to/invoice.pdf"

# 3) create parse job
curl -s -X POST http://127.0.0.1:8080/v1/parse-jobs \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: local-job-001" \
  -d '{"file_ids":["<FILE_ID>"],"debug":false}'

# 4) list invoices
curl -s "http://127.0.0.1:8080/v1/invoices?limit=100&offset=0" \
  -H "X-API-Key: <API_KEY>"

# 5) create report job
curl -s -X POST http://127.0.0.1:8080/v1/reports \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: local-report-001" \
  -d '{"formats":["json","csv","summary_csv"]}'

# 6) list reports
curl -s "http://127.0.0.1:8080/v1/reports?status=succeeded&limit=50&offset=0" \
  -H "X-API-Key: <API_KEY>"

# 7) retry report
curl -s -X POST "http://127.0.0.1:8080/v1/reports/<REPORT_ID>/retry" \
  -H "X-API-Key: <API_KEY>"
```
- Repo is mounted in container at `/workspace`.
- Ensure Gmail OAuth files exist in repo root if using Gmail flow.
- Import ready-to-use n8n workflow JSON files:
  - `integrations/n8n/workflows/monthly_invoices_daily.json`
  - `integrations/n8n/workflows/monthly_invoices_graph_bootstrap.json`

Import workflows via CLI (when UI import is unavailable):

```bash
# import all JSON workflows from the repo folder
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml exec n8n \
  n8n import:workflow --separate --input=/workspace/integrations/n8n/workflows

# verify imported workflows
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml exec n8n \
  n8n list:workflow
```

### 9.1 Bootstrap + Daily Runbook

```bash
# 1) Ensure Graph client id exists in repo root .env
# GRAPH_CLIENT_ID=<your-client-id>

# 2) Start/recreate n8n with .env loaded
make run-n8n

# 3) One-time Graph auth bootstrap (interactive, seeds token cache)
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml exec n8n \
  make -C /workspace run-monthly \
  MONTHLY_PROVIDERS=outlook \
  GRAPH_INTERACTIVE_AUTH=1 \
  GRAPH_TOKEN_CACHE_PATH=/home/node/.n8n/msal_graph_invoice_cache.bin

# 4) Verify env inside n8n and let daily workflow run silently
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml exec n8n printenv GRAPH_CLIENT_ID
```

Recovery when daily run reports `AUTH_REQUIRED`:

```bash
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml exec n8n \
  make -C /workspace run-monthly \
  MONTHLY_PROVIDERS=outlook \
  GRAPH_INTERACTIVE_AUTH=1 \
  GRAPH_TOKEN_CACHE_PATH=/home/node/.n8n/msal_graph_invoice_cache.bin
```

## 10. Go API

Run:

```bash
make -C apps/api-go run
```

Current endpoint:
- `GET /healthz` -> `200 ok`

`integrations/openapi/invoices.yaml` describes broader future invoice endpoints that are not fully implemented in current Go handler.

## 11. Testing and Quality

Run all root tests:

```bash
make test
```

Coverage policy:
- `make test` enforces minimum Python source coverage of `80%` (excluding `tests/*`).
- Override locally if needed: `make test COVERAGE_MIN=85`

Targeted test suites:

```bash
pytest -q tests/test_invoices_report.py tests/test_invoices_report_utils.py
pytest -q tests/test_invoice_finders.py
```

Lint/format:

```bash
make lint
make fmt
```

## 12. Historical Scripts

- `archive/` contains historical scripts and experiments retained for reference/debugging.
- Supported day-to-day entry points are the CLIs under `apps/workers-py/src/invplatform/cli`.

## 13. Meta Billing Graph API Explorer URLs

For ready-to-paste Graph API Explorer URLs (business sanity, invoices edge, ad account activities, `me/businesses`, `me/adaccounts`), see:

- `docs/META_BILLING_GRAPH_API_EXPLORER.md`
