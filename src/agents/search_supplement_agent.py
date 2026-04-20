# -*- coding: utf-8 -*-
"""
V7.4-D SearchSupplementAgent - 自愈引擎核心组件

当 Iteration 3 结果为 FAILURE 时，启动跨学科检索：
- arXiv (算法/物理)
- IEEE (工程)
- PubMed (生物医学)
- UK Biobank (临床规范)

目标：寻找 2025-2026 年针对该问题的最新行业标准操作程序 (SOP) 或顶级期刊方法论。

核心功能：
1. 多源检索策略（Multi-Source Retrieval）
2. 针对红方 rejection_reason 的精准搜索
3. 跨学科证据聚合
4. 返回可操作的补丁素材

作者: V7.4-D 架构工程师
日期: 2026-04-19
"""

import sys
import os
import time
import json
import re
import concurrent.futures
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path

# 项目路径设置
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv(project_root / '.env', encoding='utf-8')


# ==================== 检索域配置 ====================

SEARCH_DOMAINS = {
    'arxiv': {
        'name': 'arXiv',
        'description': '算法、物理、数学预印本库',
        'url': 'https://arxiv.org',
        'categories': ['cs.LG', 'cs.AI', 'q-bio.BM', 'physics.bio-ph'],
        'priority': 1,
        'min_year': 2025,
    },
    'ieee': {
        'name': 'IEEE Xplore',
        'description': '工程、计算机、电子领域顶会顶刊',
        'url': 'https://ieeexplore.ieee.org',
        'priority': 2,
        'min_year': 2025,
    },
    'pubmed': {
        'name': 'PubMed',
        'description': '生物医学文献库',
        'url': 'https://pubmed.ncbi.nlm.nih.gov',
        'priority': 1,
        'min_year': 2025,
    },
    'ukbiobank': {
        'name': 'UK Biobank',
        'description': '临床规范、大规模队列研究',
        'url': 'https://www.ukbiobank.ac.uk',
        'priority': 3,
        'min_year': 2025,
    }
}


# ==================== 搜索关键词映射 ====================

# 根据红方攻击类型生成搜索关键词
REJECTION_TO_SEARCH_KEYWORDS = {
    # 数据泄漏类攻击
    'LEAKAGE': {
        'primary': ['data leakage prevention', 'training set contamination',
                   'cross-validation isolation', 'nested CV leakage free'],
        'arxiv': ['nested cross-validation', 'data leakage machine learning',
                 'train-test contamination', 'temporal validation'],
        'pubmed': ['blinded validation', 'independent cohort validation',
                  'external validation biomarker', 'training set leakage medical AI'],
        'ieee': ['preprocessing pipeline isolation', 'feature selection within CV',
                'model validation without leakage'],
        'ukbiobank': ['UK Biobank validation protocol', 'holdout set standard',
                     'phenotype validation SOP'],
    },
    # 过拟合类攻击
    'OVERFITTING': {
        'primary': ['overfitting prevention', 'generalization gap',
                   'regularization deep learning', 'early stopping protocol'],
        'arxiv': ['overfitting regularization', 'generalization bound',
                 'dropout early stopping', 'model complexity control'],
        'pubmed': ['overfitting medical AI', 'clinical AI generalization',
                  'validation cohort independent'],
        'ieee': ['overfitting detection', 'model selection criterion',
                'hyperparameter tuning validation'],
        'ukbiobank': ['clinical model validation', 'external validation UK Biobank',
                     'generalization clinical prediction'],
    },
    # 偏倚类攻击
    'BIAS': {
        'primary': ['bias correction', 'confounder control',
                   'propensity score matching', 'selection bias'],
        'arxiv': ['bias correction algorithm', 'fairness machine learning',
                 'causal inference bias'],
        'pubmed': ['confounding adjustment', 'propensity matching clinical',
                  'selection bias epidemiology', 'case-control bias'],
        'ieee': ['algorithmic bias detection', 'fairness constraint'],
        'ukbiobank': ['population bias UK Biobank', 'confounder adjustment SOP',
                     'propensity score protocol'],
    },
    # 验证方法类攻击
    'VALIDATION': {
        'primary': ['validation methodology', 'benchmark independent',
                   'temporal holdout', 'nested cross-validation'],
        'arxiv': ['validation methodology', 'benchmark fairness',
                 'temporal validation time series'],
        'pubmed': ['clinical validation guideline', 'external validation biomarker',
                  'validation cohort independent'],
        'ieee': ['IEEE validation standard', 'model evaluation protocol'],
        'ukbiobank': ['UK Biobank phenotype validation', 'clinical validation SOP'],
    },
    # AlphaFold3 特有：训练集泄漏
    'AF3_LEAKAGE': {
        'primary': ['AlphaFold3 training set', 'PDB contamination',
                   'structure prediction leakage', 'MMseqs2 homology filter'],
        'arxiv': ['AlphaFold3 validation', 'protein structure benchmark',
                 'training set contamination AF3', 'homology filtering'],
        'pubmed': ['AlphaFold3 reliability', 'protein structure validation',
                  'PDB training set leakage'],
        'ieee': ['protein structure prediction benchmark'],
        'ukbiobank': ['protein structure validation clinical'],
    },
    # 动态验证缺失
    'DYNAMIC_VALIDATION': {
        'primary': ['molecular dynamics validation', 'MD simulation protocol',
                   'MM-PBSA binding energy', 'conformational stability'],
        'arxiv': ['molecular dynamics benchmark', 'MD simulation deep learning',
                 'conformational sampling validation'],
        'pubmed': ['molecular dynamics drug design', 'MD simulation protein',
                  'binding free energy validation'],
        'ieee': ['MD simulation standard', 'conformational analysis protocol'],
        'ukbiobank': ['protein dynamics clinical'],
    },
    # V7.4-F 新增：物理验证缺失
    'PHYSICAL_VALIDATION': {
        'primary': ['physical validation protocol', 'sensor detection method',
                   'experimental feasibility assessment', 'measurement uncertainty'],
        'arxiv': ['experimental validation deep learning', 'sensor calibration AI',
                 'measurement protocol machine learning'],
        'pubmed': ['clinical sensor validation', 'biomarker detection protocol',
                  'measurement feasibility study'],
        'ieee': ['sensor standard IEEE', 'measurement instrumentation protocol'],
        'ukbiobank': ['phenotype measurement SOP', 'sensor validation UK Biobank'],
    },
    # V7.4-F 新增：伪科学检测
    'PSEUDOSCIENCE': {
        'primary': ['scientific rigor validation', 'pseudoscience detection',
                   'evidence-based methodology', 'physical feasibility'],
        'arxiv': ['scientific validity assessment', 'reproducibility verification'],
        'pubmed': ['evidence-based medicine', 'clinical validation guideline',
                  'scientific method rigor'],
        'ieee': ['engineering feasibility assessment', 'validity check protocol'],
        'ukbiobank': ['clinical evidence validation SOP', 'rigorous validation UK Biobank'],
    },
}


