# Frontend Conversion Backlog (KISS)

Date: 2026-03-09
Owner: Product + Engineering

## 1. Purpose

Turn the current API-first SaaS backend into a production-ready, mobile-friendly web frontend with full testability, observability, and traceability.

This plan is intentionally simple:
- one web app first
- one primary API backend
- vertical slices by user journey
- every slice includes tests and telemetry

## 2. Current Baseline

Implemented backend capabilities:
- tenant bootstrap via control-plane API
- tenant API keys
- file upload
- parse jobs
- invoice listing
- report jobs + artifact download
- dashboard summary and metrics endpoint

Implemented references:
- `apps/workers-py/src/invplatform/saas/api.py`
- `integrations/openapi/saas-openapi.v0.1.0.json`
- `docs/PRD_V1_SAAS.md`
- `docs/ARCHITECTURE.md`

Missing capabilities needed by requested frontend journeys:
- end-user login/session model (current model is API-key only)
- provider connection management (Gmail/Outlook OAuth lifecycle)
- collection-job APIs for provider-based collection runs
- scheduling APIs for daily automated runs
- user-facing audit/events API for traceability screens

## 3. Scope Box (Frontend MVP)

In scope:
- responsive web app for tenant users
- login, provider configuration, collection runs, report generation/download
- schedule daily collection runs
- observability and traceability in UI and backend integration
- full automated testing with >=80% frontend coverage

Out of scope for this phase:
- billing/subscriptions/payments
- native mobile apps
- advanced OCR/rule-builder UX
- multi-region and enterprise compliance controls

## 4. Tech Stack (Recommended)

- App framework: React + TypeScript + Vite
- Routing: React Router
- Data fetching/cache: TanStack Query
- Form and validation: React Hook Form + Zod
- UI system: Tailwind CSS + accessible headless primitives
- API contracts: OpenAPI-generated client types
- Unit/integration tests: Vitest + React Testing Library + MSW
- E2E tests: Playwright
- Error tracking: Sentry
- Tracing/telemetry: OpenTelemetry web SDK + request ID propagation

## 5. Responsive Design Standards

- Mobile-first implementation on every screen.
- Breakpoints: 360, 768, 1024, 1440.
- Minimum touch target: 44x44 px.
- Fluid typography and spacing via `clamp()` and tokenized scales.
- Table-to-card responsive behavior for data-heavy pages.
- Accessibility baseline: keyboard-first navigation, visible focus, WCAG AA contrast.
- Performance budgets on mobile profiles before release.

## 6. User Journeys and Acceptance Targets

### Journey J1: Tenant Login
- User can authenticate and land on dashboard in <= 30 seconds.
- Session survives refresh and expires safely.
- Unauthorized access to protected routes is blocked.

### Journey J2: Collect Current Month Invoices (Gmail/Outlook)
- User can choose provider(s), trigger a run, and see status progression.
- Failures are explicit and retryable.
- Run produces files and parse outputs linked to run details.

### Journey J3: Create Reports (Totals, VAT, PDF)
- User can create report from selected scope.
- User can track status and download artifacts (JSON/CSV/SUMMARY/PDF).
- Report totals and VAT are visible in UI summary.

### Journey J4: Tenant Configuration
- User can configure providers, test connection, and rotate/revoke credentials.
- Connection health is visible without opening logs.

### Journey J5: Daily Scheduled Collection
- User can create/edit/pause/resume daily schedule.
- User can see next run time, last run status, and run history.

### Journey J6: Operational Confidence (Added)
- User can inspect activity timeline with request IDs.
- User can export a support bundle for failed runs.

## 7. Epics, Topics, and Concrete Tasks

## Epic E1: Frontend Foundation

