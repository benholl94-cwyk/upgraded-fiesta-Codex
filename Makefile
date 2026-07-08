.PHONY: build test validate full-debug full-debug-deep init-github rebase-guard safe-ops-validate safe-ops-plan localhost-export-once localhost-export-https codex-setup codex-check run clean

build:
	cargo build --workspace

test:
	cargo test --workspace

validate:
	python3 scripts/validate_repo.py

full-debug:
	python3 scripts/full_debug.py --write-report

full-debug-deep:
	python3 scripts/full_debug.py --deep --write-report

init-github:
	python3 scripts/init_github_repo.py

rebase-guard:
	python3 scripts/rebase_guard.py

safe-ops-validate:
	python3 scripts/safe_write_edit_ops.py validate --object examples/safe-write-edit-ops.object.json

safe-ops-plan:
	python3 scripts/safe_write_edit_ops.py plan --object examples/safe-write-edit-ops.object.json

localhost-export-once:
	python3 scripts/localhost_export_server.py --scheme https --once

localhost-export-https:
	python3 scripts/localhost_export_server.py --scheme https --host 127.0.0.1 --port 9443

codex-setup:
	bash .codex/setup.sh

codex-check:
	bash scripts/codex_fullstack_check.sh

run:
	docker compose up

clean:
	cargo clean
	docker compose down -v
