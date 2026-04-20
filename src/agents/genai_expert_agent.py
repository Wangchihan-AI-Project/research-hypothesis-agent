# -*- coding: utf-8 -*-
"""
首席生成式AI架构师智能体 (GenAIExpertAgent)
SOTA级别生成式AI架构专家

核心身份 (CORE MANDATE):
- **SOTA级架构设计**: 追踪领域最前沿的GenAI技术，拒绝平庸架构
- **算法创新优先**: 追求非平凡的架构改进，而非简单应用
- **可落地实现**: 所有架构必须有具体的代码实现路径

绝对红线:
- 禁止为了"凑GenAI内容"而强行集成AI到不合适的场景
- 禁止忽视计算成本��数据隐私等实际约束
- 每个架构选择必须有SOTA文献支撑

核心评估标准 (学术三要素):
- **新颖性 (Novelty)**: 架构设计或应用场景是否有创新
- **严谨性 (Rigor)**: 架构设计是否严密，是否有理论支撑
- **颠覆性 (Disruptiveness)**: 是否挑战现有GenAI范式

职责范围:
- 分析数据科学方案中的GenAI赋能机会
- 设计大模型架构（LLM/Diffusion/Transformer）
- 规划合成数据生成策略
- 设计微调/LoRA/P-Tuning/RAG方案
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


# ============ 生成式AI前沿技术栈 ============

GENAI_TECH_STACK = {
    'large_language_models': {
        'foundation_models': {
            'GPT-4': 'OpenAI最强通用LLM，适用于复杂推理',
            'Claude-3': 'Anthropic高性能LLM，长文本处理优势',
            'Llama-3': 'Meta开源最强LLM，可本地部署',
            'Mistral': '高效开源LLM，适合边缘部署'
        },
        'clinical_llms': {
            'ClinicalBERT': 'BERT在临床文本上的预训练',
            'BioBERT': '生物医学文本预训练BERT',
            'PubMedBERT': 'PubMed摘要预训练BERT',
            'Med-PaLM': 'Google医疗专用LLM',
            'ClinicalGPT': '临床决策支持专用LLM'
        },
        'biological_sequence_models': {
            'ESM-2': 'Meta蛋白质语言模型，650M参数',
            'ESM-3': '最新多模态蛋白质模型',
            'DNABERT': 'DNA序列语言模型',
            'HyenaDNA': '长序列DNA模型，支持1M tokens',
            'Nucleus Transformer': '基因组理解模型',
            'GenePT': '基因表达预训练Transformer'
        },
        'fine_tuning_methods': {
            'LoRA': '低秩适应，参数量<1%',
            'QLoRA': '量化LoRA，4bit微调',
            'P-Tuning': '提示微调',
            'Adapter': '适配器微调',
            'Prefix-Tuning': '前缀微调'
        }
    },
    'diffusion_models': {
        'image_generation': {
            'Stable Diffusion': '图像生成基础模型',
            'DALL-E 3': 'OpenAI图像生成模型'
        },
        'biological_diffusion': {
            'RFdiffusion': '蛋白质结构设计扩散模型',
            'ProteinMPNN': '蛋白质序列设计',
            'DiffusionPCR': '单细胞数据生成',
            'scDiff': '单细胞合成数据生成',
            'SynPop': '群体合成数据生成'
        },
        'conditional_generation': {
            'Classifier-Free Guidance': '无分类器引导采样',
            'Text-to-Image': '文本到图像生成',
            'Text-to-Protein': '文本到蛋白质设计',
            'Structure-to-Sequence': '结构到序列生成'
        }
    },
    'synthetic_data_generation': {
        'tabular_synthesis': {
            'CTGAN': '条件GAN生成表格数据',
            'TVAE': '变分自编码器表格数据',
            'GaussianCopula': '高斯Copula模型',
            'SDV': '合成数据套件',
            'YData-Synthetic': '企业级合成数据'
        },
        'privacy_preserving': {
            'Differential Privacy': '差分隐私保护',
            'Federated Learning': '联邦学习',
            'Secure Aggregation': '安全聚合',
            'DP-SGD': '差分隐私随机梯度下降'
        }
    },
    'retrieval_augmented_generation': {
        'vector_databases': {
            'ChromaDB': '轻量级向量数据库',
            'Pinecone': '托管向量数据库',
            'Milvus': '开源向量数据库',
            'FAISS': 'Facebook相似性搜索',
            'Weaviate': '开源向量搜索引擎'
        },
        'embedding_models': {
            'text-embedding-ada-002': 'OpenAI文本嵌入',
            'Cohere-embed': 'Cohere嵌入模型',
            'BGE-M3': '双语嵌入模型',
            'E5': '文本检索嵌入',
            ' VoyageAI': '领域专用嵌入'
        },
        'rag_frameworks': {
            'LangChain': 'LLM应用开发框架',
            'LlamaIndex': '数据框架',
            'Haystack': '深度学习RAG',
            'SemanticKernel': '微软RAG框架',
            'AutoRAG': '自动RAG优化'
        }
    }
}

# GenAI赋能场景
GENAI_USE_CASES = {
    'data_augmentation': {
        'scenario': '数据匮乏/小样本问题',
        'solution': '使用扩散模型或GAN生成合成数据',
        'examples': [
            'scDiff生成单细胞合成数据用于模型预训练',
            'RFdiffusion生成蛋白质结构变体',
            'CTGAN生成临床表格数据'
        ]
    },
    'unstructured_data_processing': {
        'scenario': '非结构化临床文本/影像处理',
        'solution': '微调Clinical LLM或使用多模态模型',
        'examples': [
            'ClinicalBERT提取临床表型',
            'Med-PaLM进行临床推理',
            'BiomedCLIP处理医学影像'
        ]
    },
    'zero_shot_prediction': {
        'scenario': '跨物种/跨任务泛化',
        'solution': '使用蛋白质/基因组语言模型进行zero-shot预测',
        'examples': [
            'ESM-2预测蛋白质功能',
            'DNABERT预测调控元件',
            'GenePT预测基因表达'
        ]
    },
    'generative_design': {
        'scenario': '从头设计（De novo design）',
        'solution': '使用扩散模型或自回归生成',
        'examples': [
            'RFdiffusion设计全新蛋白质',
            'DiffusionProtein生成蛋白质序列',
            'ProteinMPNN优化蛋白质稳定性'
        ]
    },
    'knowledge_integration': {
        'scenario': '整合海量文献/知识库',
        'solution': 'RAG架构+向量数据库',
        'examples': [
            'BioRAG: 生物医学知识问答',
            'ClinicalRAG: 临床决策支持',
            'LitRAG: 文献驱动的假设生成'
        ]
    }
}


class GenAIExpertAgent(BaseAgent):
    """
    首席生成式AI架构师智能体 (SOTA GenAI Architect)

    Core Mandate:
    - SOTA级架构设计: 追踪领域最前沿的GenAI技术
    - 算法创新优先: 追求非平凡的架构改进
    - 可落地实现: 所有架构必须有具体的代码实现路径

    评估标准:
    - 新颖性: 架构设计或应用场景是否有创新
    - 严谨性: 架构设计是否严密，是否有理论支撑
    - 颠覆性: 是否挑战现有GenAI范式

    禁止: 强行集成AI到不合适的场景，忽视计算成本和数据隐私
    """

    def __init__(self):
        super().__init__("首席生成式AI架构师", agent_type="genai_expert")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.max_retries = 3
        self.model = os.getenv("GENAI_MODEL", "claude-opus-4-6")

    def execute(self, input_data: Dict) -> Dict:
        """
        执行GenAI赋能方案生成

        Args:
            input_data: {
                'hypothesis_data': dict - 假设数据
                'tech_analysis': dict - 技术分析报告
                'validation_result': dict - 验证报告
                'output_dir': str - 输出目录
            }

        Returns:
            {
                'success': bool,
                'genai_proposal': str - GenAI赋能方案
                'proposal_path': str - 方案保存路径
            }
        """
        hypothesis_data = input_data.get('hypothesis_data', {})
        tech_analysis = input_data.get('tech_analysis', {})
        validation_result = input_data.get('validation_result', {})
        output_dir = input_data.get('output_dir', 'reports')

        if not hypothesis_data:
            raise ValueError('缺少假设数据 (hypothesis_data)')

        print(f"[GenAI架构师] 开始生成方案，假设: {hypothesis_data.get('title', 'Unknown')}")

        # 使用重试机制生成GenAI赋能方案
        genai_proposal = None
        for attempt in range(self.max_retries):
            try:
                print(f"[GenAI架构师] 第 {attempt + 1}/{self.max_retries} 次尝试生成方案...")
                genai_proposal = self._generate_genai_proposal(
                    hypothesis_data=hypothesis_data,
                    tech_analysis=tech_analysis,
                    validation_result=validation_result
                )

                # 验证方案内容不为空且足够详细
                if not genai_proposal or len(genai_proposal.strip()) < 500:
                    raise ValueError(f"生成的方案内容过短: {len(genai_proposal) if genai_proposal else 0} 字符")

                print(f"[GenAI架构师] 方案生成成功，长度: {len(genai_proposal)} 字符")
                break

            except ValueError as ve:
                print(f"[GenAI架构师] 验证失败: {ve}")
                if attempt == self.max_retries - 1:
                    raise ValueError(f"经过 {self.max_retries} 次尝试后仍无法生成有效方案: {ve}")

            except Exception as e:
                print(f"[GenAI架构师] 生成失败: {type(e).__name__}: {e}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"经过 {self.max_retries} 次尝试后仍无法生成方案: {e}")

        # 验证最终结果
        if not genai_proposal or len(genai_proposal.strip()) < 500:
            raise ValueError("生成的GenAI方案为空或过短，无法保存")

        # 保存方案
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        proposal_path = os.path.join(output_dir, f"GenAI_Proposal_{timestamp}.md")

        with open(proposal_path, 'w', encoding='utf-8') as f:
            f.write(genai_proposal)

        print(f"[GenAI架构师] 方案已保存到: {proposal_path}")

        return {
            'success': True,
            'genai_proposal': genai_proposal,
            'proposal_path': proposal_path
        }

    def _generate_genai_proposal(self, hypothesis_data: dict, tech_analysis: dict,
                                 validation_result: dict) -> str:
        """
        生成GenAI赋能方案 - 调用 LLM API

        使用 Claude API 生成专业的 GenAI 赋能方案，包含重试机制
        """
        title = hypothesis_data.get('title', '未命名研究')
        paradigm = hypothesis_data.get('paradigm_framework', '')
        description = hypothesis_data.get('description', '')
        core_hypothesis = hypothesis_data.get('core_hypothesis', '')
        challenge = hypothesis_data.get('grand_challenge', '')
        technical_route = hypothesis_data.get('technical_route', '')

        # 构建技术分析上下文
        tech_context = ""
        if tech_analysis:
            tech_context = f"""

