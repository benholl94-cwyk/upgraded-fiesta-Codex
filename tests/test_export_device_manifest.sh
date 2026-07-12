#!/usr/bin/env bash
# Tests for scripts/export_device_manifest.swift and its accompanying
# documentation (docs/mobile-device-manifest.md) and README.md reference.
#
# Uses a minimal pure-bash harness: no external test framework required.
#
# Two categories of checks are performed:
#   1. Static checks against the script/doc source text. These never require
#      a Swift toolchain and always run.
#   2. Runtime checks that actually execute the script with `swift`. These
#      are skipped (not failed) when no Swift toolchain is available on the
#      current machine, since Swift is not installed on every CI/dev host.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPT_UNDER_TEST="$REPO_ROOT/scripts/export_device_manifest.swift"
DOC_UNDER_TEST="$REPO_ROOT/docs/mobile-device-manifest.md"
README_FILE="$REPO_ROOT/README.md"

# ---------------------------------------------------------------------------
# Minimal test harness
# ---------------------------------------------------------------------------
PASS=0
FAIL=0
SKIP=0
ERRORS=()

pass() { PASS=$((PASS + 1)); printf '  ok: %s\n' "$1"; }
fail_test() {
  FAIL=$((FAIL + 1))
  ERRORS+=("FAIL: $1")
  printf '  FAIL: %s\n' "$1"
}
skip_test() { SKIP=$((SKIP + 1)); printf '  skip: %s\n' "$1"; }

assert_file_contains() {
  local label="$1" file="$2" pattern="$3"
  if grep -qF "$pattern" "$file"; then
    pass "$label"
  else
    fail_test "$label (expected '$file' to contain: $pattern)"
  fi
}

assert_file_matches() {
  local label="$1" file="$2" pattern="$3"
  if grep -qE "$pattern" "$file"; then
    pass "$label"
  else
    fail_test "$label (expected '$file' to match regex: $pattern)"
  fi
}

assert_file_not_contains() {
  local label="$1" file="$2" pattern="$3"
  if grep -qF "$pattern" "$file"; then
    fail_test "$label (expected '$file' NOT to contain: $pattern)"
  else
    pass "$label"
  fi
}

# ---------------------------------------------------------------------------
# Section A: static checks on scripts/export_device_manifest.swift
# ---------------------------------------------------------------------------
echo "=== scripts/export_device_manifest.swift (static) ==="

if [[ ! -f "$SCRIPT_UNDER_TEST" ]]; then
  fail_test "A00: scripts/export_device_manifest.swift exists"
