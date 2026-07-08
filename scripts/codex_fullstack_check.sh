#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Codex fullstack check failed: required command not found: $cmd" >&2
    exit 1
  fi
}

echo "Codex fullstack check for upgraded-fiesta"
echo "Repository: $ROOT"

require_cmd python3
require_cmd cargo
require_cmd npm

python3 scripts/validate_repo.py
python3 scripts/validate_agent_audit.py --audit config/agent-objectives.audit.json --routes config/ops-route-matrix.example.json
python3 scripts/repo_trusted_ops.py validate --profile config/repo-trusted-ops.fullstack.json

if cargo fmt --version >/dev/null 2>&1; then
  cargo fmt --all -- --check
else
  echo "cargo fmt not available; skipping Rust formatting check" >&2
fi

cargo check --workspace
cargo test --workspace

if [[ -f ui/package.json ]]; then
  (
    cd ui
    npm install --package-lock=false --no-audit --no-fund
    npm run build
  )
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  POSTGRES_PASSWORD=OPS_DRY_RUN_COMPOSE_PARSER_ONLY docker compose config >/dev/null
else
  echo "docker compose not available; skipping Compose syntax check" >&2
fi

echo "Codex fullstack check complete."
