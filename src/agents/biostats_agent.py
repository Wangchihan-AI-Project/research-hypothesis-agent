# -*- coding: utf-8 -*-
"""
生物统计��专家智能体 (BiostatsAgent - 强化统计防御性指标版)
极度严谨的高级生物统计学家与因果推断专家

核心身份 (CORE MANDATE):
- **因果推断严密性**: 从相关到因果，追求统计推断的最高标准
- **偏倚控制 (Bias Control)**: 识别、量化、校正所有潜在偏倚
- **因果稳健性 (Causal Robustness)**: E-value敏感性分析，验证结论对未测量混杂的耐受度
- **一票否决权**: 在验证阶段，对统计逻辑拥有"一票否决权"

核心评估标准 (学术三要素):
- **新颖性 (Novelty)**: 统计方法或框架是否有创新
- **严谨性 (Rigor)**: 因果推断是否严密，偏倚控制是否到位
- **颠覆性 (Disruptiveness)**: 是否挑战现有统计范式

绝对红线:
- 禁止为了"凑数据"而放松统计标准
- 禁止忽视数据泄漏、选择性报告等统计陷阱
- 每个因果结论必须经过E-value敏感性分析

职责范围:
1. 外部独立队列验证设计
2. 蒙特卡洛模拟与统计功效计算（强制）
3. 反事实推断与因果图构建
4. 敏感性分析（E-value计算 - 强制）
5. 多重假设检验校正（FDR/Bonferroni - 强制）
6. 数据穿越检测与预防
"""
from typing import Dict, List, Optional, Any
import json
import sys
import os
import re
import time
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import BaseAgent
import anthropic
from utils.llm_utils import SafeExtractor, LLMParseError
from utils.modality_aware_preprocessing import (
    ModalityDetector,
    ModalityAwarePreprocessor,
    MediationAnalysisValidator,
    validate_mediation_analysis
)


# ============ 生物统计学前沿技术栈 ============

BIOSTATS_TECH_STACK = {
    'causal_inference': {
        'methods': {
            'Pearls_Causal_Framework': 'Pearl因果层级与do-calculus',
            'Potential_Outcomes': 'Rubin潜在结果框架',
            'Propensity_Score': '倾向性评分匹配/加权/分层',
            'Instrumental_Variable': '工具变量估计',
            'Difference_in_Differences': '双重差分法',
            'Regression_Discontinuity': '断点回归设计',
            'Mediation_Analysis': '中介效应分析',
            'Negative_Control': '阴性对照结局/暴露'
        },
        'dag_learning': {
            'PC_Algorithm': 'Peter-Clark因果发现算法',
            'FCI_Algorithm': '快速因果推断',
            'GES': '贪密等价搜索',
            'DAGitty': 'DAG绘制工具',
            'dagitty': 'R包实现'
        }
    },
    'bias_analysis': {
        'selection_bias': {
            'Heckman_correction': 'Heckman选择模型',
            'Inverse_Probability_Weighting': '逆概率加权'
        },
        'measurement_error': {
            'Regression_Calibration': '回归校准',
            'SIMEX': '模拟外推法',
            'Bayesian_Measurement_Error': '贝叶斯测量误差模型'
        },
        'confounding': {
            'Backdoor_Criterion': '后门准则',
            'Frontdoor_Criterion': '前门准则',
            'Negative_Control_Outcome': '阴性对照结局'
        },
        'sensitivity_analysis': {
            'Evalue': 'E-value敏感性分析',
            'Rosenbaum_Bounds': 'Rosenbaum界限',
            'Monte_Carlo_Sensitivity': '蒙特卡洛敏感性分析',
            'Tipping_Point': 'tipping point分析'
        }
    },
    'power_analysis': {
        'methods': {
            'Power_Sample_Size': '传统功效分析',
            'Simulation_Based': '基于模拟的功效分析',
            'Bayesian_Power': '贝叶斯功效分析',
            'Conditional_Power': '条件功效（期中分析）',
            'Adaptive_Design': '适应性设计'
        },
        'software': {
            'GPower': '功效分析软件',
            'powerMediation': 'R中介效应功效',
            'pwr': 'R基础功效包',
            'simr': 'R混合模型功效'
        }
    },
    'multiple_testing': {
        'correction_methods': {
            'Bonferroni': 'Bonferroni校正（保守）',
            'Holm': 'Holm逐步校正',
            'BH_FDR': 'Benjamini-Hochberg FDR',
            'BY_FDR': 'Benjamini-Yekutieli FDR（保守）',
            'Storey_q': 'Storey q-value',
            'Permutation': '置换检验'
        }
    },
    'validation': {
        'external_validation': {
            'Independent_Cohort': '独立外部队列验证',
            'Temporal_Validation': '时间序列验证',
            'Geographic_Validation': '地理跨中心验证',
            'Cross_Validation': 'K折交叉验证',
            'Bootstrap': 'Bootstrap自助法',
            'Nested_CV': '嵌套交叉验证（防数据泄漏）'
        },
        'leakage_prevention': {
            'Train_Test_Split': '按时间/患者分割',
            'Feature_Selection_Within_CV': 'CV内特征选择',
            'Clustering_Aware_Split': '聚类感知分割',
            'GroupKFold': '分组K折（防同一样本泄漏）'
        }
    },
    'survival_analysis': {
        'methods': {
            'Kaplan_Meier': 'Kaplan-Meier生存曲线',
            'Cox_Regression': 'Cox比例风险模型',
            'Competing_Risks': '竞争风险模型',
            'Time_Dependent_Covariates': '时变协变量',
            'Joint_Modeling': '联合模型（纵向+生存）'
        }
    }
}


