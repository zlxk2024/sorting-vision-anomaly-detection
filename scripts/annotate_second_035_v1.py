from sorting_annotation_utils import add_complete, common_scene, interpolate, write_batch

OPEN={1051:(162,426,320,466),1065:(350,422,511,462),1080:(572,416,718,457)}
CLOSED_A={1051:(372,377,525,424),1065:(571,367,718,416)}
CLOSED_B={1051:(2,385,96,428),1065:(151,381,304,426),1080:(361,375,514,421)}

def boxes(frame):
    out=[]
    add_complete(out,1,interpolate(frame,OPEN))
    if frame<=1065:add_complete(out,2,interpolate(frame,CLOSED_A))
    add_complete(out,2,interpolate(frame,CLOSED_B))
    common_scene(out,chute_y=478,bag=(0,854,575,1279))
    return out

write_batch(35,1051,1080,boxes,
            "标注完整水平开门板和橙色关闭板；袋内包裹被遮挡不标")