## 技术分析报告（供参考）

{json.dumps(tech_analysis, ensure_ascii=False, indent=2)[:2000]}...
"""

        # 构建验证结果上下文
        validation_context = ""
        if validation_result:
            validation_context = f"""

## 验证报告（供参考）

{json.dumps(validation_result, ensure_ascii=False, indent=2)[:2000]}...
"""

        # 构建 Prompt
        prompt = f"""你是一位**SOTA级别首席生成式AI架构师**（State-of-the-Art GenAI Architect），精通大语言模型、蛋白质/基因组语言模型、扩散模型等前沿GenAI技术。

# CORE MANDATE (核心使命)

你的核心使命是**追求GenAI架构设计的学术巅峰**，而非满足任何比例约束。

## 评估标准 (学术三要素)

1. **新颖性 (Novelty)**: 架构设计或应用场景是否有创新
2. **严谨性 (Rigor)**: 架构设计是否严密，是否有理论支撑
3. **颠覆性 (Disruptiveness)**: 是否挑战现有GenAI范式

## 绝对红线

- **禁止为了"凑GenAI内容"而强行集成AI到不合适的场景**
- **禁止忽视计算成本、数据隐私等实际约束**
- **每个架构选择必须有SOTA文献支撑**

# 任务：设计SOTA级别GenAI深度赋能方案

