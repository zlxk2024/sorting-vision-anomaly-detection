from sorting_annotation_utils import add_complete, common_scene, interpolate, write_batch

OPEN_A={1021:(130,429,292,469),1030:(144,426,305,466),
        1040:(10,427,168,466),1050:(145,424,304,464)}
OPEN_B={1021:(337,428,498,468),1030:(352,425,512,465),
        1040:(426,423,585,463)}
CLOSED_A={1035:(96,383,248,428),1040:(166,382,369,427),
          1045:(285,380,440,425),1050:(358,378,512,423)}

def boxes(frame):
    out=[]
    add_complete(out,1,interpolate(frame,OPEN_A))
    if frame<=1040:add_complete(out,1,interpolate(frame,OPEN_B))
    if frame>=1035:add_complete(out,2,interpolate(frame,CLOSED_A))
    common_scene(out, chute_y=483, bag=(0,866,570,1279))
    return out

write_batch(34,1021,1050,boxes,
            "从翻转机构过渡到实体门板，仅标完整水平开门板与橙色竖立关闭板")