# ==================== 检索结果数据类 ====================

@dataclass
class SearchResult:
    """单条检索结果"""
    source: str                           # 数据源 (arxiv/pubmed/ieee/ukbiobank)
    title: str                            # 标题
    authors: List[str] = field(default_factory=list)
    abstract: str = ""                    # 摘要/内容
    year: int = 0                         # 发表年份
    doi: Optional[str] = None             # DOI
    arxiv_id: Optional[str] = None        # ArXiv ID
    pmid: Optional[str] = None            # PMID
    url: str = ""                         # 原文链接
    relevance_score: float = 0.0          # 相关性评分
    key_methodology: str = ""             # 核心方法论提取
    citation: str = ""                    # 格式化引用

    def to_dict(self) -> Dict:
        return {
            'source': self.source,
            'title': self.title,
            'authors': self.authors,
            'abstract': self.abstract,
            'year': self.year,
            'doi': self.doi,
            'arxiv_id': self.arxiv_id,
            'pmid': self.pmid,
            'url': self.url,
            'relevance_score': self.relevance_score,
            'key_methodology': self.key_methodology,
            'citation': self.citation,
        }


@dataclass
class MultiSourceRetrievalResult:
    """多源检索聚合结果"""
    query_keywords: List[str]             # 搜索关键词
    detected_attack_types: List[str]      # 检测到的攻击类型
    arxiv_results: List[SearchResult] = field(default_factory=list)
    pubmed_results: List[SearchResult] = field(default_factory=list)
    ieee_results: List[SearchResult] = field(default_factory=list)
    ukbiobank_results: List[SearchResult] = field(default_factory=list)
    total_found: int = 0
    retrieval_timestamp: str = ""
    retrieval_duration: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'query_keywords': self.query_keywords,
            'detected_attack_types': self.detected_attack_types,
            'arxiv_results': [r.to_dict() for r in self.arxiv_results],
            'pubmed_results': [r.to_dict() for r in self.pubmed_results],
            'ieee_results': [r.to_dict() for r in self.ieee_results],
            'ukbiobank_results': [r.to_dict() for r in self.ukbiobank_results],
            'total_found': self.total_found,
            'retrieval_timestamp': self.retrieval_timestamp,
            'retrieval_duration': self.retrieval_duration,
        }


# ==================== SearchSupplementAgent ====================

