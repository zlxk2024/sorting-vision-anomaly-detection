from pathlib import Path
import shutil


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
SOURCE = (
    ROOT
    / "datasets/sorting_yolo_stage1/m3_prelabels_10/"
    "five_class_all_10_v8_prompt_standard"
)
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/bootstrap_yolo_10"


def main() -> None:
    for split in ("train", "val"):
        image_dir = OUTPUT / "images" / split
        label_dir = OUTPUT / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)

        for image_path in sorted((SOURCE / "images").glob("*.jpg")):
            shutil.copy2(image_path, image_dir / image_path.name)
            label_path = SOURCE / "labels_yolo" / f"{image_path.stem}.txt"
            shutil.copy2(label_path, label_dir / label_path.name)

    yaml_text = f"""path: {OUTPUT}
train: images/train
val: images/val
names:
  0: parcel
  1: drawer_open
  2: drawer_closed
  3: chute
  4: bag
"""
    (OUTPUT / "dataset.yaml").write_text(yaml_text, encoding="utf-8")


if __name__ == "__main__":
    main()
