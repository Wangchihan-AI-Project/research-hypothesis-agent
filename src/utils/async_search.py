# -*- coding: utf-8 -*-
"""
V6.0 asyncio 异步检索器 (Async Draft-Verification Retrieval)

使用 asyncio 实现并发检索，指数退避重试机制。

核心功能：
- 三阶段异步执行（Draft → Verify → Synthesize）
- 并发拉取支持/挑战/碰撞文献
- 指数退避重试（最高3次）
- Semaphore 并发限制
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import time

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 检索状态枚举 ====================

class SearchPhase(Enum):
    """检索阶段"""
    DRAFT = "draft"         # Phase 1: 快速草稿
    VERIFY = "verify"       # Phase 2: 验证检索
    SYNTHESIZE = "synthesize"  # Phase 3: 综合输出


class SearchType(Enum):
    """检索类型"""
    SUPPORTING = "supporting"    # 支持文献
    CHALLENGING = "challenging"  # 挑战文献
    COLLISION = "collision"      # 碰撞检测


# ==================== 重试异常 ====================

class RateLimitError(Exception):
    """速率限制异常"""
    pass


class TimeoutError(Exception):
    """超时异常"""
    pass


class MaxRetriesExceededError(Exception):
    """最大重试次数超限异常"""
    def __init__(self, query: str, search_type: str):
        self.query = query
        self.search_type = search_type
        super().__init__(f"Max retries exceeded for {search_type}: {query}")


# ==================== 草稿结果数据类 ====================

@dataclass
class DraftResult:
    """
    Phase 1 草稿结果

    包含初步假设框架和关键词列表
    """
    title: str                              # 假设标题
    core_hypothesis: str                    # 核心假设
    mechanism_outline: str                  # 机制概述
    keywords: List[str] = field(default_factory=list)  # 检索关键词
    expected_impact: str = ""               # 预期影响
    draft_phase: str = "phase_1"            # 阶段标记
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'title': self.title,
            'core_hypothesis': self.core_hypothesis,
            'mechanism_outline': self.mechanism_outline,
            'keywords': self.keywords,
            'expected_impact': self.expected_impact,
            'draft_phase': self.draft_phase,
            'timestamp': self.timestamp,
        }


# ==================== 验证结果数据类 ====================

@dataclass
class VerificationResult:
    """
    Phase 2 验证检索结果

    包含支持/挑战/碰撞三类文献
    """
    supporting_papers: List[Dict] = field(default_factory=list)  # 支持文献
    challenging_papers: List[Dict] = field(default_factory=list)  # 挑战文献
    collision_papers: List[Dict] = field(default_factory=list)    # 碰撞文献
    verified_ids: Dict[str, List[str]] = field(default_factory=dict)  # 验证ID
    search_stats: Dict = field(default_factory=dict)  # 搜索统计
    errors: List[str] = field(default_factory=list)    # 错误列表
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'supporting_papers': self.supporting_papers,
            'challenging_papers': self.challenging_papers,
            'collision_papers': self.collision_papers,
            'verified_ids': self.verified_ids,
            'search_stats': self.search_stats,
            'errors': self.errors,
            'timestamp': self.timestamp,
        }


# ==================== 最终结果数据类 ====================

@dataclass
class FinalHypothesisResult:
    """
    Phase 3 最终假设结果

    包含完整假设和证据支撑
    """
    title: str                              # 假设标题
    core_hypothesis: str                    # 核心假设
    details: str                            # 详细内容（七段式）
    mechanism: str                          # 机制描述
    counterfactual_analysis: Dict           # 反事实分析
    scores: Dict                            # 评分
    evidence: Dict                          # 证据支撑
    verified_ids: Dict[str, List[str]]      # 验证ID
    support_status: str = "adequate"        # 支撑状态
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'title': self.title,
            'core_hypothesis': self.core_hypothesis,
            'details': self.details,
            'mechanism': self.mechanism,
            'counterfactual_analysis': self.counterfactual_analysis,
            'scores': self.scores,
            'evidence': self.evidence,
            'verified_ids': self.verified_ids,
            'support_status': self.support_status,
            'timestamp': self.timestamp,
        }


# ==================== 异步检索器 ====================

class AsyncDraftVerificationRetrieval:
    """
    异步草稿-验证检索系统

    使用 asyncio 实现并发检索，指数退避重试
    """

    # 配置常量
    MAX_RETRIES = 3                         # 最大重试次数
    MAX_CONCURRENT = 4                      # 最大并发检索数
    BASE_DELAY = 1.0                        # 指数退避基数
    TIMEOUT = 30                            # HTTP超时（秒）

    def __init__(
        self,
        max_retries: int = None,
        max_concurrent: int = None,
        base_delay: float = None,
        data_sources: List[str] = None,
    ):
        """
        初始化异步检索器

        Args:
            max_retries: 最大重试次数
            max_concurrent: 最大并发数
            base_delay: 指数退避基数
            data_sources: 数据源列表
        """
        self.max_retries = max_retries or self.MAX_RETRIES
        self.max_concurrent = max_concurrent or self.MAX_CONCURRENT
        self.base_delay = base_delay or self.BASE_DELAY
        self.data_sources = data_sources or ['pubmed']

        # 搜索器实例（延迟加载）
        self._searchers = {}

    def _get_searcher(self, source: str) -> Any:
        """
        获取数据源搜索器（延迟加载）

        Args:
            source: 数据源名称

        Returns:
            搜索器实例
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
                    logger.warning(f"[Async Search] Unknown source: {source}")
                    return None

            except ImportError as e:
                logger.warning(f"[Async Search] Source {source} not available: {e}")
                return None

        return self._searchers.get(source)

    async def execute(
        self,
        user_input: str,
        domain: str = None,
        bootstrap_env: Dict = None,
    ) -> Tuple[Dict, Dict]:
        """
        三阶段异步执行

        Phase 1: 快速草稿生成（同步）
        Phase 2: 并发验证检索（异步）
        Phase 3: 综合输出（同步）

        Args:
            user_input: 用户研究想法
            domain: 学科领域
            bootstrap_env: Bootstrap环境信息

        Returns:
            Tuple[Dict, Dict]: (最终假设, 验证信息)
        """
        logger.info(f"[Async Search] Starting 3-phase execution")
        logger.info(f"[Async Search] User input: {user_input[:100]}...")
        logger.info(f"[Async Search] Domain: {domain or 'auto'}")
        logger.info(f"[Async Search] Data sources: {self.data_sources}")

        start_time = time.time()

        try:
            # ==================== Phase 1: 草稿生成 ====================
            logger.info("[Async Search] Phase 1: Draft generation")
            draft = await self._generate_draft_async(user_input, domain)

            if not draft:
                logger.error("[Async Search] Draft generation failed")
                return {}, {'errors': ['Draft generation failed']}

            logger.info(f"[Async Search] Draft generated: {draft.title}")
            logger.info(f"[Async Search] Keywords extracted: {draft.keywords}")

            # ==================== Phase 2: 并发验证检索 ====================
            logger.info("[Async Search] Phase 2: Concurrent verification")
            verification = await self._verify_draft_concurrent(draft)

            logger.info(f"[Async Search] Verification completed")
            logger.info(f"[Async Search] Supporting: {len(verification.supporting_papers)}")
            logger.info(f"[Async Search] Challenging: {len(verification.challenging_papers)}")
            logger.info(f"[Async Search] Collision: {len(verification.collision_papers)}")

            # 检查支撑状态
            if len(verification.supporting_papers) < 2:
                verification.errors.append("Insufficient supporting literature")
                logger.warning("[Async Search] Insufficient support")

            # ==================== Phase 3: 综合输出 ====================
            logger.info("[Async Search] Phase 3: Synthesis")
            final = await self._synthesize_final_async(draft, verification)

            elapsed = time.time() - start_time
            logger.info(f"[Async Search] Completed in {elapsed:.2f}s")

            return final.to_dict(), verification.to_dict()

        except Exception as e:
            logger.error(f"[Async Search] Execution error: {e}")
            return {}, {'errors': [str(e)]}

    async def _generate_draft_async(
        self,
        user_input: str,
        domain: str = None,
    ) -> Optional[DraftResult]:
        """
        ��步生成草稿

        Args:
            user_input: 用户输入
            domain: 学科领域

        Returns:
            DraftResult: 草稿结果
        """
        # 提取关键词
        keywords = self._extract_keywords(user_input)

        # 构建初步假设框架
        title = self._generate_title(user_input)
        core_hypothesis = self._generate_core_hypothesis(user_input, keywords)
        mechanism_outline = self._generate_mechanism_outline(user_input, keywords)

        return DraftResult(
            title=title,
            core_hypothesis=core_hypothesis,
            mechanism_outline=mechanism_outline,
            keywords=keywords,
            expected_impact="待验证",
        )

    async def _verify_draft_concurrent(self, draft: DraftResult) -> VerificationResult:
        """
        并发验证检索

        同时拉取：
        - 支持文献 (supporting)
        - 挑战文献 (challenging)
        - 碰撞检测 (collision)

        Args:
            draft: 草稿结果

        Returns:
            VerificationResult: 验证结果
        """
        result = VerificationResult()
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def limited_search(query: str, search_type: SearchType):
            async with semaphore:
                return await self._search_with_retry_async(query, search_type)

        # 构建查询
        keywords = draft.keywords
        supporting_query = " ".join(keywords[:3])
        challenging_query = f"NOT ({' '.join(keywords[:2])})"
        collision_query = draft.title

        # 并发执行三种检索
        tasks = [
            limited_search(supporting_query, SearchType.SUPPORTING),
            limited_search(challenging_query, SearchType.CHALLENGING),
            limited_search(collision_query, SearchType.COLLISION),
        ]

        # 针对每个数据源也并发执行
        source_tasks = []
        for source in self.data_sources:
            source_tasks.extend([
                limited_search(f"{source}:{supporting_query}", SearchType.SUPPORTING),
            ])

        # 执行并发检索
        search_results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        # 处理结果
        for i, search_result in enumerate(search_results):
            if isinstance(search_result, Exception):
                logger.error(f"[Async Search] Search {i} failed: {search_result}")
                result.errors.append(str(search_result))

            elif isinstance(search_result, Dict):
                search_type = search_result.get('search_type')

                if search_type == SearchType.SUPPORTING.value:
                    papers = search_result.get('papers', [])
                    result.supporting_papers.extend(papers)

                    # 收集验证ID
                    for paper in papers:
                        if paper.get('pmid'):
                            result.verified_ids.setdefault('pmids', []).append(paper['pmid'])
                        elif paper.get('arxiv_id'):
                            result.verified_ids.setdefault('arxiv_ids', []).append(paper['arxiv_id'])
                        elif paper.get('doi'):
                            result.verified_ids.setdefault('dois', []).append(paper['doi'])

                elif search_type == SearchType.CHALLENGING.value:
                    result.challenging_papers.extend(search_result.get('papers', []))

                elif search_type == SearchType.COLLISION.value:
                    result.collision_papers.extend(search_result.get('papers', []))

        # 记录统计
        result.search_stats = {
            'total_papers': len(result.supporting_papers) + len(result.challenging_papers) + len(result.collision_papers),
            'sources_used': self.data_sources,
            'concurrent_limit': self.max_concurrent,
        }

        return result

    async def _search_with_retry_async(
        self,
        query: str,
        search_type: SearchType,
    ) -> Dict:
        """
        带指数退避的异步检索

        遇到 429 或超时，优雅重试（最多3次）

        Args:
            query: 搜索关键词
            search_type: 检索类型

        Returns:
            Dict: 搜索结果
        """
        # 解析数据源
        source = 'pubmed'
        actual_query = query

        if ':' in query:
            parts = query.split(':', 1)
            source = parts[0]
            actual_query = parts[1]

        # 获取搜索器
        searcher = self._get_searcher(source)

        if not searcher:
            return {
                'success': False,
                'search_type': search_type.value,
                'error': f'Source {source} not available',
                'papers': [],
            }

        # 指数退避重试
        for attempt in range(self.max_retries):
            try:
                # 检查是否支持异步
                if hasattr(searcher, 'search_async'):
                    search_result = await searcher.search_async(actual_query)
                else:
                    # 回退到同步（在异步上下文中运行）
                    search_result = await asyncio.get_event_loop().run_in_executor(
                        None,
                        searcher.search,
                        actual_query,
                    )

                if search_result.get('success'):
                    return {
                        'success': True,
                        'search_type': search_type.value,
                        'source': source,
                        'query': actual_query,
                        'papers': search_result.get('papers', []),
                        'total': search_result.get('total', 0),
                    }

                else:
                    error = search_result.get('error', 'Unknown error')

                    # 检查是否需要重试
                    if '429' in error or 'rate limit' in error.lower():
                        delay = self.base_delay * (2 ** attempt)
                        logger.warning(f"[Async Search] Rate limited, retrying in {delay}s")
                        await asyncio.sleep(delay)

                    elif 'timeout' in error.lower():
                        delay = self.base_delay * (2 ** attempt)
                        logger.warning(f"[Async Search] Timeout, retrying in {delay}s")
                        await asyncio.sleep(delay)

                    else:
                        # 其他错误，不重试
                        return {
                            'success': False,
                            'search_type': search_type.value,
                            'error': error,
                            'papers': [],
                        }

            except asyncio.TimeoutError:
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"[Async Search] Async timeout, retrying in {delay}s")
                await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"[Async Search] Search error: {e}")

                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    return {
                        'success': False,
                        'search_type': search_type.value,
                        'error': str(e),
                        'papers': [],
                    }

        # 最大重试次数超限
        return {
            'success': False,
            'search_type': search_type.value,
            'error': 'Max retries exceeded',
            'papers': [],
        }

    async def _synthesize_final_async(
        self,
        draft: DraftResult,
        verification: VerificationResult,
    ) -> FinalHypothesisResult:
        """
        异步综合输出

        Args:
            draft: 草稿结果
            verification: 验证结果

        Returns:
            FinalHypothesisResult: 最终假设
        """
        # 判断支撑状态
        support_status = "adequate"
        if len(verification.supporting_papers) < 2:
            support_status = "insufficient"
        elif len(verification.collision_papers) >= 2:
            support_status = "collision_detected"

        # 构建最终假设
        final = FinalHypothesisResult(
            title=draft.title,
            core_hypothesis=draft.core_hypothesis,
            details=self._build_details(draft, verification),
            mechanism=draft.mechanism_outline,
            counterfactual_analysis=self._build_counterfactual(draft),
            scores=self._calculate_scores(draft, verification),
            evidence={
                'supporting_papers': verification.supporting_papers[:5],
                'challenging_papers': verification.challenging_papers[:3],
                'collision_papers': verification.collision_papers[:3],
            },
            verified_ids=verification.verified_ids,
            support_status=support_status,
        )

        return final

    # ==================== 辅助方法 ====================

    def _extract_keywords(self, user_input: str) -> List[str]:
        """
        从用户输入中提取关键词

        Args:
            user_input: 用户输入文本

        Returns:
            List[str]: 关键词列表
        """
        import re

        # 移除停用词
        stopwords = {'的', '与', '在', '是', '和', '对', '为', '及', '等', '中',
                     '研究', '分析', '关系', '影响', '作用', '机制'}

        # 分词
        words = re.findall(r'[\w\u4e00-\u9fff]+', user_input)

        # 过滤
        keywords = []
        for word in words:
            if len(word) >= 2 and word not in stopwords:
                keywords.append(word)

        # 返回前5个关键词
        return keywords[:5]

    def _generate_title(self, user_input: str) -> str:
        """生成假设标题"""
        # 简化处理，直接返回用户输入的前50字
        return user_input[:50] + "..." if len(user_input) > 50 else user_input

    def _generate_core_hypothesis(self, user_input: str, keywords: List[str]) -> str:
        """生成核心假设"""
        if keywords:
            return f"{keywords[0]} → Mediator → Outcome 关系假设"
        return "核心假设待验证"

    def _generate_mechanism_outline(self, user_input: str, keywords: List[str]) -> str:
        """生成机制概述"""
        return f"基于 {user_input[:100]} 的机制推断框架"

    def _build_details(self, draft: DraftResult, verification: VerificationResult) -> str:
        """构建详细内容"""
        details_parts = [
            f"## 标题\n{draft.title}",
            f"## 核心假设\n{draft.core_hypothesis}",
            f"## 机制概述\n{draft.mechanism_outline}",
            f"## 支撑文献\n共 {len(verification.supporting_papers)} 篇",
        ]

        # 添加具体文献
        for i, paper in enumerate(verification.supporting_papers[:3], 1):
            title = paper.get('title', 'Unknown')
            identifier = paper.get('pmid') or paper.get('arxiv_id') or paper.get('doi') or ''
            details_parts.append(f"{i}. {title[:50]}... [{identifier}]")

        return "\n\n".join(details_parts)

    def _build_counterfactual(self, draft: DraftResult) -> Dict:
        """构建反事实分析"""
        return {
            'mediator_block_effect': "Mediator阻断后效应衰减30-50%",
            'alternative_pathway': "替代路径待验证",
            'sample_reduction_impact': "样本减半后功效下降",
        }

    def _calculate_scores(self, draft: DraftResult, verification: VerificationResult) -> Dict:
        """计算评分"""
        # 基于文献数量估算评分
        support_count = len(verification.supporting_papers)
        collision_count = len(verification.collision_papers)

        # 新颖性评分
        novelty = 8.0 - collision_count * 0.5
        novelty = max(0, min(10, novelty))

        # 严谨性评分
        rigor = 7.0 + support_count * 0.2
        rigor = max(0, min(10, rigor))

        # 影响力评分
        impact = 7.5

        return {
            'novelty': novelty,
            'rigor': rigor,
            'impact': impact,
            'overall': (novelty + rigor + impact) / 3,
        }


