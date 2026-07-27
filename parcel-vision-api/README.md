# 快递3D点云定位服务

输入一帧3D相机 XYZ 点云，自动分割传送带上的多个快递，计算吸取点、姿态和尺寸，并输出《3D相机识别位置通用协议 V1.0.1》规定的 `package_location` JSON。

核心流程：传送带平面拟合、5毫米高度图、快递实例分割、最小包围矩形、吸取点评分、相机坐标到机械臂坐标转换。

## 项目结构

```text
parcel-vision-api/
├── parcel_vision/              核心算法、HTTP服务和调用客户端
├── tests/                      自动测试
├── docs/                       TCP协议原文和GitHub上传说明
├── examples/                   可直接联调的高拟真点云
├── API.md                      HTTP接口说明
├── calibration.example.json   手眼标定矩阵示例
├── parcel_vision.example.json 算法参数示例
├── Dockerfile                 容器部署
└── pyproject.toml             Python项目配置
```

## 安装

要求 Python 3.9 或更高版本。

```bash
cd "/Users/lixing.guo/Documents/机械臂/parcel-vision-api"
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

需要生成可视化图片时：

```bash
python3 -m pip install -e ".[visualization]"
```

## 启动服务

```bash
python3 -m parcel_vision.api \
  --host 0.0.0.0 \
  --port 8080 \
  --config parcel_vision.example.json
```

接口：

- `GET /health`：服务健康检查
- `POST /v1/package-location`：上传点云并返回所有快递坐标

## 上传示例点云

另开一个终端执行：

```bash
cd "/Users/lixing.guo/Documents/机械臂/parcel-vision-api"
python3 -m parcel_vision.api_client \
  examples/irregular_parcels.ply \
  --url http://127.0.0.1:8080/v1/package-location \
  --device arm1 \
  --include-extensions
```

示例点云是高拟真仿真数据，包含12件大小和形状不同的快递，仅用于联调和演示。

## 现场标定

未提供标定矩阵时，接口返回相机坐标。完成相机与机械臂手眼标定后：

```bash
python3 -m parcel_vision.api \
  --host 0.0.0.0 \
  --port 8080 \
  --config parcel_vision.example.json \
  --transform calibration.json
```

`calibration.example.json` 只展示格式，不能作为现场标定结果。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

测试覆盖核心分割、坐标转换、协议序列化、文件上传、JSON点数组、multipart客户端和错误响应。

## Docker

```bash
docker build -t parcel-vision-api .
docker run --rm -p 8080:8080 parcel-vision-api
```

## 输入格式

支持 `NPY`、`NPZ`、`PCD`、ASCII `PLY`、`XYZ/TXT`、`CSV` 和 MATLAB `MAT`。所有距离默认使用毫米。

点云应包含足够大的传送带平面。当前几何算法适用于摊平且轮廓可分离的快递；完全贴合、同高重叠的包裹需要增加 RGB-D 实例分割。

## 文档

- [HTTP API说明](API.md)
- [TCP协议原文](docs/3D相机识别位置-TCP-协议V1.0.1.docx)
- [GitHub上传步骤](docs/GITHUB_UPLOAD.md)
