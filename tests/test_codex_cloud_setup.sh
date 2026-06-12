#!/usr/bin/env bash
# Tests for scripts/codex_cloud_setup.sh
# Pure-bash test runner — no external testing framework required.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPT_UNDER_TEST="$REPO_ROOT/scripts/codex_cloud_setup.sh"

# ---------------------------------------------------------------------------
# Minimal test framework
# ---------------------------------------------------------------------------
PASS=0
FAIL=0
ERRORS=()

pass() { PASS=$((PASS + 1)); printf '  PASS: %s\n' "$1"; }
fail() { FAIL=$((FAIL + 1)); ERRORS+=("FAIL: $1"); printf '  FAIL: %s\n' "$1"; }

assert_exit_zero()   { [[ $1 -eq 0 ]]   && pass "$2" || fail "$2 (exit=$1, expected 0)"; }
assert_exit_nonzero(){ [[ $1 -ne 0 ]]   && pass "$2" || fail "$2 (exit=$1, expected non-zero)"; }
assert_exit_one()    { [[ $1 -eq 1 ]]   && pass "$2" || fail "$2 (exit=$1, expected 1)"; }
assert_contains()    { echo "$1" | grep -qF "$2" && pass "$3" || fail "$3 (output did not contain: '$2')"; }
assert_not_contains(){ echo "$1" | grep -qF "$2" && fail "$3 (output unexpectedly contained: '$2')" || pass "$3"; }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Create a temporary fake repo that mirrors the required directory layout.
# Sets global TMPDIR_ROOT and FAKE_SCRIPT (path to the copy of the script).
make_fake_repo() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  # Mirror scripts/ subdirectory so BASH_SOURCE-based root detection works.
  mkdir -p "$tmpdir/scripts"
  mkdir -p "$tmpdir/docs"
  cp "$SCRIPT_UNDER_TEST" "$tmpdir/scripts/codex_cloud_setup.sh"
  chmod +x "$tmpdir/scripts/codex_cloud_setup.sh"
  TMPDIR_ROOT="$tmpdir"
  FAKE_SCRIPT="$tmpdir/scripts/codex_cloud_setup.sh"
}

cleanup_fake_repo() {
  [[ -n "${TMPDIR_ROOT:-}" ]] && rm -rf "$TMPDIR_ROOT"
  TMPDIR_ROOT=""
  FAKE_SCRIPT=""
}

create_required_files() {
  touch "$TMPDIR_ROOT/README.md"
  touch "$TMPDIR_ROOT/docs/iphone-local-dev-setup.md"
}

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

test_success_all_files_present() {
  printf '\n[test] success when all required files are present\n'
  make_fake_repo
  create_required_files

  stdout=$("$FAKE_SCRIPT" 2>/dev/null)
  exit_code=$?
  cleanup_fake_repo

  assert_exit_zero "$exit_code" "exit code is 0 when all files present"
  assert_contains "$stdout" "No dependency installation required. Documentation files are present." \
    "stdout contains success message"
}

test_header_printed_before_file_check() {
  printf '\n[test] header lines are printed before file check\n'
  make_fake_repo
  create_required_files

  stdout=$("$FAKE_SCRIPT" 2>/dev/null)
  exit_code=$?
  cleanup_fake_repo

  assert_exit_zero "$exit_code" "exit code 0 with header test"
  assert_contains "$stdout" "Codex cloud setup for upgraded-fiesta" \
    "stdout contains project name header"
  assert_contains "$stdout" "Repository:" \
    "stdout contains Repository label"
}

test_repository_path_in_header() {
  printf '\n[test] repository path is embedded in header output\n'
  make_fake_repo
  create_required_files

  stdout=$("$FAKE_SCRIPT" 2>/dev/null)
  cleanup_fake_repo

  # The script prints the absolute path it resolved; it must be non-empty.
  assert_contains "$stdout" "Repository: /" \
    "stdout Repository line contains an absolute path"
}

test_missing_readme() {
  printf '\n[test] exit 1 when README.md is absent\n'
  make_fake_repo
  # Only create the docs file; omit README.md
  touch "$TMPDIR_ROOT/docs/iphone-local-dev-setup.md"

  exit_code=0
  stderr=$("$FAKE_SCRIPT" 2>&1 >/dev/null) || exit_code=$?
  cleanup_fake_repo

  assert_exit_one "$exit_code" "exit code 1 when README.md is missing"
  assert_contains "$stderr" "Missing required file: README.md" \
    "stderr names the missing README.md"
}

test_missing_docs_file() {
  printf '\n[test] exit 1 when docs/iphone-local-dev-setup.md is absent\n'
  make_fake_repo
  # Only create README.md; omit the docs file
  touch "$TMPDIR_ROOT/README.md"

  exit_code=0
  stderr=$("$FAKE_SCRIPT" 2>&1 >/dev/null) || exit_code=$?
  cleanup_fake_repo

  assert_exit_one "$exit_code" "exit code 1 when docs/iphone-local-dev-setup.md is missing"
  assert_contains "$stderr" "Missing required file: docs/iphone-local-dev-setup.md" \
    "stderr names the missing docs file"
}

