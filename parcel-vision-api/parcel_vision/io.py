from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np

from .pipeline import ParcelDetection


def load_point_cloud(path: str | Path) -> np.ndarray:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".npy":
        return np.load(path)
    if suffix == ".npz":
        archive = np.load(path)
        key = "points" if "points" in archive else archive.files[0]
        return archive[key]
    if suffix in {".xyz", ".txt", ".csv"}:
        delimiter = "," if suffix == ".csv" else None
        return np.loadtxt(path, delimiter=delimiter, comments="#")[:, :3]
    if suffix == ".ply":
        return _load_ascii_ply(path)
    if suffix == ".pcd":
        return _load_pcd(path)
    if suffix == ".mat":
        return _load_mat_point_cloud(path)
    raise ValueError(f"Unsupported point-cloud format: {suffix}")


def load_transform(path: str | Path) -> np.ndarray:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    matrix = np.asarray(data.get("camera_to_robot", data), dtype=float)
    if matrix.shape != (4, 4):
        raise ValueError("Transform JSON must contain a 4x4 camera_to_robot matrix")
    return matrix


def build_protocol_response(
    detections: list[ParcelDetection],
    transaction_id: str,
    send_time: int,
    device: str = "arm1",
    include_extensions: bool = True,
) -> dict:
    return {
        "svc_cont": {
            "message": {
                "status": "success",
                "data": [
                    item.protocol_item(device, include_extensions=include_extensions)
                    for item in detections
                ],
            }
        },
        "tcp_cont": {
            "transaction_id": transaction_id,
            "send_time": send_time,
            "service_type": "package_location",
        },
    }


def _load_ascii_ply(path: Path) -> np.ndarray:
    with path.open("r", encoding="ascii") as handle:
        first = handle.readline().strip()
        if first != "ply":
            raise ValueError("Not a PLY file")
        vertex_count = None
        properties: list[str] = []
        in_vertex = False
        while True:
            line = handle.readline()
            if not line:
                raise ValueError("Incomplete PLY header")
            fields = line.strip().split()
            if fields[:2] == ["format", "ascii"]:
                pass
            elif fields[:2] == ["format", "binary_little_endian"]:
                raise ValueError("Binary PLY is not supported; export ASCII PLY or NPY")
            elif fields[:2] == ["element", "vertex"]:
                vertex_count = int(fields[2])
                in_vertex = True
            elif fields and fields[0] == "element" and fields[1] != "vertex":
                in_vertex = False
            elif fields and fields[0] == "property" and in_vertex:
                properties.append(fields[-1])
            elif fields and fields[0] == "end_header":
                break
        if vertex_count is None:
            raise ValueError("PLY has no vertex element")
        xyz_indices = [properties.index(axis) for axis in ("x", "y", "z")]
        rows = []
        for _ in range(vertex_count):
            values = handle.readline().split()
            rows.append([float(values[index]) for index in xyz_indices])
    return np.asarray(rows, dtype=float)


def _load_mat_point_cloud(path: Path) -> np.ndarray:
    from scipy.io import loadmat

    data = {key: value for key, value in loadmat(path).items() if not key.startswith("__")}
    lower_keys = {key.lower(): key for key in data}
    if all(axis in lower_keys for axis in ("x", "y", "z")):
        xyz = [np.asarray(data[lower_keys[axis]], dtype=float).ravel() for axis in ("x", "y", "z")]
        return np.column_stack(xyz)

    numeric = [np.asarray(value) for value in data.values() if np.asarray(value).dtype.kind in "fiu"]
    for array in numeric:
        squeezed = np.squeeze(array)
        if squeezed.ndim >= 2 and squeezed.shape[-1] == 3:
            return squeezed.reshape(-1, 3).astype(float)
        if squeezed.ndim == 2 and squeezed.shape[0] == 3:
            return squeezed.T.astype(float)
    raise ValueError(f"Could not find XYZ arrays in MATLAB file; variables: {sorted(data)}")


