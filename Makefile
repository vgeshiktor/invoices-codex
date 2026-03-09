.PHONY: setup dev up down test lint fmt run-gmail run-graph run-report run-monthly run-n8n quarantine run-saas-api run-saas-worker run-saas-rq-worker run-saas-cleanup run-saas-enqueue-cleanup run-saas-openapi-export run-saas-demo-up run-saas-demo-down run-saas-demo-logs

setup: ## התקנות ראשוניות
	pre-commit install

dev: ## הרצה מקומית של כל הסרוויסים (דוקר קומפוז)
	docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml up --build

up:
	docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml up -d

down:
	docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml down

test:
	@if $(PYTHON) -c "import coverage" > /dev/null 2>&1; then \
		echo "Running pytest with coverage..."; \
		PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m coverage run -m pytest tests && \
		$(PYTHON) -m coverage report --show-missing --omit='tests/*' --fail-under=$(COVERAGE_MIN); \
	else \
		echo "coverage module not found for $(PYTHON); attempting installation..."; \
		if $(PYTHON) -m pip install --quiet coverage; then \
			PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m coverage run -m pytest tests && \
			$(PYTHON) -m coverage report --show-missing --omit='tests/*' --fail-under=$(COVERAGE_MIN); \
		else \
			echo "Failed to install coverage, running pytest without coverage."; \
			PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m pytest tests; \
		fi \
	fi

lint:
	$(MAKE) -C apps/api-go lint
	$(MAKE) -C apps/workers-py lint

fmt:
	$(MAKE) -C apps/api-go fmt
	$(MAKE) -C apps/workers-py fmt

PYTHON ?= python
PYTHONPATH_EXTRA := apps/workers-py/src
COVERAGE_MIN ?= 80

START_DATE ?=
END_DATE ?=

GMAIL_INVOICES_DIR ?= invoices_gmail
GMAIL_EXTRA_ARGS ?= --save-candidates $(GMAIL_INVOICES_DIR)/reports/candidates_gmail.json \
	--save-nonmatches $(GMAIL_INVOICES_DIR)/reports/rejected_gmail.json

GRAPH_CLIENT_ID ?=
GRAPH_AUTHORITY ?= consumers
GRAPH_INTERACTIVE_AUTH ?=
GRAPH_TOKEN_CACHE_PATH ?= ./.msal_token_cache.bin
GRAPH_INVOICES_DIR ?= invoices_outlook
GRAPH_EXTRA_ARGS ?= --save-json $(GRAPH_INVOICES_DIR)/reports/invoices.json \
	--save-csv $(GRAPH_INVOICES_DIR)/reports/invoices.csv \
    --download-report $(GRAPH_INVOICES_DIR)/reports/download_report.json \
	--explain --verify \
	--save-candidates $(GRAPH_INVOICES_DIR)/reports/candidates_outlook.json \
	--save-nonmatches $(GRAPH_INVOICES_DIR)/reports/vrejected_outlook.json

MONTHLY_BASE_DIR ?= invoices
MONTHLY_PROVIDERS ?= gmail,outlook
MONTHLY_GMAIL_ARGS ?= --exclude-sent --verify
MONTHLY_GRAPH_ARGS ?= --exclude-sent --verify --explain \
	$(if $(GRAPH_TOKEN_CACHE_PATH),--token-cache-path $(GRAPH_TOKEN_CACHE_PATH),) \
	$(if $(GRAPH_INTERACTIVE_AUTH),--interactive-auth,)
MONTHLY_SEQUENTIAL ?=

REPORT_INPUT_DIR ?= invoices_outlook
REPORT_JSON_OUTPUT ?= reports/invoice_report.json
REPORT_CSV_OUTPUT ?= reports/invoice_report.csv
REPORT_SUMMARY_CSV_OUTPUT ?= reports/invoice_report.summary.csv
REPORT_EXTRA_ARGS ?=
SAAS_DATABASE_URL ?= sqlite:///./invoices_saas.db
SAAS_REDIS_URL ?=
SAAS_STORAGE_URL ?= local://./data/saas_storage
SAAS_QUEUE ?= invoices
SAAS_WORKER_BURST ?=
SAAS_RETENTION_DAYS ?= 30
PARSE_JOB_ID ?=
SAAS_OPENAPI_OUTPUT ?=
SAAS_CONTROL_PLANE_API_KEY ?=

