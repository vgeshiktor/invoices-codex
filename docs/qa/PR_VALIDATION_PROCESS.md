# PR Validation Process

Date: 2026-03-18
Scope: enforce the QA/architecture governance and content requirements for every pull request created during the Overview-first SaaS rollout (Wave 5-8).

## Purpose
All PRs must prove compliance with the project’s governance (PR title, reviewer guide, architecture review, linked issues) and design traceability rules captured in `docs/qa/PR_VALIDATION_REQUIREMENTS_TEMPLATE.md`. The validation script at `scripts/validate_pr.sh` automates those checks and outputs a markdown report that becomes part of the PR chapter.

## Required Steps
1. **Prepare the PR metadata**
   - Use the standard team format: titles prefixed with `[FE-xxx]` or `[BE-xxx]`, linked issues documented with closing keywords, and the PR body split into the stated sections (Problem, Summary, Design Notes, Reviewer Guide, Backend/Frontend Architecture Reviews, Testing, Rollout/Risk, Linked Issues).
   - Confirm all touched design docs (Examples: `docs/Web UI Design Review.md`, `docs/Invoices Web UI IA.pdf`, `docs/FRONTEND_WEEK6_EXECUTION_PLAN.md`) are referenced in the PR body’s Design Notes section.
2. **Run the validation script**
   - Example command:
     ```bash
     scripts/validate_pr.sh \
       --repo vgeshiktor/invoices-codex \
       --pr $PR_NUMBER \
       --expected-issues "$ISSUE_LIST" \
       --design-docs "docs/Web UI Design Review.md,docs/Invoices Web UI IA.pdf" \
       --traceability-file docs/qa/PR_TRACEABILITY_RULES_TEMPLATE.json \
       --output docs/qa/PR_${PR_NUMBER}_VALIDATION_REPORT.md \
       --strict
     ```
   - `--expected-issues` must list the issues resolved by this PR, including cross-repo references when applicable (e.g., `owner/repo#123`).
   - `--design-docs` should include the authoritative docs for the impacted page or workflow (Overview, Providers, Reports, etc.).
   - `--traceability-file` remains the same for all PRs. The script will fail fast if any governance gate is marked FAIL.
3. **Commit the validation report**
   - The output file (e.g., `docs/qa/PR_47_VALIDATION_REPORT.md`) must be added to the PR so reviewers can see the gating status.
   - If the report is not PASS, fix the root cause (naming, docs, tests) and rerun the script after rebasing on `origin/main`.
4. **Review handoff**
   - Mention the validation report path in the PR status update comment.
   - QA (Apollo) tracks outstanding validation artifacts and blocks merges when validations fail.

## Enforcement Notes
- Every agent prompt (see `docs/qa/AGENT_NEXT_ISSUE_PROMPT_TEMPLATE.md`) reminds contributors to run this script before opening a PR.
- The CI pipeline should require the presence of `docs/qa/PR_<PR_NUMBER>_VALIDATION_REPORT.md` and exit if the report is missing or indicates FAIL.
- Any architectural or scope deviation must be called out in the `Design Notes` and `Architecture Review` sections of the PR body and reflected in the validation report.
