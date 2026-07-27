from sorting_annotation_utils import add_complete, interpolate, write_batch

C1={1:(55,270,250,329),6:(120,276,331,335),11:(29,282,178,341),
    16:(60,279,265,338),21:(155,277,352,336),26:(244,276,438,335),
    30:(310,274,519,334)}
C2={1:(307,269,485,328),6:(399,273,578,333),11:(241,278,423,337),
    16:(333,276,507,335),21:(423,273,603,333),26:(507,271,698,331)}

def boxes(f):
    out=[]
    add_complete(out,2,interpolate(f,C1)); add_complete(out,2,interpolate(f,C2))
    # Two physical orange chute channels; camera shifts slightly during this second.
    d=round(553+(f-1)*(55/29)); y=round(381+(f-1)*(17/29))
    out += [(3,0,y,d-3,770),(3,d,y,719,770),(4,73,878,719,1279)]
    return out

write_batch(0,1,30,boxes,
            "无完整运动包裹；标注橙色关闭门板、两个闸口和主落袋")
