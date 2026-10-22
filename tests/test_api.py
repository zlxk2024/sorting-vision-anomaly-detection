import json
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from sorting_vision.api import create_server
from sorting_vision.inference import ARTIFACTS


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.calls = []
        self.block = None
        self.started = threading.Event()
        self.runner_error = None
        def runner(video, output, **kwargs):
            self.calls.append((video, output))
            if self.runner_error:
                raise self.runner_error
            if self.block is not None:
                self.started.set()
                self.block.wait(timeout=5)
            for name in ARTIFACTS.values():
                (output / name).write_bytes(b"[]" if name.endswith(".json") else b"artifact")
            return {"status": "completed", "frame_count": 2, "event_count": 0, "events": []}
        self.server = create_server("127.0.0.1", 0, Path(self.temp.name), api_key="test-key", runner=runner)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.temp.cleanup()

    def request(self, route, body=None, **headers):
        return urllib.request.urlopen(urllib.request.Request(
            self.url + route, data=body, headers={"Authorization": "Bearer test-key", **headers}), timeout=10)

    def test_health_and_upload_result_artifacts(self):
        with self.request("/health") as response:
            self.assertEqual("ok", json.load(response)["status"])
        with self.request("/v1/analyze-video", b"test-video", **{"X-Filename": "../../clip.mp4"}) as response:
            result = json.load(response)
        self.assertEqual(1, len(self.calls))
        self.assertEqual("input.mp4", self.calls[0][0].name)
        with self.request(f"/v1/jobs/{result['job_id']}") as response:
            self.assertEqual(result, json.load(response))
        with self.request(result["artifacts"]["video"]) as response:
            self.assertEqual(b"artifact", response.read())
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request(f"/v1/jobs/{result['job_id']}/artifacts/inference_log")
        self.assertEqual(404, error.exception.code)

    def test_authentication_is_required_for_jobs(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(urllib.request.Request(self.url + "/v1/analyze-video", data=b"x"))
        self.assertEqual(401, error.exception.code)
        self.assertEqual([], self.calls)

    def test_invalid_video_extension_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/v1/analyze-video", b"data", **{"X-Filename": "payload.py"})
        self.assertEqual(415, error.exception.code)
        self.assertEqual([], self.calls)

    def test_traversal_and_unknown_job_are_rejected(self):
        for route in ["/v1/jobs/../models", "/v1/jobs/" + "0" * 32]:
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request(route)
            self.assertEqual(404, error.exception.code)

    def test_upload_limit_is_enforced_before_inference(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/v1/analyze-video", b"x", **{"Content-Length": str(257 * 1024 * 1024)})
        self.assertEqual(413, error.exception.code)
        self.assertEqual([], self.calls)

    def test_timeout_releases_inference_slot(self):
        self.runner_error = subprocess.TimeoutExpired("inference", 1)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/v1/analyze-video", b"video")
        self.assertEqual(504, error.exception.code)
        self.runner_error = None
        with self.request("/v1/analyze-video", b"video") as response:
            self.assertEqual("completed", json.load(response)["status"])

    def test_concurrent_inference_is_rejected(self):
        self.block = threading.Event()
        result = []
        def first_request():
            with self.request("/v1/analyze-video", b"video") as response:
                result.append(response.status)
        thread = threading.Thread(target=first_request)
        thread.start()
        try:
            self.assertTrue(self.started.wait(timeout=5))
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request("/v1/analyze-video", b"second-video")
            self.assertEqual(429, error.exception.code)
        finally:
            self.block.set()
            thread.join(timeout=5)
        self.assertEqual([200], result)


if __name__ == "__main__":
    unittest.main()
