# Operations Access User Acceptance Gates

Status: implemented as repository gates, remote activation disabled
Date anchor: 2026-07-08

## Result

The live-operations access path now has explicit user-acceptance thresholds. Acceptance is interactive through either:

1. GitHub Actions `workflow_dispatch` inputs, or
2. the GitHub issue template `.github/ISSUE_TEMPLATE/ops-user-acceptance.yml`.

Acceptance does not activate remote execution. It validates that the operator explicitly acknowledges every required threshold before any later remote activation stage is considered.

## Acceptance phrase

The required phrase is:

```text
USER_ACCEPT_OPS_ACCESS_THRESHOLDS
```

## Required thresholds

| ID | Threshold | Blocks remote activation |
|---|---|---:|
| `T01_HOST_IDENTITY_PIN` | Approved remote host identity pin exists outside Git. | yes |
| `T02_DEDICATED_LOW_PRIVILEGE_ACCOUNT` | Dedicated low-privilege operations account exists. | yes |
| `T03_ENVIRONMENT_SCOPED_ACCESS_CREDENTIAL` | Environment-scoped access credential exists outside Git. | yes |
| `T04_REMOTE_GUARD_REVIEWED` | Reviewed remote guard implementation exists. | yes |
| `T05_STAGING_DENIAL_AUDITED` | Staging validation shows unknown operations denied and audited. | yes |
| `T06_REDACTION_PROOF_SYNTHETIC_ONLY` | Redaction proof uses synthetic credential markers only. | yes |
| `T07_REMOTE_ACTIVATION_STILL_DISABLED_BY_DEFAULT` | Remote activation remains disabled by default. | no |

## Evidence rules

Allowed evidence:

- confirmation that a protected environment value exists;
- confirmation that a protected environment secret exists;
- sanitized staging audit record reference;
- reviewed deployment/change reference;
- synthetic redaction proof reference.

Denied evidence:

- raw secret values;
- credential material;
- production `.env` content;
- unredacted remote logs;
- unrestricted shell transcripts;
- host-specific sensitive inventory.

## Workflow acceptance mode

The workflow builds a temporary acceptance JSON from interactive `workflow_dispatch` inputs and validates it with:

```text
python3 scripts/validate_ops_user_accept.py --acceptance <runtime-file>
```

The temporary file exists only in the workflow runner. It is not committed to Git.

## Issue acceptance mode

The issue template provides a human-readable acceptance checklist. It is suitable for review records and operator sign-off, but it does not activate remote execution.

## Activation boundary

Remote execution remains disabled until a separate reviewed implementation adds a remote guard, environment-scoped credentials, host identity pin validation, staging audit proof, redaction proof, and explicit production promotion gate.
