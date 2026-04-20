# -*- coding: utf-8 -*-
"""
数字病理学与机器视觉专家智能体 (DigitalPathologyAgent)
SOTA级别空间拓扑分析专家

核心身份 (CORE MANDATE):
- **高维空间拓扑分析**: 从十亿像素WSI中提取有意义的空间模式
- **图神经网络 (GNN) 建模**: 使用GNN对WSI图像特征进行拓扑建模
- **细胞通讯拓扑验证**: 验证计算推断的细胞-细胞相互作用在空间上的真实性
- **长程依赖捕获**: 建模跨越数百微米的远距离细胞相互作用

绝对红线:
- 绝对禁止提及任何物理制片/染色过程
- 禁止为了"凑空间模式"而过度解读噪声
- 每个空间结论必须有组织学验证

核心评估标准 (学术三要素):
- **新颖性 (Novelty)**: 空间分析方法或视角是否有创新
- **严谨性 (Rigor)**: 空间统计是否严密，拓扑验证是否到位
- **颠覆性 (Disruptiveness)**: 是否挑战现有空间组织范式

职责范围:
1. 数字全切片(WSI)图像分析
2. 空间转录组数据分析
3. 组织微环境拓扑建模
4. 图神经网络(GNN)在病理图像中的应用
5. 多尺度特征提取（细胞级、组织级、切片级）
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


# ============ 数字病理学前沿技术栈 ============

DIGITAL_PATHOLOGY_TECH_STACK = {
    'wsi_analysis': {
        'preprocessing': {
            'TissueSegmentation': 'Otsu阈值、深度学习分割',
            'MacrowaveRemoval': '伪影去除',
            'ColorNormalization': 'Macenko或Vahadane归一化',
            'PatchExtraction': '多尺度切块策略'
        },
        'feature_extraction': {
            'Handcrafted': '形态学特征、纹理特征(GLCM/LBP)',
            'DeepLearning': 'ResNet、EfficientNet、Vision Transformer',
            'SelfSupervised': 'SimCLR、MoCo、DINO自监督预训练'
        },
        'cell_detection': {
            'CellProfiler': '经典细胞检测',
            'HoVer-Net': '同时分割和分类',
            'Cellpose': '通用细胞分割',
            'QuPath': '开源病理图像分析'
        }
    },
    'spatial_analysis': {
        'spatial_transcriptomics': {
            'Visium': '10x Genomics空间转录组',
            'Slide-seq': '高分辨率空间转录组',
            'MERFISH': '多重误差稳健荧光原位杂交',
            'seqFISH': '序贯荧光原位杂交'
        },
        'topology_modeling': {
            'GNN': '图神经网络建模细胞相互作用',
            'SpatialAutocorrelation': 'Moran\'s I、Geary\'s C',
            'RipleyK': '空间聚类分析',
            'NicheNet': '细胞通讯推断'
        }
    },
    'microenvironment': {
        'tme_quantification': {
            'ImmuneInfiltration': '免疫细胞浸润评估',
            'TumorPurity': '肿瘤纯度估算',
            'StromalRatio': '基质比例计算',
            'VascularDensity': '血管密度分析'
        },
        'cellular_interaction': {
            'LigandReceptor': '配体-受体对分析',
            'CellPhoneDB': '细胞通讯数据库',
            'NATMI': '互作网络分析'
        }
    },
    'deep_learning': {
        'architectures': {
            'CNN': '卷积神经网络(ResNet、DenseNet)',
            'VisionTransformer': 'ViT、Swin Transformer',
            'MultipleInstanceLearning': 'MIL弱监督学习',
            'GraphNeuralNetwork': 'GCN、GAT、GraphSAGE'
        },
        'self_supervised': {
            'DINO': 'ViT自监督学习',
            'MoCo': '动量对比学习',
            'SimCLR': '简单对比学习',
            'BYOL': '自举学习'
        }
    },
    'integration': {
        'multi_modal': {
            'PathologyGenomics': '病理图像与基因组整合',
            'Radiogenomics': '影像组学',
            'SpatialOmics': '空间多组学整合'
        }
    }
}


class DigitalPathologyAgent(BaseAgent):
    """
    数字病理学与机器视觉专家智能体 (SOTA Digital Pathologist)

    Core Mandate:
    - 高维空间拓扑分析: 从十亿像素WSI中提取有意义的空间模式
    - 图神经网络建模: 使用GNN对WSI图像特征进行拓扑建模
    - 细胞通讯拓扑验证: 验证计算推断的细胞相互作用在空间上的真实性
    - 长程依赖捕获: 建模跨越数百微米的远距离细胞相互作用

    评估标准:
    - 新颖性: 空间分析方法或视角是否有创新
    - 严谨性: 空间统计是否严密，拓扑验证是否到位
    - 颠覆性: 是否挑战���有空间组织范式

    禁止: 物理制片/染色过程，过度解读噪声
    """

    def __init__(self):
        super().__init__("数字病理学专家", agent_type="digital_pathology")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.max_retries = 3
        self.model = os.getenv("PATHOLOGY_MODEL", "claude-opus-4-6")
        self.extractor = SafeExtractor()

    def execute(self, input_data: Dict) -> Dict:
        """
        执行数字病理学分析方案设计

        Args:
            input_data: {
                'hypothesis_data': dict - 假设数据
                'genai_proposal': str - GenAI架构方案
                'compbio_proposal': str - 计算生物学方案
                'output_dir': str - 输出目录
            }

        Returns:
            {
                'success': bool,
                'pathology_proposal': str - 数字病理学方案
                'spatial_design': dict - 空间分析设计
                'report_path': str - 报告保存路径
            }
        """
        hypothesis_data = input_data.get('hypothesis_data', {})
        genai_proposal = input_data.get('genai_proposal', '')
        compbio_proposal = input_data.get('compbio_proposal', '')
        output_dir = input_data.get('output_dir', 'reports')

        if not hypothesis_data:
            raise ValueError('缺少假设数据 (hypothesis_data)')

        print(f"[数字病理学专家] 开始设计WSI分析Pipeline，假设: {hypothesis_data.get('title', 'Unknown')}")

        # 使用重试机制生成数字病理学方案
        pathology_proposal = None
        for attempt in range(self.max_retries):
            try:
                print(f"[数字病理学专家] 第 {attempt + 1}/{self.max_retries} 次尝试生成方案...")
                pathology_proposal = self._generate_pathology_proposal(
                    hypothesis_data=hypothesis_data,
                    genai_proposal=genai_proposal,
                    compbio_proposal=compbio_proposal
                )

                # 验证方案内容不为空且足够详细
                if not pathology_proposal or len(pathology_proposal.strip()) < 500:
                    raise ValueError(f"生成的方案内容过短: {len(pathology_proposal) if pathology_proposal else 0} 字符")

                print(f"[数字病理学专家] 方案生成成功，长度: {len(pathology_proposal)} 字符")
                break

            except ValueError as ve:
                print(f"[数字病理学专家] 验证失败: {ve}")
                if attempt == self.max_retries - 1:
                    raise ValueError(f"经过 {self.max_retries} 次尝试后仍无法生成有效方案: {ve}")

            except Exception as e:
                print(f"[数字病理学专家] 生成失败: {type(e).__name__}: {e}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"经过 {self.max_retries} 次尝试后仍无法生成方案: {e}")

        # 验证最终结果
        if not pathology_proposal or len(pathology_proposal.strip()) < 500:
            raise ValueError("生成的数字病理学方案为空或过短，无法保存")

        # 保存方案
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"DigitalPathology_Pipeline_{timestamp}.md")

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(pathology_proposal)

        print(f"[数字病理学专家] 方案已保存到: {report_path}")

        # 提取结构化空间分析设计
        spatial_design = self._extract_spatial_design(pathology_proposal)

        return {
            'success': True,
            'pathology_proposal': pathology_proposal,
            'spatial_design': spatial_design,
            'report_path': report_path
        }

    def _generate_pathology_proposal(self, hypothesis_data: dict,
                                      genai_proposal: str,
                                      compbio_proposal: str) -> str:
        """
        生成数字病理学方案 - 调用 LLM API

        你是一位赛博飞升的病理医生（Digital Pathology Expert），
        将传统病理学与深度学习完美融合。

        你的核心技能包括但不限于：
        - **WSI分析**：十亿像素级全切片图像处理
        - **空间转录组**：Visium、Slide-seq、MERFISH数据分析
        - **组织微环境建模**：使用GNN进行拓扑分析
        - **多尺度特征提取**：细胞级、组织级、切片级

        绝对禁止：任何物理制片/染色过程（H&E染色、免疫组化、切片制作）
        """
        title = hypothesis_data.get('title', '未命名研究')
        paradigm = hypothesis_data.get('paradigm_framework', '')
        description = hypothesis_data.get('description', '')
        challenge = hypothesis_data.get('grand_challenge', '')

        # 构建上游上下文
        genai_context = ""
        if genai_proposal:
            genai_context = f"""

