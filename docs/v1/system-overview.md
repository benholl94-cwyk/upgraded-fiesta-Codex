# v1 System Overview

Status: v1 formative document
Date anchor: 2026-07-08

## Product identity

This repository defines the v1 release contract for an autonomous AI operations product named `upgraded-fiesta-Codex autonomous AI operations product`.

The product is mobile-first, repository-native, and GitHub-Actions-capable. It is structured around machine-readable operations objects, trusted local checks, declared external checks, audit-valid stream outputs, and finishline artifact gates.

## System layers

| Layer | Primary assets |
|---|---|
| Repository structure | `scripts/validate_repo.py`, `Cargo.toml`, `Makefile` |
| Agent objectives | `config/agent-objectives.audit.json`, `scripts/validate_agent_audit.py` |
| Operations routing | `config/ops-route-matrix.example.json`, `scripts/ops_route_runner.py` |
| Trusted operations | `config/repo-trusted-ops.fullstack.json`, `scripts/repo_trusted_ops.py` |
| Workflow dispatch | `datasets/workflow-dispatch.fullstacked.dataset.json`, `scripts/validate_workflow_dispatch_dataset.py` |
| Finishline proof | `.github/workflows/finishline-debug-console.yml` |
| Audit stream | `scripts/audit_valid_debug_streampipe.py` |
| v1 release gate | `.github/workflows/v1-release-gate.yml`, `scripts/validate_v1_released_system.py` |

## Operating model

The v1 product treats the user as tactical owner and the repository automation as the executing system where available. Runtime evidence is produced as reports and GitHub Actions artifacts, not as unverified claims.

## Release interpretation

The v1 release files provide a complete machine contract and documentation set. Full runtime proof requires a successful workflow artifact for the target commit.