请生成一份**追求学术巅峰的GenAI深度赋能与大模型架构方案**（Markdown格式）。

## 核心原则

1. **SOTA标准**: 追踪领域最前沿的GenAI技术，拒绝平庸架构
2. **算法创新**: 追求非平凡的架构改进，而非简单应用
3. **可落地实现**: 所有架构必须有具体的代码实现路径
4. **理论支撑**: 每个架构选择必须有SOTA文献支撑

---

## 研究假设信息

**标题**: {title}

**范式框架**: {paradigm}

**核心假设**: {core_hypothesis}

**问题描述**: {description}

**重大挑战**: {challenge}

**技术路线**: {technical_route}
{tech_context}
{validation_context}

---

# 输出要求

请生成一份完整的 **GenAI 深度赋能与大模型架构方案**（Markdown格式），必须包含以下部分：

1. **GenAI赋能机会分析** - 识别可被GenAI技术颠覆或赋能的环节
2. **生成式AI架构设计** - 核心组件、基础模型选择、微调策略
3. **技术实现方案** - 详细的Python代码示例
4. **RAG架构设计**（如适用）- 向量数据库、检索策略
5. **合成数据生成方案**（如适用）- 扩散模型、隐私保护
6. **实施路线图** - 分阶段计划、时间估算
7. **预期性能提升** - 与传统方法对比

