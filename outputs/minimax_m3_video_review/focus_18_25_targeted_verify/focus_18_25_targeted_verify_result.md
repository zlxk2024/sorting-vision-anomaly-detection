# MiniMax-M3 目标异常核验版（不自由分类 + 全路径ROI + 0.2秒）

## verify_18_open_no_drop：17.8s - 18.8s，target=open_no_drop

```json
{
  "target_label": "open_no_drop",
  "verdict": "yes",
  "confidence": 0.75,
  "key_frames": ["17.80s", "18.20s", "18.60s"],
  "evidence": "灰色包裹位于左侧小车/格口上方，机构已开但连续多帧未下落，滑道无包裹通过。",
  "other_possible_label": "none",
  "human_action": "review"
}
```

## verify_19_20_slide_abnormal：18.8s - 20.2s，target=slide_abnormal

```json
{
  "target_label": "slide_abnormal",
  "verdict": "yes",
  "confidence": 0.6,
  "key_frames": ["19.40s", "19.60s", "19.80s"],
  "evidence": "包裹从格口释放后滑上橙色滑道，轨迹明显偏向右侧边缘并贴边滑行，未居中下落",
  "other_possible_label": "wrong_chute",
  "human_action": "review"
}
```

## verify_21_open_no_drop_multi_visible：20.6s - 21.8s，target=open_no_drop

```json
{
  "target_label": "open_no_drop",
  "verdict": "no",
  "confidence": 0.82,
  "key_frames": ["20.60s", "20.80s", "21.20s"],
  "evidence": "小车在输送线上正常移动，机构未处于打开/释放状态，包裹随小车正常前行，未见卡在开口不下落",
  "other_possible_label": "normal",
  "human_action": "accept"
}
```

## verify_23_25_normal_guard：23.0s - 25.0s，target=open_no_drop_or_slide_abnormal

```json
{
  "target_label": "open_no_drop_or_slide_abnormal",
  "verdict": "no",
  "confidence": 0.95,
  "key_frames": ["24.0s", "24.4s", "24.6s", "24.8s"],
  "evidence": "包裹24.0s释放，24.2s-24.6s沿左侧格口斜面正中正常下滑，24.8s入袋，无卡阻或偏移。",
  "other_possible_label": "normal",
  "human_action": "accept"
}
```
