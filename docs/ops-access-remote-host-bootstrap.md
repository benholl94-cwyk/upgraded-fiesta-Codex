# Operations Access Remote Host Bootstrap Contract

Status: implementation contract, not activated
Date anchor: 2026-07-08

## Result

A remote host is eligible for live operations only after it satisfies this contract. The repository does not contain remote credentials, private keys, production `.env` files, host-specific secrets, or unrestricted shell entrypoints.

## Activation model

The host must expose a dedicated operations account whose only purpose is brokered automation. That account must be least-privilege, non-root, auditable, and bound to a forced operations guard. Remote work is expressed as named operations from `config/ops-command-manifest.example.json`, not as arbitrary shell text.

## Required host properties

| Area | Required property |
|---|---|
| Identity | Stable host identity must be pinned in the automation environment before use. |
| Account | Dedicated low-privilege operations account. |
| Authentication | Public-key authentication only. Password and root login are not part of the normal path. |
| Authorization | Operations must be allowlisted by manifest. |
| Execution | Guarded adapter execution only; no unrestricted session by default. |
| Audit | Accepted and denied operation attempts must produce structured audit events. |
| Redaction | Logs and artifacts must redact credential-like values before persistence. |
| Network | Network work is denied unless a declared-target policy explicitly allows it. |
| Disable path | Removing the environment-scoped credential must disable access completely. |

## Required repository-side values

These values belong in a platform secret manager or environment configuration, not in Git:

| Name | Type | Purpose |
|---|---|---|
| `OPS_HOST_IDENTITY_PIN` | secret or protected variable | Remote host identity pin used before any connection is accepted. |
| `OPS_REMOTE_ACCOUNT` | protected variable | Dedicated remote operations account name. |
| `OPS_ACCESS_KEY` | secret | Environment-scoped credential for the approved remote account. |
| `OPS_ACCESS_PROFILE` | protected variable | One of `staging`, `production`, or `mobile-lab`. |
| `OPS_AUDIT_MODE` | protected variable | Expected value: `jsonl`. |

## Remote guard requirements

The remote guard must:

1. Receive an operation name.
2. Reject missing, unknown, disabled, or malformed operations.
3. Resolve the operation against the manifest deployed on the host.
4. Enforce timeout, output limit, network policy, and working-directory policy.
5. Execute through a fixed adapter, not through unrestricted command parsing.
6. Redact credential-like output before writing logs.
7. Emit an audit event for both allow and deny decisions.
8. Return deterministic success or failure status.

## Initial allowed operations

| Operation | Activation state | Purpose |
|---|---:|---|
| `repo.validate` | active locally, remote pending | Validate repository structure. |
| `ops.validate` | active locally, remote pending | Validate operations access manifest. |
| `service.status` | reserved | Read-only status for approved named services. |
| `external.api.check` | reserved | Declared-target API health checks only. |

## Pre-production acceptance gates

| Gate | Required result |
|---|---|
| Repository hygiene | No committed credentials or host-specific secrets. |
| Manifest validation | `scripts/validate_ops_access_config.py` returns `ok: true`. |
| Remote identity | Host identity is pinned before access. |
| Account scope | Remote account is non-root and dedicated. |
| Operation denial | Unknown operations are denied and audited. |
| Output handling | Oversized output is truncated and marked. |
| Redaction | Synthetic credential markers are removed from persisted output. |
| Network policy | Operations with `network: deny` cannot reach external targets. |
| Rollback | Removing the access credential disables the path. |

## Current state

The repository contains the policy and validation contract. Live remote execution is intentionally disabled until a reviewed remote guard, environment-scoped credential set, host identity pin, and staging validation pass exist.
