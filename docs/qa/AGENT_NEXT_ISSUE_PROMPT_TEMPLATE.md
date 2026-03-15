# Agent Next-Issue Prompt Template

Use this template whenever you ask an agent (`nebula`, `vega`, `apollo`, `orion`, `andromeda`) to start the next task.

## Copy/Paste Template

```text
You are <AGENT_NAME> in repo `vgeshiktor/invoices-codex`.

Execute this workflow end-to-end for the next unblocked issue assigned to you.

1) Branch cleanup after merge
- Assume previous PR is merged to `main`.
- Run:
  git checkout main
  git pull origin main
  git branch -d <PREVIOUS_BRANCH> || true
  git push origin --delete <PREVIOUS_BRANCH> || true

2) Select next issue
- Pick the next unblocked issue assigned to <AGENT_NAME> from GitHub Project/plan.
- Keep scope to one issue per PR.
- If more than one issue is available, choose the smallest vertical slice first.

3) Create fresh branch from updated main
- Branch format: `codex/<agent>-<issue-id-lowercase>`
- Run:
  git checkout main
  git pull origin main
  git checkout -b codex/<agent>-<issue-id-lowercase>
  git push -u origin codex/<agent>-<issue-id-lowercase>

4) Implement issue completely
- Follow project architecture and tenant-safety rules.
- Add/update tests (happy path + at least one failure path).
- Update docs/contracts/OpenAPI/ADR when behavior or architecture changes.
- Keep commits conventionally named.
- Avoid merge commits in PR branch history.

5) Open PR with required format
- PR title: `[FE-xxx] ...` or `[BE-xxx] ...`
- PR body must include:
  - Problem Statement
  - Linked Issues (with closing keyword, e.g. `Closes #<issue_number>`)
  - Summary
  - Design Notes
  - Reviewer Guide
  - Backend Architecture Review (`Status: Approved|N/A`, `Reviewed By: ...`)
  - Frontend Architecture Review (`Status: Approved|N/A`, `Reviewed By: ...`)
  - Testing
  - Rollout / Risk Notes

6) Run required PR validation
- Run:
  scripts/validate_pr.sh \
    --repo vgeshiktor/invoices-codex \
    --pr <PR_NUMBER> \
    --expected-issues "#<issue_number>" \
    --design-docs "<relevant_docs_csv>" \
    --traceability-file docs/qa/PR_TRACEABILITY_RULES_TEMPLATE.json \
    --output docs/qa/PR_<PR_NUMBER>_VALIDATION_REPORT.md \
    --strict

7) Resolve issues after validation
- If validation is FAIL:
  - fix all failed gates
  - rebase on latest `origin/main` and fully resolve merge conflicts
  - resolve all open Sourcery/Codex review threads
  - rerun validation
- Repeat until validation report is PASS.

8) Final handoff
- Return:
  - issue selected
  - branch created
  - implementation summary
  - checks/test results
  - PR URL
  - validation report path
  - remaining risks/blockers
```

## Placeholders

- `<AGENT_NAME>`: `nebula`, `vega`, `apollo`, `orion`, `andromeda`
- `<PREVIOUS_BRANCH>`: example `codex/vega` or `codex/nebula-be-101`
- `<agent>`: lowercase agent name
- `<issue-id-lowercase>`: example `fe-004`, `be-101`
- `<issue_number>`: numeric GitHub issue number
- `<relevant_docs_csv>`: comma-separated docs paths used for traceability
