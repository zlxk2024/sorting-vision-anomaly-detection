# Horus RV1126B AI Camera YOLO Deployment Research

Date: 2026-08-24

## 1. Conclusion

The trained sorting YOLO model can be deployed on the Horus RV1126B AI camera for edge inference, but it cannot be deployed as the original PyTorch `.pt` model.

Recommended deployment path:

```text
YOLO .pt
  -> export ONNX
  -> convert to RKNN INT8 for rv1126b
  -> run with RKNN Runtime on camera
  -> C/C++ postprocess
  -> lightweight tracking and anomaly rules
  -> OSD/WebSocket/GPIO/RS485/server event output
```

This camera is suitable for a PoC with one camera running a lightweight model such as YOLO11n. It is not suitable for model training, multimodal large-model inference, or heavy multi-camera centralized analysis.

## 2. Current Model

Local trained model:

```text
./models/sorting_yolo11n_v2_mixed_best.pt
```

Model classes:

```text
0 parcel
1 drawer_open
2 drawer_closed
3 chute
4 bag
```

Known model size:

```text
YOLO11n
2.59M parameters
about 1.6 GFLOPs at imgsz=320
model file about 5.2 MB
```

Current training dataset:

```text
./datasets/sorting_yolo_v2_mixed
train: 754 images
val: 162 images
test: 165 images
```

This model size is reasonable for RV1126B PoC after INT8 quantization.

## 3. Camera SDK Findings

SDK folder:

```text
./data/videos/horuskit_WT-1126B_WT-2.06.06-B
```

Important SDK files:

```text
sdk/src/example/obj_detection_yolov8_1126b.cpp
sdk/src/example/postprocess_yolov8.cpp
sdk/src/example/yolov8_1126b.h
sdk/3rdparty/lib/rv1126b/librknnrt.so
sdk/lib/libhrssdk.so
sdk/CMakeLists.txt
build.sh
```

Key facts:

- The SDK already contains an RV1126B YOLO object detection example.
- The example uses `HRS_VideoGetFrame` to fetch YUV420 frames from the camera pipeline.
- The example calls RKNN Runtime APIs: `rknn_init`, `rknn_inputs_set`, `rknn_run`, `rknn_outputs_get`.
- The SDK includes `librknnrt.so`, about 7.4 MB.
- The SDK includes Horus media/control library `libhrssdk.so`, about 5.4 MB.
- The app is cross-compiled into `hrsipc`.
- The camera can be accessed by SSH/SCP and can run files from `/userdata` or `/app`.

Important implementation caveat:

The SDK README says `arm-linux-gnueabihf`, but `build.sh` and `sdk/CMakeLists.txt` use:

```text
aarch64-rockchip1240-linux-gnu
```

For this Horus RV1126B kit, treat it as AArch64 unless the vendor confirms otherwise.

## 4. Official RKNN Compatibility

Rockchip RKNN Toolkit2 v2.3.2 supports RV1126B.

Rockchip RKNN Model Zoo supports YOLO11 on RV1126B and supports FP16/INT8 conversion.

Therefore the model deployment path is technically valid:

```text
YOLO11n ONNX -> RKNN INT8 target_platform=rv1126b
```

## 5. Model Conversion Plan

### Step 1: Export YOLO .pt to ONNX

Run this on a PC/server, not on the camera:

```bash
cd .
python3 - <<'PY'
from ultralytics import YOLO

model = YOLO("models/sorting_yolo11n_v2_mixed_best.pt")
model.export(
    format="onnx",
    imgsz=320,
    opset=12,
    simplify=True,
    dynamic=False,
)
PY
```

Expected output:

```text
models/sorting_yolo11n_v2_mixed_best.onnx
```

Recommended to also test 640 if 320 misses small parcels:

```text
320x320: faster, lower memory, better for camera PoC
640x640: better small-object recall, may be too slow on RV1126B
```

### Step 2: Prepare RKNN Toolkit2

Use Linux x86_64 environment:

```bash
conda create -n toolkit2 python=3.8
conda activate toolkit2
git clone https://github.com/airockchip/rknn-toolkit2.git --depth 1
git clone https://github.com/airockchip/rknn_model_zoo.git --depth 1
```

Install RKNN Toolkit2 v2.3.2 according to the Horus NPU2 document:

```bash
pip install -r rknn-toolkit2/rknn-toolkit2/packages/x86_64/requirements_cp38-2.3.2.txt
pip install rknn-toolkit2/rknn-toolkit2/packages/x86_64/rknn_toolkit2-2.3.2-*.whl
```

### Step 3: Convert ONNX to RKNN INT8

Use the RKNN Model Zoo `examples/yolo11` converter as the first choice.

Target:

```text
target_platform = rv1126b
quantization = i8 / INT8
```

Typical command shape:

