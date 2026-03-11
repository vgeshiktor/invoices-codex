#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/validate_pr.sh \
    --repo <owner/repo> \
    --pr <number> \
    [--expected-issues "#8,owner/repo#12"] \
    [--design-docs "docs/contracts/AUTH_WEEK2_CONTRACT.md,docs/contracts/AUTH_WEEK2_MIGRATION_SCOPE.md"] \
    [--traceability-file docs/qa/PR_TRACEABILITY_RULES_TEMPLATE.json] \
    [--output docs/qa/PR_<number>_VALIDATION_REPORT.md] \
    [--strict]

Description:
  Validates a PR against the 14 governance gates from
  docs/qa/PR_VALIDATION_REQUIREMENTS_TEMPLATE.md and generates
  a Markdown validation report.

Requirements:
  - gh CLI authenticated for target repo
  - jq
USAGE
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

to_lc() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

md_escape() {
  local s="${1:-}"
  s="${s//$'\n'/<br>}"
  s="${s//|/\\|}"
  printf '%s' "$s"
}

normalize_issue_ref() {
  local raw="$1"
  raw="$(trim "$raw")"
  if [[ "$raw" =~ ^#[0-9]+$ ]]; then
    printf '%s/%s%s' "$TARGET_OWNER" "$TARGET_REPO" "$raw"
  elif [[ "$raw" =~ ^[0-9]+$ ]]; then
    printf '%s/%s#%s' "$TARGET_OWNER" "$TARGET_REPO" "$raw"
  elif [[ "$raw" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[0-9]+$ ]]; then
    printf '%s' "$raw"
  else
    return 1
  fi
}

array_contains() {
  local needle="$1"
  shift
  local x
  for x in "$@"; do
    [[ "$x" == "$needle" ]] && return 0
  done
  return 1
}

has_kw_ref_in_text_lc() {
  local text_lc="$1"
  local full_ref="$2"
  local ref_repo="${full_ref%#*}"
  local ref_number="${full_ref##*#}"
  local kw
  for kw in closes fixes resolves; do
    if [[ "$ref_repo" == "$TARGET_OWNER/$TARGET_REPO" ]]; then
      if [[ "$text_lc" == *"$kw #$ref_number"* ]] || [[ "$text_lc" == *"$kw $ref_repo#$ref_number"* ]]; then
        return 0
      fi
    else
      if [[ "$text_lc" == *"$kw $ref_repo#$ref_number"* ]]; then
        return 0
      fi
    fi
  done
  return 1
}

set_gate() {
  local idx="$1"
  local status="$2"
  local evidence="$3"
  GATE_STATUS["$idx"]="$status"
  GATE_EVIDENCE["$idx"]="$evidence"
}

REPO=""
PR_NUMBER=""
EXPECTED_ISSUES_RAW=""
DESIGN_DOCS_RAW=""
TRACEABILITY_FILE=""
OUTPUT=""
STRICT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --pr)
      PR_NUMBER="${2:-}"
      shift 2
      ;;
    --expected-issues)
      EXPECTED_ISSUES_RAW="${2:-}"
      shift 2
      ;;
    --design-docs)
      DESIGN_DOCS_RAW="${2:-}"
      shift 2
      ;;
    --traceability-file)
      TRACEABILITY_FILE="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT="${2:-}"
      shift 2
      ;;
    --strict)
      STRICT=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$REPO" || -z "$PR_NUMBER" ]]; then
  usage
  exit 1
fi

if [[ ! "$REPO" =~ ^[^/]+/[^/]+$ ]]; then
  echo "--repo must be in <owner>/<repo> format." >&2
  exit 1
fi