class SearchSupplementAgent:
    """
    V7.4-D 自愈引擎核心组件

    当 Iteration 3 失败时，启动跨学科检索：
    - 针对 rejection_reason 提取攻击类型
    - 在多源数据库中搜索 2025-2026 最新方法论
    - 返回可操作的补丁素材
    """

    MAX_RESULTS_PER_SOURCE = 10
    MIN_YEAR = 2025
    MAX_YEAR = 2026

    def __init__(self):
        """初始化检索代理"""
        self.retrieval_history: List[Dict] = []
        print("[V7.4-D] SearchSupplementAgent 初始化完成")

    def execute(self, input_data: Dict) -> Dict:
        """
        执行跨学科检索

        V7.4-F 增强：新增 defense_result 和 iteration_history 参数

        Args:
            input_data: {
                'rejection_reason': str - 红方拒绝原因
                'red_attack_report': dict - 红方攻击报告
                'defense_result': dict - 防御委员会裁决 (V7.4-F 新增)
                'iteration_history': list - 迭代历史 (V7.4-F 新增)
                'hypothesis_domain': str - 研究领域
                'original_idea': str - 原始课题描述
            }

        Returns:
            {
                'success': bool,
                'retrieval_result': MultiSourceRetrievalResult,
                'patch_materials': List[Dict] - 可用于合成补丁的素材
                'attack_types_detected': List[str]
            }
        """
        rejection_reason = input_data.get('rejection_reason', '')
        red_attack_report = input_data.get('red_attack_report', {})
        defense_result = input_data.get('defense_result', {})          # V7.4-F 新增
        iteration_history = input_data.get('iteration_history', None)  # V7.4-F 新增
        hypothesis_domain = input_data.get('hypothesis_domain', 'computational_biology')
        original_idea = input_data.get('original_idea', '')

        print(f"[V7.4-F] 启动跨学科检索...")
        print(f"[V7.4-F] 拒绝原因摘要: {rejection_reason[:100]}...")
        if defense_result:
            print(f"[V7.4-F] 委员会裁决摘要: {str(defense_result)[:100]}...")

        start_time = datetime.now()

        # Step 1: 提取攻击类型 (V7.4-F 增强：多源回溯)
        attack_types = self._extract_attack_types(
            red_attack_report,
            rejection_reason,
            defense_result,       # V7.4-F 新增
            iteration_history     # V7.4-F 新增
        )
        print(f"[V7.4-F] 检测到攻击类型: {attack_types}")

        # Step 2: 生成搜索关键词
        search_keywords = self._generate_search_keywords(attack_types, original_idea)
        print(f"[V7.4-D] 搜索关���词: {search_keywords[:5]}...")

        # Step 3: 并发执行多源检索
        retrieval_result = self._execute_multi_source_search(search_keywords, attack_types)

        end_time = datetime.now()
        retrieval_result.retrieval_duration = (end_time - start_time).total_seconds()
        retrieval_result.retrieval_timestamp = end_time.isoformat()

        # Step 4: 提取补丁素材
        patch_materials = self._extract_patch_materials(retrieval_result, attack_types)

        print(f"[V7.4-D] 检索完成: 共找到 {retrieval_result.total_found} 篇相关文献")
        print(f"[V7.4-D] 检索耗时: {retrieval_result.retrieval_duration:.2f}s")

        # 记录历史
        self.retrieval_history.append({
            'timestamp': end_time.isoformat(),
            'attack_types': attack_types,
            'total_found': retrieval_result.total_found,
            'keywords_used': search_keywords,
        })

        return {
            'success': retrieval_result.total_found > 0,
            'retrieval_result': retrieval_result.to_dict(),
            'patch_materials': patch_materials,
            'attack_types_detected': attack_types,
        }

    # V7.4-F 新增攻击类型：物理验证缺失和伪科学检测
    PHYSICAL_VALIDATION = {
        'primary': ['physical validation', 'sensor validation', 'measurement protocol',
                   'experimental feasibility', 'sensor detection'],
        'arxiv': ['experimental validation protocol', 'measurement uncertainty',
                 'sensor calibration', 'instrument validation'],
        'pubmed': ['clinical measurement validation', 'biomarker detection method',
                  'sensor feasibility study'],
        'ieee': ['sensor standard', 'measurement protocol IEEE'],
        'ukbiobank': ['measurement validation SOP', 'sensor protocol UK Biobank'],
    }

    PSEUDOSCIENCE_DETECTED = {
        'primary': ['pseudoscience detection', 'scientific rigor validation',
                   'physical feasibility check'],
        'arxiv': ['scientific validity assessment', 'pseudoscience identification'],
        'pubmed': ['evidence-based validation', 'scientific method rigor'],
        'ieee': ['engineering feasibility assessment'],
        'ukbiobank': ['clinical evidence validation'],
    }

    def _extract_attack_types(
        self,
        red_attack_report: dict,
        rejection_reason: str,
        defense_result: dict = None,      # V7.4-F 新增参数
        iteration_history: list = None    # V7.4-F 新增参数
    ) -> List[str]:
        """
        V7.4-F 增强：从多源数据中提取攻击类型

        数据源优先级：
        1. red_attack_report (红方攻击报告)
        2. defense_result (委员会裁决文本)
        3. iteration_history (迭代历史累积)
        4. rejection_reason (拒绝原因)

        Returns:
            List[str]: 攻击类型列表，至少包含一个有效类型
        """
        attack_types = []

        # ==================== 数据源1：红方攻击报告 ====================
        attack_text = ""
        if red_attack_report:
            critical_flaws = red_attack_report.get('critical_flaws', [])
            for flaw in critical_flaws[:5]:
                if isinstance(flaw, dict):
                    attack_text += flaw.get('issue', '') + " "
                    # V7.4-F 新增：提取 category 字段
                    category = flaw.get('category', '')
                    if category and category.upper() in [
                        'LEAKAGE', 'OVERFITTING', 'BIAS', 'VALIDATION',
                        'AF3_LEAKAGE', 'DYNAMIC_VALIDATION',
                        'PSEUDOSCIENCE', 'PHYSICAL_IMPOSSIBILITY',
                        'PHYSICAL_VALIDATION'  # V7.4-F 新增类型
                    ]:
                        attack_types.append(category.upper())
                else:
                    attack_text += str(flaw) + " "

            severe_issues = red_attack_report.get('severe_issues', [])
            for issue in severe_issues[:3]:
                if isinstance(issue, dict):
                    attack_text += issue.get('issue', '') + " "
                else:
                    attack_text += str(issue) + " "

        # ==================== V7.4-F 新增：数据源2：委员会裁决文本 ====================
        if defense_result and not attack_types:
            final_verdict = defense_result.get('final_verdict', '')
            critical_issues = defense_result.get('critical_issues', [])
            committee_response = defense_result.get('committee_response', '')

            # NLP 提取攻击类型（当红方报告为空时回溯）
            if final_verdict:
                attack_text += final_verdict + " "
            if committee_response:
                attack_text += committee_response + " "

            for issue in critical_issues[:5]:
                attack_text += str(issue) + " "

            print(f"[V7.4-F] 从委员会裁决回溯: '{attack_text[:100]}...'")

        # ==================== V7.4-F 新增：数据源3：迭代历史累积 ====================
        if iteration_history and not attack_types:
            for iter_record in iteration_history[-2:]:  # 回溯最近2轮
                if iter_record.get('status') == 'defense_failed':
                    verdict = iter_record.get('defense_verdict', '')
                    red_verdict = iter_record.get('red_team_verdict', '')
                    attack_text += verdict + " " + red_verdict + " "

        # ==================== 数据源4：拒绝原因 ====================
        attack_text += rejection_reason
        attack_text_lower = attack_text.lower()

        # ==================== 关键词检测（当 category 未直接提取时）====================
        if not attack_types:
            type_keywords = {
                'LEAKAGE': ['data leakage', '数据泄漏', 'leak', '泄漏', '训练集泄漏',
                           'training set contamination', 'contamination', '穿越',
                           '泄露风险', '样本泄漏', 'temporal leakage', 'future data'],
                'OVERFITTING': ['overfit', '过拟合', 'overfitting', '泛化', 'generalization',
                              '泛化能力', '拟合过度', '泛化性', '过拟合风险'],
                'BIAS': ['bias', '偏倚', '偏', 'confounder', '混杂', '内生性',
                        'selection bias', '选择偏倚', 'propensity'],
                'VALIDATION': ['validation', '验证', 'benchmark', '基准', '独立验证',
                              'external validation', 'nested cv', '交叉验证'],
                'AF3_LEAKAGE': ['alphafold3', 'af3', 'pdb', 'pdb training',
                              '结构预测泄漏', 'homology', '同源性', 'mmseqs'],
                'DYNAMIC_VALIDATION': ['molecular dynamics', 'md simulation', '动态',
                                      'conformational', '构象', 'mm-pbsa', 'binding energy',
                                      '物理验证', '物理动力学'],
                # V7.4-F 新增攻击类型
                'PSEUDOSCIENCE': ['伪科学', 'pseudoscience', '科幻', 'science fiction',
                                 '无实验验证', '无法验证', '超自然', 'supernatural',
                                 '量子共振', 'quantum resonance', '能量场', 'biofield',
                                 '意识探测', 'consciousness detection'],
                'PHYSICAL_VALIDATION': ['物理验证缺失', '无传感器', 'no sensor',
                                       '信号捕获', 'signal capture', '效应度量',
                                       'measurement', '物理可行性', 'physical feasibility',
                                       '无法测量', 'cannot measure'],
            }

            for attack_type, keywords in type_keywords.items():
                for kw in keywords:
                    if kw.lower() in attack_text_lower:
                        attack_types.append(attack_type)
                        break

        # ==================== V7.4-G 新增：前沿科学排除伪科学判定 ====================
        # 前沿科学关键词（不应标记为 PSEUDOSCIENCE）
        FRONTIER_SCIENCE_KEYWORDS = ['alphafold', 'protein', 'mutation', 'crispr', 'gwas',
                                    'sequencing', 'rna-seq', 'single cell', 'genomic',
                                    'biobank', 'xgboost', 'deep learning', 'neural network']

        # 如果检测到 PSEUDOSCIENCE，检查是否为前沿科学
        if 'PSEUDOSCIENCE' in attack_types:
            # 从假说文本中检查前沿科学关键词
            hypothesis_text = ""
            if defense_result:
                hypothesis_text = defense_result.get('hypothesis_text', '') or ""
            if not hypothesis_text and iteration_history:
                for iter_record in iteration_history:
                    hypothesis_text += iter_record.get('hypothesis', '') or ""

            if any(kw in hypothesis_text.lower() for kw in FRONTIER_SCIENCE_KEYWORDS):
                # 前沿科学不应标记为 PSEUDOSCIENCE
                attack_types.remove('PSEUDOSCIENCE')
                if 'VALIDATION' not in attack_types:
                    attack_types.append('VALIDATION')  # 替换为方法论验证类型
                print(f"[V7.4-G] 前沿科学关键词检测，PSEUDOSCIENCE 替换为 VALIDATION")

        # ==================== V7.4-F 修复：禁止盲目搜索 ====================
        # 如果仍未检测到任何类型，返回 PHYSICAL_VALIDATION 触发专项搜索
        if not attack_types:
            attack_types.append('PHYSICAL_VALIDATION')
            print("[V7.4-F] ⚠️ 未检测到具体攻击类型，触发物理验证专项搜索")

        return list(set(attack_types))  # 去重

    def _generate_search_keywords(self, attack_types: List[str], original_idea: str) -> List[str]:
        """
        根据攻击类型生成针对性搜索关键词

        Returns:
            List[str]: 搜索关键词列表
        """
        keywords = []

        # 从每个攻击类型的关键词映射中提取
        for attack_type in attack_types:
            if attack_type in REJECTION_TO_SEARCH_KEYWORDS:
                type_keywords = REJECTION_TO_SEARCH_KEYWORDS[attack_type]
                # 添加 primary 关键词
                keywords.extend(type_keywords.get('primary', []))
                # 添加特定领域关键词
                keywords.extend(type_keywords.get('arxiv', []))
                keywords.extend(type_keywords.get('pubmed', []))

        # 从原始课题提取领域关键词
        if original_idea:
            # 提取关键技术名词
            tech_keywords = re.findall(r'\b[A-Z][a-z]+\b|\b[A-Z]{2,}\b', original_idea)
            keywords.extend(tech_keywords[:5])

        # 添加年份约束关键词
        keywords.append('2025')
        keywords.append('2026')

        # 去重并限制数量
        keywords = list(set(keywords))
        return keywords[:20]  # 最多 20 个关键词

    def _execute_multi_source_search(
        self,
        search_keywords: List[str],
        attack_types: List[str]
    ) -> MultiSourceRetrievalResult:
        """
        ���发执行多源检索

        Returns:
            MultiSourceRetrievalResult: 聚合检索结果
        """
        result = MultiSourceRetrievalResult(
            query_keywords=search_keywords,
            detected_attack_types=attack_types,
        )

        # 构建并发检索任务
        search_tasks = []

        # ArXiv 检索任务
        def fetch_arxiv():
            return self._search_arxiv(search_keywords, attack_types)

        # PubMed 检索任务
        def fetch_pubmed():
            return self._search_pubmed(search_keywords, attack_types)

        # IEEE 检索任务（模拟 - 使用 Semantic Scholar 作为替代）
        def fetch_ieee():
            return self._search_ieee_alternative(search_keywords, attack_types)

        # UK Biobank 检索任务（模拟 - 使用 PubMed 搜索 UK Biobank 相关文献）
        def fetch_ukbiobank():
            return self._search_ukbiobank_alternative(search_keywords, attack_types)

        search_tasks = [fetch_arxiv, fetch_pubmed, fetch_ieee, fetch_ukbiobank]

        print(f"[V7.4-D] 启动 {len(search_tasks)} 个并发检索任务...")

        # 并发执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(task): task for task in search_tasks}

            done, pending = concurrent.futures.wait(
                futures.keys(),
                timeout=120,
                return_when=concurrent.futures.ALL_COMPLETED
            )

            for future in done:
                try:
                    task_result = future.result(timeout=5)
                    source = task_result.get('source', 'unknown')
                    papers = task_result.get('papers', [])

                    if source == 'arxiv':
                        result.arxiv_results = papers
                        print(f"[V7.4-D] [ArXiv] 返回 {len(papers)} 篇文献")
                    elif source == 'pubmed':
                        result.pubmed_results = papers
                        print(f"[V7.4-D] [PubMed] 返回 {len(papers)} 篇文献")
                    elif source == 'ieee':
                        result.ieee_results = papers
                        print(f"[V7.4-D] [IEEE] 返回 {len(papers)} 篇文献")
                    elif source == 'ukbiobank':
                        result.ukbiobank_results = papers
                        print(f"[V7.4-D] [UKB] 返回 {len(papers)} 篇文献")

                except Exception as e:
                    print(f"[V7.4-D] 检索任务异常: {e}")

            # 取消超时任务
            for future in pending:
                future.cancel()

        result.total_found = (
            len(result.arxiv_results) +
            len(result.pubmed_results) +
            len(result.ieee_results) +
            len(result.ukbiobank_results)
        )

        return result

    def _search_arxiv(self, keywords: List[str], attack_types: List[str]) -> Dict:
        """
        ArXiv 检索

        Returns:
            {'source': 'arxiv', 'papers': List[SearchResult]}
        """
        try:
            from src.data_sources.arxiv_searcher import ArXivSearcher
            searcher = ArXivSearcher()

            # 构建查询字符串
            query = ' '.join(keywords[:10])

            # 执行搜索（2025-2026 年文献）
            search_result = searcher.search(
                query,
                max_results=self.MAX_RESULTS_PER_SOURCE,
                start_year=self.MIN_YEAR,
                end_year=self.MAX_YEAR,
            )

            papers = []
            for p in search_result.get('papers', []):
                # 构建格式化引用
                arxiv_id = p.get('arxiv_id', '')
                citation = f"[arXiv: {arxiv_id}] {p.get('title', '')} ({p.get('year', 0)})"

                papers.append(SearchResult(
                    source='arxiv',
                    title=p.get('title', ''),
                    authors=p.get('authors', []),
                    abstract=p.get('abstract', ''),
                    year=p.get('year', 0),
                    arxiv_id=arxiv_id,
                    url=p.get('abs_url', f"https://arxiv.org/abs/{arxiv_id}"),
                    relevance_score=self._calculate_relevance(p.get('abstract', ''), keywords),
                    key_methodology=self._extract_methodology(p.get('abstract', '')),
                    citation=citation,
                ))

            return {'source': 'arxiv', 'papers': papers}

        except Exception as e:
            print(f"[V7.4-D] ArXiv 检索异常: {e}")
            return {'source': 'arxiv', 'papers': []}

    def _search_pubmed(self, keywords: List[str], attack_types: List[str]) -> Dict:
        """
        PubMed 检索

        Returns:
            {'source': 'pubmed', 'papers': List[SearchResult]}
        """
        try:
            from src.utils.pubmed import PubMedSearcher
            searcher = PubMedSearcher()

            # 构建查询字符串
            query = ' '.join(keywords[:10])

            # 执行搜索（2025-2026 年文献）
            search_result = searcher.search_by_idea(
                query,
                max_results=self.MAX_RESULTS_PER_SOURCE,
                start_year=self.MIN_YEAR,
                end_year=self.MAX_YEAR,
            )

            papers = []
            for p in search_result.get('papers', []):
                pmid = p.get('pmid', '')
                citation = f"[PMID: {pmid}] {p.get('title', '')} ({p.get('year', 0)})"

                # V7.4-D Debug: 检查 abstract 是否存在
                abstract = p.get('abstract', '')
                rel_score = self._calculate_relevance(abstract, keywords)
                print(f"[V7.4-D Debug] PMID: {pmid}, abstract_len: {len(abstract)}, relevance: {rel_score:.3f}")

                papers.append(SearchResult(
                    source='pubmed',
                    title=p.get('title', ''),
                    authors=p.get('authors', []),
                    abstract=abstract,
                    year=p.get('year', 0),
                    pmid=pmid,
                    doi=p.get('doi'),
                    url=p.get('url', f"https://pubmed.ncbi.nlm.nih.gov/{pmid}"),
                    relevance_score=rel_score,
                    key_methodology=self._extract_methodology(abstract),
                    citation=citation,
                ))

            return {'source': 'pubmed', 'papers': papers}

        except Exception as e:
            print(f"[V7.4-D] PubMed 检索异常: {e}")
            return {'source': 'pubmed', 'papers': []}

    def _search_ieee_alternative(self, keywords: List[str], attack_types: List[str]) -> Dict:
        """
        IEEE 检索替代方案（使用 Semantic Scholar）

        由于 IEEE Xplore 需要 API key，使用 Semantic Scholar 替代检索 IEEE 相关文献

        Returns:
            {'source': 'ieee', 'papers': List[SearchResult]}
        """
        try:
            from src.data_sources.semantic_scholar_searcher import SemanticScholarSearcher
            searcher = SemanticScholarSearcher()

            # 构建查询（添加 IEEE 相关关键词）
            ieee_keywords = keywords[:8] + ['IEEE', 'standard', 'protocol']
            query = ' '.join(ieee_keywords)

            search_result = searcher.search(query, max_results=self.MAX_RESULTS_PER_SOURCE)

            papers = []
            for p in search_result.get('papers', []):
                doi = p.get('doi', '')
                year = p.get('year', 0)

                # 过滤：只保留 2025+ 的文献
                if year < self.MIN_YEAR:
                    continue

                citation = f"[DOI: {doi}] {p.get('title', '')} ({year})"

                papers.append(SearchResult(
                    source='ieee',
                    title=p.get('title', ''),
                    authors=p.get('authors', []),
                    abstract=p.get('abstract', ''),
                    year=year,
                    doi=doi,
                    url=p.get('url', f"https://doi.org/{doi}" if doi else ""),
                    relevance_score=self._calculate_relevance(p.get('abstract', ''), keywords),
                    key_methodology=self._extract_methodology(p.get('abstract', '')),
                    citation=citation,
                ))

            return {'source': 'ieee', 'papers': papers}

        except Exception as e:
            print(f"[V7.4-D] IEEE 替代检索异常: {e}")
            return {'source': 'ieee', 'papers': []}

    def _search_ukbiobank_alternative(self, keywords: List[str], attack_types: List[str]) -> Dict:
        """
        UK Biobank 检索替代方案（使用 PubMed 搜索 UK Biobank 相关文献）

        Returns:
            {'source': 'ukbiobank', 'papers': List[SearchResult]}
        """
        try:
            from src.utils.pubmed import PubMedSearcher
            searcher = PubMedSearcher()

            # 构建查询（添加 UK Biobank 相关关键词）
            ukb_keywords = keywords[:8] + ['UK Biobank', 'validation', 'protocol', 'SOP']
            query = ' '.join(ukb_keywords)

            search_result = searcher.search_by_idea(
                query,
                max_results=self.MAX_RESULTS_PER_SOURCE,
                start_year=self.MIN_YEAR,
                end_year=self.MAX_YEAR,
            )

            papers = []
            for p in search_result.get('papers', []):
                pmid = p.get('pmid', '')
                citation = f"[PMID: {pmid}] {p.get('title', '')} ({p.get('year', 0)})"

                papers.append(SearchResult(
                    source='ukbiobank',
                    title=p.get('title', ''),
                    authors=p.get('authors', []),
                    abstract=p.get('abstract', ''),
                    year=p.get('year', 0),
                    pmid=pmid,
                    url=p.get('url', f"https://pubmed.ncbi.nlm.nih.gov/{pmid}"),
                    relevance_score=self._calculate_relevance(p.get('abstract', ''), keywords),
                    key_methodology=self._extract_methodology(p.get('abstract', '')),
                    citation=citation,
                ))

            return {'source': 'ukbiobank', 'papers': papers}

        except Exception as e:
            print(f"[V7.4-D] UK Biobank 替代检索异常: {e}")
            return {'source': 'ukbiobank', 'papers': []}

    def _calculate_relevance(self, abstract: str, keywords: List[str]) -> float:
        """
        计算文献与关键词的相关性评分

        V7.4-D 修复：使用更宽松的匹配逻辑，因为 ML 关键词可能与生物医学文献不直接匹配

        Returns:
            float: 相关性评分 (0-1)
        """
        if not abstract:
            # 如果没有摘要，给予默认相关性（而不是 0）
            # 原因：PubMed 检索已按关键词过滤，文献本身是相关的
            return 0.15

        abstract_lower = abstract.lower()
        matches = 0

        # 原始关键词匹配
        for kw in keywords:
            kw_lower = kw.lower()
            # 宽松匹配：检查关键词的任何子部分
            if kw_lower in abstract_lower:
                matches += 1
            # 检查关键词的核心词汇（去掉修饰词）
            elif len(kw_lower) > 5:
                core_words = kw_lower.split()
                for word in core_words:
                    if len(word) > 4 and word in abstract_lower:
                        matches += 0.5  # 半匹配也算
                        break

        # V7.4-D: 如果关键词匹配数为 0，但文献被检索到，说明存在隐含相关性
        # 给予最低保底分数 0.1（因为 PubMed 已按关键词过滤）
        base_score = min(matches / max(len(keywords), 1), 1.0)
        if base_score < 0.1 and abstract:
            # 保底分数：文献被检索到就说明有一定相关性
            return 0.1

        return base_score

    def _extract_methodology(self, abstract: str) -> str:
        """
        从摘要中提取核心方法论��键词

        Returns:
            str: 方法论摘要
        """
        if not abstract:
            return ""

        # 方法论关键词模式
        methodology_patterns = [
            r'using\s+([A-Z][a-z]+(?:\s+[a-z]+){0,3})',
            r'applied\s+([A-Z][a-z]+(?:\s+[a-z]+){0,3})',
            r'implemented\s+([A-Z][a-z]+(?:\s+[a-z]+){0,3})',
            r'employed\s+([A-Z][a-z]+(?:\s+[a-z]+){0,3})',
            r'(?:nested|cross|external)\s+(?:validation|CV)',
            r'(?:regularization|dropout|early\s+stopping)',
            r'(?:MM-PBSA|molecular\s+dynamics|conformational)',
        ]

        extracted = []
        for pattern in methodology_patterns:
            matches = re.findall(pattern, abstract, re.IGNORECASE)
            if matches:
                extracted.extend(matches[:2])

        return ', '.join(extracted[:5]) if extracted else ""

    def _extract_patch_materials(
        self,
        retrieval_result: MultiSourceRetrievalResult,
        attack_types: List[str]
    ) -> List[Dict]:
        """
        从检索结果中提取可用于合成补丁的素材

        Returns:
            List[Dict]: 补丁素材列表
        """
        materials = []

        # 按相关性排序聚合所有结果
        all_results = (
            retrieval_result.arxiv_results +
            retrieval_result.pubmed_results +
            retrieval_result.ieee_results +
            retrieval_result.ukbiobank_results
        )

        # 按相关性评分排序
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)

        # 提取 Top 5 高相关性结果作为补丁素材
        for result in all_results[:5]:
            # V7.4-D: 降低相关性阈值从 0.3 到 0.05，因为检索关键词较多导致匹配率低
            # 如果有文献被检索到，即使相关性低也应该作为补丁素材
            if result.relevance_score > 0.05 or len(all_results) <= 3:  # 降级阈值或强制接受
                materials.append({
                    'citation': result.citation,
                    'key_methodology': result.key_methodology,
                    'source': result.source,
                    'relevance_score': result.relevance_score,
                    'year': result.year,
                    'attack_type_relevant': attack_types,
                    'abstract_summary': result.abstract[:500] if result.abstract else "",
                })

        print(f"[V7.4-D] 补丁素材提取: 共 {len(all_results)} 篇文献, 筛选出 {len(materials)} 条素材")
        for m in materials:
            print(f"[V7.4-D]   - {m['citation'][:50]}... (relevance: {m['relevance_score']:.2f})")

        return materials


