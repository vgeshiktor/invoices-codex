#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Sync imported frontend issues into a GitHub Project v2 and set fields:
Status / Owner / Week.

Usage:
  scripts/sync_frontend_project_fields.sh \
    --project-number <number> \
    [--project-owner <owner>] \
    [--repo <owner/repo>] \
    [--issue-pack <path>] \
    [--status-option <name>] \
    [--dry-run]

Options:
  --project-number   Required. GitHub Project number.
  --project-owner    Project owner login (user/org). Default: repo owner.
  --repo             Repository in owner/name format. Default: current repo from gh.
  --issue-pack       Path to issue pack markdown. Default: docs/FRONTEND_GITHUB_ISSUES.md
  --status-option    Initial Status field option. Default: Todo
  --dry-run          Print intended actions without mutating GitHub.
  -h, --help         Show help.

Notes:
  - Requires gh auth with "project" scope:
      gh auth refresh -s project
  - Issues must already exist in GitHub (run import_frontend_github_issues.sh first).
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ISSUE_PACK="$REPO_ROOT/docs/FRONTEND_GITHUB_ISSUES.md"

REPO="${REPO:-}"
PROJECT_OWNER="${PROJECT_OWNER:-}"
PROJECT_NUMBER=""
STATUS_OPTION="Todo"
DRY_RUN=0

while (($#)); do
  case "$1" in
    --project-number)
      PROJECT_NUMBER="$2"
      shift 2
      ;;
    --project-owner)
      PROJECT_OWNER="$2"
      shift 2
      ;;
    --repo)
      REPO="$2"
      shift 2
      ;;
    --issue-pack)
      ISSUE_PACK="$2"
      shift 2
      ;;
    --status-option)
      STATUS_OPTION="$2"
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

if [[ -z "$PROJECT_NUMBER" ]]; then
  echo "--project-number is required." >&2
  usage
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required: https://cli.github.com/" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required." >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh is not authenticated. Run: gh auth login" >&2
  exit 1
fi

if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
fi

if [[ -z "$PROJECT_OWNER" ]]; then
  PROJECT_OWNER="${REPO%%/*}"
fi

if [[ ! -f "$ISSUE_PACK" ]]; then
  echo "Issue pack not found: $ISSUE_PACK" >&2
  exit 1
fi

owner_for_issue_id() {
  case "$1" in
    BE-001|BE-101|BE-201|BE-301|BE-401) echo "Nebula" ;;
    BE-102|BE-202|BE-302) echo "Andromeda" ;;
    FE-001|FE-003|FE-005|FE-101|FE-201|FE-301|FE-401|FE-402|FE-501|FE-601|FE-602|FE-604) echo "Orion" ;;
    FE-002|FE-004|FE-006|FE-102|FE-103|FE-202|FE-302|FE-303|FE-403|FE-404|FE-502|FE-603|FE-605|FE-703|FE-704) echo "Vega" ;;
    FE-007|FE-104|FE-203|FE-304|FE-405|FE-503|FE-701|FE-702|FE-705) echo "Apollo" ;;
    *) echo "" ;;
  esac
}

parse_issue_pack() {
  awk -v OFS='\t' '
    function flush_issue() {
      if (id != "" && title != "" && milestone != "") {
        print id, title, milestone
      }
    }
    /^### / {
      flush_issue()
      id = substr($0, 5)
      gsub(/[[:space:]]+$/, "", id)
      title = ""
      milestone = ""
      next
    }
    /^Title:/ {
      if (match($0, /`[^`]+`/)) {
        title = substr($0, RSTART + 1, RLENGTH - 2)
      }
      next
    }
    /^Milestone:/ {
      if (match($0, /`[^`]+`/)) {
        milestone = substr($0, RSTART + 1, RLENGTH - 2)
      }
      next
    }
    END { flush_issue() }
  ' "$ISSUE_PACK"
}

log_cmd() {
  printf '%q ' "$@"
  printf '\n'
}

run_or_echo() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] '
    log_cmd "$@"
  else
    "$@"
  fi
}

