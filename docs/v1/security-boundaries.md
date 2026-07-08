# v1 Security Boundaries

Status: v1 formative document
Date anchor: 2026-07-08

## Default-deny boundaries

The v1 product keeps the following defaults disabled:

- secret reads;
- unrestricted remote shell;
- destructive Docker execution;
- arbitrary shell execution;
- fabricated runtime success claims.

## Allowed operations

Allowed operations are declared, bounded, and report-producing:

- repository validation;
- agent objective validation;
- trusted-ops profile validation;
- workflow-dispatch dataset validation;
- route-matrix validation;
- Docker Compose parse-only generation;
- runtime report generation;
- audit-valid stream compilation.

## Artifact boundary

Runtime proof is externalized into artifacts. Reports are generated in `reports/` and are not committed as source. Source files define the proof machinery; artifacts prove runtime execution.

## Production interpretation

A production-ready declaration requires both a source contract and successful runtime artifacts. The source contract alone is not treated as proof of live execution.
