import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "/Users/lixing.guo/Documents/机械臂/outputs/visual_model_quote_20260725";
const outputFile = `${outputDir}/AI错分视觉模型开发报价评估.xlsx`;

const wb = Workbook.create();
const summary = wb.worksheets.add("报价总览");
const detail = wb.worksheets.add("详细报价");
const scope = wb.worksheets.add("范围与验收");
const sources = wb.worksheets.add("依据与说明");

const navy = "#0B1F3A";
const blue = "#1665D8";
const cyan = "#E8F2FF";
const light = "#F4F7FB";
const green = "#DFF4E5";
const amber = "#FFF2CC";
const red = "#FCE8E6";
const gray = "#5F6B7A";
const border = "#D7DFE8";
const white = "#FFFFFF";
const moneyFmt = '¥#,##0;[Red](¥#,##0);-';
const pctFmt = "0.0%";

for (const sheet of [summary, detail, scope, sources]) {
  sheet.showGridLines = false;
}

// ------------------------- 详细报价 -------------------------
detail.mergeCells("A1:L1");
detail.getRange("A1").values = [["AI错分视觉模型开发——详细报价（预算版）"]];
detail.getRange("A1:L1").format = {
  fill: navy,
  font: { bold: true, color: white, size: 18 },
  verticalAlignment: "center",
  horizontalAlignment: "center",
};
detail.getRange("A1:L1").format.rowHeight = 36;
detail.mergeCells("A2:L2");
detail.getRange("A2").values = [[
  "范围：视频人工标注、模型训练、GPU资源及人力成本；不含相机、工控机、服务器、后台APP和现场弱电。"
]];
detail.getRange("A2:L2").format = {
  fill: cyan,
  font: { color: navy, size: 10 },
  wrapText: true,
  verticalAlignment: "center",
};
detail.getRange("A2:L2").format.rowHeight = 28;

detail.getRange("A4:L4").values = [[
  "序号", "费用类别", "工作项", "计价依据", "数量", "单位",
  "未税单价", "未税金额", "税率", "税额", "含税金额", "交付/说明"
]];
detail.getRange("A4:L4").format = {
  fill: blue,
  font: { bold: true, color: white },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: border },
};
detail.getRange("A4:L4").format.rowHeight = 30;

