.PHONY: build test validate full-debug full-debug-deep init-github rebase-guard safe-ops-validate safe-ops-plan localhost-export-once localhost-export-write-var localhost-export-https operable-status operable-validate operable-export operable-doctor operable-serve operable-network network-status network-measure network-doctor depo-status depo-connect depo-serve device-exec-status device-exec-doctor remote-control-status remote-control-accept remote-control-deny remote-control-serve codex-setup codex-check run clean

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

localhost-export-write-var:
	python3 scripts/localhost_export_server.py --scheme https --write --output-dir "$${HOME}/usr/var/upgraded-fiesta-Codex/localhost-export"

localhost-export-https:
	python3 scripts/localhost_export_server.py --scheme https --host 127.0.0.1 --port 9443

operable-status:
	python3 scripts/operable_repo.py status

operable-validate:
	python3 scripts/operable_repo.py validate

operable-export:
	python3 scripts/operable_repo.py export

operable-doctor:
	python3 scripts/operable_repo.py doctor

operable-serve:
	python3 scripts/operable_repo.py serve

operable-network:
	python3 scripts/operable_repo.py network measure

network-status:
	python3 scripts/network_capabilities.py status

network-measure:
	python3 scripts/network_capabilities.py measure

network-doctor:
	python3 scripts/network_capabilities.py doctor

depo-status:
	python3 scripts/depo_server.py status

depo-connect:
	python3 scripts/depo_server.py connect

depo-serve:
	python3 scripts/depo_server.py serve --host 127.0.0.1 --port 9797

device-exec-status:
	python3 scripts/device_exec_check.py status

device-exec-doctor:
	python3 scripts/device_exec_check.py doctor

remote-control-status:
	python3 scripts/remote_control_gate.py status

remote-control-accept:
	python3 scripts/remote_control_gate.py accept --source local_user_cli_accept

remote-control-deny:
	python3 scripts/remote_control_gate.py deny --source local_user_cli_deny

remote-control-serve:
	python3 scripts/remote_control_gate.py serve

codex-setup:
	bash .codex/setup.sh

codex-check:
	bash scripts/codex_fullstack_check.sh

run:
	docker compose up

clean:
	cargo clean
	docker compose down -v
