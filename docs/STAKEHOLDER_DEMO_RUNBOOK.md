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
- `jq` is installed (`jq --version`).
- You have at least one PDF invoice path available.
- Open:
  - `Terminal A` for infrastructure/logs
  - `Terminal B` for API calls
  - browser tabs for Swagger and dashboard

## 3) Start Demo Stack

```bash
export SAAS_CONTROL_PLANE_API_KEY=dev-control-plane-key
export SAAS_AUTH_ACCESS_TOKEN_SECRET=dev-auth-access-token-secret
make run-saas-demo-up
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
if ! curl -fsS "$BASE_URL/healthz" >/dev/null; then
  echo "SaaS API is not reachable at $BASE_URL"
  echo "Start stack: docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml up -d --build saas-api saas-rq-worker"
  exit 1
fi

RESP=$(curl -sS -X POST "$BASE_URL/v1/control-plane/tenants" \
  -H "X-Control-Plane-Key: $SAAS_CONTROL_PLANE_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Actor: demo-admin" \
  -d "{\"name\":\"$DEMO_TENANT_NAME\"}" \
  -w $'\n%{http_code}') || {
    echo "Tenant bootstrap request failed (network/connection error)."
    exit 1
  }

HTTP_CODE="${RESP##*$'\n'}"
BOOTSTRAP_JSON="${RESP%$'\n'*}"

if [[ "$HTTP_CODE" != "201" ]]; then
  echo "Tenant bootstrap failed with HTTP $HTTP_CODE"
  echo "$BOOTSTRAP_JSON"
  exit 1
fi

echo "$BOOTSTRAP_JSON"

if ! jq -e '.tenant.id and .api_key.plain_text' >/dev/null <<<"$BOOTSTRAP_JSON"; then
  echo "Unexpected tenant bootstrap response payload."
  exit 1
fi

TENANT_ID=$(jq -r '.tenant.id' <<<"$BOOTSTRAP_JSON")
TENANT_API_KEY=$(jq -r '.api_key.plain_text' <<<"$BOOTSTRAP_JSON")

echo "TENANT_ID=$TENANT_ID"
echo "TENANT_API_KEY=$TENANT_API_KEY"
```

## 7) Control Plane: List Tenants

```bash
RESP=$(curl -sS "$BASE_URL/v1/control-plane/tenants?limit=10&offset=0" \
  -H "X-Control-Plane-Key: $SAAS_CONTROL_PLANE_API_KEY" \
  -w $'\n%{http_code}') || {
    echo "List tenants request failed."
    exit 1
  }

HTTP_CODE="${RESP##*$'\n'}"
TENANTS_JSON="${RESP%$'\n'*}"

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "List tenants failed with HTTP $HTTP_CODE"
  echo "$TENANTS_JSON"
  exit 1
fi

echo "$TENANTS_JSON" | jq .
```

## 8) Tenant API: Upload File

```bash
if [[ ! -f "$FILE_PATH" ]]; then
  echo "Invoice file not found: $FILE_PATH"
  exit 1
fi

RESP=$(curl -sS -X POST "$BASE_URL/v1/files" \
  -H "X-API-Key: $TENANT_API_KEY" \
  -F "file=@$FILE_PATH" \
  -w $'\n%{http_code}') || {
    echo "File upload request failed."
    exit 1
  }

HTTP_CODE="${RESP##*$'\n'}"
FILE_JSON="${RESP%$'\n'*}"

if [[ "$HTTP_CODE" != "200" && "$HTTP_CODE" != "201" ]]; then
  echo "File upload failed with HTTP $HTTP_CODE"
  echo "$FILE_JSON"
  exit 1
fi

if ! jq -e '.id' >/dev/null <<<"$FILE_JSON"; then
  echo "Unexpected file upload response payload."
  echo "$FILE_JSON"
  exit 1
fi

echo "$FILE_JSON"
FILE_ID=$(jq -r '.id' <<<"$FILE_JSON")
echo "FILE_ID=$FILE_ID"
```

