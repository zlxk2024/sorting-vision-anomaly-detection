# 工控机摄像头实时检测与结果入库

本服务持续读取摄像头，逐帧运行 YOLO11n V2 和 ByteTrack，通过带持续时间的规则输出异常候选，再将事件和摄像头状态写入 SQL 数据库。模型输入是一张张 RGB 图像；视频采集、跟踪、异常规则、入库由服务负责。离线上传视频接口仍使用 8080；实时服务独立使用 8081。

## 1. 业务方需要提供什么

| 信息 | 配置位置 | 对接要求 |
|---|---|---|
| 摄像头 RTSP 地址、账号密码、码流/分辨率 | `.env` 的 `SORTING_CAMERA_1_URL` | 工控机能访问；优先固定机位、固定焦距、TCP RTSP |
| 数据库类型、地址、端口、库名、账号、密码、TLS 要求 | `.env` 的 `SORTING_DATABASE_URL` | PostgreSQL 或 MySQL；账号具有目标表读写权限 |
| 现场抽屉、闸口的位置 | YAML 的 `cameras[].regions` | 根据实际画面标定，示例坐标不能直接用于验收 |
| 滞留/多件/落格错误的确认时长、移动距离容差 | YAML 的 `rules` | 与业务人员看正常/异常样本后确定 |
| 抽屉应投闸口的固定关系（如有） | 抽屉 ROI 的 `expected_chute_id` | 动态目标需后续对接 PLC/WCS 任务，不能用固定配置代替 |
| 工控机 CPU/GPU、操作系统、相机数量、验收样本 | 部署与验收记录 | 先接一路，再按现场速度评估算力和漏检 |

无需修改源码即可替换连接信息。当前实现面向普通 RGB/RTSP 摄像头；厂商 SDK、深度相机、NPU/RKNN 不在本入口中。

## 2. 克隆、配置和启动

```bash
git lfs install
git clone https://github.com/zlxk2024/sorting-vision-anomaly-detection.git
cd sorting-vision-anomaly-detection
git lfs pull --include='models/*'
python3 scripts/verify_project.py
cp .env.example .env
chmod 600 .env
```

编辑 `.env`，填真实连接信息和一个足够长的随机 `SORTING_API_KEY`。不要提交该文件。连接串示例：

```dotenv
SORTING_CAMERA_1_URL=rtsp://user:password@camera-host:554/path
SORTING_DATABASE_URL=postgresql+psycopg://user:password@database-host:5432/sorting
# 或 mysql+pymysql://user:password@database-host:3306/sorting?charset=utf8mb4
SORTING_API_KEY=replace-with-a-long-random-value
SORTING_STORAGE_DIR=/work/realtime
```

密码包含 `@`、`:`、`/`、`#` 等保留字符时，按 URL 百分号编码；`.env` 中含 `$` 时使用单引号避免 Compose 插值。数据库服务须先创建好库和账号。容器内的 `localhost` 表示容器自身，填写可从容器访问的地址。按现场要求配置数据库 TLS；本仓库不提供真实账号。

编辑 `config/realtime.example.yaml`：

- `site_id` 和摄像头 `id` 使用 1–64 位字母、数字、下划线或短横线，稳定且唯一。
- ROI `box` 为 `[左, 上, 右, 下]`，所有坐标除以画面宽高归一化至 0–1。用轨迹中心归属 ROI，重叠时取面积最小的区域。
- 在抽屉区域可加 `expected_chute_id: chute-01`。无目标时只能给出跨闸口视觉候选。
- 默认 CPU，`image_size: 320`。NVIDIA 使用前先配置匹配的 CUDA/PyTorch 镜像，再设 `device: '0'`；本 Dockerfile 是 CPU 镜像。
- 增加摄像头条目时分别配置 `source_env`，并在 `.env` 增加对应变量。每路保留独立跟踪状态，模型推理串行，实际总吞吐必须实测。

```bash
docker compose -f compose.realtime.yaml build
docker compose -f compose.realtime.yaml run --rm sorting-realtime \
  python -m sorting_vision.realtime --config /app/config/realtime.example.yaml --check-config
docker compose -f compose.realtime.yaml up -d
# 查看状态；日志只输出错误类型，不输出摄像头或数据库密码
docker compose -f compose.realtime.yaml ps
docker compose -f compose.realtime.yaml logs --tail=100
```

