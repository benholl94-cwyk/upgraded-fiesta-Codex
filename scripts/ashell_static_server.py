#!/usr/bin/env python3
"""Quiet local static server for a-Shell/iPhone previews.

This is intentionally small and dependency-free. It suppresses common iOS/Safari
client disconnect tracebacks such as BrokenPipeError and returns 204 for
/favicon.ico when the repository does not contain a favicon.
"""

from __future__ import annotations

import argparse
import errno
import http.server
import os
import socketserver
import sys
from pathlib import Path


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with iPhone-friendly noise reduction."""

    def do_GET(self) -> None:
        if self.path == "/favicon.ico" and not Path("favicon.ico").exists():
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if self.path == "/favicon.ico" and not Path("favicon.ico").exists():
            self.send_response(204)
            self.end_headers()
            return
        super().do_HEAD()

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            return
        except OSError as exc:
            if exc.errno in {errno.EPIPE, errno.ECONNRESET}:
                return
            raise

    def log_error(self, format: str, *args: object) -> None:
        message = format % args
        if "Broken pipe" in message or "Connection reset" in message:
            return
        super().log_error(format, *args)


class QuietThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request: object, client_address: object) -> None:
        exc_type, exc, _traceback = sys.exc_info()
        if exc_type in {BrokenPipeError, ConnectionResetError}:
            return
        if isinstance(exc, OSError) and exc.errno in {errno.EPIPE, errno.ECONNRESET}:
            return
        super().handle_error(request, client_address)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the upgraded-fiesta static platform quietly on iPhone/a-Shell.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="Bind port. Default: 8000")
    parser.add_argument("--directory", default=".", help="Directory to serve. Default: current directory")
    args = parser.parse_args()

    root = Path(args.directory).resolve()
    if not root.exists():
        print(f"ERROR: directory does not exist: {root}", file=sys.stderr)
        return 2

    os.chdir(root)
    handler = QuietHTTPRequestHandler
    server = QuietThreadingHTTPServer((args.host, args.port), handler)

    print(f"Serving upgraded-fiesta from {root}")
    print(f"Open http://localhost:{args.port}/")
    print("Stop with Ctrl-C.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
