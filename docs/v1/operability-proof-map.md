# v1 Operability Proof Map

Status: v1 formative document
Date anchor: 2026-07-08

## Proof classes

| Proof class | Source | Runtime artifact required |
|---|---|---:|
| Code path proof | committed files and validators | no |
| Workflow gate proof | committed GitHub workflow files | no |
| Report generator proof | committed Python generators | no |
| Runtime execution proof | GitHub Actions run logs and artifacts | yes |
| Fullworking proof | all required reports with `ok=true` | yes |

## Main proof chain

```text
v1 manifest
  -> v1 validator
  -> hard-scan-full-space
  -> v1-release-gate workflow
  -> finishline-debug-console workflow
  -> audit-valid debug-streampipe
  -> runtime artifacts
```

## Artifact names

```text
v1-release-proof
finishline-debug-console
repo-trusted-ops-report
ops-route-dry-run-reports
```

## Current source-side status

The v1 source-side release contract is complete when the validator returns `ok=true`. Runtime completeness is not inferred from source completeness.
