# -*- coding: utf-8 -*-
"""
V7.1 动态 RAG 路由器 (Dynamic Data Source Router) - 集中式日志挂载版

V7.1 核心改进：
1. 集中式日志挂载：网络请求深水区异常自动捕获堆栈
2. Task ID 贯穿：支持外部传入 Task ID（通过 TaskLogContext）
3. 超时统计追踪：记录每个数据源的超时次数

核心机制：
- 领域关键词检测
- 多数据源并发检索
- 智能路由决策
- 检索结果聚合
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import aiohttp
from datetime import datetime
from concurrent.futures import TimeoutError as FuturesTimeoutError

# ==================== V7.1: 集中式日志挂载 ====================
from src.utils.logger import get_central_logger, TaskLogContext, log_exceptions

logger = get_central_logger()


# ==================== V7.1: 数据源优先级配置 ====================

class SourcePriority(Enum):
    """V7.1 数据源优先级级别"""
    PRIMARY = "primary"      # 主要数据源（必须成功）
    SECONDARY = "secondary"  # 辅助数据源（可超时跳过）
    FALLBACK = "fallback"    # 降级数据源（仅在其他失败时使用）

# V7.1: 数据源优先级映射
SOURCE_PRIORITY_CONFIG = {
    'pubmed': SourcePriority.PRIMARY,
    'arxiv': SourcePriority.PRIMARY,
    'semantic_scholar': SourcePriority.SECONDARY,
    'crossref': SourcePriority.FALLBACK,
    'google_scholar': SourcePriority.FALLBACK,
}

# V7.1: 数据源超时配置（秒）
SOURCE_TIMEOUT_CONFIG = {
    'pubmed': 15,           # PubMed 超时 15秒
    'arxiv': 10,            # ArXiv 超时 10秒
    'semantic_scholar': 20, # Semantic Scholar 超时 20秒
    'crossref': 15,         # CrossRef 超时 15秒
    'default': 30,          # 默认超时 30秒
}

# V7.1: 降级数据源映射
FALLBACK_SOURCE_MAPPING = {
    'pubmed': ['semantic_scholar', 'crossref'],
    'arxiv': ['semantic_scholar'],
    'semantic_scholar': ['crossref'],
}


# ==================== 领域数据源映射 ====================

DOMAIN_SOURCE_MAPPING = {
    # ==================== 医学/生命科学 → PubMed ====================
    'medicine': ['pubmed'],
    'biology': ['pubmed'],
    'biomedicine': ['pubmed'],
    'biomedical': ['pubmed'],
    'neuroscience': ['pubmed'],
    'cardiology': ['pubmed'],
    'oncology': ['pubmed'],
    'cancer': ['pubmed'],
    'genomics': ['pubmed'],
    'proteomics': ['pubmed'],
    'immunology': ['pubmed'],
    'pharmacology': ['pubmed'],
    'biochemistry': ['pubmed'],
    'molecular_biology': ['pubmed'],
    'cell_biology': ['pubmed'],
    'pathology': ['pubmed'],
    'physiology': ['pubmed'],
    'anatomy': ['pubmed'],
    'microbiology': ['pubmed'],
    'virology': ['pubmed'],
    'epidemiology': ['pubmed'],
    'public_health': ['pubmed'],
    'clinical_medicine': ['pubmed'],
    'internal_medicine': ['pubmed'],
    'surgery': ['pubmed'],
    'pediatrics': ['pubmed'],
    'obstetrics': ['pubmed'],
    'gynecology': ['pubmed'],
    'psychiatry': ['pubmed'],
    'radiology': ['pubmed'],
    'nuclear_medicine': ['pubmed'],
    'medical_imaging': ['pubmed'],
    'diagnostics': ['pubmed'],
    'therapeutics': ['pubmed'],
    'drug_discovery': ['pubmed'],
    'precision_medicine': ['pubmed'],
    'translational_medicine': ['pubmed'],
    'regenerative_medicine': ['pubmed'],
    'stem_cell': ['pubmed'],
    'gene_therapy': ['pubmed'],
    'alzheimer': ['pubmed'],
    'dementia': ['pubmed'],
    'neurodegenerative': ['pubmed'],
    'stroke': ['pubmed'],
    'cardiovascular': ['pubmed'],
    'heart': ['pubmed'],
    'diabetes': ['pubmed'],
    'obesity': ['pubmed'],
    'metabolism': ['pubmed'],
    'endocrinology': ['pubmed'],
    'nephrology': ['pubmed'],
    'pulmonology': ['pubmed'],
    'respiratory': ['pubmed'],
    'gastroenterology': ['pubmed'],
    'hepatology': ['pubmed'],
    'hematology': ['pubmed'],
    'oncogene': ['pubmed'],
    'tumor': ['pubmed'],
    'cancer_research': ['pubmed'],
    'immunotherapy': ['pubmed'],
    'vaccine': ['pubmed'],
    'antibody': ['pubmed'],
    'protein': ['pubmed'],
    'enzyme': ['pubmed'],
    'rna': ['pubmed'],
    'dna': ['pubmed'],
    'sequencing': ['pubmed'],
    'crispr': ['pubmed'],
    'gene_expression': ['pubmed'],
    'single_cell': ['pubmed'],
    'bioinformatics': ['pubmed', 'arxiv'],
    'computational_biology': ['pubmed', 'arxiv'],

    # ==================== 计算机/物理/数学 → ArXiv + Semantic Scholar ====================
    'computer_science': ['arxiv', 'semantic_scholar'],
    'cs': ['arxiv', 'semantic_scholar'],
    'artificial_intelligence': ['arxiv', 'semantic_scholar', 'pubmed'],
    'ai': ['arxiv', 'semantic_scholar', 'pubmed'],
    'machine_learning': ['arxiv', 'semantic_scholar', 'pubmed'],
    'ml': ['arxiv', 'semantic_scholar', 'pubmed'],
    'deep_learning': ['arxiv', 'semantic_scholar', 'pubmed'],
    'neural_network': ['arxiv', 'semantic_scholar', 'pubmed'],
    'nlp': ['arxiv', 'semantic_scholar'],
    'natural_language_processing': ['arxiv', 'semantic_scholar'],
    'computer_vision': ['arxiv', 'semantic_scholar'],
    'cv': ['arxiv', 'semantic_scholar'],
    'robotics': ['arxiv', 'semantic_scholar'],
    'reinforcement_learning': ['arxiv', 'semantic_scholar'],
    'data_science': ['arxiv', 'semantic_scholar', 'pubmed'],
    'data_mining': ['arxiv', 'semantic_scholar'],
    'big_data': ['arxiv', 'semantic_scholar'],
    'database': ['arxiv', 'semantic_scholar'],
    'software_engineering': ['arxiv', 'semantic_scholar'],
    'programming': ['arxiv', 'semantic_scholar'],
    'algorithm': ['arxiv', 'semantic_scholar'],
    'optimization': ['arxiv', 'semantic_scholar'],
    'distributed_system': ['arxiv', 'semantic_scholar'],
    'cloud_computing': ['arxiv', 'semantic_scholar'],
    'network': ['arxiv', 'semantic_scholar'],
    'security': ['arxiv', 'semantic_scholar'],
    'cybersecurity': ['arxiv', 'semantic_scholar'],
    'blockchain': ['arxiv', 'semantic_scholar'],
    'quantum_computing': ['arxiv', 'semantic_scholar'],
    'physics': ['arxiv', 'semantic_scholar'],
    'quantum_physics': ['arxiv', 'semantic_scholar'],
    'condensed_matter': ['arxiv', 'semantic_scholar'],
    'particle_physics': ['arxiv', 'semantic_scholar'],
    'astrophysics': ['arxiv', 'semantic_scholar'],
    'cosmology': ['arxiv', 'semantic_scholar'],
    'gravitation': ['arxiv', 'semantic_scholar'],
    'thermodynamics': ['arxiv', 'semantic_scholar'],
    'electromagnetism': ['arxiv', 'semantic_scholar'],
    'fluid_mechanics': ['arxiv', 'semantic_scholar'],
    'plasma': ['arxiv', 'semantic_scholar'],
    'optics': ['arxiv', 'semantic_scholar'],
    'photonics': ['arxiv', 'semantic_scholar'],
    'materials_science': ['arxiv', 'semantic_scholar'],
    'nanotechnology': ['arxiv', 'semantic_scholar'],
    'chemistry': ['arxiv', 'semantic_scholar'],
    'chemical_engineering': ['arxiv', 'semantic_scholar'],
    'mathematics': ['arxiv', 'semantic_scholar'],
    'math': ['arxiv', 'semantic_scholar'],
    'statistics': ['arxiv', 'semantic_scholar', 'pubmed'],
    'probability': ['arxiv', 'semantic_scholar'],
    'algebra': ['arxiv', 'semantic_scholar'],
    'geometry': ['arxiv', 'semantic_scholar'],
    'topology': ['arxiv', 'semantic_scholar'],
    'analysis': ['arxiv', 'semantic_scholar'],
    'number_theory': ['arxiv', 'semantic_scholar'],
    'combinatorics': ['arxiv', 'semantic_scholar'],
    'graph_theory': ['arxiv', 'semantic_scholar'],
    'logic': ['arxiv', 'semantic_scholar'],
    'game_theory': ['arxiv', 'semantic_scholar'],
    'information_theory': ['arxiv', 'semantic_scholar'],
    'signal_processing': ['arxiv', 'semantic_scholar'],
    'control_system': ['arxiv', 'semantic_scholar'],
    'electronics': ['arxiv', 'semantic_scholar'],
    'electrical_engineering': ['arxiv', 'semantic_scholar'],
    'mechanical_engineering': ['arxiv', 'semantic_scholar'],
    'civil_engineering': ['arxiv', 'semantic_scholar'],
    'aerospace': ['arxiv', 'semantic_scholar'],

    # ==================== 社会科学 → Semantic Scholar ====================
    'psychology': ['semantic_scholar', 'pubmed'],
    'cognitive_science': ['semantic_scholar', 'pubmed'],
    'behavioral_science': ['semantic_scholar', 'pubmed'],
    'economics': ['semantic_scholar'],
    'finance': ['semantic_scholar'],
    'business': ['semantic_scholar'],
    'management': ['semantic_scholar'],
    'marketing': ['semantic_scholar'],
    'sociology': ['semantic_scholar'],
    'anthropology': ['semantic_scholar'],
    'political_science': ['semantic_scholar'],
    'law': ['semantic_scholar'],
    'history': ['semantic_scholar'],
    'philosophy': ['semantic_scholar'],
    'linguistics': ['semantic_scholar', 'arxiv'],
    'education': ['semantic_scholar'],
    'communication': ['semantic_scholar'],
    'media': ['semantic_scholar'],
    'journalism': ['semantic_scholar'],
    'geography': ['semantic_scholar'],
    'environmental_science': ['semantic_scholar', 'pubmed'],
    'climate': ['semantic_scholar', 'arxiv'],
    'urban_planning': ['semantic_scholar'],
    'architecture': ['semantic_scholar'],
    'design': ['semantic_scholar'],
    'art': ['semantic_scholar'],
    'music': ['semantic_scholar'],
    'literature': ['semantic_scholar'],
    'cultural_studies': ['semantic_scholar'],

    # ==================== 默认 ====================
    'default': ['pubmed', 'semantic_scholar'],
    'unknown': ['pubmed', 'semantic_scholar'],
}


# ==================== 领域关键词检测规则 ====================

DOMAIN_KEYWORDS = {
    # 医学关键词
    'medicine': [
        'clinical', 'patient', 'disease', 'treatment', 'therapy', 'diagnosis',
        'medical', 'hospital', 'doctor', 'medicine', 'drug', 'pharmaceutical',
        'health', 'healthcare', 'symptom', 'prognosis', 'mortality',
        'alzheimer', 'dementia', 'cancer', 'tumor', 'stroke', 'diabetes',
        'cardiovascular', 'neurological', 'psychiatric', 'infection',
    ],
    'biology': [
        'cell', 'protein', 'gene', 'dna', 'rna', 'molecular', 'biochemistry',
        'genomics', 'proteomics', 'metabolomics', 'transcriptomics',
        'organism', 'species', 'evolution', 'mutation', 'expression',
        'pathway', 'signaling', 'receptor', 'enzyme', 'chromosome',
    ],
    'neuroscience': [
        'brain', 'neuron', 'neural', 'cortex', 'hippocampus', 'synaptic',
        'cognitive', 'memory', 'learning', 'neuroplasticity', 'neurodegeneration',
        'fmri', 'eeg', 'neuroimaging', 'neurotransmitter', 'dopamine',
    ],
    'genomics': [
        'genome', 'genomic', 'sequencing', 'wgs', 'wga', 'gwas', 'snp',
        'variant', 'mutation', 'allele', 'chromosome', 'inheritance',
        'genotype', 'phenotype', 'heritability', 'polygenic',
    ],
    'immunology': [
        'immune', 'immunology', 'antibody', 'antigen', 'lymphocyte',
        't-cell', 'b-cell', 'cytokine', 'inflammation', 'autoimmune',
        'vaccine', 'immunotherapy', 'immune_response',
    ],

    # 计算机关键词
    'computer_science': [
        'algorithm', 'software', 'hardware', 'programming', 'code',
        'database', 'network', 'system', 'architecture', 'framework',
        'api', 'interface', 'backend', 'frontend', 'deployment',
    ],
    'ai': [
        'artificial intelligence', 'machine learning', 'deep learning',
        'neural network', 'transformer', 'attention', 'embedding',
        'classification', 'regression', 'clustering', 'prediction',
        'training', 'inference', 'model', 'optimization', 'gradient',
    ],
    'nlp': [
        'natural language', 'text', 'sentence', 'word', 'token',
        'language model', 'translation', 'sentiment', 'summarization',
        'question answering', 'dialogue', 'chatbot', 'speech',
    ],
    'computer_vision': [
        'image', 'video', 'pixel', 'object detection', 'segmentation',
        'recognition', 'classification', 'tracking', '3d', 'rendering',
        'camera', 'visual', 'scene', 'texture',
    ],

    # 物理关键词
    'physics': [
        'quantum', 'particle', 'wave', 'energy', 'force', 'field',
        'matter', 'mass', 'velocity', 'acceleration', 'momentum',
        'photon', 'electron', 'atom', 'nucleus', 'radiation',
    ],

    # 数学关键词
    'mathematics': [
        'theorem', 'proof', 'equation', 'function', 'variable',
        'matrix', 'vector', 'tensor', 'derivative', 'integral',
        'polynomial', 'series', 'limit', 'convergence', 'algorithm',
    ],

    # 社会科学关键词
    'psychology': [
        'behavior', 'cognitive', 'emotion', 'perception', 'memory',
        'motivation', 'personality', 'social', 'psychological',
        'mental', 'stress', 'anxiety', 'depression',
    ],
    'economics': [
        'market', 'price', 'supply', 'demand', 'trade', 'investment',
        'gdp', 'inflation', 'employment', 'growth', 'policy', 'economic',
    ],
}


# ==================== 路由结果数据类 ====================

class DataSource(Enum):
    """数据源类型"""
    PUBMED = "pubmed"
    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CROSSREF = "crossref"
    GOOGLE_SCHOLAR = "google_scholar"


@dataclass
class RoutingResult:
    """
    路由决策结果

    包含领域检测结果和数据源选择
    """
    domain: str                              # 检测到的领域
    sources: List[str]                       # 选择的数据源
    routing_reason: str                      # 路由理由
    confidence: float = 1.0                  # 路由置信度
    detected_keywords: List[str] = field(default_factory=list)  # 检测到的关键词
    user_domain_match: bool = True           # 是否匹配用户提供的领域
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'domain': self.domain,
            'sources': self.sources,
            'routing_reason': self.routing_reason,
            'confidence': self.confidence,
            'detected_keywords': self.detected_keywords,
            'user_domain_match': self.user_domain_match,
            'timestamp': self.timestamp,
        }

    def get_source_config_text(self) -> str:
        """
        生成数据源配置文本

        用于 PI Prompt 的 {DATA_SOURCE_CONFIG} 插槽
        """
        source_descriptions = {
            'pubmed': 'PubMed (医学/生命科学文献数据库) - 使用 PMID 引用格式',
            'arxiv': 'ArXiv (计算机/物理/数学预印本) - 使用 arXiv:xxx 引用格式',
            'semantic_scholar': 'Semantic Scholar (全学科学术搜索) - 使用 DOI 引用格式',
        }

        lines = []
        for source in self.sources:
            desc = source_descriptions.get(source, source)
            lines.append(f"- {desc}")

        return "\n".join(lines)


@dataclass
class SearchRequest:
    """
    搜索请求

    封装用户输入和路��结果
    """
    query: str                               # 搜索关键词
    domain: str                              # 学科领域
    sources: List[str]                       # 数据源列表
    max_results: int = 20                    # 每个数据源最大结果数
    filters: Dict = field(default_factory=dict)  # 过滤条件
    routing_result: RoutingResult = None     # 路由结果


@dataclass
class SearchResult:
    """
    搜索结果

    来自多个数据源的聚合结果
    """
    source: str                              # 数据源
    success: bool                            # 是否成功
    papers: List[Dict] = field(default_factory=list)  # 文献列表
    total_count: int = 0                     # 总数量
    error: str = None                        # 错误信息
    query_used: str = None                   # 实际使用的查询
    time_elapsed: float = 0.0                # 耗时


@dataclass
class AggregatedSearchResults:
    """
    聚合搜索结果

    来自所有数据源的合并结果
    """
    domain: str                              # 学科领域
    results_by_source: Dict[str, SearchResult] = field(default_factory=dict)
    all_papers: List[Dict] = field(default_factory=list)  # 合并后的所有文献
    verified_ids: Dict[str, List[str]] = field(default_factory=dict)  # 验证过的ID
    total_papers: int = 0                    # 总文献数
    search_time: float = 0.0                 # 总搜索时间
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'domain': self.domain,
            'results_by_source': {k: v for k, v in self.results_by_source.items()},
            'all_papers': self.all_papers,
            'verified_ids': self.verified_ids,
            'total_papers': self.total_papers,
            'search_time': self.search_time,
            'timestamp': self.timestamp,
        }


# ==================== 动态 RAG 路由器 ====================

class DynamicRAGRouter:
    """
    动态数据源路由器

    根据 {USER_DOMAIN} 自动选择最佳检索 API

    核心功能：
    1. 领域自动检测
    2. 数据源智能路由
    3. 异步并发检索
    4. 结果聚合
    """

    def __init__(
        self,
        max_concurrent_searches: int = 4,
        default_max_results: int = 20,
        enable_auto_detect: bool = True,
        # V7.1: 新增超时和优先级配置
        enable_timeout_control: bool = True,
        global_timeout: float = 60.0,
        enable_priority_queue: bool = True,
        enable_fallback: bool = True,
    ):
        """
        初始化路由器

        V7.1 新增参数：
        - enable_timeout_control: 是否启用统一超时控制
        - global_timeout: 全局最大超时时间（秒）
        - enable_priority_queue: 是否启用优先级队列
        - enable_fallback: 是否启用降级策略

        Args:
            max_concurrent_searches: 最大并发检索数
            default_max_results: 默认每个数据源最大结果数
            enable_auto_detect: 是否启用领域自动检测
        """
        self.max_concurrent = max_concurrent_searches
        self.default_max_results = default_max_results
        self.enable_auto_detect = enable_auto_detect

        # V7.1: 超时和优先级配置
        self.enable_timeout_control = enable_timeout_control
        self.global_timeout = global_timeout
        self.enable_priority_queue = enable_priority_queue
        self.enable_fallback = enable_fallback

        # 数据源适配器（延迟加载）
        self._searchers = {}

        # V7.1: 超时追踪
        self._timeout_stats: Dict[str, int] = {}

        logger.info(
            f"[DynamicRAGRouter V7.1] 初始化完成\n"
            f"  并发数: {self.max_concurrent}\n"
            f"  超时控制: {self.enable_timeout_control}\n"
            f"  全局超时: {self.global_timeout}秒\n"
            f"  优先级队列: {self.enable_priority_queue}\n"
            f"  降级策略: {self.enable_fallback}"
        )

    def _get_source_timeout(self, source: str) -> float:
        """
        V7.1: 获取数据源超时时间

        Args:
            source: 数据源名称

        Returns:
            float: 超时时间（秒）
        """
        return SOURCE_TIMEOUT_CONFIG.get(source, SOURCE_TIMEOUT_CONFIG['default'])

    def _get_source_priority(self, source: str) -> SourcePriority:
        """
        V7.1: 获取数据源优先级

        Args:
            source: 数据源名称

        Returns:
            SourcePriority: 优先级级别
        """
        return SOURCE_PRIORITY_CONFIG.get(source, SourcePriority.SECONDARY)

    def _get_fallback_sources(self, source: str) -> List[str]:
        """
        V7.1: 获取降级数据源列表

        Args:
            source: 原数据源名称

        Returns:
            List[str]: 降级数据源列表
        """
        return FALLBACK_SOURCE_MAPPING.get(source, [])

    def _get_searcher(self, source: str) -> Any:
        """
        获取数据源适配器（延迟加载）

        Args:
            source: 数据源名称

        Returns:
            数据源搜索器实例
        """
        if source not in self._searchers:
            try:
                if source == 'pubmed':
                    from src.utils.pubmed import PubMedSearcher
                    self._searchers[source] = PubMedSearcher()

                elif source == 'arxiv':
                    from src.data_sources.arxiv_searcher import ArXivSearcher
                    self._searchers[source] = ArXivSearcher()

                elif source == 'semantic_scholar':
                    from src.data_sources.semantic_scholar_searcher import SemanticScholarSearcher
                    self._searchers[source] = SemanticScholarSearcher()

                else:
                    logger.warning(f"Unknown data source: {source}")
                    return None

            except ImportError as e:
                logger.warning(f"Data source {source} not available: {e}")
                return None

        return self._searchers.get(source)

    def route(
        self,
        user_input: str,
        user_domain: str = None,
    ) -> RoutingResult:
        """
        路由决策

        Args:
            user_input: 用户研究想法
            user_domain: 用户学科领域（可选，自动检测）

        Returns:
            RoutingResult: 包含数据源列表和路由理由
        """
        # 1. 领域检测
        detected_domain = user_domain
        detected_keywords = []

        if not user_domain or self.enable_auto_detect:
            detected_domain, detected_keywords = self._detect_domain(user_input)

        # 检查是否匹配用户提供的领域
        user_domain_match = True
        if user_domain and detected_domain != user_domain:
            # 如果用户提供了领域，但检测结果不同
            # 优先使用用户提供的领域，但记录不匹配
            detected_domain = user_domain
            user_domain_match = False

        # 2. 数据源选择
        sources = DOMAIN_SOURCE_MAPPING.get(detected_domain.lower(), DOMAIN_SOURCE_MAPPING['default'])

        # 3. 构建路由理由
        routing_reason = self._get_routing_reason(detected_domain, sources)

        # 4. 计���置信度
        confidence = 1.0 if detected_keywords else 0.8

        return RoutingResult(
            domain=detected_domain,
            sources=sources,
            routing_reason=routing_reason,
            confidence=confidence,
            detected_keywords=detected_keywords,
            user_domain_match=user_domain_match,
        )

    def _detect_domain(self, user_input: str) -> Tuple[str, List[str]]:
        """
        自动检测学科领域

        Args:
            user_input: 用户输入文本

        Returns:
            Tuple[str, List[str]]: (检测到的领域, 匹配的关键词列表)
        """
        user_input_lower = user_input.lower()

        best_domain = 'default'
        best_keywords = []
        best_score = 0

        for domain, keywords in DOMAIN_KEYWORDS.items():
            matched_keywords = []
            score = 0

            for keyword in keywords:
                # 检查关键词是否出现
                if keyword.lower() in user_input_lower:
                    matched_keywords.append(keyword)
                    score += 1

            # 更新最佳匹配
            if score > best_score:
                best_score = score
                best_domain = domain
                best_keywords = matched_keywords

        logger.info(f"[RAG Router] Detected domain: {best_domain} (score={best_score})")
        logger.info(f"[RAG Router] Matched keywords: {best_keywords}")

        return best_domain, best_keywords

    def _get_routing_reason(self, domain: str, sources: List[str]) -> str:
        """
        生成路由理由说明

        Args:
            domain: 学科领域
            sources: 数据源列表

        Returns:
            str: 路由理由
        """
        reasons = []

        # 医学/生命科学
        if domain in ['medicine', 'biology', 'neuroscience', 'genomics', 'immunology',
                      'cardiology', 'oncology', 'pharmacology', 'biochemistry']:
            reasons.append(f"学科领域 '{domain}' 属于医学/生命科学范畴")
            reasons.append("PubMed 是最权威的生物医学文献数据库")

        # 计算机/物理
        elif domain in ['computer_science', 'ai', 'machine_learning', 'physics',
                        'mathematics', 'nlp', 'computer_vision']:
            reasons.append(f"学科领域 '{domain}' 属于计算机/物理/数学范畴")
            reasons.append("ArXiv 是计算机和物理预印本的主要来源")
            reasons.append("Semantic Scholar 提供广泛的学术文献覆盖")

        # 社会科学
        elif domain in ['psychology', 'economics', 'sociology', 'education']:
            reasons.append(f"学科领域 '{domain}' 属于社会科学范畴")
            reasons.append("Semantic Scholar 提供全学科学术搜索")

        else:
            reasons.append(f"学科领域 '{domain}' 未明确分类")
            reasons.append("使用混合数据源策略确保文献覆盖")

        # 添加数据源说明
        reasons.append(f"选择数据源: {', '.join(sources)}")

        return " | ".join(reasons)

    def search(
        self,
        query: str,
        routing_result: RoutingResult = None,
        user_domain: str = None,
        max_results: int = None,
    ) -> AggregatedSearchResults:
        """
        同步搜索（兼容模式）

        Args:
            query: 搜索关键词
            routing_result: 路由结果（可选，自动路由）
            user_domain: 学科领域（可选）
            max_results: 最大结果数

        Returns:
            AggregatedSearchResults: 聚合搜索结果
        """
        # 如果没有路由结果，执行路由
        if not routing_result:
            routing_result = self.route(query, user_domain)

        max_results = max_results or self.default_max_results

        results = AggregatedSearchResults(
            domain=routing_result.domain,
        )

        # 按数据源搜��
        for source in routing_result.sources:
            searcher = self._get_searcher(source)

            if searcher:
                try:
                    logger.info(f"[RAG Router] Searching {source} with query: {query}")

                    # 调用搜索器
                    if source == 'pubmed':
                        papers = searcher.search_papers(query, max_results=max_results)
                    else:
                        papers = searcher.search(query, max_results=max_results)

                    result = SearchResult(
                        source=source,
                        success=True,
                        papers=papers,
                        total_count=len(papers),
                        query_used=query,
                    )

                    # 收集验证 ID
                    for paper in papers:
                        if source == 'pubmed' and paper.get('pmid'):
                            results.verified_ids.setdefault('pmids', []).append(paper['pmid'])
                        elif source == 'arxiv' and paper.get('arxiv_id'):
                            results.verified_ids.setdefault('arxiv_ids', []).append(paper['arxiv_id'])
                        elif paper.get('doi'):
                            results.verified_ids.setdefault('dois', []).append(paper['doi'])

                except Exception as e:
                    logger.error(f"[RAG Router] Search {source} failed: {e}")
                    result = SearchResult(
                        source=source,
                        success=False,
                        error=str(e),
                        query_used=query,
                    )

                results.results_by_source[source] = result

        # 合合所有文献
        for source_result in results.results_by_source.values():
            if source_result.success:
                results.all_papers.extend(source_result.papers)

        results.total_papers = len(results.all_papers)

        logger.info(f"[RAG Router] Total papers found: {results.total_papers}")
        logger.info(f"[RAG Router] Verified IDs: {sum(len(v) for v in results.verified_ids.values())}")

        return results

    async def search_async(
        self,
        query: str,
        routing_result: RoutingResult = None,
        user_domain: str = None,
        max_results: int = None,
    ) -> AggregatedSearchResults:
        """
        V7.1 异步并发搜索（RLCRL漏洞修复）

        新增机制：
        1. 统一超时控制：每个数据源设置超时限制
        2. 优先级队列：PRIMARY 数据源优先，SECONDARY 可超时跳过
        3. 降级策略：PRIMARY 失败时自动切换 FALLBACK
        4. 部分结果返回：即使超时也返回已获取结果

        Args:
            query: 搜索关键词
            routing_result: 路由结果（可选，自动路由）
            user_domain: 学科领域（可选）
            max_results: 最大结果数

        Returns:
            AggregatedSearchResults: 聚合搜索结果
        """
        start_time = datetime.now()

        # 如果没有路由结果，执行路由
        if not routing_result:
            routing_result = self.route(query, user_domain)

        max_results = max_results or self.default_max_results

        results = AggregatedSearchResults(
            domain=routing_result.domain,
        )

        # V7.1: 按优先级分组数据源
        if self.enable_priority_queue:
            primary_sources = []
            secondary_sources = []
            fallback_sources = []

            for source in routing_result.sources:
                priority = self._get_source_priority(source)
                if priority == SourcePriority.PRIMARY:
                    primary_sources.append(source)
                elif priority == SourcePriority.SECONDARY:
                    secondary_sources.append(source)
                else:
                    fallback_sources.append(source)

            # 搜索顺序：PRIMARY → SECONDARY → FALLBACK
            ordered_sources = primary_sources + secondary_sources + fallback_sources
        else:
            ordered_sources = routing_result.sources

        # V7.1: 创建带超时控制的并发搜索任务
        semaphore = asyncio.Semaphore(self.max_concurrent)
        failed_primary_sources = []  # 记录失败的 PRIMARY 数据源

        async def limited_search_with_timeout(source: str):
            """V7.1: 带超时控制的搜索（深水区网络请求）"""
            async with semaphore:
                timeout = self._get_source_timeout(source) if self.enable_timeout_control else self.global_timeout

                try:
                    # 使用 asyncio.wait_for 添加超时控制
                    result = await asyncio.wait_for(
                        self._search_single_source_async(source, query, max_results),
                        timeout=timeout
                    )
                    return source, result, None

                except asyncio.TimeoutError:
                    # V7.1: 超时处理 - 记录完整信息
                    self._timeout_stats[source] = self._timeout_stats.get(source, 0) + 1
                    logger.warning(
                        f"[RAG Router] {source} 搜索超时 ({timeout}秒)\n"
                        f"  优先级: {self._get_source_priority(source).value}\n"
                        f"  累计超时次数: {self._timeout_stats[source]}\n"
                        f"  查询: {query[:50]}..."
                    )

                    # 如果是 PRIMARY 数据源，记录失败以便后续降级
                    if self._get_source_priority(source) == SourcePriority.PRIMARY:
                        failed_primary_sources.append(source)

                    return source, None, f"Timeout after {timeout}s"

                except Exception as e:
                    # V7.1: 深水区异常捕获 - 记录完整堆栈和关键变量
                    logger.exception(
                        f"[RAG Router] {source} 搜索异常（深水区网络请求）",
                        extra_vars={
                            'source': source,
                            'query': query[:100],
                            'max_results': max_results,
                            'timeout': timeout,
                            'priority': self._get_source_priority(source).value,
                            'exception_type': type(e).__name__
                        }
                    )
                    if self._get_source_priority(source) == SourcePriority.PRIMARY:
                        failed_primary_sources.append(source)
                    return source, None, str(e)

        # V7.1: 并发执行所有数据源搜索（带全局超时）
        tasks = [limited_search_with_timeout(source) for source in ordered_sources]

        try:
            # 全局超时控制
            search_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=False),
                timeout=self.global_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"[RAG Router V7.1] 全局超时触发 ({self.global_timeout}秒)")
            # 获取已完成的结果
            search_results = []
            for task in tasks:
                if task.done() and not task.cancelled():
                    try:
                        search_results.append(task.result())
                    except Exception:
                        pass

        # 处理结果
        for source, result, error in search_results:
            if result is not None and isinstance(result, SearchResult):
                results.results_by_source[source] = result

                # 收集验证 ID
                if result.success:
                    for paper in result.papers:
                        if source == 'pubmed' and paper.get('pmid'):
                            results.verified_ids.setdefault('pmids', []).append(paper['pmid'])
                        elif source == 'arxiv' and paper.get('arxiv_id'):
                            results.verified_ids.setdefault('arxiv_ids', []).append(paper['arxiv_id'])
                        elif paper.get('doi'):
                            results.verified_ids.setdefault('dois', []).append(paper['doi'])

            elif error is not None:
                results.results_by_source[source] = SearchResult(
                    source=source,
                    success=False,
                    error=error,
                    query_used=query,
                )

        # V7.1: 降级策略 - PRIMARY 失败时尝试 FALLBACK
        if self.enable_fallback and failed_primary_sources:
            logger.info(f"[RAG Router V7.1] PRIMARY 数据源失败: {failed_primary_sources}, 尝试降级")

            for failed_source in failed_primary_sources:
                fallback_sources = self._get_fallback_sources(failed_source)
                for fallback_source in fallback_sources:
                    if fallback_source not in results.results_by_source:
                        try:
                            fallback_result = await asyncio.wait_for(
                                self._search_single_source_async(fallback_source, query, max_results),
                                timeout=self._get_source_timeout(fallback_source)
                            )
                            if fallback_result.success:
                                results.results_by_source[fallback_source] = fallback_result
                                results.all_papers.extend(fallback_result.papers)
                                logger.info(f"[RAG Router V7.1] 降级成功: {failed_source} → {fallback_source}")
                        except Exception as e:
                            logger.warning(f"[RAG Router V7.1] 降级失败: {fallback_source}, {e}")

        # 合并所有文献
        for source_result in results.results_by_source.values():
            if source_result.success:
                results.all_papers.extend(source_result.papers)

        results.total_papers = len(results.all_papers)
        results.search_time = (datetime.now() - start_time).total_seconds()

        logger.info(
            f"[RAG Router V7.1] 搜索完成\n"
            f"  总文献数: {results.total_papers}\n"
            f"  成功数据源: {sum(1 for r in results.results_by_source.values() if r.success)}\n"
            f"  搜索耗时: {results.search_time:.2f}秒\n"
            f"  验证ID数: {sum(len(v) for v in results.verified_ids.values())}"
        )

        return results

    async def _search_single_source_async(
        self,
        source: str,
        query: str,
        max_results: int,
    ) -> SearchResult:
        """
        异步搜索单个数据源

        Args:
            source: 数据源名称
            query: 搜索关键词
            max_results: 最大结果数

        Returns:
            SearchResult: 搜索结果
        """
        searcher = self._get_searcher(source)

        if not searcher:
            return SearchResult(
                source=source,
                success=False,
                error=f"Data source {source} not available",
                query_used=query,
            )

        try:
            # 检查是否支持异步搜索
            if hasattr(searcher, 'search_async'):
                papers = await searcher.search_async(query, max_results=max_results)
            else:
                # 回退到同步搜索
                papers = searcher.search(query, max_results=max_results)

            return SearchResult(
                source=source,
                success=True,
                papers=papers,
                total_count=len(papers),
                query_used=query,
            )

        except Exception as e:
            logger.error(f"[RAG Router] Search {source} error: {e}")
            return SearchResult(
                source=source,
                success=False,
                error=str(e),
                query_used=query,
            )


# ==================== 便捷函数 ====================

def route_query(user_input: str, user_domain: str = None) -> RoutingResult:
    """
    快捷路由函数

    Args:
        user_input: 用户研究想法
        user_domain: 学科领域（可选）

    Returns:
        RoutingResult: 路由结果
    """
    router = DynamicRAGRouter()
    return router.route(user_input, user_domain)


def search_multi_source(
    query: str,
    user_domain: str = None,
    max_results: int = 20,
) -> AggregatedSearchResults:
    """
    快捷多源搜索函数

    Args:
        query: 搜索关键词
        user_domain: 学科领域（可选）
        max_results: 最大结果数

    Returns:
        AggregatedSearchResults: 聚合搜索结果
    """
    router = DynamicRAGRouter()
    return router.search(query, user_domain=user_domain, max_results=max_results)


async def search_multi_source_async(
    query: str,
    user_domain: str = None,
    max_results: int = 20,
) -> AggregatedSearchResults:
    """
    快捷异步多源搜索函数

    Args:
        query: 搜索关键词
        user_domain: 学科领域（可选）
        max_results: 最大结果数

    Returns:
        AggregatedSearchResults: 聚合搜索结果
    """
    router = DynamicRAGRouter()
    return await router.search_async(query, user_domain=user_domain, max_results=max_results)


# ==================== 测试 ====================

if __name__ == '__main__':
    print("=" * 60)
    print("V6.0 动态 RAG 路由器 - 测试")
    print("=" * 60)

    router = DynamicRAGRouter()

    # 测试路由决策
    test_cases = [
        ("阿尔茨海默病患者海马体萎缩与认知功能下降的关系", None),
        ("基于深度学习的图像分类算法优化", None),
        ("Transformer模型在自然语言处理中的应用", None),
        ("量子计算在密码学中的应用研究", None),
        ("宏观经济政策对就业的影响分析", None),
    ]

    for query, domain in test_cases:
        print(f"\n输入: {query}")
        result = router.route(query, domain)
        print(f"领域: {result.domain}")
        print(f"数据源: {result.sources}")
        print(f"理由: {result.routing_reason}")
        print(f"关键词: {result.detected_keywords}")

    print("\n" + "=" * 60)
    print("测试完成")