| ID | Topic | Task | Dependency | Acceptance Criteria |
|---|---|---|---|---|
| FE-001 | Repo structure | Create `apps/web` workspace with Vite + TS | none | `npm run dev`, `build`, `test` succeed |
| FE-002 | Quality gates | Add ESLint, Prettier, TypeScript strict mode | FE-001 | CI fails on lint/type errors |
| FE-003 | App shell | Implement layout, nav, route guard skeleton | FE-001 | Protected routes blocked without session |
| FE-004 | API client | Generate typed client from OpenAPI | FE-001 | Client compiles and is used in one page |
| FE-005 | Error handling | Add global error boundary and fallback states | FE-003 | Unhandled UI errors render safe fallback |
| FE-006 | Design tokens | Add color/spacing/type tokens and dark-safe contrast | FE-003 | Tokens used across all base components |
| FE-007 | CI | Add frontend test/build steps to CI pipeline | FE-002 | PR requires green frontend checks |

## Epic E2: Auth and Tenant User Model

| ID | Topic | Task | Dependency | Acceptance Criteria |
|---|---|---|---|---|
| BE-001 | Backend auth | Add user/session model and auth endpoints | none | `/auth/*` and `/v1/me` endpoints available |
| FE-101 | Login UX | Build login screen and protected route flow | BE-001 | User can login/logout; refresh keeps session |
| FE-102 | RBAC UX | Role-aware navigation and action-level permissions | FE-101 | Restricted actions hidden/blocked by role |
| FE-103 | Session security | Implement secure token storage and renew flow | FE-101 | Session expiry handled gracefully |
| FE-104 | Auth tests | Add unit/integration/e2e tests for auth flow | FE-101 | Login journey e2e is stable in CI |

## Epic E3: Provider Configuration (Gmail/Outlook)

| ID | Topic | Task | Dependency | Acceptance Criteria |
|---|---|---|---|---|
| BE-101 | Provider domain | Add provider config model and CRUD endpoints | BE-001 | Tenant-scoped provider records persisted |
| BE-102 | OAuth lifecycle | Add OAuth start/callback/refresh/revoke endpoints | BE-101 | End-to-end provider connect works |
| FE-201 | Provider settings | Build provider list, connect, disconnect, re-auth UI | BE-102 | User sees current connection state |
| FE-202 | Health indicators | Show token health and last sync metadata | BE-102 | Health state visible without raw logs |
| FE-203 | Provider tests | Add tests for provider connect/disconnect flows | FE-201 | Both Gmail and Outlook paths pass e2e |

## Epic E4: Invoice Collection Runs

| ID | Topic | Task | Dependency | Acceptance Criteria |
|---|---|---|---|---|
| BE-201 | Collection jobs | Add `collection_jobs` model and APIs | BE-102 | Run lifecycle persisted (`queued/running/succeeded/failed`) |
| BE-202 | Orchestration | Wire collection jobs to provider executors and parse pipeline | BE-201 | Run creates files and parse jobs |
| FE-301 | Collect wizard | Build "Collect current month" wizard with provider selector | BE-201 | User starts run in <= 3 clicks |
| FE-302 | Run detail | Build run progress page with statuses and errors | FE-301 | Status updates visible until completion |
| FE-303 | Retry UX | Add retry action and idempotency-safe behavior | BE-202 | Retry creates expected new run state |
| FE-304 | Collection tests | Add e2e coverage for successful and failed runs | FE-301 | CI validates happy + failure path |

## Epic E5: Reports and Financial Summary UX

| ID | Topic | Task | Dependency | Acceptance Criteria |
|---|---|---|---|---|
| FE-401 | Report builder | Build report creation flow with format selection | existing report APIs | User can create report from selected scope |
| FE-402 | Report status | Build report list/detail with live status updates | FE-401 | Status transitions visible and accurate |
| FE-403 | Artifact download | Add downloads for JSON/CSV/SUMMARY/PDF | FE-402 | All available artifacts downloadable |
| FE-404 | Totals/VAT cards | Render totals/VAT summary cards from report data | FE-402 | Totals match backend report response |
| FE-405 | Report tests | Add integration and e2e tests for report journey | FE-401 | Report journey stable in CI |

## Epic E6: Scheduling (Daily Runs)

| ID | Topic | Task | Dependency | Acceptance Criteria |
|---|---|---|---|---|
| BE-301 | Schedule model | Add schedule entities and CRUD endpoints | BE-201 | Schedules persist with timezone |
| BE-302 | Scheduler runtime | Add scheduler worker trigger and run linkage | BE-301 | Scheduled run executes at configured time |
| FE-501 | Schedule UI | Build create/edit/pause/resume schedule pages | BE-301 | User manages schedule without CLI |
| FE-502 | History UI | Show next run, last run, and schedule run history | FE-501 | History page shows accurate status timeline |
| FE-503 | Scheduling tests | Add e2e for schedule creation and execution visibility | FE-501 | Daily schedule flow passes in CI |