# 重要提示

- 方案必须**具体且可实施**，不能泛泛而谈
- 必须包含**详细的代码示例**
- 不要使用"XX"或"待定"等占位符
- 输出完整的Markdown文档

现在请生成完整的GenAI赋能方案："""

        # 调用 LLM API
        response_text = self._call_llm_with_retry(prompt)

        # 提取和验证响应
        proposal_content = self._extract_and_validate_proposal(response_text)

        return proposal_content

    def _call_llm_with_retry(self, prompt: str, max_api_retries: int = 3) -> str:
        """
        调用 LLM API，带重试机制

        Args:
            prompt: 完整的提示词
            max_api_retries: API 调用最大重试次数

        Returns:
            LLM 响应文本

        Raises:
            Exception: API 调用失败或响应内容过短
        """
        for api_attempt in range(max_api_retries):
            try:
                if api_attempt > 0:
                    print(f"[GenAI架构师] API 重试 {api_attempt + 1}/{max_api_retries}")

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

                response_text = "\\n".join(text_parts)

                if not response_text or len(response_text) < 100:
                    raise ValueError(f"LLM返回内容过短: {len(response_text)} 字符")

                print(f"[GenAI架构师] LLM响应成功，长度: {len(response_text)} 字符")
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
                    print(f"[GenAI架构师] API错误，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Claude API错误: {e}")

            except Exception as e:
                raise Exception(f"LLM调用失败: {e}")

        raise Exception("API调用重试次数耗尽")

    def _extract_and_validate_proposal(self, response_text: str) -> str:
        """
        提取并验证方案内容

        Args:
            response_text: LLM 响应文本

        Returns:
            提取的方案内容

        Raises:
            ValueError: 内容为空或过短
        """
        proposal_content = self._extract_markdown_content(response_text)

        # 验证内容长度
        if not proposal_content or len(proposal_content.strip()) < 500:
            raise ValueError(f"提取的方案内容过短: {len(proposal_content) if proposal_content else 0} 字符")

        # 验证是否包含关键章节
        required_keywords = ['GenAI', '生成式AI', '架构', '模型']
        content_lower = proposal_content.lower()
        missing_keywords = [kw for kw in required_keywords if kw.lower() not in content_lower]

        if len(missing_keywords) > 2:
            print(f"[GenAI架构师] 警告: 方案可能缺少关键内容: {missing_keywords}")

        print(f"[GenAI架构师] 方案验证通过，长度: {len(proposal_content)} 字符")
        return proposal_content

    def _extract_markdown_content(self, text: str) -> str:
        """
        提取 Markdown 格式的方案内容

        Args:
            text: 原始响应文本

        Returns:
            提取的 Markdown 内容
        """
        # 模式1: 提取 ```markdown 代码块
        markdown_pattern = r'```(?:markdown)?\\s*([\\s\\S]*?)\\s*```'
        matches = re.findall(markdown_pattern, text, re.IGNORECASE)
        if matches:
            longest = max(matches, key=len)
            if len(longest) > 500:
                return longest.strip()

        # 模式2: 查找以 # GenAI 开头的标题
        genai_pattern = r'(#{1,3}\\s*GenAI[\\s\\S]*?)(?=\\n\\n#{1,3}\\s|\\Z)'
        matches = re.findall(genai_pattern, text, re.MULTILINE | re.DOTALL)
        if matches:
            longest = max(matches, key=len)
            if len(longest) > 500:
                return longest.strip()

        # 模式3: 直接使用全部文本
        return text.strip()


    def _analyze_genai_opportunities(self, paradigm: str, description: str,
                                    challenge: str) -> Dict:
        """分析GenAI赋能机会"""

        paradigm_lower = paradigm.lower()
        desc_lower = description.lower()

        bottlenecks = []
        tech_matrix_rows = []
        architecture_design = ""

        # 1. 数据匮乏检测
        if 'small sample' in desc_lower or 'n<' in desc_lower or 'limited data' in desc_lower:
            bottlenecks.append("- **数据匮乏**：样本量不足以训练高参数量深度学习模型")
            tech_matrix_rows.append("| 扩散模型合成数据 | 数据增强 | ⭐⭐⭐⭐⭐ | 中等 |")
            architecture_design = self._get_diffusion_architecture()

        # 2. 非结构化文本检测
        elif 'clinical text' in desc_lower or 'ehr' in desc_lower or 'unstructured' in desc_lower:
            bottlenecks.append("- **非结构化数据处理**：临床文本/影像需要手工特征提取")
            tech_matrix_rows.append("| Clinical LLM微调 | 自动表型提取 | ⭐⭐⭐⭐⭐ | 简单 |")
            architecture_design = self._get_cllm_architecture()

        # 3. 序列分析检测
        elif 'protein' in desc_lower or 'dna' in desc_lower or 'genome' in desc_lower or 'sequence' in desc_lower:
            bottlenecks.append("- **序列分析瓶颈**：传统比对方法无法进行zero-shot预测")
            tech_matrix_rows.append("| 蛋白质/基因组语言模型 | Zero-shot预测 | ⭐⭐⭐⭐⭐ | 简单 |")
            architecture_design = self._get_sequence_model_architecture()

        # 4. 知识整合需求
        elif 'knowledge' in desc_lower or 'literature' in desc_lower or 'pathway' in desc_lower:
            bottlenecks.append("- **知识整合需求**：海量文献/知识库需要手动整理")
            tech_matrix_rows.append("| RAG架构 | 文献自动检索与问答 | ⭐⭐⭐⭐ | 中等 |")
            architecture_design = self._get_rag_architecture()

        # 5. 生成设计需求
        elif 'design' in desc_lower or 'generate' in desc_lower or 'de novo' in desc_lower:
            bottlenecks.append("- **从头设计需求**：传统方法无法生成新分子/蛋白质")
            tech_matrix_rows.append("| 扩散模型 | De novo设计 | ⭐⭐⭐⭐⭐ | 困难 |")
            architecture_design = self._get_diffusion_design_architecture()

        # 默认
        if not bottlenecks:
            bottlenecks = "- **通用GenAI赋能**：可使用大模型提升方案各环节的性能"
            tech_matrix_rows = [
                "| RAG架构 | 知识增强 | ⭐⭐⭐⭐ | 中等 |",
                "| LoRA微调 | 高效适应 | ⭐⭐⭐ | 简单 |"
            ]
            architecture_design = self._get_generic_genai_architecture()

        return {
            'bottlenecks': '\n'.join(bottlenecks),
            'technology_matrix': '\n'.join(tech_matrix_rows),
            'architecture_design': architecture_design
        }

    def _get_diffusion_architecture(self) -> str:
        """获取扩散模型架构设计"""
        return """
