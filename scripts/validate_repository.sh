#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

printf '%s\n' 'repository validation: start'

python3 -m py_compile \
  scripts/validate_mobile_iphone_platform.py \
  scripts/mobile_operator.py \
  scripts/ashell_static_server.py \
  scripts/repository_audit_report.py

python3 scripts/validate_mobile_iphone_platform.py
python3 scripts/mobile_operator.py self-test
python3 scripts/ashell_static_server.py --self-test
sh scripts/repository_audit_report.sh --format json >/tmp/upgraded-fiesta-audit.json
rm -f /tmp/upgraded-fiesta-audit.json

python3 - <<'PY'
from pathlib import Path
required = [
    'README.md',
    'AGENTS.md',
    'index.html',
    'styles.css',
    'app.js',
    'manifest.webmanifest',
    'service-worker.js',
    'docs/iphone-local-dev-setup.md',
    'docs/mobile-iphone-automation-workflows.md',
    'scripts/codex_cloud_setup.sh',
    'scripts/validate_repository.sh',
    'install/ashell_onebash_installer.sh',
]
missing = [path for path in required if not Path(path).is_file()]
empty = [path for path in required if Path(path).is_file() and Path(path).stat().st_size == 0]
if missing:
    raise SystemExit(f'missing required files: {missing}')
if empty:
    raise SystemExit(f'empty required files: {empty}')
print('repository file contract is valid')
PY

printf '%s\n' 'repository validation: ok'