const items = [
  [1, "需求与数据", "现场场景与异常定义梳理", "高级方案/算法人员", 6, "人天", 2500, null, 0.06, null, null, "明确3类异常、门/小车/格口关系及数据口径"],
  [2, "需求与数据", "标注规范与黄金样本制定", "高级算法人员", 6, "人天", 2500, null, 0.06, null, null, "形成parcel、gate_open、gate_closed、cart_load_area规范"],
  [3, "需求与数据", "视频抽帧、去重与样本切分", "数据工程人员", 6, "人天", 2000, null, 0.06, null, null, "按视频批次划分训练/验证/测试集"],
  [4, "人工标注", "目标框人工标注", "约8,000帧", 8000, "帧", 6, null, 0.06, null, null, "每帧标注包裹、门状态和小车载物区域"],
  [5, "人工标注", "标注质检与返修", "约8,000帧", 8000, "帧", 2, null, 0.06, null, null, "双人抽检、难例复核、错框返修"],
  [6, "人工标注", "事件级时间段标注", "约200段视频", 200, "段", 40, null, 0.06, null, null, "标出开门未落、掉错格口、一车多件及正常对照"],
  [7, "数据治理", "数据集版本管理与质量报告", "数据工程人员", 6, "人天", 2000, null, 0.06, null, null, "数据版本、类别统计、泄漏检查及质量报告"],
  [8, "核心模型", "YOLO目标检测模型定制训练", "视觉算法工程师", 20, "人天", 2750, null, 0.06, null, null, "检测包裹、开门、关门、小车载物区域"],
  [9, "核心模型", "多目标跟踪与小车归属", "视觉算法工程师", 15, "人天", 3000, null, 0.06, null, null, "包裹跟踪ID及parcel→cart_load_area归属"],
  [10, "异常算法", "开门未落判断", "视觉算法工程师", 10, "人天", 2500, null, 0.06, null, null, "开门状态、包裹滞留时间和离开轨迹"],
  [11, "异常算法", "A格开门、包裹落入B格判断", "视觉算法工程师", 14, "人天", 2500, null, 0.06, null, null, "目标格口与实际轨迹匹配；需格口编号/业务目标"],
  [12, "异常算法", "同一小车两件及以上判断", "视觉算法工程师", 10, "人天", 2500, null, 0.06, null, null, "同一小车区域内多个不同包裹跟踪ID"],
  [13, "迭代优化", "难例挖掘与两轮模型迭代", "视觉算法工程师", 14, "人天", 2500, null, 0.06, null, null, "覆盖黑袋、白包、遮挡、运动模糊和异常门状态"],
  [14, "迭代优化", "ONNX/TensorRT推理优化", "推理工程师", 10, "人天", 2500, null, 0.06, null, null, "模型导出、测速、显存与并发优化"],
  [15, "测试交付", "独立测试集评估与报告", "测试/算法人员", 10, "人天", 2000, null, 0.06, null, null, "检测精度、异常召回、误报和时延报告"],
  [16, "测试交付", "SDK/API及示例程序", "推理工程师", 6, "人天", 2500, null, 0.06, null, null, "输入视频流，输出目标框和异常事件JSON"],
  [17, "测试交付", "项目管理与周报沟通", "项目经理", 6, "人天", 2500, null, 0.06, null, null, "进度、风险、数据问题和阶段评审"],
  [18, "GPU资源", "训练GPU算力", "4090/A800同等级云资源估算", 400, "GPU小时", 15, null, 0.06, null, null, "多轮训练、超参数试验和难例迭代"],
  [19, "GPU资源", "推理压测GPU算力", "同等级云资源估算", 100, "GPU小时", 15, null, 0.06, null, null, "多路视频、帧率和时延压力测试"],
  [20, "GPU资源", "数据存储与备份", "项目周期内预算", 1, "项", 3500, null, 0.06, null, null, "原始视频、抽帧、标签、模型和日志"],
  [21, "测试交付", "现场视频复测与阈值标定", "算法人员", 4, "人天", 2500, null, 0.06, null, null, "基于客户新视频做一次集中标定；不含差旅"],
];

detail.getRange(`A5:L${4 + items.length}`).values = items;
for (let r = 5; r <= 4 + items.length; r++) {
  detail.getRange(`H${r}`).formulas = [[`=E${r}*G${r}`]];
  detail.getRange(`J${r}`).formulas = [[`=H${r}*I${r}`]];
  detail.getRange(`K${r}`).formulas = [[`=H${r}+J${r}`]];
}

const totalRow = 5 + items.length;
detail.mergeCells(`A${totalRow}:G${totalRow}`);
detail.getRange(`A${totalRow}`).values = [["合计"]];
detail.getRange(`H${totalRow}`).formulas = [[`=SUM(H5:H${totalRow - 1})`]];
detail.getRange(`I${totalRow}`).values = [[""]];
detail.getRange(`J${totalRow}`).formulas = [[`=SUM(J5:J${totalRow - 1})`]];
detail.getRange(`K${totalRow}`).formulas = [[`=SUM(K5:K${totalRow - 1})`]];
detail.getRange(`L${totalRow}`).values = [["建议客户报价：视觉算法试点版"]];

