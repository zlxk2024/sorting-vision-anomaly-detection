from sorting_annotation_utils import common_scene, write_batch

def boxes(frame):
    out=[]
    common_scene(out,chute_y=450,bag=(0,831,590,1279))
    return out

write_batch(39,1171,1184,boxes,
            "末段上方均为机构背面；只保留两个闸口和主落袋")
