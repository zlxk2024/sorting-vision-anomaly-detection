from __future__ import annotations

import argparse
import json
import time
import uuid

import numpy as np

from .demo import make_synthetic_scene
from .io import build_protocol_response, load_point_cloud, load_transform
from .pipeline import ParcelVisionConfig, ParcelVisionPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Locate conveyor parcels in an XYZ point cloud")
    parser.add_argument("point_cloud", nargs="?", help="NPY, NPZ, XYZ, CSV or ASCII PLY file")
    parser.add_argument("--demo", action="store_true", help="run with a generated three-parcel scene")
    parser.add_argument("--transform", help="JSON file containing camera_to_robot 4x4 matrix")
    parser.add_argument("--device", default="arm1")
    parser.add_argument("--grid-size", type=float, default=5.0)
    parser.add_argument("--min-height", type=float, default=10.0)
    parser.add_argument("--min-area", type=float, default=2500.0)
    parser.add_argument(
        "--segmentation-method", choices=("connected", "height_edges"), default="connected"
    )
    parser.add_argument("--height-edge-threshold", type=float, default=12.0)
    parser.add_argument("--min-detection-score", type=float, default=0.0)
    args = parser.parse_args()

    if args.demo:
        points, _ = make_synthetic_scene()
    elif args.point_cloud:
        points = load_point_cloud(args.point_cloud)
    else:
        parser.error("provide a point_cloud file or use --demo")

    transform = load_transform(args.transform) if args.transform else None
    config = ParcelVisionConfig(
        grid_size=args.grid_size,
        min_height=args.min_height,
        min_area=args.min_area,
        segmentation_method=args.segmentation_method,
        height_edge_threshold=args.height_edge_threshold,
        min_detection_score=args.min_detection_score,
    )
    detections = ParcelVisionPipeline(config).process(points, transform)
    response = build_protocol_response(
        detections,
        transaction_id=uuid.uuid4().hex,
        send_time=int(time.time() * 1000),
        device=args.device,
    )
    print(json.dumps(response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
