from sorting_annotation_utils import add_complete, interpolate, write_batch

WHITE = {
    61: (350, 526, 456, 610),
    66: (390, 650, 489, 739),
}
YELLOW = {
    80: (31, 228, 128, 344),
    82: (55, 247, 151, 365),
    86: (93, 263, 211, 387),
    90: (207, 246, 287, 374),
}
OPEN = {
    61: (432, 315, 635, 365),
    66: (43, 326, 225, 372),
    71: (119, 322, 300, 368),
    76: (198, 319, 379, 365),
    82: (291, 313, 474, 361),
    86: (356, 310, 537, 356),
    90: (421, 306, 608, 353),
}
CLOSED = {
    61: (194, 267, 369, 323),
    66: (250, 262, 427, 319),
    71: (333, 263, 510, 319),
    76: (407, 258, 589, 316),
}


def boxes(frame):
    out = []
    if frame <= 68:
        add_complete(out, 0, interpolate(frame, WHITE))
    if frame >= 80:
        add_complete(out, 0, interpolate(frame, YELLOW))
    add_complete(out, 1, interpolate(frame, OPEN))
    if frame <= 79:
        add_complete(out, 2, interpolate(frame, CLOSED))
    divider = round(608 + (frame - 61) * 2.0)
    out += [(3, 0, 382, divider - 4, 758), (3, divider, 382, 719, 758)]
    out.append((4, 236, 856, 719, 1279))
    return out


write_batch(
    2, 61, 90, boxes,
    "白色件下落至袋口后消失；黄色件从左侧完整进入画面后开始标注；边缘残缺实体不标"
)
