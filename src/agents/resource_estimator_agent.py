# -*- coding: utf-8 -*-
"""
资��核算Agent (ResourceEstimatorAgent)
算法驱动的资源配置专家

核心身份 (CORE MANDATE):
- **算法驱动资源分配 (Algorithm-Driven Resource Allocation)**: 根据实际算法需求核算算力、存储、成本
- **精确预算**: 基于模型参数量、数据吞吐量、计算复杂度进行精确资源核算
- **成本优化**: 在保证算法性能的前提下，寻找最优资源配置方案

绝对红线:
- 禁止拍脑袋估算，所有资源需求必须基于具体算法参数
- 禁止为了"省成本"而牺牲算法性能
- 每个资源建议必须有计算依据

核心评估标准 (学术三要素):
- **新颖性 (Novelty)**: 资源配置方案是否有创新
- **严谨性 (Rigor)**: 资源核算是否精确，是否有计算依据
- **颠覆性 (Disruptiveness)**: 是否通过资源配置优化实现性能突破

职责范围:
1. 读取GenAI的模型参数量
2. 读取DigitalPathology的图像吞吐量
3. 计算GPU显存预算
4. 估算计算时长
5. 云端存储成本建议
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


# ============ 资源核算参考数据 ============

RESOURCE_REFERENCE = {
    'gpu_specs': {
        'NVIDIA_A100_80GB': {
            'vram': 80,
            'memory_bandwidth': '2039 GB/s',
            'cuda_cores': 10752,
            'tensor_cores': 336,
            'peak_performance': '312 TFLOPS (FP16)',
            'hourly_cost_cloud': 2.5  # USD/hour approx
        },
        'NVIDIA_A100_40GB': {
            'vram': 40,
            'memory_bandwidth': '1555 GB/s',
            'cuda_cores': 6912,
            'tensor_cores': 216,
            'peak_performance': '194 TFLOPS (FP16)',
            'hourly_cost_cloud': 1.5
        },
        'NVIDIA_V100_32GB': {
            'vram': 32,
            'memory_bandwidth': '900 GB/s',
            'cuda_cores': 5120,
            'tensor_cores': 640,
            'peak_performance': '125 TFLOPS (FP16)',
            'hourly_cost_cloud': 1.0
        },
        'NVIDIA_RTX_4090_24GB': {
            'vram': 24,
            'memory_bandwidth': '1008 GB/s',
            'cuda_cores': 16384,
            'tensor_cores': 512,
            'peak_performance': '83 TFLOPS (FP16)',
            'hourly_cost_cloud': 0.5
        },
        'NVIDIA_RTX_3090_24GB': {
            'vram': 24,
            'memory_bandwidth': '936 GB/s',
            'cuda_cores': 10496,
            'tensor_cores': 328,
            'peak_performance': '36 TFLOPS (FP16)',
            'hourly_cost_cloud': 0.4
        }
    },
    'storage_costs': {
        'ssd_cloud': 0.10,  # USD/GB/month
        'hdd_cloud': 0.02,  # USD/GB/month
        's3_standard': 0.023,  # USD/GB/month
        's3_ia': 0.0125  # USD/GB/month
    },
    'memory_requirements': {
        'model_training': {
            'per_param_fp32': 4,  # bytes
            'per_param_fp16': 2,  # bytes
            'per_param_mixed': 4 + 2,  # bytes (fp32 + fp16)
            'optimizer_overhead': 2,  # multiplier for AdamW
            'activation_overhead': 1.5  # multiplier for activations
        },
        'inference': {
            'per_param_fp16': 2,
            'kv_cache_overhead': 1.2
        }
    }
}


class ResourceEstimatorAgent(BaseAgent):
    """
    资源核算Agent

    角色：算法���动的资源分配专家
    专长：GPU预算、时长估算、成本分析

    Core Mandate:
    - 算法驱动资源分配: 根据实际算法需求核算算力、存储、成本
    - 精确预算: 基于模型参数量、数据吞吐量、计算复杂度进行精确核算
    - 成本优化: 在保证算法性能的前提下，寻找最优资源配置
    """

    def __init__(self):
        super().__init__("资源核算专家", agent_type="resource_estimator")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.max_retries = 3
        self.model = os.getenv("RESOURCE_MODEL", "claude-opus-4-6")
        self.extractor = SafeExtractor()

    def execute(self, input_data: Dict) -> Dict:
        """
        执行资源核算

        Args:
            input_data: {
                'hypothesis_data': dict - 假设数据
                'genai_proposal': str - GenAI架构方案
                'compbio_proposal': str - 计算生物学方案
                'pathology_proposal': str - 数字病理学方案
                'biostats_proposal': str - 生物统计学方案
                'output_dir': str - 输出目录
            }

        Returns:
            {
                'success': bool,
                'resource_report': str - 资源核算报告
                'resource_budget': dict - 资源预算
                'report_path': str - 报告保存路径
            }
        """
        hypothesis_data = input_data.get('hypothesis_data', {})
        genai_proposal = input_data.get('genai_proposal', '')
        compbio_proposal = input_data.get('compbio_proposal', '')
        pathology_proposal = input_data.get('pathology_proposal', '')
        biostats_proposal = input_data.get('biostats_proposal', '')
        output_dir = input_data.get('output_dir', 'reports')

        if not hypothesis_data:
            raise ValueError('缺少假设数据 (hypothesis_data)')

        print(f"[资源核算专家] 开始核算资源，假设: {hypothesis_data.get('title', 'Unknown')}")

        # 使用重试机制生成资源核算报告
        resource_report = None
        for attempt in range(self.max_retries):
            try:
                print(f"[资源核算专家] 第 {attempt + 1}/{self.max_retries} 次尝试生成报告...")
                resource_report = self._generate_resource_report(
                    hypothesis_data=hypothesis_data,
                    genai_proposal=genai_proposal,
                    compbio_proposal=compbio_proposal,
                    pathology_proposal=pathology_proposal,
                    biostats_proposal=biostats_proposal
                )

                # 验证报告内容不为空且足够详细
                if not resource_report or len(resource_report.strip()) < 500:
                    raise ValueError(f"生成的报告内容过短: {len(resource_report) if resource_report else 0} 字符")

                print(f"[资源核算专家] 报告生成成功，长度: {len(resource_report)} 字符")
                break

            except ValueError as ve:
                print(f"[资源核算专家] 验证失败: {ve}")
                if attempt == self.max_retries - 1:
                    raise ValueError(f"经过 {self.max_retries} 次尝试后仍无法生成有效报告: {ve}")

            except Exception as e:
                print(f"[资源核算专家] 生成失败: {type(e).__name__}: {e}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"经过 {self.max_retries} 次尝试后仍无法生成报告: {e}")

        # 验证最终结果
        if not resource_report or len(resource_report.strip()) < 500:
            raise ValueError("生成的资源核算报告为空或过短，无法保存")

        # 保存报告
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"Resource_Estimation_{timestamp}.md")

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(resource_report)

        print(f"[资源核算专家] 报告已保存到: {report_path}")

        # 提取资源预算
        resource_budget = self._extract_resource_budget(resource_report)

        return {
            'success': True,
            'resource_report': resource_report,
            'resource_budget': resource_budget,
            'report_path': report_path
        }

    def _generate_resource_report(self, hypothesis_data: dict,
                                   genai_proposal: str,
                                   compbio_proposal: str,
                                   pathology_proposal: str,
                                   biostats_proposal: str) -> str:
        """生成资源核算报告"""
        title = hypothesis_data.get('title', '未命名研究')
        paradigm = hypothesis_data.get('paradigm_framework', '')

        # 构建上游上下文
        upstream_context = f"""
