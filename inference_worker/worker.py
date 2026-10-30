from http.server import BaseHTTPRequestHandler, HTTPServer
import hashlib
import json
import os
import tempfile
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODELS_DIR = "/app/models" if os.path.exists("/app/models") else os.path.join(BASE_DIR, "models")
DEFAULT_CACHE_DIR = os.path.join(tempfile.gettempdir(), "trt_cache")

ENGINE_PATH = os.environ.get("ENGINE_PATH", os.path.join(DEFAULT_MODELS_DIR, "eo_detector_fp16.engine"))
MANIFEST_PATH = os.environ.get("MANIFEST_PATH", os.path.join(DEFAULT_MODELS_DIR, "manifest.json"))
CACHE_DIR = os.environ.get("TRT_CACHE_DIR", DEFAULT_CACHE_DIR)
PORT = int(os.environ.get("WORKER_PORT", "9000"))
WARMUP_SECONDS = float(os.environ.get("ENGINE_WARMUP_SEC", "2.0"))


def verify_engine():
    if not os.path.exists(ENGINE_PATH) or not os.path.exists(MANIFEST_PATH):
        return False, "missing_files", ""
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as mf:
            manifest = json.load(mf)
        expected = manifest.get("sha256", "")
        with open(ENGINE_PATH, "rb") as ef:
            actual = hashlib.sha256(ef.read()).hexdigest()
        if actual != expected:
            return False, expected, actual
        os.makedirs(CACHE_DIR, exist_ok=True)
        lock_file = os.path.join(CACHE_DIR, "fp16_execution_context.lock")
        with open(lock_file, "w", encoding="utf-8") as lf:
            lf.write(actual)
        return True, expected, actual
    except Exception as exc:
        print(f"[inference_worker] ERROR: cannot verify engine or write cache in {CACHE_DIR}: {exc}", flush=True)
        return False, "error", str(exc)


class WorkerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        valid, expected, actual = verify_engine()
        if self.path == "/status":
            code = 200 if valid else 500
            body = json.dumps({
                "service": "inference_worker",
                "engine_loaded": os.path.exists(ENGINE_PATH),
                "checksum_valid": valid,
                "expected_sha256": expected,
                "actual_sha256": actual,
            }).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress noisy healthcheck logs in production
        return


if __name__ == "__main__":
    if WARMUP_SECONDS > 0:
        time.sleep(WARMUP_SECONDS)
    ok, exp, act = verify_engine()
    print(f"[inference_worker] engine checksum valid={ok} (expected={exp[:12]}..., actual={act[:12]}...)", flush=True)
    HTTPServer(("0.0.0.0", PORT), WorkerHandler).serve_forever()
