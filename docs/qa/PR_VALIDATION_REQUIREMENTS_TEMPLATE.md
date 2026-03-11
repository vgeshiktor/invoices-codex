# PR Validation Requirements and Template

Date: `<YYYY-MM-DD>`
PR: `<https://github.com/<owner>/<repo>/pull/<number>>`
Issue(s): `<#123, #124 or owner/repo#123>`

## Purpose

Use this template to validate any PR against:

1. Process/governance quality gates.
2. Content completeness required by project docs.
3. Design/contract traceability (what was planned vs what was implemented).

---

## A) Validation Inputs (Required)

- Target PR number and URL.
- Base branch and head branch.
- Linked issues (expected list).
- Applicable design docs (PRD, contract, ADR, migration scope, architecture docs).
- Required CI checks for the repo.

---

## B) PR Governance Checklist (14 Gates)

Mark each item `PASS` / `FAIL` / `N/A` and add evidence.

| # | Validation Item | Status | Evidence |
|---|---|---|---|
| 1 | PR title format matches team convention (for example `[FE-123] ...` / `[BE-123] ...`) | `<PASS/FAIL/N/A>` | `<title + rule reference>` |
| 2 | PR summary follows documentation guidelines (`problem`, `design`, `tests`, `rollout/risk`) | `<PASS/FAIL/N/A>` | `<PR body section evidence>` |
| 3 | Commit messages follow naming convention (conventional commits or team standard) | `<PASS/FAIL/N/A>` | `<commit examples>` |
| 4 | Reviewer guide exists and is actionable | `<PASS/FAIL/N/A>` | `<section + review order>` |
| 5 | File-level changes are scoped and aligned with PR goal | `<PASS/FAIL/N/A>` | `<key files + rationale>` |
| 6 | Linked issues are correct (right issue IDs) | `<PASS/FAIL/N/A>` | `<issue map>` |
| 7 | Linked issues are complete (no missing issue from scope) | `<PASS/FAIL/N/A>` | `<expected vs actual list>` |
| 8 | Sourcery review findings resolved | `<PASS/FAIL/N/A>` | `<thread status>` |
| 9 | Codex review findings resolved | `<PASS/FAIL/N/A>` | `<thread status>` |
| 10 | PR summary lists all resolved issues with closing keywords | `<PASS/FAIL/N/A>` | `<Closes/Fixes/Resolves lines>` |
| 11 | Closing keyword exists in PR body or commit message | `<PASS/FAIL/N/A>` | `<exact location>` |
| 12 | Cross-repo issues use full form (`Closes owner/repo#123`) | `<PASS/FAIL/N/A>` | `<body/commit evidence>` |
| 13 | All checks are green | `<PASS/FAIL/N/A>` | `<check run names + states>` |
| 14 | No conflicts with base branch (mergeable cleanly) | `<PASS/FAIL/N/A>` | `<mergeable + merge state>` |

---

## C) PR Body Content Requirements

Required sections:

- Problem Statement
- Linked Issues
- Summary
- Design Notes
- Reviewer Guide
- Testing
- Rollout / Risk Notes

Status: `<PASS/FAIL>`
Missing sections: `<list or none>`

---

## D) Design/Contract Traceability Matrix

Add one row per key requirement from design documents.

| Requirement Source | Requirement | Status (`PASS/PARTIAL/FAIL/DEFERRED/N/A`) | Evidence in PR | Notes |
|---|---|---|---|---|
| `<doc path + section>` | `<requirement text>` | `<status>` | `<file/path/test/check>` | `<deviation/risk>` |
| `<doc path + section>` | `<requirement text>` | `<status>` | `<file/path/test/check>` | `<deviation/risk>` |

Status meanings:

- `PASS`: fully implemented and verified by code/tests.
- `PARTIAL`: partially implemented; remainder identified.
- `DEFERRED`: intentionally postponed and documented.
- `FAIL`: required but missing or contradictory.
- `N/A`: not applicable to this PR.

---

## E) Linked Issue Validation

### Expected Issues from Scope

- `<#123>`
- `<#124>`

### Found in PR (closing references)

- `<#123>`
- `<owner/repo#124>`

### Result

- Correctness: `<PASS/FAIL>`
- Completeness: `<PASS/FAIL>`
- Gap list: `<missing/extra links>`

---

## F) Review Findings Closure

### Sourcery

- Open threads: `<count>`
- Resolved threads: `<count>`
- Unresolved high-priority findings: `<list or none>`
- Status: `<PASS/FAIL>`

### Codex

- Open threads: `<count>`
- Resolved threads: `<count>`
- Unresolved high-priority findings: `<list or none>`
- Status: `<PASS/FAIL>`

---

## G) CI and Mergeability

- Required checks list:
  - `<check-1>`
  - `<check-2>`
- Current check status: `<all green / failing checks>`
- Mergeability: `<MERGEABLE/CONFLICTING/UNKNOWN>`
- Base up-to-date requirement met: `<yes/no>`

Status: `<PASS/FAIL>`

---

## H) Risks, Deviations, and Follow-ups

| Type | Description | Severity (`P0-P3`) | Owner | Tracking Issue |
|---|---|---|---|---|
| `<risk/deviation>` | `<details>` | `<P0-P3>` | `<name>` | `<#issue>` |

---

## I) Final Verdict

Overall: `<PASS / PASS WITH DEFERRED ITEMS / FAIL>`

Summary:

- Governance gates: `<x>/14 passed`
- Content completeness: `<PASS/FAIL>`
- Design traceability: `<PASS/PARTIAL/FAIL>`
- Blocking gaps: `<none or list>`

Decision:

- `<Approved to merge>` or `<Not ready to merge>`

---

## Optional: Quick CLI Evidence Commands

```bash
# PR overview (title/body/commits/files/checks/issues)
gh pr view <PR_NUMBER> --repo <owner>/<repo> \
  --json title,body,commits,files,statusCheckRollup,closingIssuesReferences,mergeable,mergeStateStatus,reviews

# Check runs
gh pr checks <PR_NUMBER> --repo <owner>/<repo>

# Review thread resolution status
gh api graphql -f query='
query($owner:String!, $repo:String!, $number:Int!){
  repository(owner:$owner,name:$repo){
    pullRequest(number:$number){
      reviewThreads(first:100){
        nodes{
          isResolved
          comments(first:10){ nodes{ author{ login } path } }
        }
      }
    }
  }
}' -F owner=<owner> -F repo=<repo> -F number=<PR_NUMBER>
```

## Optional: Automated Validation Script

```bash
scripts/validate_pr.sh \
  --repo <owner>/<repo> \
  --pr <PR_NUMBER> \
  --expected-issues "#123,owner/repo#124" \
  --design-docs "docs/contracts/CONTRACT.md,docs/contracts/MIGRATION_SCOPE.md" \
  --traceability-file docs/qa/PR_TRACEABILITY_RULES_TEMPLATE.json \
  --output docs/qa/PR_<PR_NUMBER>_VALIDATION_REPORT.md
```

Use `--strict` to return non-zero exit code when final verdict is `FAIL`.
