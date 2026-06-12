#!/usr/bin/env bash
# Tests for scripts/codex_cloud_setup.sh
#
# Usage: bash tests/test_codex_cloud_setup.sh
#
# Each test function sets up a temporary directory that mimics a repo root,
# copies the script into it, and asserts the expected exit code / output.

set -euo pipefail

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts/codex_cloud_setup.sh"

# ── Helpers ──────────────────────────────────────────────────────────────────

PASS=0
FAIL=0
ERRORS=()

pass() { printf '[PASS] %s\n' "$1"; PASS=$((PASS + 1)); }
fail() { printf '[FAIL] %s\n' "$1"; FAIL=$((FAIL + 1)); ERRORS+=("$1"); }

# Create a temp directory that looks like the repo root expected by the script.
# $1 – space-separated list of files to create (relative to fake root).
# Returns the path in $FAKE_ROOT.
make_fake_repo() {
  local files=("$@")
  FAKE_ROOT="$(mktemp -d)"
  # The script lives at <root>/scripts/codex_cloud_setup.sh
  mkdir -p "$FAKE_ROOT/scripts"
  cp "$SCRIPT_PATH" "$FAKE_ROOT/scripts/codex_cloud_setup.sh"
  chmod +x "$FAKE_ROOT/scripts/codex_cloud_setup.sh"
  for f in "${files[@]}"; do
    mkdir -p "$FAKE_ROOT/$(dirname "$f")"
    touch "$FAKE_ROOT/$f"
  done
}

cleanup_fake_repo() {
  [[ -n "${FAKE_ROOT:-}" ]] && rm -rf "$FAKE_ROOT"
}

# ── Test cases ────────────────────────────────────────────────────────────────

# 1. Both required files present → exit 0
test_both_files_present_exits_zero() {
  make_fake_repo "README.md" "docs/iphone-local-dev-setup.md"
  local exit_code=0
  bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" >/dev/null 2>&1 || exit_code=$?
  if [[ $exit_code -eq 0 ]]; then
    pass "both required files present → exits 0"
  else
    fail "both required files present → exits 0 (got exit code $exit_code)"
  fi
  cleanup_fake_repo
}

