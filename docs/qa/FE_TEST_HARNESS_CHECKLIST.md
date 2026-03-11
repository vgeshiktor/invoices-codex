# FE Week 1 Test Harness Checklist

Prepared by: Apollo (QA1)
Prepared on: 2026-03-11
Scope lock: Week 1 bootstrap test harness only

## 1. Objective

Define the minimum test harness needed in Week 1 so CI can run stable frontend unit checks now and stage integration/e2e expansion for Week 2+.

## 2. Tooling Baseline (Week 1)

Primary stack:
- Test runner: `Vitest`
- Component testing: `@testing-library/react` + `@testing-library/jest-dom`
- API mocking for unit/integration: `MSW`
- E2E framework (staged): `Playwright`

Runtime baseline:
- Node `20.x` for local + CI.

## 3. Minimal Harness Checklist

### A. Vitest (required in Week 1)

- [ ] Add `vitest` config for `jsdom` environment.
- [ ] Add `test/setup.ts` and register it via `setupFiles`.
- [ ] Ensure CI command runs in non-watch mode (`npm run test -- --run`).
- [ ] Add one smoke unit test for app shell/render baseline.
- [ ] Disable flaky timers/network dependence in default test setup.

Definition of done:
- `npm run test -- --run` passes locally and in CI without watch mode.

### B. React Testing Library (required in Week 1)

- [ ] Install and wire `@testing-library/react`.
- [ ] Install and wire `@testing-library/jest-dom` in setup.
- [ ] Add shared `render` helper if providers/router wrappers are needed.
- [ ] Ensure assertions are user-facing (role/text/label), not implementation-detail snapshots.

Definition of done:
- At least one representative component/app-shell test passes through RTL helpers.

### C. MSW (required as harness baseline in Week 1)

- [ ] Install `msw` and create baseline handlers folder (e.g., `src/test/msw/handlers.ts`).
- [ ] Add server lifecycle hooks in test setup (`listen/resetHandlers/close`).
- [ ] Add one mocked API test path to prove request interception works.
- [ ] Keep handlers deterministic and data fixtures versioned in repo.

Definition of done:
- One Vitest + RTL test uses MSW successfully with no external network dependency.

### D. Playwright (staging plan; not required gate in Week 1)

Week 1 staging tasks:
- [ ] Decide browser matrix for CI start (`chromium` only for first pass).
- [ ] Add placeholder config and `e2e` directory scaffold.
- [ ] Add one non-blocking smoke scenario draft (`login shell reachable` or equivalent).
- [ ] Keep Playwright check optional/non-required until Week 2 auth journey (`FE-104`).

Exit criteria for Week 1 staging:
- Playwright is scaffolded and runnable locally, but **not** a required merge gate yet.

## 4. Week 1 Staging Plan by Day

1. Mon: wire Vitest + RTL setup and one smoke test.
2. Tue: add MSW handlers and one mocked integration-style test.
3. Wed: stabilize deterministic test behavior and command contract.
4. Thu: scaffold Playwright config/spec (non-blocking).
5. Fri: verify CI gate alignment and publish checklist status.

## 5. CI Contract for Harness (Week 1)

Frontend CI in Week 1 must run:
1. `npm run lint`
2. `npm run typecheck`
3. `npm run test -- --run`
4. `npm run build`

Expected behavior:
- Unit tests are required and blocking.
- Playwright remains informational/non-blocking until Week 2 scope.

## 6. Failure Prevention Checklist

- [ ] No real network calls in unit/integration tests (MSW enforced).
- [ ] Avoid time-dependent assertions without explicit clock control.
- [ ] Keep fixtures small and explicit (no random test data).
- [ ] Keep test command deterministic across local and CI.
- [ ] Track flaky tests in a dedicated follow-up issue immediately.

## 7. Required Dependencies

Core:
- `vitest`
- `@vitest/coverage-v8` (recommended for near-term coverage readiness)
- `@testing-library/react`
- `@testing-library/jest-dom`
- `@testing-library/user-event`
- `jsdom`
- `msw`

Staged:
- `@playwright/test`

Install template (Day 1):
- `npm install -D vitest @vitest/coverage-v8 @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom msw @playwright/test`

## 8. Day 1 Harness Implementation Order

1. Wire Vitest config and `test/setup.ts`.
2. Register RTL + `jest-dom` in setup.
3. Add MSW server lifecycle and one mocked API test.
4. Ensure `npm run test -- --run` is green locally.
5. Connect test command to CI matrix required check.
6. Scaffold Playwright as non-blocking placeholder.

## 9. Expected Week 1 Harness Artifacts

Target files to exist by Week 1 close (names may vary slightly by implementation):
- `apps/web/vitest.config.ts`
- `apps/web/src/test/setup.ts`
- `apps/web/src/test/msw/handlers.ts`
- `apps/web/src/test/msw/server.ts`
- `apps/web/src/**/*.test.tsx` (at least one app-shell or route smoke test)
- `apps/web/playwright.config.ts` (staged, non-blocking)
- `apps/web/e2e/smoke.spec.ts` (staged, non-blocking)

## 10. Harness Triage Categories

When frontend tests fail, classify quickly and route action:
1. `HARNESS_CONFIG`: broken setup/config imports, wrong environment, missing setup file.
2. `MOCK_CONTRACT`: MSW handlers out of sync with API contract or fixture shape.
3. `TEST_LOGIC`: assertion or test-flow bug.
4. `APP_REGRESSION`: real UI behavior regression.

Routing guidance:
- `HARNESS_CONFIG` and `MOCK_CONTRACT`: QA1 + FE2 first.
- `TEST_LOGIC`: test author first.
- `APP_REGRESSION`: feature owner first.

## 11. Day 1 Success Criteria (Harness)

1. `npm run test -- --run` passes locally on clean install.
2. CI `frontend / unit` is green using same command.
3. At least one RTL test runs with `jest-dom` assertions.
4. At least one MSW-backed test runs with no external network dependency.
5. Playwright scaffold exists but is non-blocking.
