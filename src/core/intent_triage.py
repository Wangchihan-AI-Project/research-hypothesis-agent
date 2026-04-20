# -*- coding: utf-8 -*-
"""
V7.3 意图分诊器 (Intent Triage Agent)

核心功能：
1. 接收红方攻击原始文本
2. 使用 LLM 语义分析映射到风险矩阵
3. 返回定向防御协议

作者: V7.3 发版工程师
日期: 2026-04-18
"""

import os
import json
from enum import Enum
from typing import List, Dict, Optional
from dotenv import load_dotenv
from pathlib import Path

# 加载环境变量
project_root = Path(__file__).parent.parent.parent
env_file = project_root / '.env'
if env_file.exists():
    load_dotenv(env_file, encoding='utf-8')


class RiskCategory(Enum):
    """风险矩阵枚举"""
    LEAKAGE = "LEAKAGE"           # 数据穿透、预处理、时空相关性
    BIAS = "BIAS"                 # 样本代表性、序列冗余、选择偏差
    INTERPRETABILITY = "INTERPRETABILITY"  # 黑盒模型、不可解释性
    OVERFITTING = "OVERFITTING"   # 过拟合风险
    VALIDATION = "VALIDATION"     # 验证策略问题
    UNKNOWN = "UNKNOWN"           # 未分类


class DefenseProtocol:
    """定向防御协议"""

    # V7.3 防御模板库 (The Defense Armory - ML 专项版)
    DEFENSE_PROTOCOL_MAP = {
        RiskCategory.LEAKAGE: {
            "name": "数据泄漏防御协议 (ML 专项)",
            "mandatory_injections": [
                "基于 Scaffold 的样本划分策略 (Scaffold Splitting)",
                "嵌套交叉验证 (Nested Cross-Validation)",
                "分子指纹相似性过滤: 训练集与测试集 Tanimoto 系数 < 0.3"
            ],
            "technical_safeguards_template": {
                "data_leak_prevention": {
                    "scaffold_splitting": "使用基于 Bemis-Murcko Scaffold 的划分策略，确保训练集和测试集在化学骨架上完全独立，避免序列同源性导致的泄漏",
                    "similarity_filtering": "计算分子间的 Tanimoto 相似度，移除与测试集相似度 > 0.3 的训练样本",
                    "nested_cv": "外层5折评估泛化性能，内层5折优化超参数，两层完全独立",
                    "pipeline_integration": "使用 scikit-learn Pipeline 确保预处理与模型训练在同一 CV 折叠内执行"
                }
            }
        },

        RiskCategory.INTERPRETABILITY: {
            "name": "可解释性防御协议 (ML 专项)",
            "mandatory_injections": [
                "Integrated Gradients (集成梯度) 归因分析",
                "Attention Map 可视化",
                "SHAP 值二级验证"
            ],
            "technical_safeguards_template": {
                "interpretability_framework": {
                    "integrated_gradients": "使用 Integrated Gradients 方法对 GNN 的预测进行归因，将梯度映射回原子级别的物理贡献，识别关键结合位点",
                    "attention_visualization": "对跨模态 Transformer 的 Attention 权重进行可视化，揭示模型关注的蛋白质区域和配体特征",
                    "shap_verification": "使用 SHAP (Shapley Additive Explanations) 作为二级验证，确保归因结果的稳健性",
                    "biophysical_validation": "将模型识别的关键残基与已知晶体结构和结合数据进行交叉验证"
                }
            }
        },

        RiskCategory.OVERFITTING: {
            "name": "过拟合防御协议",
            "mandatory_injections": [
                "Dropout (p=0.3) + L2正则化",
                "早停机制 (Early Stopping)",
                "独立验证集监控"
            ],
            "technical_safeguards_template": {
                "overfitting_prevention": {
                    "regularization": "Dropout (p=0.3) + L2正则化 (λ=1e-4) + Batch Normalization",
                    "early_stopping": "设置耐心值 (patience=10)，当验证损失连续 10 轮不下降时触发早停",
                    "validation_strategy": "预留 20% 独立验证集，仅在最终评估时使用",
                    "model_complexity_control": "限制 VAE 潜在维度 ≤ 128，防止模型参数过度拟合训练数据"
                }
            }
        },

        RiskCategory.VALIDATION: {
            "name": "验证策略防御协议",
            "mandatory_injections": [
                "分层 K-Fold 交叉验证",
                "时间感知分割 (Time-Aware Split)",
                "阴性对照实验"
            ],
            "technical_safeguards_template": {
                "validation_protocol": {
                    "stratified_kfold": "使用分层 K-Fold (K=5)，确保每折中阳性/阴性样本比例一致",
                    "time_aware_split": "对时序数据按时间戳排序，训练集使用早期数据，测试集使用最新数据",
                    "negative_controls": "设计阴性对照实验（如随机打乱标签），验证模型不会学到虚假关联",
                    "seed_control": "固定随机种子 (seed=42)，确保实验可复现"
                }
            }
        },

        RiskCategory.UNKNOWN: {
            "name": "通用防御协议",
            "mandatory_injections": [
                "标准交叉验证",
                "基础可解释性分析",
                "统计显著性检验"
            ],
            "technical_safeguards_template": {
                "general_safeguards": {
                    "cross_validation": "使用标准 K-Fold 交叉验证 (K=5)",
                    "statistical_validation": "对所有关键指标进行统计显著性检验 (p < 0.05)",
                    "reproducibility": "记录所有超参数和随机种子，确保实验可复现"
                }
            }
        }
    }

    @classmethod
    def get_protocol(cls, category: RiskCategory) -> Dict:
        """获取指定风险类别的防御协议"""
        return cls.DEFENSE_PROTOCOL_MAP.get(category, cls.DEFENSE_PROTOCOL_MAP[RiskCategory.UNKNOWN])


