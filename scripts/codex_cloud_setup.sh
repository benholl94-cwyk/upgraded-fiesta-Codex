#!/usr/bin/env sh
set -eu

printf '%s\n' 'codex cloud setup: start'

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

python3 --version
python3 -m py_compile scripts/validate_mobile_iphone_platform.py
python3 scripts/validate_mobile_iphone_platform.py

python3 - <<'PY'
from pathlib import Path

required_files = [
    'index.html',
    'styles.css',
    'app.js',
    'manifest.webmanifest',
    'service-worker.js',
    'README.md',
    'docs/iphone-local-dev-setup.md',
]
missing = [path for path in required_files if not Path(path).is_file()]
if missing:
    raise SystemExit(f'missing required static files: {missing}')
print('static file contract is valid')
PY

printf '%s\n' 'codex cloud setup: ok'