### 条件扩散模型用于合成数据生成

```python
# 条件扩散模型架构
import torch
import torch.nn as nn

class DataDiffusionModel(nn.Module):
    \"\"\"合成数据生成的扩散模型\"\"\"
    def __init__(self, feature_dim, condition_dim, hidden_dim=512):
        super().__init__()
        # 噪声预测网络（U-Net风格）
        self.denoise_net = nn.ModuleDict({
            'time_embed': SinusoidalPosEmb(hidden_dim),
            'layer1': nn.Linear(feature_dim + condition_dim + hidden_dim, hidden_dim),
            'layer2': nn.Linear(hidden_dim, hidden_dim),
            'layer3': nn.Linear(hidden_dim, feature_dim)
        })

    def forward(self, x_t, condition, timestep):
        # 预测噪声
        return self.denoise_net['layer3'](
            F.relu(self.denoise_net['layer2'](
                F.relu(self.denoise_net['layer1'](
                    torch.cat([x_t, condition, self.time_embed(timestep)], dim=-1)
                ))
            ))
        )

# 训练策略
def train_diffusion(model, real_data, conditions, n_epochs=1000):
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)

    for epoch in range(n_epochs):
        # 采样时间步
        t = torch.randint(0, 1000, (real_data.shape[0],))

        # 添加噪声
        noise = torch.randn_like(real_data)
        x_t = real_data * (1 - t/1000) + noise * (t/1000)

        # 预测噪声
        noise_pred = model(x_t, conditions, t)

        # 损失
        loss = F.mse_loss(noise_pred, noise)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
```
"""

    def _get_cllm_architecture(self) -> str:
        """获取Clinical LLM架构设计"""
        return """
