#!/usr/bin/env python3
"""Small local static server for a-Shell previews."""

import argparse
import http.server
import os
import socketserver
import sys
from pathlib import Path


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/favicon.ico" and not Path("favicon.ico").exists():
            self.send_response(204)
            self.end_headers()
            return
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

    def copyfile(self, source, outputfile):
        try:
            return http.server.SimpleHTTPRequestHandler.copyfile(self, source, outputfile)
        except (BrokenPipeError, ConnectionResetError):
            return None


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        exc_type, _exc, _traceback = sys.exc_info()
        if exc_type in (BrokenPipeError, ConnectionResetError):
            return
        return http.server.HTTPServer.handle_error(self, request, client_address)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--directory", default=".")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        print("ashell static server self-test ok")
        return 0
    root = Path(args.directory).resolve()
    if not root.exists():
        print("ERROR: directory does not exist: %s" % root, file=sys.stderr)
        return 2
    os.chdir(str(root))
    server = Server((args.host, args.port), Handler)
    print("Serving upgraded-fiesta from %s" % root)
    print("Open http://localhost:%s/" % args.port)
    print("Stop with Ctrl-C.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
