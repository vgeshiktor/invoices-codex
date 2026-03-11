# FE App Shell Acceptance Criteria (`FE-003`)

Prepared by: Orion (FE1)
Prepared on: 2026-03-11
Scope lock: Week 1 (`FE-003`, with alignment to `FE-005` and `FE-006`)
Constraint: route guard is stubbed in Week 1 (real backend auth lands in Week 2).

## 1. Objective

Define testable acceptance criteria for app shell + protected-route skeleton so implementation and QA can sign off consistently.

Authoritative structure note:
- canonical Week 1 file/folder structure is defined in `docs/frontend/FE_WEEK1_BOOTSTRAP_CHECKLIST.md` (Step 3).
- this document defines acceptance criteria and the required FE-003 subset within that structure.

## 2. In Scope

- Shell layout and navigation skeleton.
- Protected-route stub behavior.
- Loading and error state expectations for guarded routes.
- Week 1-level responsiveness and accessibility baseline.

## 3. Out of Scope (Week 1)

- Real login API/session refresh logic (`FE-101+`).
- RBAC action-level restrictions (`FE-102`).
- Production observability instrumentation (`FE-601+`).

## 4. Scope Assumptions for Referenced Issue IDs

- `FE-003`: route shell and protected-route skeleton only (stub auth state allowed).
- `FE-005`: error-boundary compatibility is required, but full FE-005 delivery is separate.
- `FE-006`: token usage compatibility is required, but full token rollout is separate.
- `FE-101+`: real auth/session implementation starts in Week 2.
- `FE-601+`: observability instrumentation starts in Week 9.

## 5. Acceptance Criteria

### AC-01 Layout regions

- App shell renders persistent `Header`, `Navigation`, and `Main` content regions on protected pages.
- Layout frame remains stable during route changes (no full-shell remount).

### AC-02 Navigation baseline

- Navigation renders routes required for skeleton flow (`Dashboard`, placeholder protected areas, `Login`).
- Active route has visible selected state.
- Unknown path routes to `NotFound` or safe default route.

### AC-03 Protected-route stub

- `ProtectedRoute` reads auth state from one stub source (`state/auth.stub.ts` or equivalent).
- If unauthenticated, user is redirected to `Login` route.
- Direct URL access to protected routes while unauthenticated is blocked.

### AC-04 Guard loading state

- Guard exposes a transient loading state while auth status resolves (even if stubbed).
- Loading UI is non-blocking and accessible (`aria-busy` on main container or equivalent).
- No blank white screen during guard resolution.

### AC-05 Guard error state

- Invalid auth stub state (malformed payload/missing expected fields) resolves safely to unauthenticated path.
- Route-level guard exceptions render a safe fallback state with a retry action.
- Error state messaging avoids leaking internal details.

### AC-06 Week 1 global error alignment (`FE-005`)

- Shell routes are compatible with a global error boundary wrapper.
- Fallback view preserves a way back to a known route (`Login` or `Dashboard`).

### AC-07 Baseline responsive behavior

- Shell is usable at widths `360`, `768`, and `1024`.
- Navigation remains reachable on mobile (collapsed menu, drawer, or stacked nav).
- No horizontal overflow in shell chrome at `360` width.

### AC-08 Baseline accessibility behavior

- Keyboard navigation reaches header/nav/main landmarks in logical order.
- Focus ring is visible for interactive nav elements.
- Color contrast for nav text and active state meets WCAG AA baseline.

### AC-09 Test expectations for Week 1

- At least one integration test confirms unauthenticated redirect from protected route.
- At least one integration test confirms authenticated render of shell content.
- At least one integration test confirms guard loading state is rendered.
- At least one integration test confirms guard error fallback path is safe.

## 6. Minimal FE-003 Required Subset (within canonical Week 1 structure)

```text
apps/web/src/
  app/
    App.tsx
    providers.tsx
  components/shell/
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
```

## 7. FE-003 Done Conditions

`FE-003` is done only when:

1. AC-01..AC-05 are implemented and manually verified.
2. AC-07..AC-08 pass manual responsive/a11y smoke checks.
3. AC-09 tests are present and passing in local run.
4. No dependencies beyond Week 1 scope are introduced.
