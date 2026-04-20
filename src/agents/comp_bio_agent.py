# -*- coding: utf-8 -*-
"""
计算生物学专家智能体 (CompBioAgent)
SOTA级别多组学整合专家

核心身份 (CORE MANDATE):
- **SOTA级多组学整合**: 追踪领域最前沿算法，拒绝平庸方案
- **极其严苛的QC协议**: 数据质量是计算分析的绝对基石，不可妥协
- **生物学机制计算建模**: 从模式发现到机制解析，追求可解释性

绝对红线:
- 禁止任何湿实验操作（细胞培养、动物模型、染色切片）
- 禁止为了"凑内容"而生成平庸分析
- 每个算法选择必须有SOTA文献支撑

核心评估标准 (学术三要素):
- **新颖性 (Novelty)**: 方法或分析视角是否有创新
- **严谨性 (Rigor)**: 统计方法是否严密，QC是否到位
- **颠覆性 (Disruptiveness)**: 是否挑战现有范式

职责范围:
1. 单细胞转录组学分析（scRNA-seq去噪、批次效应校正、轨迹推断）
2. 多组学数据整合（基因组、转录组、蛋白质组、代谢组）
3. 蛋白质结构预测与分子对接（AlphaFold、ESM、RoseTTAFold）
4. 基因调控网络推断（SCENIC、GRNBoost2、因果发现）
5. 系统生物学建模（信号通路、代谢网络、动力学模拟）

输入数据依赖：
- GenAIExpertAgent的输出（底层架构方案）
- 原始假设数据

输出成果：
- 高维组学数据处理Pipeline
- 蛋白质结构预测方案
- 多组学整合分析策略
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
    ModalityAwarePreprocessor
)


# ============ 计算生物学前沿技术栈 ============

COMPBIO_TECH_STACK = {
    'single_cell_analysis': {
        'denoising_methods': {
            'MAGIC': '基于扩散的单细胞数据去噪',
            'SAVER': '单细胞表达量恢复',
            'scImpute': '单细胞插补',
            'DCA': '深度计数自动编码器',
            'scVI': '单细胞变分推断'
        },
        'batch_correction': {
            'Harmony': '谐波整合算法',
            'BBKNN': '批次平衡k近邻',
            'SeuratIntegration': '基于CCA的整合',
            'Scanorama': '全景整合',
            'LIGER': '集成非负矩阵分解'
        },
        'dimensionality_reduction': {
            'UMAP': '统一流形逼近与投影',
            'tSNE': 't分布随机邻域嵌入',
            'PHATE': '潜在时间势类似分析',
            'DiffusionMaps': '扩散映射',
            'PCA': '主成分分析'
        }
    },
    'multi_omics_integration': {
        'methods': {
            'MOFA+': '多组学因子分析',
            'SNF': '相似性网络融合',
            'iClusterPlus': '整合聚类',
            'mixOmics': '多组学混合模型',
            'MOGSA': '多组学基因集分析'
        }
    },
    'protein_structure': {
        'prediction': {
            'AlphaFold2': '深度学习蛋白质结构预测',
            'AlphaFold-Multimer': '蛋白质复合物预测',
            'ESMFold': 'Meta蛋白质语言模型预测',
            'RoseTTAFold': '三轨神经网络'
        },
        'language_models': {
            'ESM-2': '650M参数蛋白质语言模型',
            'ESM-3': '多模态蛋白质模型',
            'ProtBert': '基于BERT的蛋白质模型',
            'TAPE': '蛋白质评估基准'
        }
    },
    'genomic_analysis': {
        'variant_calling': {
            'GATK': '基因组分析工具包',
            'DeepVariant': '深度学习变异检测',
            'FreeBayes': '贝叶斯变异检测'
        },
        'gene_expression': {
            'DESeq2': '差异表达分析',
            'edgeR': '经验贝叶斯方法',
            'limma': '线性模型微阵列分析'
        }
    },
    'network_analysis': {
        'grn_inference': {
            'SCENIC': '单细胞调控网络推断',
            'PIDC': '部分信息分解',
            'GRNBoost2': '基于梯度的网络推断',
            'Inferelator': '贝叶斯网络推断'
        },
        'pathway_analysis': {
            'GSEA': '基因集富集分析',
            'ReactomePA': '反应通路分析',
            'clusterProfiler': '聚类谱分析'
        }
    }
}


class CompBioAgent(BaseAgent):
    """
    计算生物学专家智能体 (SOTA Computational Biologist)

    Core Mandate:
    - SOTA级多组学整合：追踪领域最前沿，拒绝平庸方案
    - 极其严苛的QC协议：数据质量是绝对基石，不可妥协
    - 生物学机制计算建模：从模式发现到机制解析

    评估标准:
    - 新颖性: 方法或分析视角是否有创新
    - 严谨性: 统计方法是否严密，QC是否到位
    - 颠覆性: 是否挑战现有范式

    禁止: 任何湿实验操作，为了"凑内容"生成平庸分析
    """

    def __init__(self):
        super().__init__("计算生物学专家", agent_type="comp_bio")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.max_retries = 3
        self.model = os.getenv("COMPBIO_MODEL", "claude-opus-4-6")
        self.extractor = SafeExtractor()

    def execute(self, input_data: Dict) -> Dict:
        """
        执行计算生物学分析方案设计

        Args:
            input_data: {
                'hypothesis_data': dict - 假设数据
                'genai_proposal': str - GenAI架构方案
                'output_dir': str - 输出目录
            }

        Returns:
            {
                'success': bool,
                'compbio_proposal': str - 计算生物学方案
                'pipeline_design': dict - Pipeline设计
                'report_path': str - 报告保存路径
            }
        """
        hypothesis_data = input_data.get('hypothesis_data', {})
        genai_proposal = input_data.get('genai_proposal', '')
        output_dir = input_data.get('output_dir', 'reports')

        if not hypothesis_data:
            raise ValueError('缺少假设数据 (hypothesis_data)')

        print(f"[计算生物学专家] 开始设计Pipeline，假设: {hypothesis_data.get('title', 'Unknown')}")

        # 使用重试机制生成计算生物学方案
        compbio_proposal = None
        for attempt in range(self.max_retries):
            try:
                print(f"[计算生物学专家] 第 {attempt + 1}/{self.max_retries} 次尝试生成方案...")
                compbio_proposal = self._generate_compbio_proposal(
                    hypothesis_data=hypothesis_data,
                    genai_proposal=genai_proposal
                )

                # 验证方案内容不为空且足够详细
                if not compbio_proposal or len(compbio_proposal.strip()) < 500:
                    raise ValueError(f"生成的方案内容过短: {len(compbio_proposal) if compbio_proposal else 0} 字符")

                print(f"[计算生物学专家] 方案生成成功，长度: {len(compbio_proposal)} 字符")
                break

            except ValueError as ve:
                print(f"[计算生物学专家] 验证失败: {ve}")
                if attempt == self.max_retries - 1:
                    raise ValueError(f"经过 {self.max_retries} 次尝试后仍无法生成有效方案: {ve}")

            except Exception as e:
                print(f"[计算生物学专家] 生成失败: {type(e).__name__}: {e}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"经过 {self.max_retries} 次尝试后仍无法生成方案: {e}")

        # 验证最终结果
        if not compbio_proposal or len(compbio_proposal.strip()) < 500:
            raise ValueError("生成的计算生物学方案为空或过短，无法保存")

        # 保存方案
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"CompBio_Pipeline_{timestamp}.md")

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(compbio_proposal)

        print(f"[计算生物学专家] 方案已保存到: {report_path}")

        # 提取结构化Pipeline设计和QC协议
        pipeline_design = self._extract_pipeline_design(compbio_proposal)
        qc_protocol = self._extract_qc_protocol(compbio_proposal)

        return {
            'success': True,
            'compbio_proposal': compbio_proposal,
            'pipeline_design': pipeline_design,
            'qc_protocol': qc_protocol,  # 新增：QC协议
            'report_path': report_path
        }

    def _generate_compbio_proposal(self, hypothesis_data: dict,
                                    genai_proposal: str) -> str:
        """
        生成计算生物学方案 - 调用 LLM API

        你是一位顶尖计算生物学家，专注于高维组学数据的纯计算分析。
        你精通但不限于：scRNA-seq去噪、多组学降维、AlphaFold结构预测、
        基因调控网络推断、系统生物学建模。

        绝对禁止：任何涉及湿实验的内容（细胞培养、动物模型、染色切片）
        """
        title = hypothesis_data.get('title', '未命名研究')
        paradigm = hypothesis_data.get('paradigm_framework', '')
        description = hypothesis_data.get('description', '')
        challenge = hypothesis_data.get('grand_challenge', '')
        technical_route = hypothesis_data.get('technical_route', '')

        # ========== 模态感知预处理协议生成 ==========
        combined_text = f"{title} {paradigm} {description} {challenge} {technical_route}"
        modality_info = ModalityDetector.detect_modality(combined_text)
        print(f"[计算生物学专家] 模态检测: {modality_info['primary_modality']}")
        preprocessing_protocol = ModalityAwarePreprocessor.generate_preprocessing_protocol(
            modality_info, hypothesis_data
        )

        # 构建GenAI上下文
        genai_context = ""
        if genai_proposal:
            genai_context = f"""

