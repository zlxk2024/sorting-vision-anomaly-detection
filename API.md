# 快递点云定位 HTTP API

服务接收一帧包含传送带平面和快递的 XYZ 点云，输出《3D相机识别位置通用协议 V1.0.1》中的 `package_location` 报文。输入距离和输出距离均为毫米，角度为度。

## 启动

```bash
python3 -m parcel_vision.api \
  --host 0.0.0.0 \
  --port 8080 \
  --config parcel_vision.example.json \
  --transform calibration.json
```

未提供 `--transform` 时，返回相机坐标；提供标定矩阵后，返回机械臂基坐标。
`--config` 用于加载算法参数，示例适合包含不规则件和高度差的测试场景；现场参数应使用相机点云重新标定。

## 健康检查

```http
GET /health
```

成功响应：

```json
{"status":"ok","service":"parcel-vision","version":"1.0"}
```

## 上传点云

```http
POST /v1/package-location
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `file` | 是 | 点云文件，支持 NPY、NPZ、PCD、ASCII PLY、XYZ、TXT、CSV、MAT |
| `device` | 否 | 机械臂别名，默认 `arm1` |
| `transaction_id` | 否 | 消息 ID；不传时服务自动生成 |
| `camera_to_robot` | 否 | 4×4 JSON 标定矩阵；优先于服务启动参数 |
| `include_extensions` | 否 | `true` 时增加 object_id、score 和运行元数据 |

调用内置客户端：

```bash
python3 -m parcel_vision.api_client \
  reports/generated_irregular_parcels/irregular_parcels.ply \
  --url http://127.0.0.1:8080/v1/package-location \
  --device arm1 \
  --transform calibration.example.json
```

也可以直接使用 curl：

```bash
curl -X POST http://127.0.0.1:8080/v1/package-location \
  -F file=@camera_points.pcd \
  -F device=arm1 \
  -F transaction_id=2025071410381137573399
```

## JSON 点数组

小型点云或联调时，可以直接发送：

```json
{
  "device": "arm1",
  "transaction_id": "test-001",
  "points": [[0, 0, 1000], [5, 0, 1000], [10, 0, 920]],
  "camera_to_robot": [
    [1, 0, 0, 100],
    [0, 1, 0, -50],
    [0, 0, 1, 20],
    [0, 0, 0, 1]
  ]
}
```

大量点云应使用文件上传，避免 JSON 体积和解析开销。

## 成功响应

默认响应只包含协议 V1.0.1 规定的业务字段：

```json
{
  "svc_cont": {
    "message": {
      "status": "success",
      "data": [
        {
          "device": "arm1",
          "location": {
            "x": "123.45",
            "y": "67.89",
            "z": "810.20",
            "angle_z": "12.30",
            "angle_y": "0.00",
            "angle_x": "180.00",
            "object_length": "320.00",
            "object_width": "210.00",
            "object_height": "145.00",
            "object_type": "2"
          }
        }
      ]
    }
  },
  "tcp_cont": {
    "transaction_id": "test-001",
    "send_time": 1752460691290,
    "service_type": "package_location"
  }
}
```

`x/y/z` 是吸取点，不是包裹体积中心。当前纯点云版本不能可靠区分信封和软包，`object_type` 暂按盒子 `2` 输出；后续接入 RGB 分类模型后可输出 `0/1/2`。

## 错误响应

HTTP 状态码会区分请求错误，响应体仍保留协议外层结构：

```json
{
  "svc_cont": {
    "message": {
      "status": "failed",
      "error_code": "invalid_point_cloud",
      "error_message": "Could not find a dominant conveyor plane"
    }
  },
  "tcp_cont": {
    "transaction_id": "自动生成的消息ID",
    "send_time": 1752460691290,
    "service_type": "package_location"
  }
}
```

## 输入要求

- 点云坐标单位必须是毫米。
- 一帧至少包含 100 个有效 XYZ 点。
- 画面必须包含足够大的传送带平面，供 RANSAC 建立坐标基准。
- 相机到机械臂标定矩阵应由现场手眼标定得到，不能直接使用示例数值。
- 当前几何分割适用于摊平且轮廓可分离的快递；完全贴合、同高重叠的包裹需要 RGB-D 实例分割。

## Docker

```bash
docker build -t parcel-vision-api .
docker run --rm -p 8080:8080 parcel-vision-api
```
