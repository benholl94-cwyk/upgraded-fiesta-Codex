# Live Operations Access Policy

Status: repository gates implemented, remote activation disabled
Date anchor: 2026-07-08
Scope: upgraded-fiesta-Codex

## Result

The approved model is a brokered live-operations access layer. It is not an unrestricted remote control channel.

The access layer must use explicit operator authorization, environment-scoped credentials, host identity verification, least-privilege accounts, command allowlists, audit records, and fail-closed validation.

## Boundaries

- No credentials are committed to the repository.
- No local environment is extracted automatically.
- No unauthenticated remote execution is allowed.
- No unrestricted administrative session is the default path.
- No silent persistence mechanism is allowed.
- All operations must be attributable to an actor, workflow, repository revision, operation name, result, and timestamp.

## Required gates before activation

1. Repository contains only templates and validators, not credential material.
2. Remote identity is pinned before any connection is accepted.
3. Remote account is dedicated to operations and uses least privilege.
4. Commands are represented as named operations, not arbitrary free-form shell text.
5. Each operation is validated against a manifest.
6. Output is redacted before storage.
7. Every accepted and denied operation produces an audit event.
8. Long-running and excessive-output operations are terminated.
9. Disabling the environment credentials fully disables remote operations.
10. Production activation requires a successful staging validation pass.

## Implemented repository additions

| Path | Status | Purpose |
|---|---:|---|
| `config/ops-command-manifest.example.json` | implemented | Fail-closed operation manifest with disabled remote profiles. |
| `scripts/validate_ops_access_config.py` | implemented | Static validator for schema, denied command tokens, timeouts, output limits, audit requirements, and network policy. |
| `docs/ops-access-remote-host-bootstrap.md` | implemented | Remote host eligibility contract without credentials or host-specific secrets. |
| `.github/workflows/ops-access-dispatch.yml` | implemented | Manual dispatch workflow that validates gates and refuses remote activation. |

## Current hard stop

The live connection is not activated in this context because no approved remote host identity, dedicated remote account, reviewed remote guard, or environment-scoped credential is available here. That is the correct secure state.

## Next activation threshold

Remote operations may only move beyond repository validation after all of these are present outside Git:

1. Approved remote host identity pin.
2. Dedicated low-privilege operations account.
3. Environment-scoped access credential.
4. Reviewed remote guard implementation.
5. Staging validation showing unknown operations denied and audited.
6. Redaction proof using synthetic credential markers only.