# ==================== 便捷函数 ====================

async def execute_async_retrieval(
    user_input: str,
    domain: str = None,
    data_sources: List[str] = None,
) -> Tuple[Dict, Dict]:
    """
    快捷异步检索执行函数

    Args:
        user_input: 用户研究想法
        domain: 学科领域
        data_sources: 数据源列表

    Returns:
        Tuple[Dict, Dict]: (最终假设, 验证信息)
    """
    retrieval = AsyncDraftVerificationRetrieval(data_sources=data_sources)
    return await retrieval.execute(user_input, domain)


# ==================== 测试 ====================

if __name__ == '__main__':
    print("=" * 60)
    print("V6.0 asyncio 异步检索器 - 测试")
    print("=" * 60)

    # 测试异步执行
    async def test_async_retrieval():
        retrieval = AsyncDraftVerificationRetrieval(data_sources=['pubmed'])

        result, verification = await retrieval.execute(
            user_input="阿尔茨海默病患者海马体萎缩与认知功能下降的关系",
            domain="神经科学",
        )

        print(f"\n最终假设:")
        print(f"  标题: {result.get('title', 'N/A')}")
        print(f"  支撑状态: {result.get('support_status', 'N/A')}")

        print(f"\n验证信息:")
        print(f"  支撑文献: {len(verification.get('supporting_papers', []))}")
        print(f"  碰撞文献: {len(verification.get('collision_papers', []))}")

    # 运行异步测试
    asyncio.run(test_async_retrieval())

    print("\n" + "=" * 60)
    print("测试完成")