def _load_pcd(path: Path) -> np.ndarray:
    with path.open("rb") as handle:
        header: dict[str, list[str]] = {}
        while True:
            line = handle.readline()
            if not line:
                raise ValueError("Incomplete PCD header")
            decoded = line.decode("ascii", errors="strict").strip()
            if not decoded or decoded.startswith("#"):
                continue
            fields = decoded.split()
            header[fields[0].upper()] = fields[1:]
            if fields[0].upper() == "DATA":
                break
        payload = handle.read()

    names = header.get("FIELDS", header.get("COLUMNS", []))
    sizes = [int(value) for value in header.get("SIZE", [])]
    types = header.get("TYPE", [])
    counts = [int(value) for value in header.get("COUNT", ["1"] * len(names))]
    point_count = int(header.get("POINTS", [header.get("WIDTH", ["0"])[0]])[0])
    if not all(axis in names for axis in ("x", "y", "z")):
        raise ValueError("PCD file does not contain x, y and z fields")
    if not (len(names) == len(sizes) == len(types) == len(counts)):
        raise ValueError("Invalid PCD field metadata")

    mode = header["DATA"][0].lower()
    if mode == "ascii":
        rows = np.loadtxt(payload.decode("ascii").splitlines())
        return rows[:, [names.index(axis) for axis in ("x", "y", "z")]].astype(float)

    dtypes = [_pcd_dtype(kind, size) for kind, size in zip(types, sizes)]
    if mode == "binary":
        structured_dtype = np.dtype(
            [(name, dtype, count) if count > 1 else (name, dtype) for name, dtype, count in zip(names, dtypes, counts)]
        )
        cloud = np.frombuffer(payload, dtype=structured_dtype, count=point_count)
        return np.column_stack([cloud[axis] for axis in ("x", "y", "z")]).astype(float)

    if mode != "binary_compressed":
        raise ValueError(f"Unsupported PCD DATA mode: {mode}")
    if len(payload) < 8:
        raise ValueError("Incomplete compressed PCD payload")
    compressed_size, uncompressed_size = struct.unpack("<II", payload[:8])
    raw = _lzf_decompress(payload[8 : 8 + compressed_size], uncompressed_size)
    columns: dict[str, np.ndarray] = {}
    offset = 0
    for name, dtype, count in zip(names, dtypes, counts):
        byte_count = point_count * np.dtype(dtype).itemsize * count
        values = np.frombuffer(raw, dtype=dtype, count=point_count * count, offset=offset)
        columns[name] = values.reshape(point_count, count) if count > 1 else values
        offset += byte_count
    return np.column_stack([columns[axis] for axis in ("x", "y", "z")]).astype(float)


def _pcd_dtype(kind: str, size: int) -> np.dtype:
    mapping = {
        ("F", 4): "<f4",
        ("F", 8): "<f8",
        ("I", 1): "<i1",
        ("I", 2): "<i2",
        ("I", 4): "<i4",
        ("U", 1): "<u1",
        ("U", 2): "<u2",
        ("U", 4): "<u4",
    }
    try:
        return np.dtype(mapping[(kind.upper(), size)])
    except KeyError as exc:
        raise ValueError(f"Unsupported PCD type/size: {kind}{size}") from exc


def _lzf_decompress(data: bytes, expected_size: int) -> bytes:
    output = bytearray()
    index = 0
    while index < len(data):
        control = data[index]
        index += 1
        if control < 32:
            length = control + 1
            output.extend(data[index : index + length])
            index += length
            continue
        length = control >> 5
        reference_offset = (control & 0x1F) << 8
        if length == 7:
            if index >= len(data):
                raise ValueError("Invalid LZF extended length")
            length += data[index]
            index += 1
        if index >= len(data):
            raise ValueError("Invalid LZF back reference")
        reference_offset += data[index]
        index += 1
        length += 2
        reference = len(output) - reference_offset - 1
        if reference < 0:
            raise ValueError("Invalid LZF reference offset")
        for _ in range(length):
            output.append(output[reference])
            reference += 1
    if len(output) != expected_size:
        raise ValueError(f"LZF size mismatch: expected {expected_size}, got {len(output)}")
    return bytes(output)
