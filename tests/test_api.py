import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

from parcel_vision.api import (
    PROTOCOL_LOCATION_FIELDS,
    ParcelLocationService,
    create_server,
)
from parcel_vision.api_client import locate_file
from parcel_vision.demo import make_synthetic_scene
from parcel_vision.pipeline import ParcelVisionConfig


class ParcelVisionAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.points, _ = make_synthetic_scene()
        service = ParcelLocationService(
            ParcelVisionConfig(grid_size=5.0, plane_ransac_iterations=100)
        )
        cls.server = create_server("127.0.0.1", 0, service, max_upload_bytes=32 * 1024 * 1024)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_health_endpoint(self):
        with urlopen(f"{self.base_url}/health", timeout=5) as response:
            payload = json.loads(response.read())
        self.assertEqual("ok", payload["status"])

    def test_npy_upload_returns_document_protocol(self):
        buffer = io.BytesIO()
        np.save(buffer, self.points)
        request = Request(
            f"{self.base_url}/v1/package-location?device=arm2&transaction_id=tx-api-1",
            data=buffer.getvalue(),
            headers={
                "Content-Type": "application/octet-stream",
                "X-Filename": "frame.npy",
            },
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read())

        self.assertEqual("success", payload["svc_cont"]["message"]["status"])
        self.assertEqual("package_location", payload["tcp_cont"]["service_type"])
        self.assertEqual("tx-api-1", payload["tcp_cont"]["transaction_id"])
        data = payload["svc_cont"]["message"]["data"]
        self.assertEqual(3, len(data))
        self.assertTrue(all(item["device"] == "arm2" for item in data))
        self.assertEqual(PROTOCOL_LOCATION_FIELDS, set(data[0]["location"]))

    def test_json_points_can_return_extensions_and_transform(self):
        payload = {
            "points": self.points.tolist(),
            "device": "arm1",
            "include_extensions": True,
            "camera_to_robot": [
                [1, 0, 0, 100],
                [0, 1, 0, -50],
                [0, 0, 1, 20],
                [0, 0, 0, 1],
            ],
        }
        request = Request(
            f"{self.base_url}/v1/package-location",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read())

        location = result["svc_cont"]["message"]["data"][0]["location"]
        self.assertIn("object_id", location)
        self.assertIn("score", location)
        self.assertEqual("robot", result["svc_cont"]["message"]["meta"]["coordinate_system"])

    def test_multipart_client_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.npy"
            np.save(path, self.points)
            result = locate_file(
                f"{self.base_url}/v1/package-location",
                path,
                transaction_id="tx-multipart-1",
                include_extensions=True,
            )

        self.assertEqual("tx-multipart-1", result["tcp_cont"]["transaction_id"])
        self.assertEqual(3, result["svc_cont"]["message"]["meta"]["parcel_count"])

    def test_unsupported_upload_returns_protocol_error(self):
        request = Request(
            f"{self.base_url}/v1/package-location",
            data=b"not a cloud",
            headers={"X-Filename": "frame.exe"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=5)
        payload = json.loads(raised.exception.read())
        self.assertEqual(415, raised.exception.code)
        self.assertEqual("failed", payload["svc_cont"]["message"]["status"])
        self.assertEqual("unsupported_format", payload["svc_cont"]["message"]["error_code"])


if __name__ == "__main__":
    unittest.main()
