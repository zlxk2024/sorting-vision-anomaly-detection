from sorting_annotation_utils import add_complete, common_scene, interpolate, write_batch

FALLING = {
    871:(204,617,287,670), 876:(204,730,304,804), 880:(219,822,319,913),
}
NEW_PARCEL = {
    889:(12,357,131,452), 891:(30,362,169,458),
    896:(55,377,232,479), 900:(80,390,263,503),
}
OPEN = {
    871:(280,431,438,468), 876:(366,432,526,469),
    881:(439,434,603,472), 886:(515,435,683,474),
}
CLOSED_A = {
    871:(16,382,174,430), 876:(151,386,308,433),
    881:(225,389,382,437), 886:(304,393,457,440),
    891:(377,394,531,441), 896:(454,395,609,443),
    900:(515,395,674,444),
}

def boxes(frame):
    out=[]
    if frame <= 880:
        add_complete(out,0,interpolate(frame,FALLING))
    if frame >= 889:
        add_complete(out,0,interpolate(frame,NEW_PARCEL))
    if frame <= 886:
        add_complete(out,1,interpolate(frame,OPEN))
    add_complete(out,2,interpolate(frame,CLOSED_A))
    # A preceding closed plate remains complete until it exits left.
    prev=interpolate(frame,CLOSED_A)
    add_complete(out,2,(prev[0]-218,prev[1],prev[2]-218,prev[3]))
    common_scene(out)
    return out

write_batch(29,871,900,boxes,
            "跟踪前一包裹进入落袋，并标注随后进入画面的新黑色包裹")