## GenAI架构方案（上游输���）

{genai_proposal[:2000]}...
"""

        # 构建 Prompt
        prompt = f"""你是一位**SOTA级别计算生物学家**（State-of-the-Art Computational Biologist）。

# CORE MANDATE (核心使命)

你的核心使命是**追求计算生物学的学术巅峰**，而非满足任何比例约束。

## 评估标准 (学术三要素)

1. **新颖性 (Novelty)**: 方法或分析视角是否有创新
2. **严谨性 (Rigor)**: 统计方法是否严密，QC是否到位
3. **颠覆性 (Disruptiveness)**: 是否挑战现有范式

## 核心技能

- **单细胞转录组学**: scRNA-seq去噪、批次效应校正、轨迹推断
- **多组学整合**: 基因组、转录组、蛋白质组、代谢组的联合分析
- **蛋白质结构预测**: AlphaFold、ESM、RoseTTAFold
- **基因调控网络推断**: SCENIC、GRNBoost2、因果发现算法
- **系统生物学建模**: 信号通路、代谢网络、动力学模拟

## 绝对红线

- **绝不涉及任何湿实验操作**（细胞培养、动物模型、染色切片、物理实验）
- **绝不为了"凑内容"生成平庸分析**
- **每个算法选择必须有SOTA文献支撑**

