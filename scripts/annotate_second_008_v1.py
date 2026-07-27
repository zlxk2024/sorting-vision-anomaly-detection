from sorting_annotation_utils import write_batch


def moving_closed(frame):
    boxes = []
    base = 158 + 16.2 * (frame - 211)
    # 本秒左侧逐步只剩翻转机构背面；实际橙色关闭门板的左边界随传送带右移。
    real_plate_min_x = 16.0 * (frame - 241)
    for k in range(-8, 5):
        x1 = round(base + 240 * k)
        x2 = x1 + 180
        if x1 >= max(3, real_plate_min_x) and x2 <= 716:
            boxes.append((2, x1, 267, x2, 330))
    return boxes


def boxes(frame):
    out = moving_closed(frame)
    out += [(3, 0, 382, 629, 754), (3, 633, 382, 719, 754)]
    out.append((4, 236, 851, 719, 1279))
    return out


write_batch(
    8, 241, 270, boxes,
    "无包裹事件；翻转机构背面不标，完整橙色关闭门板按运动轨迹标注"
)
