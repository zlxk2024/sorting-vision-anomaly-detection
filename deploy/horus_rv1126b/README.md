# Horus RV1126B Sorting YOLO Deployment

This folder contains the first deployable engineering package for running the trained sorting YOLO model on a Horus RV1126B AI camera.

It covers:

- exporting the trained YOLO `.pt` model to ONNX;
- preparing representative quantization images;
- converting ONNX to RKNN INT8 for `rv1126b`;
- camera-side C++ event-state logic for sorting anomaly detection;
- integration notes for Horus SDK `HRS_VideoGetFrame` and RKNN Runtime.

## Current Model

```text
./models/sorting_yolo11n_v2_mixed_best.pt
```

Classes:

```text
0 parcel
1 drawer_open
2 drawer_closed
3 chute
4 bag
```

## Deployment Flow

```text
sorting_yolo11n_v2_mixed_best.pt
  -> export_sorting_yolo_onnx.py
  -> sorting_yolo11n_v2_mixed_best.onnx
  -> prepare_quant_images.py
  -> quant_images.txt
  -> convert_onnx_to_rknn.py
  -> sorting_yolo11n_v2_mixed_best.rknn
  -> copy to camera
  -> Horus C++ app loads RKNN and runs inference
```

## 1. Export ONNX

Run on PC/server:

```bash
cd .
python3 deploy/horus_rv1126b/export_sorting_yolo_onnx.py \
  --weights models/sorting_yolo11n_v2_mixed_best.pt \
  --imgsz 320
```

Expected output:

```text
models/sorting_yolo11n_v2_mixed_best.onnx
```

## 2. Prepare Quantization Images

Run on PC/server:

```bash
python3 deploy/horus_rv1126b/prepare_quant_images.py \
  --image-dir datasets/sorting_yolo_v2_mixed/images/train \
  --output deploy/horus_rv1126b/quant_images.txt \
  --limit 300
```

## 3. Convert ONNX to RKNN

Run in Linux x86_64 environment with RKNN Toolkit2 installed:

```bash
python3 deploy/horus_rv1126b/convert_onnx_to_rknn.py \
  --onnx models/sorting_yolo11n_v2_mixed_best.onnx \
  --output models/sorting_yolo11n_v2_mixed_best.rknn \
  --dataset deploy/horus_rv1126b/quant_images.txt \
  --target rv1126b
```

This script requires:

```text
rknn-toolkit2 == 2.3.2
```

## 4. Camera-side Integration

Use the Horus SDK example as the integration base:

```text
./data/videos/horuskit_WT-1126B_WT-2.06.06-B/sdk/src/example/obj_detection_yolov8_1126b.cpp
```

Replace or extend it with:

```text
sorting_event_state_machine.hpp
```

The final camera loop should be:

```text
HRS_VideoGetFrame
  -> crop/resize ROI
  -> RKNN Runtime inference
  -> YOLO postprocess
  -> SortingEventStateMachine.update()
  -> OSD/WebSocket/TCP/GPIO/RS485 alarm output
```

The local state-machine demo can be compiled on Mac/Linux:

```bash
cd ./deploy/horus_rv1126b
cmake -S . -B build
cmake --build build
./build/sorting_horus_integration_demo
```

This only validates the event-state logic. It does not access the Horus camera.

## 5. Recommended PoC Settings

```text
model: YOLO11n INT8 RKNN
input size: 320 first
camera count per device: 1
effective FPS target: >= 10
alarm latency target: <= 500-1000 ms
ROI: only sorting mechanism and chute/bag area
```

If 320 misses small parcels, test:

```text
640 full frame
or two 320 ROI tiles
or external IPC/GPU edge server
```

## 6. What Still Needs Real Device Validation

- RKNN model loading on RV1126B;
- output tensor shape and YOLO11 postprocess correctness;
- live FPS;
- CPU/NPU/RAM usage;
- RGA preprocessing speed;
- OSD/event output;
- GPIO/RS485 alarm wiring;
- 24-hour stability.

For real camera deployment steps, see:

```text
deploy/horus_rv1126b/REAL_CAMERA_RUNBOOK.md
```