---

# 研究假设信息

**标题**: {title}

**范式框架**: {paradigm}

**核心假设**: {description}

**重大挑战**: {challenge}

**技术路线**: {technical_route}

**检测到的数据模态**: {modality_info['primary_modality']}

{genai_context}

---

## 【模态感知预处理协议】（已根据数据类型自动生成）

{preprocessing_protocol}

---

# 任务：设计SOTA级别计算生物学Pipeline

请生成一份**追求学术巅峰的计算生物学分析方案**（Markdown格式）。

## 核心原则

1. **拒绝平庸**: 每个方法选择都必须是领域SOTA或接近SOTA
2. **QC至上**: Data QC & Harmonization Protocol必须是独立的、极其详尽的子模块
3. **机制导向**: 不仅要发现模式，更要解析生物学机制
4. **可复现性**: 提供可直接运行的代码框架，指定版本号

## 【核心子模块】Data QC & Harmonization Protocol
**这是CompBioAgent输出中必须包含的独立子模块，没有此协议后续分析视为无效**

### 1.1 批次效应检测与校正
- 批次效应检测方法（PCA可视化、KB测试、RLE图）
- 校正算法选择（ComBat/ComBat-seq/Harmony/MNN/scVI）
- **强制要求**：明确说明是否需要ComBat校正及原因
- 校正效果验证方案

