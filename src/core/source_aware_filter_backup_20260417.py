# -*- coding: utf-8 -*-
"""
V7.1 Source-Aware 过滤器 - 异构数据源智能过滤

核心原则：
1. 数据源感知：根据数据源特性应用不同过滤规则
2. ArXiv IF 豁免：预印本库无 IF 字段，自动旁路
3. 日期强制：PubMed 和 ArXiv 都强制应用日期过滤
4. 引用量等效：ArXiv 可选使用引用量替代 IF（未来扩��）
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SourceAwareFilter:
    """
    数据源感知过滤器

    处理异构数据源的过滤逻辑差异：
    - PubMed: 有 IF，有日期
    - ArXiv: 无 IF（预印本），有日期
    - Semantic Scholar: 有 IF（部分），有日期
    """

    # 预印本数据源（无 IF）
    PREPRINT_SOURCES = {'arxiv', 'biorxiv', 'medrxiv', 'chemrxiv'}

    # 有 IF 的数据源
    IF_SOURCES = {'pubmed', 'pubmed_central', 'semantic_scholar', 'crossref'}

    @classmethod
    def filter_papers(
        cls,
        papers: List[Dict],
        min_if: Optional[float] = None,
        date_range: Optional[tuple] = None,
        source_field: str = 'source'
    ) -> List[Dict]:
        """
        Source-Aware 过滤：根据数据源类型应用不同规则

        Args:
            papers: 论文列表
            min_if: 最低影响因子（对预印本自动豁免）
            date_range: 日期范围 (start_year, end_year) - 强制生效
            source_field: 数据源字段名

        Returns:
            过滤后的论文列表
        """
        filtered = []

        # 统计信息
        stats = {
            'total': len(papers),
            'removed_if': 0,
            'removed_date': 0,
            'arxiv_passed': 0,  # ArXiv 豁免 IF 后通过的论文数
            'final': 0
        }

        for paper in papers:
            # 获取数据源
            source = paper.get(source_field, 'unknown').lower()

            # ========== 日期过滤：强制生效（所有数据源） ==========
            if date_range:
                start_year, end_year = date_range
                pub_date = paper.get('publication_date') or paper.get('published') or paper.get('year')

                if pub_date:
                    try:
                        # 提取年份
                        if isinstance(pub_date, str):
                            year = int(pub_date.split('-')[0])
                        elif isinstance(pub_date, datetime):
                            year = pub_date.year
                        else:
                            year = int(pub_date)

                        # 检查范围
                        if start_year and year < start_year:
                            stats['removed_date'] += 1
                            continue
                        if end_year and year > end_year:
                            stats['removed_date'] += 1
                            continue
                    except (ValueError, TypeError):
                        # 日期解析失败，保留（宽松策略）
                        pass

            # ========== IF 过滤：Source-Aware 豁免 ==========
            if min_if is not None and min_if > 0:
                # 检查是否为预印本（自动豁免 IF）
                if source in cls.PREPRINT_SOURCES:
                    # ArXiv 等预印本：自动豁免 IF 检查
                    stats['arxiv_passed'] += 1
                    logger.debug(f"[Source-Aware] {source} 论文豁免 IF 检查: {paper.get('title', 'N/A')[:50]}...")
                # 检查是否有 IF 字段
                elif 'journal' in paper and paper['journal']:
                    # 有期刊信息，检查 IF
                    try:
                        from src.utils.journal_if import get_journal_if
                        if_val = get_journal_if(paper['journal'])

                        if if_val < min_if:
                            stats['removed_if'] += 1
                            logger.debug(f"[Source-Aware] IF 不达标: {paper['journal']} (IF={if_val} < {min_if})")
                            continue
                    except ImportError:
                        logger.warning("[Source-Aware] journal_if 模块不可用，跳过 IF 检查")
                else:
                    # 无期刊信息（如部分 S2 论文），保留（宽松策略）
                    logger.debug(f"[Source-Aware] 无期刊信息，跳过 IF 检查: {source}")

            filtered.append(paper)

        stats['final'] = len(filtered)

        # 日志输出
        logger.info(
            f"[Source-Aware Filter] 过滤统计:\n"
            f"  输入: {stats['total']} 篇\n"
            f"  IF 豁免（预印本）: {stats['arxiv_passed']} 篇\n"
            f"  IF 过滤移除: {stats['removed_if']} 篇\n"
            f"  日期过滤移除: {stats['removed_date']} 篇\n"
            f"  输出: {stats['final']} 篇"
        )

        return filtered

    @classmethod
    def is_preprint_source(cls, source: str) -> bool:
        """检查是否为预印本数据源"""
        return source.lower() in cls.PREPRINT_SOURCES

    @classmethod
    def get_filter_strategy(cls, source: str) -> str:
        """
        获取数据源的过滤策略

        Returns:
            'if_and_date': 同时应用 IF 和日期过滤
            'date_only': 仅应用日期过滤（预印本）
            'none': 无过滤
        """
        if source.lower() in cls.PREPRINT_SOURCES:
            return 'date_only'
        elif source.lower() in cls.IF_SOURCES:
            return 'if_and_date'
        else:
            return 'none'

    @classmethod
    def add_source_marker(cls, papers: List[Dict], source: str) -> List[Dict]:
        """
        为论文添加数据源标记（用于后续 Source-Aware 过滤）

        Args:
            papers: 论文列表
            source: 数据源名称

        Returns:
            添加了 source 字段的论文列表
        """
        for paper in papers:
            paper['source'] = source
        return papers


# ==================== 便捷函数 ====================

def apply_source_aware_filter(
    papers: List[Dict],
    min_if: Optional[float] = None,
    date_range: Optional[tuple] = None,
) -> List[Dict]:
    """
    应用 Source-Aware 过滤的便捷函数

    Args:
        papers: 论文列表
        min_if: 最低影响因子（ArXiv 自动豁免）
        date_range: 日期范围 (start_year, end_year)

    Returns:
        过滤后的论文列表
    """
    return SourceAwareFilter.filter_papers(papers, min_if, date_range)


def get_filter_strategy_description(source: str) -> str:
    """
    获取过滤策略的描述文本（用于审计日志）

    Args:
        source: 数据源名称

    Returns:
        策略描述
    """
    strategy = SourceAwareFilter.get_filter_strategy(source)

    descriptions = {
        'if_and_date': f"[{source}] 应用 IF + 日期双重过滤",
        'date_only': f"[{source}] 仅应用日期过滤（预印本豁免 IF）",
        'none': f"[{source}] 无过滤"
    }

    return descriptions.get(strategy, f"[{source}] 未知策略")
