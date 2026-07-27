from sorting_annotation_utils import add_complete, common_scene, interpolate, write_batch

OPEN_A = {
    931:(326,428,486,468), 936:(397,428,555,469),
    941:(464,427,627,468), 946:(538,426,698,467),
}
OPEN_B = {
    941:(64,433,204,472), 946:(112,432,272,472),
    951:(183,431,337,471), 956:(247,430,405,470),
    960:(298,429,458,469),
}

def boxes(frame):
    out=[]
    if frame <= 946:
        add_complete(out,1,interpolate(frame,OPEN_A))
    if frame >= 941:
        add_complete(out,1,interpolate(frame,OPEN_B))
    common_scene(out, chute_y=487, bag=(0,875,535,1279))
    return out

write_batch(31,931,960,boxes,
            "袋内包裹被袋沿遮挡，不标 parcel；翻转机构背面不标 drawer_closed")
