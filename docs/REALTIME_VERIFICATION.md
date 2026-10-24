# 实时检测验证记录（2026-10-24）

本次完成真实模型、真实 RTSP 协议、本地隔离 PostgreSQL 的端到端验证。测试未接业务方现场摄像头、数据库、PLC 或 WCS。

## 环境和输入

- Apple M1 / 8 GB；Docker Desktop Linux ARM64，分配 8 CPU / 约 3.827 GiB。
- 本仓库 CPU Dockerfile，YOLO11n V2 `.pt`，推理尺寸 320，ByteTrack。实际依赖快照见 [realtime-python-freeze-2026-10-24.txt](realtime-python-freeze-2026-10-24.txt)。
- FFmpeg 将一张真实分拣图像以 720×1280 / 10 FPS、H.264、1 秒关键帧间隔发布到临时 MediaMTX；服务通过 TCP RTSP 接入。
- 为验证事件通路，将整个画面设为一个闸口 ROI、规则置信度设为 0.2。固定画面中的包裹应触发 `chute_stall`。
- 这是受控静止场景；不作为真实产线异常准确率、漏检率或错分准确率证据。测试视频、图片、随机密码均未入 Git。

## 通过的验证

| 检查 | 结果 |
|---|---|
| Docker 实际构建、启动、加载 V2 模型 | 通过 |
| GitHub 全新克隆、LFS 拉取、Compose build/up | 提交 837b8f8，全新目录校验两个模型成功，ready=true，产生 2 个新事件并有片段 |
| RTSP 连续采集、ByteTrack、持续时间异常规则 | 产生滞留候选并写入 PostgreSQL |
| `/ready`、摄像头指标、带密钥事件查询 | 实际请求通过；未授权请求的拒绝由 API 回归测试覆盖 |
| 截图与片段下载 | JPEG 78,726 字节、MP4 196,512 字节；实际解码成功，33 帧、10 FPS、640×1138 |
| 停止 RTSP 发布再恢复 | 就绪降为 503，清理旧状态，收到新帧并恢复处理后 200 |
| 停止 PostgreSQL | 就绪 503，检测继续；故障窗口处理数从 196 增至 236，队列累积 5 条 |
| 断库期间强制杀死并重启服务，再启动 PostgreSQL | 从持久化 outbox 恢复，最终 pending=0、ready=true |
| 幂等与中断状态 | 测试库累计 10 条、10 个不同事件 ID；旧 open 变为 interrupted；恢复后没有重试重复行 |
| PostgreSQL 重复投递、更新、中文 JSON、跨站点同摄像头 ID | 实际数据库检查通过 |
| SQLite 故障队列、版本确认竞争、重启、规则、API 等 | 32 项 unittest 通过，包含原离线 API 回归 |
| 源码语法和两个模型 SHA256 | `scripts/verify_project.py` 通过，模型未变更 |

测试时发现长关键帧间隔会影响断流后解码，已在部署文档说明低延迟码流建议，并修复“连接建立即在线”的状态判断：等待首帧为 connecting，采集画面过期也会降级。新增对应回归测试。

## 性能

20 秒连续统计窗口约 **8.54 分析 FPS**，输入 10 FPS。推理耗时的单次快照约 0.1 秒；这不是 P95 延迟统计。处理慢时保留最新帧并覆盖旧帧，因此不会按原输入帧率逐帧分析。

该数字仅表示本机、该分辨率/尺寸、该静止受控输入和当时系统负载下的短时吞吐。不能作为 x86 工控机或 NVIDIA GPU 的结果，不代表完整班次稳定性，不证明快速运动包裹不会漏检。现场需重新测端到端延迟、吞吐和事件召回。

## 数据库兼容性边界

PostgreSQL 16 与 SQLite 已实际测试。MySQL 使用 SQLAlchemy + PyMySQL，提供配置和通用幂等写入实现；本机对官方 MySQL 8.4 ARM64 和 8.0 Debian AMD64 镜像重试拉取均遇到 TLS 传输错误，未能启动 MySQL 实例。因此 MySQL 驱动已实现，但真实 MySQL 写入尚未验证，不能将 PostgreSQL 的通过结果当作 MySQL 的通过结果。现场数据库权限、TLS、网络、版本和现有表结构仍需联调。

## 复核和复现

技术指标与各故障阶段状态见 [REALTIME_VERIFICATION_2026-10-24.json](REALTIME_VERIFICATION_2026-10-24.json)。累计测试库包含前序调试事件，因此事件条数只用于核对唯一 ID，不是准确率样本数。

1. 从 GitHub 克隆并拉取 LFS，运行源码/哈希检查。
2. 安装 `requirements-realtime.txt` 和 PyYAML 后运行 `python -m unittest discover -s tests -v`；完整推理用 README/Docker 环境。
3. 用自有合规样本通过 FFmpeg 发布 RTSP，设置 `-g 10 -keyint_min 10`、10 FPS；可使用 [MediaMTX 官方配置](https://raw.githubusercontent.com/bluenviron/mediamtx/main/mediamtx.yml) 启动隔离 RTSP 服务。
4. 按 REALTIME.md 配置隔离 PostgreSQL 和摄像头地址；受控静止测试可将 chute ROI 设为全画面。启动 Compose 后查询 `/ready`、事件及证据；该 ROI 不用于现场部署。
5. 依次停止/恢复 RTSP 发布、停止数据库、确认 pending 增长、强制重启服务、恢复数据库，检查队列清零、遗留事件中断且主键无重复。
6. 现场验收另行使用校准 ROI、真实正常/异常样本以及目标工控机长时间运行。
