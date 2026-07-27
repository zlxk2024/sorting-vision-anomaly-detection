from sorting_annotation_utils import add_complete, interpolate, write_batch

PARCEL = {
    301: (166, 287, 261, 365),
    306: (257, 335, 332, 422),
    311: (292, 400, 405, 493),
    316: (318, 490, 454, 596),
    321: (350, 628, 501, 746),
    325: (374, 759, 536, 851),
}
OPEN = {
    301: (172, 317, 340, 360),
    306: (256, 310, 443, 355),
    311: (344, 306, 530, 351),
    316: (430, 301, 619, 347),
    321: (518, 298, 704, 343),
}
CLOSED = {
    306: (25, 260, 204, 320),
    311: (111, 255, 289, 316),
    316: (195, 250, 374, 312),
    321: (281, 246, 457, 307),
    326: (365, 241, 543, 303),
    330: (430, 238, 608, 300),
}


def boxes(frame):
    out = []
    if frame <= 325:
        add_complete(out, 0, interpolate(frame, PARCEL))
    if frame <= 322:
        add_complete(out, 1, interpolate(frame, OPEN))
    if frame >= 306:
        add_complete(out, 2, interpolate(frame, CLOSED))
    out += [(3, 0, 377, 629, 752), (3, 633, 377, 719, 752)]
    out.append((4, 236, 845, 719, 1279))
    return out


write_batch(
    10, 301, 330, boxes,
    "黑色件连续下落，进入袋口遮挡后停止标注；同步标注承载开门板与完整橙色关闭门板"
)
