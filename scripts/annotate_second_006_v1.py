from sorting_annotation_utils import add_complete, interpolate, write_batch

OPEN = {
    181: (158, 321, 338, 369),
    186: (239, 318, 423, 365),
    191: (318, 316, 500, 363),
    196: (397, 314, 580, 361),
    201: (478, 311, 660, 359),
}
CLOSED = {
    181: (351, 268, 578, 327),
    186: (480, 264, 660, 324),
    191: (76, 273, 264, 333),
    196: (157, 272, 338, 331),
    201: (243, 269, 421, 329),
    206: (318, 267, 497, 327),
    210: (385, 265, 566, 325),
}


def boxes(frame):
    out = []
    if frame <= 203:
        add_complete(out, 1, interpolate(frame, OPEN))
    add_complete(out, 2, interpolate(frame, CLOSED))
    out += [(3, 0, 380, 629, 754), (3, 633, 380, 719, 754)]
    out.append((4, 236, 851, 719, 1279))
    return out


write_batch(
    6, 181, 210, boxes,
    "粉色件已进入袋内并被袋沿遮挡，不再标 parcel；继续标注清晰完整的开/关门板"
)
