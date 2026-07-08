# v1 Release Runbook

Status: v1 formative document
Date anchor: 2026-07-08

## Release gates

| Gate | Command or workflow |
|---|---|
| Repository validation | `python3 scripts/validate_repo.py` |
| Agent audit validation | `python3 scripts/validate_agent_audit.py --audit config/agent-objectives.audit.json --routes config/ops-route-matrix.example.json` |
| Trusted operations validation | `python3 scripts/repo_trusted_ops.py validate --profile config/repo-trusted-ops.fullstack.json` |
| Workflow dispatch validation | `python3 scripts/validate_workflow_dispatch_dataset.py --dataset datasets/workflow-dispatch.fullstacked.dataset.json` |
| v1 release validation | `python3 scripts/validate_v1_released_system.py --manifest releases/v1/released-fullworking-system.manifest.json` |
| Full-space hard scan | `make hard-scan-full-space` |
| v1 release gate | `.github/workflows/v1-release-gate.yml` |
| Finishline artifact gate | `.github/workflows/finishline-debug-console.yml` |

## Runtime proof

Full v1 runtime proof requires workflow artifacts. The main expected artifact is:

```text
v1-release-proof
```

The finishline artifact is:

```text
finishline-debug-console
```

## Operator model

The operator does not need to be represented as a developer or shell executor. Repository-native automation produces the evidence when the environment supports it.

## Failure handling

If a runtime artifact is missing, the system remains code-contract-complete but not runtime-proof-complete. Do not overwrite that distinction.
