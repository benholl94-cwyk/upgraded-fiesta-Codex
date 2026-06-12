#!/usr/bin/env bash
# Tests for scripts/codex_cloud_setup.sh
# Pure-bash test harness — no external test framework required.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SETUP_SCRIPT="$REPO_ROOT/scripts/codex_cloud_setup.sh"
VALIDATE_SCRIPT="$REPO_ROOT/scripts/validate_iphone_control_plane.sh"

# ── Harness ──────────────────────────────────────────────────────────────────

PASS=0
FAIL=0
TMPDIR_BASE=""

_setup_suite() {
  TMPDIR_BASE="$(mktemp -d)"
}

_teardown_suite() {
  [[ -n "$TMPDIR_BASE" ]] && rm -rf "$TMPDIR_BASE"
}

# Create a temp repo that mirrors the real layout with both scripts present.
make_env() {
  local name="${1:-env}"
  local env="$TMPDIR_BASE/$name"
  mkdir -p "$env/scripts" "$env/docs"
  cp "$SETUP_SCRIPT"    "$env/scripts/codex_cloud_setup.sh"
  cp "$VALIDATE_SCRIPT" "$env/scripts/validate_iphone_control_plane.sh"
  printf '%s' "$env"
}

# Write fully valid README + docs into an env dir.
write_valid_files() {
  local env="$1"

  cat > "$env/README.md" <<'EOF'
# upgraded-fiesta

Stand der geprüften App-/Tool-Informationen: 2026-06-12

Lies die vollständige Anleitung: docs/iphone-local-dev-setup.md
EOF

  cat > "$env/docs/iphone-local-dev-setup.md" <<'EOF'
## 1. Zielbild
## 2. Realistische Grenzen von iOS
## 3. Empfohlene App-Rollen
## 6. Git mit Working Copy einrichten
## 7. a-Shell einrichten
## 8. iSH einrichten
## 10. Lokale Web-Entwicklung
## 11. Internet-Grundlagen und Online-Arbeit
## 13. Sicherheit
## 14. Backup-Strategie
## 16. Fehlerbehebung
## 17. Minimal-Checkliste

export DEV_HOST=127.0.0.1
export DEV_BIND=127.0.0.1
export NO_PROXY="localhost,127.0.0.1,::1,*.local"
Nutze `0.0.0.0` nur wenn du explizit LAN-Zugriff brauchst.
Teile niemals `id_ed25519`, sondern nur `id_ed25519.pub`.
Führe unbekannte Shell-Skripte nicht blind mit `curl ... | sh` aus
EOF
}

# Run the setup script inside the given env; capture stdout+stderr.
run_setup() {
  local env="$1"
  (cd "$env" && bash scripts/codex_cloud_setup.sh 2>&1)
}

# ── Assertion helpers ─────────────────────────────────────────────────────────

assert_exit() {
  local test_name="$1"
  local expected="$2"
  local actual="$3"
  local output="$4"
  if [[ "$actual" -eq "$expected" ]]; then
    printf '[PASS] %s\n' "$test_name"
    (( PASS++ ))
  else
    printf '[FAIL] %s — expected exit %d, got %d\nOutput:\n%s\n' \
      "$test_name" "$expected" "$actual" "$output"
    (( FAIL++ ))
  fi
}

assert_output_contains() {
  local test_name="$1"
  local pattern="$2"
  local output="$3"
  if printf '%s' "$output" | grep -qF "$pattern"; then
    printf '[PASS] %s\n' "$test_name"
    (( PASS++ ))
  else
    printf '[FAIL] %s — expected output to contain: %s\nActual output:\n%s\n' \
      "$test_name" "$pattern" "$output"
    (( FAIL++ ))
  fi
}

assert_output_not_contains() {
  local test_name="$1"
  local pattern="$2"
  local output="$3"
  if ! printf '%s' "$output" | grep -qF "$pattern"; then
    printf '[PASS] %s\n' "$test_name"
    (( PASS++ ))
  else
    printf '[FAIL] %s — expected output NOT to contain: %s\nActual output:\n%s\n' \
      "$test_name" "$pattern" "$output"
    (( FAIL++ ))
  fi
}

# ── Tests ─────────────────────────────────────────────────────────────────────

test_happy_path_exit_zero() {
  local env; env="$(make_env happy)"
  write_valid_files "$env"
  local output; output="$(run_setup "$env")"
  local rc=$?
  assert_exit "happy path exits 0" 0 "$rc" "$output"
}

