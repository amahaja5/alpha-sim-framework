#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Reject stale references from the pre-split espn-api layout and old command patterns.
PATTERN='/Users/amahajan/src/espn-api|espn_api/utils/|requirements.txt|run_tests.py|python fantasy_decision_maker.py|tests\\.football\\.unit'

if rg -n "$PATTERN" README.md CHANGELOG.md docs/*.md; then
  echo ""
  echo "Found stale documentation references."
  exit 1
fi

echo "Docs reference check passed."