else
  pass "A00: scripts/export_device_manifest.swift exists"

  if [[ -s "$SCRIPT_UNDER_TEST" ]]; then
    pass "A01: script file is not empty"
  else
    fail_test "A01: script file is not empty"
  fi

  first_line="$(head -n1 "$SCRIPT_UNDER_TEST")"
  if [[ "$first_line" == "#!/usr/bin/env swift" ]]; then
    pass "A02: script starts with '#!/usr/bin/env swift' shebang"
  else
    fail_test "A02: expected shebang '#!/usr/bin/env swift', got: $first_line"
  fi

  assert_file_contains "A03: imports Foundation" "$SCRIPT_UNDER_TEST" "import Foundation"
  assert_file_contains "A04: has conditional CryptoKit import guard" "$SCRIPT_UNDER_TEST" "#if canImport(CryptoKit)"
  assert_file_contains "A05: imports CryptoKit inside the guard" "$SCRIPT_UNDER_TEST" "import CryptoKit"

  # DeviceInfo struct and required fields
  assert_file_contains "A06: defines DeviceInfo Codable struct" "$SCRIPT_UNDER_TEST" "struct DeviceInfo: Codable"
  for field in schemaVersion timestamp host os cpuCores physicalMemoryBytes physicalMemoryGB uptimeSeconds uptimeHours; do
    assert_file_matches "A07: DeviceInfo declares field '$field'" "$SCRIPT_UNDER_TEST" "let ${field}:"
  done

  # DeviceManifest struct and required fields
  assert_file_contains "A08: defines DeviceManifest Codable struct" "$SCRIPT_UNDER_TEST" "struct DeviceManifest: Codable"
  for field in manifestVersion device integrityHash; do
    assert_file_matches "A09: DeviceManifest declares field '$field'" "$SCRIPT_UNDER_TEST" "let ${field}:"
  done

  # Version literals
  assert_file_contains "A10: schemaVersion literal is 1.0.0" "$SCRIPT_UNDER_TEST" 'schemaVersion: "1.0.0"'
  assert_file_contains "A11: manifestVersion literal is 1.0.0" "$SCRIPT_UNDER_TEST" 'manifestVersion: "1.0.0"'

  # JSON encoding configuration
  assert_file_contains "A12: JSONEncoder uses prettyPrinted formatting" "$SCRIPT_UNDER_TEST" ".prettyPrinted"
  assert_file_contains "A13: JSONEncoder uses sortedKeys formatting" "$SCRIPT_UNDER_TEST" ".sortedKeys"

  # SHA-256: CryptoKit path
  assert_file_contains "A14: uses CryptoKit SHA256 when available" "$SCRIPT_UNDER_TEST" "SHA256.hash(data:"
  assert_file_contains "A15: CryptoKit hash formatted as lowercase hex bytes" "$SCRIPT_UNDER_TEST" '%02x'

  # SHA-256: pure-Swift fallback path
  assert_file_contains "A16: has a #else fallback branch for calculateSHA256" "$SCRIPT_UNDER_TEST" "#else"
  assert_file_contains "A17: fallback defines rotateRight helper" "$SCRIPT_UNDER_TEST" "func rotateRight("
  assert_file_contains "A18: fallback SHA-256 uses first standard round constant" "$SCRIPT_UNDER_TEST" "0x428a2f98"
  assert_file_contains "A19: fallback SHA-256 uses last standard round constant" "$SCRIPT_UNDER_TEST" "0xc67178f2"
  assert_file_contains "A20: fallback SHA-256 uses standard initial hash value" "$SCRIPT_UNDER_TEST" "0x6a09e667"
  assert_file_contains "A21: fallback formats digest as 32-bit hex words" "$SCRIPT_UNDER_TEST" '%08x'
  assert_file_contains "A22: fallback branch closed with #endif" "$SCRIPT_UNDER_TEST" "#endif"

  # Error handling
  assert_file_contains "A23: defines DeviceInfoError enum" "$SCRIPT_UNDER_TEST" "enum DeviceInfoError: Error"
  assert_file_contains "A24: DeviceInfoError has encodingFailed case" "$SCRIPT_UNDER_TEST" "case encodingFailed"
  assert_file_contains "A25: exportManifest catches errors" "$SCRIPT_UNDER_TEST" "} catch {"
  assert_file_contains "A26: error path prints manifest_export_failed marker" "$SCRIPT_UNDER_TEST" "manifest_export_failed"

  # The script must not write anything to disk (per docs: "without writing
  # host-specific data into the repository" / "ephemeral diagnostics").
  assert_file_not_contains "A27: script does not use FileManager to write files" "$SCRIPT_UNDER_TEST" "FileManager"
  assert_file_not_contains "A28: script does not call Data.write(to:)" "$SCRIPT_UNDER_TEST" ".write(to:"

  # The script must invoke its own entry point at top level so `swift
  # scripts/export_device_manifest.swift` actually produces output.
  last_nonblank="$(grep -vE '^\s*$' "$SCRIPT_UNDER_TEST" | tail -n1)"
  if [[ "$last_nonblank" == "exportManifest()" ]]; then
    pass "A29: exportManifest() is invoked as the final top-level statement"
  else
    fail_test "A29: expected final statement to be 'exportManifest()', got: $last_nonblank"
  fi

  # collectDeviceInfo should read process info, not hardcode any values that
  # would be inappropriate to have committed to source (regression guard
  # against accidentally hardcoding real host-identifying data).
  assert_file_contains "A30: reads host name from ProcessInfo" "$SCRIPT_UNDER_TEST" "process.hostName"
  assert_file_contains "A31: reads OS version string from ProcessInfo" "$SCRIPT_UNDER_TEST" "process.operatingSystemVersionString"
  assert_file_contains "A32: reads processor count from ProcessInfo" "$SCRIPT_UNDER_TEST" "process.processorCount"
  assert_file_contains "A33: reads physical memory from ProcessInfo" "$SCRIPT_UNDER_TEST" "process.physicalMemory"
  assert_file_contains "A34: reads system uptime from ProcessInfo" "$SCRIPT_UNDER_TEST" "process.systemUptime"

  # Memory/uptime derived-unit conversions should use the documented divisors.
  assert_file_contains "A35: GB conversion divides by 1_073_741_824" "$SCRIPT_UNDER_TEST" "1_073_741_824"
  assert_file_contains "A36: hours conversion divides by 3600" "$SCRIPT_UNDER_TEST" "/ 3600"
