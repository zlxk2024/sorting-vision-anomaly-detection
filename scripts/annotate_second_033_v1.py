from sorting_annotation_utils import add_complete, common_scene, interpolate, write_batch

OPEN_A={1000:(2,438,142,478),1010:(2,435,143,475),
        1020:(130,429,292,469)}
OPEN_B={1007:(145,436,305,476),1010:(188,434,350,474),
        1020:(337,428,498,468)}

def boxes(frame):
    out=[]
    if frame>=1000:add_complete(out,1,interpolate(frame,OPEN_A))
    if frame>=1007:add_complete(out,1,interpolate(frame,OPEN_B))
    common_scene(out, chute_y=487, bag=(0,877,555,1279))
    return out

write_batch(33,991,1020,boxes,
            "仅标完整水平银色开门板；袋内遮挡包裹和机构背面均不标")
