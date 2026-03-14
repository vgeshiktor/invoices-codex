# MVP Web Demo Kickoff (All Agents)

Updated: 2026-03-14
Owners: Nebula (BE1), Andromeda (BE2), Orion (FE1), Vega (FE2), Apollo (QA1)

## 1. Current State Snapshot (Source: live issue/PR state)

Completed and usable now:

- `#8` `[BE-001]` auth/session backend baseline (CLOSED)
- `#13` `[BE-101]` provider config CRUD backend (CLOSED)
- `#1` `[FE-001]` web workspace scaffold (CLOSED)
- `#4` `[FE-004]` OpenAPI typed client baseline (CLOSED)
- `#7` `[FE-007]` frontend CI lint/type/test/build gates (CLOSED)
- `#40` `[FE-701]` frontend testing pyramid CI gate (CLOSED)
- API demo baseline is available in `docs/STAKEHOLDER_DEMO_RUNBOOK.md`

Still open and required for first web MVP demo:

- Auth/shell: `#3` `[FE-003]`, `#9` `[FE-101]`
- Provider flow: `#14` `[BE-102]`, `#15` `[FE-201]`
- Collection flow: `#18` `[BE-201]`, `#19` `[BE-202]`, `#20` `[FE-301]`, `#21` `[FE-302]`
- Report flow: `#24` `[FE-401]`, `#25` `[FE-402]`, `#26` `[FE-403]`, `#27` `[FE-404]`

## 2. MVP Demo Scope (KISS)

The first stakeholder web demo must show:

1. login in web UI and protected page access
2. provider configuration (at least one provider appears connected)
3. collect current month invoices
4. report creation and totals/VAT visibility
5. report download (JSON/CSV at minimum)

Out of scope for this kickoff:

- schedules (`E6`)
- observability expansion (`E7`) beyond existing dashboard/runbook
- release-hardening bundle (`E8` except already-merged FE-701 baseline)

## 3. Kickoff Plan (Parallel, Next Unblocked Work)

Priority lane A (start immediately):

1. Nebula: `#14` `[BE-102]` provider OAuth lifecycle endpoints
2. Andromeda: `#18` `[BE-201]` collection_jobs model + APIs
3. Orion: `#3` `[FE-003]` app shell + protected route skeleton
4. Vega: `#15` `[FE-201]` provider settings screen (start with mocked contract; wire final integration when `#14` merges)
5. Apollo: run PR governance/quality enforcement on every lane-A PR using `scripts/validate_pr.sh --strict`; publish one validation report per PR under `docs/qa/`

Priority lane B (start as dependencies clear):

1. Orion: `#9` `[FE-101]` login/logout UI + protected-route flow (after `#3`)
2. Andromeda: `#19` `[BE-202]` orchestration from collection jobs to parse pipeline (after `#18`)
3. Vega: `#20` `[FE-301]` collect-current-month wizard (after `#18`)
4. Vega: `#21` `[FE-302]` run detail/progress page (after `#19` + `#20`)
5. Orion + Vega: `#24/#25/#26/#27` report flow once invoice collection path is usable

## 4. Definition Of Done For This Kickoff

This kickoff phase is complete when:

1. Lane A PRs are merged with all required checks green.
2. Lane B has started with no dependency ambiguity.
3. No P0/P1 blockers remain on auth/provider/collection critical path.
4. Demo narrative can be executed in local environment in <= 15 minutes.

## 5. Operating Rules (Do Not Drift)

1. One issue per branch and one PR per issue.
2. Branch naming format: `codex/<agent>-<issue-id-lowercase>`.
3. No merge commits in feature branches.
4. Every PR must pass strict validation:

```bash
scripts/validate_pr.sh \
  --repo vgeshiktor/invoices-codex \
  --pr <PR_NUMBER> \
  --expected-issues "#<ISSUE_NUMBER>" \
  --design-docs "<DOCS_CSV>" \
  --traceability-file docs/qa/PR_TRACEABILITY_RULES_TEMPLATE.json \
  --output docs/qa/PR_<PR_NUMBER>_VALIDATION_REPORT.md \
  --strict
```

## 6. Risk Notes (Current)

- Issue `#58` has been refreshed from this document; keep this file and issue body synchronized when statuses change.
- `#15` FE provider UI depends on finalized behavior from `#14`; Vega can start UI shell but final integration must wait for backend merge.
- Collection and report web flows remain blocked by `#18/#19` backend completion.