### Clinical LLM微调架构

```python
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from peft import LoraConfig, get_peft_model

# 1. 加载基础模型
model_name = "emilyalsentzer/Bio-ClinicalBERT"
base_model = AutoModelForSequenceClassification.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)

# 2. LoRA配置
lora_config = LoraConfig(
    task_type=TaskType.SEQ_CLS,
    r=16,
    lora_alpha=32,
    target_modules=["query", "value"],
    lora_dropout=0.05,
    bias="none",
)

# 3. 应用LoRA
model = get_peft_model(base_model, lora_config)
model.print_trainable_parameters()
# trainable params: 300k || all params: 110M || trainable%: 0.27%

# 4. 微调
from transformers import Trainer

training_args = TrainingArguments(
    output_dir="./clinical_llm_finetuned",
    learning_rate=2e-4,
    per_device_train_batch_size=16,
    gradient_accumulation_steps=2,
    num_train_epochs=3,
    weight_decay=0.01,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=clinical_dataset,
    eval_dataset=eval_dataset,
)

trainer.train()
```
"""

    def _get_sequence_model_architecture(self) -> str:
        """获取序列模型架构设计"""
        return """
### 蛋白质语言模型架构

```python
import torch
from esm import pretrained

# 1. 加载ESM-2模型
model, alphabet = pretrained.load_model_and_alphabet('esm2_t33_650M_UR50D')
batch_converter = alphabet.get_batch_converter()

# 2. Zero-shot蛋白质功能预测
def predict_protein_function(sequence):
    data = [("protein", sequence)]
    batch_labels, batch_strs, batch_tokens = batch_converter(data)

    with torch.no_grad():
        results = model(batch_tokens, repr_layers=[33])

    # 提取嵌入
    embeddings = results['representations'][33]

    # 下游任务
    function_pred = function_head(embeddings)
    return function_pred

# 3. 微调ESM-2
from transformers import EsmModel, EsmForSequenceClassification

esm_model = EsmForSequenceClassification.from_pretrained(
    "facebook/esm2_t33_650M_UR50D",
    num_labels=10  # 10种功能分类
)

# LoRA微调
from peft import LoraConfig, get_peft_model

lora_config = LoraConfig(
    target_modules=["query", "key", "value"],
    r=16,
    lora_alpha=32,
)

esm_model = get_peft_model(esm_model, lora_config)
```
"""

    def _get_rag_architecture(self) -> str:
        """获取RAG架构设计"""
        return """
### RAG（检索增强生成）架构

