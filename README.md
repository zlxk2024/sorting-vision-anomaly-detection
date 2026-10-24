# 快递分拣视频异常检测

输入 RGB 视频，使用 **YOLO11n V2 + ByteTrack + V1 时序规则**识别包裹、抽屉、闸口等对象，输出不掉件、飘格、一车两件、滞留的视觉异常候选。

本仓库提供离线视频分析、摄像头实时检测、异常候选入库和 HTTP 查询接口，包含 V2 `.pt`、`.onnx` 模型。当前为 PoC 版本；实体检测指标不能代替异常事件验收，Horus 相机接入仍是工程骨架。

实时接入：见 [摄像头与数据库部署文档](docs/REALTIME.md) 和 [实时链路验证记录](docs/REALTIME_VERIFICATION.md)。连接信息通过 `.env` 注入，支持 PostgreSQL/MySQL/SQLite；使用 `docker compose -f compose.realtime.yaml up -d --build` 启动前须先配置摄像头、数据库和现场 ROI。

## 1. 克隆并取得模型

仓库当前为私有，部署者需要仓库访问权限。先在本机安装 Git LFS，然后执行：

```bash
git lfs install
git clone https://github.com/zlxk2024/sorting-vision-anomaly-detection.git
cd sorting-vision-anomaly-detection
git lfs pull --include="models/*"
python3 scripts/verify_project.py
```

校验只依赖 Python 标准库；如果模型还是 LFS 指针文件，会明确提示重新下载。模型与哈希见 [models/manifest.json](models/manifest.json)。

## 2. Python 部署

推荐 Python 3.11，支持声明为 Python 3.10 及以上。CPU 环境示例：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e .
python scripts/verify_project.py
```

NVIDIA GPU 环境先自行安装匹配 CUDA 的 PyTorch/torchvision，再安装本项目；CLI/API 使用 `--device 0`。macOS 使用系统支持的 PyTorch 安装方式，不使用上面的 Linux CPU wheel 源即可。

### 命令行分析视频

视频由调用者提供，不需要训练数据：

```bash
python scripts/detect_sorting_events_v1.py \
  --video /path/to/input.mp4 \
  --output runs/my-video --device cpu
```

默认使用 `models/sorting_yolo11n_v2_mixed_best.pt`，规则版本为 V1。输出：

- `events_v1.json` / `events_v1.csv`：异常候选与开始/结束时间、轨迹 ID、证据。
- `detections_v1.json`：逐帧检测框、类别、置信度和轨迹 ID。
- `sorting_events_v1.mp4`：叠加检测框和异常提示的视频。

### 启动 HTTP 服务

```bash
python -m sorting_vision.api --host 127.0.0.1 --port 8080 --data-dir runs/api
```

提交视频，接口同步等待分析结束：

```bash
curl --fail --max-time 1900 \
  -H 'Content-Type: application/octet-stream' \
  -H 'X-Filename: input.mp4' \
  --data-binary @/path/to/input.mp4 \
  http://127.0.0.1:8080/v1/analyze-video
```

需要鉴权时，在启动服务前设置 `SORTING_API_KEY`，请求增加 `Authorization: Bearer <your-key>`。跨主机访问请使用 `--host 0.0.0.0`，配置该密钥并通过现有 HTTPS 网关暴露服务。默认 Compose 只发布到本机回环地址。

## 3. Docker 部署（CPU）

确认 `git lfs pull` 和模型校验通过后：

```bash
docker compose up -d --build
curl --fail http://127.0.0.1:8080/health
```

默认端口 8080，任务和输出保存在宿主机 `runs/api/`。如需鉴权，启动 Compose 前设置 `SORTING_API_KEY` 环境变量。镜像构建会校验模型，避免把 LFS 指针当成权重。

Dockerfile 安装 CPU 版 PyTorch；GPU 部署请按目标 CUDA 环境调整基础镜像和运行参数。Docker 构建首次需要联网下载依赖。

## 4. 调用接口

| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/health` | 健康检查，不要求密钥 |
| POST | `/v1/analyze-video` | 上传视频二进制并同步分析 |
| GET | `/v1/jobs/{job_id}` | 读取完成任务结果 |
| GET | `/v1/jobs/{job_id}/artifacts/{name}` | 下载 events、events_csv、detections 或 video |

