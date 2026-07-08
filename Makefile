.PHONY: build test validate full-debug full-debug-deep init-github rebase-guard safe-ops-validate safe-ops-plan localhost-export-once localhost-export-write-var localhost-export-https operable-status operable-validate operable-export operable-doctor operable-serve operable-network network-status network-measure network-doctor depo-status depo-connect depo-serve device-exec-status device-exec-doctor agent-audit-validate trusted-ops-validate trusted-ops-report trusted-ops-report-local trusted-ops-report-external workflow-dispatch-validate hard-scan-full-space audit-streampipe audit-streampipe-full ops-route-validate ops-route-dry-run ops-route-dry-run-execute docker-ops-config docker-ops-services codex-setup codex-check run clean

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

agent-audit-validate:
	python3 scripts/validate_agent_audit.py --audit config/agent-objectives.audit.json --routes config/ops-route-matrix.example.json

trusted-ops-validate:
	python3 scripts/repo_trusted_ops.py validate --profile config/repo-trusted-ops.fullstack.json

trusted-ops-report:
	python3 scripts/repo_trusted_ops.py report --profile config/repo-trusted-ops.fullstack.json --write-report reports/repo-trusted-ops-report.json

trusted-ops-report-local:
	python3 scripts/repo_trusted_ops.py report --profile config/repo-trusted-ops.fullstack.json --execute-local --write-report reports/repo-trusted-ops-report.json

trusted-ops-report-external:
	python3 scripts/repo_trusted_ops.py report --profile config/repo-trusted-ops.fullstack.json --execute-local --probe-external --write-report reports/repo-trusted-ops-report.json

workflow-dispatch-validate:
	python3 scripts/validate_workflow_dispatch_dataset.py --dataset datasets/workflow-dispatch.fullstacked.dataset.json

hard-scan-full-space: validate agent-audit-validate trusted-ops-validate workflow-dispatch-validate ops-route-validate

audit-streampipe:
	python3 scripts/audit_valid_debug_streampipe.py --output-dir reports/audit-valid-debug-streampipe

audit-streampipe-full:
	mkdir -p reports
	python3 scripts/repo_trusted_ops.py report --profile config/repo-trusted-ops.fullstack.json --execute-local --write-report reports/repo-trusted-ops-report.json
	python3 scripts/ops_route_runner.py --route-matrix config/ops-route-matrix.example.json --execute-safe --write-report reports/ops-route-dry-run-report.json
	POSTGRES_PASSWORD=OPS_DRY_RUN_COMPOSE_PARSER_ONLY docker compose -f docker-compose.yml -f docker-compose.ops-dry-run.yml config > reports/docker-compose-ops-dry-run.config.yml
	POSTGRES_PASSWORD=OPS_DRY_RUN_COMPOSE_PARSER_ONLY docker compose -f docker-compose.yml -f docker-compose.ops-dry-run.yml config --services > reports/docker-compose-ops-dry-run.services.txt
	python3 scripts/audit_valid_debug_streampipe.py --output-dir reports/audit-valid-debug-streampipe

ops-route-validate:
	python3 scripts/ops_route_runner.py --route-matrix config/ops-route-matrix.example.json --validate-only

ops-route-dry-run:
	python3 scripts/ops_route_runner.py --route-matrix config/ops-route-matrix.example.json --write-report reports/ops-route-dry-run-report.json

ops-route-dry-run-execute:
	python3 scripts/ops_route_runner.py --route-matrix config/ops-route-matrix.example.json --execute-safe --write-report reports/ops-route-dry-run-report.json

docker-ops-config:
	POSTGRES_PASSWORD=OPS_DRY_RUN_COMPOSE_PARSER_ONLY docker compose -f docker-compose.yml -f docker-compose.ops-dry-run.yml config

docker-ops-services:
	POSTGRES_PASSWORD=OPS_DRY_RUN_COMPOSE_PARSER_ONLY docker compose -f docker-compose.yml -f docker-compose.ops-dry-run.yml config --services

codex-setup:
	bash .codex/setup.sh

codex-check:
	bash scripts/codex_fullstack_check.sh

run:
	docker compose up

clean:
	cargo clean
	docker compose down -v
