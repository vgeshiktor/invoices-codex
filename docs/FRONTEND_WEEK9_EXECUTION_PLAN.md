# Frontend Week 9 Execution Plan

Date: 2026-03-09
Scope: Execute `BE-401`, `FE-601..FE-605` from `docs/FRONTEND_CONVERSION_BACKLOG.md`

## 1. Week 9 Goal

By end of Week 9:
- tenant-scoped audit query API is available for UI consumption.
- frontend telemetry taxonomy is defined and versioned.
- frontend is instrumented with tracing/error reporting.
- key user flows expose request correlation IDs.
- activity timeline and support bundle export are available in UI.

## 2. Team Slots (Fill Names)

- `Owner-BE-Audit`: backend audit query API lead
- `Owner-FE-Observability`: frontend telemetry/instrumentation lead
- `Owner-FE-Timeline`: activity timeline/support bundle lead
- `Owner-QA`: observability and traceability validation lead
- `Owner-Review`: cross-stack reviewer and merge gate

## 3. Issue Map (Week 9 Only)

| ID | Title | Primary Owner | Backup Owner | Depends On |
|---|---|---|---|---|
| BE-401 | Add tenant-scoped audit event query API | Owner-BE-Audit | Owner-Review | existing audit writes |
| FE-601 | Define and document frontend telemetry event taxonomy | Owner-FE-Observability | Owner-QA | FE-001 |
| FE-602 | Add frontend OTel + Sentry instrumentation | Owner-FE-Observability | Owner-FE-Timeline | FE-601 |
| FE-603 | Propagate and display request correlation IDs | Owner-FE-Observability | Owner-FE-Timeline | FE-301 |
| FE-604 | Build tenant activity timeline UI from audit events | Owner-FE-Timeline | Owner-FE-Observability | BE-401 |
| FE-605 | Add support bundle export for failed run diagnostics | Owner-FE-Timeline | Owner-QA | FE-603 |

## 4. Backend Contract for Week 9 (Freeze Early)

Audit query endpoint (tenant-scoped):
- `GET /v1/audit-events?limit=&offset=&event_type=&actor=&from=&to=`

Required fields:
- `id`
- `tenant_id`
- `event_type`
- `actor`
- `payload`
- `created_at`
- `request_id` (if available in payload/metadata)

Response envelope:
- `items`
- `total`
- `limit`
- `offset`

Security and privacy constraints:
- strict tenant scoping for all audit event queries.
- sensitive fields are masked before response.
- query endpoint supports pagination limits to prevent data overfetch.

## 5. Day-by-Day Execution

## Day 1 (Mon): Audit API + Telemetry Taxonomy Start

Planned issues:
- BE-401 (start)
- FE-601 (start)

Tasks:
1. Freeze audit query API contract and filtering/pagination rules.
2. Implement backend audit events list endpoint with tenant isolation tests.
3. Draft telemetry event taxonomy for key frontend journeys.

End-of-day checkpoint:
- BE-401 PR opened.
- FE-601 draft taxonomy shared for review.

## Day 2 (Tue): Audit API Completion + Telemetry Taxonomy Finalization

Planned issues:
- BE-401 (finish)
- FE-601 (finish)
- FE-602 (start)

Tasks:
1. Finalize audit endpoint performance and masking behavior.
2. Version and publish telemetry taxonomy in docs.
3. Start frontend instrumentation wiring (OpenTelemetry + error reporting SDK).

End-of-day checkpoint:
- BE-401 merged.
- FE-601 merged.
- FE-602 at least 40% complete.

## Day 3 (Wed): Instrumentation + Correlation IDs

Planned issues:
- FE-602 (finish)
- FE-603 (start)

Tasks:
1. Instrument key frontend actions and page transitions.
2. Capture runtime errors with contextual metadata.
3. Propagate request correlation IDs to UI-visible surfaces.

End-of-day checkpoint:
- FE-602 merged.
- FE-603 in progress with request IDs visible in at least one key flow.

## Day 4 (Thu): Timeline UI + Support Bundle Start

Planned issues:
- FE-603 (finish)
- FE-604 (start)
- FE-605 (start)

Tasks:
1. Complete request ID visibility across critical journeys.
2. Build activity timeline with filtering and pagination.
3. Start support bundle export composition (request IDs + status + event snippets).

End-of-day checkpoint:
- FE-603 merged.
- FE-604 at least 60% complete.
- FE-605 baseline export path implemented.

## Day 5 (Fri): Timeline Completion + Support Bundle Completion

Planned issues:
- FE-604 (finish)
- FE-605 (finish)

Tasks:
1. Finalize activity timeline UX and error/empty states.
2. Finalize support bundle export output shape and download action.
3. Add integration/e2e checks for timeline and diagnostics export.

End-of-day checkpoint:
- FE-604 and FE-605 merged.
- Week 9 traceability checks green in CI.

## 6. Daily Standup Template

Use this exact format:

- Yesterday: completed IDs
- Today: planned IDs
- Blockers: audit/telemetry/frontend/test
- Confidence: `Green | Yellow | Red`

## 7. Definition of Done (Week 9)

For each issue:
- acceptance criteria from issue body met
- tests added and green in CI
- docs updated (taxonomy/API) where changed
- reviewed and merged

Week-level DoD:
- `BE-401`, `FE-601`, `FE-602`, `FE-603`, `FE-604`, `FE-605` all closed
- timeline and support bundle usable for production debugging
- request IDs and audit events support end-to-end traceability
- no open P0/P1 observability/traceability defects

## 8. Test Matrix (Minimum)

- Unit:
  - telemetry event mapping
  - request ID formatting/display logic
  - support bundle payload builder
- Integration:
  - audit events query and timeline rendering
  - masked field handling and pagination behavior
- E2E:
  - key user action -> request ID visible -> timeline shows related event
  - failed flow -> support bundle download includes correlation context

## 9. Risks and Fast Mitigations

- Risk: telemetry noise reduces signal quality.
- Mitigation: apply event taxonomy gating and sample non-critical events.

- Risk: audit payload includes sensitive fields.
- Mitigation: enforce backend masking and add automated checks for secret patterns.

- Risk: timeline pagination causes slow UI on large tenants.
- Mitigation: cursor/offset pagination with strict page size and lazy loading.

## 10. Week 9 Exit Artifacts

At week close, produce:
1. merged PR list for `BE-401`, `FE-601..FE-605`.
2. CI links proving observability/traceability checks are green.
3. short handoff note for Week 10 quality/release hardening.