默认服务启动时自动创建缺失表，不修改已有表。若 DBA 不允许运行账号建表，先由有权限的账号通过同一配置执行 `--init-db`，再将 YAML 的 `database.create_tables` 设为 `false`。已有表的结构变更需 DBA 单独迁移；`create_all` 不是迁移工具。

MySQL 运行账号只有 SELECT/INSERT/UPDATE/DELETE 权限时，由 DBA 在目标业务库执行 [deploy/mysql/schema.sql](../deploy/mysql/schema.sql)，然后设置 `database.create_tables: false`。运行账号不能替 DBA 执行 `--init-db`。该 SQL 不含服务器地址、账号或密码；未对任何实际业务库自动执行。

Python 部署：按 README 创建 Python 3.11 环境并 `pip install -e .`，从安全方式设置环境变量后执行：

```bash
python -m sorting_vision.realtime --config config/realtime.example.yaml
```

Python 进程默认不加载 `.env`；可显式添加 `--env-file .env`，Compose 会通过 `env_file` 加载。裸机部署须用 systemd `EnvironmentFile` 或环境变量注入，设置 storage 为裸机可写路径。设备输入 `0` 可用 OpenCV 默认摄像头；Docker USB 需要另外映射设备，当前验证覆盖 RTSP。

## 3. 异常规则与判断边界

所有条件必须在连续观测中持续达到阈值，使用单调时钟的实际秒数，不把“帧数”当作秒数。默认最小置信度 0.35，移动容差是归一化画面对角坐标中的欧氏距离 0.025；需现场标定。

当前业务统一为三类；“飘格”是“落格错误”的旧称，不另设第四类。`rules.enabled_event_types` 可从下列三种 ID 中选择，默认全部启用。“不掉件”退出默认检测类型；历史记录不删除、不改写。

| event_type | event_type_name（中文业务名称） | 条件 | 默认持续时间 |
|---|---|---|---|
| `wrong_chute` | 落格错误 | 进入与配置目标不同的闸口；无目标时只检查同一轨迹跨闸口 | 0.15 秒 |
| `multi_parcel_drawer` | 一车两件/多件混放 | 同一抽屉 ROI 中存在至少两个去重后的包裹轨迹 | 0.25 秒 |
| `chute_stall` | 格口包裹滞留 | 同一包裹轨迹在同一闸口 ROI 中保持静止 | 1.2 秒 |

实时输出使用 `rule_version: live-v2`，新增 `event_type_name` 到 JSON payload，英文 ID 保持兼容。离线 JSON/CSV 的 `name` 同步使用新中文名称，默认同样仅输出三类；模型的五个实体类别和权重不变。旧验证报告中的四类描述是当时的规则版本。

事件先 `open`，持续时更新同一 `event_id`；条件解除 0.4 秒后 `closed`，移动立即结束静止事件。`start_at`/`end_at` 为实际异常观测的起止 UTC 时间，`duration_seconds` 为观测持续时长，`closed_at` 为确认结束/中断时间。断流、间隔超过 2 秒、会话变化、重启将旧事件标记 `interrupted`，并重置跟踪与规则，不跨断流累计时长。

`review_status` 当前固定为 `pending`，这些是视觉异常候选。模型检测包裹/开抽屉/闭抽屉/闸口/袋，不直接识别业务正确性；遮挡、跟踪 ID 断裂、相机位移、反光和画面冻结都可能造成漏检或误报。`wrong_chute` 的 `judgement_basis` 区分配置目标与无目标视觉候选；尚未接 PLC/WCS 动态任务，不承诺最终错分判断。人工复核/确认接口不在本次范围内。

## 4. 数据表与持久化

支持 PostgreSQL（psycopg）、MySQL（PyMySQL）和 SQLite（本地演示）。SQLite 示例：`sqlite:////work/realtime/results.sqlite3`。

- `sorting_events`：`event_id` 主键；`site_id`、`camera_id`、`event_type`、`status`、起止时间、持续时间、复核状态、截图路径、片段路径；`payload` JSON 保存完整置信度、轨迹 ID、抽屉/实际/预期闸口、规则/模型版本、依据和证据状态。
- `sorting_camera_status`：`site_id + camera_id` 联合主键；状态、UTC 心跳、JSON 指标（采集/处理/覆盖丢帧数、重连次数、处理 FPS、最近推理耗时）。
- `runs/realtime/outbox.sqlite3`：本地持久化投递队列。SQL 提交成功才确认；相同事件更新同一行。数据库中断后本地继续检测，指数退避重试，恢复后补写；重启恢复队列，并中断遗留 open 事件。

