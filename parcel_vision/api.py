from __future__ import annotations

import argparse
import json
import tempfile
import time
import uuid
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import numpy as np

from .io import build_protocol_response, load_point_cloud, load_transform
from .pipeline import ParcelVisionConfig, ParcelVisionPipeline


SUPPORTED_SUFFIXES = {".npy", ".npz", ".xyz", ".txt", ".csv", ".ply", ".pcd", ".mat"}
PROTOCOL_LOCATION_FIELDS = {
    "x",
    "y",
    "z",
    "angle_z",
    "angle_y",
    "angle_x",
    "object_length",
    "object_width",
    "object_height",
    "object_type",
}


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass
class LocateRequest:
    points: Optional[np.ndarray] = None
    file_bytes: Optional[bytes] = None
    filename: str = ""
    device: str = "arm1"
    transaction_id: str = ""
    camera_to_robot: Optional[np.ndarray] = None
    include_extensions: bool = False


class ParcelLocationService:
    def __init__(
        self,
        config: Optional[ParcelVisionConfig] = None,
        default_transform: Optional[np.ndarray] = None,
        max_points: int = 5_000_000,
    ):
        self.pipeline = ParcelVisionPipeline(config)
        self.default_transform = default_transform
        self.max_points = max_points

    def locate(self, request: LocateRequest) -> dict:
        points = request.points
        if points is None:
            points = self._load_uploaded_file(request.file_bytes, request.filename)
        points = np.asarray(points)
        if points.ndim < 1:
            raise APIError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_point_cloud",
                "点云必须是 N x 3 数组",
            )
        if len(points) > self.max_points:
            raise APIError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "too_many_points",
                f"点云包含 {len(points)} 个点，超过上限 {self.max_points}",
            )

        transform = request.camera_to_robot
        if transform is None:
            transform = self.default_transform
        started = time.perf_counter()
        try:
            detections = self.pipeline.process(points, transform)
        except (ValueError, TypeError) as exc:
            raise APIError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_point_cloud", str(exc)) from exc

        response = build_protocol_response(
            detections,
            transaction_id=request.transaction_id or uuid.uuid4().hex,
            send_time=int(time.time() * 1000),
            device=request.device,
            include_extensions=request.include_extensions,
        )
        if request.include_extensions:
            response["svc_cont"]["message"]["meta"] = {
                "point_count": int(len(points)),
                "parcel_count": len(detections),
                "runtime_ms": round((time.perf_counter() - started) * 1000.0, 2),
                "coordinate_system": "robot" if transform is not None else "camera",
                "distance_unit": "mm",
                "angle_unit": "degree",
            }
        return response

    @staticmethod
    def _load_uploaded_file(content: Optional[bytes], filename: str) -> np.ndarray:
        if content is None:
            raise APIError(HTTPStatus.BAD_REQUEST, "missing_point_cloud", "缺少点云文件或 points 数组")
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
            raise APIError(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "unsupported_format",
                f"不支持 {suffix or '无扩展名'} 格式；支持：{supported}",
            )
        try:
            with tempfile.TemporaryDirectory(prefix="parcel-vision-") as directory:
                path = Path(directory) / f"upload{suffix}"
                path.write_bytes(content)
                return load_point_cloud(path)
        except APIError:
            raise
        except Exception as exc:
            raise APIError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "point_cloud_read_failed",
                f"点云文件读取失败：{exc}",
            ) from exc


def create_server(
    host: str,
    port: int,
    service: ParcelLocationService,
    max_upload_bytes: int = 256 * 1024 * 1024,
) -> ThreadingHTTPServer:
    class Handler(ParcelVisionAPIHandler):
        pass

    Handler.service = service
    Handler.max_upload_bytes = max_upload_bytes
    return ThreadingHTTPServer((host, port), Handler)