fi

# ---------------------------------------------------------------------------
# Section B: static checks on docs/mobile-device-manifest.md
# ---------------------------------------------------------------------------
echo "=== docs/mobile-device-manifest.md (static) ==="

if [[ ! -f "$DOC_UNDER_TEST" ]]; then
  fail_test "B00: docs/mobile-device-manifest.md exists"
else
  pass "B00: docs/mobile-device-manifest.md exists"

  if [[ -s "$DOC_UNDER_TEST" ]]; then
    pass "B01: doc file is not empty"
  else
    fail_test "B01: doc file is not empty"
  fi

  assert_file_contains "B02: has top-level heading" "$DOC_UNDER_TEST" "# Mobile device manifest exporter"
  assert_file_contains "B03: references the script path" "$DOC_UNDER_TEST" "scripts/export_device_manifest.swift"
  assert_file_contains "B04: documents the exact run command" "$DOC_UNDER_TEST" "swift scripts/export_device_manifest.swift"
  assert_file_contains "B05: mentions manifestVersion field" "$DOC_UNDER_TEST" "\`manifestVersion\`"
  assert_file_contains "B06: mentions manifest version value 1.0.0" "$DOC_UNDER_TEST" "1.0.0"
  assert_file_contains "B07: mentions device field" "$DOC_UNDER_TEST" "\`device\`"
  assert_file_contains "B08: mentions integrityHash field" "$DOC_UNDER_TEST" "\`integrityHash\`"
  assert_file_contains "B09: mentions SHA-256" "$DOC_UNDER_TEST" "SHA-256"
  assert_file_contains "B10: warns against committing manifests that identify a private device" \
    "$DOC_UNDER_TEST" "Do not commit generated manifests"
  assert_file_contains "B11: describes output as ephemeral diagnostics" "$DOC_UNDER_TEST" "ephemeral diagnostics"
  assert_file_contains "B12: notes no host-specific data is written to the repo" \
    "$DOC_UNDER_TEST" "without writing host-specific data into the repository"

  # The script referenced by the doc must actually exist (cross-check).
  if [[ -f "$SCRIPT_UNDER_TEST" ]]; then
    pass "B13: script referenced by docs actually exists on disk"
  else
    fail_test "B13: docs reference scripts/export_device_manifest.swift but it is missing"
  fi
fi

# ---------------------------------------------------------------------------
# Section C: README.md reference
# ---------------------------------------------------------------------------
echo "=== README.md (static) ==="

if [[ ! -f "$README_FILE" ]]; then
  fail_test "C00: README.md exists"
else
  assert_file_contains "C01: README references docs/mobile-device-manifest.md" \
    "$README_FILE" "docs/mobile-device-manifest.md"
  assert_file_contains "C02: README describes it as a mobile device manifest exporter doc" \
    "$README_FILE" "mobile device manifest exporter documentation"

  if [[ -f "$DOC_UNDER_TEST" ]]; then
    pass "C03: file referenced by README (docs/mobile-device-manifest.md) exists"
  else
    fail_test "C03: README references docs/mobile-device-manifest.md but it is missing"
  fi