## 9) Tenant API: Create Parse Job (Idempotency Demo)

`POST /v1/parse-jobs` is async and may return `202 Accepted`.

```bash
RESP1=$(curl -sS -X POST "$BASE_URL/v1/parse-jobs" \
  -H "X-API-Key: $TENANT_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-parse-001" \
  -d "{\"file_ids\":[\"$FILE_ID\"],\"debug\":false}" \
  -w $'\n%{http_code}') || {
    echo "Parse job create request failed."
    exit 1
  }

HTTP_CODE_1="${RESP1##*$'\n'}"
PARSE_JSON_1="${RESP1%$'\n'*}"
if [[ "$HTTP_CODE_1" != "200" && "$HTTP_CODE_1" != "201" && "$HTTP_CODE_1" != "202" ]]; then
  echo "Parse job create failed with HTTP $HTTP_CODE_1"
  echo "$PARSE_JSON_1"
  exit 1
fi
if ! jq -e '.id' >/dev/null <<<"$PARSE_JSON_1"; then
  echo "Unexpected parse job create payload."
  echo "$PARSE_JSON_1"
  exit 1
fi

RESP2=$(curl -sS -X POST "$BASE_URL/v1/parse-jobs" \
  -H "X-API-Key: $TENANT_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-parse-001" \
  -d "{\"file_ids\":[\"$FILE_ID\"],\"debug\":true}" \
  -w $'\n%{http_code}') || {
    echo "Parse job idempotent replay request failed."
    exit 1
  }

HTTP_CODE_2="${RESP2##*$'\n'}"
PARSE_JSON_2="${RESP2%$'\n'*}"
if [[ "$HTTP_CODE_2" != "200" && "$HTTP_CODE_2" != "201" && "$HTTP_CODE_2" != "202" ]]; then
  echo "Parse job idempotent replay failed with HTTP $HTTP_CODE_2"
  echo "$PARSE_JSON_2"
  exit 1
fi
if ! jq -e '.id' >/dev/null <<<"$PARSE_JSON_2"; then
  echo "Unexpected parse job replay payload."
  echo "$PARSE_JSON_2"
  exit 1
fi

echo "$PARSE_JSON_1"
echo "$PARSE_JSON_2"
PARSE_JOB_ID=$(jq -r '.id' <<<"$PARSE_JSON_1")
PARSE_JOB_ID_2=$(jq -r '.id' <<<"$PARSE_JSON_2")
echo "PARSE_JOB_ID=$PARSE_JOB_ID"
if [[ "$PARSE_JOB_ID_2" != "$PARSE_JOB_ID" ]]; then
  echo "Warning: idempotent replay returned different job id: $PARSE_JOB_ID_2"
fi
```

## 10) Poll Parse Job

```bash
for _ in {1..120}; do
  RESP=$(curl -sS "$BASE_URL/v1/parse-jobs/$PARSE_JOB_ID" \
    -H "X-API-Key: $TENANT_API_KEY" \
    -w $'\n%{http_code}') || {
      echo "Parse status poll request failed."
      exit 1
    }

  HTTP_CODE="${RESP##*$'\n'}"
  PARSE_STATUS_JSON="${RESP%$'\n'*}"
  if [[ "$HTTP_CODE" != "200" ]]; then
    echo "Parse status poll failed with HTTP $HTTP_CODE"
    echo "$PARSE_STATUS_JSON"
    exit 1
  fi
  if ! jq -e '.status' >/dev/null <<<"$PARSE_STATUS_JSON"; then
    echo "Unexpected parse status payload."
    echo "$PARSE_STATUS_JSON"
    exit 1
  fi

  STATUS=$(jq -r '.status' <<<"$PARSE_STATUS_JSON")
  echo "parse status: $STATUS"
  [ "$STATUS" = "succeeded" ] && break
  [ "$STATUS" = "failed" ] && break
  sleep 2
done

if [[ "$STATUS" != "succeeded" ]]; then
  echo "Parse job did not succeed. Final status: $STATUS"
  exit 1
fi
```