```bash
cd rknn_model_zoo/examples/yolo11/python
python convert.py /path/to/sorting_yolo11n_v2_mixed_best.onnx rv1126b i8 /path/to/sorting_yolo11n_v2_mixed_best.rknn
```

If the official `yolo11` converter script format is different in the downloaded version, follow its README exactly.

### Step 4: Prepare Quantization Dataset

INT8 conversion needs representative images. Use 100-300 frames from the actual sorting scenes:

```text
normal drawer closed
drawer open with parcel
parcel sliding/downfall
different parcel types: carton, black bag, white bag
different lighting/exposure
old scene + new camera angle
```

Do not use only abnormal frames. The quantization dataset should represent normal image distribution.

Recommended local source:

```text
./datasets/sorting_yolo_v2_mixed/images/train
```

## 6. Camera-side Application Plan

The Horus example is YOLOv8, while our model is YOLO11. There are two viable paths.

### Option A: Use Rockchip YOLO11 C++ Demo, Then Integrate Horus Frame Input

This is cleaner for YOLO11 output format.

Process:

```text
1. Build rknn_model_zoo/examples/yolo11/cpp for rv1126b/aarch64.
2. Verify it can run a still image on the camera.
3. Replace image file input with Horus `HRS_VideoGetFrame`.
4. Add OSD/event output with Horus SDK.
```

Pros:

- YOLO11 postprocess is already aligned with official Rockchip example.
- Lower risk of output tensor mismatch.

Cons:

- Need to integrate Horus camera frame APIs.

### Option B: Modify Horus YOLOv8 Example

This reuses:

```text
sdk/src/example/obj_detection_yolov8_1126b.cpp
```

Required changes:

```text
1. Replace model path with sorting YOLO RKNN model.
2. Replace class labels with parcel/drawer_open/drawer_closed/chute/bag.
3. Replace YOLOv8 postprocess with YOLO11 postprocess if output tensors differ.
4. Add tracking and event state machine.
5. Add alarm output.
```

Pros:

- Already connected to Horus video frame, OSD, WebSocket.

Cons:

- YOLOv8 and YOLO11 output may differ.
- Existing code loads model paths inconsistently:
  - `/userdata/model/yolov8.rknn`
  - `/app/model/yolov8.rknn`
- Existing code does CPU NV12-to-RGB conversion and should be optimized.

Recommended choice:

Use Option A for model correctness, then merge Horus frame/OSD/event parts from Option B.

## 7. Frame Input and Preprocessing

The Horus example currently does:

```text
HRS_VideoGetFrame
  -> YUV420/NV12 frame
  -> nv12_to_rgb24 CPU conversion
  -> rknn_inputs_set
```

For PoC this can work.

For production, optimize:

```text
Use RGA for resize/color conversion
Avoid CPU pixel loop
Avoid unnecessary memory copy
Use fixed input size 320 or ROI crop
```

The current example assumes the frame size equals model input size. For a real camera stream, we should support:

```text
camera frame 1920x1080 / 1280x720
  -> crop ROI containing sorting mechanism
  -> resize to model size
  -> run RKNN
```

For this project, ROI is strongly recommended because full-frame 320 downscale makes parcels too small.

## 8. Event Logic on Camera

The YOLO model only outputs object boxes:

```text
parcel
drawer_open
drawer_closed
chute
bag
```

The camera-side C++ application still needs a rule engine:

```text
detections over time
  -> assign parcel track IDs
  -> associate parcel with drawer/chute/bag
  -> state machine
  -> output anomaly event
```

Minimum camera-side events:

```text
open_no_drop:
  drawer_open appears, parcel stays in drawer longer than threshold

stall:
  parcel stays on chute area longer than threshold

multi_parcel_candidate:
  more than one parcel appears in same drawer region before/opening

wrong_chute/floating:
  only reliable when PLC/WCS target chute is available
```

Without PLC/WCS:

```text
wrong_chute can only be "visual abnormal trajectory candidate"
not confirmed wrong chute
```

## 9. PLC/WCS Association

If PLC provides:

```text
order_id
drawer_id
drawer_open_time
target_chute_id
expected_arrival_time
```

Then the camera app can output:

```json
{
  "camera_id": "CAM-01",
  "visual_track_id": 102,
  "visual_drawer_id": "VD03",
  "plc_drawer_id": "D03",
  "order_id": "SF123456",
  "drawer_open_time": "2026-08-24 14:30:21.280",
  "leave_drawer_time": "2026-08-24 14:30:21.720",
  "target_chute_id": "C08",
  "actual_chute_id": "VC08",
  "event_type": "normal",
  "confidence": 0.92
}
```

Association method:

```text
same camera coverage
+ drawer/chute spatial mapping
+ time window matching
+ nearest visual event
```

## 10. Build and Deploy Plan

### Build app

On Linux build machine with AArch64 toolchain:

