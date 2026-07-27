from sorting_annotation_utils import add_complete, common_scene, interpolate, write_batch

OPEN = {961:(313,430,473,470), 970:(436,432,600,472),
        980:(580,433,718,474)}

def boxes(frame):
    out=[]
    add_complete(out,1,interpolate(frame,OPEN))
    common_scene(out, chute_y=488, bag=(0,878,545,1279))
    return out

write_batch(32,961,990,boxes,
            "袋内包裹仅部分可见不标 parcel；机构背面不是抽屉")
