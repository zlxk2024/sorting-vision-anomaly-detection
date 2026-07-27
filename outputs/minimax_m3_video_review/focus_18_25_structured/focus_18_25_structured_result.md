# MiniMax-M3 结构规则版预标注（无答案提示 + 全路径ROI + 0.2秒）

## segment_a：17.8s - 20.2s

```json
{
  "segment_summary": "has_candidate_anomaly",
  "frame_notes": [
    {"time": "17.80s", "note": "上方传送带左侧小车有深色物体"},
    {"time": "18.00s", "note": "左侧小车仍有深色物体，右侧小车可见浅色包装"},
    {"time": "18.20s", "note": "深色包裹出现在中段传送带"},
    {"time": "18.40s", "note": "深色包裹向右移动"},
    {"time": "18.60s", "note": "包裹继续右移至中段"},
    {"time": "18.80s", "note": "包裹接近右侧格口位置"},
    {"time": "19.00s", "note": "深色包裹落入右侧格口顶部"},
    {"time": "19.20s", "note": "包裹开始下滑，处于右格口上部"},
    {"time": "19.40s", "note": "包裹滑至右格口右上部，靠近右边界"},
    {"time": "19.60s", "note": "包裹贴右侧下滑至格口底部"},
    {"time": "19.80s", "note": "包裹从右格口右下角出画"},
    {"time": "20.00s", "note": "格口已空，仅小车残留碎屑"},
    {"time": "20.20s", "note": "格口无包裹，传送带仍有杂物"}
  ],
  "events": [
    {
      "start_time": "18.20s",
      "end_time": "19.00s",
      "label": "normal",
      "subtags": ["dark_parcel", "conveyor_transit"],
      "evidence": "18.20s-18.80s可见深色包裹沿上方传送带从左向右平稳移动，19.00s落入右侧格口",
      "confidence": 0.7,
      "suggestion_for_human": "accept"
    },
    {
      "start_time": "19.20s",
      "end_time": "19.80s",
      "label": "slide_abnormal",
      "subtags": ["dark_parcel", "lateral_drift", "edge_stuck"],
      "evidence": "19.40s包裹位于右格口右上侧靠近右边界；19.60s进一步贴右下滑至格口底部；19.80s从右格口右下角出画，整体轨迹偏向右格口右边缘，存在横向偏移",
      "confidence": 0.55,
      "suggestion_for_human": "review"
    }
  ],
  "miss_risk": "medium",
  "false_positive_risk": "medium"
}
```

## segment_b：20.4s - 22.2s

```json
{
  "segment_summary": "has_candidate_anomaly",
  "frame_notes": [
    {"time": "20.4s", "note": "中右小车可见深色包裹，橙色滑道空"},
    {"time": "20.6s", "note": "深色包裹仍在小车，滑道无包裹"},
    {"time": "20.8s", "note": "深色包裹随小车左移，滑道空"},
    {"time": "21.0s", "note": "深色包裹仍在小车，滑道空"},
    {"time": "21.2s", "note": "深色包裹持续在小车上移动"},
    {"time": "21.4s", "note": "包裹在小车中段，滑道仍空"},
    {"time": "21.6s", "note": "左侧格口机构打开，包裹未见下落"},
    {"time": "21.8s", "note": "左侧两格口打开，橙色滑道仍空"},
    {"time": "22.0s", "note": "左侧机构开合中，滑道无包裹"},
    {"time": "22.2s", "note": "机构复位，深色包裹仍在右侧小车"}
  ],
  "events": [
    {
      "start_time": "20.4s",
      "end_time": "21.4s",
      "label": "uncertain",
      "subtags": ["black_parcel", "cart_moving"],
      "evidence": "20.4s-21.4s 可见深色包裹随小车从右向左移动，途经多个格口，但均未释放至滑道；对应格口开合动作不明显",
      "confidence": 0.5,
      "suggestion_for_human": "review"
    },
    {
      "start_time": "21.6s",
      "end_time": "22.2s",
      "label": "open_no_drop",
      "subtags": ["black_parcel", "door_open_no_parcel"],
      "evidence": "21.6s-21.8s 左侧格口机构明显打开，但橙色滑道和袋口区域始终未出现下落包裹；22.0s-22.2s 机构复位，深色包裹仍在最右侧小车未释放",
      "confidence": 0.7,
      "suggestion_for_human": "review"
    }
  ],
  "miss_risk": "medium",
  "false_positive_risk": "medium"
}
```

## segment_c：23.0s - 25.0s

```json
{
  "segment_summary": "normal",
  "frame_notes": [
    {"time": "23.00s", "note": "顶部小车移动中，橙色滑道无包裹"},
    {"time": "23.20s", "note": "小车继续移动，滑道空"},
    {"time": "23.40s", "note": "小车移出中央位置，滑道无包裹"},
    {"time": "23.60s", "note": "顶部小车移过，滑道空"},
    {"time": "23.80s", "note": "小车移向左侧，滑道空"},
    {"time": "24.00s", "note": "左侧格口上部出现一小白色包裹"},
    {"time": "24.20s", "note": "小包裹开始沿左侧滑道下滑"},
    {"time": "24.40s", "note": "白色包裹在左滑道中段下滑"},
    {"time": "24.60s", "note": "包裹接近左侧袋口，轨迹居中"},
    {"time": "24.80s", "note": "包裹进入左侧黄条纹集包袋"},
    {"time": "25.00s", "note": "包裹已落入袋中，滑道恢复空"}
  ],
  "events": [
    {
      "start_time": "24.00s",
      "end_time": "24.80s",
      "label": "normal",
      "subtags": ["white_parcel", "lateral_drift"],
      "evidence": "24.00s左侧格口上部出现白色小包裹，24.20s-24.60s沿左滑道居中下滑，24.80s进入对应黄条纹袋口，轨迹居中无横向偏移",
      "confidence": 0.82,
      "suggestion_for_human": "accept"
    }
  ],
  "miss_risk": "low",
  "false_positive_risk": "low"
}
```
