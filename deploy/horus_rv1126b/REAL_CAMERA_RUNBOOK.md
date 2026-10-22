# Horus RV1126B Real Camera Deployment Runbook

This runbook explains how to deploy and run the sorting YOLO model on a real Horus RV1126B camera.

Use this order:

```text
1. Confirm camera network access
2. Copy files to /userdata for PoC
3. Run still-image RKNN test
4. Run live camera app
5. Verify detection and alarm output
6. Package into /app or firmware after PoC passes
```

## 1. Prepare Files

Required model files on PC:

```text
./models/sorting_yolo11n_v2_mixed_best.onnx
./deploy/horus_rv1126b/quant_images.txt
```

After RKNN conversion, expected model file:

```text
./models/sorting_yolo11n_v2_mixed_best.rknn
```

Required camera app files after cross-compilation:

```text
hrsipc_sorting
libhrssdk.so
librknnrt.so
librga.so
sorting_yolo11n_v2_mixed_best.rknn
sorting_classes.txt
```

For the first PoC, do not replace the original firmware. Put files under `/userdata`.

## 2. Connect to Camera

Default camera information from Horus quick start:

```text
default wired IP: 192.168.1.8
web user: admin
web password: <use device-specific credentials>
ssh user: root
ssh password: <use device-specific credentials>
```

If the camera IP has been changed, use HorusTool to search the device IP.

Check network:

```bash
ping CAMERA_IP
```

Login:

```bash
ssh root@CAMERA_IP
```

If SSH complains about known host:

```bash
ssh-keygen -f "$HOME/.ssh/known_hosts" -R CAMERA_IP
ssh root@CAMERA_IP
```

## 3. Confirm RTSP Stream

Use VLC or ffplay:

```text
rtsp://CAMERA_IP/h264
rtsp://CAMERA_IP/h264?chn=1
rtsp://CAMERA_IP/h265
rtsp://CAMERA_IP/h265?chn=1
```

This step confirms the camera is capturing normally before running AI inference.

## 4. Copy Files to Camera

Create folders:

```bash
ssh root@CAMERA_IP
mkdir -p /userdata/sorting_app
mkdir -p /userdata/sorting_app/model
mkdir -p /userdata/sorting_app/lib
exit
```

Copy files from PC:

```bash
scp /path/to/hrsipc_sorting root@CAMERA_IP:/userdata/sorting_app/
scp ./models/sorting_yolo11n_v2_mixed_best.rknn root@CAMERA_IP:/userdata/sorting_app/model/sorting_yolo.rknn
scp ./deploy/horus_rv1126b/sorting_classes.txt root@CAMERA_IP:/userdata/sorting_app/model/
scp /path/to/libhrssdk.so root@CAMERA_IP:/userdata/sorting_app/lib/
scp /path/to/librknnrt.so root@CAMERA_IP:/userdata/sorting_app/lib/
scp /path/to/librga.so root@CAMERA_IP:/userdata/sorting_app/lib/
```

Possible local SDK source paths:

```text
./data/videos/horuskit_WT-1126B_WT-2.06.06-B/sdk/lib/libhrssdk.so
./data/videos/horuskit_WT-1126B_WT-2.06.06-B/sdk/3rdparty/lib/rv1126b/librknnrt.so
```

The exact `librga.so` location depends on the SDK install output or RKNN Model Zoo install package.

## 5. Run Still-image RKNN Test First

Before live video, verify that the RKNN model can load and infer on the device.

If using RKNN Model Zoo YOLO11 demo, copy the whole install folder to camera:

```text
install/rv1126b_linux_aarch64/rknn_yolo11_demo/
```

Then run:

```bash
ssh root@CAMERA_IP
cd /userdata/rknn_yolo11_demo
export LD_LIBRARY_PATH=./lib:$LD_LIBRARY_PATH
./rknn_yolo11_demo model/sorting_yolo.rknn model/test.jpg
```

Pass criteria:

```text
1. model loads successfully
2. output tensor shape is printed
3. result image or console boxes are generated
4. no rknn_init/rknn_run error
```

If this fails, do not continue to live video. Fix model conversion or runtime/library mismatch first.

## 6. Run Live Camera App

Run the Horus-integrated app:

```bash
ssh root@CAMERA_IP
cd /userdata/sorting_app
export LD_LIBRARY_PATH=/userdata/sorting_app/lib:/app/lib:$LD_LIBRARY_PATH
chmod +x ./hrsipc_sorting
./hrsipc_sorting
```

Expected live pipeline:

```text
HRS_VideoGetFrame
  -> YUV frame
  -> ROI crop / resize / color conversion
  -> rknn_inputs_set
  -> rknn_run
  -> rknn_outputs_get
  -> YOLO11 postprocess
  -> SortingEventStateMachine
  -> JSON event / OSD / alarm
```

## 7. What to Watch in Logs

Normal logs should include:

```text
rknn sdk version
driver version
model input height/width/channel
model input/output tensor count
detection count
event JSON
FPS / inference latency
```

Bad logs:

```text
rknn_init fail
rknn_run error
HRS_VideoGetFrame failed
frame size != model input size
segmentation fault
out of memory
```

## 8. Verify Output

Verify these one by one:

```text
1. RTSP preview still works.
2. OSD boxes are correct.
3. parcel / drawer_open / drawer_closed / chute / bag are detected.
4. open_no_drop can trigger.
5. stall_on_chute can trigger.
6. multi_parcel_candidate can trigger.
7. false alarms are not excessive.
8. event time is correct.
9. alarm output reaches server or alarm light.
```

## 9. Alarm Output Options

Recommended PoC sequence:

```text
1. print JSON to console
2. push JSON through WebSocket or TCP/HTTP to server
3. display OSD boxes
4. trigger GPIO/RS485 alarm light after wiring is confirmed
```

Do not start with GPIO as the first verification step. It adds hardware uncertainty.

## 10. Performance Test

Run for at least 30 minutes first:

```text
record FPS
record RKNN inference time
record preprocessing time
record postprocess time
record CPU usage
record memory usage
record temperature if available
```

Then run 24 hours:

```text
no crash
no memory leak
no video pipeline failure
no model reload failure
```

## 11. If It Is Too Slow

Try in this order:

```text
1. use 320 input
2. crop ROI before inference
3. skip frames, for example process 10-15 effective FPS
4. replace CPU NV12-to-RGB with RGA
5. reduce OSD/log frequency
6. use external IPC/GPU edge server if still insufficient
```

## 12. Package After PoC

After `/userdata` PoC works, choose one production path.

Path A: copy into `/app`

```text
/app/hrsipc
/app/model/sorting_yolo.rknn
/app/lib/libhrssdk.so
/app/lib/librknnrt.so
```

Path B: build firmware

```bash
cd /path/to/horuskit_WT-1126B_WT-2.06.06-B
./build.sh fw
```

Then upgrade through web UI or RKDevTool.

Use firmware packaging only after the `/userdata` version is stable.

## 13. Vendor Questions Before Running

Ask the vendor to confirm:

```text
1. Whether `/userdata` app execution is allowed.
2. Whether replacing `/app/hrsipc` is allowed.
3. Exact AArch64 cross compiler version.
4. RKNPU2 driver version.
5. librknnrt version matching firmware.
6. Correct path for librga.so.
7. Whether GPIO/RS485 pins are available for alarm light.
8. How to configure auto-start after reboot.
```
