"""Minimal local echo target for testing the mutator's fire loop.

POST anything; responds with the body parsed back as JSON plus a
'hit_token' field set to "OBJECTIVE_ACHIEVED" only when the request body
contains the substring "secret".

This lets us fire variants through the mutator and verify hit detection
end-to-end without hitting any external target.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        hit = "secret" in body.lower()
        resp = {
            "received": body[:200],
            "len": len(body),
            "hit_token": "OBJECTIVE_ACHIEVED" if hit else "REFUSED",
        }
        data = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args, **kwargs):
        pass  # silence


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()