detail.getRange(`A5:L${totalRow - 1}`).format = {
  font: { color: "#202B3C", size: 10 },
  verticalAlignment: "center",
  borders: {
    insideHorizontal: { style: "thin", color: "#E7ECF2" },
    bottom: { style: "thin", color: "#E7ECF2" },
  },
};
detail.getRange(`A${totalRow}:L${totalRow}`).format = {
  fill: navy,
  font: { bold: true, color: white },
  verticalAlignment: "center",
  borders: { preset: "outside", style: "medium", color: navy },
};
detail.getRange(`A${totalRow}:L${totalRow}`).format.rowHeight = 30;
detail.getRange(`G5:H${totalRow}`).format.numberFormat = moneyFmt;
detail.getRange(`I5:I${totalRow - 1}`).format.numberFormat = pctFmt;
detail.getRange(`J5:K${totalRow}`).format.numberFormat = moneyFmt;
detail.getRange(`A5:A${totalRow - 1}`).format.horizontalAlignment = "center";
detail.getRange(`E5:F${totalRow - 1}`).format.horizontalAlignment = "center";
detail.getRange(`C5:D${totalRow - 1}`).format.wrapText = true;
detail.getRange(`L5:L${totalRow}`).format.wrapText = true;
detail.freezePanes.freezeRows(4);

const widths = {
  A: 7, B: 13, C: 28, D: 24, E: 10, F: 11,
  G: 14, H: 15, I: 10, J: 14, K: 15, L: 42,
};
for (const [col, width] of Object.entries(widths)) {
  detail.getRange(`${col}:${col}`).format.columnWidth = width;
}
detail.getRange(`5:${totalRow - 1}`).format.rowHeight = 36;