### 1.2 缺失值插补策略
- 缺失模式识别（MCAR/MAR/MNAR）
- 插补方法选择（MICE/MissForest/KNN/深度学习）
- 多重插补实现（m=5-10次插补）
- 插补结果验证

### 1.3 多中心数据异质性校准
- 中心间差异评估（PERMANOVA分析）
- 跨中心调和策略（ComBat/CVAE/Domain Adaptation）
- 中心特异性效应保留策略
- 调和后一致��验证

### 1.4 数据质量控制清单
- 样本级QC标准（线粒体基因比例、检测基因数、UMI数）
- 特征级QC标准（低表达基因过滤、高变基因选择）
- 异常样本检测与处理
- QC通过/失败判定标准

## 2. 数据类型与预处理
- 识别研究涉及的高维组学数据类型
- 原始数据格式与读取方法
- 基因注释与映射

## 3. 核心分析模块
根据研究需求选择：
- **单细胞分析**：降维（UMAP/tSNE）、聚类、细胞类型注释、轨迹推断
- **差异表达分析**：DESeq2/edgeR/limma
- **网络推断**：基因调控网络、蛋白质相互作用网络
- **结构预测**：AlphaFold/ESM预测蛋白质3D结构

## 4. 多组学整合策略
- 整合方法选择（MOFA+、SNF等）
- 跨组学关联分析
- 因果推断设计

## 5. 虚拟验证闭环（In silico Validation Loop）- 强制
**针对预测的生物靶点，必须设计计算模拟验证方案**

### 5.1 蛋白质结构模拟验证
- **AlphaFold3/Multimer预测**：预测靶点蛋白-蛋白复合物结构
- **结合亲和力估算**：使用FoldX、Rosetta计算ΔΔG
- **构象稳定性分析**：分子动力学模拟（GROMACS/AMBER）
- **突变扫描**：In silico饱和突变预测功能影响

### 5.2 代谢网络模拟验证
- **单基因剔除模拟（In silico Knockout）**：使用COBRApy预测必需基因
- **通量平衡分析（FBA）**：预测代谢通路扰动后果
- **网络鲁棒性评估**：节点移除模拟验证靶点重要性

### 5.3 基因调控网络模拟
- **SCENIC因果推断**：验证转录因子-靶点调控关系
- **NicheNet通讯模拟**：预测配体-受体信号传导
- **CellOracle扰动预测**：模拟基因过表达/敲除效应

### 5.4 虚拟验证报告要求
- **预测置信度**：每个模拟结果必须给出置信度评分
- **与实验数据对比**：如存在公开数据，必须进行对比验证
- **假阳性控制**：明确指出模拟结果的局限性

## 6. Python/R实现代码
- Data QC代码（批次检测、ComBat校正）
- MICE插补代码
- 核心分析代码
- **虚拟验证代码**（AlphaFold/COBRApy调用示例）
- 注释关键参数和依赖库版本

---

# 输出要求

1. **SOTA标准**: 所有方法选择必须追踪领域最前沿
2. **QC优先**: Data QC & Harmonization Protocol必须是独立的、详细的子模块
3. **具体可行**: 提供可直接运行的代码框架
4. **版本明确**: 指定关键库的版本号
5. **不要占位符**: 不要使用"XX"或"待定"
6. **Markdown格式**: 输出完整的Markdown文档
7. **虚拟验证强制**: 必须包含In silico验证方案，否则视为不合格

