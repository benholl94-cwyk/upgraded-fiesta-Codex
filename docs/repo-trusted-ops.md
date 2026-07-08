# Repo Trusted Ops

Status: enabled repo-trusted operations toolchain
Date anchor: 2026-07-08

## Purpose

`repo-trusted-ops` provides a machine-readable operational fullstack profile for local and external gap checks. It is designed for mobile-first repository operation and GitHub Actions execution.

## Implemented files

| Path | Role |
|---|---|
| `config/repo-trusted-ops.fullstack.json` | Local and external trusted-ops fullstack profile. |
| `scripts/repo_trusted_ops.py` | Validator and report generator with live UTC timestamp. |
| `.github/workflows/repo-trusted-ops.yml` | GitHub Actions workflow for profile validation and report artifact export. |
| `Makefile` | `trusted-ops-*` targets. |
| `AGENTS.md` | Repository rules requiring trusted-ops validation. |

## Local sets

The profile includes local checks for:

- repository structure;
- agent audit objectives;
- operations access manifest;
- route matrix;
- device execution status;
- depo server status;
- Docker Compose config parse-only;
- Docker Compose service listing parse-only.

## External sets

External checks are declared only and are not probed by default. The current declared external set includes the GitHub repository API endpoint and required workflow file presence checks.

External HTTP probing requires explicit `--probe-external` or the workflow input `probe_external=true`.

## Runtime boundaries

The trusted-ops profile requires:

- `secret_read_allowed=false`;
- `remote_execution_allowed=false`;
- `destructive_execution_allowed=false`;
- `arbitrary_shell_allowed=false`;
- `declared_targets_only=true`;
- live UTC datetime in every generated report.

## Reports

The main report path is:

```text
reports/repo-trusted-ops-report.json
```

Runtime reports are intentionally not committed. They are local/CI artifacts.

## Workflow

Workflow name:

```text
Repo Trusted Ops
```

Inputs:

```yaml
execute_local: true
probe_external: false
```

The workflow uploads artifact:

```text
repo-trusted-ops-report
```

## Operability meaning

This toolchain enables repository-trusted operational checks and produces objective evidence. It does not claim full production enablement until the workflow has run and the report artifact exists for the target commit.
