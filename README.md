# Fullstack Heavy Metal

Generated from the uploaded Markdown specification as a Rust workspace.

## Includes

- core types, traits, events and configuration
- gateway skeleton with health/chat/session/agent/memory/tool handler modules
- agent runtime modules for pi, codex and cli backends
- memory modules for fts, vector, hybrid, embeddings, dreaming, episodic and semantic memory
- channel crates for telegram, discord, slack and whatsapp
- tool crates for exec, browser, web and media
- plugin, sdk, session, vector, cron, auth and cli crates
- ui scaffold, docker files, makefile, configuration, SQL and validator
- mobile-visible Open_Source deployment checkpoint documentation in `docs/open-source-mobile-status.md`
- mobile device manifest exporter documentation in `docs/mobile-device-manifest.md`


## Docker Compose startup

The root `docker-compose.yml` intentionally does not contain a default database password. Set `POSTGRES_PASSWORD` in the shell before running Compose, or provide it through your deployment secret manager. You may also override `POSTGRES_USER` and `POSTGRES_DB`; they default to `heavy` and `heavy_metal`.

```sh
POSTGRES_PASSWORD="replace-with-a-strong-password" docker compose up -d
```

Use `.env.production.example` as a safe template only. Keep the copied `.env` file local and uncommitted.

## Codex fullstack setup

Repository-level Codex behavior is defined in:

- `AGENTS.md`
- `.codex/config.toml`
- `.codex/setup.sh`
- `.codex/maintenance.sh`
- `scripts/codex_fullstack_setup.sh`
- `scripts/codex_fullstack_check.sh`

For Codex cloud, configure the environment setup command as:

```sh
bash .codex/setup.sh
```

For cached Codex cloud environments, configure the maintenance command as:

```sh
bash .codex/maintenance.sh
```

For a complete local or cloud verification pass, run:

```sh
make codex-check
```

## Validate

```sh
python3 scripts/validate_repo.py
```
