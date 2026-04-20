# -*- coding: utf-8 -*-
"""
V6.0 数据源模块入口

提供多数据源检索适配器：
- PubMedSearcher: 医学/生物文献
- ArXivSearcher: 计算机/物理/数学预印本
- SemanticScholarSearcher: 全学科学术搜索
"""

from .arxiv_searcher import ArXivSearcher, ArXivSearchResult
from .semantic_scholar_searcher import SemanticScholarSearcher, S2SearchResult

__all__ = [
    'ArXivSearcher',
    'ArXivSearchResult',
    'SemanticScholarSearcher',
    'S2SearchResult',
]