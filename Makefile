.PHONY: build test validate run clean

build:
	cargo build --workspace

test:
	cargo test --workspace

validate:
	python3 scripts/validate_repo.py

run:
	docker compose up

clean:
	cargo clean
	docker compose down -v