```bash
cd /path/to/horuskit_WT-1126B_WT-2.06.06-B
export PATH=/path/to/aarch64-rockchip1240-linux-gnu/bin:$PATH
./build.sh app
```

Expected output:

```text
build_app/hrsipc
```

For production performance, change CMake debug flags:

```text
current: -O0 -g
recommended: -O2 or -O3 for release
```

### Copy to camera

Camera default:

```text
IP: 192.168.1.8
user: root
password: 123456
```

Copy model and app:

```bash
scp build_app/hrsipc root@CAMERA_IP:/userdata/hrsipc_sorting
scp sorting_yolo11n_v2_mixed_best.rknn root@CAMERA_IP:/userdata/model/sorting_yolo.rknn
scp sdk/lib/libhrssdk.so root@CAMERA_IP:/userdata/lib/
```

Run test:

```bash
ssh root@CAMERA_IP
export LD_LIBRARY_PATH=/userdata/lib:/app/lib:$LD_LIBRARY_PATH
chmod +x /userdata/hrsipc_sorting
/userdata/hrsipc_sorting
```

Alternative production deployment:

```text
put app into /app
put libraries into /app/lib
put model into /app/model
package firmware
upgrade through web UI or RKDevTool
```

## 11. Verification Checklist

Before promising production deployment, test these on a real camera:

```text
1. RKNN model can load successfully.
2. Input/output tensor shapes match postprocess.
3. Single image inference result is close to PyTorch result.
4. Live video inference runs continuously.
5. End-to-end FPS reaches target.
6. NPU/CPU/RAM usage is acceptable.
7. 320 vs 640 accuracy tradeoff is measured.
8. ROI crop works under real installation angle.
9. Event rules output correct timestamps.
10. Alarm output path is verified: GPIO/RS485/WebSocket/TCP.
11. 24-hour stability test passes.
```

Recommended minimum acceptance thresholds for PoC:

```text
effective FPS: >= 10
end-to-end alarm latency: <= 500 ms to 1000 ms
model load success rate: 100%
24h crash count: 0
false alarm: acceptable only after customer-defined threshold
missed critical anomaly: must be manually reviewed
```

## 12. Risks

Main risks:

```text
1. 1 GB RAM may limit 640 inference and complex tracking.
2. Existing Horus demo uses CPU color conversion, which may reduce FPS.
3. YOLO11 postprocess must match RKNN output tensors exactly.
4. Current model was trained mostly on limited scenes; new camera angle may need more data.
5. Wrong chute cannot be fully confirmed without PLC/WCS expected chute.
6. GPIO/RS485 physical wiring must be confirmed with vendor.
```

## 13. Recommended Engineering Sequence

Phase 1: Offline conversion

```text
.pt -> ONNX -> RKNN INT8
verify still-image inference
compare PyTorch vs RKNN output
```

Phase 2: Camera still-image demo

```text
copy RKNN Model Zoo YOLO11 demo to camera
run image inference on camera
measure model load and inference latency
```

Phase 3: Live camera demo

```text
connect Horus HRS_VideoGetFrame to YOLO11 RKNN inference
add ROI crop
draw OSD boxes
output JSON events
```

Phase 4: Sorting anomaly demo

```text
add lightweight tracking
add open_no_drop / stall / multi-parcel candidate rules
integrate PLC/WCS when available
trigger alarm output
```

Phase 5: Production hardening

```text
release build -O2/-O3
RGA preprocessing
auto-start service
watchdog
model version management
24h/72h stability test
```

## 14. Questions for Camera Vendor

Ask the vendor these questions before final quotation:

```text
1. Is this firmware definitely AArch64 for RV1126B?
2. Is the RKNPU2 driver version >= 0.9.2?
3. Can we replace or extend /app/hrsipc?
4. Can custom apps auto-start after reboot?
5. Are GPIO pins exposed for alarm light?
6. Is RS485 available and documented?
7. Can the camera output raw frame ROI or only full frame?
8. Can they provide an optimized RGA resize/color-conversion sample?
9. How much free RAM is available during normal video encoding?
10. Can they provide a sample device for RKNN latency benchmark?
```

## 15. Final Recommendation

Use the Horus RV1126B camera for edge PoC, but keep the first version conservative:

```text
YOLO11n INT8
ROI crop
320 input first
single-camera single-model inference
simple C++ tracking/event rules
alarm through WebSocket/TCP first, GPIO after hardware confirmation
```

If 320 input misses small parcels, test:

```text
640 full frame
or two 320 ROI tiles
or move inference to an external edge IPC/GPU box
```

Do not promise one camera can handle all anomaly types perfectly by itself. The correct promise is:

```text
The camera can run lightweight YOLO inference locally.
Production-grade anomaly recognition still needs model conversion, camera-side C++ integration, ROI optimization, real-device benchmark, and PLC/WCS association.
```
