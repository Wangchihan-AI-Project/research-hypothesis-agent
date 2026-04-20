# -*- coding: utf-8 -*-
"""
数据治理与质控审计智能体 (DataGovernanceAgent)
Health DS 数据质量把关人

核心身份：
- 数据治理与质控专家，负责审查数据的完整性与可用性
- 在DataHunter之后、GenAI之前执行，是纯干实验流程的第一道防线

职责范围：
1. 批次效应检测与校正方案设计
2. 缺失值插补策略（Multiple Imputation）
3. 多中心数据异质性校准（ComBat算法）
4. 数据完整性审计
5. 数据分布一致性检验

输入数据依赖：
- DataHunterAgent的输出（数据探勘报告）
- 原始假设数据

输出成果：
- 数据治理审计报告
- QC与调和协议
- 批次效应校正方案
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


# ============ 数据治理技术栈 ============

DATA_GOVERNANCE_STACK = {
    'batch_effect_correction': {
        'methods': {
            'ComBat': '基于经验贝叶斯的批次效应校正（最常用）',
            'ComBat_seq': '适用于测序数据的ComBat变体',
            'MNN': 'Mutual Nearest Neighbors校正',
            'Harmony': '谐波整合算法',
            'limma_removeBatchEffect': 'limma包的批次效应移除',
            'RUV': 'Remove Unwanted Variation方法'
        }
    },
    'missing_data_imputation': {
        'methods': {
            'Multiple_Imputation': '多重插补（金标准）',
            'MICE': 'Multivariate Imputation by Chained Equations',
            'MissForest': '基于随机森林的插补',
            'KNN_Imputation': 'K近邻插补',
            'Matrix_Completion': '矩阵补全算法',
            'DeepLearning': '基于深度学习的插补（GAIN、MIDA）'
        },
        'assumptions': {
            'MAR': 'Missing At Random - 随机缺失',
            'MCAR': 'Missing Completely At Random - 完全随机缺失',
            'MNAR': 'Missing Not At Random - 非随机缺失'
        }
    },
    'multi_center_harmonization': {
        'methods': {
            'ComBat': '跨中心调和（最常用）',
            'CVAE': 'Conditional Variational Autoencoder',
            'Domain_Adaptation': '域适应方法',
            'Meta_Analysis': '荟萃分析层面的整合'
        }
    },
    'quality_control': {
        'outlier_detection': {
            'PCA': '主成分分析异常检测',
            'Isolation_Forest': '孤立森林',
            'DBSCAN': '密度聚类异常检测',
            'Mahalanobis_Distance': '马氏距离'
        },
        'distribution_checks': {
            'KS_Test': 'Kolmogorov-Smirnov检验',
            'Anderson_Darling': 'Anderson-Darling检验',
            'Shapiro_Wilk': 'Shapiro-Wilk正态性检验',
            'QQ_Plot': 'Q-Q图可视化'
        }
    }
}


class DataGovernanceAgent(BaseAgent):
    """
    数据治理与质控审计智能体

    角色：Health DS 数据质量把关人
    专长：批次效应校正、缺失值插补、多中心调和
    """

    def __init__(self):
        super().__init__("数据治理专家", agent_type="data_governance")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.max_retries = 3
        self.model = os.getenv("GOVERNANCE_MODEL", "claude-opus-4-6")
        self.extractor = SafeExtractor()

    def execute(self, input_data: Dict) -> Dict:
        """
        执行数据治理审计

        Args:
            input_data: {
                'hypothesis_data': dict - 假设数据
                'data_hunter_report': dict - 数据探勘报告
                'output_dir': str - 输出目录
            }

        Returns:
            {
                'success': bool,
                'governance_report': str - 数据治理审计报告
                'qc_protocol': dict - QC与调和协议
                'report_path': str - 报告保存路径
            }
        """
        hypothesis_data = input_data.get('hypothesis_data', {})
        data_hunter_report = input_data.get('data_hunter_report', {})
        output_dir = input_data.get('output_dir', 'reports')

        if not hypothesis_data:
            raise ValueError('缺少假设数据 (hypothesis_data)')

        print(f"[数据治理专家] 开始审计，假设: {hypothesis_data.get('title', 'Unknown')}")

        # 使用重试机制生成治理审计报告
        governance_report = None
        for attempt in range(self.max_retries):
            try:
                print(f"[数据治理专家] 第 {attempt + 1}/{self.max_retries} 次尝试生成报告...")
                governance_report = self._generate_governance_report(
                    hypothesis_data=hypothesis_data,
                    data_hunter_report=data_hunter_report
                )

                # 验证报告内容不为空且足够详细
                if not governance_report or len(governance_report.strip()) < 500:
                    raise ValueError(f"生成的报告内容过短: {len(governance_report) if governance_report else 0} 字符")

                print(f"[数据治理专家] 报告生成成功，长度: {len(governance_report)} 字符")
                break

            except ValueError as ve:
                print(f"[数据治理专家] 验证失败: {ve}")
                if attempt == self.max_retries - 1:
                    raise ValueError(f"经过 {self.max_retries} 次尝试后仍无法生成有效报告: {ve}")

            except Exception as e:
                print(f"[数据治理专家] 生成失败: {type(e).__name__}: {e}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"经过 {self.max_retries} 次尝试后仍无法生成报告: {e}")

        # 验证最终结果
        if not governance_report or len(governance_report.strip()) < 500:
            raise ValueError("生成的数据治理报告为空或过短，无法保存")

        # 保存报告
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"DataGovernance_Audit_{timestamp}.md")

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(governance_report)

        print(f"[数据治理专家] 报告已保存到: {report_path}")

        # 提取QC协议
        qc_protocol = self._extract_qc_protocol(governance_report)

        return {
            'success': True,
            'governance_report': governance_report,
            'qc_protocol': qc_protocol,
            'report_path': report_path
        }

    def _generate_governance_report(self, hypothesis_data: dict,
                                     data_hunter_report: dict) -> str:
        """生成数据治理审计报告"""

        title = hypothesis_data.get('title', '未命名研究')
        paradigm = hypothesis_data.get('paradigm_framework', '')
        description = hypothesis_data.get('description', '')
        challenge = hypothesis_data.get('grand_challenge', '')

        # 构建数据探勘上下文
        hunter_context = ""
        if data_hunter_report:
            hunter_context = f"""

