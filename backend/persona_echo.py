"""
Echo target v2: discriminates by persona. Returns hit_token=PASSED only
when the persona name is in the wrapper. Used to test persona x target
analytics against a target that has persona-aware detection.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys

# Which personas does this target "accept"? Configurable per-port.
# Default: any persona-containing wrapper passes.
ACCEPTED_PERSONAS = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else {
    "DAN", "BetterDAN", "DeveloperMode", "AntiGPT", "PersonGPT", "Maximum",
    "STAN", "DUDE", "BasedGPT", "JailBreak", "AIM", "UCAR"
}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        body_lower = body.lower()
        matched_persona = None
        for p in ACCEPTED_PERSONAS:
            if p.lower() in body_lower:
                matched_persona = p
                break
        hit = matched_persona is not None
        resp = {
            "received_len": len(body),
            "matched_persona": matched_persona,
            "accepted_set": sorted(ACCEPTED_PERSONAS),
            "result": "PASSED" if hit else "REFUSED",
        }
        data = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args, **kwargs):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8770
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()