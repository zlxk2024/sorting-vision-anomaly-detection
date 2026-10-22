# Camera App Integration Notes

The file `sorting_horus_integration.cpp` is a buildable logic skeleton, not a complete replacement for the vendor `hrsipc` program.

The real camera app should be implemented by modifying the Horus SDK example:

```text
./data/videos/horuskit_WT-1126B_WT-2.06.06-B/sdk/src/example/obj_detection_yolov8_1126b.cpp
```

## Integration Points

### 1. Model path

Replace hard-coded YOLOv8 model path:

```text
/app/model/yolov8.rknn
```

with:

```text
/app/model/sorting_yolo.rknn
```

or:

```text
/userdata/model/sorting_yolo.rknn
```

Use one path only. The current vendor example loads `/userdata/model/yolov8.rknn` and initializes `/app/model/yolov8.rknn`, which should be cleaned up.

### 2. Class names

Replace COCO labels with:

```text
parcel
drawer_open
drawer_closed
chute
bag
```

### 3. YOLO postprocess

If using RKNN Model Zoo YOLO11 converter, use the YOLO11 C++ postprocess from RKNN Model Zoo.

Do not assume the current `postprocess_yolov8.cpp` will match YOLO11 output tensors.

### 4. Detection mapping

After postprocess, convert each detection into:

```cpp
sorting_vision::Detection{
    class_id,
    score,
    sorting_vision::Box{left, top, right, bottom}
}
```

Then call:

```cpp
std::vector<Event> events = state_machine.update(detections, timestamp_s);
```

### 5. Alarm output

For PoC, output JSON event through WebSocket/TCP first.

After hardware wiring is confirmed, add GPIO/RS485 alarm light.

### 6. Preprocessing

The vendor example currently uses CPU `nv12_to_rgb24`. This is acceptable for first bring-up but should be replaced by RGA resize/color conversion for production.

### 7. ROI

The model should receive only useful regions:

```text
drawer mechanism
chute area
bag entrance
```

Avoid full-frame 320 downscale if parcels become too small.
