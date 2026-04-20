# -*- coding: utf-8 -*-
"""
V6.0 Semantic Scholar 搜索适配器

用于全学科学术文献检索，覆盖自然科学、社会科学等领域。

核心功能：
- 同步和异步检索支持
- 指数退避重试机制
- 引用和被引用关系获取
- 论文影响力指标（引用数、h-index）
- DOI 验证
"""

import re
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import time
import requests

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== Semantic Scholar API 配置 ====================

S2_API_URL = "https://api.semanticscholar.org/graph/v1"
S2_SEARCH_URL = f"{S2_API_URL}/paper/search"
S2_PAPER_URL = f"{S2_API_URL}/paper"

# API 返回字段
S2_DEFAULT_FIELDS = [
    'paperId',
    'title',
    'abstract',
    'authors',
    'year',
    'citationCount',
    'referenceCount',
    'publicationDate',
    'publicationVenue',
    'journal',
    'doi',
    'url',
    'isOpenAccess',
    'fieldsOfStudy',
    's2FieldsOfStudy',
]


# ==================== DOI 格式验证 ====================

DOI_PATTERN = r'10\.\d{4,}/[^\s]+'


def validate_doi(doi: str) -> Tuple[bool, str]:
    """
    验证 DOI 格式

    Args:
        doi: DOI 字符串

    Returns:
        Tuple[bool, str]: (是否有效, 标准化DOI)
    """
    # 清理输入
    doi = doi.strip()

    # 移除前缀
    for prefix in ['doi:', 'DOI:', 'https://doi.org/', 'http://dx.doi.org/']:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]

    # 验证格式
    match = re.search(DOI_PATTERN, doi)
    if match:
        return True, match.group(0)

    return False, doi


# ==================== Semantic Scholar 搜索结果数据类 ====================

@dataclass
class S2SearchResult:
    """
    Semantic Scholar 单篇文献结果
    """
    paper_id: str                           # S2 Paper ID
    title: str                              # 标题
    authors: List[str] = field(default_factory=list)  # 作者
    abstract: str = ""                      # 摘要
    year: int = 0                           # 发表年份
    doi: Optional[str] = None               # DOI
    url: str = ""                           # S2 URL
    citation_count: int = 0                 # 引用数
    reference_count: int = 0                # 参考文献数
    publication_date: Optional[str] = None  # 发表日期
    publication_venue: Optional[str] = None # 发表载体（期刊/会议）
    journal: Optional[str] = None           # 期刊名称
    is_open_access: bool = False            # 是否开放获取
    fields_of_study: List[str] = field(default_factory=list)  # 研究领域
    influential_citation_count: int = 0     # 高影响力引用数

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'paper_id': self.paper_id,
            'title': self.title,
            'authors': self.authors,
            'abstract': self.abstract,
            'year': self.year,
            'doi': self.doi,
            'url': self.url,
            'citation_count': self.citation_count,
            'reference_count': self.reference_count,
            'publication_date': self.publication_date,
            'publication_venue': self.publication_venue,
            'journal': self.journal,
            'is_open_access': self.is_open_access,
            'fields_of_study': self.fields_of_study,
            'influential_citation_count': self.influential_citation_count,
        }


# ==================== Semantic Scholar 搜索器 ====================

