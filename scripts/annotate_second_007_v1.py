from sorting_annotation_utils import write_batch


def moving_closed(frame):
    boxes = []
    base = 158 + 16.2 * (frame - 211)
    for k in range(-4, 5):
        x1 = round(base + 240 * k)
        x2 = x1 + 180
        if x1 >= 3 and x2 <= 716:
            boxes.append((2, x1, 267, x2, 330))
    return boxes


def boxes(frame):
    out = moving_closed(frame)
    out += [(3, 0, 382, 629, 754), (3, 633, 382, 719, 754)]
    out.append((4, 236, 851, 719, 1279))
    return out


write_batch(
    7, 211, 240, boxes,
    "无包裹事件；仅标画面中完整的橙色竖直关闭门板，边缘残缺门板不标"
)
