from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import csv
import json
import os
import shutil


ROOT = Path(__file__).resolve().parents[1]
OLD_MANIFEST = (
    ROOT / "datasets/sorting_yolo_stage1/compact_v2_selection/manifest.csv"
)
NEW_A = (
    ROOT
    / "datasets/sorting_two_chutes_supplement/review_additional_100_v2"
)
NEW_B = (
    ROOT
    / "datasets/sorting_two_chutes_supplement/review_expansion_400_v1_7"
)
OUTPUT = ROOT / "datasets/sorting_yolo_v2_mixed"

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
NEW_VAL_BLOCKS = {4, 11, 15}
NEW_TEST_BLOCKS = {2, 9, 16}


def link_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def label_counts(label: Path) -> Counter:
    counts = Counter()
    for line in label.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid YOLO row in {label}: {line}")
        class_id = int(parts[0])
        values = [float(value) for value in parts[1:]]
        if class_id not in range(len(CLASSES)):
            raise ValueError(f"Invalid class id in {label}: {class_id}")
        if not all(0.0 <= value <= 1.0 for value in values):
            raise ValueError(f"Out-of-bounds box in {label}: {line}")
        counts[CLASSES[class_id]] += 1
    return counts


def new_split(timestamp: float) -> str:
    block = int(timestamp // 10)
    if block in NEW_TEST_BLOCKS:
        return "test"
    if block in NEW_VAL_BLOCKS:
        return "val"
    return "train"


def add_sample(
    *,
    source_name: str,
    source_image: Path,
    source_label: Path,
    split: str,
    timestamp: str,
    output_name: str,
    rows: list[dict],
    totals: dict,
) -> None:
    if not source_image.exists():
        raise FileNotFoundError(source_image)
    if not source_label.exists():
        raise FileNotFoundError(source_label)
    counts = label_counts(source_label)
    image_destination = OUTPUT / "images" / split / f"{output_name}.jpg"
    label_destination = OUTPUT / "labels" / split / f"{output_name}.txt"
    link_or_copy(source_image, image_destination)
    link_or_copy(source_label, label_destination)
    totals[(split, source_name)].update(counts)
    rows.append(
        {
            "name": output_name,
            "source": source_name,
            "split": split,
            "time_seconds": timestamp,
            "image_source": "./" + str(source_image.resolve().relative_to(ROOT)),
            "label_source": "./" + str(source_label.resolve().relative_to(ROOT)),
            **{name: counts[name] for name in CLASSES},
        }
    )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    totals = defaultdict(Counter)

    for row in csv.DictReader(OLD_MANIFEST.open(encoding="utf-8")):
        stem = Path(row["frame"]).stem
        add_sample(
            source_name="old_scene_compact",
            source_image=(ROOT / row["image_source"]),
            source_label=(ROOT / row["label_source"]),
            split=row["split"],
            timestamp=row["second"],
            output_name=f"old_{stem}",
            rows=rows,
            totals=totals,
        )

    new_sources = [
        (
            "new_scene_reviewed_200",
            NEW_A,
            NEW_A / "manifest_final.csv",
            "new_a",
        ),
        (
            "new_scene_reviewed_400",
            NEW_B,
            NEW_B / "manifest.csv",
            "new_b",
        ),
    ]
    for source_name, root, manifest, prefix in new_sources:
        for row in csv.DictReader(manifest.open(encoding="utf-8")):
            timestamp = float(row["time_seconds"])
            image = root / "images" / row["image"]
            label = root / "labels_yolo" / f"{Path(row['image']).stem}.txt"
            add_sample(
                source_name=source_name,
                source_image=image,
                source_label=label,
                split=new_split(timestamp),
                timestamp=f"{timestamp:.3f}",
                output_name=f"{prefix}_{Path(row['image']).stem}",
                rows=rows,
                totals=totals,
            )

    with (OUTPUT / "split_manifest.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    data_yaml = (
        ""
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "names:\n"
        + "".join(f"  {index}: {name}\n" for index, name in enumerate(CLASSES))
    )
    (OUTPUT / "data.yaml").write_text(data_yaml, encoding="utf-8")
    for subset, predicate in (
        ("old", lambda row: row["source"] == "old_scene_compact"),
        ("new", lambda row: row["source"].startswith("new_scene_")),
    ):
        test_images = [
            f"./images/test/{row['name']}.jpg"
            for row in rows
            if row["split"] == "test" and predicate(row)
        ]
        list_path = OUTPUT / f"test_{subset}.txt"
        list_path.write_text("\n".join(test_images) + "\n", encoding="utf-8")
        subset_yaml = (
            ""
            "train: images/train\n"
            "val: images/val\n"
            f"test: {list_path.name}\n"
            "names:\n"
            + "".join(
                f"  {index}: {name}\n"
                for index, name in enumerate(CLASSES)
            )
        )
        (OUTPUT / f"data_{subset}_test.yaml").write_text(
            subset_yaml, encoding="utf-8"
        )

    summary = {
        "images": len(rows),
        "split_images": dict(Counter(row["split"] for row in rows)),
        "source_images": dict(Counter(row["source"] for row in rows)),
        "instances_by_split_and_source": {
            f"{split}/{source}": {
                name: counts[name] for name in CLASSES
            }
            for (split, source), counts in sorted(totals.items())
        },
        "new_scene_split_policy": {
            "group_unit": "non-overlapping 10-second time block",
            "val_blocks": sorted(NEW_VAL_BLOCKS),
            "test_blocks": sorted(NEW_TEST_BLOCKS),
            "reason": (
                "Prevent adjacent or duplicate frames from the same video "
                "appearing in different splits."
            ),
        },
        "old_scene_policy": (
            "Use the existing second-grouped split from compact_v2_selection."
        ),
    }
    (OUTPUT / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
