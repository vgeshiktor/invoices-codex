# MVP Demo Runbook (QA-201)

Date: 2026-03-17  
Owner: QA (Apollo)  
Issue: #82

## Purpose

Run one smoke pack for the MVP demo flow in under 10 minutes.

## Preconditions

1. Branch contains `apps/web/e2e/mvp-smoke.e2e.spec.ts`.
2. Frontend dependencies are installed in `apps/web`.
3. Port `4173` is available.
4. The Playwright harness builds the app before preview, so no separate manual `npm run build` step is required.

## Commands

1. `cd apps/web`
2. `npm run test:e2e -- mvp-smoke.e2e.spec.ts`

## Expected Outcome

1. Failure-path test (`invalid credentials`) passes.
2. Happy-path smoke passes end-to-end.
3. Provider page renders `Test connection`, the action runs once, and a success result panel is shown.
4. Dashboard summary request succeeds after the provider step.

## Fast Triage

1. If login step fails:
2. Check auth route mocks in `mvp-smoke.e2e.spec.ts`.
3. If provider page fails:
4. Check route rendering and provider fixture payload shape.
5. If `Test connection` step fails:
6. Check the stubbed BE-104 response shape in `mvp-smoke.e2e.spec.ts` includes `provider`, `status`, `message`, `tested_at`, and `request_id`.
7. If dashboard step fails:
8. Check `/v1/dashboard/summary` route intercept and dashboard button selector.

## Demo-Day Reference

1. Run `npm run test:e2e -- mvp-smoke.e2e.spec.ts`.
2. Keep this file as the single smoke/demo command reference.
