# Stakeholder Demo Runbook (Control Plane + Runtime Alignment)

This runbook is a complete, copy-paste script for demonstrating:
- control-plane tenant bootstrap
- tenant-scoped API usage
- async parse/report execution via Redis + RQ
- Swagger, dashboard, and metrics visibility

## 1) Demo Objective

Use this narrative in the first minute:

"This demo shows end-to-end SaaS flow: tenant onboarding, async invoice parsing, report generation, and operational visibility."

## 2) Pre-Demo Checklist

- Docker Desktop is running.
- You have at least one PDF invoice path available.
- Open:
  - `Terminal A` for infrastructure/logs
  - `Terminal B` for API calls
  - browser tabs for Swagger and dashboard

## 3) Start Demo Stack

```bash
export SAAS_CONTROL_PLANE_API_KEY=dev-control-plane-key
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml up -d --build redis saas-api saas-rq-worker
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml ps
```

## 4) Health Check

```bash
until curl -fsS http://127.0.0.1:8081/healthz >/dev/null; do sleep 1; done
echo "SaaS API is up"
```

## 5) Shared Variables

```bash
export BASE_URL=http://127.0.0.1:8081
export DEMO_TENANT_NAME="Stakeholder Demo Tenant"
export FILE_PATH="/absolute/path/to/invoice.pdf"
```

## 6) Control Plane: Create Tenant

```bash
BOOTSTRAP_JSON=$(curl -fsS -X POST "$BASE_URL/v1/control-plane/tenants" \
  -H "X-Control-Plane-Key: $SAAS_CONTROL_PLANE_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Actor: demo-admin" \
  -d "{\"name\":\"$DEMO_TENANT_NAME\"}")

echo "$BOOTSTRAP_JSON"

TENANT_ID=$(python -c 'import json,sys; print(json.loads(sys.stdin.read())["tenant"]["id"])' <<<"$BOOTSTRAP_JSON")
TENANT_API_KEY=$(python -c 'import json,sys; print(json.loads(sys.stdin.read())["api_key"]["plain_text"])' <<<"$BOOTSTRAP_JSON")

echo "TENANT_ID=$TENANT_ID"
echo "TENANT_API_KEY=$TENANT_API_KEY"
```

## 7) Control Plane: List Tenants

```bash
curl -fsS "$BASE_URL/v1/control-plane/tenants?limit=10&offset=0" \
  -H "X-Control-Plane-Key: $SAAS_CONTROL_PLANE_API_KEY"
```

## 8) Tenant API: Upload File

```bash
FILE_JSON=$(curl -fsS -X POST "$BASE_URL/v1/files" \
  -H "X-API-Key: $TENANT_API_KEY" \
  -F "file=@$FILE_PATH")

echo "$FILE_JSON"
FILE_ID=$(python -c 'import json,sys; print(json.loads(sys.stdin.read())["id"])' <<<"$FILE_JSON")
```

## 9) Tenant API: Create Parse Job (Idempotency Demo)

```bash
PARSE_JSON_1=$(curl -fsS -X POST "$BASE_URL/v1/parse-jobs" \
  -H "X-API-Key: $TENANT_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-parse-001" \
  -d "{\"file_ids\":[\"$FILE_ID\"],\"debug\":false}")

PARSE_JSON_2=$(curl -fsS -X POST "$BASE_URL/v1/parse-jobs" \
  -H "X-API-Key: $TENANT_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-parse-001" \
  -d "{\"file_ids\":[\"$FILE_ID\"],\"debug\":true}")

echo "$PARSE_JSON_1"
echo "$PARSE_JSON_2"
PARSE_JOB_ID=$(python -c 'import json,sys; print(json.loads(sys.stdin.read())["id"])' <<<"$PARSE_JSON_1")
```

## 10) Poll Parse Job

```bash
while true; do
  PARSE_STATUS_JSON=$(curl -fsS "$BASE_URL/v1/parse-jobs/$PARSE_JOB_ID" -H "X-API-Key: $TENANT_API_KEY")
  STATUS=$(python -c 'import json,sys; print(json.loads(sys.stdin.read())["status"])' <<<"$PARSE_STATUS_JSON")
  echo "parse status: $STATUS"
  [ "$STATUS" = "succeeded" ] && break
  [ "$STATUS" = "failed" ] && break
  sleep 2
done
```

## 11) List Invoices

```bash
curl -fsS "$BASE_URL/v1/invoices?limit=50&offset=0" -H "X-API-Key: $TENANT_API_KEY"
```

## 12) Create Report Job and Poll

```bash
REPORT_JSON=$(curl -fsS -X POST "$BASE_URL/v1/reports" \
  -H "X-API-Key: $TENANT_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-report-001" \
  -d '{"formats":["json","csv","summary_csv"]}')

echo "$REPORT_JSON"
REPORT_ID=$(python -c 'import json,sys; print(json.loads(sys.stdin.read())["id"])' <<<"$REPORT_JSON")

while true; do
  REPORT_STATUS_JSON=$(curl -fsS "$BASE_URL/v1/reports/$REPORT_ID" -H "X-API-Key: $TENANT_API_KEY")
  RSTATUS=$(python -c 'import json,sys; print(json.loads(sys.stdin.read())["status"])' <<<"$REPORT_STATUS_JSON")
  echo "report status: $RSTATUS"
  [ "$RSTATUS" = "succeeded" ] && break
  [ "$RSTATUS" = "failed" ] && break
  sleep 2
done
```

## 13) Download Report Artifact

```bash
curl -fsS "$BASE_URL/v1/reports/$REPORT_ID/download?format=json" \
  -H "X-API-Key: $TENANT_API_KEY" \
  -o /tmp/demo-report.json

ls -lh /tmp/demo-report.json
head -n 20 /tmp/demo-report.json
```

## 14) Show UI and Metrics

- Swagger: `http://127.0.0.1:8081/swagger`
- Dashboard: `http://127.0.0.1:8081/dashboard` (paste `TENANT_API_KEY`)

```bash
curl -fsS "$BASE_URL/metrics" | head -n 30
```

## 15) Close with Value Summary

- Tenant onboarding is now API-driven via control-plane endpoints.
- Runtime is async and queue-backed (Redis + RQ worker).
- End-to-end flow is working: onboarding -> upload -> parse -> report -> download.
- Operational visibility exists through Swagger, dashboard, and metrics.

## 16) Fast Troubleshooting

```bash
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml logs --tail=120 saas-api saas-rq-worker redis
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml up -d --build saas-api saas-rq-worker redis
```

## 17) Stop Demo Stack

```bash
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml stop saas-api saas-rq-worker redis
```