class SemanticScholarSearcher:
    """
    Semantic Scholar 搜索适配器

    支持同步和异步检索，覆盖全学科学术文献
    """

    # 检索配置
    MAX_RESULTS_DEFAULT = 20
    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # 指数退避基数
    TIMEOUT = 30  # HTTP 超时（秒）
    RATE_LIMIT_DELAY = 1.0  # S2 API 速率限制间隔

    def __init__(
        self,
        max_results: int = None,
        enable_retry: bool = True,
        api_key: str = None,  # S2 API Key（可选，提高速率限制）
    ):
        """
        初始化 Semantic Scholar 搜索器

        Args:
            max_results: 默认最大结果数
            enable_retry: 是否启用重试
            api_key: Semantic Scholar API Key（可选）
        """
        self.max_results = max_results or self.MAX_RESULTS_DEFAULT
        self.enable_retry = enable_retry
        self.api_key = api_key
        self._last_request_time = 0

    def _get_headers(self) -> Dict:
        """
        获取 HTTP 请求头

        Returns:
            Dict: 请求头字典
        """
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Research-Hypothesis-Agent-V6/1.0',
        }

        if self.api_key:
            headers['x-api-key'] = self.api_key

        return headers

    def _build_fields_param(self, fields: List[str] = None) -> str:
        """
        构建返回字段参数

        Args:
            fields: 字段列表

        Returns:
            str: 字段参数字符串
        """
        if not fields:
            fields = S2_DEFAULT_FIELDS

        return ','.join(fields)

    def _parse_s2_response(self, data: Dict) -> List[S2SearchResult]:
        """
        解析 Semantic Scholar API JSON 响应

        Args:
            data: API 响应 JSON

        Returns:
            List[S2SearchResult]: 解析后的文献列表
        """
        results = []

        papers = data.get('data', [])

        for paper in papers:
            # Paper ID
            paper_id = paper.get('paperId', '')

            # 标题
            title = paper.get('title', '')

            # 作者
            authors = []
            for author in paper.get('authors', []):
                name = author.get('name', '')
                if name:
                    authors.append(name)

            # 摘要
            abstract = paper.get('abstract', '') or ''

            # 年份
            year = paper.get('year', 0) or 0

            # DOI
            doi = paper.get('doi')
            if doi:
                is_valid, validated_doi = validate_doi(doi)
                if is_valid:
                    doi = validated_doi

            # URL
            url = paper.get('url', '')

            # 引用数
            citation_count = paper.get('citationCount', 0) or 0

            # 参考文献数
            reference_count = paper.get('referenceCount', 0) or 0

            # 发表日期
            publication_date = paper.get('publicationDate')

            # 发表载体
            publication_venue = None
            venue = paper.get('publicationVenue')
            if venue:
                publication_venue = venue.get('name', '')

            # 期刊
            journal = paper.get('journal')
            if journal:
                journal = journal.get('name', '')

            # 是否开放获取
            is_open_access = paper.get('isOpenAccess', False)

            # 研究领域
            fields_of_study = []
            fos = paper.get('fieldsOfStudy', [])
            if fos:
                fields_of_study = [f for f in fos if f]

            # S2 研究领域
            s2fos = paper.get('s2FieldsOfStudy', [])
            if s2fos:
                for f in s2fos:
                    category = f.get('category', '')
                    if category and category not in fields_of_study:
                        fields_of_study.append(category)

            # 高影响力引用数
            influential_citation_count = paper.get('influentialCitationCount', 0) or 0

            # 构建结果对象
            result = S2SearchResult(
                paper_id=paper_id,
                title=title,
                authors=authors,
                abstract=abstract,
                year=year,
                doi=doi,
                url=url,
                citation_count=citation_count,
                reference_count=reference_count,
                publication_date=publication_date,
                publication_venue=publication_venue,
                journal=journal,
                is_open_access=is_open_access,
                fields_of_study=fields_of_study,
                influential_citation_count=influential_citation_count,
            )

            results.append(result)

        return results

    def search(
        self,
        query: str,
        max_results: int = None,
        fields: List[str] = None,
        year_range: Tuple[int, int] = None,
        publication_types: List[str] = None,
        fields_of_study: List[str] = None,
    ) -> Dict:
        """
        同步搜索 Semantic Scholar

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            fields: 返回字段列表
            year_range: 年份范围 (start, end)
            publication_types: 发表类型 ['JournalArticle', 'Conference', ...]
            fields_of_study: 研究领域限制

        Returns:
            Dict: 搜索结果
        """
        max_results = max_results or self.max_results

        # 构建参数
        params = {
            'query': query,
            'limit': max_results,
            'fields': self._build_fields_param(fields),
        }

        # 添加过滤条件
        if year_range:
            params['year'] = f'{year_range[0]}-{year_range[1]}'

        if publication_types:
            params['publicationTypes'] = ','.join(publication_types)

        if fields_of_study:
            params['fieldsOfStudy'] = ','.join(fields_of_study)

        # 执行请求（带重试）
        for attempt in range(self.MAX_RETRIES):
            try:
                # 遵守 API 速率限制
                elapsed = time.time() - self._last_request_time
                if elapsed < self.RATE_LIMIT_DELAY:
                    time.sleep(self.RATE_LIMIT_DELAY - elapsed)

                response = requests.get(
                    S2_SEARCH_URL,
                    params=params,
                    headers=self._get_headers(),
                    timeout=self.TIMEOUT,
                )

                self._last_request_time = time.time()

                if response.status_code == 200:
                    data = response.json()
                    papers = self._parse_s2_response(data)
                    total = data.get('total', len(papers))
                    logger.info(f"[S2] Search returned {len(papers)} papers (total: {total})")

                    return {
                        'success': True,
                        'papers': [p.to_dict() for p in papers],
                        'query': query,
                        'source': 'semantic_scholar',
                        'total': total,
                    }

                elif response.status_code == 429:
                    # 速率限制，等待后重试
                    delay = self.BASE_DELAY * (2 ** attempt)
                    logger.warning(f"[S2] Rate limited, retrying in {delay}s")
                    time.sleep(delay)

                elif response.status_code == 503:
                    # 服务暂时不可用
                    delay = self.BASE_DELAY * (2 ** attempt) * 2
                    logger.warning(f"[S2] Service unavailable, retrying in {delay}s")
                    time.sleep(delay)

                else:
                    logger.error(f"[S2] API error: {response.status_code}")
                    return {
                        'success': False,
                        'error': f'API error: {response.status_code}',
                        'papers': [],
                    }

            except requests.exceptions.Timeout:
                logger.warning(f"[S2] Timeout, attempt {attempt + 1}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.BASE_DELAY * (2 ** attempt))

            except Exception as e:
                logger.error(f"[S2] Search error: {e}")
                return {
                    'success': False,
                    'error': str(e),
                    'papers': [],
                }

        return {
            'success': False,
            'error': 'Max retries exceeded',
            'papers': [],
        }

    async def search_async(
        self,
        query: str,
        max_results: int = None,
        fields: List[str] = None,
        year_range: Tuple[int, int] = None,
        publication_types: List[str] = None,
        fields_of_study: List[str] = None,
    ) -> Dict:
        """
        异步搜索 Semantic Scholar

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            fields: 返回字段列表
            year_range: 年份范围
            publication_types: 发表类型
            fields_of_study: 研究领域

        Returns:
            Dict: 搜索结果
        """
        max_results = max_results or self.max_results

        # 构建参数
        params = {
            'query': query,
            'limit': max_results,
            'fields': self._build_fields_param(fields),
        }

        if year_range:
            params['year'] = f'{year_range[0]}-{year_range[1]}'

        if publication_types:
            params['publicationTypes'] = ','.join(publication_types)

        if fields_of_study:
            params['fieldsOfStudy'] = ','.join(fields_of_study)

        # 构建 URL
        param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        url = f"{S2_SEARCH_URL}?{param_str}"

        # 异步请求
        for attempt in range(self.MAX_RETRIES):
            try:
                # 遵守速率限制
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        headers=self._get_headers(),
                        timeout=aiohttp.ClientTimeout(total=self.TIMEOUT),
                    ) as response:

                        if response.status == 200:
                            data = await response.json()
                            papers = self._parse_s2_response(data)
                            total = data.get('total', len(papers))
                            logger.info(f"[S2 Async] Search returned {len(papers)} papers")

                            return {
                                'success': True,
                                'papers': [p.to_dict() for p in papers],
                                'query': query,
                                'source': 'semantic_scholar',
                                'total': total,
                            }

                        elif response.status == 429:
                            delay = self.BASE_DELAY * (2 ** attempt)
                            logger.warning(f"[S2 Async] Rate limited, retrying in {delay}s")
                            await asyncio.sleep(delay)

                        elif response.status == 503:
                            delay = self.BASE_DELAY * (2 ** attempt) * 2
                            logger.warning(f"[S2 Async] Service unavailable")
                            await asyncio.sleep(delay)

                        else:
                            logger.error(f"[S2 Async] API error: {response.status}")
                            return {
                                'success': False,
                                'error': f'API error: {response.status}',
                                'papers': [],
                            }

            except asyncio.TimeoutError:
                logger.warning(f"[S2 Async] Timeout, attempt {attempt + 1}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.BASE_DELAY * (2 ** attempt))

            except Exception as e:
                logger.error(f"[S2 Async] Search error: {e}")
                return {
                    'success': False,
                    'error': str(e),
                    'papers': [],
                }

        return {
            'success': False,
            'error': 'Max retries exceeded',
            'papers': [],
        }

    def fetch_by_id(self, paper_id: str) -> Dict:
        """
        根据 Paper ID 获取单篇文献

        Args:
            paper_id: S2 Paper ID 或 DOI

        Returns:
            Dict: 文献信息
        """
        # 判断是 DOI 还是 Paper ID
        is_doi = False
        if paper_id.startswith('10.'):
            is_valid, validated_doi = validate_doi(paper_id)
            if is_valid:
                paper_id = validated_doi
                is_doi = True

        # 构建 URL
        if is_doi:
            url = f"{S2_PAPER_URL}/DOI:{paper_id}"
        else:
            url = f"{S2_PAPER_URL}/{paper_id}"

        params = {
            'fields': self._build_fields_param(),
        }

        # 执行请求
        try:
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=self.TIMEOUT,
            )

            if response.status_code == 200:
                data = response.json()
                paper = self._parse_s2_response({'data': [data]})

                if paper:
                    return {
                        'success': True,
                        'paper': paper[0].to_dict(),
                    }

            return {
                'success': False,
                'error': 'Paper not found',
            }

        except Exception as e:
            logger.error(f"[S2] Fetch by ID error: {e}")
            return {
                'success': False,
                'error': str(e),
            }

    def get_citations(self, paper_id: str, max_results: int = 50) -> Dict:
        """
        获取论文的引用文献

        Args:
            paper_id: S2 Paper ID
            max_results: 最大结果数

        Returns:
            Dict: 引用文献列表
        """
        url = f"{S2_PAPER_URL}/{paper_id}/citations"

        params = {
            'fields': self._build_fields_param(['paperId', 'title', 'authors', 'year']),
            'limit': max_results,
        }

        try:
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=self.TIMEOUT,
            )

            if response.status_code == 200:
                data = response.json()
                citations = []

                for citation in data.get('data', []):
                    citing_paper = citation.get('citingPaper', {})
                    citations.append({
                        'paper_id': citing_paper.get('paperId'),
                        'title': citing_paper.get('title'),
                        'authors': [a.get('name') for a in citing_paper.get('authors', [])],
                        'year': citing_paper.get('year'),
                    })

                return {
                    'success': True,
                    'citations': citations,
                    'total': len(citations),
                }

            return {
                'success': False,
                'error': 'Failed to get citations',
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }

    def get_references(self, paper_id: str, max_results: int = 50) -> Dict:
        """
        获取论文的参考文献

        Args:
            paper_id: S2 Paper ID
            max_results: 最大结果数

        Returns:
            Dict: 参考文献列表
        """
        url = f"{S2_PAPER_URL}/{paper_id}/references"

        params = {
            'fields': self._build_fields_param(['paperId', 'title', 'authors', 'year']),
            'limit': max_results,
        }

        try:
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=self.TIMEOUT,
            )

            if response.status_code == 200:
                data = response.json()
                references = []

                for ref in data.get('data', []):
                    cited_paper = ref.get('citedPaper', {})
                    references.append({
                        'paper_id': cited_paper.get('paperId'),
                        'title': cited_paper.get('title'),
                        'authors': [a.get('name') for a in cited_paper.get('authors', [])],
                        'year': cited_paper.get('year'),
                    })

                return {
                    'success': True,
                    'references': references,
                    'total': len(references),
                }

            return {
                'success': False,
                'error': 'Failed to get references',
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }


