# -*- coding: utf-8 -*-
"""
首席临床医学专家智能体 (Chief M.D. / Clinical Translator)
三甲医院主任医师级别 - 纯临床效用评估专家

核心身份（重构后）：
- 20年+临床经验的三甲医院主任医师
- **专注于转化计算模型为宏观临床收益评估**
- 使用纯数据指标评估临床效用（DCA决策曲线、NRI净重分类改善）
- **绝对不负责提供任何物理样本或湿实验资源**

职责范围（重构后）：
1. ���床效用评估（使用纯数据指标）
2. 决策曲线分析（DCA）
3. 净重分类改善指数（NRI、IDI）
4. 临床影响曲线预测
5. 外部验证的临床解读
6. 真实世界证据转化策略

输入数据依赖：
- BiostatsAgent的输出（统计学验证框架）
- 所有上游Agent的输出

输出成果：
- 临床效用评估报告
- DCA决策曲线分析设计
- NRI/IDI计算方案
- 临床转化策略
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
from utils.llm_utils import SafeExtractor, RetryExecutor, LLMParseError


# ============ 临床效用评估指标（纯数据指标）===========

CLINICAL_UTILITY_METRICS = {
    'decision_curve_analysis': {
        'description': '决策曲线分析：评估模型在不同阈值概率下的净获益',
        'metrics': {
            'Net_Benefit': '净获益 = (TP/n) - (FP/n) * (p_t / (1 - p_t))',
            'Standardized_Net_Benefit': '标准化净获益',
            'Decision_Curve': '决策曲线绘制',
            'Clinical_Impact_Curve': '临床影响曲线'
        },
        'interpretation': {
            'high_value': '净获益显著优于"全治疗"和"不治疗"策略',
            'moderate_value': '净获益优于部分策略',
            'low_value': '净获益无明显优势'
        }
    },
    'reclassification_metrics': {
        'description': '重分类改善指标：评估新模型相比基准模型的改善程度',
        'metrics': {
            'NRI': 'Net Reclassification Improvement - 净重分类改善指数',
            'IDI': 'Integrated Discrimination Improvement - 综合判别改善指数',
            'Category_based_NRI': '基于分类的NRI',
            'Continuous_NRI': '连续型NRI'
        },
        'interpretation': {
            'NRI_gt_0.2': '改善程度 > 0.2 = 显著改善',
            'NRI_gt_0.1': '改善程度 > 0.1 = 中等改善',
            'NRI_lt_0.1': '改善程度 < 0.1 = 轻微改善'
        }
    },
    'calibration_metrics': {
        'description': '校准度指标：评估预测概率与实际发生率的一致性',
        'metrics': {
            'Calibration_Plot': '校准曲线',
            'Hosmer_Lemeshow': 'Hosmer-Lemeshow检验',
            'Brier_Score': 'Brier评分（越低越好）',
            'Calibration_Slope': '校准斜率（理想值=1）',
            'Calibration_Intercept': '校准截距（理想值=0）'
        }
    },
    'clinical_endpoints': {
        'hard_endpoints': {
            'OS': 'Overall Survival - 总生存期（金标准）',
            'PFS': 'Progression-Free Survival - 无进展生存期',
            'CSS': 'Cancer-Specific Survival - 癌症特异性生存期',
            'MACE': 'Major Adverse Cardiac Events - 主要不良心脏事件',
            'All_cause_mortality': '全因死亡率'
        },
        'soft_endpoints': {
            'ORR': 'Objective Response Rate - 客观缓解率',
            'DCR': 'Disease Control Rate - 疾病控制率',
            'QALYs': 'Quality-Adjusted Life Years - 质量调整生命年',
            'Early_detection_rate': '早期诊断率'
        }
    },
    'external_validation_clinical': {
        'metrics': {
            'Temporal_Validation': '时间序列验证的临床解读',
            'Geographic_Validation': '跨中心验证的临床一致性',
            'Population_Validation': '不同人群验证的适用性评估'
        }
    }
}


class ClinicalMDAgent(BaseAgent):
    """
    首席临床医学专家智能体 (Chief M.D. - Clinical Utility Expert)

    Core Mandate:
    - 临床效用: 评估该发现能否改变临床实践
    - 指南变革潜力: 该发现是否足以挑战或更新现有临床指南
    - 数据驱动的临床决策: 使用纯数据指标（DCA、NRI）评估效用

    评估标准:
    - 新颖性: 临床应用场景是否有创新
    - 严谨性: 临床效用评估是否严密
    - 颠覆性: 是否改变临床指南或实践

    禁止: 提供物理样本、湿实验资源，夸大临床意义
    """

    def __init__(self):
        super().__init__("首席临床医学专家", agent_type="clinical_md")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.max_retries = 3
        self.model = os.getenv("CLINICAL_MODEL", "claude-opus-4-6")
        self.extractor = SafeExtractor()
        self.retry_executor = RetryExecutor(max_retries=self.max_retries)

    def execute(self, input_data: Dict) -> Dict:
        """
        执行临床效用评估（重构版）

        Args:
            input_data: {
                'hypothesis_data': dict - 假设数据
                'biostats_proposal': str - 生物统计学方案（上游）
                'genai_proposal': str - GenAI架构方案
                'compbio_proposal': str - 计算生物学方案
                'pathology_proposal': str - 数字病理学方案
                'output_dir': str - 输出目录
            }

        Returns:
            {
                'success': bool,
                'clinical_review': str - 临床效用评估报告
                'utility_metrics': dict - 效用指标设计
                'report_path': str - 报告保存路径
            }
        """
        hypothesis_data = input_data.get('hypothesis_data', {})
        biostats_proposal = input_data.get('biostats_proposal', '')
        genai_proposal = input_data.get('genai_proposal', '')
        compbio_proposal = input_data.get('compbio_proposal', '')
        pathology_proposal = input_data.get('pathology_proposal', '')
        output_dir = input_data.get('output_dir', 'reports')

        if not hypothesis_data:
            raise ValueError('缺少假设数据 (hypothesis_data)')

        print(f"[临床专家] 开始评估临床效用，假设: {hypothesis_data.get('title', 'Unknown')}")

        # 使用重试机制生成临床效用评估报告
        clinical_review = None
        for attempt in range(self.max_retries):
            try:
                print(f"[临床专家] 第 {attempt + 1}/{self.max_retries} 次尝试生成报告...")
                clinical_review = self._generate_clinical_utility_assessment(
                    hypothesis_data=hypothesis_data,
                    biostats_proposal=biostats_proposal,
                    genai_proposal=genai_proposal
                )

                # 验证报告内容不为空且足够详细
                if not clinical_review or len(clinical_review.strip()) < 500:
                    raise ValueError(f"生成的报告内容过短: {len(clinical_review) if clinical_review else 0} 字符")

                print(f"[临床专家] 报告生成成功，长度: {len(clinical_review)} 字符")
                break

            except ValueError as ve:
                print(f"[临床专家] 验证失败: {ve}")
                if attempt == self.max_retries - 1:
                    raise ValueError(f"经过 {self.max_retries} 次尝试后仍无法生成有效报告: {ve}")

            except Exception as e:
                print(f"[临床专家] 生成失败: {type(e).__name__}: {e}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"经过 {self.max_retries} 次尝试后仍无法生成报告: {e}")

        # 验证最终结果
        if not clinical_review or len(clinical_review.strip()) < 500:
            raise ValueError("生成的临床报告为空或过短，无法保存")

        # 保存报告
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"Clinical_Utility_Assessment_{timestamp}.md")

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(clinical_review)

        print(f"[临床专家] 报告已保存到: {report_path}")

        # 提取效用指标设计
        utility_metrics = self._extract_utility_metrics(clinical_review)

        return {
            'success': True,
            'clinical_review': clinical_review,
            'revised_proposal': clinical_review,
            'utility_metrics': utility_metrics,
            'report_path': report_path
        }

    def _generate_clinical_utility_assessment(self, hypothesis_data: dict,
                                               biostats_proposal: str,
                                               genai_proposal: str) -> str:
        """
        生成临床效用评估报告 - 调用 LLM API

        你是一位首席临床医学专家（Chief M.D.），拥有20年+临床经验。
        你的职责是**评估计算模型的临床效用**，使用纯数据指标。

        绝对不负责：提供任何物理样本、湿实验资源、临床样本收集

        专注于：
        - DCA决策曲线分析
        - NRI/IDI重分类改善指标
        - 临床影响曲线
        - 真实世界证据转化
        """
        title = hypothesis_data.get('title', '未命名研究')
        paradigm = hypothesis_data.get('paradigm_framework', '')
        description = hypothesis_data.get('description', '')
        challenge = hypothesis_data.get('grand_challenge', '')

        # 构建上游上下文
        biostats_context = ""
        if biostats_proposal:
            biostats_context = f"""