上游方案摘要：
- GenAI架构: {genai_proposal[:400] if genai_proposal else '未提供'}...
- 计算生物学: {compbio_proposal[:400] if compbio_proposal else '未提供'}...
- 数字病理学: {pathology_proposal[:400] if pathology_proposal else '未提供'}...
- 生物统计: {biostats_proposal[:400] if biostats_proposal else '未提供'}...
"""

        # 构建 Prompt
        prompt = f"""你是一位**SOTA级别算法驱动的资源分配专家**（Algorithm-Driven Resource Allocation Expert）。

# CORE MANDATE (核心使命)

你的核心使命是**基于实际���法需求进行精确资源核算**，而非拍脑袋估算。

## 评估标准 (学术三要素)

1. **新颖性 (Novelty)**: 资源配置方案是否有创新
2. **严谨性 (Rigor)**: 资源核算是否精确，是否有计算依据
3. **颠覆性 (Disruptiveness)**: 是否通过资源配置优化实现性能突破

## 绝对红���

- **禁止拍脑袋估算，所有资源需求必须基于具体算法参数**
- **禁止为了"省成本"而牺牲算法性能**
- **每个资源建议必须有计算依据**

---

# 研究假设信息

**标题**: {title}

**范式框架**: {paradigm}

{upstream_context}