test_happy_path_prints_codex_banner() {
  local env; env="$(make_env banner)"
  write_valid_files "$env"
  local output; output="$(run_setup "$env")"
  assert_output_contains "output contains project banner" \
    "Codex cloud setup for upgraded-fiesta" "$output"
}

test_happy_path_prints_repository_line() {
  local env; env="$(make_env repo_line)"
  write_valid_files "$env"
  local output; output="$(run_setup "$env")"
  assert_output_contains "output contains 'Repository:' line" \
    "Repository:" "$output"
}

test_happy_path_repository_path_is_absolute() {
  local env; env="$(make_env abs_path)"
  write_valid_files "$env"
  local output; output="$(run_setup "$env")"
  # The repository path printed must start with /
  local repo_line; repo_line="$(printf '%s' "$output" | grep '^Repository:')"
  local repo_path="${repo_line#Repository: }"
  if [[ "$repo_path" == /* ]]; then
    printf '[PASS] repository path is absolute\n'
    (( PASS++ ))
  else
    printf '[FAIL] repository path is absolute — got: %s\n' "$repo_path"
    (( FAIL++ ))
  fi
}

test_happy_path_prints_success_message() {
  local env; env="$(make_env success_msg)"
  write_valid_files "$env"
  local output; output="$(run_setup "$env")"
  assert_output_contains "output contains final success message" \
    "No dependency installation required. Static iPhone control-plane validation passed." \
    "$output"
}

test_happy_path_success_message_after_validation() {
  local env; env="$(make_env msg_order)"
  write_valid_files "$env"
  local output; output="$(run_setup "$env")"
  # Both the validator success message and the setup success message must appear.
  assert_output_contains "validator success message present" \
    "Static iPhone control-plane validation passed." "$output"
  assert_output_contains "setup success message present" \
    "No dependency installation required." "$output"
}

test_propagates_failure_when_readme_missing() {
  local env; env="$(make_env fail_readme)"
  write_valid_files "$env"
  rm "$env/README.md"
  local output; output="$(run_setup "$env")"
  local rc=$?
  assert_exit "exits non-zero when README.md missing" 1 "$rc" "$output"
  assert_output_contains "failure output contains validation error" \
    "Validation failed:" "$output"
}

test_propagates_failure_when_docs_missing() {
  local env; env="$(make_env fail_docs)"
  write_valid_files "$env"
  rm "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_setup "$env")"
  local rc=$?
  assert_exit "exits non-zero when docs file missing" 1 "$rc" "$output"
  assert_output_contains "failure output contains validation error" \
    "Validation failed:" "$output"
}

test_propagates_failure_when_disallowed_pattern_present() {
  local env; env="$(make_env fail_brew)"
  write_valid_files "$env"
  printf '\nbrew install git\n' >> "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_setup "$env")"
  local rc=$?
  assert_exit "exits non-zero when disallowed brew install present" 1 "$rc" "$output"
  assert_output_contains "failure mentions disallowed pattern" \
    "macOS desktop package-manager assumption" "$output"
}

test_no_success_message_on_failure() {
  local env; env="$(make_env no_success_on_fail)"
  write_valid_files "$env"
  rm "$env/README.md"
  local output; output="$(run_setup "$env")"
  assert_output_not_contains "no final success message when validation fails" \
    "No dependency installation required." "$output"
}

# Regression: validate_iphone_control_plane.sh must be called from repo root,
# not from the scripts/ directory — check that the repository path printed by
# codex_cloud_setup.sh does NOT end with "/scripts".
test_repo_root_not_scripts_subdir() {
  local env; env="$(make_env root_check)"
  write_valid_files "$env"
  local output; output="$(run_setup "$env")"
  local repo_line; repo_line="$(printf '%s' "$output" | grep '^Repository:')"
  local repo_path="${repo_line#Repository: }"
  if [[ "$repo_path" != */scripts ]]; then
    printf '[PASS] repo root does not point inside scripts/\n'
    (( PASS++ ))
  else
    printf '[FAIL] repo root points inside scripts/: %s\n' "$repo_path"
    (( FAIL++ ))
  fi
}

# ── Main ─────────────────────────────────────────────────────────────────────

_setup_suite
trap _teardown_suite EXIT

test_happy_path_exit_zero
test_happy_path_prints_codex_banner
test_happy_path_prints_repository_line
test_happy_path_repository_path_is_absolute
test_happy_path_prints_success_message
test_happy_path_success_message_after_validation
test_propagates_failure_when_readme_missing
test_propagates_failure_when_docs_missing
test_propagates_failure_when_disallowed_pattern_present
test_no_success_message_on_failure
test_repo_root_not_scripts_subdir

printf '\nResults: %d passed, %d failed\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]