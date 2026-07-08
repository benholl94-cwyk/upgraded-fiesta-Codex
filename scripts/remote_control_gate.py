#!/usr/bin/env python3
"""Consent-gated remote-control route switch.

This controller exposes a machine-readable master switch for non-destructive
remote-control routes. It does not auto-click UI prompts, bypass consent,
escalate privileges, run sudo, or execute arbitrary shell commands.

Activation requires a local accept action:
  python3 scripts/remote_control_gate.py accept --source local_user_screen_accept
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.server
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "datasets" / "remote-control.config.json"
REPORT_SCHEMA = "upgraded-fiesta.remote-control.report.v1"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON root must be object: {path}")
    return payload


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    if config.get("schema") != "upgraded-fiesta.remote-control.config.v1":
        raise RuntimeError("invalid remote control config schema")
    return config


def expand_runtime_path(raw: str) -> Path:
    home = os.environ.get("HOME", str(Path.home()))
    expanded = raw.replace("$HOME", home).replace("${HOME}", home).replace("$home", home).replace("${home}", home)
    return Path(os.path.expandvars(os.path.expanduser(expanded))).resolve()


def consent_path(config: dict[str, Any]) -> Path:
    return expand_runtime_path(config["runtime"]["consent_file"])


def route_state_path(config: dict[str, Any]) -> Path:
    return expand_runtime_path(config["runtime"]["route_state_file"])


def read_consent(config: dict[str, Any]) -> dict[str, Any]:
    path = consent_path(config)
    if not path.is_file():
        return {
            "schema": "upgraded-fiesta.remote-control.consent-state.v1",
            "accepted": False,
            "denied": False,
            "source": "missing_state",
            "remote_control_enable_any": False,
            "routes_enable_all": False,
            "auto_accept_popup": False
        }
    return load_json(path)


def write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    path.write_bytes(data)
    return {"path": str(path), "bytes": len(data), "sha256": sha256_bytes(data)}


def route_states(config: dict[str, Any], consent: dict[str, Any]) -> list[dict[str, Any]]:
    enabled = bool(consent.get("accepted")) and bool(consent.get("remote_control_enable_any"))
    states = []
    for route in config["routes"]:
        states.append({
            **route,
            "enabled": bool(enabled and route.get("enabled_after_accept") and not route.get("destructive")),
            "enabled_reason": "local_user_accept" if enabled else "blocked_until_local_accept"
        })
    return states


def base_report(command: str, config: dict[str, Any]) -> dict[str, Any]:
    consent = read_consent(config)
    routes = route_states(config, consent)
    return {
        "schema": REPORT_SCHEMA,
        "generated_at_utc": utc_now(),
        "ok": True,
        "command": command,
        "repository": {
            "full_name": config["repository"]["full_name"],
            "default_branch": config["repository"]["default_branch"],
            "known_main_head": config["repository"]["known_main_head_after_device_exec"],
        },
        "consent": consent,
        "routes": routes,
        "blocked_routes": config["blocked_routes"],
        "security": config["security"],
    }


def accept(config: dict[str, Any], source: str) -> dict[str, Any]:
    if source not in {"local_user_screen_accept", "local_user_cli_accept", "local_user_owner_accept"}:
        raise RuntimeError("accept source must be explicit local user accept")
    payload = {
        "schema": "upgraded-fiesta.remote-control.consent-state.v1",
        "accepted": True,
        "denied": False,
        "source": source,
        "accepted_at_utc": utc_now(),
        "remote_control_enable_any": True,
        "routes_enable_all": True,
        "auto_accept_popup": False,
        "bypass_user_consent": False,
    }
    consent_meta = write_json(consent_path(config), payload)
    report = base_report("accept", config)
    report["consent_file"] = consent_meta
    report["route_state_file"] = write_json(route_state_path(config), {"schema": "upgraded-fiesta.remote-control.routes-state.v1", "generated_at_utc": utc_now(), "routes": report["routes"]})
    return report


def deny(config: dict[str, Any], source: str) -> dict[str, Any]:
    payload = {
        "schema": "upgraded-fiesta.remote-control.consent-state.v1",
        "accepted": False,
        "denied": True,
        "source": source,
        "denied_at_utc": utc_now(),
        "remote_control_enable_any": False,
        "routes_enable_all": False,
        "auto_accept_popup": False,
        "bypass_user_consent": False,
    }
    consent_meta = write_json(consent_path(config), payload)
    report = base_report("deny", config)
    report["consent_file"] = consent_meta
    report["route_state_file"] = write_json(route_state_path(config), {"schema": "upgraded-fiesta.remote-control.routes-state.v1", "generated_at_utc": utc_now(), "routes": report["routes"]})
    return report


class GateHandler(http.server.BaseHTTPRequestHandler):
    server_version = "upgraded-fiesta-remote-control-gate/1.0"

    def write_response(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        config = self.server.config  # type: ignore[attr-defined]
        parsed = urlparse(self.path)
        report = base_report("serve", config)
        enabled_paths = {route["path"]: route for route in report["routes"] if route.get("enabled")}
        if parsed.path in {"/", "/status"}:
            self.write_response(200, report)
        elif parsed.path in enabled_paths:
            self.write_response(200, {"schema": "upgraded-fiesta.remote-control.route-ok.v1", "ok": True, "route": enabled_paths[parsed.path]})
        else:
            self.write_response(403, {"schema": "upgraded-fiesta.remote-control.route-blocked.v1", "ok": False, "path": parsed.path, "reason": "route_disabled_until_local_user_accept"})

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(json.dumps({"schema": "upgraded-fiesta.remote-control.access.v1", "generated_at_utc": utc_now(), "client": self.client_address[0], "message": fmt % args}, sort_keys=True) + "\n")


def serve(config: dict[str, Any]) -> int:
    host = config["runtime"]["default_bind_host"]
    port = int(config["runtime"]["default_port"])
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("remote-control gate refuses non-loopback default bind")
    server = http.server.ThreadingHTTPServer((host, port), GateHandler)
    server.config = config  # type: ignore[attr-defined]
    print(json.dumps({"schema": "upgraded-fiesta.remote-control.server.v1", "ok": True, "base_url": f"http://{host}:{port}", "requires_local_accept": True}, indent=2, sort_keys=True), flush=True)
    server.serve_forever()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consent-gated remote-control route switch")
    parser.add_argument("command", choices=["status", "accept", "deny", "serve"])
    parser.add_argument("--source", default="local_user_cli_accept")
    args = parser.parse_args(argv)
    try:
        config = load_config()
        if args.command == "status":
            report = base_report("status", config)
        elif args.command == "accept":
            report = accept(config, args.source)
        elif args.command == "deny":
            report = deny(config, args.source)
        else:
            return serve(config)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.get("ok") else 1
    except Exception as exc:
        print(json.dumps({"schema": "upgraded-fiesta.remote-control.error.v1", "generated_at_utc": utc_now(), "ok": False, "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
