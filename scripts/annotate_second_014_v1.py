from sorting_annotation_utils import add_complete, interpolate, write_batch

CLOSED = {
    421: (382, 257, 580, 322),
    425: (448, 253, 647, 318),
    429: (514, 249, 714, 314),
}


def boxes(frame):
    out = []
    if frame <= 429:
        add_complete(out, 2, interpolate(frame, CLOSED))
    out += [(3, 0, 388, 613, 756), (3, 618, 388, 719, 756)]
    out.append((4, 166, 853, 719, 1279))
    return out


write_batch(
    14, 421, 450, boxes,
    "翻转机构背面不属于抽屉；仅在完整可见时标注右移的实际橙色关闭门板"
)