**警告**: 没有通过QC协议的数据，不能进入后续分析环节。
**警告**: 缺少虚拟验证方案的Pipeline将被驳回。

现在请生成完整的计算生物学Pipeline方案："""

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
                    print(f"[计算生物学专家] API 重试 {api_attempt + 1}/{max_api_retries}")

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

                print(f"[计算生物学专家] LLM响应成功，长度: {len(response_text)} 字符")
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
                    print(f"[计算生物学专家] API错误，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Claude API错误: {e}")

            except Exception as e:
                raise Exception(f"LLM调用失败: {e}")

        raise Exception("API调用重试次数耗尽")

    def _extract_pipeline_design(self, proposal: str) -> Dict:
        """从方案中提取结构化Pipeline设计"""
        import re

        pipeline = {
            'data_types': [],
            'analysis_modules': [],
            'integration_methods': [],
            'computational_requirements': {
                'cpu': 'unknown',
                'memory': 'unknown',
                'gpu': 'unknown'
            }
        }

        # 提取数据类型
        data_patterns = {
            'scRNA-seq': r'(?:scRNA|single.?cell|单细胞)',
            'bulk RNA-seq': r'(?:bulk RNA|转录组)',
            'ATAC-seq': r'ATAC',
            '蛋白质组': r'(?:蛋白质组|proteomics?|mass.?spec)',
            '代谢组': r'(?:代谢组|metabolomics?)',
            '基因组': r'(?:全基因组|WGS|WES|genomics?|variant)'
        }

        for data_type, pattern in data_patterns.items():
            if re.search(pattern, proposal, re.IGNORECASE):
                pipeline['data_types'].append(data_type)

        # 提取分析方法
        method_patterns = {
            'UMAP': r'UMAP',
            'tSNE': r'tSNE',
            'MAGIC': r'MAGIC',
            'scVI': r'scVI',
            'Harmony': r'Harmony',
            'MOFA+': r'MOFA',
            'AlphaFold': r'AlphaFold',
            'SCENIC': r'SCENIC',
            'GSEA': r'GSEA'
        }

        for method, pattern in method_patterns.items():
            if re.search(pattern, proposal, re.IGNORECASE):
                pipeline['analysis_modules'].append(method)

        # 提取计算资源
        if re.search(r'GPU|cuda', proposal, re.IGNORECASE):
            pipeline['computational_requirements']['gpu'] = 'required'

        memory_match = re.search(r'(\d+)\s*GB', proposal, re.IGNORECASE)
        if memory_match:
            pipeline['computational_requirements']['memory'] = f"{memory_match.group(1)}GB"

        return pipeline

    def _extract_qc_protocol(self, proposal: str) -> Dict:
        """从方案中提取QC协议"""
        import re

        protocol = {
            'batch_correction': {
                'required': False,
                'method': 'unknown',
                'verification': 'unknown'
            },
            'missing_data': {
                'imputation_method': 'unknown',
                'assumption': 'unknown'
            },
            'multi_center': {
                'harmonization': False,
                'method': 'unknown'
            },
            'qc_thresholds': {
                'sample_level': [],
                'feature_level': []
            }
        }

        # 检测批次校正
        if re.search(r'ComBat|batch.*correct|批次.*校正', proposal, re.IGNORECASE):
            protocol['batch_correction']['required'] = True
            if re.search(r'ComBat[_-]?seq', proposal, re.IGNORECASE):
                protocol['batch_correction']['method'] = 'ComBat_seq'
            elif re.search(r'ComBat', proposal, re.IGNORECASE):
                protocol['batch_correction']['method'] = 'ComBat'
            elif re.search(r'Harmony', proposal, re.IGNORECASE):
                protocol['batch_correction']['method'] = 'Harmony'
            elif re.search(r'MNN', proposal, re.IGNORECASE):
                protocol['batch_correction']['method'] = 'MNN'
            elif re.search(r'scVI', proposal, re.IGNORECASE):
                protocol['batch_correction']['method'] = 'scVI'

        # 检测验证方法
        if re.search(r'PCA.*visual|UMAP.*batch|KB.*test|PERMANOVA', proposal, re.IGNORECASE):
            protocol['batch_correction']['verification'] = 'visual_statistical'

        # 检测插补方法
        imputation_patterns = {
            'MICE': r'MICE|Multiple.*Imputation.*Chained',
            'MissForest': r'MissForest',
            'KNN': r'KNN.*Imput',
            'GAIN': r'GAIN|DeepLearning.*Imput',
            'scImpute': r'scImpute'
        }

        for method, pattern in imputation_patterns.items():
            if re.search(pattern, proposal, re.IGNORECASE):
                protocol['missing_data']['imputation_method'] = method
                break

        # 检测缺失假设
        if re.search(r'MAR|Missing.?At.?Random', proposal, re.IGNORECASE):
            protocol['missing_data']['assumption'] = 'MAR'
        elif re.search(r'MCAR|Missing.?Completely', proposal, re.IGNORECASE):
            protocol['missing_data']['assumption'] = 'MCAR'
        elif re.search(r'MNAR|Missing.?Not.?Random', proposal, re.IGNORECASE):
            protocol['missing_data']['assumption'] = 'MNAR'

        # 检测多中心调和
        if re.search(r'多中心|multi.?center|跨中心', proposal, re.IGNORECASE):
            protocol['multi_center']['harmonization'] = True
            if re.search(r'ComBat', proposal, re.IGNORECASE):
                protocol['multi_center']['method'] = 'ComBat'
            elif re.search(r'CVAE', proposal, re.IGNORECASE):
                protocol['multi_center']['method'] = 'CVAE'
            elif re.search(r'Domain.?Adapt', proposal, re.IGNORECASE):
                protocol['multi_center']['method'] = 'Domain_Adaptation'

        # 提取QC阈值
        sample_patterns = {
            'mitochondrial': r'(?:线粒体|mitochondrial|MT.?%).*?(\d+)',
            'gene_count': r'(?:基因数|gene.?count|detected.?gene).*?(\d+)',
            'umi_count': r'(?:UMI|read.?count).*?(\d+)'
        }

        for qc_type, pattern in sample_patterns.items():
            match = re.search(pattern, proposal, re.IGNORECASE)
            if match:
                protocol['qc_thresholds']['sample_level'].append(f"{qc_type}: < {match.group(1)}")

        feature_patterns = {
            'low_expression': r'(?:低表达|low.?express).*?(\d+)',
            'highly_variable': r'(?:高变|highly.?variable|HVG).*?(\d+)'
        }

        for qc_type, pattern in feature_patterns.items():
            match = re.search(pattern, proposal, re.IGNORECASE)
            if match:
                protocol['qc_thresholds']['feature_level'].append(f"{qc_type}: {match.group(1)}")

        return protocol


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    # 测试计算生物学专家
    test_hypothesis = {
        'title': '单细胞多组学整合的癌症耐药机制研究',
        'description': '整合scRNA-seq和空间转录组数据，识别癌症耐药的关键细胞亚群和分子靶点',
        'paradigm_framework': '单细胞多组学 + 机器学习',
        'grand_challenge': '癌症耐药性的细胞异质性',
        'technical_route': '计算生物学驱动的多组学整合分析'
    }

    agent = CompBioAgent()
    result = agent.execute({
        'hypothesis_data': test_hypothesis,
        'genai_proposal': '使用Transformer架构整合多模态组学数据',
        'output_dir': 'reports'
    })

    if result['success']:
        print("=" * 60)
        print("计算生物学Pipeline设计完成")
        print("=" * 60)
        print(f"报告路径: {result['report_path']}")
        print(f"涉及数据类型: {result['pipeline_design']['data_types']}")
        print(f"分析方法: {result['pipeline_design']['analysis_modules']}")
