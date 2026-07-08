# Live Operations Access Policy

Status: planned, not activated
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

## Recommended repository additions

- `config/ops-command-manifest.example.json`
- `scripts/validate_ops_access_config.py`
- `docs/ops-access-remote-host-bootstrap.md`
- `.github/workflows/ops-access-dispatch.yml`

These additions must remain non-secret and fail closed when required environment values are missing.

## Current hard stop

The live connection is not activated in this context because no approved remote host identity, dedicated remote account, or environment-scoped credential is available here. That is the correct secure state.
