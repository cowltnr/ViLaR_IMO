#!/usr/bin/env bash
set -euo pipefail

secret_pattern='(?i)(AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:api[_-]?key|secret|password|token)\s*[:=]\s*["\x27][^"\x27]+)'
staged_paths_file="$(mktemp)"
staged_blob_file="$(mktemp)"

cleanup() {
  rm -f -- "$staged_paths_file" "$staged_blob_file"
}
trap cleanup EXIT

if ! git diff --cached --name-only -z --diff-filter=ACMR \
  >"$staged_paths_file" 2>/dev/null; then
  printf '%s\n' 'Unable to enumerate staged content for credential scanning.' >&2
  exit 2
fi

secret_found=false
while IFS= read -r -d '' path; do
  if ! git cat-file blob ":$path" >"$staged_blob_file" 2>/dev/null; then
    printf '%s\n' 'Unable to read staged content for credential scanning.' >&2
    exit 2
  fi

  if rg --pcre2 --quiet "$secret_pattern" "$staged_blob_file" \
    >/dev/null 2>&1; then
    secret_found=true
    break
  else
    scanner_status=$?
    if (( scanner_status != 1 )); then
      printf '%s\n' 'Credential scanner failed; staged content was not approved.' >&2
      exit 2
    fi
  fi
done <"$staged_paths_file"

if [[ "$secret_found" == true ]]; then
  printf '%s\n' 'Secret-pattern match found in staged content; remove and revoke it before commit.' >&2
  exit 1
fi