# 2. Both required files present → success message on stdout
test_both_files_present_success_message() {
  make_fake_repo "README.md" "docs/iphone-local-dev-setup.md"
  local output
  output=$(bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" 2>/dev/null)
  if echo "$output" | grep -qF 'No dependency installation required. Documentation files are present.'; then
    pass "both files present → success message printed to stdout"
  else
    fail "both files present → success message printed to stdout (output: $output)"
  fi
  cleanup_fake_repo
}

# 3. Both required files present → header line printed
test_header_line_printed() {
  make_fake_repo "README.md" "docs/iphone-local-dev-setup.md"
  local output
  output=$(bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" 2>/dev/null)
  if echo "$output" | grep -qF 'Codex cloud setup for upgraded-fiesta'; then
    pass "header line 'Codex cloud setup for upgraded-fiesta' is printed"
  else
    fail "header line 'Codex cloud setup for upgraded-fiesta' is printed (output: $output)"
  fi
  cleanup_fake_repo
}

# 4. Both required files present → repository path line printed
test_repository_line_printed() {
  make_fake_repo "README.md" "docs/iphone-local-dev-setup.md"
  local output
  output=$(bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" 2>/dev/null)
  if echo "$output" | grep -qF "Repository: $FAKE_ROOT"; then
    pass "repository path line is printed with correct path"
  else
    fail "repository path line is printed with correct path (output: $output)"
  fi
  cleanup_fake_repo
}

# 5. README.md missing → exit 1
test_readme_missing_exits_one() {
  make_fake_repo "docs/iphone-local-dev-setup.md"
  local exit_code=0
  bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" >/dev/null 2>&1 || exit_code=$?
  if [[ $exit_code -eq 1 ]]; then
    pass "README.md missing → exits 1"
  else
    fail "README.md missing → exits 1 (got exit code $exit_code)"
  fi
  cleanup_fake_repo
}

# 6. README.md missing → error message on stderr
test_readme_missing_stderr_message() {
  make_fake_repo "docs/iphone-local-dev-setup.md"
  local stderr_output
  stderr_output=$(bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" 2>&1 >/dev/null || true)
  if echo "$stderr_output" | grep -qF 'Missing required file: README.md'; then
    pass "README.md missing → error message on stderr"
  else
    fail "README.md missing → error message on stderr (stderr: $stderr_output)"
  fi
  cleanup_fake_repo
}

# 7. README.md missing → error NOT printed to stdout
test_readme_missing_no_stdout_error() {
  make_fake_repo "docs/iphone-local-dev-setup.md"
  local stdout_output
  stdout_output=$(bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" 2>/dev/null || true)
  if ! echo "$stdout_output" | grep -qF 'Missing required file'; then
    pass "README.md missing → missing-file error not printed to stdout"
  else
    fail "README.md missing → missing-file error not printed to stdout (stdout: $stdout_output)"
  fi
  cleanup_fake_repo
}

# 8. docs/iphone-local-dev-setup.md missing → exit 1
test_docs_file_missing_exits_one() {
  make_fake_repo "README.md"
  local exit_code=0
  bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" >/dev/null 2>&1 || exit_code=$?
  if [[ $exit_code -eq 1 ]]; then
    pass "docs/iphone-local-dev-setup.md missing → exits 1"
  else
    fail "docs/iphone-local-dev-setup.md missing → exits 1 (got exit code $exit_code)"
  fi
  cleanup_fake_repo
}

# 9. docs/iphone-local-dev-setup.md missing → error message on stderr
test_docs_file_missing_stderr_message() {
  make_fake_repo "README.md"
  local stderr_output
  stderr_output=$(bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" 2>&1 >/dev/null || true)
  if echo "$stderr_output" | grep -qF 'Missing required file: docs/iphone-local-dev-setup.md'; then
    pass "docs/iphone-local-dev-setup.md missing → error message on stderr"
  else
    fail "docs/iphone-local-dev-setup.md missing → error message on stderr (stderr: $stderr_output)"
  fi
  cleanup_fake_repo
}

# 10. Both files missing → exit 1 (script aborts on first missing file)
test_both_files_missing_exits_one() {
  make_fake_repo  # no files
  local exit_code=0
  bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" >/dev/null 2>&1 || exit_code=$?
  if [[ $exit_code -eq 1 ]]; then
    pass "both required files missing → exits 1"
  else
    fail "both required files missing → exits 1 (got exit code $exit_code)"
  fi
  cleanup_fake_repo
}

# 11. Both files missing → success message NOT printed
test_both_files_missing_no_success_message() {
  make_fake_repo
  local stdout_output
  stdout_output=$(bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" 2>/dev/null || true)
  if ! echo "$stdout_output" | grep -qF 'No dependency installation required'; then
    pass "both files missing → success message not printed to stdout"
  else
    fail "both files missing → success message not printed to stdout (stdout: $stdout_output)"
  fi
  cleanup_fake_repo
}

# 12. Only README.md missing while docs file exists → only README error reported
test_only_readme_error_reported_when_readme_missing() {
  make_fake_repo "docs/iphone-local-dev-setup.md"
  local stderr_output
  stderr_output=$(bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" 2>&1 >/dev/null || true)
  if echo "$stderr_output" | grep -qF 'Missing required file: README.md' \
     && ! echo "$stderr_output" | grep -qF 'docs/iphone-local-dev-setup.md'; then
    pass "only README.md error reported when README.md is the first missing file"
  else
    fail "only README.md error reported when README.md is the first missing file (stderr: $stderr_output)"
  fi
  cleanup_fake_repo
}

# 13. Script can be invoked from a different working directory (regression: CWD independence)
test_script_works_from_different_cwd() {
  make_fake_repo "README.md" "docs/iphone-local-dev-setup.md"
  local exit_code=0
  # Invoke from /tmp — the script should cd to repo root itself
  (cd /tmp && bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh") >/dev/null 2>&1 || exit_code=$?
  if [[ $exit_code -eq 0 ]]; then
    pass "script exits 0 when invoked from a different working directory"
  else
    fail "script exits 0 when invoked from a different working directory (exit code $exit_code)"
  fi
  cleanup_fake_repo
}

# 14. Output line order: header before repository before success message
test_output_line_order() {
  make_fake_repo "README.md" "docs/iphone-local-dev-setup.md"
  local output
  output=$(bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" 2>/dev/null)
  local header_line repo_line success_line
  header_line=$(echo "$output" | grep -n 'Codex cloud setup for upgraded-fiesta' | head -1 | cut -d: -f1)
  repo_line=$(echo "$output"   | grep -n 'Repository:'                           | head -1 | cut -d: -f1)
  success_line=$(echo "$output"| grep -n 'No dependency installation required'   | head -1 | cut -d: -f1)
  if [[ -n "$header_line" && -n "$repo_line" && -n "$success_line" \
        && "$header_line" -lt "$repo_line" && "$repo_line" -lt "$success_line" ]]; then
    pass "stdout line order: header < repository < success message"
  else
    fail "stdout line order: header < repository < success message (lines: header=$header_line repo=$repo_line success=$success_line)"
  fi
  cleanup_fake_repo
}

# 15. Boundary: required file exists as a directory (not a regular file) → exit 1
test_readme_is_directory_exits_one() {
  make_fake_repo "docs/iphone-local-dev-setup.md"
  # Create README.md as a directory instead of a file
  mkdir -p "$FAKE_ROOT/README.md"
  local exit_code=0
  bash "$FAKE_ROOT/scripts/codex_cloud_setup.sh" >/dev/null 2>&1 || exit_code=$?
  if [[ $exit_code -eq 1 ]]; then
    pass "README.md exists as a directory (not a regular file) → exits 1"
  else
    fail "README.md exists as a directory (not a regular file) → exits 1 (exit code $exit_code)"
  fi
  rm -rf "$FAKE_ROOT/README.md"
  cleanup_fake_repo
}

# ── Run all tests ─────────────────────────────────────────────────────────────

FAKE_ROOT=""

test_both_files_present_exits_zero
test_both_files_present_success_message
test_header_line_printed
test_repository_line_printed
test_readme_missing_exits_one
test_readme_missing_stderr_message
test_readme_missing_no_stdout_error
test_docs_file_missing_exits_one
test_docs_file_missing_stderr_message
test_both_files_missing_exits_one
test_both_files_missing_no_success_message
test_only_readme_error_reported_when_readme_missing
test_script_works_from_different_cwd
test_output_line_order
test_readme_is_directory_exits_one

# ── Summary ───────────────────────────────────────────────────────────────────

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
if [[ ${#ERRORS[@]} -gt 0 ]]; then
  printf 'Failed tests:\n'
  for e in "${ERRORS[@]}"; do
    printf '  - %s\n' "$e"
  done
  exit 1
fi
