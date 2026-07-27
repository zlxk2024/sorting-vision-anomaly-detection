from sorting_annotation_utils import add_complete, interpolate, write_batch

PARCEL = {
    361: (447, 481, 555, 627),
    363: (465, 537, 583, 682),
    365: (489, 609, 610, 790),
    367: (523, 706, 620, 868),
}
PARCEL_TOP = {
    374: (12, 211, 101, 275),
    379: (66, 203, 154, 270),
    385: (157, 235, 246, 338),
    390: (218, 248, 307, 353),
}
OPEN = {
    381: (6, 305, 174, 349),
    385: (78, 304, 248, 347),
    390: (164, 303, 331, 346),
}
CLOSED_A = {
    363: (18, 237, 208, 296),
    370: (134, 233, 315, 293),
    380: (260, 228, 439, 289),
    390: (371, 224, 552, 286),
}
CLOSED_B = {
    363: (241, 228, 417, 290),
    370: (357, 225, 536, 287),
    380: (525, 220, 706, 282),
}


def boxes(frame):
    out = []
    if frame <= 367:
        add_complete(out, 0, interpolate(frame, PARCEL))
    if frame >= 374:
        add_complete(out, 0, interpolate(frame, PARCEL_TOP))
    if frame >= 381:
        add_complete(out, 1, interpolate(frame, OPEN))
    if frame >= 363:
        add_complete(out, 2, interpolate(frame, CLOSED_A))
    if 363 <= frame <= 380:
        add_complete(out, 2, interpolate(frame, CLOSED_B))
    out += [(3, 0, 371, 629, 745), (3, 633, 371, 719, 745)]
    out.append((4, 236, 833, 719, 1279))
    return out


write_batch(
    12, 361, 390, boxes,
    "继续跟踪米色小件；补充上层新包裹；drawer_open 仅框包裹下方真实水平银色门板"
)
