# Task: Deep Project Review + SaaS Expansion Plan

## Scope
- Learn the project deeply
- Review code and architecture with concrete improvements
- Design a path to a fully-fledged SaaS service
- Identify missing capabilities and add a practical implementation backlog

## What Was Done
- Read project docs, build files, Docker/CI setup, and core runtime modules
- Reviewed main execution paths:
  - `apps/workers-py/src/invplatform/cli/gmail_invoice_finder.py`
  - `apps/workers-py/src/invplatform/cli/graph_invoice_finder.py`
  - `apps/workers-py/src/invplatform/cli/invoices_report.py`
  - `apps/workers-py/src/invplatform/cli/monthly_invoices.py`
  - `apps/api-go/cmd/invoicer/main.go`
- Validated runtime baseline:
  - `PYTHONPATH=apps/workers-py/src python -m pytest tests -q`
  - Result: `159 passed`
- Evaluated static quality gates:
  - `python -m mypy apps/workers-py/src`
  - Result: 105 typing errors (mostly in large CLI modules)

## Deliverables
- `project_reviews/2026_03_08/review.md`
- `project_reviews/2026_03_08/saas_blueprint.md`
- `project_reviews/2026_03_08/missing_capabilities_backlog.md`
