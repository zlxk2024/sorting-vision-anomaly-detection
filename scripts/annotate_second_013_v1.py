from sorting_annotation_utils import add_complete, interpolate, write_batch

PARCEL = {
    391: (220, 255, 309, 373),
    396: (271, 317, 342, 431),
    401: (302, 402, 416, 527),
    407: (330, 544, 466, 691),
    412: (367, 695, 511, 875),
}
OPEN = {
    391: (174, 305, 357, 347),
    396: (244, 302, 430, 345),
    401: (323, 299, 510, 343),
    407: (410, 301, 599, 346),
    413: (503, 295, 691, 341),
}
CLOSED_OLD = {
    391: (432, 232, 612, 295),
    396: (508, 229, 688, 293),
}
CLOSED_NEW = {
    401: (55, 259, 244, 320),
    407: (157, 252, 353, 316),
    413: (258, 246, 454, 311),
    420: (367, 240, 568, 306),
}


def boxes(frame):
    out = []
    if frame <= 412:
        add_complete(out, 0, interpolate(frame, PARCEL))
    if frame <= 413:
        add_complete(out, 1, interpolate(frame, OPEN))
    if frame <= 396:
        add_complete(out, 2, interpolate(frame, CLOSED_OLD))
    if frame >= 401:
        add_complete(out, 2, interpolate(frame, CLOSED_NEW))
    out += [(3, 0, 369, 629, 743), (3, 633, 369, 719, 743)]
    out.append((4, 204, 829, 719, 1279))
    return out


write_batch(
    13, 391, 420, boxes,
    "跟踪纸箱/白色件下落；只框实际水平银色开门板和实际橙色关闭门板"
)
