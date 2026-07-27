from sorting_annotation_utils import common_scene, write_batch

def boxes(frame):
    out=[]
    common_scene(out,chute_y=461,bag=(0,838,590,1279))
    return out

write_batch(38,1141,1170,boxes,
            "画面上方均为翻转机构背面，不误标 drawer_open/drawer_closed")