fi

# ---------------------------------------------------------------------------
# Section D: runtime checks (require a Swift toolchain; skipped otherwise)
# ---------------------------------------------------------------------------
echo "=== scripts/export_device_manifest.swift (runtime) ==="

if ! command -v swift >/dev/null 2>&1; then
  skip_test "D00-D14: swift toolchain not available on this machine; runtime checks skipped"
elif [[ ! -f "$SCRIPT_UNDER_TEST" ]]; then
  skip_test "D00-D14: script under test is missing; runtime checks skipped"
else
  RUNTIME_OUTPUT="$(swift "$SCRIPT_UNDER_TEST" 2>/tmp/export_device_manifest_stderr.$$)"
  RUNTIME_EXIT=$?
  RUNTIME_STDERR="$(cat /tmp/export_device_manifest_stderr.$$ 2>/dev/null)"
  rm -f "/tmp/export_device_manifest_stderr.$$"

  if [[ $RUNTIME_EXIT -eq 0 ]]; then
    pass "D00: swift scripts/export_device_manifest.swift exits 0"
  else
    fail_test "D00: expected exit 0, got $RUNTIME_EXIT (stderr: $RUNTIME_STDERR)"
  fi

  # Helper: extract a field from the JSON output via python3.
  json_get() {
    python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
node = d
for key in sys.argv[1:]:
    node = node[key]
print(node)
" "$@" <<<"$RUNTIME_OUTPUT" 2>/dev/null
  }

  if printf '%s' "$RUNTIME_OUTPUT" | python3 -c "import json, sys; json.loads(sys.stdin.read())" 2>/dev/null; then
    pass "D01: stdout is valid JSON"
  else
    fail_test "D01: stdout is not valid JSON; got: $RUNTIME_OUTPUT"
  fi

  if [[ "$(json_get error 2>/dev/null)" == "" ]] && ! printf '%s' "$RUNTIME_OUTPUT" | grep -qF '"manifest_export_failed"'; then
    pass "D02: happy-path output has no manifest_export_failed error envelope"
  else
    fail_test "D02: unexpected error envelope in output: $RUNTIME_OUTPUT"
  fi

  mv_value="$(json_get manifestVersion)"
  if [[ "$mv_value" == "1.0.0" ]]; then
    pass "D03: manifestVersion == 1.0.0"
  else
    fail_test "D03: expected manifestVersion 1.0.0, got: $mv_value"
  fi

  sv_value="$(json_get device schemaVersion)"
  if [[ "$sv_value" == "1.0.0" ]]; then
    pass "D04: device.schemaVersion == 1.0.0"
  else
    fail_test "D04: expected device.schemaVersion 1.0.0, got: $sv_value"
  fi

  host_value="$(json_get device host)"
  if [[ -n "$host_value" ]]; then
    pass "D05: device.host is non-empty"
  else
    fail_test "D05: device.host was empty"
  fi

  os_value="$(json_get device os)"
  if [[ -n "$os_value" ]]; then
    pass "D06: device.os is non-empty"
  else
    fail_test "D06: device.os was empty"
  fi

  cores_value="$(json_get device cpuCores)"
  if [[ "$cores_value" =~ ^[0-9]+$ ]] && [[ "$cores_value" -gt 0 ]]; then
    pass "D07: device.cpuCores is a positive integer"
  else
    fail_test "D07: expected positive integer cpuCores, got: $cores_value"
  fi

  mem_bytes="$(json_get device physicalMemoryBytes)"
  if [[ "$mem_bytes" =~ ^[0-9]+$ ]] && [[ "$mem_bytes" -gt 0 ]]; then
    pass "D08: device.physicalMemoryBytes is a positive integer"
  else
    fail_test "D08: expected positive integer physicalMemoryBytes, got: $mem_bytes"
  fi

  # physicalMemoryGB should be consistent with physicalMemoryBytes / 2^30.
  consistency_check="$(python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
