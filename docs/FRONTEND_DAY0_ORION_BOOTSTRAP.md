# Frontend Day 0 - Orion (FE1)

Prepared on: 2026-03-11
Context: Kickoff Day 0 assignment from `docs/FRONTEND_PARALLEL_EXECUTION_MATRIX.md` (planned kickoff date: 2026-03-10)

## 1. Goal

Prepare a practical bootstrap checklist for creating `apps/web` (Week 1 `FE-001`) and define explicit app-shell acceptance criteria (Week 1 `FE-003`).

## 2. `apps/web` Bootstrap Checklist (`FE-001` readiness)

## 2.1 Pre-bootstrap decisions (must be frozen before scaffolding)

- [ ] Package manager: `npm` (baseline; no existing JS workspace in repo).
- [ ] Runtime baseline: Node.js `20.x` LTS.
- [ ] App stack: React + TypeScript + Vite.
- [ ] Router baseline: React Router.
- [ ] Testing baseline: Vitest + React Testing Library.
- [ ] Working directory: `apps/web`.

## 2.2 Scaffold steps

- [ ] Initialize app workspace in `apps/web` using Vite React TypeScript template.
- [ ] Create scripts in `apps/web/package.json`:
  - [ ] `dev`
  - [ ] `build`
  - [ ] `test`
  - [ ] `lint`
  - [ ] `typecheck`
- [ ] Add starter folder structure:
  - [ ] `src/app`
  - [ ] `src/pages`
  - [ ] `src/components`
  - [ ] `src/routes`
  - [ ] `src/lib`
- [ ] Add base shell files:
  - [ ] `src/main.tsx`
  - [ ] `src/App.tsx`
  - [ ] `src/routes/router.tsx`

## 2.3 Validation commands (must pass locally)

- [ ] `cd apps/web && npm install`
- [ ] `cd apps/web && npm run dev`
- [ ] `cd apps/web && npm run build`
- [ ] `cd apps/web && npm run test`
- [ ] `cd apps/web && npm run lint`
- [ ] `cd apps/web && npm run typecheck`

## 2.4 CI integration checklist (handoff to FE-002/FE-007 owners)

- [ ] Add Node setup (`node-version: 20`) in `.github/workflows/ci.yml`.
- [ ] Add dependency install step for `apps/web`.
- [ ] Add frontend checks in CI (lint, typecheck, test, build).
- [ ] Ensure frontend checks fail PRs on violations.

## 2.5 Day-1 completion evidence template

- [ ] Attach terminal output proving `dev/build/test` pass.
- [ ] Attach screenshot of app running locally.
- [ ] Link PR closing `FE-001`.

## 3. App-Shell Acceptance Criteria (`FE-003`)

Use these criteria as testable acceptance conditions for implementation and QA sign-off.

### AC-001 Layout frame

- App renders a persistent shell with `Header`, `Primary Navigation`, and `Main Content` regions.
- Shell is visible on all protected routes.

### AC-002 Navigation behavior

- Primary nav includes at least placeholder links for Week 1/2 core areas (`Dashboard`, `Providers`, `Collections`, `Reports`, `Settings`).
- Active route is visually distinguishable.
- Unknown routes resolve to a safe fallback route/page.

### AC-003 Protected route gate (stub auth allowed)

- A protected route wrapper exists and checks auth state from a single source (`auth store/context`).
- Unauthenticated users are redirected to a public entry route (Week 1 stub is acceptable).
- Attempted direct navigation to protected URLs while unauthenticated is blocked.

### AC-004 State transitions

- Transition from unauthenticated -> authenticated updates the guard without page reload.
- Transition from authenticated -> unauthenticated routes user out of protected pages.

### AC-005 Accessibility baseline

- Keyboard users can reach header/nav/main landmarks.
- Focus is visible on nav links and primary actions.
- Color contrast for shell text and interactive states meets WCAG AA baseline.

### AC-006 Responsive baseline

- Shell is usable at widths: `360`, `768`, and `1024` (minimum).
- Navigation remains accessible on mobile (collapsed menu or equivalent).
- No horizontal scrolling in shell chrome on mobile viewport.

### AC-007 Error-safe behavior

- Route guard failures do not crash the app; a safe fallback state is shown.
- Invalid auth state (missing/expired placeholder token) is handled as unauthenticated.

### AC-008 Test coverage minimum for FE-003

- At least one integration test verifies protected-route blocking.
- At least one integration test verifies successful render of shell after auth state is set.
- At least one test verifies unauthenticated redirect behavior.

## 4. Week 1 Handoff Notes

- `FE-001`: this checklist is execution-ready for Monday implementation.
- `FE-003`: acceptance criteria above should be copied into issue/PR checklist.
- `FE-007`: CI checklist section can be reused directly when wiring required checks.
