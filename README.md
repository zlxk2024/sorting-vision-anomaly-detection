# 快递分拣视觉异常检测系统

本仓库汇总快递分拣视觉项目的代码、技术文档、YOLO 标注数据、模型权重、
推理结果和评估材料。仓库默认设为私有，用于现场方案验证与后续工程交付。

## 视觉异常检测目标

系统通过现场摄像机视频识别 `parcel`、`drawer_open`、`drawer_closed`、
`chute` 和 `bag`，结合目标跟踪、时间窗口及 PLC 事件判断：

1. 开门不掉件：门已打开，包裹超过正常时间仍停留在抽屉；
2. 飘格/掉错格口：包裹实际落入位置与 PLC 目标闸口不一致；
3. 一车两件：同一抽屉内同时存在两个及以上包裹；
4. 失速/滞留：包裹长时间停留在闸口或滑落路径上。

## 仓库结构

- `scripts/`：抽帧、标注、训练、推理、跟踪和异常事件判断脚本；
- `datasets/`：YOLO 数据集、统一标注规范和新机位补充数据；
- `runs/`、`outputs/`：训练权重、推理视频和实验结果；
- `docs/`：架构、硬件、评估及数据集说明；
- `evaluation/`：异常检测评估工具；
- `parcel_vision/`：快递点云定位原型；
- `reports/`：测试报告、对比图和客户演示材料。

关键文档：

- [数据标注统一标准](datasets/sorting_yolo_stage1/ANNOTATION_STANDARD_v1.md)
- [数据集说明](docs/DATASET_CARD.md)
- [异常检测评估框架](docs/快递分拣视觉模型与异常检测系统评估体系_V1.0.md)

二进制数据、视频和模型由 Git LFS 管理。克隆后执行：

```bash
git lfs pull
```

## YOLO 数据与训练

类别顺序固定为：

```text
0 parcel
1 drawer_open
2 drawer_closed
3 chute
4 bag
```

正式训练前应查看每个数据目录的 `manifest.csv` 或 `README.md`，只合并已经
人工确认或视觉复核通过的样本。首轮预标注数据不能未经复核直接进入生产训练集。

---

## 传送带快递点云定位原型

这个程序把3D相机输出的XYZ点云转换为多个快递的抓取坐标，并生成“3D相机识别位置通用协议”中的 `package_location` JSON。

处理流程：RANSAC拟合传送带平面、生成5毫米高度图、形态学修复、连通域分割、最小面积矩形测量、吸取点评分、相机到机械臂坐标转换。

## HTTP 服务

启动对外接口：

```bash
python3 -m parcel_vision.api \
  --host 0.0.0.0 \
  --port 8080 \
  --config parcel_vision.example.json \
  --transform calibration.example.json
```

上传点云并获取协议坐标：

```bash
python3 -m parcel_vision.api_client \
  reports/generated_irregular_parcels/irregular_parcels.ply \
  --url http://127.0.0.1:8080/v1/package-location \
  --device arm1
```

接口地址为 `POST /v1/package-location`，健康检查为 `GET /health`。完整字段、curl 示例、错误码和 Docker 部署方法见 [API.md](API.md)。

## 快速运行

识别核心依赖 Python 3.9、NumPy 和 SciPy；生成对比图还需要 Matplotlib。运行内置的三个快递仿真场景：

```bash
python3 -m parcel_vision.cli --demo
```

处理实际点云：

```bash
python3 -m parcel_vision.cli camera_points.npy --transform calibration.json
```

支持 `NPY`、`NPZ`、`XYZ/TXT`、`CSV`、MATLAB `MAT`、PCD 和 ASCII `PLY`。所有输入距离默认使用毫米。

相机到机械臂的标定文件格式：

```json
{
  "camera_to_robot": [
    [1, 0, 0, 100],
    [0, 1, 0, -50],
    [0, 0, 1, 20],
    [0, 0, 0, 1]
  ]
}
```

运行测试：

