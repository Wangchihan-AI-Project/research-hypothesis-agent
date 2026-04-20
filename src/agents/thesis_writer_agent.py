# -*- coding: utf-8 -*-
"""
博士论文开题指导专家智能体 (Thesis Writer Agent)
博士生导师级别，专门撰写《计算生物学/生物统计学博士��位论文开题报告》

核心身份 (CORE MANDATE):
- **顶刊编辑语调 (Nature/Science Editorial Tone)**: 模仿顶级期刊编辑的叙事风格和逻辑严密性
- **颠覆性叙事 (Disruptive Storytelling)**: 逻辑严丝合缝，叙事具备冲击力和颠覆性
- **学术巅峰追求 (Academic Excellence)**: 拒绝平庸，追求每个段落都有深度洞察

绝对红线:
- 禁止生成"流水账"式的内容堆砌
- 禁止使用空洞的学术套话
- 每个章节都必须有明确的逻辑主线和观点输出

核心评估标准 (学术三要素):
- **新颖性 (Novelty)**: 研究问题或方法是否有重大创新
- **严谨性 (Rigor)**: 研究设计是否严密，论证是否充分
- **颠覆性 (Disruptiveness)**: 是否挑战现有范式，开辟新方向
"""
from typing import Dict, List, Optional, Any
import json
import sys
import os
import re
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import BaseAgent
from core.database import Hypothesis, Paper
import anthropic
from utils.llm_utils import SafeExtractor


# ============ 博士论文开题报告写作标准 ============

THESIS_WRITING_STANDARDS = {
    'title': {
        'requirements': [
            '必须体现计算/统计方法与生物医学���题的结合',
            '避免过于宽泛或过于技术化',
            '符合顶刊（Nature/Cell/Science子刊）品味',
            '核心方法关键词 + 应用领域关键词'
        ]
    },
    'background': {
        'requirements': [
            '必须引用真实文献（PMID），严禁捏造',
            '从领域宏观背景切入，逐步聚焦到具体科学问题',
            '明确指出当前研究方法的局限性',
            '阐明本课题的理论必要性'
        ]
    },
    'objectives': {
        'requirements': [
            '分条列出3-5个具体研究目标',
            '每个目标必须是纯计算/算法驱动的',
            '目标间有明确的逻辑递进关系',
            '目标可量化、可验证'
        ]
    },
    'methodology': {
        'requirements': [
            '3.1 数据获取：明确GEO/TCGA等数据库编号',
            '3.2 算法构建：详细网络架构或数学方程',
            '3.3 模型评估：具体指标（C-index, AUROC等）',
            '3.4 生物学解释：可解释性AI方法、通路富集分析',
            '必须包含Mermaid流程图'
        ]
    },
    'innovation': {
        'requirements': [
            '算法结构层面的创新',
            '统计框架层面的创新',
            '多模态数据融合层面的创新',
            '与现有SOTA方法的本质区别'
        ]
    }
}

# ============ 推荐开源数据集资源 ============