---

# 任务：生成SOTA级别资源核算报告

请生成一份**追求学术巅峰的资源核算与成本分析报告**（Markdown格式）。

## 核心原则

1. **算法驱动**: 所有资源需求必须基于具体算法参数
2. **精确预算**: 基于模型参数量、数据吞吐量、计算复杂度进行精确核算
3. **成本优化**: 在保证算法性能的前提下，寻找最优资源配置
4. **计算依据**: 每个资源建议必须有明确的计算公式

## 1. 模型参数量核算
- 从GenAI架构中提取/估算模型参数量
- 计算训练时显存需求（FP32/FP16/Mixed Precision）
- 计算推理时显存需求
- 考虑优化器开销（AdamW通常需要2x参数量）

## 2. 数据吞吐量核算
- 从CompBioAgent中提取数据规模（样本数、特征数）
- 从DigitalPathologyAgent中提取图像规格（WSI尺寸、patch数量）
- 计算单样本处理时间
- 计算总数据量及存储需求

## 3. 计算时长估算
- 训练阶段：epochs × batch_time × iterations
- 推理阶段：样本数 × 单样本推理时间
- 数据预处理时长
- 总时长估算（保守估计）

## 4. GPU配置建议
根据显存需求推荐：
- A100 80GB：超大模型、大批次
- A100 40GB：大模型、中等批次
- V100 32GB：中等模型
- RTX 4090 24GB：小模型、本地开发
- 多卡并行策略（DataParallel / DistributedDataParallel）

## 5. 云端成本估算
- 计算成本（GPU小时数 × 时费率）
- 存储成本（数据量 × 存储单价 × 月数）
- 数据传输成本（如适用）
- 总成本估算（保守/乐观）

## 6. 成本优化建议
- Spot实例使用策略
- 预留实例折扣
- 数据生命周期管理
- 本地+云端混合方案

---

# GPU参考规格

| GPU | 显存 | 峰值性能(FP16) | 云端时费(约) |
|-----|------|----------------|---------------|
| A100 80GB | 80GB | 312 TFLOPS | $2.5/小时 |
| A100 40GB | 40GB | 194 TFLOPS | $1.5/小时 |
| V100 32GB | 32GB | 125 TFLOPS | $1.0/小时 |
| RTX 4090 | 24GB | 83 TFLOPS | $0.5/小时 |

# 存储参考价格

| 类型 | 价格 |
|-----|------|
| S3 Standard | $0.023/GB/月 |
| S3 IA | $0.0125/GB/月 |
| EBS SSD | $0.10/GB/月 |

---

# 输出要求