详细请求、响应、错误码和 Python 调用示例见 [API.md](API.md)。一次最多分析一个视频；忙时返回 429，默认上传限制 256 MiB、推理超时 1,800 秒，均可通过启动参数调整。没有后台排队、自动重试或断点续传。

Python 本地调用：

```python
from pathlib import Path
from sorting_vision.inference import run_video

result = run_video(Path('/path/to/input.mp4'), Path('runs/python-call'))
print(result['events'])
```

## 5. 目录和训练边界

| 路径 | 内容 |
|---|---|
| `sorting_vision/` | 离线 HTTP、实时采集/规则、SQL 投递、证据和模型校验 |
| `scripts/` | 视频分析，以及历史数据准备、标注、训练、评估脚本 |
| `models/` | V2 权重、ONNX 和哈希清单 |
| `deploy/horus_rv1126b/` | ONNX/RKNN 转换、C++ 模拟状态机、相机接入说明 |
| `docs/` | 模型报告、标注规范、评估体系、部署验证记录 |
| `evaluation/` | 事件真值与验收结果模板 |
| `tests/` | 离线/实时 API、持续时间规则、采集队列和数据库投递测试 |

本次发布不包含现场视频、图片/标签、历史运行输出、报价、旧点云/机械臂代码或凭据。旧版内容保留在 Git 历史中，当前版本没有重写历史。

推理与 HTTP 调用不需要训练数据。**重新训练需要另行提供经复核的数据和 V1 初始化权重**；`train_sorting_yolo_v2.py` 沿用历史路径 `datasets/sorting_yolo_v2_mixed/data.yaml` 和 `runs/sorting_yolo/sorting_yolo11n_v1/weights/best.pt`。数据准备脚本是研发材料，不应直接对现有数据执行。早期三类与小样本标注脚本不是正式五类训练入口。

`.[annotation]`、`.[documents]`、`.[export]` 分别提供模型辅助预标注、Word 生成、ONNX 导出附加依赖；历史抽帧脚本需要系统 ffmpeg。模型辅助预标注会调用外部 API，只有显式运行并配置凭据时才使用。

## 6. 能力与验证

固定类别顺序：`0 parcel`、`1 drawer_open`、`2 drawer_closed`、`3 chute`、`4 bag`。V2 历史测试 mAP@0.5 为 0.894；新场景包裹 Precision 0.574、关闭抽屉 Recall 0.480，仍需优化。

离线入口先完成视频推理，再统一分析异常；新增实时入口持续读取 RTSP，使用按秒和归一化坐标的增量规则，经本地 outbox 写入数据库。当前已验证一路，多路吞吐和完整班次稳定性需在目标工控机验收。缺少 PLC/WCS 目标格口时，飘格仅是视觉候选。完整限制见 [KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)。

- [摄像头实时检测与入库验证](docs/REALTIME_VERIFICATION.md)
- [Docker 实际部署与性能报告](docs/DOCKER_PERFORMANCE_2026-10-22.md)
- [部署与真实模型验证](docs/DEPLOYMENT_VERIFICATION.md)
- [V2 训练与评估报告](docs/YOLO_V2_模型训练与评估报告_2026-07-29.md)
- [标注标准](docs/ANNOTATION_STANDARD_v1.md)
- [评估体系](docs/快递分拣视觉模型与异常检测系统评估体系_V1.0.md)
- [模型信息与使用许可说明](models/README.md)

安装项目依赖后运行测试：`python -m unittest discover -s tests -v`。第三方依赖和模型沿用各自许可，本次未将项目声明为自由使用的开源授权。
