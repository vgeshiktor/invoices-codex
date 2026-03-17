# MVP Demo Smoke Matrix (QA-201)

Date: 2026-03-17  
Owner: QA (Apollo)  
Issue: #82

## Goal

Provide a repeatable smoke matrix for the Next Small MVP flow:
`login -> providers -> test connection -> dashboard`.

## Smoke Cases

| ID | Type | Preconditions | Steps | Expected Result |
| --- | --- | --- | --- | --- |
| SMK-01 | Happy path | Web app is reachable and auth mocks/fixtures are active | 1. Open app. 2. Login with tenant user. 3. Open Providers page. 4. Verify `Test connection` action is visible. 5. Trigger `Test connection`. 6. Verify the success result panel renders. 7. Open Dashboard and fetch summary. | Login succeeds, providers load, test-connection action is present and callable, result metadata renders, and dashboard summary request succeeds. |
| SMK-02 | Failure path | Web app is reachable | 1. Open login page. 2. Submit wrong password. | User remains on Login page and sees an auth error message (`Invalid credentials`). |

## Automation Mapping

- `apps/web/e2e/mvp-smoke.e2e.spec.ts`:
- `mvp smoke: login -> providers -> test connection -> dashboard` maps to `SMK-01`.
- `mvp smoke failure path: invalid credentials keep user on login` maps to `SMK-02`.
