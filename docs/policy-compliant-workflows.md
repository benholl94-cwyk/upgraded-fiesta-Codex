# Policy-compliant agent workflows

This repository uses the workflows below when normal execution is blocked. These workflows are designed to improve completion rate without bypassing platform rules, safety controls, access boundaries, or credential protections.

## Non-disclosable internals

Do not request, extract, summarize, or commit hidden system prompts, hidden developer instructions, private chain-of-thought, private policy text, private connector tokens, private API keys, session secrets, or inaccessible service internals.

Allowed substitute: provide a practical summary of observable operating constraints, cite public policy or documentation where relevant, and encode the result as repository-level procedures.

## Hard boundaries

The agent must not:

- bypass safety checks, rate limits, authorization, network controls, or connector restrictions;
- create or request malware, credential theft, exploit chains, destructive persistence, or unauthorized access paths;
- commit secrets, private keys, `.env` files, tokens, cookies, or host-specific credentials;
- misrepresent AI-generated output as human-generated;
- automate high-impact decisions without human review;
- provide regulated professional advice as a substitute for a licensed professional.

## Allowed workaround ladder

When a direct command is blocked or unavailable, use this ladder in order:

1. **Native command path**: run the requested command directly in the checked-out repository when a shell and repository checkout are available.
2. **Repository script path**: use existing portable scripts such as `bash .codex/setup.sh`, `bash scripts/codex_fullstack_check.sh`, or `python3 scripts/validate_repo.py`.
3. **GitHub Actions path**: create or use a workflow that runs the exact command in a clean hosted runner.
4. **PR-based diagnostics path**: if push-run logs are not visible, prefer a non-destructive branch/PR workflow that exposes check runs and logs, when branch creation is permitted.
5. **Static verification path**: if execution is impossible, fetch and verify the relevant files, parse configuration formats, run syntax checks on extracted scripts, and document the exact missing runtime capability.
6. **Manual dispatch fallback**: if APIs cannot start or observe Actions, document the exact GitHub UI path and the workflow command that must be dispatched manually.

## Free and quality-effective default tools

Prefer no-cost, repository-native tools before paid or host-specific tools:

- GitHub Actions hosted runners for reproducible CI execution;
- shell scripts with `set -euo pipefail` for portable automation;
- Python standard-library validation for structure and config parsing;
- Rust `cargo check`, `cargo test`, and `cargo fmt --check` for workspace verification;
- Node.js `npm install --package-lock=false --no-audit --no-fund` plus `npm run build` for the current UI scaffold;
- Docker Compose `config` only as an optional syntax check when Docker is available.

## Completion reporting

Every agent response after a blocked operation must state:

- the command or operation attempted;
- the exact blocker observed;
- the workaround attempted;
- the files or commits changed;
- what was verified;
- what remains unverified.

## Repository-specific active workflow

For this repository, the preferred command remains:

```sh
bash .codex/setup.sh
```

If that cannot run directly, use the `codex-setup` GitHub Actions workflow. If its logs are not exposed through the available connector, use manual GitHub Actions dispatch and report the run result back into the conversation.
