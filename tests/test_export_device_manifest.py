from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
#
# scripts/export_device_manifest.swift is a standalone `swift` script (no
# Package.swift / XCTest target exists in this repo). Its top-level code
# (`exportManifest()`) runs unconditionally on load, so to exercise its
# individual functions in isolation we strip that trailing call and append
# small driver snippets, then execute the result with the `swift`
# interpreter -- mirroring how the Python tests in this directory `import`
# scripts directly and how the shell tests invoke scripts as subprocesses.

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
_SCRIPT_PATH = _SCRIPTS_DIR / "export_device_manifest.swift"
_SWIFT_BIN = shutil.which("swift")
_SUBPROCESS_TIMEOUT = 120

pytestmark = pytest.mark.skipif(
    _SWIFT_BIN is None,
    reason="swift toolchain not available in this environment",
)


def _library_source() -> str:
    """Return the script source with the trailing `exportManifest()`
    top-level call removed, so its declarations can be reused without
    triggering the script's own stdout/side effects."""
    source = _SCRIPT_PATH.read_text()
    trimmed = source.rstrip()
    assert trimmed.endswith("exportManifest()"), (
        "export_device_manifest.swift no longer ends with a bare "
        "exportManifest() call; update this test helper to match."
    )
    return trimmed[: -len("exportManifest()")].rstrip() + "\n"