b = d['device']['physicalMemoryBytes']
gb = d['device']['physicalMemoryGB']
expected = b / 1073741824
print('ok' if abs(gb - expected) < 1e-6 else 'mismatch expected=%r got=%r' % (expected, gb))
" <<<"$RUNTIME_OUTPUT" 2>&1)"
  if [[ "$consistency_check" == "ok" ]]; then
    pass "D09: physicalMemoryGB matches physicalMemoryBytes / 1073741824"
  else
    fail_test "D09: $consistency_check"
  fi

  # uptimeHours should be consistent with uptimeSeconds / 3600.
  uptime_check="$(python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
secs = d['device']['uptimeSeconds']
hours = d['device']['uptimeHours']
expected = secs / 3600
print('ok' if abs(hours - expected) < 1e-6 else 'mismatch expected=%r got=%r' % (expected, hours))
" <<<"$RUNTIME_OUTPUT" 2>&1)"
  if [[ "$uptime_check" == "ok" ]]; then
    pass "D10: uptimeHours matches uptimeSeconds / 3600"
  else
    fail_test "D10: $uptime_check"
  fi

  hash_value="$(json_get integrityHash)"
  if [[ "$hash_value" =~ ^[0-9a-f]{64}$ ]]; then
    pass "D11: integrityHash is a 64-character lowercase hex SHA-256 digest"
  else
    fail_test "D11: expected 64-char lowercase hex digest, got: $hash_value"
  fi

  ts_value="$(json_get device timestamp)"
  if [[ "$ts_value" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}.*Z$ ]]; then
    pass "D12: device.timestamp looks like an ISO-8601 UTC timestamp"
  else
    fail_test "D12: expected ISO-8601 'Z' timestamp, got: $ts_value"
  fi

  # Output must be pretty-printed (multi-line), not a single compact line.
  line_count="$(printf '%s\n' "$RUNTIME_OUTPUT" | wc -l)"
  if [[ "$line_count" -gt 1 ]]; then
    pass "D13: output is pretty-printed across multiple lines"
  else
    fail_test "D13: expected multi-line pretty-printed JSON, got $line_count line(s)"
  fi

  # Top-level keys must be sorted alphabetically: device, integrityHash,
  # manifestVersion.
  device_pos="$(printf '%s' "$RUNTIME_OUTPUT" | grep -n '"device"' | head -1 | cut -d: -f1)"
  hash_pos="$(printf '%s' "$RUNTIME_OUTPUT" | grep -n '"integrityHash"' | head -1 | cut -d: -f1)"
  version_pos="$(printf '%s' "$RUNTIME_OUTPUT" | grep -n '"manifestVersion"' | head -1 | cut -d: -f1)"
  if [[ -n "$device_pos" && -n "$hash_pos" && -n "$version_pos" \
        && "$device_pos" -lt "$hash_pos" && "$hash_pos" -lt "$version_pos" ]]; then
    pass "D14: top-level keys appear in sorted order (device, integrityHash, manifestVersion)"
  else
    fail_test "D14: expected sorted top-level key order; positions device=$device_pos integrityHash=$hash_pos manifestVersion=$version_pos"
  fi

  # Regression: running the script twice should always produce a
  # self-consistent, well-formed manifest (not just on the first run).
  SECOND_OUTPUT="$(swift "$SCRIPT_UNDER_TEST" 2>/dev/null)"
  if printf '%s' "$SECOND_OUTPUT" | python3 -c "import json, sys; json.loads(sys.stdin.read())" 2>/dev/null; then
    pass "D15: regression - a second independent run also produces valid JSON"
  else
    fail_test "D15: second run did not produce valid JSON: $SECOND_OUTPUT"
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "Results: $PASS passed, $FAIL failed, $SKIP skipped"
for err in "${ERRORS[@]}"; do
  echo "  $err"
done

[[ $FAIL -eq 0 ]] || exit 1