class IntentTriageAgent:
    """V7.3 意图分诊智能体"""

    def __init__(self):
        self.agent_name = "V7.3_Intent_Triage_Agent"
        # 使用极速推理模型
        self.model = os.getenv("TRIAGE_MODEL", "gemini-2.0-flash-exp")
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

    def triage_red_attack_semantic(self, red_attack_text: str) -> List[RiskCategory]:
        """
        意图分诊：将红方攻击文本映射到风险矩阵

        Args:
            red_attack_text: 红方攻击原始文本

        Returns:
            List[RiskCategory]: 检测到的风险类别列表（可能多个）
        """
        if not red_attack_text or len(red_attack_text.strip()) < 10:
            return [RiskCategory.UNKNOWN]

        # 构建分诊提示词
        prompt = self._build_triage_prompt(red_attack_text)

        try:
            # 调用 LLM 进行语义分析
            result = self._call_llm(prompt)

            # 解析结果
            categories = self._parse_triage_result(result)
            print(f"[V7.3 意图分诊] 红方攻击 → {categories}")

            return categories if categories else [RiskCategory.UNKNOWN]

        except Exception as e:
            print(f"[V7.3 意图分诊] 分析失败，回退到默认: {e}")
            return [RiskCategory.UNKNOWN]

    def _build_triage_prompt(self, red_attack_text: str) -> str:
        """构建分诊提示词"""
        return f"""你是 V7.3 意图分诊系统（ML 专项版）。请将以下红方攻击内容映射到风险矩阵。

## 红方攻击内容
{red_attack_text[:2000]}

## 风险矩阵定义（ML 专项）
1. **LEAKAGE** - 数据穿透、预处理泄漏、序列同源性（Homology）、训练测试集重叠、Scaffold 泄漏、分子结构相似性穿越
2. **BIAS** - 样本代表性不足、序列冗余、选择偏差、混杂因素、数据集不平衡
3. **INTERPRETABILITY** - 黑盒模型、缺乏可解释性、归因分析缺失、物理可解释性不足
4. **OVERFITTING** - 过拟合风险、泛化能力不足、模型复杂度过高
5. **VALIDATION** - 验证策略问题、交叉验证缺失、Scaffold Splitting 缺失

## 输出要求
请以 JSON 格式输出检测到的风险类别（最多3个）：
```json
{{
  "detected_risks": ["LEAKAGE", "BIAS"],
  "confidence": 0.85,
  "reasoning": "简短理由"
}}
```

如果攻击内容不涉及任何风险类别，返回 UNKNOWN。"""

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM（支持 Anthropic 和 Gemini）"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        base_url = os.getenv("ANTHROPIC_BASE_URL")

        if api_key and base_url:
            # 使用 Anthropic Claude
            import anthropic
            client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
            response = client.messages.create(
                model=os.getenv("MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        else:
            # 回退到简单关键词匹配
            return self._fallback_keyword_matching(prompt)

    def _fallback_keyword_matching(self, prompt: str) -> str:
        """回退：基于关键词的快速匹配（V7.3 优化版：带评分机制）"""
        prompt_lower = prompt.lower()
        detected_scores = {}

        # V7.3 ML 专项关键词扩展（高权重在前）
        keywords_map = {
            RiskCategory.LEAKAGE: [
                # 高权重 - ML 核心术语
                ('同源性', 3), ('homology', 3), ('序列同源', 3),
                ('scaffold splitting', 3), ('scaffold split', 3),
                # 中权重
                ('scaffold', 2), ('分子相似', 2), ('结构相似', 2),
                # 常规术语
                ('泄漏', 1), ('泄露', 1), ('穿越', 1), ('temporal', 1),
                ('future', 1), ('预处理', 1), ('isolation', 1), ('leak', 1),
                ('训练测试', 1), ('train test overlap', 1), ('数据泄露', 1),
                ('信息泄露', 1), ('相似性穿越', 1)
            ],
            RiskCategory.BIAS: [
                # 高权重
                ('选择偏倚', 2), ('class imbalance', 2), ('样本偏斜', 2),
                # 中权重
                ('数据不平衡', 1.5), ('imbalanced', 1.5),
                # 常规术语
                ('偏差', 1), ('bias', 1), ('冗余', 1), ('redundant', 1),
                ('代表性', 1), ('representative', 1), ('混杂', 1), ('confounding', 1)
            ],
            RiskCategory.INTERPRETABILITY: [
                # 高权重 - ML 可解释性核心
                ('integrated gradients', 3), ('归因分析', 2), ('attribution', 2),
                ('物理可解释', 2), ('可解释性', 1.5),
                # 中权重
                ('shap', 2), ('lime', 2), ('attention map', 2),
                # 常规术语
                ('可解释', 1), ('interpret', 1), ('黑盒', 1), ('black box', 1),
                ('explain', 1), ('透明性', 1), ('attention', 1), ('梯度', 1),
                ('gradient', 1), ('贡献度', 1), ('contribution', 1)
            ],
            RiskCategory.OVERFITTING: [
                # 高权重
                ('过拟合风险', 2), ('泛化能力', 2),
                # 中权重
                ('模型复杂', 1.5), ('欠拟合', 1.5), ('underfit', 1.5),
                # 常规术语
                ('过拟合', 1), ('overfit', 1), ('泛化', 1), ('generalization', 1)
            ],
            RiskCategory.VALIDATION: [
                # 高权重
                ('scaffold split', 2), ('分层抽样', 2), ('stratified', 2),
                # 中权重
                ('交叉验证', 1), ('cross validation', 1), ('k-fold', 1),
                # 常规术语（低权重避免误触发）
                ('cv', 0.5), ('验证集', 0.5), ('测试集', 0.5)
            ]
        }

        # 计算每个类别的得分
        for category, weighted_keywords in keywords_map.items():
            score = 0
            matched_keywords = []
            for keyword, weight in weighted_keywords:
                if keyword in prompt_lower:
                    score += weight
                    matched_keywords.append(f"{keyword}({weight})")
            if score > 0:
                detected_scores[category] = {'score': score, 'matches': matched_keywords}

        # 只保留得分 ≥1.5 的类别，并最多返回前3个
        filtered = {k: v for k, v in detected_scores.items() if v['score'] >= 1.5}
        sorted_categories = sorted(filtered.items(), key=lambda x: x[1]['score'], reverse=True)[:3]

        detected = [cat.value for cat, _ in sorted_categories]

        # 调试输出
        print(f"[V7.3 关键词匹配] 检测得分: {[(cat.value, info['score']) for cat, info in sorted_categories]}")

        result = {
            "detected_risks": detected if detected else ["UNKNOWN"],
            "confidence": 0.7,
            "reasoning": "关键词匹配回退"
        }
        return json.dumps(result)

    def _parse_triage_result(self, result: str) -> List[RiskCategory]:
        """解析 LLM 返回结果"""
        try:
            # 提取 JSON
            import re
            json_match = re.search(r'\{[^{}]*\}', result, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                risks = data.get("detected_risks", ["UNKNOWN"])
                return [RiskCategory[r] for r in risks if r in RiskCategory.__members__]
        except Exception as e:
            print(f"[V7.3 意图分诊] 解析失败: {e}")

        return [RiskCategory.UNKNOWN]


def triage_red_attack_semantic(red_attack_text: str) -> List[RiskCategory]:
    """
    V7.3 意图分诊入口函数

    Args:
        red_attack_text: 红方攻击原始文本

    Returns:
        List[RiskCategory]: 检测到的风险类别
    """
    agent = IntentTriageAgent()
    return agent.triage_red_attack_semantic(red_attack_text)


def build_defense_injection(categories: List[RiskCategory]) -> str:
    """
    V7.3 定向防御注入构建器

    根据检测到的风险类别，生成对应的防御注入文本

    Args:
        categories: 风险类别列表

    Returns:
        str: 防御注入文本
    """
    if not categories:
        return ""

    injection_parts = []
    injection_parts.append("### 🛡️ 【V7.3 定向防御协议】（强制执行）\n")
    injection_parts.append("**红方攻击检测 → 系统自动锁定风险类别并生成防御方案**\n\n")

    for category in categories:
        protocol = DefenseProtocol.get_protocol(category)

        injection_parts.append(f"#### 📋 {protocol['name']}\n")
        injection_parts.append("**必须注入的技术措施：**\n")

        for injection in protocol['mandatory_injections']:
            injection_parts.append(f"- {injection}\n")

        injection_parts.append("\n**技术防范措施模板：**\n")
        injection_parts.append(f"```json\n{json.dumps(protocol['technical_safeguards_template'], ensure_ascii=False, indent=2)}\n```\n\n")

    injection_parts.append("**⚠️ 硬性要求：**\n")
    injection_parts.append("- 必须在 JSON 假说的 `methodology.technical_safeguards` 字段中包含上述所有技术措施\n")
    injection_parts.append("- 不得省略任何一项强制注入的技术方案\n")
    injection_parts.append("- 这些措施是你的假设通过防御委员会答辩的必要条件\n\n")

    return "".join(injection_parts)
