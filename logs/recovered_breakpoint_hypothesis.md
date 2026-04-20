# 断点回归假设数据备份

**从日志恢复的时间**: 2026-04-14

## 完整假设数据

```json
{
  "title": "基于断点回归设计的肿瘤免疫微环境时空演化因果图谱",
  "core_problem": "肿瘤免疫微环境研究存在严重的'幸存者偏差'。现有横断面研究混淆了'时间'与'效应'，无法区分是免疫浸润导致了肿瘤退缩，还是肿瘤退缩招募了免疫细胞。",
  "core_hypothesis": "免疫治疗（如PD-1阻断）构成了一个严酷的'自然实验'。利用治疗起效的精确时间点作为断点，可以识别出真正的因果驱动细胞亚群。",
  "technical_route": "数据：非小细胞肺癌免疫治疗scRNA-seq队列；方法：模糊断点回归（Fuzzy RDD）、事件史分析、逆概率加权（IPW）。",
  "expected_breakthrough": "构建首张'因果'而非'相关'的肿瘤免疫互作图谱，剔除治疗无效者的背景噪声，锁定响应者特有的细胞动力学特征。",
  "clinical_value": "精准识别免疫治疗真正的获益人群，预测假性进展和超进展风险。",
  "statistical_novelty": "本研究的统计学核心在于利用断点回归（RDD）处理纵向生物医学数据中的内生性。在免疫治疗响应分析中，'响应'本身不��随机分配的，而是与肿瘤抗原性高度相关。RDD通过比较断点（响应发生时刻）两侧无限接近的样本，局部实现了'准随机实验'假设。我们结合非参数估计（局部多项式回归）来精确估计处理效应，避免参数模型设定的误判，并利用McCrary密度检验检验断点处的操纵性，确保因果识别的有效性。",
  "internal_reasoning": "时序混淆分析：大多数bulk测序分析将时间点混在一起，实际上是把'起因'和'结果'混合平均了。RDD能利用时间维度的突变剥离因果。",
  "crack_mode": "矛盾点突破",
  "paradigm_framework": "计量经济学（RDD） + 轨迹推断",
  "data_requirements": "接受免疫检查点抑制剂治疗的NSCLC患者的多时间点scRNA-seq数据",
  "search_queries": [
    "immunotherapy response AND regression discontinuity",
    "tumor microenvironment AND causal inference",
    "single-cell RNA-seq AND longitudinal analysis"
  ]
}
```

## 字段映射说明

当此假设返回给前端UI时，将进行以下字段映射：

| HypothesisAgent 输出 | 前端 UI 读取 |
|---------------------|-------------|
| technical_route | → description |
| core_hypothesis | → rationale |
| expected_breakthrough | → novelty |
| clinical_value | → expected_value |
| paradigm_framework | → paradigm_framework (匹配) |
| (从core_problem生成) | → grand_challenge |

## 使用方法

如果需要手动将此假设导入系统，请在前端UI的数据库中创建一条新记录，使用上述字段映射后的数据。
