#!/usr/bin/env python3
"""Standalone network capability inventory and real bandwidth measurer.

The default bandwidth measurement is a localhost TCP loopback transfer. It emits
actual runtime measurements from the current environment without third-party
services, secrets, packet capture, or external network probes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
from pathlib import Path
import queue
import socket
import ssl
import subprocess
import sys
import threading
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "datasets" / "network-capabilities.config.json"
REPORT_SCHEMA = "upgraded-fiesta.network-capabilities.report.v1"


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
    if config.get("schema") != "upgraded-fiesta.network-capabilities.config.v1":
        raise RuntimeError("invalid network capabilities config schema")
    return config


def run_command(argv: list[str], timeout: int = 5) -> dict[str, Any]:
    try:
        completed = subprocess.run(argv, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        return {"argv": argv, "returncode": completed.returncode, "ok": completed.returncode == 0, "output_tail": completed.stdout[-6000:]}
    except FileNotFoundError:
        return {"argv": argv, "returncode": 127, "ok": False, "output_tail": f"command not found: {argv[0]}"}
    except subprocess.TimeoutExpired as exc:
        return {"argv": argv, "returncode": 124, "ok": False, "output_tail": f"timeout after {timeout}s\n{exc.stdout or ''}"}


def bandwidth_record(bytes_count: int, elapsed_seconds: float) -> dict[str, Any]:
    bps = bytes_count / elapsed_seconds if elapsed_seconds > 0 else 0.0
    return {
        "bytes": bytes_count,
        "elapsed_seconds": elapsed_seconds,
        "bytes_per_second": bps,
        "bits_per_second": bps * 8.0,
        "megabits_per_second_decimal": (bps * 8.0) / 1_000_000.0,
        "mebibytes_per_second_binary": bps / (1024.0 * 1024.0),
    }


def loopback_tcp_sample(bind_host: str, payload_bytes: int, timeout_seconds: int) -> dict[str, Any]:
    ready: queue.Queue[tuple[int, str | None]] = queue.Queue(maxsize=1)
    result: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
    payload = b"N" * min(1024 * 1024, payload_bytes)

    def server() -> None:
        received = 0
        start = 0.0
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind((bind_host, 0))
                srv.listen(1)
                srv.settimeout(timeout_seconds)
                ready.put((srv.getsockname()[1], None))
                conn, _ = srv.accept()
                with conn:
                    conn.settimeout(timeout_seconds)
                    start = time.perf_counter()
                    while received < payload_bytes:
                        chunk = conn.recv(1024 * 1024)
                        if not chunk:
                            break
                        received += len(chunk)
                    elapsed = time.perf_counter() - start
                    result.put({"ok": received == payload_bytes, "received_bytes": received, "elapsed_seconds": elapsed})
        except Exception as exc:
            if ready.empty():
                ready.put((0, str(exc)))
            result.put({"ok": False, "received_bytes": received, "elapsed_seconds": 0.0, "error": str(exc)})

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    port, error = ready.get(timeout=timeout_seconds)
    if error:
        return {"ok": False, "error": error}

    sent = 0
    start = time.perf_counter()
    with socket.create_connection((bind_host, port), timeout=timeout_seconds) as client:
        client.settimeout(timeout_seconds)
        while sent < payload_bytes:
            block = payload[: min(len(payload), payload_bytes - sent)]
            client.sendall(block)
            sent += len(block)
        client.shutdown(socket.SHUT_WR)
    client_elapsed = time.perf_counter() - start
    server_result = result.get(timeout=timeout_seconds)
    record = bandwidth_record(sent, max(client_elapsed, float(server_result.get("elapsed_seconds", 0.0))))
    record.update({
        "ok": bool(server_result.get("ok")) and sent == payload_bytes,
        "bind_host": bind_host,
        "port_scope": "ephemeral_loopback",
        "sent_bytes": sent,
        "received_bytes": server_result.get("received_bytes"),
        "client_elapsed_seconds": client_elapsed,
        "server_elapsed_seconds": server_result.get("elapsed_seconds"),
        "payload_sha256": sha256_bytes(str(payload_bytes).encode("utf-8")),
    })
    if "error" in server_result:
        record["error"] = server_result["error"]
    return record


def measure_loopback(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config["runtime"]
    samples = []
    for index in range(int(runtime["loopback_samples"])):
        item = loopback_tcp_sample(str(runtime["bind_host"]), int(runtime["loopback_payload_bytes"]), int(runtime["loopback_timeout_seconds"]))
        item["sample_index"] = index
        samples.append(item)
    valid = [s for s in samples if s.get("ok")]
    mbps_values = [float(s["megabits_per_second_decimal"]) for s in valid]
    mib_values = [float(s["mebibytes_per_second_binary"]) for s in valid]
    return {
        "ok": len(valid) == len(samples),
        "method": "localhost_tcp_loopback_send_recv",
        "payload_bytes_per_sample": int(runtime["loopback_payload_bytes"]),
        "sample_count": len(samples),
        "valid_sample_count": len(valid),
        "samples": samples,
        "summary": {
            "min_mbps": min(mbps_values) if mbps_values else None,
            "max_mbps": max(mbps_values) if mbps_values else None,
            "avg_mbps": sum(mbps_values) / len(mbps_values) if mbps_values else None,
            "min_mib_per_second": min(mib_values) if mib_values else None,
            "max_mib_per_second": max(mib_values) if mib_values else None,
            "avg_mib_per_second": sum(mib_values) / len(mib_values) if mib_values else None,
        }
    }


def dns_inventory(config: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for target in config["runtime"].get("dns_targets", []):
        try:
            infos = socket.getaddrinfo(str(target), None)
            addresses = sorted({item[4][0] for item in infos})
            records.append({"target": target, "ok": True, "addresses": addresses, "address_count": len(addresses)})
        except Exception as exc:
            records.append({"target": target, "ok": False, "error": str(exc)})
    return records


def tcp_probe(config: dict[str, Any]) -> list[dict[str, Any]]:
    probes = []
    for target in config["runtime"].get("tcp_probe_targets", []):
        host, port = str(target["host"]), int(target["port"])
        start = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=1.0):
                elapsed = time.perf_counter() - start
                probes.append({"label": target.get("label"), "host": host, "port": port, "ok": True, "elapsed_seconds": elapsed, "required": bool(target.get("required", False))})
        except Exception as exc:
            elapsed = time.perf_counter() - start
            probes.append({"label": target.get("label"), "host": host, "port": port, "ok": False, "elapsed_seconds": elapsed, "required": bool(target.get("required", False)), "error": str(exc)})
    return probes


def interface_inventory() -> dict[str, Any]:
    hostname = socket.gethostname()
    inventory = {
        "hostname": hostname,
        "fqdn": socket.getfqdn(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "socket_has_ipv6": socket.has_ipv6,
        "openssl_version": getattr(ssl, "OPENSSL_VERSION", None),
        "commands": {
            "ip_addr": run_command(["ip", "addr"], timeout=3),
            "ifconfig": run_command(["ifconfig"], timeout=3),
            "route": run_command(["route", "-n"], timeout=3),
            "netstat_route": run_command(["netstat", "-rn"], timeout=3),
        }
    }
    try:
        inventory["hostname_addresses"] = sorted({item[4][0] for item in socket.getaddrinfo(hostname, None)})
    except Exception as exc:
        inventory["hostname_addresses_error"] = str(exc)
    return inventory


def build_report(command: str, config: dict[str, Any], *, include_measurement: bool) -> dict[str, Any]:
    measurements: dict[str, Any] = {
        "dns_resolution": dns_inventory(config),
        "tcp_port_probe": tcp_probe(config),
    }
    if include_measurement:
        measurements["loopback_tcp_bandwidth"] = measure_loopback(config)
    report = {
        "schema": REPORT_SCHEMA,
        "generated_at_utc": utc_now(),
        "command": command,
        "ok": True,
        "repository": {
            "full_name": config["repository"]["full_name"],
            "default_branch": config["repository"]["default_branch"],
            "known_main_head": config["repository"]["known_main_head_after_operable_repo"],
        },
        "capabilities": {
            **config["capabilities"],
            "interface_inventory": interface_inventory(),
        },
        "measurements": measurements,
        "security": config["security"],
    }
    required_probe_failures = [p for p in measurements["tcp_port_probe"] if p.get("required") and not p.get("ok")]
    if required_probe_failures:
        report["ok"] = False
        report["required_probe_failures"] = required_probe_failures
    if include_measurement and not measurements["loopback_tcp_bandwidth"].get("ok"):
        report["ok"] = False
    return report


def write_report(report: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    state_root = ROOT / config["runtime"]["state_root"]
    state_root.mkdir(parents=True, exist_ok=True)
    path = state_root / "network-capabilities.report.json"
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8")
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(payload.encode("utf-8")), "sha256": sha256_bytes(payload.encode("utf-8"))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory network capabilities and measure real loopback bandwidth.")
    parser.add_argument("command", choices=["status", "measure", "doctor"])
    args = parser.parse_args(argv)
    try:
        config = load_config()
        include_measurement = args.command in {"measure", "doctor"}
        report = build_report(args.command, config, include_measurement=include_measurement)
        if args.command == "doctor":
            report["runtime_report"] = write_report(report, config)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.get("ok") else 1
    except Exception as exc:
        print(json.dumps({"schema": "upgraded-fiesta.network-capabilities.error.v1", "generated_at_utc": utc_now(), "ok": False, "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
