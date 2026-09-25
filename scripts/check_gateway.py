"""Run the real gateway nginx.conf against stub upstreams and check Host/Origin filtering.

Protects the loopback-only API from DNS rebinding and cross-site writes. Needs an
nginx binary (NGINX_BIN, default: nginx on PATH); no Docker or archive data.
"""

import http.server
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "infra" / "gateway" / "nginx.conf"
UPSTREAMS = ("frontend:80", "backend:3000", "ai:8002")
GATEWAY_PORTS = (8080, 3000, 8002)


class Stub(http.server.BaseHTTPRequestHandler):
    def _answer(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        body = b"upstream"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = do_DELETE = do_PUT = do_PATCH = _answer

    def log_message(self, *args):
        pass


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def render(stub_port, ports):
    text = CONFIG.read_text()
    for upstream in UPSTREAMS:
        text = text.replace(f"http://{upstream}", f"http://127.0.0.1:{stub_port}")
    for original, actual in zip(GATEWAY_PORTS, ports):
        text = re.sub(rf"listen {original};", f"listen 127.0.0.1:{actual};", text)
    return text


def request(port, path, host, origin=None, method="GET"):
    headers = {"Host": host}
    if origin is not None:
        headers["Origin"] = origin
    data = b"{}" if method != "GET" else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def cases(ui, api, mcp):
    # (name, port, path, Host, Origin, method, expected status)
    return [
        ("UI via 127.0.0.1", ui, "/", "127.0.0.1:8080", None, "GET", 200),
        ("UI via localhost", ui, "/", "localhost:8080", None, "GET", 200),
        ("UI via [::1]", ui, "/", "[::1]:8080", None, "GET", 200),
        ("UI Host is case-insensitive", ui, "/", "LocalHost:8080", None, "GET", 200),
        ("UI same-origin POST", ui, "/api/documents", "127.0.0.1:8080", "http://127.0.0.1:8080", "POST", 200),
        ("UI rebinding Host", ui, "/", "attacker.example:8080", None, "GET", 403),
        ("UI rebinding Host with its own Origin", ui, "/api/documents", "attacker.example:8080",
         "http://attacker.example:8080", "POST", 403),
        ("UI loopback-looking suffix", ui, "/", "localhost.attacker.example:8080", None, "GET", 403),
        ("UI cross-site POST", ui, "/api/documents", "127.0.0.1:8080", "http://attacker.example", "POST", 403),
        ("UI other local port POST", ui, "/api/documents", "127.0.0.1:8080", "http://127.0.0.1:5173", "POST", 403),
        ("UI opaque Origin", ui, "/api/documents", "127.0.0.1:8080", "null", "POST", 403),
        ("API health", api, "/api/health", "127.0.0.1:3000", None, "GET", 200),
        ("API Swagger same-origin", api, "/api/documents", "localhost:3000", "http://localhost:3000", "POST", 200),
        ("API rebinding Host", api, "/api/documents", "attacker.example:3000", None, "GET", 403),
        ("API cross-site DELETE", api, "/api/documents/x", "127.0.0.1:3000", "http://attacker.example", "DELETE", 403),
        ("MCP client without Origin", mcp, "/mcp", "127.0.0.1:8002", None, "POST", 200),
        ("MCP rebinding Host", mcp, "/mcp", "attacker.example:8002", None, "POST", 403),
        ("MCP Inspector on another loopback port", mcp, "/mcp", "localhost:8002", "http://localhost:6274",
         "POST", 200),
        ("MCP cross-site browser", mcp, "/mcp", "localhost:8002", "http://attacker.example", "POST", 403),
        ("MCP other paths", mcp, "/", "127.0.0.1:8002", None, "GET", 404),
    ]


def main():
    nginx = os.environ.get("NGINX_BIN", "nginx")
    stub_port = free_port()
    ports = [free_port() for _ in GATEWAY_PORTS]
    stub = http.server.ThreadingHTTPServer(("127.0.0.1", stub_port), Stub)
    threading.Thread(target=stub.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "logs").mkdir()
        Path(tmp, "gateway.conf").write_text(render(stub_port, ports))
        Path(tmp, "nginx.conf").write_text(
            f"pid {tmp}/nginx.pid;\nerror_log {tmp}/logs/error.log;\nevents {{}}\n"
            f"http {{\n  client_body_temp_path {tmp}/body;\n  proxy_temp_path {tmp}/proxy;\n"
            f"  include {tmp}/gateway.conf;\n}}\n"
        )
        test = subprocess.run([nginx, "-t", "-p", tmp, "-c", f"{tmp}/nginx.conf"], capture_output=True, text=True)
        if test.returncode:
            print(test.stderr, file=sys.stderr)
            return 1
        server = subprocess.Popen([nginx, "-p", tmp, "-c", f"{tmp}/nginx.conf", "-g", "daemon off;"])
        try:
            for _ in range(50):
                try:
                    socket.create_connection(("127.0.0.1", ports[-1]), timeout=0.2).close()
                    break
                except OSError:
                    time.sleep(0.1)
            failures = 0
            for name, port, path, host, origin, method, expected in cases(*ports):
                actual = request(port, path, host, origin, method)
                ok = actual == expected
                failures += not ok
                print(f"{'ok  ' if ok else 'FAIL'} {name}: {actual} (expected {expected})")
        finally:
            server.terminate()
            server.wait(timeout=10)
            stub.shutdown()
    print(f"{failures} gateway check(s) failed" if failures else "Gateway Host/Origin checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