class BiostatsAgent(BaseAgent):
    """
    生物统计学专家智能体（强化版）

    角色：极度严谨的高级生物统计学家与因果推断专家
    专长：因果推断、偏倚控制、E-value敏感性分析、因果稳健性

    Core Mandate:
    - 因果推断严密性: 从相关到因果
    - 偏倚控制 (Bias Control): 识别、量化、校正所有潜在偏倚
    - 因果稳健性 (Causal Robustness): E-value敏感性分析
    - 一票否决权: 在验证阶段，对统计逻辑拥有"一票否决权"
    """

    def __init__(self):
        super().__init__("生物统计学专家", agent_type="biostats")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.max_retries = 3
        self.model = os.getenv("BIOSTATS_MODEL", "claude-opus-4-6")
        self.extractor = SafeExtractor()

    def execute(self, input_data: Dict) -> Dict:
        """
        执行生物统计学验证框架设计

        Args:
            input_data: {
                'hypothesis_data': dict - 假设数据
                'genai_proposal': str - GenAI架构方案
                'compbio_proposal': str - 计算生物学方案
                'pathology_proposal': str - 数字病理学方案
                'output_dir': str - 输出目录
            }

        Returns:
            {
                'success': bool,
                'biostats_proposal': str - 生物统计学方案
                'validation_framework': dict - 验证框架设计
                'defensive_metrics': dict - 防御性指标（E-value/Power/FDR）
                'report_path': str - 报告保存路径
            }
        """
        hypothesis_data = input_data.get('hypothesis_data', {})
        genai_proposal = input_data.get('genai_proposal', '')
        compbio_proposal = input_data.get('compbio_proposal', '')
        pathology_proposal = input_data.get('pathology_proposal', '')
        output_dir = input_data.get('output_dir', 'reports')

        if not hypothesis_data:
            raise ValueError('缺少假设数据 (hypothesis_data)')

        print(f"[生物统计学专家] 开始设计验证框架，假设: {hypothesis_data.get('title', 'Unknown')}")

        # 使用重试机制生成生物统计学方案
        biostats_proposal = None
        for attempt in range(self.max_retries):
            try:
                print(f"[生物统计学专家] 第 {attempt + 1}/{self.max_retries} 次尝试生成方案...")
                biostats_proposal = self._generate_biostats_proposal(
                    hypothesis_data=hypothesis_data,
                    genai_proposal=genai_proposal,
                    compbio_proposal=compbio_proposal,
                    pathology_proposal=pathology_proposal
                )

                # 验证方案内容不为空且足够详细
                if not biostats_proposal or len(biostats_proposal.strip()) < 500:
                    raise ValueError(f"生成的方案内容过短: {len(biostats_proposal) if biostats_proposal else 0} 字符")

                print(f"[生物统计学专家] 方案生成成功，长度: {len(biostats_proposal)} 字符")
                break

            except ValueError as ve:
                print(f"[生物统计学专家] 验证失败: {ve}")
                if attempt == self.max_retries - 1:
                    raise ValueError(f"经过 {self.max_retries} 次尝试后仍无法生成有效方案: {ve}")

            except Exception as e:
                print(f"[生物统计学专家] 生成失败: {type(e).__name__}: {e}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"经过 {self.max_retries} 次尝试后仍无法生成方案: {e}")

        # 验证最终结果
        if not biostats_proposal or len(biostats_proposal.strip()) < 500:
            raise ValueError("生成的生物统计学方案为空或过短，无法保存")

        # 保存方案
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"Biostats_ValidationFramework_{timestamp}.md")

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(biostats_proposal)

        print(f"[生物统计学专家] 方案已保存到: {report_path}")

        # 提取结构化验证框架和防御性指标
        validation_framework = self._extract_validation_framework(biostats_proposal)
        defensive_metrics = self._extract_defensive_metrics(biostats_proposal)

        return {
            'success': True,
            'biostats_proposal': biostats_proposal,
            'validation_framework': validation_framework,
            'defensive_metrics': defensive_metrics,  # 新增：防御性指标
            'report_path': report_path
        }

    def _generate_biostats_proposal(self, hypothesis_data: dict,
                                     genai_proposal: str,
                                     compbio_proposal: str,
                                     pathology_proposal: str) -> str:
        """生成生物统计学方案 - 调用 LLM API"""
        title = hypothesis_data.get('title', '未命名研究')
        paradigm = hypothesis_data.get('paradigm_framework', '')
        description = hypothesis_data.get('description', '')
        challenge = hypothesis_data.get('grand_challenge', '')

        # ========== 模态感知预处理协议生成 ==========
        # 1. 检测数据模态
        combined_text = f"{title} {paradigm} {description} {challenge}"
        modality_info = ModalityDetector.detect_modality(combined_text)

        print(f"[模态检测] 主要模态: {modality_info['primary_modality']}")
        if modality_info['is_adni']:
            print(f"[模态检测] 检测到 ADNI 数据，启用专用预处理流程")
        elif modality_info['is_single_cell']:
            print(f"[模态检测] 检测到单细胞数据，启用严格隔离预处理流程")
        elif modality_info['is_neuro_imaging']:
            print(f"[模态检测] 检测到神经影像数据，启用影像预处理流程")

        # 2. 生成模态匹配的预处理协议
        preprocessing_protocol = ModalityAwarePreprocessor.generate_preprocessing_protocol(
            modality_info, hypothesis_data
        )

        # 3. 生成 Bootstrap 中介分析代码
        mediation_code = MediationAnalysisValidator.get_bootstrap_mediation_code()

        # 构建上游上下文（完整版 - 确保信息完整性）
        upstream_context = f"""
上游方案摘要：
- GenAI架构: {genai_proposal[:2000] if genai_proposal else '未提供'}...
- 计算生物学: {compbio_proposal[:2000] if compbio_proposal else '未提供'}...
- 数字病理学: {pathology_proposal[:2000] if pathology_proposal else '未提供'}...
"""

        # 构建 Prompt（强化版）
        prompt = f"""你是一位**SOTA级别生物统计学家与因果推断专家**（State-of-the-Art Biostatistician & Causal Inference Expert）。

# CORE MANDATE (核心使命)

你的核心使命是**追求因果推断的学术巅峰**，而非满足任何比例约束。

## 评估标准 (学术三要素)

1. **新颖性 (Novelty)**: 统计方法或框架是否有创新
2. **严谨性 (Rigor)**: 因果推断是否严密，偏倚控制是否到位
3. **颠覆性 (Disruptiveness)**: 是否挑战现有统计范式

## 核心技能

- **因果推断**: DAG因果图构建、Pearl do-calculus、后门准则、倾向性评分、工具变量
- **偏倚控制**: 识别、量化、校正所有潜在偏倚（混杂、选择偏倚、测量误差）
- **因果稳健性**: E-value敏感性分析、Rosenbaum界限、tipping point
- **外部验证**: 独立队列设计、地理/时间跨中心验证、嵌套交叉验证（防数据泄漏）
- **功效分析**: 样本量计算、蒙特卡洛模拟、贝叶斯功效、适应性设计
- **多重检验校正**: FDR/Bonferroni/Holm、置换检验
- **数据泄漏防护**: CV内特征选择、GroupKFold、聚类感知分割

## 绝对红线

- **绝不为了"凑数据"放松统计标准**
- **绝不忽视数据泄漏、选择性报告等统计陷阱**
- **每个因果结论必须经过E-value敏感性分析**

---

# 研究假设信息

**标题**: {title}

**范式框架**: {paradigm}

**核心假设**: {description}

**重大挑战**: {challenge}

{upstream_context}

---

## 【模态感知预处理协议】（已自动检测数据类型：{modality_info['primary_modality']}）

{preprocessing_protocol}

---

## 【因果中介分析金标准】（Bootstrap实现）

{mediation_code}

---

# 任务：设计SOTA级别因果推断验证框架

请生成一份**追求学术巅峰的生物统计学验证框架方���**（Markdown格式）。

## 核心原则

1. **因果优先**: 从相关到因果，追求统计推断的最高标准
2. **偏倚控制**: 识别、量化、校正所有潜在偏倚
3. **稳健性验证**: 每个因果结论必须经过E-value敏感性分析
4. **一票否决权**: 在验证阶段，对统计逻辑拥有"一票否决权"

---

## 【强制要求】因果推断防御性指标 (Causal Inference Defensive Metrics)
**以下三项为强制输出，缺一不可**

### 0.1 E-value 计算与敏感性分析
- **E-value定义**：为使观察到的效应大小不再显著，所需的未测量混杂因素与暴露及结局关联的最小强度
- **强制计算**：给出主要终点效应量对应的E-value
- **解读标准**：
  - E-value > 1.0：较强的结果，能耐受相当强度的未测量混杂
  - E-value ≈ 1.0：结果对未测量混杂较为敏感
  - E-value < 1.0：结果非常脆弱，轻微的未测量混杂即可推翻结论
- **敏感性分析场景**：列出需要计算E-value的具体场景
- **代码实现**：使用R的EValue包或手动计算公式

### 0.2 统计功效分析 (Power Analysis)
- **A priori功效计算**：研究设计前的样本量估算
  - 效应量假设（HR、Cohen's d、OR等）
  - α水平（通常0.05，双侧）
  - 目标功效（通常80%或90%）
  - 计算所需样本量
- **Post-hoc功效验证**：基于实际样本量的功效复核
- **蒙特卡洛模拟**：使用模拟验证假设的功效
- **适应性设计考虑**：期中分析、样本量重估计
- **代码实现**：R的pwr包或GPower

### 0.3 多重假设检验校正 (FDR Correction)
- **识别检验场景**：明确列出所有涉及多重检验的分析环节
- **校正方法选择**：
  - FDR（Benjamini-Hochberg）：适用于探索性研究
  - Bonferroni：适用于验证性研究（保守）
  - Holm-Bonferroni：折中方案
  - 置换检验：数据驱动的校正
- **校正层级预设**：主要终点 vs 次要终点的不同校正策略
- **代码实现**：R的p.adjust()或Python的statsmodels

---

## 1. 因果推断设计
- 构建DAG（有向无环图）展示变量关系
- 识别后门路径并设计阻断策略
- 选择合适的因果推断方法（倾向性评分/工具变量/双重差分等）
- 与E-value分析联动

## 2. 数据泄漏防护
- 明确数据分割策略（按患者/时间/中心）
- CV外操作清单（哪些操作绝对不能在CV外进行）
- 特征选择策略（必须在CV内进行）
- 嵌套交叉验证设计

## 3. 外部验证方案
- 独立队列设计（至少2个外部中心）
- 时间序列验证（如适用）
- 地理跨中心验证策略
- 桥接研究设计

## 4. R/Python实现代码
- 统计分析代码框架
- **E-value计算代码**（使用EValue包或手动实现）
- **功效分析代码**（pwr、powerMediation等包）
- **FDR校正代码**
- 因果推断实现（使用causalml、DoWhy或R包）

---

# 输出要求

1. **E-value强制**：必须给出具体的E-value数值和解读
2. **功效分析强制**：必须给出样本量计算结果和功效验证
3. **FDR强制**：必须明确校正方法和应用场景
4. **数学严谨**：所有统计方法必须有理论依据
5. **防弹设计**：明确列出所有可能的数据泄漏点并给出解决方案
6. **可复现**：提供完整的代码框架
7. **不要占位符**：不要使用"XX"或"待定"
8. **Markdown格式**：输出完整的Markdown文档

**警告**：缺少E-value、功效分析或FDR校正中任何一项，方案将被视为不合格。

现在请生成完整的生物统计学验证框架方案："""

        # 调用 LLM API
        response_text = self._call_llm_with_retry(prompt)

        # 提取和验证响应
        proposal_content = self.extractor.safe_extract_markdown(response_text, min_length=500)

        return proposal_content

    def _call_llm_with_retry(self, prompt: str, max_api_retries: int = 3) -> str:
        """调用 LLM API，带重试机制"""
        for api_attempt in range(max_api_retries):
            try:
                if api_attempt > 0:
                    print(f"[生物统计学专家] API 重试 {api_attempt + 1}/{max_api_retries}")

                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=8000,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=300
                )

                # 提取响应文本
                text_parts = []
                for block in message.content:
                    # 跳过 ThinkingBlock，只处理 TextBlock
                    if hasattr(block, 'type') and block.type == 'text':
                        text_parts.append(block.text)
                    elif hasattr(block, 'text') and not hasattr(block, 'thinking'):
                        text_parts.append(block.text)

                response_text = "\n".join(text_parts)

                if not response_text or len(response_text) < 100:
                    raise ValueError(f"LLM返回内容过短: {len(response_text)} 字符")

                print(f"[生物统计学专家] LLM响应成功，长度: {len(response_text)} 字符")
                return response_text

            except anthropic.APIError as e:
                error_str = str(e)
                is_retryable = (
                    'E015' in error_str or '500' in error_str or '502' in error_str or
                    '503' in error_str or 'rate_limit' in error_str.lower() or
                    'timeout' in error_str.lower()
                )

                if is_retryable and api_attempt < max_api_retries - 1:
                    wait_time = (api_attempt + 1) * 5
                    print(f"[生物统计学专家] API错误，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Claude API错误: {e}")

            except Exception as e:
                raise Exception(f"LLM调用失败: {e}")

        raise Exception("API调用重试次数耗尽")

    def _extract_validation_framework(self, proposal: str) -> Dict:
        """从方案中提取结构化验证框架"""
        import re

        framework = {
            'causal_methods': [],
            'validation_strategies': [],
            'multiple_testing_correction': 'unknown',
            'power_analysis': {
                'sample_size': 'unknown',
                'power': 'unknown'
            }
        }

        # 提取因果推断方法
        causal_patterns = {
            'Propensity_Score': r'(?:倾向性评分|propensity.?score)',
            'DAG': r'(?:DAG|有向无环图|causal.?graph)',
            'Instrumental_Variable': r'(?:工具变量|instrumental.?variable)',
            'Difference_in_Differences': r'(?:双重差分|DID|diff.?in.?diff)',
            'Mediation_Analysis': r'(?:中介|mediation)',
            'Negative_Control': r'(?:阴性对照|negative.?control)'
        }

        for method, pattern in causal_patterns.items():
            if re.search(pattern, proposal, re.IGNORECASE):
                framework['causal_methods'].append(method)

        # 提取验证策略
        validation_patterns = {
            'External_Cohort': r'(?:外部队列|external.?cohort|independent.?validation)',
            'Nested_CV': r'(?:嵌套交叉|nested.?cv)',
            'GroupKFold': r'(?:GroupKFold|分组K折)',
            'Temporal_Validation': r'(?:时间验证|temporal.?validation)',
            'Geographic_Validation': r'(?:地理验证|跨中心|multi.?center)'
        }

        for strategy, pattern in validation_patterns.items():
            if re.search(pattern, proposal, re.IGNORECASE):
                framework['validation_strategies'].append(strategy)

        # 提取多重检验校正方法
        correction_patterns = {
            'FDR': r'(?:FDR|Benjamini.?Hochberg|BH)',
            'Bonferroni': r'Bonferroni',
            'Holm': r'Holm',
            'Permutation': r'(?:置换|permutation)'
        }

        for correction, pattern in correction_patterns.items():
            if re.search(pattern, proposal, re.IGNORECASE):
                framework['multiple_testing_correction'] = correction
                break

        # 提取样本量和功效
        sample_match = re.search(r'(?:样本量|sample.?size|N\s*[=:]\s*)(\d+)', proposal, re.IGNORECASE)
        if sample_match:
            framework['power_analysis']['sample_size'] = sample_match.group(1)

        power_match = re.search(r'(?:功效|power)[^\d]*(\d+)', proposal, re.IGNORECASE)
        if power_match:
            framework['power_analysis']['power'] = f"{power_match.group(1)}%"

        return framework

    def _extract_defensive_metrics(self, proposal: str) -> Dict:
        """提取防御性指标（E-value、Power、FDR）"""
        import re

        metrics = {
            'evalue': {
                'calculated': False,
                'value': 'unknown',
                'interpretation': 'unknown'
            },
            'power_analysis': {
                'calculated': False,
                'sample_size': 'unknown',
                'target_power': 'unknown',
                'achieved_power': 'unknown'
            },
            'fdr_correction': {
                'method': 'unknown',
                'scenarios': []
            }
        }

        # 提取E-value
        evalue_match = re.search(r'E[-\s]?value[^\d]*(\d+\.?\d*)', proposal, re.IGNORECASE)
        if evalue_match:
            metrics['evalue']['calculated'] = True
            metrics['evalue']['value'] = evalue_match.group(1)

        # 提取E-value解读
        if re.search(r'较强|robust|tolerate', proposal, re.IGNORECASE):
            metrics['evalue']['interpretation'] = 'strong'
        elif re.search(r'敏感|sensitive|fragile', proposal, re.IGNORECASE):
            metrics['evalue']['interpretation'] = 'sensitive'

        # 提取功效分析
        if re.search(r'功效|power.*analysis|a priori', proposal, re.IGNORECASE):
            metrics['power_analysis']['calculated'] = True

        sample_match = re.search(r'(?:样本量|sample.*size|N)[^\d]*(\d+)', proposal, re.IGNORECASE)
        if sample_match:
            metrics['power_analysis']['sample_size'] = sample_match.group(1)

        power_target_match = re.search(r'(?:目标.*功效|target.*power)[^\d]*(\d+)', proposal, re.IGNORECASE)
        if power_target_match:
            metrics['power_analysis']['target_power'] = f"{power_target_match.group(1)}%"

        # 提取FDR校正
        fdr_methods = {
            'FDR': r'(?:FDR|Benjamini.?Hochberg|BH)',
            'Bonferroni': r'Bonferroni',
            'Holm': r'Holm'
        }

        for method, pattern in fdr_methods.items():
            if re.search(pattern, proposal, re.IGNORECASE):
                metrics['fdr_correction']['method'] = method
                break

        # 提取校正场景
        scenarios = re.findall(r'(?:多重检验|multiple.*testing|校正|correction)[：:](.{10,100}?)(?:\n|$)', proposal, re.IGNORECASE)
        metrics['fdr_correction']['scenarios'] = [s.strip() for s in scenarios if s.strip()]

        return metrics


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    # 测试生物统计学专家（强化版）
    test_hypothesis = {
        'title': '基于因果推断的癌症生存预测模型',
        'description': '构建考虑混杂因素的因果推断框架，评估治疗方案对生存的因果效应',
        'paradigm_framework': '因果推断 + 生存分析',
        'grand_challenge': '观察性研究中的混杂偏倚'
    }

    agent = BiostatsAgent()
    result = agent.execute({
        'hypothesis_data': test_hypothesis,
        'genai_proposal': '使用因果发现算法构建DAG',
        'compbio_proposal': '基因表达数据处理',
        'pathology_proposal': '病理图像特征提取',
        'output_dir': 'reports'
    })

    if result['success']:
        print("=" * 60)
        print("生物统计学验证框架设计完成")
        print("=" * 60)
        print(f"报告路径: {result['report_path']}")
        print(f"E-value: {result['defensive_metrics']['evalue']}")
        print(f"功效分析: {result['defensive_metrics']['power_analysis']}")
        print(f"FDR校正: {result['defensive_metrics']['fdr_correction']}")
