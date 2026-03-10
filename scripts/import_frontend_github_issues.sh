#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Import frontend milestones/labels/issues into GitHub from docs/FRONTEND_GITHUB_ISSUES.md.

Usage:
  scripts/import_frontend_github_issues.sh [--repo owner/name] [--issue-pack path] [--dry-run]

Options:
  --repo        GitHub repository in owner/name format. Default: current repo from gh.
  --issue-pack  Path to issue pack markdown file.
  --dry-run     Print actions without creating/updating anything.
  -h, --help    Show this help.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ISSUE_PACK="$REPO_ROOT/docs/FRONTEND_GITHUB_ISSUES.md"
REPO="${REPO:-}"
DRY_RUN=0

while (($#)); do
  case "$1" in
    --repo)
      REPO="$2"
      shift 2
      ;;
    --issue-pack)
      ISSUE_PACK="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
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

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required. Install from https://cli.github.com/" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh is not authenticated. Run: gh auth login" >&2
  exit 1
fi

if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
fi

if [[ ! -f "$ISSUE_PACK" ]]; then
  echo "Issue pack not found: $ISSUE_PACK" >&2
  exit 1
fi

parse_issue_pack() {
  awk -v OFS='\t' '
    function flush_issue() {
      if (id != "" && title != "") {
        print id, title, milestone, labels, depends, acceptance
      }
    }
    /^### / {
      flush_issue()
      id = substr($0, 5)
      gsub(/[[:space:]]+$/, "", id)
      title = ""
      milestone = ""
      labels = ""
      depends = ""
      acceptance = ""
      next
    }
    /^Title:/ {
      if (match($0, /`[^`]+`/)) {
        title = substr($0, RSTART + 1, RLENGTH - 2)
      }
      next
    }
    /^Labels:/ {
      labels = ""
      line = $0
      while (match(line, /`[^`]+`/)) {
        label = substr(line, RSTART + 1, RLENGTH - 2)
        labels = labels (labels == "" ? "" : ",") label
        line = substr(line, RSTART + RLENGTH)
      }
      next
    }
    /^Milestone:/ {
      if (match($0, /`[^`]+`/)) {
        milestone = substr($0, RSTART + 1, RLENGTH - 2)
      }
      next
    }
    /^Depends on:/ {
      if (match($0, /`[^`]+`/)) {
        depends = substr($0, RSTART + 1, RLENGTH - 2)
      }
      next
    }
    /^Acceptance Criteria:/ {
      acceptance = $0
      sub(/^Acceptance Criteria:[[:space:]]*/, "", acceptance)
      next
    }
    END {
      flush_issue()
    }
  ' "$ISSUE_PACK"
}

PARSED_FILE="$(mktemp)"
trap 'rm -f "$PARSED_FILE"' EXIT
parse_issue_pack > "$PARSED_FILE"

if [[ ! -s "$PARSED_FILE" ]]; then
  echo "No issues parsed from $ISSUE_PACK" >&2
  exit 1
fi

echo "Repository: $REPO"
echo "Issue pack: $ISSUE_PACK"
echo

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
  else
    "$@"
  fi
}

echo "Step 1/3: Ensure milestones exist (Week 1..Week 10 + parsed milestones)"
EXISTING_MILESTONES="$(gh api "repos/$REPO/milestones?state=all&per_page=100" --paginate -q '.[].title' || true)"

MILESTONE_FILE="$(mktemp)"
trap 'rm -f "$PARSED_FILE" "$MILESTONE_FILE"' EXIT
{
  for week in 1 2 3 4 5 6 7 8 9 10; do
    echo "Week $week"
  done
  cut -f3 "$PARSED_FILE"
} | sed '/^$/d' | sort -u > "$MILESTONE_FILE"

while IFS= read -r milestone; do
  if grep -Fxq "$milestone" <<<"$EXISTING_MILESTONES"; then
    echo "  - exists: $milestone"
    continue
  fi
  echo "  - create: $milestone"
  run_cmd gh api -X POST "repos/$REPO/milestones" -f "title=$milestone" -f state=open >/dev/null
  EXISTING_MILESTONES="${EXISTING_MILESTONES}"$'\n'"$milestone"
done < "$MILESTONE_FILE"

echo
echo "Step 2/3: Ensure labels exist"
EXISTING_LABELS="$(gh label list --repo "$REPO" --limit 1000 --json name -q '.[].name' || true)"

LABEL_FILE="$(mktemp)"
trap 'rm -f "$PARSED_FILE" "$MILESTONE_FILE" "$LABEL_FILE"' EXIT
cut -f4 "$PARSED_FILE" | tr ',' '\n' | sed 's/^ *//; s/ *$//' | sed '/^$/d' | sort -u > "$LABEL_FILE"

while IFS= read -r label; do
  if grep -Fxq "$label" <<<"$EXISTING_LABELS"; then
    echo "  - exists: $label"
    continue
  fi
  echo "  - create: $label"
  run_cmd gh label create "$label" --repo "$REPO" --color BFD4F2 --description "Imported by scripts/import_frontend_github_issues.sh" >/dev/null
  EXISTING_LABELS="${EXISTING_LABELS}"$'\n'"$label"
done < "$LABEL_FILE"

echo
echo "Step 3/3: Create issues from pack (skip existing exact-title matches)"
EXISTING_TITLES="$(gh issue list --repo "$REPO" --state all --limit 1000 --json title -q '.[].title' || true)"

CREATED_COUNT=0
SKIPPED_COUNT=0
TOTAL_COUNT=0

while IFS=$'\t' read -r id title milestone labels depends acceptance; do
  TOTAL_COUNT=$((TOTAL_COUNT + 1))

  if grep -Fxq "$title" <<<"$EXISTING_TITLES"; then
    echo "  - skip existing: $title"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    continue
  fi

  BODY_FILE="$(mktemp)"
  cat > "$BODY_FILE" <<EOF
## ID
$id

## Depends On
$depends

## Acceptance Criteria
$acceptance

## Source
docs/FRONTEND_GITHUB_ISSUES.md
EOF

  issue_cmd=(gh issue create --repo "$REPO" --title "$title" --milestone "$milestone" --body-file "$BODY_FILE")
  IFS=',' read -r -a label_array <<< "$labels"
  for lbl in "${label_array[@]}"; do
    lbl="$(echo "$lbl" | sed 's/^ *//; s/ *$//')"
    if [[ -n "$lbl" ]]; then
      issue_cmd+=(--label "$lbl")
    fi
  done

  echo "  - create: $title"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] '
    printf '%q ' "${issue_cmd[@]}"
    printf '\n'
  else
    "${issue_cmd[@]}" >/dev/null
    CREATED_COUNT=$((CREATED_COUNT + 1))
    EXISTING_TITLES="${EXISTING_TITLES}"$'\n'"$title"
  fi

  rm -f "$BODY_FILE"
done < "$PARSED_FILE"

echo
echo "Done."
echo "Total parsed issues: $TOTAL_COUNT"
echo "Created: $CREATED_COUNT"
echo "Skipped existing: $SKIPPED_COUNT"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry-run mode was enabled; no GitHub changes were made."
fi
