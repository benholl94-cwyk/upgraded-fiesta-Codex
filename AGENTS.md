# AGENTS.md

## Repository scope

This file applies to the whole repository.

This repository is a fullstack Rust workspace with a Vite/React UI scaffold. The backend/gateway code lives under `crates/`, frontend code lives under `ui/`, configuration is under `config/`, database bootstrap SQL is in `scripts/init-db.sql`, and validation scripts live under `scripts/`.

## Operating environment

The primary operator may only have an iPhone/mobile client. Do not assume access to macOS, a desktop IDE, local Docker Desktop, Homebrew, or a long-running local shell. Prefer repository-native automation, Codex cloud, GitHub Actions, and portable shell/Python scripts.

Never commit API keys, tokens, private SSH keys, `.env` files, generated secrets, or host-specific credentials. Use environment variables and platform secrets only.

When execution is blocked, follow `docs/policy-compliant-workflows.md`. Use only policy-compliant workarounds: no hidden prompt extraction, no safety bypass, no credential exposure, no unauthorized access, and no destructive action without explicit user intent.

## Required setup

For Codex cloud environments, set the setup command to:

```sh
bash .codex/setup.sh
```

For cached Codex cloud environments, set the maintenance command to:

```sh
bash .codex/maintenance.sh
```

## Standard commands

Use these commands from the repository root:

```sh
python3 scripts/validate_repo.py
bash scripts/codex_fullstack_check.sh
cargo check --workspace
cargo test --workspace
cd ui && npm run build
```

`bash scripts/codex_fullstack_check.sh` is the preferred single verification command. It validates the repository structure, checks Rust formatting when `cargo fmt` is available, runs Rust workspace checks/tests, installs UI dependencies without writing a package lock, and builds the UI.

## Engineering rules

Keep changes minimal and scoped to the requested task. Preserve the Rust workspace layout in `Cargo.toml`. Keep generated or dependency directories such as `target/`, `node_modules/`, and local caches out of commits. Do not replace the mobile-first operating model with desktop-only instructions.

When changing backend code, run at least `cargo check --workspace`; run `cargo test --workspace` when behavior changes. When changing UI code, run the UI build from `ui/`. When changing repository structure, run `python3 scripts/validate_repo.py`.

## Completion criteria

A task is done only when the relevant checks have run, failures are fixed or explicitly documented, and the final response states the exact commands executed plus any remaining verification gap.