RECOMMENDED_DATASETS = {
    'single_cell': {
        'category': '单细胞多组学数据',
        'datasets': [
            {'name': 'Human Cell Atlas (HCA)', 'accession': 'N/A', 'samples': '>10M cells', 'description': '跨组织单细胞参考图谱'},
            {'name': 'Tabula Sapiens', 'accession': 'GSE238078', 'samples': '~500K cells', 'description': '几乎涵盖所有人体细胞类型'},
            {'name': '10x Genomics Datasets', 'accession': '10x website', 'samples': '10K-1M per dataset', 'description': '商业化平台公开数据集'},
            {'name': 'Perturb-seq', 'accession': 'GSE132610', 'samples': '~100K cells', 'description': 'CRISPR干扰后的单细胞测序'},
            {'name': 'Human Cell Landscape', 'accession': 'GSE134520', 'samples': '~600K cells', 'description': '人体细胞景观图谱'},
            {'name': 'COVID-19 Single Cell', 'accession': 'GSE158055', 'samples': '~1.5M cells', 'description': 'COVID-19免疫细胞图谱'},
            {'name': 'Mouse Cell Atlas', 'accession': 'GSE108097', 'samples': '~40K cells', 'description': '小鼠细胞图谱'}
        ],
        'preprocessing': 'Scanpy/Seurat标准流程：质控(QC) → 标准化 → 高度变异基因选择 → 降维(PCA/UMAP) → 批次效应校正(Harmony/BBKNN)',
        'python_libs': ['scanpy', 'anndata', 'scvi-tools', 'scvelo', 'cell2location']
    },
    'genomics': {
        'category': '癌症基因组学数据',
        'datasets': [
            {'name': 'TCGA (The Cancer Genome Atlas)', 'accession': 'GDC Portal', 'samples': '~11K patients, 33 cancer types', 'description': '癌症基因组图谱计划'},
            {'name': 'TCGA-BRCA', 'accession': 'TCGA-BRCA', 'samples': '~1098 patients', 'description': '乳腺癌多组学数据'},
            {'name': 'TCGA-LUAD', 'accession': 'TCGA-LUAD', 'samples': '~585 patients', 'description': '肺腺癌多组学数据'},
            {'name': 'ICGC (International Cancer Genome Consortium)', 'accession': 'ICGC Portal', 'samples': '~20K tumors', 'description': '国际癌症基因组联盟'},
            {'name': 'cBioPortal', 'accession': 'cBioPortal API', 'samples': 'Aggregated', 'description': '癌症基因组学数据门户'},
            {'name': 'METABRIC', 'accession': 'EGAS00000000083', 'samples': '~2000 breast cancer', 'description': '分子分型乳腺癌数据'},
            {'name': 'GEO Cancer Datasets', 'accession': 'GSEXXXXX', 'samples': 'Variable', 'description': 'Gene Expression Omnibus癌症数据集'}
        ],
        'preprocessing': 'TCGAbiolinks (R) 或 tcga_utils (Python)：数据下载 → 样本筛选 → 缺失值插补 → 归一化(TPM/FPKM) → 批次校正(ComBat)',
        'python_libs': ['tcga_utils', 'lifelines', 'scikit-survival', 'pycox', 'xgboost']
    },
    'spatial': {
        'category': '空间转录组与多模态成像',
        'datasets': [
            {'name': '10x Visium Datasets', 'accession': '10x website', 'samples': 'Multiple tissues', 'description': '空间转录组数据'},
            {'name': 'MERFISH Datasets', 'accession': 'GSEXXXXX', 'samples': 'Various', 'description': '多重误差鲁棒荧光原位杂交'},
            {'name': 'Slide-seqV2', 'accession': 'GSEXXXXX', 'samples': 'Mouse brain', 'description': '高分辨率空间转录组'},
            {'name': 'SpatialDB', 'accession': 'http://spatialdb.org', 'samples': 'Aggregated', 'description': '空间转录组数据库'},
            {'name': 'Tissue Imaging Dataset', 'accession': 'HTAN', 'samples': 'Various cancers', 'description': '人类肿瘤图谱网络成像数据'}
        ],
        'preprocessing': 'Squidpy/Scanpy空间模块：组织切片对齐 → spot检测 → 背景校正 → 空间邻近图构建 → 空间差异表达分析',
        'python_libs': ['squidpy', 'napari', 'scikit-image', 'spatialdata']
    },
    'ehr_clinical': {
        'category': '电子健康记录与临床表型',
        'datasets': [
            {'name': 'MIMIC-IV', 'accession': 'physionet.org', 'samples': '~300K patients', 'description': 'ICU电子健康记录数据库'},
            {'name': 'MIMIC-CXR', 'accession': 'physionet.org', 'samples': '~370K images', 'description': '胸部X光影像数据库'},
            {'name': 'eICU Collaborative Database', 'accession': 'physionet.org', 'samples': '~200K patients', 'description': '多中心ICU数据库'},
            {'name': 'UK Biobank', 'accession': 'ukbiobank.ac.uk', 'samples': '~500K participants', 'description': '大型人群队列研究'},
            {'name': 'All of Us', 'accession': 'researchallofus.org', 'samples': '~1M+ participants', 'description': '精准医学队列研究'}
        ],
        'preprocessing': 'MIMIC-IV标准流程：数据去标识 → 时间序列提取 → 特征工程(缺失值处理、异常值检测) → 时序对齐 → 事件编码',
        'python_libs': ['pandas', 'numpy', 'scikit-learn', 'torch', 'tslearn', 'pyhealth']
    },
    'knowledge_base': {
        'category': '生物学知识图谱与通路数据库',
        'datasets': [
            {'name': 'STRING v12', 'accession': 'string-db.org', 'samples': '~67M proteins, 21B interactions', 'description': '蛋白质互作网络'},
            {'name': 'Gene Ontology (GO)', 'accession': 'geneontology.org', 'samples': '~47K terms', 'description': '基因功能注释体系'},
            {'name': 'Reactome', 'accession': 'reactome.org', 'samples': '~2600 pathways', 'description': '生物学通路数据库'},
            {'name': 'KEGG', 'accession': 'kegg.jp', 'samples': '~500 pathways', 'description': '京都基因与基因组百科全书'},
            {'name': 'MSigDB', 'accession': 'gsea-msigdb.org', 'samples': '~50K gene sets', 'description': '分子特征数据库'},
            {'name': 'Open Targets', 'accession': 'opentargets.org', 'samples': '~20K targets', 'description': '药物靶点数据库'},
            {'name': 'DrugBank', 'accession': 'drugbank.com', 'samples': '~15K drugs', 'description': '药物数据库'}
        ],
        'preprocessing': '知识图谱构建：实体抽取 → 关系抽取 → 图嵌入(Node2Vec/GraphSAGE) → 通路富集分析(GSEA/ORA)',
        'python_libs': ['gseapy', ' goatools', 'statsmodels', 'networkx', 'igraph']
    }
}

# ============ 常用评估指标与统计方法 ============