if [[ ! "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
  echo "--pr must be a numeric PR number." >&2
  exit 1
fi

TARGET_OWNER="${REPO%%/*}"
TARGET_REPO="${REPO##*/}"
TODAY="$(date +%F)"
OUTPUT="${OUTPUT:-docs/qa/PR_${PR_NUMBER}_VALIDATION_REPORT.md}"

require_cmd gh
require_cmd jq

if [[ -n "$TRACEABILITY_FILE" && ! -f "$TRACEABILITY_FILE" ]]; then
  echo "Traceability file not found: $TRACEABILITY_FILE" >&2
  exit 1
fi

PR_JSON="$(gh pr view "$PR_NUMBER" --repo "$REPO" --json number,title,body,url,headRefName,baseRefName,author,isDraft,mergeable,mergeStateStatus,reviewDecision,commits,files,reviews,statusCheckRollup,closingIssuesReferences)"
THREADS_JSON="$(gh api graphql -f query='query($owner:String!, $repo:String!, $number:Int!){ repository(owner:$owner,name:$repo){ pullRequest(number:$number){ reviewThreads(first:100){ nodes{ isResolved comments(first:20){ nodes{ author{ login } path } } } } } } }' -F owner="$TARGET_OWNER" -F repo="$TARGET_REPO" -F number="$PR_NUMBER")"
DIFF_FILE="$(mktemp)"
trap 'rm -f "$DIFF_FILE"' EXIT
gh pr diff "$PR_NUMBER" --repo "$REPO" >"$DIFF_FILE"

TITLE="$(jq -r '.title // ""' <<<"$PR_JSON")"
BODY="$(jq -r '.body // ""' <<<"$PR_JSON")"
BODY_LC="$(to_lc "$BODY")"
PR_URL="$(jq -r '.url' <<<"$PR_JSON")"
MERGEABLE="$(jq -r '.mergeable // "UNKNOWN"' <<<"$PR_JSON")"
MERGE_STATE="$(jq -r '.mergeStateStatus // "UNKNOWN"' <<<"$PR_JSON")"
FILES_COUNT="$(jq -r '.files | length' <<<"$PR_JSON")"
COMMIT_COUNT="$(jq -r '.commits | length' <<<"$PR_JSON")"
FILES_LIST="$(jq -r '.files[]?.path' <<<"$PR_JSON")"
COMMIT_HEADLINES="$(jq -r '.commits[]?.messageHeadline' <<<"$PR_JSON")"
COMMIT_TEXT="$(jq -r '[.commits[]? | .messageHeadline, (.messageBody // "")] | join("\n")' <<<"$PR_JSON")"
COMBINED_TEXT="${BODY}"$'\n'"${COMMIT_TEXT}"
COMBINED_TEXT_LC="$(to_lc "$COMBINED_TEXT")"

declare -a GATE_STATUS
declare -a GATE_EVIDENCE
declare -a GATE_NAMES=(
  ""
  "PR title format matches team convention"
  "PR summary follows documentation guidelines"
  "Commit messages follow naming convention"
  "Reviewer guide exists and is actionable"
  "File-level changes are scoped/aligned"
  "Linked issues are correct"
  "Linked issues are complete"
  "Sourcery review findings resolved"
  "Codex review findings resolved"
  "PR summary lists resolved issues with closing keywords"
  "Closing keyword exists in PR body or commits"
  "Cross-repo issues use full form when needed"
  "All checks are green"
  "No conflicts with base branch"
)

# Gate 1: title format
if [[ "$TITLE" =~ ^\[(FE|BE)-[0-9]{3,}\][[:space:]].+ ]]; then
  set_gate 1 "PASS" "Title: $TITLE"
else
  set_gate 1 "FAIL" "Title does not match expected format [FE-xxx]/[BE-xxx]: $TITLE"
fi

# Gate 2: PR summary structure (problem/design/tests/rollout-risk)
missing_core=()
[[ "$BODY_LC" == *"problem statement"* ]] || missing_core+=("Problem Statement")
[[ "$BODY_LC" == *"design notes"* ]] || missing_core+=("Design Notes")
[[ "$BODY_LC" == *"testing"* ]] || missing_core+=("Testing")
if [[ "$BODY_LC" != *"rollout / risk notes"* && "$BODY_LC" != *"rollout/risk notes"* ]]; then
  missing_core+=("Rollout/Risk Notes")
fi
if [[ ${#missing_core[@]} -eq 0 ]]; then
  set_gate 2 "PASS" "Required sections found: problem, design, testing, rollout/risk."
else
  set_gate 2 "FAIL" "Missing required sections: $(IFS=', '; echo "${missing_core[*]}")"
fi

# Gate 3: commit naming
invalid_commits=()
while IFS= read -r h; do
  [[ -z "$h" ]] && continue
  if grep -Eq '^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]+\))?:[[:space:]].+' <<<"$h"; then
    continue
  fi
  if grep -Eq '^\[(FE|BE)-[0-9]{3,}\][[:space:]].+' <<<"$h"; then
    continue
  fi
  invalid_commits+=("$h")
done <<<"$COMMIT_HEADLINES"
if [[ ${#invalid_commits[@]} -eq 0 ]]; then
  set_gate 3 "PASS" "All commit headlines match convention."
else
  set_gate 3 "FAIL" "Non-conforming commit headlines: $(IFS=' ; '; echo "${invalid_commits[*]}")"
fi

# Gate 4: reviewer guide
if [[ "$BODY_LC" == *"reviewer guide"* || "$BODY_LC" == *"review guide"* ]]; then
  set_gate 4 "PASS" "Reviewer guide section found."
else
  set_gate 4 "FAIL" "Reviewer guide section not found in PR body."
fi

# Gate 5: file-level scope
TOP_FILES="$(jq -r '.files[:12][]? | "\(.path) (+\(.additions)/-\(.deletions))"' <<<"$PR_JSON")"
if [[ "$FILES_COUNT" -eq 0 ]]; then
  set_gate 5 "FAIL" "No file changes detected."
elif [[ "$FILES_COUNT" -le 120 ]]; then
  set_gate 5 "PASS" "Changed files: $FILES_COUNT. Top files: $(tr '\n' ';' <<<"$TOP_FILES" | sed 's/;*$//')"
else
  set_gate 5 "FAIL" "PR changes $FILES_COUNT files (scope appears too large)."
fi

declare -a EXPECTED_ISSUES_RAW_ARR=()
declare -a DESIGN_DOCS=()
if [[ -n "$EXPECTED_ISSUES_RAW" ]]; then
  IFS=',' read -r -a __tmp_expected <<<"$EXPECTED_ISSUES_RAW"
  for token in "${__tmp_expected[@]}"; do
    token="$(trim "$token")"
    [[ -n "$token" ]] && EXPECTED_ISSUES_RAW_ARR+=("$token")
  done
fi
if [[ -n "$DESIGN_DOCS_RAW" ]]; then
  IFS=',' read -r -a __tmp_docs <<<"$DESIGN_DOCS_RAW"
  for token in "${__tmp_docs[@]}"; do
    token="$(trim "$token")"
    [[ -n "$token" ]] && DESIGN_DOCS+=("$token")
  done
fi

declare -a EXPECTED_ISSUES=()
for issue_ref in "${EXPECTED_ISSUES_RAW_ARR[@]:-}"; do
  if normalized="$(normalize_issue_ref "$issue_ref")"; then
    EXPECTED_ISSUES+=("$normalized")
  else
    echo "Warning: could not normalize expected issue ref '$issue_ref'; ignoring." >&2
  fi
done

declare -a CLOSING_ISSUES=()
while IFS= read -r ref; do
  [[ -n "$ref" ]] && CLOSING_ISSUES+=("$ref")
done < <(jq -r '.closingIssuesReferences[]? | "\(.repository.owner.login)/\(.repository.name)#\(.number)"' <<<"$PR_JSON")

# Gate 6/7: linked issue correctness/completeness
extra_issues=()
missing_issues=()
if [[ ${#EXPECTED_ISSUES[@]} -eq 0 ]]; then
  set_gate 6 "N/A" "No --expected-issues provided."
  set_gate 7 "N/A" "No --expected-issues provided."
else
  for actual in "${CLOSING_ISSUES[@]:-}"; do
    if ! array_contains "$actual" "${EXPECTED_ISSUES[@]}"; then
      extra_issues+=("$actual")
    fi
  done
  for expected in "${EXPECTED_ISSUES[@]}"; do
    if ! array_contains "$expected" "${CLOSING_ISSUES[@]:-}"; then
      missing_issues+=("$expected")
    fi
  done

  if [[ ${#extra_issues[@]} -eq 0 ]]; then
    set_gate 6 "PASS" "No unexpected linked issues."
  else
    set_gate 6 "FAIL" "Unexpected linked issues: $(IFS=', '; echo "${extra_issues[*]}")"
  fi

  if [[ ${#missing_issues[@]} -eq 0 ]]; then
    set_gate 7 "PASS" "All expected issues are linked."
  else
    set_gate 7 "FAIL" "Missing expected linked issues: $(IFS=', '; echo "${missing_issues[*]}")"
  fi
fi

# Gate 8/9: bot review threads resolved
SOURCERY_TOTAL="$(jq -r '[.data.repository.pullRequest.reviewThreads.nodes[]? | {resolved: .isResolved, authors: ([.comments.nodes[]?.author.login // "" ] | map(ascii_downcase))} | select([.authors[] | contains("sourcery")] | any)] | length' <<<"$THREADS_JSON")"
SOURCERY_OPEN="$(jq -r '[.data.repository.pullRequest.reviewThreads.nodes[]? | {resolved: .isResolved, authors: ([.comments.nodes[]?.author.login // "" ] | map(ascii_downcase))} | select([.authors[] | contains("sourcery")] | any) | select(.resolved == false)] | length' <<<"$THREADS_JSON")"

if [[ "$SOURCERY_TOTAL" -eq 0 ]]; then
  set_gate 8 "N/A" "No Sourcery review threads found."
elif [[ "$SOURCERY_OPEN" -eq 0 ]]; then
  set_gate 8 "PASS" "All Sourcery threads resolved ($SOURCERY_TOTAL/$SOURCERY_TOTAL)."
else
  set_gate 8 "FAIL" "Unresolved Sourcery threads: $SOURCERY_OPEN of $SOURCERY_TOTAL."
fi

CODEX_TOTAL="$(jq -r '[.data.repository.pullRequest.reviewThreads.nodes[]? | {resolved: .isResolved, authors: ([.comments.nodes[]?.author.login // "" ] | map(ascii_downcase))} | select([.authors[] | contains("codex")] | any)] | length' <<<"$THREADS_JSON")"
CODEX_OPEN="$(jq -r '[.data.repository.pullRequest.reviewThreads.nodes[]? | {resolved: .isResolved, authors: ([.comments.nodes[]?.author.login // "" ] | map(ascii_downcase))} | select([.authors[] | contains("codex")] | any) | select(.resolved == false)] | length' <<<"$THREADS_JSON")"

if [[ "$CODEX_TOTAL" -eq 0 ]]; then
  set_gate 9 "N/A" "No Codex review threads found."
elif [[ "$CODEX_OPEN" -eq 0 ]]; then
  set_gate 9 "PASS" "All Codex threads resolved ($CODEX_TOTAL/$CODEX_TOTAL)."
else
  set_gate 9 "FAIL" "Unresolved Codex threads: $CODEX_OPEN of $CODEX_TOTAL."
fi

# Gate 10: summary includes all linked issues with closing keywords
if [[ ${#CLOSING_ISSUES[@]} -eq 0 ]]; then
  set_gate 10 "FAIL" "No closing issue references found in PR metadata."
else
  missing_kw_refs=()
  for linked in "${CLOSING_ISSUES[@]}"; do
    if ! has_kw_ref_in_text_lc "$BODY_LC" "$linked"; then
      missing_kw_refs+=("$linked")
    fi
  done
  if [[ ${#missing_kw_refs[@]} -eq 0 ]]; then
    set_gate 10 "PASS" "All linked issues are listed with closing keywords in PR body."
  else
    set_gate 10 "FAIL" "Missing closing-keyword references in PR body for: $(IFS=', '; echo "${missing_kw_refs[*]}")"
  fi
fi

# Gate 11: any closing keyword in body or commits
if grep -Eiq '(closes|fixes|resolves)[[:space:]]+([[:alnum:]_.-]+/[[:alnum:]_.-]+)?#[0-9]+' <<<"$COMBINED_TEXT"; then
  set_gate 11 "PASS" "Closing keyword reference found in PR body/commits."
else
  set_gate 11 "FAIL" "No closing keyword reference found in PR body or commits."
fi

# Gate 12: cross-repo full form for cross-repo linked issues
cross_repo_refs=()
for linked in "${CLOSING_ISSUES[@]:-}"; do
  if [[ "${linked%#*}" != "$TARGET_OWNER/$TARGET_REPO" ]]; then
    cross_repo_refs+=("$linked")
  fi
done
if [[ ${#cross_repo_refs[@]} -eq 0 ]]; then
  set_gate 12 "N/A" "No cross-repo linked issues."
else
  bad_cross=()
  for ref in "${cross_repo_refs[@]}"; do
    if ! has_kw_ref_in_text_lc "$COMBINED_TEXT_LC" "$ref"; then
      bad_cross+=("$ref")
    fi
  done
  if [[ ${#bad_cross[@]} -eq 0 ]]; then
    set_gate 12 "PASS" "All cross-repo links use full owner/repo#number format with closing keywords."
  else
    set_gate 12 "FAIL" "Cross-repo issues missing full-form closing refs: $(IFS=', '; echo "${bad_cross[*]}")"
  fi
fi

# Gate 13: all checks green
CHECK_COUNT="$(jq -r '[.statusCheckRollup[]?] | length' <<<"$PR_JSON")"
CHECK_FAILS="$(jq -r '
  [
    .statusCheckRollup[]? |
    if .__typename == "CheckRun" then
      (if (.status != "COMPLETED" or .conclusion != "SUCCESS") then "\(.name): \(.status)/\(.conclusion // "UNKNOWN")" else empty end)
    elif .__typename == "StatusContext" then
      (if .state != "SUCCESS" then "\(.context): \(.state)" else empty end)
    else
      empty
    end
  ] | .[]
' <<<"$PR_JSON")"
if [[ "$CHECK_COUNT" -eq 0 ]]; then
  set_gate 13 "FAIL" "No checks reported in statusCheckRollup."
elif [[ -z "$CHECK_FAILS" ]]; then
  set_gate 13 "PASS" "All checks passed ($CHECK_COUNT checks)."
else
  set_gate 13 "FAIL" "Failing/non-success checks: $(tr '\n' ';' <<<"$CHECK_FAILS" | sed 's/;*$//')"
fi

# Gate 14: no conflicts with base branch
if [[ "$MERGEABLE" == "MERGEABLE" && "$MERGE_STATE" == "CLEAN" ]]; then
  set_gate 14 "PASS" "mergeable=$MERGEABLE, mergeStateStatus=$MERGE_STATE"
else
  set_gate 14 "FAIL" "mergeable=$MERGEABLE, mergeStateStatus=$MERGE_STATE"
fi

# PR body required sections report
declare -a REQUIRED_SECTIONS=(
  "Problem Statement"
  "Linked Issues"
  "Summary"
  "Design Notes"
  "Reviewer Guide"
  "Testing"
  "Rollout / Risk Notes"
)
missing_sections=()
for sec in "${REQUIRED_SECTIONS[@]}"; do
  sec_lc="$(to_lc "$sec")"
  if [[ "$BODY_LC" != *"$sec_lc"* ]]; then
    missing_sections+=("$sec")
  fi
done
if [[ ${#missing_sections[@]} -eq 0 ]]; then
  CONTENT_STATUS="PASS"
  CONTENT_EVIDENCE="All required PR body sections found."
else
  CONTENT_STATUS="FAIL"
  CONTENT_EVIDENCE="Missing sections: $(IFS=', '; echo "${missing_sections[*]}")"
fi

# Design/contract traceability
TRACE_ROWS=""
declare -a TRACE_STATUSES=()

if [[ -n "$TRACEABILITY_FILE" ]]; then
  rule_count="$(jq -r '.requirements | length' "$TRACEABILITY_FILE")"
  if [[ "$rule_count" == "0" ]]; then
    TRACE_ROWS+="| (traceability file) | No requirements defined | N/A | - | - |\n"
    TRACE_STATUSES+=("N/A")
  else
    while IFS= read -r rule; do
      source_doc="$(jq -r '.source // "(unspecified)"' <<<"$rule")"
      requirement="$(jq -r '.requirement // "(unspecified requirement)"' <<<"$rule")"
      scope="$(jq -r '.scope // "all"' <<<"$rule")"
      on_missing="$(jq -r '(.on_missing // "FAIL") | ascii_upcase' <<<"$rule")"
      notes="$(jq -r '.notes // ""' <<<"$rule")"
      fixed_status="$(jq -r '(.status // "") | ascii_upcase' <<<"$rule")"

      if [[ -n "$fixed_status" ]]; then
        status="$fixed_status"
        evidence="Fixed status from rule."
      else
        corpus=""
        case "$scope" in
          diff)
            corpus="$(cat "$DIFF_FILE")"
            ;;
          body)
            corpus="$BODY"
            ;;
          files)
            corpus="$FILES_LIST"
            ;;
          commits)
            corpus="$COMMIT_TEXT"
            ;;
          all|*)
            corpus="$(cat "$DIFF_FILE")"$'\n'"$BODY"$'\n'"$FILES_LIST"$'\n'"$COMMIT_TEXT"
            ;;
        esac

        matched_pattern=""
        while IFS= read -r pattern; do
          [[ -z "$pattern" ]] && continue
          if grep -Eiq -- "$pattern" <<<"$corpus"; then
            matched_pattern="$pattern"
            break
          fi
        done < <(jq -r '.patterns[]? // empty' <<<"$rule")

        if [[ -n "$matched_pattern" ]]; then
          status="PASS"
          evidence="Matched pattern: $matched_pattern"
        else
          status="$on_missing"
          evidence="No pattern matched in scope '$scope'."
        fi
      fi

      TRACE_STATUSES+=("$status")
      TRACE_ROWS+="| $(md_escape "$source_doc") | $(md_escape "$requirement") | $status | $(md_escape "$evidence") | $(md_escape "$notes") |\n"
    done < <(jq -c '.requirements[]' "$TRACEABILITY_FILE")
  fi
elif [[ ${#DESIGN_DOCS[@]} -gt 0 ]]; then
  for doc in "${DESIGN_DOCS[@]}"; do
    status="PARTIAL"
    evidence_parts=()
    notes=""
    if [[ -f "$doc" ]]; then
      evidence_parts+=("doc exists")
    else
      status="FAIL"
      evidence_parts+=("doc missing in repo")
    fi
    if grep -Fxq "$doc" <<<"$FILES_LIST"; then
      evidence_parts+=("doc changed in PR")
      [[ "$status" != "FAIL" ]] && status="PASS"
    fi
    if [[ "$BODY" == *"$doc"* ]]; then
      evidence_parts+=("doc referenced in PR body")
      [[ "$status" != "FAIL" ]] && status="PASS"
    fi
    if [[ "$status" == "PARTIAL" ]]; then
      notes="Provide --traceability-file for requirement-level validation."
    fi
    TRACE_STATUSES+=("$status")
    TRACE_ROWS+="| $(md_escape "$doc") | Document-level coverage heuristic | $status | $(md_escape "$(IFS='; '; echo "${evidence_parts[*]}")") | $(md_escape "$notes") |\n"
  done
else
  TRACE_ROWS+="| (none provided) | No design docs specified | N/A | - | Pass --design-docs and optional --traceability-file for content validation |\n"
  TRACE_STATUSES+=("N/A")
fi

# Summaries
governance_pass=0
governance_fail=0
governance_na=0
for i in $(seq 1 14); do
  case "${GATE_STATUS[$i]}" in
    PASS) governance_pass=$((governance_pass + 1)) ;;
    FAIL) governance_fail=$((governance_fail + 1)) ;;
    *) governance_na=$((governance_na + 1)) ;;
  esac
done

trace_fail=0
trace_deferred_or_partial=0
for s in "${TRACE_STATUSES[@]}"; do
  case "$s" in
    FAIL) trace_fail=$((trace_fail + 1)) ;;
    PARTIAL|DEFERRED) trace_deferred_or_partial=$((trace_deferred_or_partial + 1)) ;;
  esac
done

overall="PASS"
decision="Approved to merge"
if [[ "$governance_fail" -gt 0 || "$CONTENT_STATUS" == "FAIL" || "$trace_fail" -gt 0 ]]; then
  overall="FAIL"
  decision="Not ready to merge"
elif [[ "$trace_deferred_or_partial" -gt 0 ]]; then
  overall="PASS WITH DEFERRED ITEMS"
  decision="Approved to merge with tracked deferred items"
fi

mkdir -p "$(dirname "$OUTPUT")"

{
  echo "# PR Validation Report"
  echo
  echo "Date: $TODAY  "
  echo "PR: $PR_URL  "
  echo "Repository: $REPO"
  echo
  echo "## Inputs"
  echo "- PR Number: $PR_NUMBER"
  echo "- Base/Head: $(jq -r '.baseRefName + " <- " + .headRefName' <<<"$PR_JSON")"
  if [[ ${#EXPECTED_ISSUES[@]} -gt 0 ]]; then
    echo "- Expected issues: $(IFS=', '; echo "${EXPECTED_ISSUES[*]}")"
  else
    echo "- Expected issues: (not provided)"
  fi
  if [[ ${#DESIGN_DOCS[@]} -gt 0 ]]; then
    echo "- Design docs: $(IFS=', '; echo "${DESIGN_DOCS[*]}")"
  else
    echo "- Design docs: (not provided)"
  fi
  if [[ -n "$TRACEABILITY_FILE" ]]; then
    echo "- Traceability rules: $TRACEABILITY_FILE"
  else
    echo "- Traceability rules: (not provided)"
  fi
  echo
  echo "## A) PR Governance Checklist (14 Gates)"
  echo
  echo "| # | Validation Item | Status | Evidence |"
  echo "|---|---|---|---|"
  for i in $(seq 1 14); do
    printf '| %s | %s | %s | %s |\n' \
      "$i" \
      "$(md_escape "${GATE_NAMES[$i]}")" \
      "${GATE_STATUS[$i]}" \
      "$(md_escape "${GATE_EVIDENCE[$i]}")"
  done
  echo
  echo "## B) PR Body Content Requirements"
  echo
  echo "- Status: $CONTENT_STATUS"
  echo "- Evidence: $CONTENT_EVIDENCE"
  echo
  echo "## C) Design/Contract Traceability Matrix"
  echo
  echo "| Requirement Source | Requirement | Status | Evidence in PR | Notes |"
  echo "|---|---|---|---|---|"
  printf '%b' "$TRACE_ROWS"
  echo
  echo "## D) Linked Issue Validation"
  echo
  echo "### Expected Issues from Scope"
  if [[ ${#EXPECTED_ISSUES[@]} -eq 0 ]]; then
    echo "- (none provided)"
  else
    for issue in "${EXPECTED_ISSUES[@]}"; do
      echo "- $issue"
    done
  fi
  echo
  echo "### Found in PR (Closing References)"
  if [[ ${#CLOSING_ISSUES[@]} -eq 0 ]]; then
    echo "- (none)"
  else
    for issue in "${CLOSING_ISSUES[@]}"; do
      echo "- $issue"
    done
  fi
  echo
  echo "## E) Review Findings Closure"
  echo
  echo "### Sourcery"
  echo "- Total threads: $SOURCERY_TOTAL"
  echo "- Open threads: $SOURCERY_OPEN"
  echo "- Status: ${GATE_STATUS[8]}"
  echo
  echo "### Codex"
  echo "- Total threads: $CODEX_TOTAL"
  echo "- Open threads: $CODEX_OPEN"
  echo "- Status: ${GATE_STATUS[9]}"
  echo
  echo "## F) CI and Mergeability"
  echo
  echo "- Status checks: $CHECK_COUNT"
  echo "- Checks gate: ${GATE_STATUS[13]} (${GATE_EVIDENCE[13]})"
  echo "- Mergeability gate: ${GATE_STATUS[14]} (${GATE_EVIDENCE[14]})"
  echo
  echo "## G) Final Verdict"
  echo
  echo "- Overall: $overall"
  echo "- Governance gates: $governance_pass passed, $governance_fail failed, $governance_na n/a (out of 14)"
  echo "- Content completeness: $CONTENT_STATUS"
  echo "- Design traceability fails: $trace_fail"
  echo "- Design traceability deferred/partial: $trace_deferred_or_partial"
  echo "- Decision: $decision"
} >"$OUTPUT"

echo "Validation report written to: $OUTPUT"
echo "Overall status: $overall"

if [[ "$STRICT" -eq 1 && "$overall" == "FAIL" ]]; then
  exit 1
fi