// ------------------------- 报价总览 -------------------------
summary.mergeCells("A1:H1");
summary.getRange("A1").values = [["AI智能错分——视觉模型开发报价评估"]];
summary.getRange("A1:H1").format = {
  fill: navy,
  font: { bold: true, color: white, size: 20 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
summary.getRange("A1:H1").format.rowHeight = 42;
summary.mergeCells("A2:H2");
summary.getRange("A2").values = [["预算日期：2026-07-25 ｜ 方案：单条产线视觉算法试点 ｜ 币种：人民币"]];
summary.getRange("A2:H2").format = {
  fill: cyan,
  font: { color: navy, size: 10 },
  horizontalAlignment: "center",
};

const kpis = [
  ["A4:B4", "A5:B6", "未税报价", `='详细报价'!H${totalRow}`, moneyFmt, blue],
  ["C4:D4", "C5:D6", "税额（6%）", `='详细报价'!J${totalRow}`, moneyFmt, "#6B5DD3"],
  ["E4:F4", "E5:F6", "含税报价", `='详细报价'!K${totalRow}`, moneyFmt, "#0E8A5F"],
  ["G4:H4", "G5:H6", "预计周期", "10–12周", "@", "#B66A00"],
];
for (const [headerRange, valueRange, label, value, format, color] of kpis) {
  summary.mergeCells(headerRange);
  summary.mergeCells(valueRange);
  summary.getRange(headerRange.split(":")[0]).values = [[label]];
  summary.getRange(headerRange).format = {
    fill: color,
    font: { bold: true, color: white, size: 10 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  if (String(value).startsWith("=")) {
    summary.getRange(valueRange.split(":")[0]).formulas = [[value]];
  } else {
    summary.getRange(valueRange.split(":")[0]).values = [[value]];
  }
  summary.getRange(valueRange).format = {
    fill: light,
    font: { bold: true, color: navy, size: 18 },
    numberFormat: format,
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: border },
  };
}

summary.mergeCells("A8:H8");
summary.getRange("A8").values = [["费用构成"]];
summary.getRange("A8:H8").format = {
  fill: navy,
  font: { bold: true, color: white, size: 12 },
  verticalAlignment: "center",
};
summary.getRange("A9:C9").values = [["费用类别", "未税金额", "占比"]];
summary.getRange("A9:C9").format = {
  fill: blue,
  font: { bold: true, color: white },
  horizontalAlignment: "center",
};
const categories = [
  "需求与数据", "人工标注", "数据治理", "核心模型",
  "异常算法", "迭代优化", "测试交付", "GPU资源",
];
summary.getRange("A10:A17").values = categories.map((x) => [x]);
for (let r = 10; r <= 17; r++) {
  summary.getRange(`B${r}`).formulas = [[
    `=SUMIF('详细报价'!$B$5:$B$${totalRow - 1},A${r},'详细报价'!$H$5:$H$${totalRow - 1})`
  ]];
  summary.getRange(`C${r}`).formulas = [[`=B${r}/$B$18`]];
}
summary.getRange("A18").values = [["合计"]];
summary.getRange("B18").formulas = [[`='详细报价'!H${totalRow}`]];
summary.getRange("C18").formulas = [["=SUM(C10:C17)"]];
summary.getRange("A10:C17").format = {
  fill: white,
  borders: {
    insideHorizontal: { style: "thin", color: border },
    bottom: { style: "thin", color: border },
  },
};
summary.getRange("A18:C18").format = {
  fill: navy,
  font: { bold: true, color: white },
};
summary.getRange("B10:B18").format.numberFormat = moneyFmt;
summary.getRange("C10:C18").format.numberFormat = pctFmt;

summary.mergeCells("E9:H9");
summary.getRange("E9").values = [["报价档位建议"]];
summary.getRange("E9:H9").format = {
  fill: blue,
  font: { bold: true, color: white },
  horizontalAlignment: "center",
};
summary.getRange("E10:H10").values = [["档位", "未税预算", "含税预算", "适用范围"]];
summary.getRange("E10:H10").format = {
  fill: cyan,
  font: { bold: true, color: navy },
  horizontalAlignment: "center",
};
summary.getRange("E11:H13").values = [
  ["POC验证版", 158000, 167480, "约2,000帧；离线验证；不承诺生产误报指标"],
  ["试点交付版（推荐）", null, null, "约8,000帧；3类异常；SDK；两轮迭代"],
  ["生产增强版", 589600, 625000, "约12,000–15,000帧；更多现场数据与三轮迭代"],
];
summary.getRange("F12").formulas = [[`='详细报价'!H${totalRow}`]];
summary.getRange("G12").formulas = [[`='详细报价'!K${totalRow}`]];
summary.getRange("F11:G13").format.numberFormat = moneyFmt;
summary.getRange("E11:H13").format = {
  wrapText: true,
  verticalAlignment: "center",
  borders: {
    insideHorizontal: { style: "thin", color: border },
    bottom: { style: "thin", color: border },
  },
};
summary.getRange("E12:H12").format.fill = green;
summary.getRange("E12:H12").format.font = { bold: true, color: navy };
summary.getRange("11:13").format.rowHeight = 42;

summary.mergeCells("E15:H15");
summary.getRange("E15").values = [["报价边界"]];
summary.getRange("E15:H15").format = {
  fill: navy,
  font: { bold: true, color: white },
};
summary.mergeCells("E16:H18");
summary.getRange("E16").values = [[
  "包含：人工标注、标注质检、模型训练、GPU资源、跟踪归属、三类异常算法、模型优化与SDK交付。\n" +
  "不包含：相机/工控机/服务器、WCS/PLC正式联调、管理后台、APP、差旅及Ultralytics商业授权。"
]];
summary.getRange("E16:H18").format = {
  fill: amber,
  font: { color: "#594400", size: 10 },
  wrapText: true,
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: "#E0C46C" },
};

for (const col of ["A", "B", "C", "D", "E", "F", "G", "H"]) {
  summary.getRange(`${col}:${col}`).format.columnWidth = 16;
}
summary.getRange("A:A").format.columnWidth = 18;
summary.getRange("H:H").format.columnWidth = 34;
summary.getRange("4:6").format.rowHeight = 28;

// ------------------------- 范围与验收 -------------------------
scope.mergeCells("A1:G1");
scope.getRange("A1").values = [["视觉模型范围、客户配合与验收建议"]];
scope.getRange("A1:G1").format = {
  fill: navy,
  font: { bold: true, color: white, size: 18 },
  horizontalAlignment: "center",
};
scope.getRange("A3:G3").values = [[
  "模块", "包含内容", "输入要求", "建议验收指标", "前置条件", "不包含", "备注"
]];
scope.getRange("A3:G3").format = {
  fill: blue,
  font: { bold: true, color: white },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
scope.getRange("A4:G7").values = [
  [
    "基础检测",
    "parcel、gate_open、gate_closed、cart_load_area",
    "固定机位、清晰视频、覆盖包裹与门状态",
    "独立测试集：目标检测Precision≥93%、Recall≥90%（建议值）",
    "每类至少500个有效目标框；测试视频不得进入训练集",
    "其他设备缺陷、条码OCR",
    "最终指标需在现场数据统计后写入合同",
  ],
  [
    "开门未落",
    "开门后包裹滞留时间与离开轨迹",
    "原始帧率≥25FPS；正常开门到落件时间分布",
    "事件Recall≥90%、误报率≤5%（建议值）",
    "每类至少50次独立事件；阈值由正常数据标定",
    "PLC机械故障诊断",
    "当前0.6–0.65秒边界样例不足以承诺零误报",
  ],
  [
    "掉错格口",
    "目标格口A与实际轨迹/落点B比较",
    "格口编号、固定ROI；目标格口来自WCS或开门事件",
    "事件Recall≥85%、误报率≤8%（建议值）",
    "必须能确定计划目标格口，且实际落点在画面可见",
    "看不到落点时的结果保证",
    "只看parcel/gate三个框不能证明A→B",
  ],
  [
    "一车多件",
    "同一cart_load_area内多个parcel跟踪ID",
    "小车载物区域标注、完整小车经过画面",
    "事件Recall≥90%、误报率≤5%（建议值）",
    "连续3–5帧满足多件，避免相邻小车同框误报",
    "仅统计全画面包裹数量",
    "必须判断同一辆小车，不采用“同框两件”规则",
  ],
];
scope.getRange("A4:G7").format = {
  wrapText: true,
  verticalAlignment: "top",
  borders: {
    insideHorizontal: { style: "thin", color: border },
    insideVertical: { style: "thin", color: "#EEF1F5" },
    bottom: { style: "thin", color: border },
  },
};
scope.getRange("4:7").format.rowHeight = 88;
const scopeWidths = [16, 31, 31, 29, 34, 23, 36];
for (let i = 0; i < scopeWidths.length; i++) {
  scope.getRangeByIndexes(0, i, 10, 1).format.columnWidth = scopeWidths[i];
}
scope.freezePanes.freezeRows(3);

scope.mergeCells("A9:G9");
scope.getRange("A9").values = [["客户需提供"]];
scope.getRange("A9:G9").format = {
  fill: navy,
  font: { bold: true, color: white },
};
scope.getRange("A10:G13").values = [
  ["1", "原始视频：不同班次、光照、包裹材质，以及正常与异常事件视频", "", "", "", "", ""],
  ["2", "业务真值：异常类型、发生时间、目标格口、实际格口、小车编号", "", "", "", "", ""],
  ["3", "现场规则：正常落件时间范围、报警延迟上限、误报容忍度", "", "", "", "", ""],
  ["4", "验收数据：与训练集独立的视频批次，每类异常建议不少于50次", "", "", "", "", ""],
];
scope.mergeCells("B10:G10");
scope.mergeCells("B11:G11");
scope.mergeCells("B12:G12");
scope.mergeCells("B13:G13");
scope.getRange("A10:G13").format = {
  fill: light,
  wrapText: true,
  verticalAlignment: "center",
  borders: {
    insideHorizontal: { style: "thin", color: border },
    bottom: { style: "thin", color: border },
  },
};
scope.getRange("10:13").format.rowHeight = 32;

// ------------------------- 依据与说明 -------------------------
sources.mergeCells("A1:F1");
sources.getRange("A1").values = [["报价依据与风险说明"]];
sources.getRange("A1:F1").format = {
  fill: navy,
  font: { bold: true, color: white, size: 18 },
  horizontalAlignment: "center",
};
sources.getRange("A3:F3").values = [["项目", "数值/结论", "性质", "来源", "日期", "说明"]];
sources.getRange("A3:F3").format = {
  fill: blue,
  font: { bold: true, color: white },
  horizontalAlignment: "center",
};
sources.getRange("A4:F8").values = [
  [
    "当前样本基础",
    "10张人工黄金样本；123帧同场景模型辅助预标注",
    "项目现状",
    "/Users/lixing.guo/Documents/机械臂/datasets/sorting_video_123_annotated_v1",
    "2026-07-25",
    "不足以直接承诺生产级误报率，报价包含扩充到约8,000帧",
  ],
  [
    "GPU小时单价",
    "¥15/GPU小时",
    "预算假设",
    "云资源供应商正式询价前的预算占位",
    "2026-07-25",
    "实际按选定GPU型号、区域、包月/按量价格调整",
  ],
  [
    "Ultralytics商业许可",
    "未计入本报价",
    "许可证风险",
    "https://www.ultralytics.com/license",
    "2026-07-25",
    "官方说明：闭源商业部署通常需要Enterprise License，或整个项目遵循AGPL-3.0开源要求",
  ],
  [
    "税率",
    "6%",
    "预算假设",
    "软件开发及技术服务预算口径",
    "2026-07-25",
    "最终以合同主体、开票内容和财税确认结果为准",
  ],
  [
    "报价有效期",
    "30天",
    "商务假设",
    "本预算表",
    "2026-07-25",
    "数据规模、异常类别或验收指标变化时需重新估价",
  ],
];
sources.getRange("A4:F8").format = {
  wrapText: true,
  verticalAlignment: "top",
  borders: {
    insideHorizontal: { style: "thin", color: border },
    insideVertical: { style: "thin", color: "#EEF1F5" },
    bottom: { style: "thin", color: border },
  },
};
sources.getRange("4:8").format.rowHeight = 62;
const sourceWidths = [22, 32, 17, 55, 15, 58];
for (let i = 0; i < sourceWidths.length; i++) {
  sources.getRangeByIndexes(0, i, 12, 1).format.columnWidth = sourceWidths[i];
}

sources.mergeCells("A10:F10");
sources.getRange("A10").values = [["重要商务说明"]];
sources.getRange("A10:F10").format = {
  fill: navy,
  font: { bold: true, color: white },
};
sources.getRange("A11:F14").values = [
  ["1", "本报价是预算评估，不构成对“零误报”的承诺。", "", "", "", ""],
  ["2", "建议先签POC或试点阶段；客户正式立项后，以现场勘察和数据清单更新工作量。", "", "", "", ""],
  ["3", "若客户无法提供目标格口/实际格口真值，掉错格口只能输出轨迹异常候选。", "", "", "", ""],
  ["4", "若采用非Ultralytics、许可证更宽松的检测框架，需重新验证精度和开发工作量。", "", "", "", ""],
];
for (let r = 11; r <= 14; r++) sources.mergeCells(`B${r}:F${r}`);
sources.getRange("A11:F14").format = {
  fill: r => r,
  wrapText: true,
  borders: {
    insideHorizontal: { style: "thin", color: border },
    bottom: { style: "thin", color: border },
  },
};
sources.getRange("A11:F14").format.fill = red;
sources.getRange("11:14").format.rowHeight = 32;

await fs.mkdir(outputDir, { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(outputFile);

for (const sheetName of ["报价总览", "详细报价", "范围与验收", "依据与说明"]) {
  const preview = await wb.render({ sheetName, autoCrop: "all", scale: 1.2, format: "png" });
  const bytes = new Uint8Array(await preview.arrayBuffer());
  await fs.writeFile(`${outputDir}/${sheetName}.png`, bytes);
}

const tableInspect = await wb.inspect({
  kind: "table",
  range: `详细报价!A4:L${totalRow}`,
  include: "values,formulas",
  tableMaxRows: 30,
  tableMaxCols: 12,
  maxChars: 12000,
});
console.log(tableInspect.ndjson);

const errorInspect = await wb.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errorInspect.ndjson);
console.log(outputFile);
