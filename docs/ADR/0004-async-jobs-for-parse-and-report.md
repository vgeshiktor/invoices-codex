# ADR 0004: Async Jobs for Parsing and Reporting

- Status: Accepted
- Date: 2026-03-08

## Context

Invoice parsing and report generation are variable-duration operations and can exceed practical API request timeouts.

## Decision

Implement parse, report, and collection orchestration operations as asynchronous jobs:
- API creates job records and enqueues background tasks.
- Worker executes tasks with retries for transient errors.
- Clients poll job status endpoints.

## Consequences

Positive:
- Stable API latency profile.
- Better resilience and retry semantics.
- Clear operational visibility of long-running workloads.
- Collection runs can orchestrate provider execution and parse pipeline linking without synchronous API timeouts.

Negative:
- Requires queue infrastructure and job lifecycle management.
- Client integration includes polling or callback pattern later.
