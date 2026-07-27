from sorting_annotation_utils import add_complete, interpolate, write_batch

PARCEL = {
    481: (154, 378, 215, 436),
    486: (201, 417, 276, 481),
    491: (219, 481, 287, 543),
    496: (218, 549, 306, 629),
    501: (218, 655, 315, 760),
    504: (214, 731, 322, 839),
}
OPEN_RIGHT = {
    481: (159, 384, 330, 430),
    491: (294, 382, 467, 428),
    501: (443, 379, 615, 425),
    507: (531, 377, 704, 423),
}
OPEN_LEFT = {
    488: (39, 386, 210, 431),
    491: (82, 384, 253, 429),
    501: (233, 381, 398, 426),
    510: (366, 378, 535, 424),
}
CLOSED = {
    499: (8, 336, 163, 393),
    501: (37, 333, 191, 390),
    506: (95, 331, 271, 391),
    510: (157, 328, 334, 389),
}


def boxes(frame):
    out = []
    if frame <= 504:
        add_complete(out, 0, interpolate(frame, PARCEL))
    if frame <= 507:
        add_complete(out, 1, interpolate(frame, OPEN_RIGHT))
    if frame >= 488:
        add_complete(out, 1, interpolate(frame, OPEN_LEFT))
    if frame >= 499:
        add_complete(out, 2, interpolate(frame, CLOSED))
    out += [(3, 0, 434, 599, 753), (3, 604, 434, 719, 753)]
    out.append((4, 115, 831, 686, 1279))
    return out


write_batch(
    16, 481, 510, boxes,
    "跟踪黑色件下落至袋口；两个水平银色门板分别跟踪；背面机构不标"
)
