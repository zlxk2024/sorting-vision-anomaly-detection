# 分拣视频分析 HTTP API

启动：`python -m sorting_vision.api --port 8080 --data-dir runs/api`。
默认 CPU、V2 PT 权重、V1 规则。模型读取失败或 LFS 文件不完整时启动会失败。

## 提交视频

`POST /v1/analyze-video`，请求体为视频原始二进制，**不是 multipart/form-data**。

- `Content-Length`：必填；普通 curl/requests 发送文件时会自动设置。
- `X-Filename`：提供 `.mp4`、`.avi`、`.mov` 或 `.mkv` 后缀；默认 video.mp4。服务端不会使用调用者提供的路径。
- `Content-Type: application/octet-stream`。
- `Authorization: Bearer <key>`：服务配置 SORTING_API_KEY 时必填；任务读取和文件下载也需要相同鉴权。

上传及推理同步执行，返回示例（帧数、事件和 ID 仅作结构说明）：

```json
{
  "status": "completed",
  "model_version": "YOLO11n-V2",
  "rule_version": "v1",
  "frame_count": 60,
  "event_count": 0,
  "events": [],
  "job_id": "0123456789abcdef0123456789abcdef",
  "artifacts": {
    "events": "/v1/jobs/0123456789abcdef0123456789abcdef/artifacts/events",
    "events_csv": "/v1/jobs/0123456789abcdef0123456789abcdef/artifacts/events_csv",
    "detections": "/v1/jobs/0123456789abcdef0123456789abcdef/artifacts/detections",
    "video": "/v1/jobs/0123456789abcdef0123456789abcdef/artifacts/video"
  }
}
```

events 中每个元素包含 `type`、`name`、`start_frame`、`end_frame`、`start_seconds`、`end_seconds`、`confidence`、`track_ids`、`evidence`。confidence 为规则计算值，不是经概率校准的事件正确率。

Python 调用示例（需要安装 requests）：

```python
import os
from pathlib import Path
import requests

base = 'http://127.0.0.1:8080'
video = Path('/path/to/input.mp4')
headers = {'X-Filename': video.name, 'Content-Type': 'application/octet-stream'}
if os.environ.get('SORTING_API_KEY'):
    headers['Authorization'] = 'Bearer ' + os.environ['SORTING_API_KEY']
with video.open('rb') as stream:
    response = requests.post(base + '/v1/analyze-video', data=stream,
                             headers=headers, timeout=(10, 1900))
response.raise_for_status()
result = response.json()
print(result['events'])
with requests.get(base + result['artifacts']['video'], headers=headers,
                  stream=True, timeout=(10, 120)) as response:
    response.raise_for_status()
    with Path('result.mp4').open('wb') as target:
        for chunk in response.iter_content(1024 * 1024):
            target.write(chunk)
```

## 任务和文件

`GET /v1/jobs/{job_id}` 读取已完成结果。`GET /v1/jobs/{job_id}/artifacts/{name}` 下载四类允许的产物。
服务重启后，保留 data-dir 即可继续读取完成结果；不提供失败任务重试或运行中进度。输出、原始上传视频及推理日志保存在 data-dir，按现场留存规则定期清理；API 不暴露原始上传视频和推理日志。

## 错误码

| HTTP 状态 | 含义 |
|---|---|
| 400 | 空请求、无效长度、分块传输或上传不完整 |
| 401 | 缺少或错误的 API 密钥 |
| 404 | 路径、任务或下载产物不存在 |
| 408 | 上传读取超时 |
| 413 | 超过上传字节限制 |
| 415 | 视频扩展名不支持 |
| 429 | 当前正在处理其他视频，稍后重试 |
| 500 | 解码或模型推理失败，凭 job_id 检查服务端 inference.log |
| 504 | 推理超过配置时间，子进程已终止 |

解码失败的无效视频可能返回 500；扩展名通过不代表视频编码有效。服务不会主动下载视频 URL，只处理调用者上传的数据。

## 部署约束

每个服务实例只运行一个推理子进程，避免旧脚本全局变量跨任务混用。长视频会积累逐帧结果，按视频时长/分辨率评估内存和磁盘容量。反向代理的上传上限和超时需与本服务一致。需要持续视频流、任务队列、多路并发或高可用时，应另行增加对应服务能力。
