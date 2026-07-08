# v1 Acceptance Criteria

Status: v1 formative document
Date anchor: 2026-07-08

## Code-contract acceptance

The v1 code contract is accepted when all required files in `releases/v1/released-fullworking-system.manifest.json` exist and `scripts/validate_v1_released_system.py` returns `ok=true`.

## Runtime acceptance

The v1 runtime is accepted only when GitHub Actions or another trusted runtime produces the required artifacts for the target commit.

## Required runtime artifacts

- `v1-release-proof`
- `finishline-debug-console`
- `repo-trusted-ops-report`
- `ops-route-dry-run-reports`

## Required report signals

| Report | Required signal |
|---|---|
| `reports/v1-release-proof.json` | `ok=true` |
| `reports/finishline-debug-console.json` | `ok=true` |
| `reports/repo-trusted-ops-report.json` | `ok=true` |
| `reports/ops-route-dry-run-report.json` | `ok=true` |
| `reports/audit-valid-debug-streampipe/audit-valid-debug-streampipe.json` | `ok=true` |

## Non-fabrication rule

Do not claim `100%-operabel`, `fullworking_runtime_complete`, or `released runtime proof complete` until the runtime artifacts exist and report success.
