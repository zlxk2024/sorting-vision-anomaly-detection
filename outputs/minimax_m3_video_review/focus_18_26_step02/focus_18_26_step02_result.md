# MiniMax-M3 18-26秒重点复核（0.2秒抽帧 + 严格提示词）

## 18.0s - 20.2s

```json
{"frame_observations":[{"time":"18.0s","observation":"上层传送带有包裹向左移动"},{"time":"18.2s","observation":"包裹在传送带上向左滑行"},{"time":"18.4s","observation":"灰色包裹出现在传送带中段"},{"time":"18.6s","observation":"包裹在传送带托盘中移动"},{"time":"18.8s","observation":"包裹在传送带右移"},{"time":"19.0s","observation":"深色包裹在传送带中部"},{"time":"19.2s","observation":"包裹继续在传送带上移动"},{"time":"19.4s","observation":"包裹接近传送带右段"},{"time":"19.6s","observation":"包裹在传送带右侧区域"},{"time":"19.8s","observation":"包裹停留在传送带右侧"},{"time":"20.0s","observation":"包裹仍在传送带右部"},{"time":"20.2s","observation":"包裹位于传送带右段托盘上"}],"events":[{"start_time":"18.0s","end_time":"20.2s","type":"normal","open_chute":"未知","actual_chute":"未知","evidence":"全程仅见包裹在传送带托盘上移动，未见明确抽屉/格口打开动作，也未见包裹下落或卡滞","confidence":0.6}],"false_positive_risk":"medium","need_human_review":true}
```

## 20.4s - 22.2s

```json
{
  "frame_observations": [
    {"time": "20.40s", "observation": "传送带右侧有一小暗色物体移动"},
    {"time": "20.60s", "observation": "暗色物体继续在传送带上移动"},
    {"time": "20.80s", "observation": "传送带上物体位置变化，格口静止"},
    {"time": "21.00s", "observation": "传送带运行，暗色物体向左移动"},
    {"time": "21.20s", "observation": "传送带上物体继续向左移动"},
    {"time": "21.40s", "observation": "传送带输送物体经过格口上方"},
    {"time": "21.60s", "observation": "物体位置变化，格口盖板未动"},
    {"time": "21.80s", "observation": "格口盖板开始动作，传送带空"},
    {"time": "22.00s", "observation": "左侧格口盖板打开，未见包裹下落"},
    {"time": "22.20s", "observation": "格口盖板处于开/闭切换状态，无包裹可见"}
  ],
  "events": [
    {
      "start_time": "20.4s",
      "end_time": "22.2s",
      "type": "normal",
      "open_chute": "未知",
      "actual_chute": "无",
      "evidence": "20.4-22.2s全程未见包裹从格口下落，传送带物体过小无法确认，格口动作正常",
      "confidence": 0.6
    }
  ],
  "false_positive_risk": "medium",
  "need_human_review": true
}
```

## 22.4s - 26.0s

```json
{
  "frame_observations": [
    {"time": "22.40s", "observation": "分拣线运行中，未见包裹在格口上"},
    {"time": "22.60s", "observation": "小车/格口运动中，无可见包裹"},
    {"time": "22.80s", "observation": "格口运行正常，未见包裹滞留"},
    {"time": "23.00s", "observation": "左侧格口盖板运动，无包裹可见"},
    {"time": "23.20s", "observation": "格口继续运行，无包裹滞留"},
    {"time": "23.40s", "observation": "分拣线运行，无明显包裹"},
    {"time": "23.60s", "observation": "格口盖板开合动作，无可见包裹"},
    {"time": "23.80s", "observation": "格口打开/关闭，无滞留包裹"},
    {"time": "24.00s", "observation": "左侧格口出现浅色小包裹"},
    {"time": "24.20s", "observation": "包裹在左格口斜面下滑中"},
    {"time": "24.40s", "observation": "包裹沿左侧斜面正常下滑"},
    {"time": "24.60s", "observation": "包裹继续下滑接近袋口"},
    {"time": "24.80s", "observation": "包裹落入左下方集装袋"},
    {"time": "25.00s", "observation": "左格口已清空，其余格口无包裹"},
    {"time": "25.20s", "observation": "分拣线正常运行，无异常"},
    {"time": "25.40s", "observation": "格口区域无包裹滞留"},
    {"time": "25.60s", "observation": "小车循环运行，无包裹可见"},
    {"time": "25.80s", "observation": "分拣线持续运行"},
    {"time": "26.00s", "observation": "无异常状态"}
  ],
  "events": [
    {
      "start_time": "24.0s",
      "end_time": "24.8s",
      "type": "normal",
      "open_chute": "左",
      "actual_chute": "左",
      "evidence": "24.00s包裹出现在左格口，24.20-24.60s沿斜面正常下滑，24.80s落入对应集装袋",
      "confidence": 0.85
    }
  ],
  "false_positive_risk": "low",
  "need_human_review": false
}
```
