from sorting_annotation_utils import add_complete, interpolate, write_batch

PARCEL = {
    151: (179, 240, 309, 359),
    156: (268, 270, 390, 421),
    161: (329, 335, 465, 492),
    166: (368, 409, 537, 576),
    171: (400, 518, 611, 707),
    176: (415, 690, 675, 889),
}
OPEN = {
    151: (216, 312, 397, 358),
    156: (240, 315, 422, 361),
    161: (314, 314, 495, 361),
    166: (397, 313, 579, 360),
    171: (476, 311, 658, 358),
}
CLOSED = {
    160: (63, 278, 245, 337),
    166: (158, 274, 337, 333),
    171: (239, 272, 415, 331),
    176: (318, 270, 497, 329),
    180: (385, 268, 563, 327),
}


def boxes(frame):
    out = []
    if frame <= 176:
        add_complete(out, 0, interpolate(frame, PARCEL))
    if frame <= 173:
        add_complete(out, 1, interpolate(frame, OPEN))
    if frame >= 160:
        add_complete(out, 2, interpolate(frame, CLOSED))
    out += [(3, 0, 379, 629, 754), (3, 633, 379, 719, 754)]
    out.append((4, 236, 851, 719, 1279))
    return out


write_batch(
    5, 151, 180, boxes,
    "跟踪粉色件从水平门板离开并下落；袋沿开始明显遮挡后停止标注"
)
