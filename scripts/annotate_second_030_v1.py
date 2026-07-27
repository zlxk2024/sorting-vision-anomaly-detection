from sorting_annotation_utils import add_complete, common_scene, interpolate, write_batch

PARCEL = {
    901:(81,390,264,504), 906:(188,448,325,541),
    911:(220,503,382,607), 916:(243,559,432,702),
    921:(270,664,465,824), 924:(285,772,470,928),
}
OPEN_A = {
    901:(2,440,139,477), 906:(2,440,139,478),
    911:(122,437,282,476), 916:(122,437,282,476),
    921:(234,432,394,472), 926:(313,430,473,470),
    930:(313,429,473,469),
}
OPEN_B = {
    911:(314,436,474,475), 916:(314,436,474,475),
    921:(458,432,618,471), 926:(509,430,690,469),
    930:(526,429,690,469),
}
CLOSED = {
    901:(530,395,690,444), 906:(600,392,718,441),
}

def boxes(frame):
    out=[]
    if frame <= 924:
        add_complete(out,0,interpolate(frame,PARCEL))
    add_complete(out,1,interpolate(frame,OPEN_A))
    if frame >= 911:
        add_complete(out,1,interpolate(frame,OPEN_B))
    if frame <= 906:
        add_complete(out,2,interpolate(frame,CLOSED))
    common_scene(out, chute_y=486, bag=(0,874,535,1279))
    return out

write_batch(30,901,930,boxes,
            "连续跟踪黑色包裹沿闸口下滑；进入袋口被遮挡后不再框 parcel")
