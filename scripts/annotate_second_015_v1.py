from sorting_annotation_utils import write_batch


def boxes(frame):
    out = [(3, 0, 414, 607, 764), (3, 612, 414, 719, 764)]
    out.append((4, 176, 855, 719, 1279))
    return out


write_batch(
    15, 451, 480, boxes,
    "画面主要为翻转机构背面，不误标 drawer；无完整包裹和完整门板"
)
