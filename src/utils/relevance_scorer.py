# -*- coding: utf-8 -*-
"""
文献相关性评分器 (Relevance Scorer)
用于两阶段漏斗过滤的快速评分功能
支持多种评分策略：TF-IDF、关键词匹配、语义相似度
"""
import re
import math
import time
from typing import List, Dict, Optional, Set
from collections import Counter
from datetime import datetime


class RelevanceScorer:
    """文献相关性评分器"""

    # 生物医学术语权重词典
    BIOMEDICAL_TERMS_WEIGHTS = {
        # 高权重术语（核心方法学）
        'machine learning': 3.0, 'deep learning': 3.0, 'neural network': 3.0,
        'transformer': 3.0, 'bert': 3.0, 'gpt': 3.0,
        'crispr': 2.5, 'gene editing': 2.5,
        'single-cell': 2.5, 'single cell': 2.5, 'scrna-seq': 2.5,
        'genomics': 2.0, 'transcriptomics': 2.0, 'proteomics': 2.0,
        'bioinformatics': 2.0, 'computational biology': 2.0,
        'causal inference': 2.5, 'causal discovery': 2.5,
        'diffusion model': 2.5, 'generative': 2.0,
        'clinical': 1.5, 'therapy': 1.5, 'diagnosis': 1.5,
        'biomarker': 1.5, 'prognosis': 1.5,
        'sequencing': 1.5, 'omics': 1.5,
        'validation': 1.0, 'prediction': 1.5, 'classification': 1.5,
    }

    # 停用词（忽略）
    STOPWORDS = {
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'can', 'of', 'at', 'by', 'for', 'with',
        'about', 'against', 'between', 'into', 'through', 'during', 'before',
        'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on',
        'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here',
        'there', 'when', 'where', 'why', 'how', 'all', 'both', 'each', 'few',
        'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
        'own', 'same', 'so', 'than', 'too', 'very', 'study', 'studies', 'paper',
        'research', 'analysis', 'result', 'using', 'used', 'based', 'approach',
        'method', 'data', 'we', 'this', 'that', 'these', 'those',
        '的', '是', '在', '和', '与', '或', '但', '而', '了', '中', '对', '为'
    }

    def __init__(self, scoring_method: str = 'hybrid'):
        """
        初始化评分器

        Args:
            scoring_method: 评分方法 ('tfidf', 'keyword', 'hybrid')
        """
        self.scoring_method = scoring_method
        self.idf_cache = {}  # IDF 缓存

    def score_papers(
        self,
        papers: List[Dict],
        query: str,
        top_k: int = 40
    ) -> List[Dict]:
        """
        为论文列表评分并排序

        Args:
            papers: 论文列表（需包含 title 和 abstract 字段）
            query: 搜索查询
            top_k: 返回前 k 篇高分论文

        Returns:
            评分并排序后的论文列表，每个论文添加 relevance_score 字段
        """
        if not papers:
            return []

        print(f"[评分器] 开始评分 {len(papers)} 篇论文 (方法: {self.scoring_method})")

        # 提取查询关键词
        query_tokens = self._tokenize(query)
        query_keywords = self._extract_keywords(query)

        # 计算每篇论文的评分
        scored_papers = []
        for i, paper in enumerate(papers):
            score = self._compute_paper_score(
                paper,
                query_tokens,
                query_keywords,
                len(papers)
            )
            paper['relevance_score'] = round(score, 4)
            scored_papers.append(paper)

            # 进度显示
            if (i + 1) % 100 == 0:
                print(f"  已评分 {i + 1}/{len(papers)} 篇...")

        # 按评分降序排序
        scored_papers.sort(key=lambda p: p['relevance_score'], reverse=True)

        # 返回前 k 篇
        result = scored_papers[:top_k]

        # 统计信息
        avg_score = sum(p['relevance_score'] for p in result) / len(result) if result else 0
        min_score = result[-1]['relevance_score'] if result else 0

        print(f"[评分器] 完成!")
        print(f"  筛选: {len(papers)} → {len(result)} 篇")
        print(f"  平均分: {avg_score:.3f}, 最低分: {min_score:.3f}")

        return result

    def _compute_paper_score(
        self,
        paper: Dict,
        query_tokens: List[str],
        query_keywords: Set[str],
        total_papers: int
    ) -> float:
        """计算单篇论文的相关性评分"""

        title = paper.get('title', '').lower()
        abstract = paper.get('abstract', '').lower()

        # 组合文本（标题权重更高）
        combined = title * 3 + ' ' + abstract

        score = 0.0

        if self.scoring_method in ['tfidf', 'hybrid']:
            # TF-IDF 评分
            tfidf_score = self._tfidf_score(combined, query_tokens, total_papers)
            score += tfidf_score * 0.6

        if self.scoring_method in ['keyword', 'hybrid']:
            # 关键词匹配评分
            keyword_score = self._keyword_score(combined, query_keywords)
            score += keyword_score * 0.4

        # 额外加分项
        score += self._bonus_score(paper, query_keywords)

        return score

    def _tfidf_score(self, text: str, query_tokens: List[str], total_docs: int) -> float:
        """计算 TF-IDF 相似度得分"""

        text_tokens = self._tokenize(text)

        if not text_tokens or not query_tokens:
            return 0.0

        # 计算 TF
        text_tf = Counter(text_tokens)
        text_len = len(text_tokens)

        # 计算 IDF（使用缓存）
        for token in query_tokens:
            if token not in self.idf_cache:
                # 简化的 IDF 计算
                self.idf_cache[token] = math.log(total_docs / (1 + 1))

        # 计算得分
        score = 0.0
        for token in query_tokens:
            if token in text_tf:
                tf = text_tf[token] / text_len
                idf = self.idf_cache.get(token, math.log(total_docs))
                score += tf * idf

        # 归一化
        max_possible = len(query_tokens) * math.log(total_docs)
        if max_possible > 0:
            score = score / max_possible

        return score

    def _keyword_score(self, text: str, query_keywords: Set[str]) -> float:
        """计算关键词匹配得分"""

        if not query_keywords:
            return 0.0

        matched = 0
        total_weight = 0

        for keyword in query_keywords:
            weight = self.BIOMEDICAL_TERMS_WEIGHTS.get(keyword, 1.0)
            total_weight += weight

            # 检查关键词是否在文本中
            if keyword in text:
                matched += weight
                # 标题匹配额外加分
                if keyword in text.split('. ')[0]:  # 假设第一句是标题
                    matched += weight * 0.5

        if total_weight == 0:
            return 0.0

        return matched / total_weight

    def _bonus_score(self, paper: Dict, query_keywords: Set[str]) -> float:
        """计算额外加分项"""

        bonus = 0.0

        # 1. 标题中包含查询词
        title = paper.get('title', '').lower()
        for keyword in query_keywords:
            if keyword in title:
                bonus += 0.1

        # 2. 摘要长度适中的论文（更可能有实质内容）
        abstract = paper.get('abstract', '')
        abstract_len = len(abstract.split())
        if 100 <= abstract_len <= 500:
            bonus += 0.05

        # 3. 数据科学元素加分
        ds_elements = paper.get('ds_elements', {})
        if ds_elements:
            if ds_elements.get('ml_models'):
                bonus += 0.1
            if ds_elements.get('dl_architectures'):
                bonus += 0.15

        # 4. 期刊质量加分（如果有影响因子信息）
        journal = paper.get('journal', '')
        high_impact_journals = {
            'nature', 'science', 'cell', 'nejm', 'lancet',
            'nature medicine', 'nature biotechnology'
        }
        if journal and any(j in journal.lower() for j in high_impact_journals):
            bonus += 0.1

        return bonus

    def _tokenize(self, text: str) -> List[str]:
        """分词并清理"""

        # 转小写
        text = text.lower()

        # 移除特殊字符，保留字母、数字、连字符
        text = re.sub(r'[^\w\s-]', ' ', text)

        # 分词
        tokens = text.split()

        # 移除停用词和短词
        tokens = [
            t for t in tokens
            if len(t) >= 2 and t not in self.STOPWORDS
        ]

        return tokens

    def _extract_keywords(self, query: str) -> Set[str]:
        """从查询中提取关键词（带权重）"""

        query_lower = query.lower()
        keywords = set()

        # 检查预定义的高权重术语
        for term, weight in self.BIOMEDICAL_TERMS_WEIGHTS.items():
            if term in query_lower:
                keywords.add(term)

        # 提取查询中的其他关键词
        tokens = self._tokenize(query)
        for token in tokens:
            if len(token) >= 3:
                keywords.add(token)

        return keywords

    def get_score_statistics(self, papers: List[Dict]) -> Dict:
        """获取评分统计信息"""

        scores = [p.get('relevance_score', 0) for p in papers]

        if not scores:
            return {}

        return {
            'count': len(scores),
            'mean': sum(scores) / len(scores),
            'max': max(scores),
            'min': min(scores),
            'median': sorted(scores)[len(scores) // 2]
        }


class BatchScorer:
    """批量评分器，处理大规模文献评分"""

    def __init__(self, batch_size: int = 100):
        """
        初始化批量评分器

        Args:
            batch_size: 每批处理的论文数量
        """
        self.batch_size = batch_size
        self.scorer = RelevanceScorer(scoring_method='hybrid')

    def score_large_dataset(
        self,
        papers: List[Dict],
        query: str,
        top_k: int = 40,
        progress_callback: Optional[callable] = None
    ) -> List[Dict]:
        """
        处理大规模数据集的评分

        Args:
            papers: 论文列表
            query: 搜索查询
            top_k: 返回前 k 篇
            progress_callback: 进度回调函数

        Returns:
            评分并排序后的论文列表
        """
        if len(papers) <= self.batch_size:
            return self.scorer.score_papers(papers, query, top_k)

        # 分批处理
        all_scored = []
        total_batches = (len(papers) + self.batch_size - 1) // self.batch_size

        for i in range(0, len(papers), self.batch_size):
            batch = papers[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1

            print(f"[批量评分] 处理批次 {batch_num}/{total_batches}...")

            # 评分当前批次
            scored_batch = self.scorer.score_papers(batch, query, len(batch))
            all_scored.extend(scored_batch)

            # 进度回调
            if progress_callback:
                progress_callback(batch_num, total_batches, len(all_scored))

            # 避免过快处理
            time.sleep(0.1)

        # 全局排序
        all_scored.sort(key=lambda p: p['relevance_score'], reverse=True)

        return all_scored[:top_k]


# 便捷函数
def score_and_filter(
    papers: List[Dict],
    query: str,
    top_k: int = 40,
    method: str = 'hybrid'
) -> List[Dict]:
    """
    评分并筛选论文（便捷函数）

    Args:
        papers: 论文列表
        query: 搜索查询
        top_k: 返回前 k 篇
        method: 评分方法

    Returns:
        评分并排序后的论文列表
    """
    scorer = RelevanceScorer(scoring_method=method)
    return scorer.score_papers(papers, query, top_k)


if __name__ == '__main__':
    # 测试评分器
    print("=" * 60)
    print("文献相关性评分器 - 测试")
    print("=" * 60)

    # 模拟论文数据
    test_papers = [
        {
            'pmid': '1',
            'title': 'Machine learning for cancer prediction using genomics data',
            'abstract': 'We developed a deep learning model to predict cancer outcomes from genomic data.'
        },
        {
            'pmid': '2',
            'title': 'A study of plant biology',
            'abstract': 'This paper examines plant growth patterns in different environments.'
        },
        {
            'pmid': '3',
            'title': 'CRISPR gene editing for therapeutic applications',
            'abstract': 'We review recent advances in CRISPR technology for treating genetic diseases.'
        },
        {
            'pmid': '4',
            'title': 'Single-cell RNA sequencing analysis reveals new cell types',
            'abstract': 'Using single-cell RNA-seq, we identified novel cell populations in human tissue.'
        },
        {
            'pmid': '5',
            'title': 'Machine learning and CRISPR: A comprehensive review',
            'abstract': 'This review discusses the intersection of ML and gene editing technologies.'
        }
    ]

    test_query = "machine learning CRISPR genomics"

    scorer = RelevanceScorer(scoring_method='hybrid')
    results = scorer.score_papers(test_papers, test_query, top_k=3)

    print(f"\n查询: {test_query}")
    print(f"\nTop 3 相关论文:")
    print("-" * 60)

    for i, paper in enumerate(results, 1):
        print(f"\n{i}. 评分: {paper['relevance_score']:.3f}")
        print(f"   标题: {paper['title']}")
        print(f"   摘要: {paper['abstract'][:80]}...")

    print("\n" + "=" * 60)