## GenAI架构方案（上游输入）

{genai_proposal[:1500]}...
"""

        compbio_context = ""
        if compbio_proposal:
            compbio_context = f"""

## 计算生物学Pipeline（上游输入）

{compbio_proposal[:1500]}...
"""

        # 构建 Prompt
        prompt = f"""你是一位**SOTA级别数字病理学与机器视觉专家**（State-of-the-Art Digital Pathologist），专注于高维空间拓扑分析。

# CORE MANDATE (核心使命)

你的核心使命是**追求空间拓扑分析的学术巅峰**，而非满足任何比例约束。

## 评估标准 (学术三要素)

1. **新颖性 (Novelty)**: 空间分析方法或视角是否有创新
2. **严谨性 (Rigor)**: 空间统计是否严密，拓扑验证是否到位
3. **颠覆性 (Disruptiveness)**: 是否挑战现有空间组织范式

## 核心技能

- **高维空间拓扑分析**: 从十亿像素WSI中提取有意义的空间模式
- **图神经网络 (GNN)**: 使用GNN对WSI图像特征进行拓扑建模
- **长程依赖捕获**: 建模跨越数百微米的远距离细胞相互作用
- **细胞通讯拓扑验证**: 验证计算推断的细胞相互作用在空间上的真实性
- **WSI分析**: 十亿像素级全切片处理、切块策略、特征提取
- **空间转录组**: Visium、Slide-seq、MERFISH数据分析
- **深度学习**: CNN、Vision Transformer、多示例学习(MIL)

