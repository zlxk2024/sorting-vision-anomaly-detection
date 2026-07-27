from collections import Counter
from pathlib import Path

from ultralytics import YOLO

label_dir = Path("/Users/lixing.guo/Documents/机械臂/outputs/yolo_baseline/phone_video_yolo11n/labels")
model = YOLO("yolo11n.pt")
names = model.names

counts = Counter()
frame_count = 0
for path in sorted(label_dir.glob("*.txt")):
    frame_count += 1
    for line in path.read_text().splitlines():
        parts = line.strip().split()
        if parts:
            counts[int(parts[0])] += 1

print(f"label_files={frame_count}")
print(f"detections={sum(counts.values())}")
for cls_id, count in counts.most_common(30):
    print(f"{names.get(cls_id, cls_id)}={count}")
