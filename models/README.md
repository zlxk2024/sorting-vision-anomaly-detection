# 模型

YOLO11n 五类目标检测模型，项目训练版本 V2。PT 用于当前 Python/HTTP 推理；ONNX 是导出中间格式，可用于其他兼容引擎或进一步转换 RKNN。当前 HTTP 服务不直接执行 ONNX。

运行 `git lfs pull --include="models/*"` 下载真实文件，再运行 `python scripts/verify_project.py` 校验。

输入尺寸配置为 320；类别顺序固定为 parcel、drawer_open、drawer_closed、chute、bag。模型只检测实体，异常判断由 ByteTrack 与规则完成。

两份权重的 SHA-256、文件大小见 manifest.json。RKNN 成品未包含，板端推理精度与速度尚需验证。

训练基于 Ultralytics YOLO11n 预训练权重；使用和再分发需遵守 Ultralytics 及相关模型/依赖许可。仓库未附加一个替代第三方许可的开源授权。历史测试指标和适用边界见 docs 中的训练报告。
