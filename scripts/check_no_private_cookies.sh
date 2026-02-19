#!/usr/bin/env bash
set -euo pipefail

is_placeholder_value() {
  local value="${1:-}"
  if [[ -z "$value" ]]; then
    return 0
  fi

  local lower
  lower="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"

  if [[ "$lower" == "..." ]]; then
    return 0
  fi

  if [[ "$lower" == \<* && "$lower" == *\> ]]; then
    return 0
  fi

  if [[ "$lower" =~ your|optional|redacted|changeme|example|placeholder|dummy|test ]]; then
    return 0
  fi

  return 1
}

fail=0

while IFS= read -r -d '' file_path; do
  staged_content="$(git show ":${file_path}" 2>/dev/null || true)"
  if [[ -z "$staged_content" ]]; then
    continue
  fi

  while IFS= read -r value; do
    if ! is_placeholder_value "$value"; then
      echo "Blocked: staged file '$file_path' contains a concrete \"swid\" value."
      fail=1
    fi
  done < <(printf '%s\n' "$staged_content" | sed -nE 's/.*"swid"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p')

  while IFS= read -r value; do
    if ! is_placeholder_value "$value"; then
      echo "Blocked: staged file '$file_path' contains a concrete \"espn_s2\" value."
      fail=1
    fi
  done < <(printf '%s\n' "$staged_content" | sed -nE 's/.*"espn_s2"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p')
done < <(git diff --cached --name-only --diff-filter=ACM -z)

if [[ "$fail" -ne 0 ]]; then
  cat <<'EOF'
Commit blocked to prevent leaking ESPN private cookies.
Remove or redact SWID/ESPN_S2 values, then recommit.
EOF
  exit 1
fi

exit 0
