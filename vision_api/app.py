from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import urllib.request

WORKER_URL = os.environ.get("WORKER_URL", "http://inference_worker:9000")
DB_HOST = os.environ.get("DB_HOST", "postgres")
APP_PORT = int(os.environ.get("APP_PORT", "8000"))


def check_worker():
    try:
        req = urllib.request.Request(f"{WORKER_URL}/status")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("engine_loaded") is True and data.get("checksum_valid") is True
    except Exception:
        return False
    return False


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            worker_ok = check_worker()
            status = "healthy" if worker_ok else "degraded"
            code = 200 if worker_ok else 503
            self._send(code, {"status": status, "worker_ready": worker_ok, "service": "vision_api"})
        elif self.path == "/api/v1/detect":
            worker_ok = check_worker()
            if not worker_ok:
                self._send(503, {"error": "inference_worker unavailable or engine invalid"})
                return
            self._send(200, {"stream": "EO_CAM_01", "detections": [{"cls": "vehicle", "conf": 0.91}]})
        else:
            self._send(404, {"error": "not found"})


if __name__ == "__main__":
    ready = check_worker()
    print(f"Starting vision_api on port {APP_PORT}, worker={WORKER_URL}, initial_worker_ready={ready}", flush=True)
    HTTPServer(("0.0.0.0", APP_PORT), Handler).serve_forever()