def _run_snippet(tmp_path: Path, extra_code: str) -> subprocess.CompletedProcess:
    """Write the script (minus its auto-run call) plus `extra_code` to a
    temp file and execute it with the swift interpreter."""
    combined = _library_source() + "\n" + extra_code + "\n"
    snippet_path = tmp_path / "snippet.swift"
    snippet_path.write_text(combined)
    return subprocess.run(
        [_SWIFT_BIN, str(snippet_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def _run_actual_script() -> subprocess.CompletedProcess:
    return subprocess.run(
        [_SWIFT_BIN, str(_SCRIPT_PATH)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=_SUBPROCESS_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# calculateSHA256 -- correctness against known SHA-256 digests
# ---------------------------------------------------------------------------
#
# calculateSHA256 dispatches either to CryptoKit or to the hand-rolled
# PortableSHA256 fallback depending on platform availability. Testing the
# public function against reference digests (computed with Python's
# hashlib) verifies correctness regardless of which branch was compiled.

class TestCalculateSHA256Vectors:
    _NAMED_CASES = {
        "empty": b"",
        "abc": b"abc",
        "pangram": b"The quick brown fox jumps over the lazy dog",
    }

    def test_known_vectors_match_hashlib(self, tmp_path):
        driver_lines = []
        for name, payload in self._NAMED_CASES.items():
            encoded = base64.b64encode(payload).decode("ascii")
            driver_lines.append(
                f'print("{name}=" + calculateSHA256(Data(base64Encoded: "{encoded}")!))'
            )
        proc = _run_snippet(tmp_path, "\n".join(driver_lines))
        assert proc.returncode == 0, proc.stderr

        actual = dict(line.split("=", 1) for line in proc.stdout.strip().splitlines())
        for name, payload in self._NAMED_CASES.items():
            expected = hashlib.sha256(payload).hexdigest()
            assert actual[name] == expected, f"{name}: {actual[name]!r} != {expected!r}"

    @pytest.mark.parametrize(
        "length", [0, 1, 55, 56, 57, 63, 64, 65, 119, 120, 128, 200, 1000]
    )
    def test_block_boundary_lengths_match_hashlib(self, tmp_path, length):
        # These lengths straddle the SHA-256 padding boundaries exercised by
        # PortableSHA256's message-padding loop (55/56/57 bytes sit right at
        # the single-block padding cutoff, 64/65 at the block size, etc).
        payload = bytes(i % 256 for i in range(length))
        encoded = base64.b64encode(payload).decode("ascii")
        proc = _run_snippet(
            tmp_path,
            f'print(calculateSHA256(Data(base64Encoded: "{encoded}")!))',
        )
        assert proc.returncode == 0, proc.stderr
        expected = hashlib.sha256(payload).hexdigest()
        assert proc.stdout.strip() == expected

    def test_output_is_lowercase_hex_of_length_64(self, tmp_path):
        proc = _run_snippet(
            tmp_path,
            'print(calculateSHA256("hello world".data(using: .utf8)!))',
        )
        assert proc.returncode == 0, proc.stderr
        digest = proc.stdout.strip()
        assert re.fullmatch(r"[0-9a-f]{64}", digest), digest

    def test_deterministic_for_same_input(self, tmp_path):
        proc = _run_snippet(
            tmp_path,
            """
            let a = calculateSHA256("determinism-check".data(using: .utf8)!)
            let b = calculateSHA256("determinism-check".data(using: .utf8)!)
            print(a == b)
            """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "true"

    def test_sensitive_to_input_changes(self, tmp_path):
        proc = _run_snippet(
            tmp_path,
            """
            let a = calculateSHA256("payload-A".data(using: .utf8)!)
            let b = calculateSHA256("payload-B".data(using: .utf8)!)
            print(a == b)
            """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "false"


# ---------------------------------------------------------------------------
# collectDeviceInfo() -- structure and field validity
# ---------------------------------------------------------------------------

class TestCollectDeviceInfo:
    def _collect(self, tmp_path) -> dict:
        proc = _run_snippet(
            tmp_path,
            """
            let info = collectDeviceInfo()
            let data = try! encodeJSON(info)
            print(String(data: data, encoding: .utf8)!)
            """,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    def test_schema_version_is_fixed(self, tmp_path):
        info = self._collect(tmp_path)
        assert info["schemaVersion"] == "1.0.0"

    def test_timestamp_is_iso8601_parseable(self, tmp_path):
        info = self._collect(tmp_path)
        # ISO8601DateFormatter's default output uses a trailing "Z" for UTC.
        datetime.fromisoformat(info["timestamp"].replace("Z", "+00:00"))

    def test_host_is_non_empty_string(self, tmp_path):
        info = self._collect(tmp_path)
        assert isinstance(info["host"], str)
        assert len(info["host"]) > 0

    def test_os_is_non_empty_string(self, tmp_path):
        info = self._collect(tmp_path)
        assert isinstance(info["os"], str)
        assert len(info["os"]) > 0

    def test_cpu_cores_is_positive_int(self, tmp_path):
        info = self._collect(tmp_path)
        assert isinstance(info["cpuCores"], int)
        assert info["cpuCores"] > 0

    def test_physical_memory_bytes_is_positive(self, tmp_path):
        info = self._collect(tmp_path)
        assert info["physicalMemoryBytes"] > 0

    def test_physical_memory_gb_matches_bytes_conversion(self, tmp_path):
        info = self._collect(tmp_path)
        expected_gb = info["physicalMemoryBytes"] / 1_073_741_824
        assert info["physicalMemoryGB"] == pytest.approx(expected_gb, rel=1e-9)

    def test_uptime_seconds_is_non_negative(self, tmp_path):
        info = self._collect(tmp_path)
        assert info["uptimeSeconds"] >= 0

    def test_uptime_hours_matches_seconds_conversion(self, tmp_path):
        info = self._collect(tmp_path)
        expected_hours = info["uptimeSeconds"] / 3600
        assert info["uptimeHours"] == pytest.approx(expected_hours, rel=1e-9)


# ---------------------------------------------------------------------------
# encodeJSON() -- pretty-printed, sorted-key JSON output
# ---------------------------------------------------------------------------

class TestEncodeJSON:
    def test_output_is_pretty_printed_multiline(self, tmp_path):
        proc = _run_snippet(
            tmp_path,
            """
            struct Sample: Codable { let b: Int; let a: Int }
            let data = try! encodeJSON(Sample(b: 2, a: 1))
            print(String(data: data, encoding: .utf8)!)
            """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "\n" in proc.stdout.strip()

    def test_keys_are_sorted_alphabetically(self, tmp_path):
        proc = _run_snippet(
            tmp_path,
            """
            struct Sample: Codable { let zeta: Int; let alpha: Int }
            let data = try! encodeJSON(Sample(zeta: 2, alpha: 1))
            print(String(data: data, encoding: .utf8)!)
            """,
        )
        assert proc.returncode == 0, proc.stderr
        output = proc.stdout
        assert output.index('"alpha"') < output.index('"zeta"')

    def test_output_round_trips_as_valid_json(self, tmp_path):
        proc = _run_snippet(
            tmp_path,
            """
            struct Sample: Codable { let value: String }
            let data = try! encodeJSON(Sample(value: "hi"))
            print(String(data: data, encoding: .utf8)!)
            """,
        )
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout) == {"value": "hi"}


# ---------------------------------------------------------------------------
# createManifest() -- assembling DeviceInfo + integrityHash
# ---------------------------------------------------------------------------

class TestCreateManifest:
    def _create(self, tmp_path) -> dict:
        proc = _run_snippet(
            tmp_path,
            """
            let manifest = try! createManifest()
            let data = try! encodeJSON(manifest)
            print(String(data: data, encoding: .utf8)!)
            """,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    def test_manifest_version_is_fixed(self, tmp_path):
        manifest = self._create(tmp_path)
        assert manifest["manifestVersion"] == "1.0.0"

    def test_contains_device_sub_object(self, tmp_path):
        manifest = self._create(tmp_path)
        assert "device" in manifest
        assert manifest["device"]["schemaVersion"] == "1.0.0"

    def test_integrity_hash_is_64_char_hex(self, tmp_path):
        manifest = self._create(tmp_path)
        assert re.fullmatch(r"[0-9a-f]{64}", manifest["integrityHash"])

    def test_integrity_hash_changes_across_successive_calls(self, tmp_path):
        proc = _run_snippet(
            tmp_path,
            """
            let first = try! createManifest()
            let second = try! createManifest()
            print(first.integrityHash != second.integrityHash)
            """,
        )
        assert proc.returncode == 0, proc.stderr
        # uptimeSeconds carries sub-second precision, so the serialized
        # device payload (and therefore the hash) differs between calls
        # even when invoked a fraction of a second apart.
        assert proc.stdout.strip() == "true"

    def test_round_trips_through_json_decoder(self, tmp_path):
        proc = _run_snippet(
            tmp_path,
            """
            let manifest = try! createManifest()
            let data = try! encodeJSON(manifest)
            let decoded = try! JSONDecoder().decode(DeviceManifest.self, from: data)
            print(
                decoded.manifestVersion == manifest.manifestVersion
                && decoded.integrityHash == manifest.integrityHash
                && decoded.device.cpuCores == manifest.device.cpuCores
            )
            """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "true"


# ---------------------------------------------------------------------------
# Full script -- black-box subprocess integration
# ---------------------------------------------------------------------------

class TestExportManifestScriptIntegration:
    def test_exits_zero(self):
        proc = _run_actual_script()
        assert proc.returncode == 0, proc.stderr

    def test_stdout_is_valid_json(self):
        proc = _run_actual_script()
        json.loads(proc.stdout)

    def test_top_level_keys_present(self):
        manifest = json.loads(_run_actual_script().stdout)
        assert set(manifest.keys()) == {"manifestVersion", "device", "integrityHash"}

    def test_device_keys_present(self):
        manifest = json.loads(_run_actual_script().stdout)
        expected_keys = {
            "schemaVersion",
            "timestamp",
            "host",
            "os",
            "cpuCores",
            "physicalMemoryBytes",
            "physicalMemoryGB",
            "uptimeSeconds",
            "uptimeHours",
        }
        assert set(manifest["device"].keys()) == expected_keys

    def test_integrity_hash_format(self):
        manifest = json.loads(_run_actual_script().stdout)
        assert re.fullmatch(r"[0-9a-f]{64}", manifest["integrityHash"])

    def test_no_error_key_on_success(self):
        manifest = json.loads(_run_actual_script().stdout)
        assert "error" not in manifest

    def test_successive_runs_produce_different_uptime(self):
        first = json.loads(_run_actual_script().stdout)
        second = json.loads(_run_actual_script().stdout)
        assert first["device"]["uptimeSeconds"] != second["device"]["uptimeSeconds"]