class ParcelVisionAPIHandler(BaseHTTPRequestHandler):
    service: ParcelLocationService
    max_upload_bytes = 256 * 1024 * 1024
    server_version = "ParcelVisionAPI/1.0"

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self._send_json(
                HTTPStatus.OK,
                {"status": "ok", "service": "parcel-vision", "version": "1.0"},
            )
            return
        self._send_error(APIError(HTTPStatus.NOT_FOUND, "not_found", "接口不存在"))

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/v1/package-location":
            self._send_error(APIError(HTTPStatus.NOT_FOUND, "not_found", "接口不存在"))
            return
        try:
            request = self._parse_locate_request()
            response = self.service.locate(request)
            self._send_json(HTTPStatus.OK, response)
        except APIError as exc:
            self._send_error(exc)
        except Exception:
            self._send_error(
                APIError(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error", "服务内部错误")
            )

    def _parse_locate_request(self) -> LocateRequest:
        length_text = self.headers.get("Content-Length")
        if length_text is None:
            raise APIError(HTTPStatus.LENGTH_REQUIRED, "length_required", "缺少 Content-Length")
        try:
            length = int(length_text)
        except ValueError as exc:
            raise APIError(HTTPStatus.BAD_REQUEST, "invalid_length", "Content-Length 无效") from exc
        if length <= 0:
            raise APIError(HTTPStatus.BAD_REQUEST, "empty_body", "请求体为空")
        if length > self.max_upload_bytes:
            raise APIError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "upload_too_large",
                f"请求体超过 {self.max_upload_bytes} 字节限制",
            )
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "application/octet-stream")
        query = parse_qs(urlparse(self.path).query)
        values = {key: items[-1] for key, items in query.items() if items}

        if content_type.split(";", 1)[0].strip().lower() == "application/json":
            return self._parse_json_request(body, values)
        if content_type.lower().startswith("multipart/form-data"):
            return self._parse_multipart_request(body, content_type, values)

        filename = self.headers.get("X-Filename", values.get("filename", ""))
        return LocateRequest(
            file_bytes=body,
            filename=filename,
            device=values.get("device", "arm1"),
            transaction_id=values.get("transaction_id", ""),
            include_extensions=_parse_bool(values.get("include_extensions", "false")),
        )

    def _parse_json_request(self, body: bytes, values: dict[str, str]) -> LocateRequest:
        try:
            payload = json.loads(body.decode("utf-8"))
            points = np.asarray(payload["points"], dtype=float)
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise APIError(
                HTTPStatus.BAD_REQUEST,
                "invalid_json",
                "JSON 必须包含数值型 points: [[x,y,z], ...]",
            ) from exc
        return LocateRequest(
            points=points,
            device=str(payload.get("device", values.get("device", "arm1"))),
            transaction_id=str(payload.get("transaction_id", values.get("transaction_id", ""))),
            camera_to_robot=_parse_transform(payload.get("camera_to_robot")),
            include_extensions=_parse_bool(
                payload.get("include_extensions", values.get("include_extensions", False))
            ),
        )

    def _parse_multipart_request(
        self, body: bytes, content_type: str, values: dict[str, str]
    ) -> LocateRequest:
        header = (
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii")
        )
        message = BytesParser(policy=policy.default).parsebytes(header + body)
        if not message.is_multipart():
            raise APIError(HTTPStatus.BAD_REQUEST, "invalid_multipart", "multipart 请求格式无效")

        file_bytes: Optional[bytes] = None
        filename = ""
        fields = dict(values)
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            part_filename = part.get_filename()
            content = part.get_payload(decode=True) or b""
            if name in {"file", "point_cloud"} and part_filename:
                file_bytes = content
                filename = part_filename
            else:
                fields[name] = content.decode(part.get_content_charset() or "utf-8").strip()
        transform_value: Any = fields.get("camera_to_robot")
        if transform_value:
            try:
                transform_value = json.loads(transform_value)
            except json.JSONDecodeError as exc:
                raise APIError(
                    HTTPStatus.BAD_REQUEST,
                    "invalid_transform",
                    "camera_to_robot 必须是 4x4 JSON 数组",
                ) from exc
        return LocateRequest(
            file_bytes=file_bytes,
            filename=filename,
            device=fields.get("device", "arm1"),
            transaction_id=fields.get("transaction_id", ""),
            camera_to_robot=_parse_transform(transform_value),
            include_extensions=_parse_bool(fields.get("include_extensions", "false")),
        )

    def _send_error(self, error: APIError) -> None:
        self._send_json(
            error.status,
            {
                "svc_cont": {
                    "message": {
                        "status": "failed",
                        "error_code": error.code,
                        "error_message": error.message,
                    }
                },
                "tcp_cont": {
                    "transaction_id": uuid.uuid4().hex,
                    "send_time": int(time.time() * 1000),
                    "service_type": "package_location",
                },
            },
        )

    def _send_json(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def _parse_transform(value: Any) -> Optional[np.ndarray]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        raise APIError(
            HTTPStatus.BAD_REQUEST,
            "invalid_transform",
            "camera_to_robot 必须是有限数值组成的 4x4 数组",
        )
    return matrix


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Expose parcel point-cloud localization as HTTP API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--config", help="ParcelVisionConfig JSON; replaces command-line algorithm defaults")
    parser.add_argument("--transform", help="default camera_to_robot calibration JSON")
    parser.add_argument("--max-upload-mb", type=int, default=256)
    parser.add_argument("--max-points", type=int, default=5_000_000)
    parser.add_argument("--grid-size", type=float, default=5.0)
    parser.add_argument("--min-height", type=float, default=10.0)
    parser.add_argument("--min-area", type=float, default=2_500.0)
    parser.add_argument(
        "--segmentation-method", choices=("connected", "height_edges"), default="connected"
    )
    parser.add_argument("--height-edge-threshold", type=float, default=12.0)
    parser.add_argument("--min-detection-score", type=float, default=0.0)
    args = parser.parse_args()

    if args.config:
        try:
            config_data = json.loads(Path(args.config).read_text(encoding="utf-8"))
            config = ParcelVisionConfig(**config_data)
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            parser.error(f"invalid --config: {exc}")
    else:
        config = ParcelVisionConfig(
            grid_size=args.grid_size,
            min_height=args.min_height,
            min_area=args.min_area,
            segmentation_method=args.segmentation_method,
            height_edge_threshold=args.height_edge_threshold,
            min_detection_score=args.min_detection_score,
        )
    transform = load_transform(args.transform) if args.transform else None
    service = ParcelLocationService(config, transform, max_points=args.max_points)
    server = create_server(
        args.host, args.port, service, max_upload_bytes=args.max_upload_mb * 1024 * 1024
    )
    print(f"Parcel Vision API listening on http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
