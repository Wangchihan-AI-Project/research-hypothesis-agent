# -*- coding: utf-8 -*-
"""
查询优化器 (Query Optimizer) - V3.0 架构升级核心模块

借鉴 karpathy/autoresearch 范式，解耦检索与智能查询优化。

核心功能：
1. 在触发检索前，生成 SearchPlan（3-5个极简查询词组）
2. 严格屏蔽年份和复杂介词
3. 遍历查询列表，直到获取有效数据
4. 提供透明的状态机日志输出

作者: 架构师 V3.0
日期: 2026-04-16
"""

from typing import List, Dict, Optional, Tuple
import re
import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SearchQuery:
    """单个搜索查询"""
    query: str
    priority: int = 0  # 优先级，0为最高
    description: str = ""
    expected_results: int = 10

    def __repr__(self):
        return f"[P{self.priority}] '{self.query}' ({self.description})"


@dataclass
class SearchPlan:
    """搜索计划 - 包含多个查询策略"""
    queries: List[SearchQuery] = field(default_factory=list)
    original_topic: str = ""
    strategy: str = "default"
    metadata: Dict = field(default_factory=dict)

    def add_query(self, query: str, priority: int = 0, description: str = ""):
        """添加查询到计划"""
        self.queries.append(SearchQuery(
            query=query,
            priority=priority,
            description=description
        ))
        # 按优先级排序
        self.queries.sort(key=lambda x: x.priority)

    def get_next_query(self) -> Optional[SearchQuery]:
        """获取下一个待执行的查询"""
        if not self.queries:
            return None
        return self.queries.pop(0)

    def has_remaining(self) -> bool:
        """是否还有剩余查询"""
        return len(self.queries) > 0

    def __repr__(self):
        return f"SearchPlan({len(self.queries)} queries, strategy={self.strategy})"


