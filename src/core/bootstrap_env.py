# -*- coding: utf-8 -*-
"""
动态环境快照预注入 (Dynamic Environment Bootstrapping)

V4.1 新增核心机制：
- 解析用户输入提取关键词和学科领域
- 生成动态沙盒边界强制注入Prompt顶部
- 阻断跨学科胡编乱造
"""

import re
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class BootstrapEnvironment:
    """动态环境快照数据结构"""

    domain: str                      # 检测到的学科领域
    domain_boundary: str             # 学科领域边界文本
    keyword_constraints: str         # 关键词约束文本
    modality_lock: str               # 模态锁定文本
    data_source_whitelist: List[str] # 数据源白名单
    keywords: List[str]              # 提取的核心关键词
    injected_at_top: bool            # 是否已注入Prompt顶部
    bootstrap_text: str              # 完整的Bootstrap注入文本


class BootstrapInjector:
    """
    动态环境快照预注入器

    核心功能：
    1. 解析用户输入的关键词和学科领域
    2. 生成动态沙盒边界
    3. 强制注入Prompt顶部
    4. 阻断跨学科的胡编乱造

    设计理念：
    - 用户输入是材料学，绝不允许生成临床医学的幻觉
    - 用户输入是神经科学，绝不允许生成肿瘤学的术语
    """

    # 学科领域关键词库（用于自动检测）
    DOMAIN_KEYWORDS = {
        'neuroscience': [
            'brain', 'neural', 'cognitive', 'neurodegeneration',
            'ADNI', 'MRI', 'PET', 'hippocampus', 'cortex',
            'Alzheimer', 'dementia', 'MMSE', 'CSF', 'amyloid',
            'tau', 'neuron', 'synapse', 'glial'
        ],
        'cardiology': [
            'heart', 'cardiac', 'cardiovascular', 'ECG',
            'myocardial', 'arrhythmia', 'atrial', 'ventricular',
            'coronary', 'blood pressure', 'cholesterol'
        ],
        'oncology': [
            'cancer', 'tumor', 'oncology', 'mutation',
            'carcinoma', 'neoplasm', 'malignant', 'benign',
            'metastasis', 'chemotherapy', 'radiotherapy'
        ],
        'genomics': [
            'GWAS', 'WGS', 'SNP', 'genetic', 'genome',
            'variant', 'allele', 'mutation', 'gene',
            'chromosome', 'DNA', 'RNA', 'sequencing'
        ],
        'proteomics': [
            'pQTL', 'protein', 'peptide', 'mass spectrometry',
            'proteome', 'expression', 'fold', 'binding'
        ],
        'immunology': [
            'immune', 'antibody', 'T-cell', 'B-cell',
            'inflammation', 'cytokine', 'vaccine', 'autoimmune',
            'lymphocyte', 'macrophage'
        ],
        'metabolomics': [
            'mQTL', 'metabolite', 'metabolism', 'metabolic',
            'glucose', 'lipid', 'amino acid', 'biomarker'
        ],
        'epidemiology': [
            'cohort', 'prevalence', 'incidence', 'risk factor',
            'mortality', 'survival', 'outcome', 'population'
        ],
        'materials_science': [
            'material', 'nanoparticle', 'polymer', 'composite',
            'synthesis', 'property', 'structure', 'surface'
        ],
        'clinical_medicine': [
            'patient', 'treatment', 'diagnosis', 'therapy',
            'clinical', 'hospital', 'medication', 'drug'
        ]
    }

    # 数据源白名单（继承现有模态锁定）
    DATA_SOURCE_WHITELIST = {
        'dry_lab': [
            'ADNI', 'GWAS', 'EHR', 'pQTL', 'mQTL',
            'UK Biobank', 'clinical_database', 'public cohort',
            'meta-analysis', 'summary statistics'
        ],
        'wet_lab': []  # 本系统禁止湿实验
    }

    # 通用停用词
    STOPWORDS = {
        'the', 'and', 'for', 'with', 'using', 'based', 'study',
        'research', 'analysis', 'method', 'approach', 'investigate',
        'explore', 'examine', 'novel', 'new', 'propose'
    }

    def inject_bootstrap(self, user_input: str) -> BootstrapEnvironment:
        """
        预注入动态环境

        Args:
            user_input: 用户原始输入文本

        Returns:
            BootstrapEnvironment: 可直接插入Prompt的环境快照
        """
        # 1. 检测学科领域
        detected_domain = self._detect_domain(user_input)

        # 2. 提取关键词
        keywords = self._extract_keywords(user_input)

        # 3. 生成模态锁定（继承钢印）
        modality_lock = self._generate_modality_lock(detected_domain)

        # 4. 构建边界文本
        domain_boundary = self._build_domain_boundary(detected_domain, keywords)
        keyword_constraints = self._build_keyword_constraints(keywords)

        # 5. 确定数据源白名单
        data_whitelist = self.DATA_SOURCE_WHITELIST.get('dry_lab', [])

        # 6. 构建完整Bootstrap文本
        bootstrap_text = self._build_full_bootstrap(
            domain_boundary,
            keyword_constraints,
            modality_lock,
            detected_domain
        )

        return BootstrapEnvironment(
            domain=detected_domain,
            domain_boundary=domain_boundary,
            keyword_constraints=keyword_constraints,
            modality_lock=modality_lock,
            data_source_whitelist=data_whitelist,
            keywords=keywords,
            injected_at_top=True,
            bootstrap_text=bootstrap_text
        )

    def _detect_domain(self, user_input: str) -> str:
        """
        检测学科领域

        Args:
            user_input: 用户输入文本

        Returns:
            str: 检测到的学科领域
        """
        input_lower = user_input.lower()

        # 计算各领域的匹配分数
        domain_scores = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in input_lower)
            if score > 0:
                domain_scores[domain] = score

        # 返回分数最高的领域
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)

        # 默认领域
        return 'general_biomedical'

    def _extract_keywords(self, user_input: str) -> List[str]:
        """
        提取关键词

        Args:
            user_input: 用户输入文本

        Returns:
            List[str]: 关键词列表（最多10个）
        """
        # 提取3-15个字母的英文词
        words = re.findall(r'\b[A-Za-z]{3,15}\b', user_input)

        # 过滤停用词
        keywords = [w for w in words if w.lower() not in self.STOPWORDS]

        # 去重
        unique_keywords = list(dict.fromkeys(keywords))

        return unique_keywords[:10]

    def _generate_modality_lock(self, domain: str) -> str:
        """
        生成模态锁定文本

        Args:
            domain: 学科领域

        Returns:
            str: 模态锁定文本
        """
        return """
╔══════════════════════════════════════════════════════════════════╗
║                    【模态锁定 - MODALITY LOCK】                    ║
╚══════════════════════════════════════════════════════════════════╝

**本研究限定为纯干实验 (Dry Lab)**
允许数据源: ADNI, GWAS, EHR, pQTL, mQTL, UK Biobank, clinical_database

**绝对禁止**:
- 湿实验技术: Western Blot, PCR, ELISA, 单细胞测序, CRISPR
- 显微镜技术: confocal, two-photon, electron microscopy
- 空间转录组: Visium, Slide-seq, MERFISH
- 体内实验: animal model, cell culture, patient tissue

**理由**: 本系统专注于临床队列数据分析，不涉及实验室实验验证
"""

    def _build_domain_boundary(self, domain: str, keywords: List[str]) -> str:
        """
        构建领域边界文本

        Args:
            domain: 学科领域
            keywords: 关键词列表

        Returns:
            str: 领域边界文本
        """
        current_year = datetime.now().year

        return f"""
【学科领域锁定 - DOMAIN BOUNDARY】

检测领域: {domain}
核心关键词: {', '.join(keywords[:5]) if keywords else '未提取'}

╔══════════════════════════════════════════════════════════════════╗
║  边界声明: 本研究假说必须在以下范围内构建                          ║
╚══════════════════════════════════════════════════════════════════╝

**允许范围**:
- 数据来源: 仅限公开临床队列数据 (ADNI, UK Biobank, GWAS summary stats)
- 方法范围: 统计学因果推断、机器学习预测模型、meta-analysis
- 术语范围: 仅限 {domain} 领域的专业术语

**排除范围**:
- 任何需要实验室实验验证的机制
- 跨学科领域的术语和假说（如: {domain} ≠ oncology）
- 未经PubMed验证的虚构现象或实验数值

**年份锁定**: {current_year - 5} - {current_year}
"""

    def _build_keyword_constraints(self, keywords: List[str]) -> str:
        """
        构建关键词约束文本

        Args:
            keywords: 关键词列表

        Returns:
            str: 关键词约束文本
        """
        if not keywords:
            return ""

        current_year = datetime.now().year

        return f"""
【关键词约束 - KEYWORD CONSTRAINTS】

强制包含: 至少使用以下关键词之一
{', '.join(keywords[:3])}

检索策略要求:
- PubMed查询必须包含至少1个上述关键词
- 年份锁定: {current_year - 5} - {current_year}
- 最低影响因子: 可配置（默认不限）

禁止事项:
- 不得在PubMed检索中使用年份词汇 (如 "2022-2024", "recent")
- 年份限制由系统后台参数处理，不在query中体现
"""

    def _build_full_bootstrap(
        self,
        domain_boundary: str,
        keyword_constraints: str,
        modality_lock: str,
        domain: str
    ) -> str:
        """
        构建完整Bootstrap注入文本

        Args:
            domain_boundary: 领域边界
            keyword_constraints: 关键词约束
            modality_lock: 模态锁定
            domain: 学科领域

        Returns:
            str: 完整Bootstrap文本
        """
        return f"""
{domain_boundary}

{keyword_constraints}

{modality_lock}

【动态沙盒激活状态】
- 领域: {domain}
- 状态: ACTIVE
- 注入位置: Prompt顶部
- 边界强制: ON

---

**重要提示**: 以下所有生成内容必须严格遵守上述边界约束。
违反边界约束将触发早期熔断机制。
"""


# ==============================================================================
# 全局便捷函数
# ==============================================================================

_global_bootstrap_injector = None


def get_bootstrap_injector() -> BootstrapInjector:
    """
    获取全局 BootstrapInjector 实例（单例模式）

    Returns:
        BootstrapInjector 实例
    """
    global _global_bootstrap_injector
    if _global_bootstrap_injector is None:
        _global_bootstrap_injector = BootstrapInjector()
    return _global_bootstrap_injector


def inject_bootstrap(user_input: str) -> BootstrapEnvironment:
    """
    全局便捷函数：预注入动态环境

    Args:
        user_input: 用户原始输入文本

    Returns:
        BootstrapEnvironment: 环境快照
    """
    injector = get_bootstrap_injector()
    return injector.inject_bootstrap(user_input)


def get_domain_from_input(user_input: str) -> str:
    """
    全局便捷函数：从输入检测学科领域

    Args:
        user_input: 用户输入

    Returns:
        str: 学科领域
    """
    injector = get_bootstrap_injector()
    return injector._detect_domain(user_input)