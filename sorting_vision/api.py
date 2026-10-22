"""Synchronous HTTP interface for offline video analysis; no extra web framework."""
from __future__ import annotations

import argparse
import hmac
import json
import mimetypes
import os
import re
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .inference import ARTIFACTS, DEFAULT_WEIGHTS, run_video, verify_models


def create_server(host, port, data_dir, *, weights=DEFAULT_WEIGHTS, device="cpu", max_upload_mb=256,
                  timeout=1800, api_key=None, runner=run_video):
    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    inference_slot = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "SortingVision/0.2"

        def _json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self):
            if api_key and not hmac.compare_digest(
                self.headers.get("Authorization", "").encode("utf-8"), f"Bearer {api_key}".encode("utf-8")
            ):
                self._json(401, {"error": "unauthorized"})
                return False
            return True

        def do_GET(self):
            route = urlparse(self.path).path
            if route == "/health":
                self._json(200, {"status": "ok", "model": "YOLO11n-V2", "mode": "offline-video"})
                return
            if not self._authorized():
                return
            match = re.fullmatch(r"/v1/jobs/([a-f0-9]{32})(?:/artifacts/([a-z_]+))?", route)
            if not match:
                self._json(404, {"error": "not_found"})
                return
            job, artifact = match.groups()
            directory = data_dir / job
            path = directory / (ARTIFACTS.get(artifact, "") if artifact else "result.json")
            if (artifact and artifact not in ARTIFACTS) or not path.is_file():
                self._json(404, {"error": "not_found"})
                return
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(path.stat().st_size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    self.wfile.write(chunk)

        def do_POST(self):
            # Close POST connections after the response, including early errors
            # where an unread request body may remain on the socket.
            self.close_connection = True
            self.connection.settimeout(60)
            if urlparse(self.path).path != "/v1/analyze-video":
                self._json(404, {"error": "not_found"})
                return
            if not self._authorized():
                return
            if self.headers.get("Transfer-Encoding"):
                self._json(400, {"error": "content_length_required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0:
                self._json(400, {"error": "empty_or_invalid_content_length"})
                return
            if length > max_upload_mb * 1024 * 1024:
                self._json(413, {"error": "video_too_large"})
                return
            suffix = Path(self.headers.get("X-Filename", "video.mp4")).suffix.lower()
            if suffix not in {".mp4", ".avi", ".mov", ".mkv"}:
                self._json(415, {"error": "unsupported_video_extension"})
                return
            if not inference_slot.acquire(blocking=False):
                self._json(429, {"error": "inference_busy", "message": "Retry after the current video completes"})
                return
            job_id = uuid.uuid4().hex
            job_dir = data_dir / job_id
            try:
                job_dir.mkdir()
                input_path = job_dir / ("input" + suffix)
                with input_path.open("wb") as stream:
                    remaining = length
                    while remaining:
                        chunk = self.rfile.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError("Incomplete video upload")
                        stream.write(chunk)
                        remaining -= len(chunk)
                result = runner(input_path, job_dir, weights=Path(weights), device=device, timeout=timeout)
                result["job_id"] = job_id
                result["artifacts"] = {
                    name: f"/v1/jobs/{job_id}/artifacts/{name}" for name in ARTIFACTS
                }
                (job_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                self._json(200, result)
            except subprocess.TimeoutExpired:
                self._json(504, {"error": "inference_timeout", "job_id": job_id})
            except ValueError as exc:
                self._json(400, {"error": "invalid_video", "message": str(exc), "job_id": job_id})
            except TimeoutError:
                self._json(408, {"error": "upload_timeout", "job_id": job_id})
            except Exception:
                self._json(500, {"error": "inference_failed", "job_id": job_id})
            finally:
                inference_slot.release()

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--data-dir", type=Path, default=Path("runs/api"))
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-upload-mb", type=int, default=256)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    if args.max_upload_mb <= 0 or args.timeout <= 0:
        parser.error("upload limit and timeout must be positive")
    verify_models()
    if not args.weights.is_file():
        parser.error("Model file not found")
    server = create_server(args.host, args.port, args.data_dir, weights=args.weights, device=args.device,
                           max_upload_mb=args.max_upload_mb, timeout=args.timeout,
                           api_key=os.environ.get("SORTING_API_KEY"))
    print(f"Sorting video API: http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