class QueryOptimizer:
    """
    查询优化器 - 核心优化逻辑

    废弃直接让生成器生成长串 Query 的逻辑。
    在触发检索前，增加一个轻量级的规划步骤。
    """

    # PubMed 语法规则
    PUBMED_SYNTAX_RULES = {
        'max_keywords': 3,  # 每个query最多3个核心关键词
        'forbidden_year_terms': [
            '2020', '2021', '2022', '2023', '2024', '2025', '2026',
            'recent', 'latest', 'last', 'past', 'current', 'year',
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december'
        ],
        'forbidden_complex_prepositions': [
            'with respect to', 'in regard to', 'in terms of',
            'based on the relationship between', 'utilizing the methodology of'
        ],
        'preferred_operators': ['AND', 'OR', 'NOT'],
        'field_tags': ['[TIAB]', '[TI]', '[AB]', '[MH]', '[TW]']
    }

    # 查询降级策略
    DEGRADATION_STRATEGIES = {
        'full': 1.0,      # full query（3个关键词）
        'medium': 0.7,    # medium query（2个关键词）
        'minimal': 0.4,   # minimal query（1-2个核心词）
        'fallback': 0.1   # fallback query（单个最核心词）
    }

    def __init__(self):
        self.logger = logger
        self.search_history: List[Dict] = []

    def optimize(
        self,
        research_topic: str,
        domain_keywords: Optional[List[str]] = None,
        strategy: str = "adaptive"
    ) -> SearchPlan:
        """
        生成优化的搜索计划

        Args:
            research_topic: 研究主题
            domain_keywords: 领域特定关键词
            strategy: 搜索策略 ('adaptive', 'conservative', 'aggressive')

        Returns:
            SearchPlan: 包含多个查询策略的搜索计划
        """
        self._log_state("[Query Optimization] Starting search plan generation...")

        plan = SearchPlan(
            original_topic=research_topic,
            strategy=strategy,
            metadata={'generated_at': datetime.now().isoformat()}
        )

        # 提取核心关键词
        core_keywords = self._extract_core_keywords(research_topic, domain_keywords)

        if not core_keywords:
            self._log_state("[Query Optimization] ⚠️ Could not extract keywords, using original topic")
            plan.add_query(
                query=self._sanitize_query(research_topic),
                priority=0,
                description="fallback query"
            )
            return plan

        # ========== 生成多层级查询策略 ==========

        # 策略1: full query（3个关键词，高优先级）
        if len(core_keywords) >= 3:
            full_query = self._build_pubmed_query(core_keywords[:3])
            plan.add_query(
                query=full_query,
                priority=0,
                description=f"full query: {' + '.join(core_keywords[:3])}"
            )

        # 策略2: medium query（2个关键词）
        if len(core_keywords) >= 2:
            medium_query = self._build_pubmed_query(core_keywords[:2])
            plan.add_query(
                query=medium_query,
                priority=1,
                description=f"medium query: {' + '.join(core_keywords[:2])}"
            )

        # 策略3: minimal query（核心单一概念）
        if core_keywords:
            minimal_query = self._build_pubmed_query([core_keywords[0]])
            plan.add_query(
                query=minimal_query,
                priority=2,
                description=f"minimal query: {core_keywords[0]}"
            )

        # 策略4: variant query（使用同义词或相关词）
        if domain_keywords and len(domain_keywords) >= 2:
            variant_query = self._build_pubmed_query(domain_keywords[:2])
            plan.add_query(
                query=variant_query,
                priority=3,
                description=f"variant query: {' + '.join(domain_keywords[:2])}"
            )

        # 策略5: 宽泛查询（如果所有策略都失败）
        broad_query = self._build_broad_query(core_keywords)
        plan.add_query(
            query=broad_query,
            priority=4,
            description="宽泛fallback query"
        )

        self._log_state(f"[Query Optimization] Search plan generated: {len(plan.queries)} queries")
        self._print_plan_summary(plan)

        return plan

    def _extract_core_keywords(
        self,
        research_topic: str,
        domain_keywords: Optional[List[str]] = None
    ) -> List[str]:
        """
        从研究主题中提取核心关键词

        使用轻量级NLP提取，避免复杂的LLM调用
        """
        keywords = []

        # 清理文本
        topic = research_topic.strip()

        # ========== 方法1: 引号提取 ==========
        # 提取引号中的精确短语
        quoted_patterns = re.findall(r'"([^"]+)"', topic)
        for pattern in quoted_patterns:
            clean = self._sanitize_single_term(pattern)
            if clean and len(clean.split()) <= 3:
                keywords.extend(clean.split())

        # ========== 方法2: 连续大写词提取（生物学术语）==========
        # 例如: Alzheimer, Parkinson, CRISPR, GPT
        uppercase_patterns = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', topic)
        for pattern in uppercase_patterns:
            keywords.append(pattern)

        # ========== 方法3: 通用分词 ==========
        # 移除标点，分词
        words = re.findall(r'\b[a-zA-Z]{3,}\b', topic)

        # 过滤停用词
        stopwords = {
            'and', 'or', 'the', 'for', 'with', 'from', 'study', 'research',
            'analysis', 'using', 'based', 'approach', 'method', 'system'
        }

        for word in words:
            word_lower = word.lower()
            if word_lower not in stopwords and len(word) >= 3:
                keywords.append(word)

        # ========== 添加领域关键词 ==========
        if domain_keywords:
            keywords.extend(domain_keywords)

        # 去重并保持顺序
        seen = set()
        unique_keywords = []
        for kw in keywords:
            clean_kw = self._sanitize_single_term(kw)
            if clean_kw and clean_kw not in seen:
                seen.add(clean_kw)
                unique_keywords.append(clean_kw)

        # 限制关键词数量
        return unique_keywords[:5]

    def _sanitize_single_term(self, term: str) -> str:
        """清理单个术语"""
        # 移除年份
        for year_term in self.PUBMED_SYNTAX_RULES['forbidden_year_terms']:
            pattern = r'\b' + re.escape(year_term) + r'\b'
            term = re.sub(pattern, '', term, flags=re.IGNORECASE)

        # 移除特殊字符（保留连字符和空格）
        term = re.sub(r'[^\w\s\-]', ' ', term)

        # 标准化空格
        term = ' '.join(term.split())

        return term.strip()

    def _sanitize_query(self, query: str) -> str:
        """
        清理查询字符串，确保符合 PubMed 语法

        严格屏蔽：
        - 年份和日期词汇
        - 复杂介词短语
        - 超长查询
        """
        # 移除年份相关词汇
        for year_term in self.PUBMED_SYNTAX_RULES['forbidden_year_terms']:
            pattern = r'\b' + re.escape(year_term) + r'\b'
            query = re.sub(pattern, '', query, flags=re.IGNORECASE)

        # 移除复杂介词
        for prep in self.PUBMED_SYNTAX_RULES['forbidden_complex_prepositions']:
            query = query.replace(prep, ' AND ')

        # 限制关键词数量
        words = query.split()
        if len(words) > self.PUBMED_SYNTAX_RULES['max_keywords']:
            words = words[:self.PUBMED_SYNTAX_RULES['max_keywords']]
            query = ' '.join(words)

        # 使用 AND 连接
        query = ' AND '.join(w.strip() for w in words if w.strip())

        return query

    def _build_pubmed_query(self, keywords: List[str]) -> str:
        """
        构建符合 PubMed 语法的查询

        格式: keyword1[TIAB] AND keyword2[TIAB] AND keyword3[TIAB]
        """
        clean_keywords = []
        for kw in keywords:
            clean = self._sanitize_single_term(kw)
            if clean:
                # 添加字段标签（标题/摘要）
                clean_keywords.append(f'{clean}[TIAB]')

        if not clean_keywords:
            return clean_keywords[0] if clean_keywords else ""

        # 使用 AND 连接
        return ' AND '.join(clean_keywords)

    def _build_broad_query(self, keywords: List[str]) -> str:
        """构建宽泛查询（使用 OR）"""
        if not keywords:
            return ""

        clean_keywords = []
        for kw in keywords[:2]:  # 只取前两个
            clean = self._sanitize_single_term(kw)
            if clean:
                clean_keywords.append(f'{clean}[TIAB]')

        if len(clean_keywords) >= 2:
            return f'({clean_keywords[0]} OR {clean_keywords[1]})'
        return clean_keywords[0] if clean_keywords else ""

    def _log_state(self, message: str):
        """记录状态日志"""
        self.logger.info(message)
        print(message)

    def _print_plan_summary(self, plan: SearchPlan):
        """打印搜索计划摘要"""
        print("\n" + "="*60)
        print("Search Plan Summary")
        print("="*60)
        print(f"Original Topic: {plan.original_topic[:60]}...")
        print(f"Strategy: {plan.strategy}")
        print(f"Query Count: {len(plan.queries)}")
        print("\nQuery Queue:")
        for i, query in enumerate(plan.queries, 1):
            print(f"  {i}. {query}")
        print("="*60 + "\n")

    def record_search_result(self, query: SearchQuery, result_count: int, success: bool):
        """记录搜索结果用于学习优化"""
        self.search_history.append({
            'query': query.query,
            'description': query.description,
            'result_count': result_count,
            'success': success,
            'timestamp': datetime.now().isoformat()
        })

    def get_search_statistics(self) -> Dict:
        """获取搜索统计信息"""
        if not self.search_history:
            return {'total_searches': 0, 'success_rate': 0}

        total = len(self.search_history)
        successful = sum(1 for h in self.search_history if h['success'])
        avg_results = sum(h['result_count'] for h in self.search_history) / total

        return {
            'total_searches': total,
            'successful_searches': successful,
            'success_rate': successful / total,
            'average_results': avg_results
        }


