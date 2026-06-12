# AGENTS.md

## Project identity

This repository is an iPhone-first local developer environment and mobile control-plane project. It is intentionally static-first: the primary runtime is `index.html` plus supporting CSS, JavaScript, manifest, service worker, documentation, settings, datasets, and validation scripts.

The project target is reliable iPhone-controlled engineering work. Local iOS tools are used for editing, Git operations, smoke checks, and orchestration. Heavy builds, containers, databases, and deployments must remain reproducible on a remote host when iOS limits are reached.

## Non-negotiable operating rules

- Keep the default branch production-stable.
- Prefer small, reviewable diffs over broad rewrites.
- Do not introduce secrets, credentials, API keys, tokens, private IPs, or personal data into the repository.
- Do not add background network calls, telemetry, tracking, or external runtime dependencies unless the task explicitly requires them and the PR explains why.
- Do not weaken the iPhone-first constraint by assuming a Mac, desktop Linux host, or Docker host is available to the user.
- Do not claim that local iOS shells can provide unrestricted OS-level control. Treat iOS sandbox limits as hard constraints.
- Do not remove existing German user-facing documentation unless replacing it with more precise German documentation.
- Do not perform destructive Git or filesystem actions such as force-push, mass delete, or history rewrite.

## Repository structure

- `index.html`, `styles.css`, `app.js`, `manifest.webmanifest`, `service-worker.js`: static app surface.
- `docs/`: user-facing guides and runbooks.
- `settings/mobile-iphone-platform/`: platform settings and shortcut catalog.
- `datasets/mobile-iphone-platform/`: CSV control datasets.
- `scripts/`: validation and setup scripts.

## Codex cloud setup

Use this setup command in the Codex environment settings for this repository:

```sh
bash scripts/codex_cloud_setup.sh
```

If the setup script is not available in an older branch, use the fallback commands:

```sh
python3 --version
python3 -m py_compile scripts/validate_mobile_iphone_platform.py
python3 scripts/validate_mobile_iphone_platform.py
```

The repository has no mandatory package-install step. Avoid adding package managers unless a concrete implementation requires them.

## Validation commands

Run these commands before proposing a pull request:

```sh
python3 -m py_compile scripts/validate_mobile_iphone_platform.py
python3 scripts/validate_mobile_iphone_platform.py
python3 - <<'PY'
from pathlib import Path
required = [
    'index.html',
    'styles.css',
    'app.js',
    'manifest.webmanifest',
    'service-worker.js',
    'README.md',
    'docs/iphone-local-dev-setup.md',
]
missing = [path for path in required if not Path(path).is_file()]
if missing:
    raise SystemExit(f'missing required static files: {missing}')
print('static file contract is valid')
PY
```

For a local static smoke test:

```sh
python3 -m http.server 8000
```

Then open `http://localhost:8000` in the available browser environment.

## Review guidelines

Codex reviews should focus on P0/P1 issues only:

- Broken iPhone execution path.
- Unsafe command generation or command injection risk.
- Secret leakage or instructions that encourage storing secrets in tracked files.
- Static app regressions: missing required files, broken service worker assumptions, invalid manifest path, invalid links to mandatory docs.
- Dataset/schema regressions that make `scripts/validate_mobile_iphone_platform.py` fail.
- Documentation that promises unsupported OS-level control from iPhone-only tooling.

## Implementation guidance

- Preserve German UX text unless the task explicitly asks for English.
- Add exact commands, expected success signals, and rollback notes when changing docs or automation instructions.
- Use defensive shell examples: `set -eu`, quoted paths, explicit working directories, and clear failure messages.
- Keep generated command blocks copy-paste-safe for a-Shell/iSH where possible.
- Prefer standard library Python for validation logic.
- Prefer static files over build pipelines for the default deployment path.

## Pull request output expectations

Every Codex PR should include:

- Summary of changed files.
- Exact validation commands run.
- Validation result.
- Remaining iPhone/iOS limitation if relevant.
- Rollback note when changing workflow or setup behavior.
