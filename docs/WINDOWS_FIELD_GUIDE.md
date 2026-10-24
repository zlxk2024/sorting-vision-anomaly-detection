# Windows 工控机现场部署与分阶段测试

适用：现场 Windows 工控机、NVIDIA RTX 3060 12GB；Mac 通过远程桌面操作。程序、GPU 推理、相机连接和本地证据均运行在工控机，远程桌面只传输操作画面。硬件配置可用于部署测试，实际速度、路数和事件准确率必须在现场测量。

## 1. ToDesk 和 Windows App 选择

| 项目 | ToDesk | Windows App（微软 RDP 客户端） |
|---|---|---|
| 首次异地协助 | 双方安装客户端，按设备码和连接密码操作 | 工控机需启用远程桌面，账号有登录权限 |
| 网络条件 | 两端能访问 ToDesk 服务，现场允许使用 | Mac 能访问工控机网络，例如现场同网段、VPN 或 RD Gateway |
| Windows 条件 | 安装对应 Windows 客户端 | 工控机系统须支持作为 RDP 被控端，家庭版不能作为该被控端 |
| 现场共同观察 | 适合与现场人员一起观察当前桌面 | 会话/锁屏行为与 Windows 配置有关，操作前与现场协调 |
| 本次建议 | 首次安装、摄像头联调优先使用；已有公司指定工具则用现有工具 | 网络和远程桌面已经配好的情况下使用 |

