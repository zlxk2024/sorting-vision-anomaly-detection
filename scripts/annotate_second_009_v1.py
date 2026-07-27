from sorting_annotation_utils import add_complete, interpolate, write_batch

PARCEL = {
    292: (68, 261, 154, 326),
    295: (104, 268, 181, 337),
    298: (139, 277, 213, 347),
    300: (159, 286, 231, 354),
}
OPEN = {
    292: (53, 321, 214, 364),
    296: (93, 319, 254, 362),
    300: (147, 316, 311, 360),
}


def boxes(frame):
    out = []
    if frame >= 292:
        add_complete(out, 0, interpolate(frame, PARCEL))
        add_complete(out, 1, interpolate(frame, OPEN))
    out += [(3, 0, 382, 629, 754), (3, 633, 382, 719, 754)]
    out.append((4, 236, 851, 719, 1279))
    return out


write_batch(
    9, 271, 300, boxes,
    "前段为机构背面不标；黑色件和承载它的水平银色开门板完整出现后开始标注"
)