# ========== 便捷函数 ==========

def create_search_plan(
    research_topic: str,
    domain_keywords: Optional[List[str]] = None,
    strategy: str = "adaptive"
) -> SearchPlan:
    """
    创建搜索计划的便捷函数

    Args:
        research_topic: 研究主题
        domain_keywords: 领域关键词（可选）
        strategy: 搜索策略

    Returns:
        SearchPlan 对象

    Example:
        >>> plan = create_search_plan("Alzheimer's disease and machine learning")
        >>> while plan.has_remaining():
        ...     query = plan.get_next_query()
        ...     results = search_pubmed(query.query)
        ...     if results:
        ...         break
    """
    optimizer = QueryOptimizer()
    return optimizer.optimize(
        research_topic=research_topic,
        domain_keywords=domain_keywords,
        strategy=strategy
    )


def optimize_query(research_topic: str) -> str:
    """
    快速优化单个查询（向后兼容）

    Args:
        research_topic: 原始研究主题

    Returns:
        优化后的查询字符串
    """
    optimizer = QueryOptimizer()
    plan = optimizer.optimize(research_topic)
    query = plan.get_next_query()
    return query.query if query else research_topic


if __name__ == '__main__':
    # 测试查询优化器
    print("="*60)
    print("Query Optimizer 测试")
    print("="*60)

    test_topics = [
        "Alzheimer's disease and machine learning for early diagnosis 2023-2024",
        "CRISPR gene editing in cancer immunotherapy",
        "Using transformer models for protein structure prediction",
        "pQTL analysis of cerebrospinal fluid biomarkers in Parkinson disease"
    ]

    for topic in test_topics:
        print(f"\n{'─'*60}")
        print(f"原始主题: {topic}")
        print(f"{'─'*60}")

        plan = create_search_plan(topic)

        print(f"优化后的查询:")
        while plan.has_remaining():
            query = plan.get_next_query()
            print(f"  → {query}")