# ==================== 便捷函数 ====================

def search_semantic_scholar(query: str, max_results: int = 20) -> Dict:
    """
    快捷 Semantic Scholar 搜索函数

    Args:
        query: 搜索关键词
        max_results: 最大结果数

    Returns:
        Dict: 搜索结果
    """
    searcher = SemanticScholarSearcher()
    return searcher.search(query, max_results=max_results)


async def search_semantic_scholar_async(query: str, max_results: int = 20) -> Dict:
    """
    快捷异步 Semantic Scholar 搜索函数

    Args:
        query: 搜索关键词
        max_results: 最大结果数

    Returns:
        Dict: 搜索结果
    """
    searcher = SemanticScholarSearcher()
    return await searcher.search_async(query, max_results=max_results)


# ==================== 测试 ====================

if __name__ == '__main__':
    print("=" * 60)
    print("V6.0 Semantic Scholar 搜索适配器 - 测试")
    print("=" * 60)

    searcher = SemanticScholarSearcher()

    # 测试搜索
    print("\n测试 1: 搜索 'machine learning'")
    result = searcher.search("machine learning", max_results=5)

    if result['success']:
        print(f"找到 {len(result['papers'])} 篇文献")
        for paper in result['papers'][:2]:
            print(f"  - {paper['paper_id']}: {paper['title'][:50]}...")
            print(f"    引用数: {paper['citation_count']}")
    else:
        print(f"搜索失败: {result['error']}")

    # 测试 DOI 验证
    print("\n测试 2: DOI 验证")
    test_dois = ['10.1234/test', 'doi:10.1234/test', 'https://doi.org/10.1234/test']
    for doi in test_dois:
        is_valid, validated = validate_doi(doi)
        print(f"  {doi} -> {validated} (valid: {is_valid})")

    print("\n" + "=" * 60)
    print("测试完成")