# ADR 0001: FastAPI API + Python Worker Architecture

- Status: Accepted
- Date: 2026-03-08

## Context

The current project has mature Python parsing/reporting domain logic and a minimal Go health endpoint. SaaS MVP requires API exposure, async processing, and low implementation risk.

## Decision

Use a Python-based architecture with:
- FastAPI API service for request/response flows.
- Separate Python worker process for async parse/report jobs.
- Shared domain module reuse from `invplatform.usecases`.

## Consequences

Positive:
- Lowest integration risk with existing parser logic.
- Fast delivery for MVP.
- Single language runtime for core business logic.

Negative:
- Less polyglot flexibility in MVP.
- Requires clear module boundaries to avoid API/worker coupling.
