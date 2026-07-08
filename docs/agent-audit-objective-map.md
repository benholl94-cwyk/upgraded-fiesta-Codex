# Agent Audit Objective Map

Status: active local audit model
Date anchor: 2026-07-08

## Result

The agent layer now has objective data, audit events, validation logic, and workflow integration.

## Objective sources

| Layer | Path | Role |
|---|---|---|
| Rust model | `crates/hm-agent/src/lib.rs` | Typed objective and audit event model. |
| Data object | `config/agent-objectives.audit.json` | Machine-readable objective-to-route map. |
| Validator | `scripts/validate_agent_audit.py` | Verifies objective fields, route coverage, non-remote default, and non-destructive default. |
| Make target | `agent-audit-validate` | Local validation target. |
| Workflow | `.github/workflows/ops-route-dry-run.yml` | Runs agent audit validation before route dry-run. |

## Objective coverage

| Objective | Route | Decision |
|---|---|---|
| `A01_REPO_VALIDATION` | `R01_REPO_VALIDATE` | local validation allowed |
| `A02_OPS_MANIFEST_VALIDATION` | `R02_OPS_MANIFEST_VALIDATE` | local validation allowed |
| `A03_ROUTE_MATRIX_VALIDATION` | `R03_OPS_ROUTE_MATRIX_VALIDATE` | local validation allowed |
| `A04_DOCKER_PARSE_PLAN` | `R04_DOCKER_COMPOSE_PARSE` | parse only |
| `A05_DOCKER_SERVICE_PLAN` | `R05_DOCKER_OVERWRITE_PLAN` | parse only |
| `A06_REMOTE_SERVICE_STATUS_RESERVED` | `R06_SERVICE_STATUS_RESERVED` | reserved until reviewed guard |
| `A07_EXTERNAL_API_CHECK_RESERVED` | `R07_EXTERNAL_API_CHECK_RESERVED` | reserved until declared targets |

## Validation criteria

The validator requires:

- schema match;
- `agent_component` set to `hm-agent`;
- remote execution flag set to `false`;
- destructive execution flag set to `false`;
- every objective has all required fields;
- every objective has a route ID that exists in the route matrix;
- decisions are from the allowed set;
- evidence paths are repository-relative;
- metrics are non-empty.

## Boundary

This audit map does not activate remote execution, destructive Docker behavior, or access to local environment values. It adds objective traceability and validation only.