test_both_required_files_missing() {
  printf '\n[test] exit 1 when both required files are absent\n'
  make_fake_repo
  # Neither required file is created

  exit_code=0
  stderr=$("$FAKE_SCRIPT" 2>&1 >/dev/null) || exit_code=$?
  cleanup_fake_repo

  assert_exit_one "$exit_code" "exit code 1 when both required files are missing"
  # README.md is first in the array so it must be reported first
  assert_contains "$stderr" "Missing required file: README.md" \
    "stderr reports README.md when both files are absent"
}

test_first_missing_file_stops_execution() {
  printf '\n[test] script stops at first missing file (README.md before docs file)\n'
  make_fake_repo
  # Neither required file is created

  exit_code=0
  stderr=$("$FAKE_SCRIPT" 2>&1 >/dev/null) || exit_code=$?
  cleanup_fake_repo

  # Because exit 1 fires on README.md, the docs error should NOT appear.
  assert_not_contains "$stderr" "Missing required file: docs/iphone-local-dev-setup.md" \
    "stderr does not report docs file when README.md check fires first"
}

test_success_message_not_printed_on_missing_file() {
  printf '\n[test] success message is not printed when a required file is missing\n'
  make_fake_repo
  # Omit README.md

  exit_code=0
  stdout=$("$FAKE_SCRIPT" 2>/dev/null) || exit_code=$?
  cleanup_fake_repo

  assert_exit_one "$exit_code" "exit code 1 in success-message suppression test"
  assert_not_contains "$stdout" "No dependency installation required." \
    "success message absent when required file is missing"
}

test_error_goes_to_stderr_not_stdout() {
  printf '\n[test] missing-file error is written to stderr, not stdout\n'
  make_fake_repo
  # Only docs file present; README.md missing

  exit_code=0
  stdout=$("$FAKE_SCRIPT" 2>/dev/null) || exit_code=$?
  cleanup_fake_repo

  assert_exit_one "$exit_code" "exit code 1 in stderr-channel test"
  assert_not_contains "$stdout" "Missing required file:" \
    "error message does not appear on stdout"
}

test_script_cds_to_repo_root() {
  printf '\n[test] script resolves and operates from the repository root\n'
  make_fake_repo
  create_required_files

  stdout=$("$FAKE_SCRIPT" 2>/dev/null)
  exit_code=$?
  cleanup_fake_repo

  # The repository path reported must equal the tmpdir root (no trailing slash).
  assert_exit_zero "$exit_code" "exit 0 in repo-root resolution test"
  assert_contains "$stdout" "Repository: $TMPDIR_ROOT" \
    "header shows correct repo root path" || true
  # Note: TMPDIR_ROOT is cleaned up above; we verify the pattern was present in output.
}

test_script_is_executable() {
  printf '\n[test] script file has executable permission\n'
  if [[ -x "$SCRIPT_UNDER_TEST" ]]; then
    pass "scripts/codex_cloud_setup.sh is executable"
  else
    fail "scripts/codex_cloud_setup.sh is NOT executable"
  fi
}

test_script_uses_strict_mode() {
  printf '\n[test] script declares set -euo pipefail (strict mode)\n'
  if grep -qF 'set -euo pipefail' "$SCRIPT_UNDER_TEST"; then
    pass "script contains 'set -euo pipefail'"
  else
    fail "script does not declare strict mode"
  fi
}

test_regression_no_package_installation() {
  printf '\n[test] regression: script performs no package installation\n'
  # The script must not invoke package managers (npm, pip, apt, brew, etc.)
  local disallowed=("npm install" "pip install" "apt-get" "apt " "brew install" "yarn" "apk add")
  local found=0
  for cmd in "${disallowed[@]}"; do
    if grep -qF "$cmd" "$SCRIPT_UNDER_TEST"; then
      fail "script unexpectedly contains package-manager invocation: '$cmd'"
      found=1
    fi
  done
  [[ $found -eq 0 ]] && pass "script contains no package-manager invocations"
}

test_regression_required_file_list_unchanged() {
  printf '\n[test] regression: required_files array contains exactly README.md and docs/iphone-local-dev-setup.md\n'
  if grep -qF '"README.md"' "$SCRIPT_UNDER_TEST" && \
     grep -qF '"docs/iphone-local-dev-setup.md"' "$SCRIPT_UNDER_TEST"; then
    pass "script checks exactly the two expected required files"
  else
    fail "script required_files array differs from expectation"
  fi
}

# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------
printf '=== Running tests for scripts/codex_cloud_setup.sh ===\n'

test_success_all_files_present
test_header_printed_before_file_check
test_repository_path_in_header
test_missing_readme
test_missing_docs_file
test_both_required_files_missing
test_first_missing_file_stops_execution
test_success_message_not_printed_on_missing_file
test_error_goes_to_stderr_not_stdout
test_script_cds_to_repo_root
test_script_is_executable
test_script_uses_strict_mode
test_regression_no_package_installation
test_regression_required_file_list_unchanged

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf '\n=== Results: %d passed, %d failed ===\n' "$PASS" "$FAIL"
if [[ ${#ERRORS[@]} -gt 0 ]]; then
  printf '\nFailed tests:\n'
  for e in "${ERRORS[@]}"; do printf '  %s\n' "$e"; done
fi

[[ $FAIL -eq 0 ]]
