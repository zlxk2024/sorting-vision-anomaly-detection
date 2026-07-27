from sorting_annotation_utils import add_complete, interpolate, write_batch

PARCEL = {
    138: (16, 219, 145, 304),
    141: (27, 226, 160, 314),
    146: (91, 245, 250, 345),
    150: (167, 246, 301, 359),
}
OPEN = {
    121: (380, 315, 568, 359),
    126: (458, 313, 646, 357),
    138: (68, 319, 246, 365),
    146: (137, 315, 318, 361),
    150: (199, 313, 381, 359),
}


def boxes(frame):
    out = []
    if frame >= 138:
        add_complete(out, 0, interpolate(frame, PARCEL))
    add_complete(out, 1, interpolate(frame, OPEN))
    divider = 633
    out += [(3, 0, 379, divider - 4, 754), (3, divider, 379, 719, 754)]
    out.append((4, 236, 851, 719, 1279))
    return out


write_batch(
    4, 121, 150, boxes,
    "粉色件左侧残缺时不标，完整进入画面后开始标注；翻转机构背面不作为关闭抽屉"
)
