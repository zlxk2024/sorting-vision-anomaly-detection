from sorting_annotation_utils import add_complete, interpolate, write_batch

LARGE_WHITE = {
    331: (188, 249, 324, 333),
    336: (203, 266, 342, 357),
    341: (268, 359, 452, 455),
    346: (346, 550, 579, 688),
    349: (372, 690, 636, 833),
}
SMALL_BEIGE = {
    334: (17, 207, 80, 278),
    339: (117, 218, 185, 294),
    346: (297, 242, 356, 333),
    351: (363, 312, 424, 401),
    356: (408, 384, 491, 493),
    360: (440, 461, 550, 620),
}
OPEN = {
    336: (40, 290, 224, 335),
    341: (125, 286, 310, 331),
    346: (210, 282, 395, 327),
    351: (295, 279, 480, 324),
    356: (380, 276, 566, 321),
    360: (447, 273, 633, 318),
}


def boxes(frame):
    out = []
    if frame <= 349:
        add_complete(out, 0, interpolate(frame, LARGE_WHITE))
    if frame >= 334:
        add_complete(out, 0, interpolate(frame, SMALL_BEIGE))
    if frame >= 336:
        add_complete(out, 1, interpolate(frame, OPEN))
    out += [(3, 0, 374, 629, 748), (3, 633, 374, 719, 748)]
    out.append((4, 236, 839, 719, 1279))
    return out


write_batch(
    11, 331, 360, boxes,
    "本秒包含两个独立包裹：大型白件与小型米色件；分别跟踪，进入袋口遮挡后停止标注"
)