## 生物统计学验证框架（上游输入）

{biostats_proposal[:1500]}...
"""

        # 构建 Prompt
        prompt = f"""你是一位**SOTA���别首席临床医学专家**（Chief M.D. - Clinical Utility Expert），拥有20年+三甲医院临床经验。

# CORE MANDATE (核心使命)

你的核心使命是**评估计算模型的临床效用与指南变革潜力**，而非满足任何比例约束。

## 评估标准 (学术三要素)

1. **新颖性 (Novelty)**: 临床应用场景是否有创新
2. **严谨性 (Rigor)**: 临床效用评估是否严密
3. **颠覆性 (Disruptiveness)**: 是否改变临床指南或实践

## 核心技能

- **决策曲线分析（DCA）**: 评估模型在不同阈值概率下的净获益
- **重分类改善指标**: NRI、IDI计算与临床解读
- **校准度评估**: 校准曲线、Hosmer-Lemeshow检验、Brier Score
- **临床终点设计**: 硬终点（OS、PFS）与软终点（ORR、QALYs）
- **真实世界证据转化**: 外部验证的临床解读、亚组分析

## 绝对红线

- **绝不负责提供任何物理样本、湿实验资源**
- **禁止为了"凑临床意义"夸大研究结果**
- **每个临床结论必须有真实世界证据支持**