# ==================== 测试入口 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V7.4-D SearchSupplementAgent 测试")
    print("=" * 70)

    agent = SearchSupplementAgent()

    # 模拟输入数据
    test_input = {
        'rejection_reason': '方案存在数据穿越风险：AlphaFold3 训练集 PDB 文献可能包含验证集样本，导致泄漏',
        'red_attack_report': {
            'critical_flaws': [
                {'issue': 'AF3 训练集 PDB 同源性泄漏风险', 'category': 'LEAKAGE'}
            ],
            'severe_issues': [
                {'issue': '缺乏动态物理验证（MD simulation）'}
            ],
        },
        'defense_result': {'defense_passed': False},
        'hypothesis_domain': 'computational_biology',
        'original_idea': 'AlphaFold3 augmented molecular dynamics pipeline for rare pathogenic variant prediction',
    }

    result = agent.execute(test_input)

    print("\n=== 检索结果 ===")
    print(f"成功: {result['success']}")
    print(f"检测攻击类型: {result['attack_types_detected']}")
    print(f"总文献数: {result['retrieval_result']['total_found']}")
    print(f"补丁素材数: {len(result['patch_materials'])}")

    for m in result['patch_materials']:
        print(f"\n补丁素材: {m['citation']}")
        print(f"  方法论: {m['key_methodology']}")
        print(f"  相关性: {m['relevance_score']:.2f}")

    print("\n" + "=" * 70)
    print("测试完成")