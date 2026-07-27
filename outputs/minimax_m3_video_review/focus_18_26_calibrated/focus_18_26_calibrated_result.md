# MiniMax-M3 校准版标注复核（ROI + 0.2秒 + 人工规则）

## case_18_white_open_no_drop：17.8s - 18.8s

```json
{
  "segment_label": "open_no_drop",
  "frame_notes": [
    {"time": "17.80s", "note": "左侧斜面有白色包裹，中间格口开始动作"},
    {"time": "18.00s", "note": "中间格口已打开，白色包裹仍停留在格口区域"},
    {"time": "18.20s", "note": "格口完全打开，白色包裹在已开格口处滞留"},
    {"time": "18.40s", "note": "白色/浅灰包裹位于已开抽屉上方，未下落"},
    {"time": "18.60s", "note": "包裹仍卡在已开格口区域，未见下落"},
    {"time": "18.80s", "note": "包裹持续滞留，连续多帧未见滑落"}
  ],
  "events": [
    {
      "start_time": "18.0s",
      "end_time": "18.8s",
      "label": "open_no_drop",
      "subtags": ["white_parcel"],
      "evidence": "18.0s-18.8s 中间格口已打开，白色包裹持续停留在已开格口区域，连续多帧未见下滑落入下层",
      "confidence": 0.92
    }
  ],
  "annotation_suggestion": "accept",
  "reason_for_human": "符合人工校准样例1：18秒附近白色快递停在已开抽屉/格口区域没有及时滑落，open_no_drop判定依据充分。"
}
```

## case_19_20_black_slide_abnormal：18.8s - 20.2s

```json
{
  "segment_label": "slide_abnormal",
  "frame_notes": [
    {"time": "18.80s", "note": "黑色包裹位于中间格口斜面顶部，姿态正常"},
    {"time": "19.00s", "note": "黑色包裹开始下滑，位于斜面中段"},
    {"time": "19.20s", "note": "黑色包裹继续下滑，位置略偏右"},
    {"time": "19.40s", "note": "黑色包裹明显滑歪，已偏离到斜面最右侧边缘"},
    {"time": "19.60s", "note": "黑色包裹落到右侧格口边缘/下沿，落点异常"},
    {"time": "19.80s", "note": "黑色包裹已从右下滑出ROI范围"},
    {"time": "20.00s", "note": "斜面区域空，黑色包裹已离开画面"},
    {"time": "20.20s", "note": "格口区域无包裹残留"}
  ],
  "events": [
    {
      "start_time": "18.8s",
      "end_time": "20.0s",
      "label": "slide_abnormal",
      "subtags": ["black_parcel", "lateral_drift", "off_path_drop"],
      "evidence": "19.20s-19.60s 包裹从中间斜面持续向右偏移，19.40s已滑到斜面最右沿，19.60s从右侧格口边缘异常落出，落点明显偏离正常格口中心",
      "confidence": 0.95
    }
  ],
  "annotation_suggestion": "accept",
  "reason_for_human": "符合人工校准样例#2：19-20秒附近黑色快递滑歪，斜面下滑过程中明显横向偏移至右侧边缘并异常落出，slide_abnormal标签成立。"
}
```

## case_21_two_parcels_open_no_drop：20.6s - 21.6s

```json
{
  "segment_label": "open_no_drop",
  "frame_notes": [
    {"time": "20.60s", "note": "左侧白色快递停留在已开抽屉区域，右侧黑色快递在相邻小车（关闭状态），两件包裹同框"},
    {"time": "20.80s", "note": "白色快递仍在已开抽屉开口处未下落，黑色快递位置未变"},
    {"time": "21.00s", "note": "白色快递持续滞留于开口区域，黑色快递仍在右侧小车上"},
    {"time": "21.20s", "note": "白色快递仍未滑落，滞留连续多帧"},
    {"time": "21.40s", "note": "白色快递仍停留在开口斜面，未下落"},
    {"time": "21.60s", "note": "白色快递位置基本不变，仍未落格"}
  ],
  "events": [
    {
      "start_time": "20.6s",
      "end_time": "21.6s",
      "label": "open_no_drop",
      "subtags": ["white_parcel", "two_parcels_visible"],
      "evidence": "20.6s-21.6s连续多帧画面中可见两个包裹：左侧白色件停留在已开抽屉开口处未下落，右侧黑色件在相邻小车上，符合人工校准样例3",
      "confidence": 0.92
    }
  ],
  "annotation_suggestion": "accept",
  "reason_for_human": "符合人工校准样例3：21秒附近画面有两个快递，白色件在已开抽屉区域连续多帧滞留未下落，建议标注open_no_drop并备注two_parcels_visible。"
}
```

## case_23_25_no_target_anomaly：23.0s - 25.0s

```json
{
  "segment_label": "normal",
  "frame_notes": [
    {"time": "23.00s", "note": "分拣小车正常移动，格口未开门，无滞留"},
    {"time": "23.40s", "note": "小车继续通过，无明显异常"},
    {"time": "23.80s", "note": "左侧格口区域可见白色件开始出现在斜面上"},
    {"time": "24.00s", "note": "左侧白色件沿斜面正常下滑，未见滞留"},
    {"time": "24.20s", "note": "白色件继续在左侧斜面下滑，轨迹正常"},
    {"time": "24.40s", "note": "白色件滑至橙色斜面中段，滑动正常"},
    {"time": "24.60s", "note": "白色件接近斜面底部，滑动正常"},
    {"time": "24.80s", "note": "白色件已滑出画面，无异常"},
    {"time": "25.00s", "note": "小车继续正常通过，无滞留"}
  ],
  "events": [
    {
      "start_time": "23.8s",
      "end_time": "24.6s",
      "label": "normal",
      "subtags": ["white_parcel", "left_chute"],
      "evidence": "24.00s-24.40s左侧白色件沿斜面正常下滑，轨迹居中无偏移；未在任何格口开口区域出现滞留",
      "confidence": 0.95
    }
  ],
  "annotation_suggestion": "accept",
  "reason_for_human": "符合人工校准样例4：23-25秒期间未观察到目标包裹在已开格口滞留，左侧白色件沿斜面正常下滑，不应误判为open_no_drop或slide_abnormal。"
}
```