run-gmail: ## הרצת Gmail invoice finder (נדרש START_DATE ו-END_DATE)
	@test -n "$(START_DATE)" || (echo "START_DATE is required. Example: make run-gmail START_DATE=2025-06-01 END_DATE=2025-07-01"; exit 1)
	@test -n "$(END_DATE)" || (echo "END_DATE is required. Example: make run-gmail START_DATE=2025-06-01 END_DATE=2025-07-01"; exit 1)
	PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m invplatform.cli.gmail_invoice_finder \
		--start-date $(START_DATE) \
		--end-date $(END_DATE) \
		--invoices-dir $(GMAIL_INVOICES_DIR) \
		$(GMAIL_EXTRA_ARGS)

run-graph: ## הרצת Outlook/Graph invoice finder (נדרש START_DATE, END_DATE, GRAPH_CLIENT_ID)
	@test -n "$(START_DATE)" || (echo "START_DATE is required. Example: make run-graph START_DATE=2025-06-01 END_DATE=2025-07-01 GRAPH_CLIENT_ID=..."; exit 1)
	@test -n "$(END_DATE)" || (echo "END_DATE is required. Example: make run-graph START_DATE=2025-06-01 END_DATE=2025-07-01 GRAPH_CLIENT_ID=..."; exit 1)
	@test -n "$(GRAPH_CLIENT_ID)" || (echo "GRAPH_CLIENT_ID is required. Pass via make run-graph GRAPH_CLIENT_ID=..."; exit 1)
	PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m invplatform.cli.graph_invoice_finder \
		--client-id "$(GRAPH_CLIENT_ID)" \
		--authority "$(GRAPH_AUTHORITY)" \
		$(if $(GRAPH_INTERACTIVE_AUTH),--interactive-auth,) \
		$(if $(GRAPH_TOKEN_CACHE_PATH),--token-cache-path "$(GRAPH_TOKEN_CACHE_PATH)",) \
		--start-date $(START_DATE) \
		--end-date $(END_DATE) \
		--invoices-dir $(GRAPH_INVOICES_DIR) \
		$(GRAPH_EXTRA_ARGS)

run-report: ## Generate invoice report JSON/CSV from downloaded PDFs
	PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m invplatform.cli.invoices_report \
		--input-dir $(REPORT_INPUT_DIR) \
		--json-output $(REPORT_JSON_OUTPUT) \
		--csv-output $(REPORT_CSV_OUTPUT) \
		--summary-csv-output $(REPORT_SUMMARY_CSV_OUTPUT) \
		$(REPORT_EXTRA_ARGS)

run-monthly: ## Download current-month invoices (Gmail+Outlook) and consolidate under invoices/
	@start_epoch=$$(date +%s); \
	start_local=$$(date '+%Y-%m-%d %H:%M:%S %Z%z'); \
	start_utc=$$(date -u '+%Y-%m-%d %H:%M:%S UTC'); \
	echo "[MONTHLY_RUN] START local=$$start_local utc=$$start_utc"; \
	run_status=0; \
	PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m invplatform.cli.monthly_invoices \
		--providers "$(MONTHLY_PROVIDERS)" \
		--base-dir $(MONTHLY_BASE_DIR) \
		$(if $(MONTH),--month $(MONTH),) \
		$(if $(YEAR),--year $(YEAR),) \
		$(if $(MONTHLY_GMAIL_ARGS),--gmail-extra-args "$(MONTHLY_GMAIL_ARGS)",) \
		$(if $(MONTHLY_GRAPH_ARGS),--graph-extra-args "$(MONTHLY_GRAPH_ARGS)",) \
		$(if $(GRAPH_CLIENT_ID),--graph-client-id "$(GRAPH_CLIENT_ID)",) \
		$(if $(MONTHLY_SEQUENTIAL),--sequential,) \
	|| run_status=$$?; \
	end_epoch=$$(date +%s); \
	end_local=$$(date '+%Y-%m-%d %H:%M:%S %Z%z'); \
	end_utc=$$(date -u '+%Y-%m-%d %H:%M:%S UTC'); \
	duration=$$((end_epoch - start_epoch)); \
	duration_h=$$((duration / 3600)); \
	duration_m=$$(((duration % 3600) / 60)); \
	duration_s=$$((duration % 60)); \
	echo "[MONTHLY_RUN] END local=$$end_local utc=$$end_utc"; \
	printf '[MONTHLY_RUN] DURATION %02dh:%02dm:%02ds (%ss)\n' $$duration_h $$duration_m $$duration_s $$duration; \
	echo "[MONTHLY_RUN] STATUS exit_code=$$run_status"; \
	exit $$run_status

