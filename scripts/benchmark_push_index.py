import json
import time
import http.server
import http.client
import urllib.parse
import threading
import socket
from urllib import request
from typing import Dict, Any
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.push_index import PooledUpsertClient

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

class DummyHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        self.rfile.read(content_length)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

    def log_message(self, format, *args):
        pass

def run_dummy_server(port):
    server = http.server.HTTPServer(('127.0.0.1', port), DummyHandler)
    server.serve_forever()

def main():
    # Find a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]

    server_thread = threading.Thread(target=run_dummy_server, args=(port,), daemon=True)
    server_thread.start()
    time.sleep(1) # Wait for server to start

    endpoint = f"http://127.0.0.1:{port}/index/upsert"
    payload = {"test": "data"}
    iterations = 500

    print(f"Running baseline benchmark with {iterations} iterations...")
    start_time = time.time()
    for _ in range(iterations):
        post_upsert_original(endpoint, payload, timeout=5.0)
    end_time = time.time()

    elapsed_baseline = end_time - start_time
    print(f"Baseline: {elapsed_baseline:.4f} seconds ({elapsed_baseline/iterations:.6f} s/req)")

    print(f"Running pooled benchmark with {iterations} iterations...")
    client = PooledUpsertClient(endpoint, timeout=5.0)
    start_time = time.time()
    for _ in range(iterations):
        client.post_upsert(payload)
    end_time = time.time()

    elapsed_pooled = end_time - start_time
    print(f"Pooled:   {elapsed_pooled:.4f} seconds ({elapsed_pooled/iterations:.6f} s/req)")

    improvement = (elapsed_baseline - elapsed_pooled) / elapsed_baseline * 100
    print(f"Improvement: {improvement:.2f}%")

if __name__ == "__main__":
    main()
