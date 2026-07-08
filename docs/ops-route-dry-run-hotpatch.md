# Operations Route Dry-Run Hotpatch

Status: implemented as safety dry-run and report-only live sync
Date anchor: 2026-07-08

## Result

The repository now contains a route-level safety dry-run system for critical-near operations. It executes safe local validation and Docker Compose parser checks, while blocking remote execution and destructive Docker actions.

## Implemented files

| Path | Purpose |
|---|---|
| `config/ops-route-matrix.example.json` | Defines every current route and critical-near operation. |
| `scripts/ops_route_runner.py` | Validates routes, executes only safe local routes when requested, and writes a report-only live-sync artifact. |
| `docker-compose.ops-dry-run.yml` | Docker Compose overlay for parse-only inspection. |
| `.github/workflows/ops-route-dry-run.yml` | Manual workflow for route safety dry-run and artifact upload. |
| `Makefile` | Adds route dry-run and Docker parser targets. |
| `.gitignore` | Ignores generated reports and runtime acceptance files. |

## Route classes

| Route | Mode | Execution behavior |
|---|---|---|
| `R01_REPO_VALIDATE` | safe execute | Runs repository validator. |
| `R02_OPS_MANIFEST_VALIDATE` | safe execute | Runs ops access manifest validator. |
| `R03_OPS_ROUTE_MATRIX_VALIDATE` | safe execute | Runs route matrix validator. |
| `R04_DOCKER_COMPOSE_PARSE` | safe execute | Runs Docker Compose parser only. |
| `R05_DOCKER_OVERWRITE_PLAN` | safe execute | Produces Docker service plan only. |
| `R06_SERVICE_STATUS_RESERVED` | blocked | Requires reviewed remote guard. |
| `R07_EXTERNAL_API_CHECK_RESERVED` | blocked | Requires declared target inventory and reviewed remote guard. |
| `R08_LIVE_SYNC_REPORT` | safe execute | Writes route dry-run report. |

## Docker overwrite boundary

The phrase `overwrite-docker` is implemented as an overlay/parse plan, not as destructive Docker mutation.

Allowed:

- `docker compose ... config`
- `docker compose ... config --services`
- generated parser artifacts uploaded by workflow

Blocked:

- `docker compose up`
- `docker compose down`
- `docker compose down -v`
- `docker compose rm`
- `docker volume rm`
- `docker system prune`
- Docker socket mount based control

## Live-sync behavior

Live-sync is `report_only`.

The generated report states:

- whether safe routes were executed;
- whether remote execution occurred;
- whether destructive Docker execution occurred;
- route decisions;
- command findings;
- execution failures;
- redacted environment preview.

## Activation boundary

Remote execution remains disabled until a separate reviewed remote guard, declared target inventory, host identity pin, environment-scoped credentials, staging denial audit, and synthetic redaction proof exist outside Git.