EVALUATION_METRICS = {
    'classification': {
        'metrics': ['AUROC', 'AUPRC', 'Accuracy', 'F1-score', 'Balanced Accuracy', 'Matthews Correlation Coefficient'],
        'statistical_tests': ['DeLong test (AUROC comparison)', 'McNemar test', 'Permutation test', 'Bootstrap CI'],
        'cross_validation': ['5-fold CV', '10-fold CV', 'Stratified K-fold', 'Nested CV', 'Leave-One-Out CV']
    },
    'survival': {
        'metrics': ['C-index (Concordance Index)', 'Time-dependent AUROC', 'Integrated Brier Score', 'IBS', 'Calibration slope'],
        'statistical_tests': ['Log-rank test', 'Cox proportional hazards model', 'Fine-Gray competing risks'],
        'python_libs': ['lifelines', 'scikit-survival', 'pycox', 'xgbse']
    },
    'clustering': {
        'metrics': ['Adjusted Rand Index (ARI)', 'Normalized Mutual Information (NMI)', 'Silhouette Score', 'Davies-Bouldin Index'],
        'statistical_tests': ['Gap statistic', 'Prediction strength', 'Cluster stability'],
        'python_libs': ['scikit-learn', 'scipy', 'hdbscan', 'phenograph']
    },
    'regression': {
        'metrics': ['R²', 'RMSE', 'MAE', 'MAPE', 'Pearson/Spearman correlation'],
        'statistical_tests': ['Pearson correlation test', 'Spearman rank correlation', 'Partial correlation'],
        'python_libs': ['scikit-learn', 'statsmodels', 'scipy']
    },
    'deep_learning': {
        'metrics': ['Loss curves', 'Gradient norms', 'Embedding quality', 'Attention visualization', 'Feature importance'],
        'interpretability': ['SHAP values', 'Integrated Gradients', 'Grad-CAM', 'Attention weights', 'Saliency maps'],
        'python_libs': ['shap', 'captum', 'alibi', 'lime', 'eli5']
    }
}