参考：[ToDesk 官方连接说明](https://www.todesk.com/helpcenter/solo-290.html)、[微软远程桌面要求](https://support.microsoft.com/en-us/windows/experience/connectivity-networking/how-to-use-remote-desktop)。远程桌面能连接工控机，不等于 Mac 可以直接访问摄像头；下列操作全部在远程的 Windows 桌面执行。

## 2. 现场先准备

- 工控机实际 Windows 版本、Python 3.11 64 位、Git 和 Git LFS。
- 能从工控机访问 GitHub、Python 包源；私有仓库由有权限的账号登录。无法联网时需另行准备匹配 Windows 的离线依赖包，不能复制 Mac 虚拟环境。
- 摄像头当前 IP、实际 RTSP 路径和摄像头账号密码；工控机网络能访问相机。厂家给过 `/stream1` 和 `/Stream1` 两种写法，以测试通过的为准；子码流同理。
- MySQL 地址、库名、运行账号和密码；工控机网络能访问该数据库。Mac 的数据库连通结果不能代替工控机连通结果。
- DBA 在目标库执行 [deploy/mysql/schema.sql](../deploy/mysql/schema.sql)。当前运行账号如只有增删改查权限，不执行 `--init-db`。
- 用实际画面确认抽屉、格口区域及编号、业务阈值；需要判断真实落格错误时提供预期目标格口。

打开 Windows PowerShell，先运行：

```powershell
nvidia-smi
py -0p
git --version
git lfs version
```

`nvidia-smi` 应显示实际 RTX 3060、驱动及显存信息。没有识别显卡时先由现场管理员处理驱动。安装 CUDA 版 PyTorch 后，还要检查 PyTorch 是否真正能使用 GPU。

## 3. 获取代码和 GPU 依赖

以下路径为示例，在工控机上创建 `C:\sorting-vision`，不要在已有同名目录里重复克隆覆盖。

```powershell
git lfs install
git clone https://github.com/zlxk2024/sorting-vision-anomaly-detection.git C:\sorting-vision
Set-Location C:\sorting-vision
git lfs pull --include="models/*"
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu126
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe scripts/verify_project.py
.\.venv\Scripts\python.exe -c "import torch; print('torch=',torch.__version__,'CUDA=',torch.version.cuda,'available=',torch.cuda.is_available()); assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))"
```

CUDA 12.6 wheel 组合来自 [PyTorch 2.8 官方安装列表](https://pytorch.org/get-started/previous-versions/)，须与现场 NVIDIA 驱动兼容。`torch.cuda.is_available()` 必须为 True，显卡名称应正确。此步骤失败时不继续宣称 GPU 已部署；按现场驱动选择官方兼容构建。本项目默认 Dockerfile 是 CPU 版，本手册使用 Windows 原生 Python GPU 环境。

## 4. 生成私有连接配置

```powershell
.\.venv\Scripts\python.exe -m sorting_vision.configure
Copy-Item config/realtime.windows.example.yaml config/realtime.windows.local.yaml
notepad config/realtime.windows.local.yaml
```

向导会依次询问相机 IP、账号、隐藏密码、路径，以及 MySQL 地址、端口、库名、账号、隐藏密码。自动对密码中的 `@` 等字符进行 URL 编码，生成随机 API key，并将本地连接信息写到 `.env`，不会打印密码。已有 `.env` 时拒绝覆盖，直接用本地编辑器修改。

`.env` 和 `config/*.local.yaml` 被 Git 忽略，不能上传真实账号、现场截图或证据。`.env` 由 `--env-file` 作为纯数据读取，不执行 shell，不进行 `${...}` 插值；显式文件中的同名变量覆盖当前进程变量。Windows 原生启动时不要把存储路径写成 Docker 的 `/work/realtime`。

本地 YAML 中确认：

- `model.device: "0"`，使用第一张 NVIDIA 显卡。
- `database.create_tables: false`，由 DBA 预建表。
- `site_id` 和 `camera_id` 使用实际约定编号；首轮测试可约定独立测试站点编号，便于区分测试结果。
- `cameras[].regions` 替换成现场校准区域；示例 ROI 不能用于异常准确率验收。
- 三类默认事件：落格错误、一车两件/多件混放、格口包裹滞留。没有动态任务目标时，“落格错误”仅为视觉候选。

## 5. 第一关：仅测试视频流

```powershell
.\.venv\Scripts\python.exe -m sorting_vision.diagnostics --env-file .env camera --seconds 10 --snapshot runs/preflight/camera.jpg
```

通过条件：`passed: true`、`input_kind: live-stream`、连续解码多帧，分辨率符合预期。用 Windows 图片查看器打开 `runs/preflight/camera.jpg`，确认是正确机位、画面清晰、抽屉和格口可见。这一步不加载 YOLO、不连数据库。

失败时分别确认工控机网络、554 端口、账号、路径大小写、编码和关键帧间隔。可以在同一台工控机使用厂家软件或播放器核对画面。单独 ping 成功、端口打开或网页能登录，都不等于视频能解码。

此诊断不会持续显示实时窗口，也不证明相机端画面未冻结；需要现场对照真实物体运动。`decoded_frames` 是取流检查计数，不是模型 FPS。

## 6. 第二关：测试 GPU 模型

```powershell
.\.venv\Scripts\python.exe -m sorting_vision.diagnostics model --image runs/preflight/camera.jpg --device 0 --output runs/preflight/model.jpg
```

通过条件：`passed: true`、`actual_device: cuda:0`、GPU 名称正确，`runs/preflight/model.jpg` 可以看到检测框。检查包裹、抽屉、格口的识别是否对应实际画面；只有模型运行成功但没有检测框，仍需核对画面和模型泛化效果。

这是单帧实体检测，不是三类业务异常验收。`cold_call_seconds` 包含加载和首次推理，不能当作稳定运行 FPS。GPU 不可用时明确失败，测试不会自动转 CPU 后声称 GPU 通过。

## 7. 第三关：检查数据库和读写权限

DBA 建表之后运行：

```powershell
.\.venv\Scripts\python.exe -m sorting_vision.diagnostics --env-file .env database
.\.venv\Scripts\python.exe -m sorting_vision.diagnostics --env-file .env database --write-test
```

第一条只读：检查连接、两张服务表、所需列和主键，不自动建表。`dba_schema_setup_required` 表示表缺失或基础结构不匹配，按返回表名让 DBA 核对；不自动迁移现有表。

第二条显式测试：在事务里向两张服务表插入带测试标记的数据，验证事件 JSON 的插入、更新、查询、删除，最后回滚。MySQL 表必须是 InnoDB。通过时 `crud_test: passed_and_rolled_back`，不留下已提交模拟事件。

这验证连接与事务内读写权限，尚未验证真实检测事件的提交持久化；下一关完成完整链路。

## 8. 第四关：启动实时检测和确认实际入库

```powershell
.\.venv\Scripts\python.exe -m sorting_vision.realtime --env-file .env --config config/realtime.windows.local.yaml --check-config
.\scripts\windows\start-realtime.cmd
```

第一条仅检查配置。第二条在当前窗口前台运行；在另一个 PowerShell 窗口进入项目目录，再运行：

```powershell
Set-Location C:\sorting-vision
.\.venv\Scripts\python.exe -m sorting_vision.diagnostics --env-file .env status
```

通过条件：`passed: true`、HTTP 200、`ready: true`、摄像头 `frames_processed` 持续增加、数据库近期 `last_success` 更新且队列 `pending` 能清零。状态查询自动从 `.env` 读取 API key，不要求把密码粘贴到命令里。

与现场人员共同核对真实画面和候选结果，通过数据库工具查询（使用实际编号替换占位）：

```sql
SELECT camera_id, site_id, state, heartbeat_at
FROM sorting_camera_status
WHERE site_id = 'YOUR_SITE' AND camera_id = 'YOUR_CAMERA';

SELECT event_id, event_type, status, start_at, review_status, snapshot_path, clip_path, payload
FROM sorting_events
WHERE site_id = 'YOUR_SITE' AND camera_id = 'YOUR_CAMERA'
ORDER BY start_at DESC LIMIT 20;
```

也可以直接查询服务从数据库读取的最近十条候选，命令会自动使用本地 API key：

```powershell
.\.venv\Scripts\python.exe -m sorting_vision.diagnostics --env-file .env events
```

摄像头心跳可先证明正常服务状态已提交；有真实异常候选时，再核对事件记录、JSON 中文类型、截图、短片是否对应同一时间和位置，并在服务重启后确认仍可查询。正常运行暂时没有异常记录，不代表程序故障。

正确识别三类事件需要经人工确认的正常/异常样本对照。录像回放应使用独立测试配置、输出目录和测试数据库，不把历史录像结果混入正式实时数据。目标格口、ROI、阈值未确认前不能把候选当作已确认业务错分。

## 9. 稳定性、关闭和结果回传

在约定的联调时段测试：断流后自动重连、数据库断开后 pending 增长且恢复清零、停止/重启后历史结果保留、持续至少一个完整班次的帧率/延迟/误报情况。记录输入分辨率、编码、帧率、推理尺寸、GPU/CPU 实际使用以及机器其他负载。

前台测试时保持服务窗口开启，使用 Ctrl+C 正常停止。断开 ToDesk 连接后，只要工控机保持运行、Python 进程未退出，检测可以继续；关闭服务窗口、注销用户或重启可能中断本次前台进程。本启动脚本没有安装 Windows 服务、开机自启或崩溃守护，长期无人值守部署需另外配置并验收，不能仅凭远程桌面连接成功判断上线。

可回传：去除凭据的诊断 JSON、GPU 型号/驱动、检测示意图、事件 ID 和复核结论。真实账号密码不发群聊、不进入 Git。ToDesk 画面流畅程度不是模型处理速度，应以程序指标和现场时间对照为准。

## 本手册的验证范围

本地回归、实际本地视频解码、实际 CPU 模型调用和 SQLite 事务回滚可在开发机验证；这不代表已在现场 Windows/RTX3060、现场 RTSP 或业务 MySQL 上通过。现场按本手册逐项记录通过/失败，完成部署验收。

开发机本次已通过 42 项回归测试，实际本地录像解码、截图、CPU 模型调用、无 CUDA 时明确失败、取流失败不输出凭据，以及独立 SQLite 的回滚读写测试。技术记录见 [WINDOWS_PREFLIGHT_VERIFICATION_2026-10-24.json](WINDOWS_PREFLIGHT_VERIFICATION_2026-10-24.json)。这些结果不代替 Windows、CUDA、现场 RTSP 或业务库提交验证。