## 数据探勘报告（上游输入）

{json.dumps(data_hunter_report, ensure_ascii=False, indent=2)[:1500]}...
"""

        # 构建 Prompt
        prompt = f"""你是一位**数据治理与质控专家**（Data Governance & QC Expert），专门负责审查健康数据科学(Health DS)项目的数据质量。

你的核心职责是确保下游分析之前，数据已经过严格的质量控制与调和。**没有QC协议，后续统计分析视为无效。**

---

# 研究假设信息

**标题**: {title}

**范式框架**: {paradigm}

**核心假设**: {description}

**重大挑战**: {challenge}
{hunter_context}

---

# 任务：生成数据治理审计与QC协议

请生成一份完整的**数据治理审计与QC调和协议**（Markdown格式），必须包含以下部分：

## 1. 数据完整性审计
- 缺失值模式分析（MCAR/MAR/MNAR识别）
- 缺失值插补策略（必须使用Multiple Imputation）
- 异常值检测与处理方案
- 数据分布一致性检验

## 2. 批次效应检测与校正
- 批次效应检测方法（PCA可视化、KB测试）
- 校正算法选择（ComBat/ComBat-seq/Harmony/MNN）
- 校正效果验证方案
- **强制要求**：必须明确是否需要ComBat校正

## 3. 多中心数据异质性校准
- 中心间差异评估（PERMANOVA分析）
- 跨中心调和策略（ComBat/CVAE/Domain Adaptation）
- 中心特异性效应保留策略
- 调和后的一致性验证

## 4. 外部验证集设计（强制）
- **独立验证集来源**：明确指定外部数据集（如 GEO、ArrayExpress、dbGaP）
- **批次效应处理**：外部验证集与训练集之间的批次校正方案
- **跨数据集泛化验证**：使用不同平台/批次的数据进行验证
- **地理/时间异质性**：不同地区、不同时间收集的数据验证
- **阻断条件**：若无外部验证��可用，必须明确说明限制

## 5. 数据质量控制清单
- 样本级QC标准
- 特征级QC标准
- 数据剔除规则
- QC通过/失败判定标准

