# 不规则快递俯视点云识别报告

## 场景

场景模拟固定俯视3D相机，共63,750个点，包含12种大小和轮廓不同的快递：

- 褶皱大软袋
- 梯形纸箱
- 缺角长条包裹
- 圆角软袋
- 破损缺角纸箱
- 气泡信封
- 圆筒包裹
- L形包装
- 大型塑料袋
- 叠放小纸箱
- 扁平微型快递
- 不规则微型软包

同时加入1.4毫米深度噪声、材质相关随机缺点、两个连续深度空洞、轻微传送带倾斜和110个离群点。

## 结果

| 指标 | 结果 |
| --- | ---: |
| 真实快递数 | 12 |
| 检出快递数 | 12 |
| 匹配快递数 | 12 |
| 吸取点到对应可见表面平均距离 | 4.02 mm |
| 可见表面距离P95 | 7.03 mm |
| 最大可见表面距离 | 8.65 mm |
| 吸取点相对完整顶部中心平均误差 | 21.20 mm |
| 平均方向误差 | 5.26度 |

L形包装、气泡信封和大型软袋的安全吸取点会主动偏离几何中心，因此完整中心误差较大，但吸取点仍位于对应快递的真实可见表面。

两个微型快递均被独立检出。扁平微型快递的顶部中心误差约0.77毫米；不规则微型软包约6.61毫米。微型软包接近圆形，因此方向角不稳定，但不影响吸盘中心选择。

## 文件

- `generated_irregular_parcels/irregular_parcels.ply`：原始点云
- `generated_irregular_parcels/overhead_depth_style.png`：视频右侧风格俯视高度图
- `generated_irregular_parcels/raw_truth_prediction_comparison.png`：原始、真值和预测对比
- `generated_irregular_parcels/prediction_colored_cloudcompare.ply`：CloudCompare预测点云
- `generated_irregular_parcels/prediction.json`：机械臂坐标输出
- `generated_irregular_parcels/grasp_plan.json`：抓取顺序

该结果来自高拟真几何仿真，不代表现场相机最终精度。