## 绝对红线

- **绝不涉及任何物理制片/染色过程**（H&E染色、免疫组化、切片制作、玻片处理）
- **禁止为了"凑空间模式"而过度解读噪声**
- **每个空间结论必须有组织学验证**

---

# 研究假设信息

**标题**: {title}

**范式框架**: {paradigm}

**核心假设**: {description}

**重大挑战**: {challenge}
{genai_context}
{compbio_context}

---

# 任务：设计SOTA级别数字病理学与空间分析Pipeline

请生成一份**追求学术巅峰的数字病理学与空间分析方案**（Markdown格式）。

## 核心原则

1. **空间拓扑优先**: 从高维WSI中提取有意义的空间模式
2. **GNN建模**: 使用图神经网络进行拓扑分析
3. **长程依赖**: 捕获跨越数百微米的远距离细胞相互作用
4. **拓扑验证**: 验证计算推断的细胞相互作用在空间上的真实性

## 1. WSI图像预处理Pipeline
- 组织区域检测与分割
- 色彩归一化（Macenko/Vahadane）
- 多尺度切块策略（patch size、overlap）
- 伪影去除（气泡、折叠、划痕）

## 2. 特征提取架构
- 深度学习backbone选择（ResNet/EfficientNet/ViT）
- 自监督预训练策略（DINO/MoCo）
- 手工特征（形态学、纹理、细胞核特征）
- 多模态特征融合

## 3. 空间分析策略
- 空间转录组数据处理（如适用）
- 图神经网络设计（GCN/GAT/GraphSAGE）
- 组织微环境拓扑建模
- 细胞-细胞相互作用推断

## 4. Python实现代码
- WSI读取与处理（openslide、tifffile）
- 深度模型构建（PyTorch/TensorFlow）
- GNN实现（PyTorch Geometric）
- 空间统计分析（squidpy、scanpy）

