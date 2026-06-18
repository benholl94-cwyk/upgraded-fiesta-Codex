#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import http.server

VERSION = "0.1.0"
REQUIRED_DIRS = ["data", "logs", "runs", "datasets", "docs", "exports", "settings", "tmp"]


def ensure_workspace(path: str) -> pathlib.Path:
    root = pathlib.Path(path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_DIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / ".ghm_workspace.json").write_text(json.dumps({"ok": True, "version": VERSION, "workspace": str(root)}, indent=2) + "\n")
    return root


def cmd_init(args):
    root = ensure_workspace(args.workspace)
    print(json.dumps({"ok": True, "workspace": str(root)}, indent=2))
    return 0


def cmd_status(args):
    root = ensure_workspace(args.workspace)
    print(json.dumps({"ok": True, "workspace": str(root), "required_dirs": REQUIRED_DIRS}, indent=2))
    return 0


def cmd_serve(args):
    root = ensure_workspace(args.workspace)
    os.chdir(root)
    print(json.dumps({"ok": True, "url": f"http://{args.host}:{args.port}", "workspace": str(root)}, sort_keys=True), flush=True)
    http.server.test(HandlerClass=QuietHandler, port=args.port, bind=args.host)
    return 0


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def handle_one_request(self):
        try:
            return super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            return


def build_parser():
    p = argparse.ArgumentParser(prog="python3 -m ghm_core.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in [("init-workspace", cmd_init), ("doctor", cmd_status), ("status", cmd_status), ("serve", cmd_serve)]:
        sp = sub.add_parser(name)
        sp.add_argument("--workspace", required=True)
        sp.add_argument("--host", default="127.0.0.1")
        sp.add_argument("--port", type=int, default=18789)
        sp.set_defaults(func=fn)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
