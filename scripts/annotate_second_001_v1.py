from sorting_annotation_utils import add_complete, interpolate, write_batch

PARCEL={46:(214,356,280,415),50:(260,382,334,444),
        55:(318,424,403,500),60:(335,476,425,558)}
OPEN={38:(42,329,199,371),41:(90,331,250,374),46:(137,334,326,376),
      51:(238,334,426,376),56:(334,332,512,374),60:(414,329,604,371)}
CLOSED={31:(2,292,80,345),36:(2,294,113,348),41:(2,295,143,349)}

def boxes(f):
    out=[]
    if f>=46:add_complete(out,0,interpolate(f,PARCEL))
    if f>=38:add_complete(out,1,interpolate(f,OPEN))
    if f<=41:add_complete(out,2,interpolate(f,CLOSED))
    d=round(610+(f-31)*(20/29)); y=round(398+(f-31)*(3/29))
    out += [(3,0,y,d-3,762),(3,d,y,719,762),(4,145,879,719,1279)]
    return out

write_batch(1,31,60,boxes,
            "跟踪白色包裹离开水平门板并下滑；机构背面不标关闭抽屉")