队列保留每个事件的最新状态和每路最新心跳，不是逐帧明细或每秒更新历史。主键和版本确认可避免重试产生重复事件、旧确认删掉新更新。同一路摄像头只运行一个实例；同一站点的摄像头不能被两个进程同时接管，否则启动恢复会中断对方事件。每个实例使用独立 storage，不能并发共享 outbox。

数据目录通过卷持久化，备份/恢复时停服务后复制整个目录（含 SQLite WAL 文件及 evidence）。数据库故障下不删除队列。磁盘损坏或耗尽不能保证持久化；观察 pending 数量并规划容量。

## 5. API 调用

Compose 默认只绑定工控机 `127.0.0.1:8081`，通过同机业务程序或反向代理访问。若需远程访问，配置可信网段、防火墙和 HTTPS 代理后再修改端口绑定。API key 非空时，除 `/health` 外均要求 `Authorization: Bearer <key>`。

```bash
curl --fail http://127.0.0.1:8081/health
curl --fail -H "Authorization: Bearer $SORTING_API_KEY" http://127.0.0.1:8081/ready
curl --fail -H "Authorization: Bearer $SORTING_API_KEY" http://127.0.0.1:8081/v1/cameras
curl --fail -H "Authorization: Bearer $SORTING_API_KEY" \
 'http://127.0.0.1:8081/v1/events?camera_id=camera-01&limit=50'
```

| 接口 | 返回 |
|---|---|
| `GET /health` | 进程存活返回 200；必须检查 `ready`，200 不代表检测可用 |
| `GET /ready` | 所有启用摄像头在线且近期处理、投递线程存活且数据库写入正常时 200，否则 503；含详细指标 |
| `GET /v1/cameras` | 摄像头状态，始终不返回连接串 |
| `GET /v1/events` | 当前站点最近候选，支持 `camera_id`、`limit`（1–200） |
| `GET /v1/events/{event_id}` | 当前站点单条完整 JSON |
| `GET /v1/events/{event_id}/snapshot` | JPEG 证据 |
| `GET /v1/events/{event_id}/clip` | MP4 证据；尚未完成/不可用返回 404 |

数据库不可用时事件查询返回 503；就绪状态将降级，进程继续工作。HTTP 就绪和健康并不代表异常业务准确率已通过验收。

## 6. 帧处理、证据和运维

采集线程仅保留最新一帧；推理慢时覆盖旧帧、计数 `frames_dropped`，不无限堆积。取帧及推理后均检查帧龄，超时丢弃。帧龄从本机解码后计时，不能测量相机端或网络内部积压；建议相机低延迟子码流、关键帧间隔约 1 秒（须小于读超时），现场核对画面延迟。建立 RTSP 连接后收到新鲜画面才算在线；等待关键帧时保持 connecting。CPU 速度不足时短暂动作可能漏掉，必须按输送速度实测，不能按摄像头标称 25/30 FPS 推断处理 FPS。

默认保存触发截图及触发前后各约 2 秒的短片；前段受服务已运行时长、处理 FPS 和 90 帧上限影响。每路最多 4 个同时录制片段，超过只存截图；低于 256 MB 可用空间时标记 `evidence_failed`。视频采用 mp4v，部分浏览器不直接播放，可下载后用播放器查看。片段编码失败不阻断事件入库，标记 `snapshot_only_clip_failed`。

证据文件与队列不自动过期删除。根据保留天数由运维安排归档，避免删除还在录制或等待入库的证据；数据库中路径需与归档策略对应。重启不会回填整段停机视频，连续检测从恢复后的最新帧开始。断流自动指数退避重连，默认 1–15 秒，读/开流超时各 5 秒。

部署验收顺序：现场一路实时图像 → 已知正常/异常样本复核 → 数据库事件与证据对照 → 断流/断库/重启恢复 → 目标工控机吞吐、延迟及至少一个完整班次稳定性。当前可复现验证见 [REALTIME_VERIFICATION.md](REALTIME_VERIFICATION.md)。

Windows 原生 GPU 部署与独立检查命令见 [WINDOWS_FIELD_GUIDE.md](WINDOWS_FIELD_GUIDE.md)。