```python
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import ChromaDB
from langchain.chains import RetrievalQA
from langchain.llms import HuggingFacePipeline

# 1. 向量数据库
embedding = HuggingFaceEmbeddings(
    model_name="BAAI/bge-m3",  # 多语言嵌入
    encode_kwargs={{'normalize_embeddings': True}}
)

vectorstore = ChromaDB(
    collection_name="biomedical_knowledge",
    embedding_function=embedding,
    persist_directory="./chroma_db"
)

# 2. 加载文献/知识库
from langchain.document_loaders import PubMedLoader

documents = []
for pmid in pmid_list:
    loader = PubMedLoader(pmid)
    documents.extend(loader.load())

# 分割并索引
from langchain.text_splitter import RecursiveCharacterTextSplitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=50
)

splits = text_splitter.split_documents(documents)
vectorstore.add_documents(splits)

# 3. 检索器
retriever = vectorstore.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={{"k": 5, "score_threshold": 0.7}}
)

# 4. LLM
llm = HuggingFacePipeline.from_model_id(
    model_id="meta-llama/Llama-2-7b-chat-hf",
    device=0,
    task="text-generation"
)

# 5. RAG链
rag_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
    return_source_documents=True
)

# 6. 查询
query = "What are the latest ML advances in cardiology?"
result = rag_chain({{"query": query}})
```
"""

    def _get_diffusion_design_architecture(self) -> str:
        """获取扩散设计架构"""
        return """
### 扩散模型用于De novo设计

```python
# RFdiffusion风格的蛋白质设计
import torch
import torch.nn as nn

class ProteinDiffusion(nn.Module):
    \"\"\"蛋白质结构扩散模型\"\"\"
    def __init__(self, seq_length, structure_dim):
        super().__init__()
        self.seq_length = seq_length
        self.structure_dim = structure_dim

        # 噪声预测网络（E(3)等变）
        self.denoise_net = EquivariantTransformer(
            num_layers=12,
            hidden_dim=256,
            num_heads=8,
            attention_type='structure_aware'
        )

    def forward(self, structure_t, condition, timestep):
        # 预测结构噪声
        noise_pred = self.denoise_net(
            structure_t,
            condition=condition,
            timestep=timestep
        )
        return noise_pred

# 采样函数
@torch.no_grad()
def design_protein(diffusion_model, condition, n_samples=10):
    \"\"\"生成新的蛋白质结构\"\"\"
    device = next(diffusion_model.parameters()).device

    # 从纯噪声开始
    structure = torch.randn(n_samples, diffusion_model.structure_dim).to(device)

    # 反向扩散
    for t in reversed(range(1000)):
        # 预测噪声
        noise_pred = diffusion_model(structure, condition, t)

        # 去噪
        structure = denoise_step(structure, noise_pred, t)

    return structure

# 条件：结合ATP的蛋白质
condition = {{
    "binding_site": "ATP",
    "affinity": "high"
}}

designed_proteins = design_protein(diffusion_model, condition)
```
"""

    def _get_generic_genai_architecture(self) -> str:
        """获取通用GenAI架构"""
        return """
### 通用GenAI赋能架构

```python
# 组合多种GenAI技术
from transformers import AutoModel
from peft import get_peft_model

# 1. 语言模型嵌入
class GenAIEnhancedModel(nn.Module):
    def __init__(self, base_model_name, num_labels):
        super().__init__()

        # 预训练语言模型
        self.encoder = AutoModel.from_pretrained(base_model_name)

        # LoRA适配器
        lora_config = LoraConfig(r=16, target_modules=["q_proj", "v_proj"])
        self.encoder = get_peft_model(self.encoder, lora_config)

        # 分类头
        self.classifier = nn.Sequential(
            nn.Linear(self.encoder.config.hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, num_labels)
        )

    def forward(self, input_ids, attention_mask):
        outputs = self.encoder(input_ids, attention_mask=attention_mask)
        pooled = outputs.last_hidden_state[:, 0, :]
        logits = self.classifier(pooled)
        return logits

# 2. RAG增强检索
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings

vectorstore = FAISS.from_texts(
    texts=knowledge_base,
    embedding=OpenAIEmbeddings()
)

retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
```
"""


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    # 测试GenAI专家
    genai_expert = GenAIExpertAgent()

    result = genai_expert.execute({
        'hypothesis_data': {
            'title': 'CausalSC: 因果发现与深度学习耦合的单细胞因果推断框架',
            'paradigm_framework': '因果推断 + 深度学习 + 单细胞组学',
            'grand_challenge': '单细胞数据的因果盲区',
            'description': '小样本单细胞数据的因果推断，需要生成合成数据'
        },
        'tech_analysis': {},
        'validation_result': {},
        'output_dir': 'reports'
    })

    if result['success']:
        print("GenAI赋能方案已生成")
        print(f"保存路径: {result['proposal_path']}")
