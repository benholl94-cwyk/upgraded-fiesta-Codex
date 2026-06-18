from __future__ import annotations

import json
import pathlib
import subprocess
import sys


def test_doctor(tmp_path: pathlib.Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "ghm_core.cli", "doctor", "--workspace", str(tmp_path / "generated_heavy_metal")],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