run-n8n: ## Start n8n (dev compose only)
	docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml up -d --build n8n

run-saas-demo-up: ## Start SaaS demo stack (saas-api + rq worker + redis)
	docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml up -d --build redis saas-api saas-rq-worker

run-saas-demo-down: ## Stop SaaS demo stack services
	docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml stop saas-api saas-rq-worker redis

run-saas-demo-logs: ## Tail SaaS demo stack logs
	docker compose --env-file .env -f deploy/compose/docker-compose.dev.yml logs -f saas-api saas-rq-worker redis

quarantine: ## Move non-invoice PDFs into quarantine/
	PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m invplatform.cli.quarantine_invoices

run-saas-api: ## Run SaaS API skeleton
	PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m invplatform.cli.saas_api \
		--database-url "$(SAAS_DATABASE_URL)" \
		--storage-url "$(SAAS_STORAGE_URL)" \
		$(if $(SAAS_CONTROL_PLANE_API_KEY),--control-plane-api-key "$(SAAS_CONTROL_PLANE_API_KEY)",) \
		$(if $(SAAS_REDIS_URL),--redis-url "$(SAAS_REDIS_URL)",)

run-saas-worker: ## Run one SaaS parse job by id
	@test -n "$(PARSE_JOB_ID)" || (echo "PARSE_JOB_ID is required. Example: make run-saas-worker PARSE_JOB_ID=<job-id>"; exit 1)
	PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m invplatform.cli.saas_worker \
		--database-url "$(SAAS_DATABASE_URL)" \
		--storage-url "$(SAAS_STORAGE_URL)" \
		"$(PARSE_JOB_ID)"

run-saas-rq-worker: ## Run SaaS RQ worker loop (parse/report queue)
	@test -n "$(SAAS_REDIS_URL)" || (echo "SAAS_REDIS_URL is required. Example: make run-saas-rq-worker SAAS_REDIS_URL=redis://127.0.0.1:6379/0"; exit 1)
	PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m invplatform.cli.saas_rq_worker \
		--database-url "$(SAAS_DATABASE_URL)" \
		--storage-url "$(SAAS_STORAGE_URL)" \
		--redis-url "$(SAAS_REDIS_URL)" \
		--queue "$(SAAS_QUEUE)" \
		$(if $(SAAS_WORKER_BURST),--burst,)

run-saas-cleanup: ## Cleanup stale SaaS report artifacts/rows
	PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m invplatform.cli.saas_cleanup \
		--database-url "$(SAAS_DATABASE_URL)" \
		--retention-days "$(SAAS_RETENTION_DAYS)" \
		--storage-url "$(SAAS_STORAGE_URL)"

run-saas-enqueue-cleanup: ## Enqueue cleanup task to RQ queue backend
	@test -n "$(SAAS_REDIS_URL)" || (echo "SAAS_REDIS_URL is required. Example: make run-saas-enqueue-cleanup SAAS_REDIS_URL=redis://127.0.0.1:6379/0"; exit 1)
	PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m invplatform.cli.saas_enqueue_cleanup \
		--database-url "$(SAAS_DATABASE_URL)" \
		--redis-url "$(SAAS_REDIS_URL)" \
		--retention-days "$(SAAS_RETENTION_DAYS)"

run-saas-openapi-export: ## Export versioned SaaS OpenAPI snapshot JSON
	PYTHONPATH=$(PYTHONPATH_EXTRA):$$PYTHONPATH $(PYTHON) -m invplatform.cli.saas_openapi_export \
		--database-url "sqlite://" \
		--storage-url "$(SAAS_STORAGE_URL)" \
		$(if $(SAAS_OPENAPI_OUTPUT),--output "$(SAAS_OPENAPI_OUTPUT)",)
