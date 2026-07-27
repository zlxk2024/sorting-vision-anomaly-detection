# MiniMax-M3 区域参考线版预标注（红/蓝/绿ROI + 0.2秒）

## segment_a：17.8s - 20.2s

```json
```json
{
  "segment_summary": "normal",
  "frame_notes": [
    {"time": "17.8s", "note": "黑色/深灰包裹位于左侧小车，在红框释放区"},
    {"time": "18.0s", "note": "黑色包裹仍在左侧小车上,小车向中右方向移动"},
    {"time": "18.2s", "note": "小车继续右移,黑色包裹可见"},
    {"time": "18.4s", "note": "小车继续右移"},
    {"time": "18.6s", "note": "小车接近中间,可见深色包裹在其上"},
    {"time": "18.8s", "note": "小车继续向右侧格口移动"},
    {"time": "19.0s", "note": "小车到达右侧格口位置,黑色包裹在小车上即将释放"},
    {"
```

## segment_b：20.4s - 22.2s

```json
```json
{
  "segment_summary": "normal",
  "frame_notes": [
    {"time": "20.40s", "note": "黑色包裹位于中间格口小车表面（红框内），格口门关闭"},
    {"time": "20.60s", "note": "黑色包裹仍在小车上（红框），准备释放"},
    {"time": "20.80s", "note": "格口门开始打开，黑色包裹到达开口处（红蓝交界）"},
    {"time": "21.00s", "note": "格口门打开，黑色包裹已从红框区域释放"},
    {"time": "21.20s", "note": "黑色包裹进入蓝框滑道顶部，开始下滑"},
    {"time": "21.40s", "note": "黑色包裹在蓝框滑道上居中下滑，轨迹正常"},
    {"time": "21.60s", "note": "黑色包裹继续沿中间格口滑道下滑，靠近绿框"},
    {"time": "21.80s", "note": "黑色包裹到达绿框袋口上方，即将落入中间袋口"},
    {"time": "22.00s", "note": "黑色包裹已落入中间格口对应绿框袋口，滑道已清空"},
    {"time": "22.20s", "note": "滑道保持空载，中间袋口收包完成"}
  ],
  "events": [
    {
      "start_time": "20.40s",
      "end_time": "22.00s",
      "label": "normal",
      "subtags": ["black_parcel", "red_zone_release", "blue_zone_drift", "green_zone_entry"],
      "evidence": "20.40-20.60s：黑色包裹在小车（红框）上滞留；20.80-21.00s：格口开门释放，包裹进入红蓝交界；21.20-21.60s：包裹沿中间格口蓝框滑道居中连续下滑；21.80-22.00s：包裹进入对应中间绿框袋口，未偏移到相邻袋口",
      "confidence": 0.93,
      "suggestion_for_human": "accept"
    }
  ],
  "miss_risk": "low",
  "false_positive_risk": "low"
}
```
```

## segment_c：23.0s - 25.0s

```json
```json
{
  "segment_summary": "normal",
  "frame_notes": [
    {"time": "23.00s", "note": "红框内小车/抽斗到位，机构闭合状态，未见包裹释放"},
    {"time": "23.20s", "note": "红框机构运动中，仍未见包裹"},
    {"time": "23.40s", "note": "红框内机构继续移动，蓝色滑道区域无包裹"},
    {"time": "23.60s", "note": "机构仍在红框内动作，无包裹进入蓝框"},
    {"time": "23.80s", "note": "红框机构开始张开，准备释放"},
    {"time": "24.00s", "note": "左侧蓝框上端出现浅色包裹，开始沿左侧滑道下滑"},
    {"time": "24.20s", "note": "白色包裹在左侧蓝框滑道中段下滑，轨迹基本居中"},
    {"time": "24.40s", "note": "包裹接近左侧蓝框底部，位置偏左但未跨格口边界"},
    {"time": "24.60s", "note": "包裹到达绿框区域上方，即将落入左侧袋口"},
    {"time": "24.80s", "note": "左侧绿框袋口内可见包裹落入"},
    {"time": "25.00s", "note": "包裹已落入左侧绿框袋口内，过程结束"}
  ],
  "events": [
    {
      "start_time": "23.80s",
      "end_time": "24.00s",
      "label": "normal",
      "subtags": ["white_parcel", "red_zone_release"],
      "evidence": "23.80s-24.00s 红框机构张开，24.00s 浅色包裹在左侧蓝框上端出现，开始正常释放下滑",
      "confidence": 0.90,
      "suggestion_for_human": "accept"
    },
    {
      "start_time": "24.00s",
      "end_time": "24.60s",
      "label": "normal",
      "subtags": ["white_parcel", "blue_zone_drift", "green_zone_entry"],
      "evidence": "24.00s-24.40s 包裹沿左侧蓝框滑道下滑，轨迹略偏左但未跨格口边界；24.60s 到达绿框区域并落入对应左侧袋口，与释放格口匹配",
      "confidence": 0.85,
      "suggestion_for_human": "accept"
    }
  ],
  "miss_risk": "low",
  "false_positive_risk": "low"
}
```
```