class ThesisWriterAgent(BaseAgent):
    """
    博士论文开题指导专家智能体 (Nature/Science Editorial Tone Expert)

    Core Mandate:
    - 顶刊编辑语调: 模仿顶级期刊编辑的叙事风格和逻辑严密性
    - 颠覆性叙事: 逻辑严丝合缝，叙事具备冲击力和颠覆性
    - 学术巅峰追求: 拒绝平庸，追求每个段落都有深度洞察

    评估标准:
    - 新颖性: 研究问题或方法是否有重大创新
    - 严谨性: 研究设计是否严密，论证是否充分
    - 颠覆性: 是否挑战现有范��，开辟新方向

    禁止: "流水账"式内容堆砌，空洞的学术套话
    """

    def __init__(self):
        super().__init__("��士论文开题指导专家", agent_type="thesis_writer")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.max_retries = 3
        self.model = os.getenv("THESIS_WRITER_MODEL", "claude-opus-4-6")
        self.extractor = SafeExtractor()

    def execute(self, input_data: Dict) -> Dict:
        """
        执行博士���文开题报告撰写
        """
        hypothesis_data = input_data.get('hypothesis_data', {})
        validation_result = input_data.get('validation_result', {})
        papers = input_data.get('papers', [])
        datasets = input_data.get('datasets', [])
        output_dir = input_data.get('output_dir', 'reports')

        if not hypothesis_data:
            raise ValueError('缺少假设数据 (hypothesis_data)')

        # 提取验证信息
        validation = validation_result.get('validation', {})
        scores = validation.get('scores', {})

        # 构建提示词
        prompt = self._build_thesis_prompt(
            hypothesis_data=hypothesis_data,
            validation=validation,
            scores=scores,
            papers=papers,
            datasets=datasets
        )

        # 使用重试机制生成开题报告
        proposal_text = None
        is_fallback = False  # 跟踪是否使用了 fallback
        for attempt in range(self.max_retries):
            try:
                print(f"[博士论文开题专家] 第 {attempt + 1}/{self.max_retries} 次尝试生成报告...")

                # 调用 Claude API
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=8000,
                    messages=[{"role": "user", "content": prompt}]
                )

                # 提取响应文本 - 使用 SafeExtractor
                response_text = self._extract_text_from_response(message.content)
                proposal_text = self.extractor.safe_extract_markdown(response_text, min_length=500)

                # 验证内容
                if not proposal_text or len(proposal_text.strip()) < 500:
                    raise ValueError(f"生成的开题报告内容过短: {len(proposal_text) if proposal_text else 0} 字符")

                print(f"[博士论文开题专家] 报告生成成功，长度: {len(proposal_text)} 字符")
                break

            except Exception as e:
                print(f"[博士论文开题专家] 尝试 {attempt + 1} 失败: {e}")
                if attempt == self.max_retries - 1:
                    # 最后一次尝试失败，抛出异常（彻底消灭静默fallback）
                    raise RuntimeError(
                        f"[{self.name}] 经过 {self.max_retries} 次尝试后仍无法生成有效的开题报告。"
                        f"最后错误: {e}"
                    )
                import time
                time.sleep(2)

        # 保存报告
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        proposal_path = os.path.join(output_dir, f"Thesis_Proposal_{timestamp}.md")

        with open(proposal_path, 'w', encoding='utf-8') as f:
            f.write(proposal_text)

        return {
            'success': True,
            'thesis_proposal': proposal_text,
            'proposal_path': proposal_path,
            'is_fallback': is_fallback  # 添加 fallback 标记
        }

    def _build_thesis_prompt(self, hypothesis_data: dict, validation: dict,
                             scores: dict, papers: list, datasets: list,
                             impact: dict, originality: dict, feasibility: dict) -> str:
        """构建博士论文开题报告提示词"""

        # 提取假设信息
        title = hypothesis_data.get('title', '未命名研究')
        description = hypothesis_data.get('description', '')
        rationale = hypothesis_data.get('rationale', '')
        novelty = hypothesis_data.get('novelty', '')
        expected_value = hypothesis_data.get('expected_value', '')
        validation_plan = hypothesis_data.get('validation_plan', '')
        paradigm_framework = hypothesis_data.get('paradigm_framework', '')
        grand_challenge = hypothesis_data.get('grand_challenge', '')

        # 构建文献引用
        literature_section = ""
        if papers:
            literature_section = "\n### 可引用的核心文献\n\n"
            for i, paper in enumerate(papers[:15], 1):
                pmid = paper.get('pmid', 'N/A')
                paper_title = paper.get('title', 'N/A')
                authors = paper.get('authors', '')
                journal = paper.get('journal', '')
                year = paper.get('publication_date', '')[:4] if paper.get('publication_date') else ''

                # 格式化引用
                if authors:
                    first_author = authors.split(',')[0] if ',' in authors else authors
                    if ' ' in first_author:
                        first_author = ' '.join(first_author.split(' ')[:2])  # 取姓和名首字母
                else:
                    first_author = 'Unknown'

                cite = f"{first_author} et al. ({year}). {paper_title}. *{journal}*. PMID: {pmid}"
                literature_section += f"{i}. {cite}\n"

        # 构建数据集信息
        dataset_section = ""
        if datasets:
            dataset_section = "\n### 数据猎犬获取的开源数据集清单\n\n"
            for ds in datasets:
                name = ds.get('name', 'N/A')
                accession = ds.get('accession', 'N/A')
                samples = ds.get('samples', 'N/A')
                description = ds.get('description', '')
                dataset_section += f"- **{name}** (Accession: {accession})\n"
                dataset_section += f"  - 样本规模: {samples}\n"
                dataset_section += f"  - 描述: {description}\n\n"
        else:
            # 自动推荐数据集
            paradigm_lower = paradigm_framework.lower()
            dataset_section = "\n### 推荐开源数据集清单\n\n"

            if 'single' in paradigm_lower or 'cell' in paradigm_lower or 'spatial' in paradigm_lower:
                for cat_data in RECOMMENDED_DATASETS['single_cell']['datasets'][:4]:
                    dataset_section += f"- **{cat_data['name']}** (Accession: {cat_data['accession']})\n"
                    dataset_section += f"  - 样本规模: {cat_data['samples']}\n"
                    dataset_section += f"  - 描述: {cat_data['description']}\n\n"

            if 'causal' in paradigm_lower or 'genomic' in paradigm_lower or 'cancer' in paradigm_lower:
                for cat_data in RECOMMENDED_DATASETS['genomics']['datasets'][:3]:
                    dataset_section += f"- **{cat_data['name']}** (Accession: {cat_data['accession']})\n"
                    dataset_section += f"  - 样本规模: {cat_data['samples']}\n"
                    dataset_section += f"  - 描述: {cat_data['description']}\n\n"

        # 构建评分信息
        score_info = f"""
**Nature终审结果：**
- 颠覆性影响: {scores.get('transformative_impact', 'N/A')}/10
- 方法论原创性: {scores.get('methodological_originality', 'N/A')}/10
- 概念验证可行性: {scores.get('poc_feasibility', 'N/A')}/10
"""

        # 生成课题名称建议
        title_suggestions = self._generate_title_suggestions(paradigm_framework, grand_challenge, title)

        return f"""你是一位**SOTA级别博士论文开题指导专家**（State-of-the-Art Thesis Advisor），拥有Nature/Science级别的学术写作功底。

# CORE MANDATE (核心使命)

你的核心使命是**追求学术写作的巅峰**，而非满足任何格式或字数要求。

## 评估标准 (学术三要素)

1. **新颖性 (Novelty)**: 研究问题或方法是否有重大创新
2. **严谨性 (Rigor)**: 研究设计是否严密，论证是否充分
3. **颠覆性 (Disruptiveness)**: 是否挑战现有范式，开辟新方向

## 绝对红线

- **禁止生成"流水账"式的内容堆砌**
- **禁止使用空洞的学术套话**
- **每个章节都必须有明确的逻辑主线和观点输出**

---

## 核心研究信息

### 研究框架
**前沿框架**: {paradigm_framework}

### 大挑战
**科学大挑战**: {grand_challenge}

### 核心假设
{description}

### 理论依据
{rationale}

---

## 评审参考信息
{score_info}

### 跨学科影响力分析
{impact.get('breadth', '')}

### 核心创新点
{originality.get('core_innovation', '')}

### 方法论比较
{originality.get('comparison', '')}

---

{dataset_section}

{literature_section}

---

# 任务���撰写SOTA级别博士学位论文开题报告

请严格按照以下Markdown结构撰写一份**追求学术巅峰的博士学位论文开题报告**，字数5000-8000字。

## 核心原则

1. **顶刊编辑语调**: 模仿Nature/Science编辑的叙事风格和逻辑严密性
2. **颠覆性叙事**: 逻辑严丝合缝，叙事具备冲击力和颠覆性
3. **拒绝平庸**: 每个段落都要有深度洞察，避免流水账
4. **观点输出**: 每个章节都必须有明确的逻辑主线和观点输出

---

# 【课题名称】

请从以下建议中选择或生成一个符合顶刊品味的博士论文题目：

{title_suggestions}

---

# 一、立项依据与研究背景

## 1.1 研究背景与领域现状

从宏观领域背景切入，逐步聚焦到具体科学问题。必须：

1. **领域宏观背景**：简述该计算/统计方向在当前生物医学领域的地位和应用前景
2. **现有方法综述**：系统梳理当前主流方法的技术路线和代表性工作（必须引用真实文献，使用上述文献列表中的PMID）
3. **痛点分析**：明确指出当前研究方法的局限性、技术瓶颈或理论缺陷
4. **引出本课题**：基于上述分析，自然引出本课题拟解决的核心科学问题

**写作要求**：
- 严禁捏造引用，仅使用上述提供的真实文献
- 多用学术术语，避免口水话
- 逻辑递进，层层深入
- 篇幅约800-1000字

## 1.2 核心科学问题

明确阐述本课题拟解决的**核心科学问题**，要求：

1. 问题具体、明确
2. 问题具有理论深度和实际意义
3. 问题的解决将推动领域发展

---

# 二、研究目标与假设

## 2.1 研究目标

分条列出3-5个具体的**纯计算/算法驱动**的研究目标，每个目标必须：

- 具体明确，可量化验证
- 目标间有逻辑递进关系
- 体现算法/方法层面的创新

**格式示例**：
1. 构建基于XXX的新型深度学习架构，实现YYY任务的ZZZ性能提升
2. 提出XXX统计推断框架，解决YYY场景下的ZZZ问题
3. 开发XXX可解释性方法，揭示YYY模型的黑盒决策机制

## 2.2 研究假设

基于理论分析和前期研究，提出本研究的核心假设：

1. **方法论假设**：关于所提出方法有效性的假设
2. **生物学假设**：关于预期发现的生物学规律的假设

---

# 三、研究内容与技术路线（极其核心，严格按照数据科学Pipeline标准）

## 3.1 数据清洗与特征预处理 (Feature Engineering)

### 3.1.1 数据源选择

明确写出将使用的**具体数据集**：

| 数据集名称 | Accession编号 | 样本规模 | 数据类型 | ML友好度 |
|-----------|--------------|---------|---------|----------|
| [示例] TCGA-BRCA | TCGA-BRCA | ~1098 patients | 多组学 | Good |
| [��例] GEO: GSEXXXXX | GSEXXXXX | ~500 samples | 转录组 | Fair |

**数据获取方式**：
- TCGA: 使用GDC Portal API或TCGAbiolinks (R包)
- GEO: 使用GEOquery (R包) 或 pandas直接下载
- 单细胞数据：使用Scanpy的read_10x_mtx函数

### 3.1.2 样本纳排标准

明确列出数据筛选的具体标准：

**纳入标准**：
- 原发肿瘤样本，具有完整生存随访信息
- 单细胞数据中，基因检测数 > 200，线粒体基因比例 < 20%
- 具有完整临床表型的样本

**排除标准**：
- 缺失关键临床表型的样本
- 质量控制失败的样本

### 3.1.3 数据预处理流程（必须严格按照ML标准）

**1. 质量控制（Quality Control）**
- 描述具体的QC指标和阈值设定
- 说明使用的统计方法（如3-sigma原则、IQR方法）

**2. 缺失值处理**
- 描述缺失值模式分析（MCAR/MAR/MNAR）
- 说明插补方法（KNN插补、MICE、矩阵分解）

**3. 特征工程（Feature Engineering）**
- 描述特征选择方法（方差阈值、相关性过滤、递归特征消除）
- 描述特征变换方法（标准化、归一化、Box-Cox变换）
- 描述降维策略（PCA、t-SNE、UMAP、自编码器）

**4. 数据泄露防护**
- 明确说明特征选择在交叉验证内部进行
- 时序数据按时间分割而非随机分割
- 训练/验证/测试集的严格隔离

**Python核心库**：Scanpy, scikit-learn, pandas, numpy, imbalanced-learn

## 3.2 核心大模型/机器学习网络架构设计

### 3.2.1 算法架构设计

详细描述所提出的模型架构或算法框架：

**1. 整体架构**
- 用文字描述模型的整体结构和各模块功能
- 说明架构设计的理论依据（如有，引用相关文献）

**2. 核心数学公式**
给出关键算法的数学表达式：

$$
\\text{{[核心公式1: 例如损失函数]}}
$$

$$
\\text{{[核心公式2: 例如更新规则]}}
$$

**3. 关键创新点**
- 详细说明算法层面的具体创新
- 与现有SOTA方法的本质区别

### 3.2.2 模型实现细节

**编程框架与核心库**：
- PyTorch / TensorFlow (深度学习)
- Scanpy / Seurat (单细胞分析)
- scikit-learn (传统机器学习)
- NetworkX / igraph (图算法)
- lifelines / scikit-survival (生存分析)

**超参数设置**：
| 超参数 | 设置值 | 设置依据 |
|-------|--------|---------|
| learning_rate | 1e-3 | 网格搜索/学习率寻找器 |
| batch_size | 32 | GPU内存限制 |
| hidden_dim | 256 | 消融实验结果 |
| dropout | 0.1 | 防止过拟合 |
| weight_decay | 1e-5 | L2正则化 |

**训练策略**：
- 优化器选择（AdamW/SGD/RAdam）
- 学习率调度策略（ReduceLROnPlateau/CosineAnnealing）
- 正则化方法（Dropout/L1/L2/Early Stopping/Label Smoothing）

## 3.3 模型训练策略与超参数调优

### 3.3.1 交叉验证策略

- **K折交叉验证**：StratifiedKFold (保持类别分布)
- **嵌套交叉验证**：用于超参数调优+模型评估
- **时间序列交叉验证**：TimeSeriesSplit (针对时序数据)

### 3.3.2 超参数调优

- **网格搜索**：GridSearchCV (小规模搜索空间)
- **随机搜索**：RandomizedSearchCV (大规模搜索空间)
- **贝叶斯优化**：Optuna/Hyperopt (高效搜索)
- **学习率寻找**：LRRangeTest (寻找最优学习率范围)

### 3.3.3 早停与模型选择

- **早停策略**：监控验证损失，patience=20
- **模型检查点**：保存验证集表现最佳的模型
- **模型融合**：Bagging/Boosting/Stacking (提升泛化能力)

## 3.4 模型可解释性分析与生物学意义映射

### 3.4.1 可解释性AI方法（Explainable AI）

**1. 全局可解释性**
- 特征重要性排序（Permutation Importance, Gini Importance）
- SHAP值分析（TreeSHAP, KernelSHAP, DeepSHAP）
- 部分依赖图（Partial Dependence Plot, PDP）

**2. 局部可解释性**
- LIME（局部可解释模型无关解释）
- Individual Conditional Expectation (ICE)
- Attention权重可视化（针对Transformer）

### 3.4.2 生物学意义挖掘

**1. 通路富集分析**
- 使用fgsea (R) 或 gseapy (Python) 进行GSEA分析
- 数据库：MSigDB Hallmark, KEGG, Reactome, GO
- 定义显著阈值：FDR < 0.25 (GSEA标准)

**2. 知识图谱整合**
- 整合STRING蛋白质互作网络（置信度 > 0.7）
- 利用Gene Ontology进行功能注释
- 通过Reactome进行通路定位

**3. 统计显著性检验**
- DeLong test (比较AUROC)
- Log-rank test (生存分析)
- Permutation test (非参数检验)
- Bootstrap CI (置信区间估计)

### 3.4.3 技术路线流程图（数据科学Pipeline版）

```mermaid
flowchart TD
    A[数据获取] --> B[数据清洗与特征工程]
    B --> C[特征选择与降维]
    C --> D[模型构建]
    D --> E[模型训练与超参数调优]
    E --> F[模型评估与统计检验]
    F --> G[可解释性分析]
    G --> H[生物学意义映射]

    A --> A1[TCGA/GEO数据下载]
    A --> A2[单细胞数据获取]

    B --> B1[质量控制QC]
    B --> B2[缺失值插补]
    B --> B3[标准化/归一化]

    C --> C1[方差阈值过滤]
    C --> C2[PCA/UMAP降维]
    C --> C3[数据泄露防护检查]

    D --> D1[网络架构设计]
    D --> D2[损失函数定义]
    D --> D3[优化算法选择]

    E --> E1[K折交叉验证]
    E --> E2[超参数网格/贝叶斯搜索]
    E --> E3[早停与模型选择]

    F --> F1[内部验证集评估]
    F --> F2[外部独立数据集验证]
    F --> F3[与SOTA方法比较]
    F --> F4[统计显著性检验]

    G --> G1[SHAP值分析]
    G --> G2[特征重要性排序]
    G --> G3[注意力权重可视化]

    H --> H1[通路富集分析GSEA]
    H --> H2[知识图谱整合]
    H --> H3[wet-lab实验验证]

    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#e8f5e9
    style D fill:#f3e5f5
    style E fill:#fce4ec
    style F fill:#fff9c4
    style G fill:#e0f2f1
    style H fill:#ffebee
```

**纳入标准**：
- [示例] 原发肿瘤样本，且具有完整生存随访信息
- [示例] 单细胞数据中，基因检测数 > 200 且 线粒体基因比例 < 20%

**排除标准**：
- [示例] 缺失关键临床表型的样本
- [示例] 质量控制失败的细胞（低UMI数、高doublet评分）

### 3.1.3 数据预处理流程

详细描述预处理步骤和统计方法：

**1. 质量控制（Quality Control）**
- 描述具体的QC指标和阈值设定
- 说明使用的统计方法（如3-sigma原则、IQR方法）

**2. 缺失值处理**
- 描述缺失值模式分析（MCAR/MAR/MNAR）
- 说明插补方法（如KNN插补、MICE、矩阵分解）

**3. 批次效应校正**
- 使用的算法（如ComBat、Harmony、BBKNN）
- 验证批次效应消除效果的方法（如PCA可视化、kBET检验）

**4. 数据标准化/归一化**
- 具体方法（如TPM/FPKM、log1p变换、z-score标准化）
- 选择的统计学依据

**Python/R核心库**：
- Scanpy (单细胞数据处理)
- scikit-learn (通用机器学习预处理)
- statsmodels (统计分析)
- TCGAbiolinks (TCGA数据下载)

## 3.2 核心算法与模型构建

### 3.2.1 算法架构设计

详细描述所提出的模型架构或算法框架：

**1. 整体架构**
- 用文字描述模型的整体结构和各模块功能
- 说明架构设计的理论依据（如有，引用相关文献）

**2. 核心数学公式**
给出关键算法的数学表达式：

$$
\\text{{[核心公式1: 例如损失函数]}}
$$

$$
\\text{{[核心公式2: 例如更新规则]}}
$$

**3. 关键创新点**
- 详细说明算法层面的具体创新
- 与现有SOTA方法的本质区别

### 3.2.2 模型实现细节

**编程框架与核心库**：
- PyTorch / TensorFlow (深度学习)
- Scanpy / Seurat (单细胞分析)
- scikit-learn (传统机器学习)
- NetworkX / igraph (图算法)
- lifelines / scikit-survival (生存分析)

**超参数设置**：
| 超参数 | 设置值 | 设置依据 |
|-------|--------|---------|
| learning_rate | 1e-3 | 经验值/网格搜索 |
| batch_size | 32 | GPU内存限制 |
| hidden_dim | 256 | 消融实验结果 |

**训练策略**：
- 优化器选择（Adam/AdamW/SGD）
- 学习率调度策略（ReduceLROnPlateau/CosineAnnealing）
- 正则化方法（Dropout/L1/L2/Early Stopping）

## 3.3 模型评估与生物学解释

### 3.3.1 评估指标体系

根据研究任务类型，给出具体的评估指标：

**分类任务**：
- AUROC (Area Under ROC Curve)
- AUPRC (Area Under Precision-Recall Curve)
- F1-score, Precision, Recall
- **统计检验**：DeLong test (比较AUROC), McNemar test (比较分类器)

**生存分析**：
- C-index (Concordance Index)
- Time-dependent AUROC
- Integrated Brier Score
- **统计检验**：Log-rank test, Cox回归

**聚类任务**：
- ARI (Adjusted Rand Index)
- NMI (Normalized Mutual Information)
- Silhouette Score

### 3.3.2 生物学意义挖掘

**1. 可解释性AI方法**
- SHAP (SHapley Additive exPlanations) 值分析
- Integrated Gradients (积分梯度)
- Attention权重可视化
- 特征重要性排序

**2. 通路富集分析**
- 使用GSEA (Gene Set Enrichiture Analysis)
- ORA (Over-Representation Analysis)
- 数据库：MSigDB, KEGG, Reactome, GO
- 工具：gseapy (Python), clusterProfiler (R)

**3. 知识图谱整合**
- 整合STRING蛋白质互作网络
- 利用Gene Ontology进行功能注释
- 通过Reactome进行通路定位

### 3.3.3 技术路线流程图

**请使用以下Mermaid语法生成专业的技术路线流程图**：

```mermaid
flowchart TD
    A[数据获取] --> B[质量控制与预处理]
    B --> C[特征工程]
    C --> D[模型构建]
    D --> E[模型训练与优化]
    E --> F[模型评估]
    F --> G[生物学解释]
    G --> H[实验验证]

    A --> A1[TCGA/GEO数据下载]
    A --> A2[单细胞数据获取]

    B --> B1[缺失值插补]
    B --> B2[批次效应校正]
    B --> B3[数据标准化]

    C --> C1[特征选择]
    C --> C2[降维处理]
    C --> C3[多模态融合]

    D --> D1[网络架构设计]
    D --> D2[损失函数定义]
    D --> D3[优化算法选择]

    E --> E1[交叉验证]
    E --> E2[超参数调优]
    E --> E3[早停策略]

    F --> F1[内部验证]
    F --> F2[外部独立数据集验证]
    F --> F3[与SOTA方法比较]

    G --> G1[SHAP可解释性分析]
    G --> G2[通路富集分析]
    G --> G3[知识图谱整合]

    H --> H1[wet-lab合作验证]
    H --> H2[临床样本验证]

    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#e8f5e9
    style D fill:#f3e5f5
    style E fill:#fce4ec
    style F fill:#fff9c4
    style G fill:#e0f2f1
    style H fill:#ffebee
```

---

# 四、拟解决的关键技术问题与创新点

## 4.1 关键技术问题

列出本研究拟解决的2-3个关键技术难点：

1. **[具体技术问题1]**
   - 问题描述：...
   - 技术难点：...
   - 拟解决方案：...

2. **[具体技术问题2]**
   - 问题描述：...
   - 技术难点：...
   - 拟解决方案：...

## 4.2 创新点

### 4.2.1 算法结构创新

- 详细说明在算法结构层面的具体创新
- 与现有方法的本质区别

### 4.2.2 统计框架创新

- 说明统计建模方法的创新
- 新的统计推断框架或假设检验方法

### 4.2.3 多模态数据融合创新

- 描述如何融合不同类型的生物医学数据
- 新的融合策略或表示学习方法

---

# 五、可行性分析

## 5.1 数据资源可行性

**公开数据源保障**：
- 列出已确认可获取的数据集（使用上述推荐数据集清单）
- 说明数据获取的技术路径（API、下载链接、数据访问申请）

**数据质量评估**：
- 引用文献中对数据集质量的评价
- 说明数据集在本研究中的适用性

## 5.2 算法实现可行性

**开源框架支持**：
- PyTorch/TensorFlow生态完善
- Scanpy/Seurat单细胞分析工具链成熟
- scikit-learn提供丰富的机器学习算法

**计算资源需求**：
- GPU: 单卡NVIDIA RTX 3090/4090或A100 (预计需求)
- 内存: 64GB+ RAM
- 存储: 2TB+ SSD（用于存储大规模数据集）
- 预计训练时间: 根据模型规模，从小时到周级别

## 5.3 理论可行性

**理论基础**：
- 引用支撑本研究的理论基础（相关文献）
- 说明方法设计的理论依据

**前期工作基础**：
- 说明相关领域的研究积累
- 引用证明技术路线可行性的文献

---

# 六、年度研究计划与预期成果

## 6.1 三年研究计划

### 第一年（202X年9月 - 202X年8月）

**上半年度（9月-2月）**：
- [ ] 完成数据获取与预处理流程搭建
- [ ] 完成文献综述，撰写研究背景章节
- [ ] 完成基础模型的初步实现
- [ ] **里程碑**：完成开题答辩

**下半年度（3月-8月）**：
- [ ] 完成核心算法的开发与优化
- [ ] 在主要数据集上完成初步实验
- [ ] 撰写第一篇论文（方法学论文）
- [ ] **里程碑**：投稿会议论文（如NeurIPS/ICML/ISMB）

### 第二年（202X年9月 - 202X年8月）

**上半年度（9月-2月）**：
- [ ] 完成大规模实验验证
- [ ] 完成与SOTA方法的系统比较
- [ ] 完成可解释性分析与生物学验证
- [ ] **里程碑**：投稿期刊论文（如Bioinformatics/NAR）

**下半年度（3月-8月）**：
- [ ] 扩展方法至多个应用场景
- [ ] 完成第二篇论文（应用论文）
- [ ] 开源代码库（GitHub）
- [ ] **里程碑**：投稿顶刊子刊（如Nature Communications/NPJS）

### 第三年（202X年9月 - 202X年8月）

**上半年度（9月-2月）**：
- [ ] 完成wet-lab合作验证（如适用）
- [ ] 完成学位论文撰写
- [ ] 完成第三篇论文（综合研究）
- [ ] **里程碑**：完成预答辩

**下半年度（3月-8月）**：
- [ ] 根据评审意见修改学位论文
- [ ] 准备答辩材料
- [ ] 完成毕业答辩
- [ ] **里程碑**：获得博士学位

## 6.2 预期学术成果

### 发表论文计划

| 年份 | 目标期刊/会议 | 论文类型 | 预期状态 |
|------|--------------|---------|---------|
| 第一年 | NeurIPS/ICML/ISMB | 会议论文 | 投稿/发表 |
| 第二年 | Bioinformatics/NAR | 方法学期刊 | 投稿/发表 |
| 第二年 | Nature Comm/NPJS | 综合研究 | 投稿 |
| 第三年 | Cell/Nature子刊 | 应用研究 | 投稿 |

### 其他成果

- **开源软件**：在GitHub发布完整代码包，获取100+ stars
- **专利申请**：如涉及具体应用，申请发明专利1-2项
- **学术交流**：参加国际会议2-3次，做口头报告

---

# 参考文献

（请仅引用上述提供的真实文献，格式如下）

1. [作者] et al. ([年份]). [论文标题]. *[期刊名]*. PMID: [PMID编号]

2. ...

---

**重要提醒**：

1. **学术规范**：严禁捏造引用，仅使用提供的真实文献
2. **行文风格**：高度专业、严谨的学术中文，多用术语
3. **技术细节**：算法描述要具体，包括数学公式和超参数
4. **数据具体**：明确数据集的Accession编号和样本规模
5. **流程图**：必须包含Mermaid格式的技术路线流程图
6. **计划可行**：研究计划要合理，考虑实际可行性

请开始撰写开题报告，确保内容详实、结构严谨、逻辑清晰。
"""

    def _generate_title_suggestions(self, paradigm: str, challenge: str, original_title: str) -> str:
        """生成课题名称建议"""

        # 根据前沿框架和大挑战生成建议标题
        suggestions = []

        paradigm_lower = paradigm.lower()

        if 'causal' in paradigm_lower or '因果' in paradigm:
            suggestions.extend([
                f"基于因果推断与深度学习的{challenge}关键调控网络解析",
                f"因果机器学习框架下的{challenge}跨模态数据融合与预测模型研究",
                f"面向{challenge}的反事实学习与因果发现算法及其生物医学应用"
            ])
        elif 'single' in paradigm_lower or 'cell' in paradigm_lower or '单细胞' in paradigm:
            suggestions.extend([
                f"基于图神经网络的单细胞多组学数据整合与{challenge}解析",
                f"大规模单细胞转录组数据的深度表征学习与{challenge}预测研究",
                f"面向{challenge}的空间转录组学与单细胞数据的联合分析框架"
            ])
        elif 'spatial' in paradigm_lower or '空间' in paradigm:
            suggestions.extend([
                f"空间组学数据的深度学习与{challenge}微环境解析方法研究",
                f"基于空间约束的图神经网络与{challenge}空间模式发现",
                f"多模态空间组学数据融合与{challenge}时空演化建模"
            ])
        elif 'physics' in paradigm_lower or '物理' in paradigm or 'thermo' in paradigm_lower:
            suggestions.extend([
                f"物理约束深度学习框架下的{challenge}动力学模拟与预测",
                f"热力学引导的生成式模型与{challenge}分子机制研究",
                f"基于哈密顿神经网络的{challenge}能量面预测与动力学路径分析"
            ])
        else:
            suggestions.extend([
                f"基于深度学习的{challenge}计算模型与方法研究",
                f"{challenge}的多模态数据融合与智能预测算法研究",
                f"面向{challenge}的可解释人工智能方法与系统生物学应用"
            ])

        # 添加原标题作为参考
        suggestions.append(f"（原标题参考）{original_title}")

        return "\n".join([f"- {s}" for s in suggestions])

    def _extract_text_from_response(self, content) -> str:
        """从响应中提取文本（正确处理 ThinkingBlock）"""
        text_parts = []
        for block in content:
            # 跳过 ThinkingBlock
            if hasattr(block, 'type') and block.type == 'thinking':
                continue
            # 只处理 TextBlock
            if hasattr(block, 'type') and block.type == 'text':
                text_parts.append(block.text)
            elif hasattr(block, 'text') and not hasattr(block, 'thinking'):
                text_parts.append(block.text)
            elif isinstance(block, str):
                text_parts.append(block)
        return "\n".join(text_parts)