## 6. Python/R实现代码
- 批次效应检测代码
- ComBat校正实现
- 多重插补代码（MICE）
- 分布检验代码

## 7. 数据治理阻断条件
明确列出以下情况：
- **数据质量过低，必须终止研究**的条件
- **需要重新收集数据**的条件
- **可以使用现有数据继续**的条件

---

# 输出要求

1. **严谨性**：所有QC方法必须有统计学依据
2. **具体可行**：提供可直接运行的代码框架
3. **阻断明确**：清晰说明什么情况下必须终止研究
4. **不要占位符**：不要使用"XX"或"待定"
5. **Markdown格式**：输出完整的Markdown文档

**重要提醒**：你是数据质量的第一道防线。如果数据质量不达标，必须明确建议终止研究。不要为了"通过"而降低标准。

现在请生成完整的数据治理审计报告："""

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
                    print(f"[数据治理专家] API 重试 {api_attempt + 1}/{max_api_retries}")

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

                print(f"[数据治理专家] LLM响应成功，长度: {len(response_text)} 字符")
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
                    print(f"[数据治理专家] API错误，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Claude API错误: {e}")

            except Exception as e:
                raise Exception(f"LLM调用失败: {e}")

        raise Exception("API调用重试次数耗尽")

    def _extract_qc_protocol(self, report: str) -> Dict:
        """从报告中提取QC协议"""
        protocol = {
            'batch_correction_required': False,
            'batch_method': 'unknown',
            'imputation_method': 'unknown',
            'multi_center_harmonization': False,
            'block_conditions': []
        }

        # 检测批次校正
        if re.search(r'ComBat|batch.*correct|批次.*校正', report, re.IGNORECASE):
            protocol['batch_correction_required'] = True
            if re.search(r'ComBat[_-]?seq', report, re.IGNORECASE):
                protocol['batch_method'] = 'ComBat_seq'
            elif re.search(r'ComBat', report, re.IGNORECASE):
                protocol['batch_method'] = 'ComBat'
            elif re.search(r'Harmony', report, re.IGNORECASE):
                protocol['batch_method'] = 'Harmony'
            elif re.search(r'MNN', report, re.IGNORECASE):
                protocol['batch_method'] = 'MNN'

        # 检测插补方法
        imputation_patterns = {
            'MICE': r'MICE|Multiple.*Imputation.*Chained',
            'MissForest': r'MissForest',
            'KNN': r'KNN.*Imput',
            'GAIN': r'GAIN|DeepLearning.*Imput'
        }

        for method, pattern in imputation_patterns.items():
            if re.search(pattern, report, re.IGNORECASE):
                protocol['imputation_method'] = method
                break

        # 检测多中心调和
        if re.search(r'多中心|multi.?center|跨中心', report, re.IGNORECASE):
            protocol['multi_center_harmonization'] = True

        # 提取阻断条件
        block_keywords = [
            r'(?:终止|停止|阻断|fail).*?[:：](.{10,100})',
            r'(?:数据质量过低|不满足.*条件|无法继续)'
        ]

        for pattern in block_keywords:
            matches = re.findall(pattern, report, re.IGNORECASE)
            protocol['block_conditions'].extend([m.strip() for m in matches])

        return protocol


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    # 测试数据治理专家
    test_hypothesis = {
        'title': '多中心scRNA-seq数据的癌症亚型发现',
        'description': '整合多个中心的单细胞数据，发现新的癌症亚型',
        'paradigm_framework': '单细胞组学 + 批次校正',
        'grand_challenge': '批次效应与中心异质性'
    }

    agent = DataGovernanceAgent()
    result = agent.execute({
        'hypothesis_data': test_hypothesis,
        'data_hunter_report': {
            'ml_assessment': {
                'overall_recommendation': 'good',
                'sample_size': 1000
            }
        },
        'output_dir': 'reports'
    })

    if result['success']:
        print("=" * 60)
        print("数据治理审计完成")
        print("=" * 60)
        print(f"报告路径: {result['report_path']}")
        print(f"批次校正: {result['qc_protocol']['batch_method']}")
        print(f"插补方法: {result['qc_protocol']['imputation_method']}")
