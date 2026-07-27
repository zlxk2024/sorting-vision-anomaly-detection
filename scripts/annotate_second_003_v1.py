from sorting_annotation_utils import add_complete, interpolate, write_batch

PARCEL = {
    91: (223, 259, 310, 386),
    95: (271, 327, 371, 456),
    100: (302, 384, 451, 511),
    105: (317, 465, 502, 597),
    110: (335, 624, 553, 731),
    113: (367, 763, 600, 850),
}
OPEN = {
    91: (438, 305, 623, 350),
    95: (501, 301, 687, 347),
}


def boxes(frame):
    out = []
    if frame <= 113:
        add_complete(out, 0, interpolate(frame, PARCEL))
    if frame <= 96:
        add_complete(out, 1, interpolate(frame, OPEN))
    divider = round(610 + (frame - 91) * 1.4)
    out += [(3, 0, 379, divider - 4, 754), (3, divider, 379, 719, 754)]
    out.append((4, 238, 851, 719, 1279))
    return out


write_batch(
    3, 91, 120, boxes,
    "连续跟踪黄色大件下落；进入袋口并被袋沿遮挡后不再标 parcel；机构背面不标抽屉"
)
