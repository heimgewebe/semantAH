import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict
from urllib import request


# Original post_upsert implementation for comparison
def post_upsert_original(
    endpoint: str, payload: Dict[str, Any], *, timeout: float
) -> Dict[str, Any] | None:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint, data=data, headers={"Content-Type": "application/json"}
    )
    with request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8").strip()
        if not body:
            return None
        return json.loads(body)


class DummyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(content_length)

        # Raw write avoids BaseHTTPRequestHandler's slow send_response/send_header
        # which can trigger Nagle's algorithm issues or DNS lookups depending on Python version
        response_body = b'{"status": "ok"}'
        self.wfile.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 16\r\n"
            b"Connection: keep-alive\r\n\r\n" + response_body
        )
        self.wfile.flush()

    def address_string(self):
        # Prevents slow DNS reverse lookups in some environments
        return self.client_address[0]

    def log_message(self, format, *args):
        pass


def run_dummy_server(port):
    server = HTTPServer(("127.0.0.1", port), DummyHandler)
    server.serve_forever()


def main():
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from scripts.push_index import PooledUpsertClient

    # Find a free port locally
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    server_thread = threading.Thread(target=run_dummy_server, args=(port,), daemon=True)
    server_thread.start()
    time.sleep(1)  # Wait for server to start

    endpoint = f"http://127.0.0.1:{port}/index/upsert"
    payload = {"test": "data"}
    iterations = 500

    print(f"Running baseline benchmark with {iterations} iterations...")
    start_time = time.time()
    for _ in range(iterations):
        post_upsert_original(endpoint, payload, timeout=5.0)
    end_time = time.time()

    elapsed_baseline = end_time - start_time
    print(
        f"Baseline: {elapsed_baseline:.4f} seconds ({elapsed_baseline / iterations:.6f} s/req)"
    )

    print(f"Running pooled benchmark with {iterations} iterations...")
    client = PooledUpsertClient(endpoint, timeout=5.0)
    try:
        start_time = time.time()
        for _ in range(iterations):
            client.post_upsert(payload)
        end_time = time.time()
    finally:
        client.close()

    elapsed_pooled = end_time - start_time
    print(
        f"Pooled:   {elapsed_pooled:.4f} seconds ({elapsed_pooled / iterations:.6f} s/req)"
    )

    improvement = (elapsed_baseline - elapsed_pooled) / elapsed_baseline * 100
    print(f"Improvement: {improvement:.2f}%")


if __name__ == "__main__":
    main()
