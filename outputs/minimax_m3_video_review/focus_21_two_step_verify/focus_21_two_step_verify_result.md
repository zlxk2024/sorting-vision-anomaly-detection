# MiniMax-M3 21秒两步法核验

```json
{
  "frame_counts": [
    {"time": "20.6s", "parcel_count": 2, "parcel_positions": "parcel_A在左中位小车，parcel_B在右位小车"},
    {"time": "20.8s", "parcel_count": 2, "parcel_positions": "parcel_A左中，parcel_B右"},
    {"time": "21.0s", "parcel_count": 2, "parcel_positions": "parcel_A中左，parcel_B右"},
    {"time": "21.2s", "parcel_count": 2, "parcel_positions": "parcel_A中，parcel_B右"},
    {"time": "21.4s", "parcel_count": 2, "parcel_positions": "parcel_A中，parcel_B右"},
    {"time": "21.6s", "parcel_count": 2, "parcel_positions": "parcel_A中右，parcel_B右"},
    {"time": "21.8s", "parcel_count": 1, "parcel_positions": "parcel_B在右位小车，左侧小车已开门但内部空"},
    {"time": "22.0s", "parcel_count": 1, "parcel_positions": "parcel_B在右位小车，左两辆小车已开门且空"},
    {"time": "22.2s", "parcel_count": 1, "parcel_positions": "parcel_B仍在右位小车未开门"}
  ],
  "parcel_tracks": [
    {
      "parcel_id": "parcel_A",
      "visible_times": ["20.6s", "20.8s", "21.0s", "21.2s", "21.4s", "21.6s"],
      "track_summary": "随小车向右移动，约21.6-21.8s小车开门后落袋/滑道，敞口内未见残留",
      "drop_status": "dropped"
    },
    {
      "parcel_id": "parcel_B",
      "visible_times": ["20.6s", "20.8s", "21.0s", "21.2s", "21.4s", "21.6s", "21.8s", "22.0s", "22.2s"],
      "track_summary": "随小车向右移动，到22.2s仍在最右侧未开门的小车上",
      "drop_status": "moved_with_cart"
    }
  ],
  "two_parcels_visible": true,
  "open_no_drop_verdict": "no",
  "confidence": 0.82,
  "key_frames": ["21.6s", "21.8s", "22.0s", "22.2s"],
  "evidence": "parcel_A所在小车在21.8s开门后敞口内无可见包裹，判定已正常下落；parcel_B始终随小车移动，所在小车至22.2s未开门，不构成开门未落。",
  "human_action": "accept"
}
```
