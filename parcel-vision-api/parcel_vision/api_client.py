from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen


def encode_multipart(
    file_path: str | Path,
    fields: Optional[dict[str, str]] = None,
) -> tuple[bytes, str]:
    path = Path(file_path)
    boundary = f"parcel-vision-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in (fields or {}).items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("ascii"),
            (
                f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            ).encode("utf-8"),
            b"Content-Type: application/octet-stream\r\n\r\n",
            path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def locate_file(
    endpoint: str,
    file_path: str | Path,
    device: str = "arm1",
    transaction_id: str = "",
    transform: Optional[list[list[float]]] = None,
    include_extensions: bool = False,
    timeout: float = 120.0,
) -> dict:
    fields = {
        "device": device,
        "transaction_id": transaction_id or uuid.uuid4().hex,
        "include_extensions": "true" if include_extensions else "false",
    }
    if transform is not None:
        fields["camera_to_robot"] = json.dumps(transform)
    body, content_type = encode_multipart(file_path, fields)
    request = Request(
        endpoint,
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Call the Parcel Vision HTTP API")
    parser.add_argument("point_cloud")
    parser.add_argument("--url", default="http://127.0.0.1:8080/v1/package-location")
    parser.add_argument("--device", default="arm1")
    parser.add_argument("--transaction-id", default="")
    parser.add_argument("--transform", help="camera_to_robot 4x4 JSON file")
    parser.add_argument("--include-extensions", action="store_true")
    args = parser.parse_args()

    transform = None
    if args.transform:
        transform_data = json.loads(Path(args.transform).read_text(encoding="utf-8"))
        transform = transform_data.get("camera_to_robot", transform_data)
    result = locate_file(
        args.url,
        args.point_cloud,
        device=args.device,
        transaction_id=args.transaction_id,
        transform=transform,
        include_extensions=args.include_extensions,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