## 5. 计算资源需求
- GPU显存需求（处理大尺寸WSI）
- 存储需求（原始图像约1-5GB/张）
- 并行处理策略

---

# 输出要求

1. **纯数字分析**：所有输入均为数字图像，不涉及物理实验
2. **具体可行**：提供可直接运行的代码框架
3. **版本明确**：指定关键库的版本号
4. **不要占位符**：不要使用"XX"或"待定"
5. **Markdown格式**：输出完整的Markdown文档

现在请生成完整的数字病理学Pipeline方案："""

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
                    print(f"[数字病理学专家] API 重试 {api_attempt + 1}/{max_api_retries}")

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

                print(f"[数字病理学专家] LLM响应成功，长度: {len(response_text)} 字符")
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
                    print(f"[数字病理学专家] API错误，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Claude API错误: {e}")

            except Exception as e:
                raise Exception(f"LLM调用失败: {e}")

        raise Exception("API调用重试次数耗尽")

    def _extract_spatial_design(self, proposal: str) -> Dict:
        """从方案中提取结构化空间分析设计"""
        import re

        design = {
            'wsi_processing': [],
            'spatial_methods': [],
            'gnn_architectures': [],
            'computational_requirements': {
                'gpu': 'unknown',
                'storage': 'unknown'
            }
        }

        # 提取WSI处理方法
        wsi_patterns = {
            'patch_extraction': r'(?:patch|切块|tile)',
            'color_normalization': r'(?:Macenko|Vahadane|归一化|normalization)',
            'tissue_segmentation': r'(?:组织分割|tissue.?segment|Otsu)'
        }

        for method, pattern in wsi_patterns.items():
            if re.search(pattern, proposal, re.IGNORECASE):
                design['wsi_processing'].append(method)

        # 提取空间分析方法
        spatial_patterns = {
            'Visium': r'Visium',
            'Slide-seq': r'Slide.?seq',
            'MERFISH': r'MERFISH',
            'GNN': r'(?:GNN|图神经|graph.?network)',
            'spatial_autocorrelation': r'(?:Moran|Geary|spatial.?auto)'
        }

        for method, pattern in spatial_patterns.items():
            if re.search(pattern, proposal, re.IGNORECASE):
                design['spatial_methods'].append(method)

        # 提取GNN架构
        gnn_patterns = {
            'GCN': r'GCN',
            'GAT': r'GAT',
            'GraphSAGE': r'GraphSAGE',
            'PyTorch Geometric': r'PyG|PyTorch.?Geometric'
        }

        for arch, pattern in gnn_patterns.items():
            if re.search(pattern, proposal, re.IGNORECASE):
                design['gnn_architectures'].append(arch)

        # 提取计算资源
        if re.search(r'GPU|cuda|RTX|A100', proposal, re.IGNORECASE):
            design['computational_requirements']['gpu'] = 'required'

        storage_match = re.search(r'(\d+)\s*(GB|TB)', proposal, re.IGNORECASE)
        if storage_match:
            design['computational_requirements']['storage'] = f"{storage_match.group(1)}{storage_match.group(2)}"

        return design


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    # 测试数字病理学专家
    test_hypothesis = {
        'title': '基于WSI和空间转录组的肿瘤微环境建模',
        'description': '整合数字病理图像和空间转录组数据，构建肿瘤微环境的图神经网络模型',
        'paradigm_framework': '数字病理 + GNN + 空间组学',
        'grand_challenge': '肿瘤微环境的细胞异质性'
    }

    agent = DigitalPathologyAgent()
    result = agent.execute({
        'hypothesis_data': test_hypothesis,
        'genai_proposal': '使用Vision Transformer提取病理图像特征',
        'compbio_proposal': '单细胞RNA-seq数据处理流程',
        'output_dir': 'reports'
    })

    if result['success']:
        print("=" * 60)
        print("数字病理学Pipeline设计完成")
        print("=" * 60)
        print(f"报告路径: {result['report_path']}")
        print(f"WSI处理: {result['spatial_design']['wsi_processing']}")
        print(f"空间方法: {result['spatial_design']['spatial_methods']}")
