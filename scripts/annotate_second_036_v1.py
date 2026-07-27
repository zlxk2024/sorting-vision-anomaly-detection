from sorting_annotation_utils import add_complete, common_scene, interpolate, write_batch

OPEN={1081:(2,431,102,469),1095:(2,429,102,467),1110:(159,423,316,463)}
CLOSED_A={1081:(152,381,305,426),1095:(151,379,305,424),1110:(368,371,521,418)}
CLOSED_B={1081:(361,375,514,421),1095:(360,374,515,420),1110:(580,366,718,413)}

def boxes(frame):
    out=[]
    add_complete(out,1,interpolate(frame,OPEN))
    add_complete(out,2,interpolate(frame,CLOSED_A))
    add_complete(out,2,interpolate(frame,CLOSED_B))
    common_scene(out,chute_y=476,bag=(0,850,580,1279))
    return out

write_batch(36,1081,1110,boxes,
            "只标实体橙色关闭板和完整水平银色开门板")