1. **精确核算**：基于实际算法参数，不要拍脑袋估算
2. **多场景对比**：给出不同GPU配置的方案
3. **成本透明**：明确列出各项成本
4. **优化建议**：给出成本优化方案
5. **Markdown格式**：输出完整的Markdown文档

现在请生成完整的资源核算报告："""

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
                    print(f"[资源核算专家] API 重试 {api_attempt + 1}/{max_api_retries}")

                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=6000,
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

                print(f"[资源核算专家] LLM响应成功，长度: {len(response_text)} 字符")
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
                    print(f"[资源核算专家] API错误，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Claude API错误: {e}")

            except Exception as e:
                raise Exception(f"LLM调用失败: {e}")

        raise Exception("API调用重试次数耗尽")

    def _extract_resource_budget(self, report: str) -> Dict:
        """从报告中提取资源预算"""
        import re

        budget = {
            'gpu_recommendation': 'unknown',
            'vram_required': 'unknown',
            'estimated_hours': 'unknown',
            'estimated_cost_usd': 'unknown',
            'storage_required': 'unknown'
        }

        # 提取GPU推荐
        gpu_patterns = {
            'A100_80GB': r'A100.*80GB|80GB.*A100',
            'A100_40GB': r'A100.*40GB|40GB.*A100',
            'V100_32GB': r'V100.*32GB|32GB.*V100',
            'RTX_4090': r'RTX.*4090|4090',
            'RTX_3090': r'RTX.*3090|3090'
        }

        for gpu, pattern in gpu_patterns.items():
            if re.search(pattern, report, re.IGNORECASE):
                budget['gpu_recommendation'] = gpu
                break

        # 提取显存需求
        vram_match = re.search(r'(?:显存|VRAM|memory).*?(\d+)\s*GB', report, re.IGNORECASE)
        if vram_match:
            budget['vram_required'] = f"{vram_match.group(1)}GB"

        # 提取时长
        time_patterns = [
            r'(\d+\.?\d*)\s*小时',
            r'(\d+\.?\d*)\s*hrs',
            r'(\d+\.?\d*)\s*h\b'
        ]

        for pattern in time_patterns:
            match = re.search(pattern, report, re.IGNORECASE)
            if match:
                budget['estimated_hours'] = f"{match.group(1)}h"
                break

        # 提取成本
        cost_match = re.search(r'\$?(\d+\.?\d*)\s*(?:USD|美元|元)', report, re.IGNORECASE)
        if cost_match:
            budget['estimated_cost_usd'] = f"${cost_match.group(1)}"

        # 提取存储需求
        storage_match = re.search(r'(\d+\.?\d*)\s*(?:TB|GB)\s*(?:存储|storage|数据)', report, re.IGNORECASE)
        if storage_match:
            budget['storage_required'] = f"{storage_match.group(1)}{storage_match.group(2) if storage_match.lastindex else ''}"

        return budget


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    # 测试资源核算专家
    test_hypothesis = {
        'title': '大模型训练项目',
        'description': '训练一个7B参数的语言模型',
        'paradigm_framework': '深度学习'
    }

    agent = ResourceEstimatorAgent()
    result = agent.execute({
        'hypothesis_data': test_hypothesis,
        'genai_proposal': '使用7B参数的Transformer模型，混合精度训练',
        'compbio_proposal': '100万样本，每个样本1000维特征',
        'pathology_proposal': '1000张WSI，每张10万x10万像素',
        'biostats_proposal': '蒙特卡洛模拟1000次',
        'output_dir': 'reports'
    })

    if result['success']:
        print("=" * 60)
        print("资源核算完成")
        print("=" * 60)
        print(f"报告路径: {result['report_path']}")
        print(f"GPU推荐: {result['resource_budget']['gpu_recommendation']}")
        print(f"显存需求: {result['resource_budget']['vram_required']}")
        print(f"估算成本: {result['resource_budget']['estimated_cost_usd']}")
