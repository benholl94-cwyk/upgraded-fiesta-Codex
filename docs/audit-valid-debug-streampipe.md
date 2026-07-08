# Audit Valid Debug Streampipe

Status: committed stream-pipe for finishline debug console artifacts
Date anchor: 2026-07-08

## Purpose

`audit-valid-debug-streampipe` compiles existing operational reports into audit-valid safety reels and emits multiple machine-readable and human-readable formats.

## Generator

```text
scripts/audit_valid_debug_streampipe.py
```

The generator reads runtime artifacts from `reports/` and writes:

```text
reports/audit-valid-debug-streampipe/audit-valid-debug-streampipe.json
reports/audit-valid-debug-streampipe/audit-valid-debug-streampipe.jsonl
reports/audit-valid-debug-streampipe/audit-valid-debug-streampipe.md
reports/audit-valid-debug-streampipe/audit-valid-debug-streampipe.sarif
```

## Safety reels

Each required artifact becomes a safety reel with:

- reel number;
- artifact path;
- required flag;
- existence signal;
- `ok` signal;
- audit decision.

Required artifacts must exist and pass their `ok` signal. Missing or failed required artifacts produce a failed stream report and SARIF result.

## Runtime boundaries

The stream-pipe does not create an interactive console. It does not perform remote execution, destructive execution, or secret reads. It compiles runtime artifact evidence into deterministic output formats.

## CI integration

The `Finishline Debug Console` workflow builds the stream-pipe after:

- repository validation;
- agent audit validation;
- trusted-ops profile validation;
- trusted-ops report generation;
- route dry-run report generation;
- Docker Compose parse artifact generation.

The workflow artifact `finishline-debug-console` includes the stream outputs.

## Local target

```text
make audit-streampipe-full
```

This target emits the same stream artifact set under `reports/`.
