from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "runs/video_quality_comparison/raw_frames"
OUT = ROOT / "runs/video_quality_comparison/annotated"
FONT = "/System/Library/Fonts/PingFang.ttc"

COLORS = {
    "parcel": "#1597E5",
    "drawer": "#43C65A",
    "chute": "#FF5555",
    "bag": "#FFC400",
}


def font(size: int):
    return ImageFont.truetype(FONT, size)


def label_box(draw, box, label, color, width=4):
    x1, y1, x2, y2 = box
    draw.rectangle(box, outline=color, width=width)
    f = font(max(16, min(24, int((x2 - x1) / 8))))
    text_box = draw.textbbox((0, 0), label, font=f)
    tw = text_box[2] - text_box[0]
    th = text_box[3] - text_box[1]
    ty = max(0, y1 - th - 9)
    draw.rounded_rectangle(
        (x1, ty, min(x2, x1 + tw + 12), ty + th + 8),
        radius=4,
        fill=color,
    )
    draw.text((x1 + 6, ty + 2), label, font=f, fill="white")


def build(spec):
    src = Image.open(RAW / spec["file"]).convert("RGB")
    w, h = src.size
    top_h = 94
    bottom_h = 76
    canvas = Image.new("RGB", (w, h + top_h + bottom_h), "#071426")
    canvas.paste(src, (0, top_h))
    draw = ImageDraw.Draw(canvas)

    draw.text((22, 12), spec["title"], font=font(29), fill="#FFFFFF")
    draw.text((22, 53), spec["meta"], font=font(18), fill="#A8D8FF")

    for item in spec["boxes"]:
        x1, y1, x2, y2 = item["box"]
        shifted = (x1, y1 + top_h, x2, y2 + top_h)
        label_box(draw, shifted, item["label"], COLORS[item["kind"]])

    y = h + top_h
    draw.rectangle((0, y, w, y + bottom_h), fill="#0B2038")
    draw.text((20, y + 10), spec["summary"], font=font(20), fill="#FFFFFF")
    draw.text((20, y + 41), spec["note"], font=font(16), fill="#B8C9DB")

    output = OUT / spec["output"]
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=94)
    return output


SPECS = [
    {
        "file": "customer_t006.jpg",
        "output": "01_customer_fixed_cctv_marked.jpg",
        "title": "客户固定摄像头｜最终部署场景代表帧",
        "meta": "960×544 · 21 FPS · H.264≈1.2 Mbps · 固定机位",
        "summary": "优势：机位稳定、连续采集、与最终上线环境一致",
        "note": "问题：包裹目标偏小，白色区域高光明显，广角鱼眼畸变较强",
        "boxes": [
            {"kind": "parcel", "label": "包裹（目标偏小）", "box": (393, 82, 430, 146)},
            {"kind": "parcel", "label": "包裹", "box": (570, 78, 610, 143)},
            {"kind": "drawer", "label": "抽屉运动区", "box": (275, 46, 700, 166)},
            {"kind": "chute", "label": "闸口", "box": (91, 185, 372, 431)},
            {"kind": "bag", "label": "落袋", "box": (115, 355, 365, 542)},
        ],
    },
    {
        "file": "two_chutes_t127_477.jpg",
        "output": "02_two_chutes_mobile_marked.jpg",
        "title": "两闸口手机视频｜近距离采样代表帧",
        "meta": "544×960 · 27 FPS · H.264≈1.2 Mbps · 竖屏近景",
        "summary": "优势：包裹和抽屉目标较大，人工标注与首版验证最容易",
        "note": "问题：竖屏覆盖少、机位会移动，与固定摄像头部署域存在差异",
        "boxes": [
            {"kind": "parcel", "label": "包裹", "box": (242, 173, 282, 247)},
            {"kind": "parcel", "label": "包裹", "box": (341, 194, 397, 268)},
            {"kind": "drawer", "label": "抽屉状态判定区", "box": (137, 239, 440, 318)},
            {"kind": "chute", "label": "两组闸口", "box": (0, 320, 543, 669)},
            {"kind": "bag", "label": "落袋", "box": (105, 650, 296, 958)},
        ],
    },
    {
        "file": "four_chutes_t078_1.jpg",
        "output": "03_four_chutes_wide_marked.jpg",
        "title": "四闸口横屏视频｜多闸口采样代表帧",
        "meta": "960×544 · 30 FPS · HEVC≈0.55 Mbps · 横屏俯拍",
        "summary": "优势：覆盖四个闸口且目标仍可辨认，视野与细节更均衡",
        "note": "问题：码率偏低、压缩更重；仍需固定机位和原始码流采集",
        "boxes": [
            {"kind": "parcel", "label": "包裹", "box": (208, 49, 269, 129)},
            {"kind": "parcel", "label": "包裹", "box": (565, 91, 612, 140)},
            {"kind": "drawer", "label": "四组抽屉运动区", "box": (0, 40, 959, 179)},
            {"kind": "chute", "label": "四个闸口", "box": (0, 181, 875, 430)},
            {"kind": "bag", "label": "落袋", "box": (0, 414, 294, 543)},
        ],
    },
]


if __name__ == "__main__":
    for spec in SPECS:
        print(build(spec))