```bash
python3 -m unittest discover -s tests -v
```

运行100帧高拟真随机压力测试并生成误差报告：

```bash
python3 -m parcel_vision.stress --scenes 100
```

报告写入 `reports/stress_report.md` 和 `reports/stress_report.json`。

验证公开真实点云：

```bash
python3 -m parcel_vision.public_eval data/public/pcl_table_scene_lms400.pcd
```

用三个公开真实 RGB-D 纸箱表面构造传送带场景并评估：

```bash
python3 -m parcel_vision.real_object_eval \
  data/public/rgbd-dataset/cereal_box/cereal_box_1/cereal_box_1_4_1.pcd \
  data/public/rgbd-dataset/cereal_box/cereal_box_1/cereal_box_1_4_30.pcd \
  data/public/rgbd-dataset/cereal_box/cereal_box_1/cereal_box_1_4_120.pcd \
  --output reports/real_object_composite_top_views
```

这项测试使用真实相机采集的物体表面，但传送带平面和纸箱摆放位置是合成的。结果与适用边界见 `reports/real_rgbd_attempt.md`。

生成原始点云与预测结果对比图，并导出 CloudCompare 彩色点云：

```bash
python3 -m parcel_vision.visualize \
  reports/real_object_composite_top_views/real_cereal_box_composite.npy \
  --morphology-radius 8 \
  --output reports/visualization
```

输出包括俯视对比图、3D 对比图和带预测包围框/中心/吸取点的彩色 PLY。

生成一帧带纸箱、软袋、相机噪声、缺点和离群点的高拟真点云：

```bash
python3 -m parcel_vision.generate_scene \
  --seed 20260717 \
  --count 10 \
  --output reports/generated_realistic_scene
```

该命令同时保存原始 `PLY/NPY`、真实坐标、预测坐标、误差结果和对比图。它是传感器仿真数据，不替代现场相机采集。

生成10件三层相互遮挡、接触和堆叠的复杂场景：

```bash
python3 -m parcel_vision.stacked_scene \
  --output reports/generated_stacked_10_parcels
```

该场景采用俯视深度遮挡，只保留相机能看到的最高表面，主要用于检验贴合和堆叠条件下的欠分割问题。

生成大小不一、轮廓不规则并带局部叠压的俯视点云：

```bash
python3 -m parcel_vision.irregular_scene \
  --output reports/generated_irregular_parcels
```

生成客户演示视频：

```bash
python3 -m parcel_vision.client_demo_video \
  --output reports/client_demo/parcel_vision_demo.mp4
```

综合验证结论见 `reports/verification_summary.md`。

## 现场接入

相机SDK只需产生形状为 `(N, 3)` 的 NumPy 数组，并调用：

```python
from parcel_vision import ParcelVisionPipeline

detections = ParcelVisionPipeline().process(points_xyz, camera_to_robot)
```

当前版本适用于摊平后、快递之间存在可见间隙的场景。软包严重粘连、上下叠放时，应增加RGB实例分割结果作为每件快递的掩码；几何连通域本身无法可靠区分完全贴合且同高的两个物体。

上游实例分割模型输出 `K x H x W` 掩码后，可直接与对齐深度图融合：

```python
from parcel_vision import CameraIntrinsics, ParcelVisionPipeline
from parcel_vision.rgbd import rgbd_instance_masks_to_detections

detections = rgbd_instance_masks_to_detections(
    depth_mm,
    instance_masks,
    CameraIntrinsics(fx=900, fy=900, cx=640, cy=360),
    ParcelVisionPipeline(),
)
```

纯点云堆叠基线可使用高度突变分割：

```bash
python3 -m parcel_vision.cli camera_points.pcd \
  --segmentation-method height_edges \
  --height-edge-threshold 12 \
  --min-detection-score 0.75
```

该模式输出的是可见表面候选，不代表被遮挡快递的完整轮廓。机械臂应按 `grasp_plan.json` 每次只抓一个可用候选，并在抓取后重新拍照。