## 11) List Invoices

```bash
RESP=$(curl -sS "$BASE_URL/v1/invoices?limit=50&offset=0" \
  -H "X-API-Key: $TENANT_API_KEY" \
  -w $'\n%{http_code}') || {
    echo "List invoices request failed."
    exit 1
  }

HTTP_CODE="${RESP##*$'\n'}"
INVOICES_JSON="${RESP%$'\n'*}"

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "List invoices failed with HTTP $HTTP_CODE"
  echo "$INVOICES_JSON"
  exit 1
fi

echo "$INVOICES_JSON" | jq .
```

## 12) Create Report Job and Poll

```bash
RESP=$(curl -sS -X POST "$BASE_URL/v1/reports" \
  -H "X-API-Key: $TENANT_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-report-001" \
  -d '{"formats":["json","csv","summary_csv"]}' \
  -w $'\n%{http_code}') || {
    echo "Create report request failed."
    exit 1
  }

HTTP_CODE="${RESP##*$'\n'}"
REPORT_JSON="${RESP%$'\n'*}"

if [[ "$HTTP_CODE" != "200" && "$HTTP_CODE" != "201" && "$HTTP_CODE" != "202" ]]; then
  echo "Create report failed with HTTP $HTTP_CODE"
  echo "$REPORT_JSON"
  exit 1
fi
if ! jq -e '.id' >/dev/null <<<"$REPORT_JSON"; then
  echo "Unexpected create report payload."
  echo "$REPORT_JSON"
  exit 1
fi

echo "$REPORT_JSON"
REPORT_ID=$(jq -r '.id' <<<"$REPORT_JSON")
echo "REPORT_ID=$REPORT_ID"

for _ in {1..120}; do
  RESP=$(curl -sS "$BASE_URL/v1/reports/$REPORT_ID" \
    -H "X-API-Key: $TENANT_API_KEY" \
    -w $'\n%{http_code}') || {
      echo "Report status poll request failed."
      exit 1
    }

  HTTP_CODE="${RESP##*$'\n'}"
  REPORT_STATUS_JSON="${RESP%$'\n'*}"
  if [[ "$HTTP_CODE" != "200" ]]; then
    echo "Report status poll failed with HTTP $HTTP_CODE"
    echo "$REPORT_STATUS_JSON"
    exit 1
  fi
  if ! jq -e '.status' >/dev/null <<<"$REPORT_STATUS_JSON"; then
    echo "Unexpected report status payload."
    echo "$REPORT_STATUS_JSON"
    exit 1
  fi

  RSTATUS=$(jq -r '.status' <<<"$REPORT_STATUS_JSON")
  echo "report status: $RSTATUS"
  [ "$RSTATUS" = "succeeded" ] && break
  [ "$RSTATUS" = "failed" ] && break
  sleep 2
done

if [[ "$RSTATUS" != "succeeded" ]]; then
  echo "Report job did not succeed. Final status: $RSTATUS"
  exit 1
fi
```

## 13) Download Report Artifact

```bash
HTTP_CODE=$(curl -sS "$BASE_URL/v1/reports/$REPORT_ID/download?format=json" \
  -H "X-API-Key: $TENANT_API_KEY" \
  -o /tmp/demo-report.json \
  -w '%{http_code}') || {
    echo "Report download request failed."
    exit 1
  }

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "Report download failed with HTTP $HTTP_CODE"
  cat /tmp/demo-report.json
  exit 1
fi

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
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml logs --tail=120 saas-api saas-rq-worker
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml up -d --build saas-api saas-rq-worker
```

## 17) Stop Demo Stack

```bash
docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml stop saas-api saas-rq-worker
```
