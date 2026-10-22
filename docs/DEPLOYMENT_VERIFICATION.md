# 部署与调用验证

日期：2026-10-22。版本：0.2.0。仓库当前工作树整理为代码、配置、技术文档和 V2 模型；业务视频、数据集、实验输出和报价不在本次发布中。历史提交保留。

## 已通过

- Python 代码语法及两份模型 SHA-256 校验。
- 9 项自动测试：API 鉴权、上传/产物读取、路径边界、不支持格式、大小限制、并发拒绝、超时后恢复，以及模型完整性/LFS 指针识别。
- 真实模型 HTTP 链路：上传本地现场视频前 60 帧，经 V2 YOLO + ByteTrack + V1 规则处理，得到 280 个检测框，存在有效轨迹 ID；事件 JSON 可读，标注视频下载后可解码且有 60 帧。
- 全新临时 Python 3.12 环境完成 `pip install --no-deps -e .`，API 模块入口可启动参数解析；完整模型运行仍使用下述现有环境。
- Compose 配置通过 `docker compose config --quiet`。
- 历史 C++ 模拟示例已在本机编译运行；本次未改变其状态机。

真实 HTTP 测试数值见 `real_http_smoke.json`。测试使用现场片段，但未将输入视频、逐帧业务检测结果或输出视频提交到仓库。60 帧片段未产生异常候选，因此不构成四类异常准确率验收。

## 测试环境与限制

本机真实模型测试复用现有 Python 3.9.6、Ultralytics 8.4.104、PyTorch 2.8.0、torchvision 0.23.0、OpenCV 5.0.0.93、NumPy 2.0.2；lap 0.5.12 从临时目录提供，没有把个人虚拟环境提交到仓库。新部署推荐 Python 3.11，项目依赖声明要求 Python >=3.10。

Docker 服务在本机未启动，故未完成镜像实际构建/容器推理；不把 Compose 语法检查作为容器运行成功。Dockerfile 在构建阶段再次校验模型文件。

未连接现场相机、PLC/WCS 或告警设备，未完成多路实时、事件级精度及长期稳定性验收。Horus RKNN 成品和相机应用尚未完成，见 `KNOWN_LIMITATIONS.md`。

## 接收者验证步骤

1. 使用有仓库权限的账号克隆，执行 `git lfs pull --include="models/*"`。
2. 执行 `python scripts/verify_project.py`，确认模型不是指针文件。
3. 按 README 安装依赖，运行单元测试。
4. 用自己的授权视频执行 CLI 或 API 调用，核对检测框、轨迹及事件。
5. Docker 部署时执行 `docker compose up -d --build`，再调用 health 和视频接口。
