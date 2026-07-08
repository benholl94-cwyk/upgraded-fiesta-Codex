.PHONY: build test validate full-debug full-debug-deep init-github codex-setup codex-check run clean

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

codex-setup:
	bash .codex/setup.sh

codex-check:
	bash scripts/codex_fullstack_check.sh

run:
	docker compose up

clean:
	cargo clean
	docker compose down -v
