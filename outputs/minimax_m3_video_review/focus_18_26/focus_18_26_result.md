# MiniMax-M3 18-26秒重点复核

## 18.0s - 22.0s

```json
{
  "frame_observations": [
    {"time": "18.0s", "observation": "上方传送带左侧小车上有一深色包裹，格口关闭"},
    {"time": "18.5s", "observation": "左侧小车倾斜打开，深色包裹正在滑动"},
    {"time": "19.0s", "observation": "包裹位于中偏左打开的小车上，闸门已开"},
    {"time": "19.5s", "observation": "右侧格口顶部出现深色包裹，滞留未落"},
    {"time": "20.0s", "observation": "上传送带可见小车，左侧有小型包裹"},
    {"time": "20.5s", "observation": "上传送带两小车上各有一个小包裹"},
    {"time": "21.0s", "observation": "中间及右侧小车上各有深色包裹"},
    {"time": "21.5s", "observation": "左侧小车闸门打开，右上小车有包裹"},
    {"time": "22.0s", "observation": "左侧格口已开，右侧小车上包裹仍在"}
  ],
  "events": [
    {
      "start_time": "18.0s",
      "end_time": "19.0s",
      "type": "open_no_drop",
      "open_chute": "左",
      "actual_chute": "无",
      "evidence": "左小车闸门打开但包裹未立即落入下方收集袋",
      "confidence": 0.6
    },
    {
      "start_time": "19.0s",
      "end_time": "20.0s",
      "type": "slide_abnormal",
      "open_chute": "左",
      "actual_chute": "右",
      "evidence": "深色包裹出现在右侧格口顶部，未落入收集袋",
      "confidence": 0.7
    },
    {
      "start_time": "21.0s",
      "end_time": "22.0s",
      "type": "open_no_drop",
      "open_chute": "左",
      "actual_chute": "无",
      "evidence": "左侧格口开启后未见包裹明显下落入袋",
      "confidence": 0.6
    }
  ],
  "need_human_review": true
}
```

## 22.0s - 26.0s

```json
{
  "frame_observations": [
    {"time": "22.0s", "observation": "格口盖板关闭，无包裹，皮带空载运行"},
    {"time": "22.5s", "observation": "格口盖板仍关闭，上层皮带空载"},
    {"time": "23.0s", "observation": "上层皮带出现小包裹，格口盖板关闭"},
    {"time": "23.5s", "observation": "包裹沿上层皮带移动，盖板未开"},
    {"time": "24.0s", "observation": "包裹接近格口位置，盖板仍关闭"},
    {"time": "24.5s", "observation": "包裹落至关闭的中格盖板表面，盖板未开"},
    {"time": "25.0s", "observation": "盖板表面包裹消失，左上有模糊物体，盖板未开"},
    {"time": "25.5s", "observation": "格口区域空，盖板仍关闭"},
    {"time": "26.0s", "observation": "全部盖板关闭，无包裹滞留"}
  ],
  "events": [
    {
      "start_time": "23.0s",
      "end_time": "25.0s",
      "type": "open_no_drop",
      "open_chute": "中",
      "actual_chute": "无",
      "evidence": "包裹到达中格口但盖板全程未打开，包裹落至盖板后消失未正常落入",
      "confidence": 0.85
    }
  ],
  "need_human_review": true
}
```