PROJECT_VIEW_JSON="$(gh project view "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --format json)"
PROJECT_ID="$(jq -r '.id // empty' <<<"$PROJECT_VIEW_JSON")"
if [[ -z "$PROJECT_ID" ]]; then
  echo "Unable to resolve project id for project $PROJECT_OWNER/$PROJECT_NUMBER" >&2
  exit 1
fi

FIELDS_JSON="$(gh project field-list "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" -L 200 --format json)"

get_field_id() {
  local field_name="$1"
  jq -r --arg n "$field_name" '[.[] | select(.name == $n)][0].id // empty' <<<"$FIELDS_JSON"
}

create_single_select_field() {
  local field_name="$1"
  local options_csv="$2"
  run_or_echo gh project field-create "$PROJECT_NUMBER" \
    --owner "$PROJECT_OWNER" \
    --name "$field_name" \
    --data-type SINGLE_SELECT \
    --single-select-options "$options_csv" >/dev/null
  if [[ "$DRY_RUN" -ne 1 ]]; then
    FIELDS_JSON="$(gh project field-list "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" -L 200 --format json)"
  fi
}

ensure_single_select_field() {
  local field_name="$1"
  local options_csv="$2"
  local field_id
  field_id="$(get_field_id "$field_name")"
  if [[ -n "$field_id" ]]; then
    echo "$field_id"
    return 0
  fi
  echo "Field '$field_name' is missing. Creating it..."
  create_single_select_field "$field_name" "$options_csv"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo ""
    return 0
  fi
  field_id="$(get_field_id "$field_name")"
  if [[ -z "$field_id" ]]; then
    echo "Failed to create project field '$field_name'." >&2
    exit 1
  fi
  echo "$field_id"
}

get_option_id() {
  local field_name="$1"
  local option_name="$2"
  jq -r --arg f "$field_name" --arg o "$option_name" '
    .[] | select(.name == $f) | (.options // [])[] | select(.name == $o) | .id
  ' <<<"$FIELDS_JSON" | head -n1
}

resolve_status_option_id() {
  local preferred="$1"
  local candidate
  for candidate in \
    "$preferred" \
    "Todo" \
    "To do" \
    "Backlog" \
    "No Status" \
    "Planned"
  do
    local opt_id
    opt_id="$(get_option_id "Status" "$candidate")"
    if [[ -n "$opt_id" ]]; then
      echo "$opt_id"
      return 0
    fi
  done
  echo ""
}

echo "Repository: $REPO"
echo "Project: $PROJECT_OWNER/$PROJECT_NUMBER"
echo "Issue pack: $ISSUE_PACK"
echo

# Ensure custom fields (Week/Owner) exist.
OWNER_FIELD_ID="$(ensure_single_select_field "Owner" "Nebula,Andromeda,Orion,Vega,Apollo")"
WEEK_FIELD_ID="$(ensure_single_select_field "Week" "Week 1,Week 2,Week 3,Week 4,Week 5,Week 6,Week 7,Week 8,Week 9,Week 10")"

# Ensure status exists (built-in on most projects). Create if missing.
STATUS_FIELD_ID="$(get_field_id "Status")"
if [[ -z "$STATUS_FIELD_ID" ]]; then
  echo "Status field is missing. Creating custom Status field..."
  create_single_select_field "Status" "Todo,In Progress,Blocked,In Review,Done"
  if [[ "$DRY_RUN" -ne 1 ]]; then
    STATUS_FIELD_ID="$(get_field_id "Status")"
  fi
fi

if [[ "$DRY_RUN" -ne 1 ]]; then
  STATUS_OPTION_ID="$(resolve_status_option_id "$STATUS_OPTION")"
  if [[ -z "$STATUS_OPTION_ID" ]]; then
    echo "Could not resolve Status option '$STATUS_OPTION' on field 'Status'." >&2
    exit 1
  fi
else
  STATUS_OPTION_ID=""
fi

PARSED_FILE="$(mktemp)"
ENRICHED_FILE="$(mktemp)"
trap 'rm -f "$PARSED_FILE" "$ENRICHED_FILE"' EXIT

parse_issue_pack > "$PARSED_FILE"
if [[ ! -s "$PARSED_FILE" ]]; then
  echo "No issues parsed from $ISSUE_PACK" >&2
  exit 1
fi

ISSUES_JSON="$(gh issue list --repo "$REPO" --state all --limit 1000 --json number,title,url)"

TOTAL=0
MISSING=0
ADDED=0
SKIPPED_ALREADY=0

echo "Adding issues to project and building assignment table..."
while IFS=$'\t' read -r issue_id issue_title issue_week; do
  TOTAL=$((TOTAL + 1))
  owner_value="$(owner_for_issue_id "$issue_id")"
  if [[ -z "$owner_value" ]]; then
    echo "  - skip (no owner mapping): $issue_id"
    MISSING=$((MISSING + 1))
    continue
  fi

  issue_row="$(jq -r --arg t "$issue_title" '.[] | select(.title == $t) | [.number, .url] | @tsv' <<<"$ISSUES_JSON" | head -n1)"
  if [[ -z "$issue_row" ]]; then
    echo "  - missing issue in repo (title mismatch): $issue_title"
    MISSING=$((MISSING + 1))
    continue
  fi

  issue_number="$(cut -f1 <<<"$issue_row")"
  issue_url="$(cut -f2 <<<"$issue_row")"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  - [dry-run] add to project: #$issue_number $issue_id ($owner_value / $issue_week)"
  else
    if add_out="$(gh project item-add "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --url "$issue_url" 2>&1)"; then
      ADDED=$((ADDED + 1))
      :
    else
      if grep -qi "already exists" <<<"$add_out"; then
        SKIPPED_ALREADY=$((SKIPPED_ALREADY + 1))
      else
        echo "Failed to add issue to project: $issue_url" >&2
        echo "$add_out" >&2
        exit 1
      fi
    fi
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$issue_id" "$issue_title" "$issue_week" "$owner_value" "$issue_number" "$issue_url" >> "$ENRICHED_FILE"
done < "$PARSED_FILE"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo
  echo "Dry-run complete. No GitHub changes were made."
  echo "Parsed issues: $TOTAL"
  echo "Missing mappings/issues: $MISSING"
  exit 0
