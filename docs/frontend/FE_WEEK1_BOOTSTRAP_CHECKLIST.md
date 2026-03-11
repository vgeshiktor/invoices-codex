# FE Week 1 Bootstrap Checklist (`FE-001` baseline)

Prepared by: Orion (FE1)
Prepared on: 2026-03-11
Scope lock: Week 1 only (`FE-001..FE-007`)
Constraint: Day 0 is planning/spec only. Do not scaffold `apps/web` yet.

## 1. Objective

Provide a step-by-step execution checklist for creating `apps/web` in Week 1 and keeping setup aligned with Week 1 issue sequence.

## 2. Week 1 Dependency Order

1. `FE-001` scaffold app workspace.
2. `FE-002` add quality gates.
3. `FE-004` wire OpenAPI client generation path.
4. `FE-003` implement app shell and protected route skeleton.
5. `FE-005` add global error boundary/fallback.
6. `FE-006` apply tokens/baseline styles.
7. `FE-007` enforce frontend CI checks.

## 3. FE-001 Step-by-Step Checklist

## Step 0: Pre-flight (before coding)

- [ ] Confirm frontend stack: React + TypeScript + Vite.
- [ ] Confirm package manager: `npm`.
- [ ] Confirm Node runtime baseline for CI and local: Node `20.x`.
- [ ] Confirm app path: `apps/web`.

## Step 1: Create app workspace (Day 1 execution)

- [ ] Run scaffold command (planned):
  - `npm create vite@latest apps/web -- --template react-ts`
- [ ] Install dependencies:
  - `cd apps/web && npm install`

## Step 2: Normalize `package.json` scripts

- [ ] Ensure these scripts exist:
  - [ ] `dev`
  - [ ] `build`
  - [ ] `test`
  - [ ] `lint`
  - [ ] `typecheck`
- [ ] Keep script names stable for CI reuse in `FE-007`.

## Step 3: Add Week 1 minimal structure

- [ ] Create architecture skeleton (no feature pages yet):

```text
apps/web/
  public/
  src/
    app/
      App.tsx
      providers.tsx
    components/
      shell/
        AppShell.tsx
        Header.tsx
        SideNav.tsx
    routes/
      index.tsx
      ProtectedRoute.tsx
    pages/
      DashboardPage.tsx
      LoginPage.tsx
      NotFoundPage.tsx
    state/
      auth.stub.ts
    styles/
      tokens.css
      globals.css
    test/
      setup.ts
    main.tsx
  index.html
  package.json
  tsconfig.json
  tsconfig.app.json
  vite.config.ts
```

## Step 4: FE-001 validation gates

- [ ] `cd apps/web && npm run dev` starts without runtime errors.
- [ ] `cd apps/web && npm run build` succeeds.
- [ ] `cd apps/web && npm run test` executes baseline test runner successfully.

## Step 5: Hand-off checkpoints for remaining Week 1 issues

- [ ] `FE-002`: wire ESLint/Prettier/TS strict and keep `lint`/`typecheck` scripts green.
- [ ] `FE-004`: add OpenAPI client generation command using `integrations/openapi/saas-openapi.v0.1.0.json`.
- [ ] `FE-003`: implement shell + protected-route stub using created route/state folders.
- [ ] `FE-005`: wrap shell routes with global error boundary fallback.
- [ ] `FE-006`: apply shared tokens via `styles/tokens.css` and shell components.
- [ ] `FE-007`: run `lint/typecheck/test/build` in CI and fail PR on errors.

## 4. Day 1 Execution Command Sequence (planned, not executed on Day 0)

```bash
cd /Users/vadimgeshiktor/repos/github.com/vgeshiktor/python-projects/invoices-codex
npm create vite@latest apps/web -- --template react-ts
cd apps/web
npm install
npm run dev
npm run build
npm run test
```

## 5. Definition of Ready for Week 1 Start

- [ ] Checklist approved by FE1 + FE2 + QA1.
- [ ] Week 1 issue order (`FE-001..FE-007`) confirmed unchanged.
- [ ] CI owner aligned on script contract (`lint`, `typecheck`, `test`, `build`).
