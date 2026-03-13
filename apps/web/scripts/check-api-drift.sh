#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

GENERATED_DIR="src/shared/api/generated"
DRIFT_STATUS="$(git status --porcelain --untracked-files=all -- "$GENERATED_DIR")"

if [[ -n "$DRIFT_STATUS" ]]; then
  echo "Generated API client drift detected:"
  git status --short --untracked-files=all -- "$GENERATED_DIR"
  exit 1
fi
