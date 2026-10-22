# Docker 实际部署与性能验证

日期：2026-10-22。

**结果：从 GitHub 全新克隆、下载 LFS 模型、实际构建镜像、启动服务、上传真实视频、下载并解码结果视频、容器重启后读取旧结果和执行新任务，均通过。当前 CPU 环境端到端处理能力约 9.5～9.6 FPS，适用于离线分析，达不到约 30 FPS 输入视频的实时处理要求。**

## 部署环境

| 项目 | 实测配置 |
|---|---|
| 源码基线 | a8e14b37cf6ad8132b430a37cf4130d22298caf2 |
| 主机 | Apple M1，8 GB 内存 |
| Docker | Desktop / Engine 27.3.1，Compose 2.30.3 |
| 虚拟机资源 | 8 CPU，3.827 GiB 内存；与其他既有服务共享 |
| 容器平台 | 原生 linux/arm64，无 x86 模拟，无 GPU |
| 运行环境 | Python 3.11.17，PyTorch 2.8.0+cpu，Ultralytics 8.4.183 |
| 其他依赖 | torchvision 0.23.0，OpenCV 5.0.0.93，NumPy 2.4.6，SciPy 1.17.1，lap 0.5.13 |
| 模型/参数 | YOLO11n V2 PT，imgsz=320，conf=0.15，ByteTrack，V1 规则 |
| 镜像大小 | 1,597,273,624 字节，约 1.60 GB |
| 镜像 ID | sha256:f9df46a5c93e4eb01eb4ae8a98988df90f59fbcb38d64d029519a4f1d5d26c26 |

完整依赖清单见 `docker-python-freeze-2026-10-22.txt`；该文件记录实测环境，不是跨平台安装锁文件。当前 requirements 使用版本范围，未来重建时应核对依赖漂移。

第一次构建需要从 Docker Hub、Debian、PyTorch CPU 源和 PyPI 下载文件。本次基础镜像元数据拉取约 248 秒，后续自动恢复并完成构建；没有更改 DNS、代理或第三方镜像源。CPU 版 PyTorch ARM64 wheel 可正常安装。

## 性能结果

输入均为 720×1280、约 29.95 FPS 的真实分拣视频；短片段为同一视频中连续 300 帧。

| 工作负载 | 帧数 | 视频时长 | 调用次数 | 端到端耗时 | 有效处理帧率 |
|---|---:|---:|---:|---:|---:|
| 完整视频 | 1,182 | 39.47 秒 | 1 | 124.43 秒 | 9.50 FPS |
| 短片段，第 1 次 | 300 | 10.02 秒 | 1 | 29.23 秒 | 10.26 FPS |
| 短片段，第 2 次 | 300 | 10.02 秒 | 1 | 31.22 秒 | 9.61 FPS |
| 短片段，第 3 次 | 300 | 10.02 秒 | 1 | 32.55 秒 | 9.22 FPS |
| 短片段中位数 | 300 | 10.02 秒 | 3 | 31.22 秒 | 9.61 FPS |

计时从发起上传到完整收到 JSON 响应，包含上传、每任务新建进程/加载模型、解码、检测、跟踪、规则分析、生成标注视频及返回结果；结果视频下载另计。每个任务都会重新加载模型，所以重复请求不能解释为常驻模型的热推理性能。

完整视频结果约 46.94 MB，下载耗时约 0.31 秒；短片段结果约 12.11 MB，下载约 0.10～0.13 秒。上述下载为本机回环网络，不代表跨网络传输速度。

完整视频调用平均 CPU 332.75%，采样峰值 401.57%；Docker CPU 100% 代表一个逻辑 CPU。完整任务采样内存峰值约 355.9 MiB；整个验证期间 cgroup 内存峰值约 446.6 MiB，包含不同计量口径中的缓存。未发生 OOM。

完整视频及每次短片段均返回 3 个异常候选。候选尚未逐事件人工复核，不能将该数字作为准确率。样本量不足以报告 P95/P99 或长期稳定性。

## 接口和持久化验证

- 容器内 9 项 API/模型单元测试全部通过。
- 实际推理期间 health 返回 200；单次响应约 30 ms。
- 未提供密钥的请求返回 401；真实推理期间第二个任务返回 429。
- 完整结果包含 1,182 帧检测及有效轨迹 ID。
- 下载的标注视频包含 1,182 帧，首帧和末帧可解码。
- 重启测试容器后，原任务 JSON 完全一致，检测结果和视频可继续下载。
- 重启后再次上传 60 帧视频，处理成功；最终健康状态 healthy、OOMKilled=false。

测试使用独立 Compose 项目 `sorting-validation`，只把测试端口映射为本机 18080，并配置临时鉴权密钥。原 Dockerfile、推理服务和默认 CPU 参数未更改；现场输入、结果视频、逐帧检测及密钥未提交到 GitHub。验证结束后停止本次测试容器，保留构建镜像和本地结果，不停止其他既有服务。

## 其他部署者如何复测

先按 README 克隆、执行 Git LFS 下载、构建并启动：

```bash
git lfs install
git clone https://github.com/zlxk2024/sorting-vision-anomaly-detection.git
cd sorting-vision-anomaly-detection
git lfs pull --include='models/*'
docker compose up -d --build
curl --fail http://127.0.0.1:8080/health
python3 scripts/benchmark_api.py \
  --url http://127.0.0.1:8080 \
  --video /path/to/authorized-video.mp4 \
  --repeats 3 --output runs/benchmark.json
```

需要采样资源时，增加 `--container`，取值为 `docker compose ps` 显示的容器名。配置了鉴权时，客户端也应设置相同的 `SORTING_API_KEY` 环境变量。客户端脚本只依赖 Python 标准库；只有资源采样选项需要 Docker CLI。

## 适用结论

本次证明该 GitHub 源码与模型在此 Linux ARM64 CPU 容器上可以实际部署和调用。完整视频约需视频时长的 3.15 倍，当前应作为离线复核工具使用。若要求持续约 30 FPS、多路实时或更低延迟，需要在最终 x86/GPU 工控机上重新测量；本次不推算 GPU 路数或生产容量。