fi

ITEMS_JSON="$(gh project item-list "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" -L 1000 --format json)"

set_field_value() {
  local item_id="$1"
  local field_id="$2"
  local option_id="$3"
  gh project item-edit \
    --id "$item_id" \
    --project-id "$PROJECT_ID" \
    --field-id "$field_id" \
    --single-select-option-id "$option_id" >/dev/null
}

UPDATED=0
echo
echo "Updating project fields (Status/Owner/Week)..."
while IFS=$'\t' read -r issue_id issue_title issue_week owner_value issue_number issue_url; do
  item_id="$(jq -r --arg url "$issue_url" '
    .[] | select((.content.url // "") == $url) | .id
  ' <<<"$ITEMS_JSON" | head -n1)"
  if [[ -z "$item_id" ]]; then
    echo "  - skip (item not found in project): #$issue_number $issue_id"
    continue
  fi

  owner_option_id="$(get_option_id "Owner" "$owner_value")"
  week_option_id="$(get_option_id "Week" "$issue_week")"
  if [[ -z "$owner_option_id" || -z "$week_option_id" || -z "$STATUS_OPTION_ID" || -z "$STATUS_FIELD_ID" || -z "$OWNER_FIELD_ID" || -z "$WEEK_FIELD_ID" ]]; then
    echo "  - skip (missing field option ids) for #$issue_number $issue_id" >&2
    continue
  fi

  set_field_value "$item_id" "$STATUS_FIELD_ID" "$STATUS_OPTION_ID"
  set_field_value "$item_id" "$OWNER_FIELD_ID" "$owner_option_id"
  set_field_value "$item_id" "$WEEK_FIELD_ID" "$week_option_id"
  UPDATED=$((UPDATED + 1))
  echo "  - updated: #$issue_number $issue_id -> Status=$STATUS_OPTION Owner=$owner_value Week=$issue_week"
done < "$ENRICHED_FILE"

echo
echo "Done."
echo "Parsed issues: $TOTAL"
echo "Added to project: $ADDED"
echo "Already in project: $SKIPPED_ALREADY"
echo "Updated fields: $UPDATED"
echo "Missing mappings/issues: $MISSING"