## Epic E7: Observability and Traceability

| ID | Topic | Task | Dependency | Acceptance Criteria |
|---|---|---|---|---|
| BE-401 | Audit query API | Add tenant-scoped audit events list/filter endpoint | existing audit writes | UI can query traceable activity |
| FE-601 | Telemetry standard | Define frontend event taxonomy and naming | FE-001 | Event dictionary approved and versioned |
| FE-602 | FE instrumentation | Add OTel spans and Sentry error instrumentation | FE-601 | Errors/traces visible in monitoring stack |
| FE-603 | Request correlation | Propagate and display `X-Request-ID` in key screens | FE-301 | Support can trace UI action to backend request |
| FE-604 | Activity timeline | Build activity timeline with filters and event details | BE-401 | Users can trace key actions chronologically |
| FE-605 | Support bundle | Add export of diagnostics for failed runs | FE-603 | Bundle includes request IDs and key state |

## Epic E8: Quality, Accessibility, and Release

| ID | Topic | Task | Dependency | Acceptance Criteria |
|---|---|---|---|---|
| FE-701 | Testing pyramid | Enforce unit/integration/e2e minimum matrix | FE-001 | Required test matrix in CI |
| FE-702 | Coverage gate | Enforce >=80% frontend coverage | FE-701 | CI blocks below threshold |
| FE-703 | Accessibility gate | Add automated a11y tests and manual checklist | FE-003 | No P1/P2 accessibility violations |
| FE-704 | Performance gate | Add Lighthouse mobile budgets and regression checks | FE-003 | Mobile perf budget met on key pages |
| FE-705 | Release checklist | Add go-live checklist and rollback runbook | FE-701 | Release checklist completed before launch |

## 8. Sprint Plan (10 Weeks)

| Sprint | Focus | Planned IDs |
|---|---|---|
| Week 1 | Foundation setup | FE-001..FE-007 |
| Week 2 | Auth baseline | BE-001, FE-101..FE-104 |
| Week 3 | Provider backend + UI | BE-101, BE-102, FE-201..FE-203 |
| Week 4 | Collection run backend + UI | BE-201, FE-301, FE-302 |
| Week 5 | Collection hardening | BE-202, FE-303, FE-304 |
| Week 6 | Reporting UX | FE-401..FE-405 |
| Week 7 | Scheduling backend + UI | BE-301, FE-501, FE-502 |
| Week 8 | Scheduling runtime + tests | BE-302, FE-503 |
| Week 9 | Observability and traceability | BE-401, FE-601..FE-605 |
| Week 10 | Quality hardening + release readiness | FE-701..FE-705 |

## 9. Delivery Metrics

- Frontend test coverage: >=80%.
- E2E pass rate on critical journeys: >=99% in CI.
- Mobile Lighthouse score (Performance/Accessibility/Best Practices): >=85 on key screens.
- Time to complete first report from login (staging): <=10 minutes.
- Traceability: 100% of critical actions expose request ID and audit event.

## 10. Risks and Mitigations

- Risk: auth and provider backend readiness delays frontend.
- Mitigation: parallelize FE mock-driven development using MSW + OpenAPI mocks.

- Risk: OAuth token expiry causes unstable daily runs.
- Mitigation: add connection health checks, proactive re-auth prompts, and runbook.

- Risk: complex data tables degrade mobile usability.
- Mitigation: mobile card views and progressive disclosure for details.

- Risk: observability implemented too late.
- Mitigation: telemetry and request ID standards mandatory from first vertical slice.

## 11. Immediate Next Actions (No Coding Yet)

1. Approve stack and sprint plan.
2. Freeze API contracts for `auth`, `providers`, `collection_jobs`, `schedules`, `audit query`.
3. Create issue tracker tickets from IDs above.
4. Start Week 1 with FE-001..FE-007.