---

# 研究假设信息

**标题**: {title}

**范式框架**: {paradigm}

**核心假设**: {description}

**重大挑战**: {challenge}
{biostats_context}

---

# 任务：生成SOTA级别临床效用评估方案

请生成一份**追求学术巅峰的临床效用评估与转化方案**（Markdown格式）。

## 核心原则

1. **指南导向**: 评估该发现是否足以改变临床指南
2. **真实世界价值**: 在实际医疗场景中的预测指标是否有意义
3. **数据驱动**: 使用纯数据指标（DCA、NRI）评估临床效用
4. **严谨解读**: 每个临床结论必须有真实世界证据支持

## 1. 决策曲线分析（DCA）设计
- 定义阈值概率范围（如：10%-90%）
- 设定比较策略（标准治疗、全治疗、不治疗）
- 设计净获益计算公式
- Python/R代码实现（使用stdca或rmda包）

## 2. 重分类改善分析（NRI/IDI）
- 选择基准模型进行对比
- 设计NRI计算方案（分类或连续）
- 设计IDI计算方案
- 临床意义解读标准

## 3. 校准度评估方案
- 校准曲线绘制方法
- Hosmer-Lemeshow检验设计
- Brier Score计算

## 4. 临床终点评估
- 主要终点选择（必须是硬终点）
- 次要终点设计
- 终点统计假设（HR、效应量）

## 5. 真实世界证据转化策略
- 外部验证的临床解读框架
- 亚组分析设计（年龄、性别、分期）
- 临床决策支持系统集成路径

## 6. R/Python实现代码
- DCA分析代码
- NRI/IDI计算代码
- 校准度评估代码

---

# 输出要求

1. **纯数据评估**：所有分析必须使用纯数据指标
2. **具体可行**：提供可直接运行的代码框架
3. **临床解读**：给出每个指标的临床意义解读
4. **不要占位符**：不要使用"XX"或"待定"
5. **Markdown格式**：输出完整的Markdown文档

