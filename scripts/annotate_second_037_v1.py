from sorting_annotation_utils import add_complete, common_scene, interpolate, write_batch

OPEN={1111:(160,423,318,463),1125:(365,416,528,456),1140:(580,409,718,449)}
CLOSED_A={1111:(370,371,523,418),1125:(584,360,718,410)}

def boxes(frame):
    out=[]
    add_complete(out,1,interpolate(frame,OPEN))
    if frame<=1125:add_complete(out,2,interpolate(frame,CLOSED_A))
    common_scene(out,chute_y=471,bag=(0,845,585,1279))
    return out

write_batch(37,1111,1140,boxes,
            "随机构翻转逐步停止标 drawer；机械背板不属于抽屉")
