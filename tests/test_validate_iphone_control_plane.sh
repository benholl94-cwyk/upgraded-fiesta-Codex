#!/usr/bin/env bash
# Tests for scripts/validate_iphone_control_plane.sh
# Pure-bash test harness — no external test framework required.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
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

# Create a fresh temp repo that mirrors the real layout, then configure it.
# Usage: make_env <subdir>  → prints the env path
make_env() {
  local name="${1:-env}"
  local env="$TMPDIR_BASE/$name"
  mkdir -p "$env/scripts" "$env/docs"
  # Copy the script under test so its BASH_SOURCE resolves correctly.
  cp "$VALIDATE_SCRIPT" "$env/scripts/validate_iphone_control_plane.sh"
  printf '%s' "$env"
}

# Write a fully-valid pair of files into an env directory.
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

# Run the validate script inside the given env; capture stdout+stderr.
run_validate() {
  local env="$1"
  (cd "$env" && bash scripts/validate_iphone_control_plane.sh 2>&1)
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

test_happy_path() {
  local env; env="$(make_env happy)"
  write_valid_files "$env"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "happy path exits 0" 0 "$rc" "$output"
  assert_output_contains "happy path prints start message" \
    "Validating static iPhone control-plane..." "$output"
  assert_output_contains "happy path prints success message" \
    "Static iPhone control-plane validation passed." "$output"
}

test_missing_readme() {
  local env; env="$(make_env no_readme)"
  write_valid_files "$env"
  rm "$env/README.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing README.md exits 1" 1 "$rc" "$output"
  assert_output_contains "missing README.md error message" \
    "missing required file: README.md" "$output"
}

test_missing_docs_file() {
  local env; env="$(make_env no_docs)"
  write_valid_files "$env"
  rm "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing docs file exits 1" 1 "$rc" "$output"
  assert_output_contains "missing docs file error message" \
    "missing required file: docs/iphone-local-dev-setup.md" "$output"
}

test_readme_missing_setup_guide_link() {
  local env; env="$(make_env no_link)"
  write_valid_files "$env"
  # Overwrite README without the link
  cat > "$env/README.md" <<'EOF'
# upgraded-fiesta

Stand der geprüften App-/Tool-Informationen: 2026-06-12
EOF
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "README missing setup guide link exits 1" 1 "$rc" "$output"
  assert_output_contains "README missing setup guide link error" \
    "link to the full setup guide" "$output"
}

test_readme_missing_review_date() {
  local env; env="$(make_env no_date)"
  write_valid_files "$env"
  # Overwrite README without the review date
  cat > "$env/README.md" <<'EOF'
# upgraded-fiesta

Lies die vollständige Anleitung: docs/iphone-local-dev-setup.md
EOF
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "README missing review date exits 1" 1 "$rc" "$output"
  assert_output_contains "README missing review date error" \
    "review date" "$output"
}

test_docs_missing_section_zielbild() {
  local env; env="$(make_env no_zielbild)"
  write_valid_files "$env"
  sed -i '/## 1\. Zielbild/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing section '## 1. Zielbild' exits 1" 1 "$rc" "$output"
  assert_output_contains "missing section '## 1. Zielbild' error" \
    "control-plane section" "$output"
}

test_docs_missing_section_grenzen() {
  local env; env="$(make_env no_grenzen)"
  write_valid_files "$env"
  sed -i '/## 2\. Realistische Grenzen/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing section '## 2. Realistische Grenzen von iOS' exits 1" 1 "$rc" "$output"
}

test_docs_missing_section_app_rollen() {
  local env; env="$(make_env no_approlen)"
  write_valid_files "$env"
  sed -i '/## 3\. Empfohlene App-Rollen/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing section '## 3. Empfohlene App-Rollen' exits 1" 1 "$rc" "$output"
}

test_docs_missing_section_git() {
  local env; env="$(make_env no_git)"
  write_valid_files "$env"
  sed -i '/## 6\. Git/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing section '## 6. Git mit Working Copy einrichten' exits 1" 1 "$rc" "$output"
}

test_docs_missing_section_ashell() {
  local env; env="$(make_env no_ashell)"
  write_valid_files "$env"
  sed -i '/## 7\. a-Shell/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing section '## 7. a-Shell einrichten' exits 1" 1 "$rc" "$output"
}

test_docs_missing_section_ish() {
  local env; env="$(make_env no_ish)"
  write_valid_files "$env"
  sed -i '/## 8\. iSH/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing section '## 8. iSH einrichten' exits 1" 1 "$rc" "$output"
}

test_docs_missing_section_webdev() {
  local env; env="$(make_env no_webdev)"
  write_valid_files "$env"
  sed -i '/## 10\. Lokale Web-Entwicklung/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing section '## 10. Lokale Web-Entwicklung' exits 1" 1 "$rc" "$output"
}

test_docs_missing_section_internet() {
  local env; env="$(make_env no_internet)"
  write_valid_files "$env"
  sed -i '/## 11\. Internet-Grundlagen/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing section '## 11. Internet-Grundlagen und Online-Arbeit' exits 1" 1 "$rc" "$output"
}

test_docs_missing_section_sicherheit() {
  local env; env="$(make_env no_sicherheit)"
  write_valid_files "$env"
  sed -i '/## 13\. Sicherheit/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing section '## 13. Sicherheit' exits 1" 1 "$rc" "$output"
}

test_docs_missing_section_backup() {
  local env; env="$(make_env no_backup)"
  write_valid_files "$env"
  sed -i '/## 14\. Backup-Strategie/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing section '## 14. Backup-Strategie' exits 1" 1 "$rc" "$output"
}

test_docs_missing_section_fehlerbehebung() {
  local env; env="$(make_env no_fehler)"
  write_valid_files "$env"
  sed -i '/## 16\. Fehlerbehebung/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing section '## 16. Fehlerbehebung' exits 1" 1 "$rc" "$output"
}

test_docs_missing_section_checkliste() {
  local env; env="$(make_env no_checklist)"
  write_valid_files "$env"
  sed -i '/## 17\. Minimal-Checkliste/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing section '## 17. Minimal-Checkliste' exits 1" 1 "$rc" "$output"
}

test_docs_missing_dev_host() {
  local env; env="$(make_env no_devhost)"
  write_valid_files "$env"
  sed -i '/export DEV_HOST/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing DEV_HOST exits 1" 1 "$rc" "$output"
  assert_output_contains "missing DEV_HOST error mentions private localhost default" \
    "private localhost default" "$output"
}

test_docs_missing_dev_bind() {
  local env; env="$(make_env no_devbind)"
  write_valid_files "$env"
  sed -i '/export DEV_BIND/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing DEV_BIND exits 1" 1 "$rc" "$output"
  assert_output_contains "missing DEV_BIND error mentions private bind default" \
    "private bind default" "$output"
}

test_docs_missing_no_proxy() {
  local env; env="$(make_env no_noproxy)"
  write_valid_files "$env"
  sed -i '/export NO_PROXY/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing NO_PROXY exits 1" 1 "$rc" "$output"
  assert_output_contains "missing NO_PROXY error mentions local proxy bypass" \
    "local proxy bypass" "$output"
}

test_docs_missing_lan_exposure_warning() {
  local env; env="$(make_env no_lan_warn)"
  write_valid_files "$env"
  sed -i '/Nutze `0.0.0.0` nur/d' "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing LAN exposure warning exits 1" 1 "$rc" "$output"
  assert_output_contains "missing LAN exposure warning error" \
    "explicit LAN exposure warning" "$output"
}

test_docs_missing_ssh_warning() {
  local env; env="$(make_env no_ssh_warn)"
  write_valid_files "$env"
  # Use python-style deletion to avoid sed locale issues with special chars
  grep -v 'id_ed25519' "$env/docs/iphone-local-dev-setup.md" > "$env/docs/iphone-local-dev-setup.md.tmp"
  mv "$env/docs/iphone-local-dev-setup.md.tmp" "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing SSH secret warning exits 1" 1 "$rc" "$output"
  assert_output_contains "missing SSH secret warning error" \
    "SSH secret handling warning" "$output"
}

test_docs_missing_download_safety_warning() {
  local env; env="$(make_env no_dl_warn)"
  write_valid_files "$env"
  grep -v 'curl \.\.\. | sh' "$env/docs/iphone-local-dev-setup.md" > "$env/docs/iphone-local-dev-setup.md.tmp"
  mv "$env/docs/iphone-local-dev-setup.md.tmp" "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "missing download safety warning exits 1" 1 "$rc" "$output"
  assert_output_contains "missing download safety warning error" \
    "download safety warning" "$output"
}

test_docs_contains_disallowed_curl_pipe() {
  local env; env="$(make_env bad_curl)"
  write_valid_files "$env"
  printf '\ncurl -fsSL https://example.com/install.sh | sh\n' \
    >> "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "disallowed curl -fsSL pattern exits 1" 1 "$rc" "$output"
  assert_output_contains "disallowed curl -fsSL error message" \
    "pipe-to-shell bootstrap pattern" "$output"
}

test_docs_contains_disallowed_docker_run() {
  local env; env="$(make_env bad_docker)"
  write_valid_files "$env"
  printf '\ndocker run --rm -it ubuntu bash\n' \
    >> "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "disallowed docker run exits 1" 1 "$rc" "$output"
  assert_output_contains "disallowed docker run error message" \
    "desktop/container assumption" "$output"
}

test_docs_contains_disallowed_brew_install() {
  local env; env="$(make_env bad_brew)"
  write_valid_files "$env"
  printf '\nbrew install node\n' >> "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "disallowed brew install exits 1" 1 "$rc" "$output"
  assert_output_contains "disallowed brew install error message" \
    "macOS desktop package-manager assumption" "$output"
}

# Boundary / negative case: empty docs file should fail on first missing section.
test_docs_completely_empty() {
  local env; env="$(make_env empty_docs)"
  write_valid_files "$env"
  : > "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "completely empty docs file exits 1" 1 "$rc" "$output"
  assert_output_contains "completely empty docs file — first section missing" \
    "control-plane section" "$output"
}

# Regression: script must not succeed when docs file is a directory.
test_docs_path_is_directory() {
  local env; env="$(make_env docs_is_dir)"
  write_valid_files "$env"
  rm "$env/docs/iphone-local-dev-setup.md"
  mkdir -p "$env/docs/iphone-local-dev-setup.md"
  local output; output="$(run_validate "$env")"
  local rc=$?
  assert_exit "docs path is directory exits 1" 1 "$rc" "$output"
  assert_output_contains "docs path is directory error message" \
    "missing required file: docs/iphone-local-dev-setup.md" "$output"
}

# ── Main ─────────────────────────────────────────────────────────────────────

_setup_suite
trap _teardown_suite EXIT

test_happy_path
test_missing_readme
test_missing_docs_file
test_readme_missing_setup_guide_link
test_readme_missing_review_date
test_docs_missing_section_zielbild
test_docs_missing_section_grenzen
test_docs_missing_section_app_rollen
test_docs_missing_section_git
test_docs_missing_section_ashell
test_docs_missing_section_ish
test_docs_missing_section_webdev
test_docs_missing_section_internet
test_docs_missing_section_sicherheit
test_docs_missing_section_backup
test_docs_missing_section_fehlerbehebung
test_docs_missing_section_checkliste
test_docs_missing_dev_host
test_docs_missing_dev_bind
test_docs_missing_no_proxy
test_docs_missing_lan_exposure_warning
test_docs_missing_ssh_warning
test_docs_missing_download_safety_warning
test_docs_contains_disallowed_curl_pipe
test_docs_contains_disallowed_docker_run
test_docs_contains_disallowed_brew_install
test_docs_completely_empty
test_docs_path_is_directory

printf '\nResults: %d passed, %d failed\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