现在请生成完整的临床效用评估方案："""

        # 调用 LLM API
        response_text = self._call_llm_with_retry(prompt)

        # 提取和验证响应
        report_content = self.extractor.safe_extract_markdown(response_text, min_length=500)

        return report_content

    def _call_llm_with_retry(self, prompt: str, max_api_retries: int = 3) -> str:
        """调用 LLM API，带重试机制"""
        for api_attempt in range(max_api_retries):
            try:
                if api_attempt > 0:
                    print(f"[临床专家] API 重试 {api_attempt + 1}/{max_api_retries}")

                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=8000,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=300
                )

                # 提取响应文本
                text_parts = []
                for block in message.content:
                    if hasattr(block, 'type') and block.type == 'text':
                        text_parts.append(block.text)
                    elif hasattr(block, 'text') and not hasattr(block, 'thinking'):
                        text_parts.append(block.text)

                response_text = "\n".join(text_parts)

                if not response_text or len(response_text) < 100:
                    raise ValueError(f"LLM返回内容过短: {len(response_text)} 字符")

                print(f"[临床专家] LLM响应成功，长度: {len(response_text)} 字符")
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
                    print(f"[临床专家] API错误，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Claude API错误: {e}")

            except Exception as e:
                raise Exception(f"LLM调用失败: {e}")

        raise Exception("API调用重试次数耗尽")

    def _extract_utility_metrics(self, report: str) -> Dict:
        """从报告中提取效用指标设计"""
        import re

        metrics = {
            'dca_design': {
                'threshold_range': 'unknown',
                'comparison_strategies': []
            },
            'reclassification': {
                'nri_design': 'unknown',
                'idi_design': 'unknown'
            },
            'calibration': {
                'methods': []
            },
            'clinical_endpoints': {
                'primary': [],
                'secondary': []
            }
        }

        # 提取DCA阈值范围
        threshold_match = re.search(r'(?:阈值|threshold)[^\d]*(\d+)[^\d]*[-~][^\d]*(\d+)', report, re.IGNORECASE)
        if threshold_match:
            metrics['dca_design']['threshold_range'] = f"{threshold_match.group(1)}-{threshold_match.group(2)}%"

        # 提取比较策略
        strategy_patterns = {
            'Standard_of_Care': r'(?:标准治疗|standard.?care|SOC)',
            'All_Treatment': r'(?:全治疗|all.?treatment|treat.?all)',
            'No_Treatment': r'(?:不治疗|no.?treatment|watch.?wait)'
        }

        for strategy, pattern in strategy_patterns.items():
            if re.search(pattern, report, re.IGNORECASE):
                metrics['dca_design']['comparison_strategies'].append(strategy)

        # 提取NRI/IDI设计
        if re.search(r'NRI', report, re.IGNORECASE):
            nri_type = 'continuous' if re.search(r'(?:连续|continuous)', report, re.IGNORECASE) else 'categorical'
            metrics['reclassification']['nri_design'] = nri_type

        if re.search(r'IDI', report, re.IGNORECASE):
            metrics['reclassification']['idi_design'] = 'included'

        # 提取校准方法
        calibration_patterns = {
            'Calibration_Plot': r'(?:校准曲线|calibration.?plot)',
            'Hosmer_Lemeshow': r'(?:Hosmer.*Lemeshow|H-L)',
            'Brier_Score': r'Brier'
        }

        for method, pattern in calibration_patterns.items():
            if re.search(pattern, report, re.IGNORECASE):
                metrics['calibration']['methods'].append(method)

        # 提取临床终点
        endpoint_patterns = {
            'OS': r'\bOS\b|总生存期',
            'PFS': r'\bPFS\b|无进展生存',
            'CSS': r'\bCSS\b',
            'MACE': r'\bMACE\b',
            'ORR': r'\bORR\b',
            'QALYs': r'\bQALYs?\b'
        }

        for endpoint, pattern in endpoint_patterns.items():
            if re.search(pattern, report, re.IGNORECASE):
                # 简单归类：硬终点放primary，软终点放secondary
                if endpoint in ['OS', 'PFS', 'CSS', 'MACE']:
                    metrics['clinical_endpoints']['primary'].append(endpoint)
                else:
                    metrics['clinical_endpoints']['secondary'].append(endpoint)

        return metrics


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    # 测试临床医学专家（重构版）
    test_hypothesis = {
        'title': 'AI辅助的癌症生存预测模型',
        'description': '基于多模态数据的癌症生存预测，使用DCA和NRI评估临床效用',
        'paradigm_framework': '机器学习 + 临床效用评估',
        'grand_challenge': '预测模型的临床转化价值评估'
    }

    agent = ClinicalMDAgent()
    result = agent.execute({
        'hypothesis_data': test_hypothesis,
        'biostats_proposal': '外部验证与因果推断框架',
        'genai_proposal': '多模态深度学习架构',
        'output_dir': 'reports'
    })

    if result['success']:
        print("=" * 60)
        print("临床效用评估完成")
        print("=" * 60)
        print(f"报告路径: {result['report_path']}")
        print(f"DCA阈值: {result['utility_metrics']['dca_design']['threshold_range']}")
        print(f"比较策略: {result['utility_metrics']['dca_design']['comparison_strategies']}")
