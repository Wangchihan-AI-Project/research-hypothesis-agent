# -*- coding: utf-8 -*-
"""
V7.1 ArXiv 搜索适配器 - 日期过滤贯通版

用于计算机科学、物理、数学等领域的预印本检索。

核心功能：
- 同步和异步检索支持
- 指数退避重试机制
- 结构化结果解析
- ArXiv ID 验证
- V7.1 新增：日期过滤支持
"""

import re
import xml.etree.ElementTree as ET
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


# ==================== ArXiv API 配置 ====================

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ARXIV_BASE_URL = "https://arxiv.org/abs/"

# ArXiv 分类代码
ARXIV_CATEGORIES = {
    'cs.AI': 'Artificial Intelligence',
    'cs.LG': 'Machine Learning',
    'cs.CL': 'Computation and Language',
    'cs.CV': 'Computer Vision',
    'cs.NE': 'Neural and Evolutionary Computing',
    'cs.RO': 'Robotics',
    'cs.SE': 'Software Engineering',
    'cs.DB': 'Databases',
    'cs.DC': 'Distributed Computing',
    'cs.CR': 'Cryptography and Security',
    'cs.IR': 'Information Retrieval',
    'physics': 'Physics (General)',
    'astro-ph': 'Astrophysics',
    'cond-mat': 'Condensed Matter',
    'gr-qc': 'General Relativity',
    'hep-th': 'High Energy Physics - Theory',
    'math': 'Mathematics',
    'stat': 'Statistics',
}


# ==================== ArXiv ID 格式验证 ====================

# ArXiv ID 正则模式
ARXIV_ID_PATTERNS = [
    r'(\d{4}\.\d{4,5})',               # 新格式: 2101.12345
    r'([a-z-]+/\d{7})',                # 老格式: hep-th/1234567
    r'([a-z-]+/\d{4}\d+)',             # 变体格式
]


def validate_arxiv_id(arxiv_id: str) -> Tuple[bool, str]:
    """
    验证 ArXiv ID 格式

    Args:
        arxiv_id: ArXiv ID 字符串

    Returns:
        Tuple[bool, str]: (是否有效, 标准化ID)
    """
    # 清理输入
    arxiv_id = arxiv_id.strip().lower()

    # 移除前缀
    for prefix in ['arxiv:', 'arxiv', 'arxiv.org/abs/', 'https://arxiv.org/abs/']:
        if arxiv_id.startswith(prefix):
            arxiv_id = arxiv_id[len(prefix):]

    # 验证格式
    for pattern in ARXIV_ID_PATTERNS:
        match = re.search(pattern, arxiv_id)
        if match:
            validated_id = match.group(1)
            return True, validated_id

    return False, arxiv_id


# ==================== ArXiv 搜索结果数据类 ====================

@dataclass
class ArXivSearchResult:
    """
    ArXiv 单篇文献结果
    """
    arxiv_id: str                           # ArXiv ID
    title: str                              # 标题
    authors: List[str] = field(default_factory=list)  # 作者
    abstract: str = ""                      # 摘要
    categories: List[str] = field(default_factory=list)  # 分类
    year: int = 0                           # 发表年份
    month: int = 0                          # 发表月份
    doi: Optional[str] = None               # DOI（如果有）
    journal_ref: Optional[str] = None       # 期刊引用（如果已发表）
    pdf_url: str = ""                       # PDF URL
    abs_url: str = ""                       # 摘要页 URL
    comment: Optional[str] = None           # 作者备注
    primary_category: str = ""              # 主分类
    updated: Optional[str] = None           # 更新时间
    published: Optional[str] = None         # 发布时间

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'arxiv_id': self.arxiv_id,
            'title': self.title,
            'authors': self.authors,
            'abstract': self.abstract,
            'categories': self.categories,
            'year': self.year,
            'month': self.month,
            'doi': self.doi,
            'journal_ref': self.journal_ref,
            'pdf_url': self.pdf_url,
            'abs_url': self.abs_url,
            'comment': self.comment,
            'primary_category': self.primary_category,
            'updated': self.updated,
            'published': self.published,
        }


# ==================== ArXiv 搜索器 ====================

class ArXivSearcher:
    """
    ArXiv 搜索适配器

    支持同步和异步检索，用于计算机科学、物理、数学等领域

    V7.1 新增：日期过滤支持
    """

    # 检索配置
    MAX_RESULTS_DEFAULT = 20
    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # 指数退避基数
    TIMEOUT = 30  # HTTP 超时（秒）
    BATCH_SIZE = 50  # 每次请求最大结果数

    def __init__(
        self,
        max_results: int = None,
        enable_retry: bool = True,
        delay: float = 3.0,  # ArXiv 建议 3 秒间隔
    ):
        """
        初始化 ArXiv 搜索器

        Args:
            max_results: 默认最大结果数
            enable_retry: 是否启用重试
            delay: 请求间隔（ArXiv 建议 3 秒）
        """
        self.max_results = max_results or self.MAX_RESULTS_DEFAULT
        self.enable_retry = enable_retry
        self.delay = delay
        self._last_request_time = 0

    def _build_query(
        self,
        keywords: str,
        categories: List[str] = None,
        start_year: int = None,
        end_year: int = None,
    ) -> str:
        """
        构建 ArXiv API 查询字符串

        V7.1 新增：日期过滤支持

        Args:
            keywords: 搜索关键词
            categories: 限制分类列表
            start_year: 起始年份（V7.1 新增）
            end_year: 结束年份（V7.1 新增）

        Returns:
            str: API 查询字符串
        """
        # 基础关键词查询
        query_parts = []

        # 处理关键词（支持 OR 逻辑）
        keywords = keywords.strip()
        if keywords:
            # 如果包含空格，拆分成多个关键词
            keyword_parts = keywords.split()
            if len(keyword_parts) > 1:
                # 多关键词使用 AND 连接
                query_parts.append(f"all:{keyword_parts[0]}")
                for kw in keyword_parts[1:]:
                    query_parts.append(f"AND all:{kw}")
            else:
                query_parts.append(f"all:{keywords}")

        # 添加分类限制
        if categories:
            cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
            query_parts.append(f"AND ({cat_query})")

        # V7.1 新增：日期过滤（谓词下推到 ArXiv API）
        # ArXiv 支持 submittedDate 范围查询：submittedDate:[YYYYMMDD TO YYYYMMDD]
        if start_year is not None or end_year is not None:
            # 默认年份范围
            s_year = start_year if start_year else 1990
            e_year = end_year if end_year else datetime.now().year
            # 构建日期范围查询字符串
            date_filter = f"submittedDate:[{s_year}0101 TO {e_year}1231]"
            query_parts.append(f"AND {date_filter}")

        return " ".join(query_parts)

    def _filter_by_year(
        self,
        papers: List[ArXivSearchResult],
        start_year: int = None,
        end_year: int = None,
    ) -> List[ArXivSearchResult]:
        """
        V7.1 新增：按年份二次过滤

        用于在 API 谓词下推后，确保结果严格符合年份要求

        Args:
            papers: 论文列表
            start_year: 起始年份
            end_year: 结束年份

        Returns:
            过滤后的论文列表
        """
        if start_year is None and end_year is None:
            return papers

        filtered = []
        for paper in papers:
            year = paper.year
            if year == 0:
                # 年份解析失败，保留（宽松策略）
                filtered.append(paper)
                continue

            # 检查年份范围
            if start_year and year < start_year:
                continue
            if end_year and year > end_year:
                continue

            filtered.append(paper)

        return filtered

    def _parse_arxiv_response(self, xml_content: str) -> List[ArXivSearchResult]:
        """
        解析 ArXiv API XML 响应

        Args:
            xml_content: XML 响应内容

        Returns:
            List[ArXivSearchResult]: 解析后的文献列表
        """
        results = []

        try:
            root = ET.fromstring(xml_content)

            # ArXiv 使用 Atom 命名空间
            ns = {'atom': 'http://www.w3.org/2005/Atom',
                  'arxiv': 'http://arxiv.org/schemas/atom'}

            # 解析每个 entry
            for entry in root.findall('atom:entry', ns):
                # ArXiv ID
                id_url = entry.find('atom:id', ns)
                arxiv_id = ""
                if id_url is not None:
                    # 从 URL 提取 ID
                    id_text = id_url.text
                    if 'arxiv.org/abs/' in id_text:
                        arxiv_id = id_text.split('/abs/')[-1]

                # 标题
                title_elem = entry.find('atom:title', ns)
                title = title_elem.text.strip() if title_elem is not None else ""

                # 作者
                authors = []
                for author in entry.findall('atom:author', ns):
                    name = author.find('atom:name', ns)
                    if name is not None:
                        authors.append(name.text)

                # 摘要
                abstract_elem = entry.find('atom:summary', ns)
                abstract = abstract_elem.text.strip() if abstract_elem is not None else ""

                # 分类
                categories = []
                primary_category = ""
                for cat in entry.findall('atom:category', ns):
                    cat_term = cat.get('term', '')
                    categories.append(cat_term)

                # 主分类
                primary_cat = entry.find('arxiv:primary_category', ns)
                if primary_cat is not None:
                    primary_category = primary_cat.get('term', '')

                # 发布时间
                published = entry.find('atom:published', ns)
                published_text = published.text if published is not None else ""

                # 解析年份和月份
                year = 0
                month = 0
                if published_text:
                    try:
                        dt = datetime.fromisoformat(published_text.replace('Z', '+00:00'))
                        year = dt.year
                        month = dt.month
                    except Exception:
                        pass

                # 更新时间
                updated = entry.find('atom:updated', ns)
                updated_text = updated.text if updated is not None else ""

                # DOI
                doi_ref = entry.find('arxiv:doi', ns)
                doi = doi_ref.text if doi_ref is not None else None

                # 期刊引用
                journal_ref = entry.find('arxiv:journal_ref', ns)
                journal_ref_text = journal_ref.text if journal_ref is not None else None

                # PDF URL
                pdf_url = ""
                for link in entry.findall('atom:link', ns):
                    if link.get('title') == 'pdf':
                        pdf_url = link.get('href', '')

                # 摘要页 URL
                abs_url = f"https://arxiv.org/abs/{arxiv_id}"

                # 备注
                comment = entry.find('arxiv:comment', ns)
                comment_text = comment.text if comment is not None else None

                # 构建结果对象
                result = ArXivSearchResult(
                    arxiv_id=arxiv_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    categories=categories,
                    year=year,
                    month=month,
                    doi=doi,
                    journal_ref=journal_ref_text,
                    pdf_url=pdf_url,
                    abs_url=abs_url,
                    comment=comment_text,
                    primary_category=primary_category,
                    updated=updated_text,
                    published=published_text,
                )

                results.append(result)

        except ET.ParseError as e:
            logger.error(f"[ArXiv] XML parsing error: {e}")

        return results

    def search(
        self,
        query: str,
        max_results: int = None,
        categories: List[str] = None,
        sort_by: str = 'relevance',
        start_year: int = None,
        end_year: int = None,
    ) -> Dict:
        """
        同步搜索 ArXiv

        V7.1 新增：日期过滤参数

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            categories: 限制分类（如 ['cs.AI', 'cs.LG']）
            sort_by: 排序方式 ('relevance', 'lastUpdatedDate', 'submittedDate')
            start_year: 起始年份（V7.1 新增）
            end_year: 结束年份（V7.1 新增）

        Returns:
            Dict: 包含 success 和 papers 的结果
        """
        max_results = max_results or self.max_results

        # V7.1: 构建查询（带日期过滤）
        search_query = self._build_query(query, categories, start_year, end_year)

        # V7.1 审计日志：记录原始查询
        date_constraint = f"{start_year}-{end_year}" if start_year or end_year else "all"
        logger.info(f"[ArXiv V7.1] 检索执行约束: Date >= {date_constraint}")
        logger.info(f"[ArXiv V7.1] Raw Query String: '{search_query}'")

        # 排序参数
        sort_map = {
            'relevance': 'relevance',
            'lastUpdatedDate': 'lastUpdatedDate',
            'submittedDate': 'submittedDate',
        }
        sortBy = sort_map.get(sort_by, 'relevance')
        sortOrder = 'descending'

        # 构建 URL
        params = {
            'search_query': search_query,
            'start': 0,
            'max_results': max_results,
            'sortBy': sortBy,
            'sortOrder': sortOrder,
        }

        # 执行请求（带重试）
        for attempt in range(self.MAX_RETRIES):
            try:
                # 遵守 ArXiv API 速率限制（3秒间隔）
                elapsed = time.time() - self._last_request_time
                if elapsed < self.delay:
                    time.sleep(self.delay - elapsed)

                import requests
                response = requests.get(
                    ARXIV_API_URL,
                    params=params,
                    timeout=self.TIMEOUT,
                )

                self._last_request_time = time.time()

                if response.status_code == 200:
                    papers = self._parse_arxiv_response(response.text)

                    # V7.1: 二次年份过滤（确保严格符合要求）
                    if start_year or end_year:
                        original_count = len(papers)
                        papers = self._filter_by_year(papers, start_year, end_year)
                        if original_count != len(papers):
                            logger.info(f"[ArXiv V7.1] 年份二次过滤: {original_count} -> {len(papers)} 篇")

                    logger.info(f"[ArXiv] Search returned {len(papers)} papers")

                    return {
                        'success': True,
                        'papers': [p.to_dict() for p in papers],
                        'query': search_query,
                        'source': 'arxiv',
                        'total': len(papers),
                        # V7.1 审计防伪证字段
                        'audit_info': {
                            'raw_query': search_query,
                            'date_constraint': date_constraint,
                            'papers_found': len(papers),
                            'timestamp': datetime.utcnow().isoformat(),
                        }
                    }

                elif response.status_code == 429:
                    # 速率限制，等待后重试
                    delay = self.BASE_DELAY * (2 ** attempt)
                    logger.warning(f"[ArXiv] Rate limited, retrying in {delay}s")
                    time.sleep(delay)

                else:
                    logger.error(f"[ArXiv] API error: {response.status_code}")
                    return {
                        'success': False,
                        'error': f'API error: {response.status_code}',
                        'papers': [],
                    }

            except requests.exceptions.Timeout:
                logger.warning(f"[ArXiv] Timeout, attempt {attempt + 1}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.BASE_DELAY * (2 ** attempt))

            except Exception as e:
                logger.error(f"[ArXiv] Search error: {e}")
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
        categories: List[str] = None,
        sort_by: str = 'relevance',
        start_year: int = None,
        end_year: int = None,
    ) -> Dict:
        """
        异步搜索 ArXiv

        V7.1 新增：日期过滤参数

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            categories: 限制分类
            sort_by: 排序方式
            start_year: 起始年份（V7.1 新增）
            end_year: 结束年份（V7.1 新增）

        Returns:
            Dict: 搜索结果
        """
        max_results = max_results or self.max_results

        # V7.1: 构建查询（带日期过滤）
        search_query = self._build_query(query, categories, start_year, end_year)

        # V7.1 审计日志
        date_constraint = f"{start_year}-{end_year}" if start_year or end_year else "all"
        logger.info(f"[ArXiv V7.1 Async] 检索执行约束: Date >= {date_constraint}")
        logger.info(f"[ArXiv V7.1 Async] Raw Query String: '{search_query}'")

        # 排序参数
        sort_map = {
            'relevance': 'relevance',
            'lastUpdatedDate': 'lastUpdatedDate',
            'submittedDate': 'submittedDate',
        }
        sortBy = sort_map.get(sort_by, 'relevance')
        sortOrder = 'descending'

        # 构建 URL
        params_str = f"search_query={search_query}&start=0&max_results={max_results}&sortBy={sortBy}&sortOrder={sortOrder}"
        url = f"{ARXIV_API_URL}?{params_str}"

        # 异步请求
        for attempt in range(self.MAX_RETRIES):
            try:
                # 遵守速率限制
                await asyncio.sleep(self.delay)

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)) as response:
                        if response.status == 200:
                            xml_content = await response.text()
                            papers = self._parse_arxiv_response(xml_content)

                            # V7.1: 二次年份过滤
                            if start_year or end_year:
                                original_count = len(papers)
                                papers = self._filter_by_year(papers, start_year, end_year)
                                if original_count != len(papers):
                                    logger.info(f"[ArXiv V7.1 Async] 年份二次过滤: {original_count} -> {len(papers)} 篇")

                            logger.info(f"[ArXiv Async] Search returned {len(papers)} papers")

                            return {
                                'success': True,
                                'papers': [p.to_dict() for p in papers],
                                'query': search_query,
                                'source': 'arxiv',
                                'total': len(papers),
                                # V7.1 审计防伪证字段
                                'audit_info': {
                                    'raw_query': search_query,
                                    'date_constraint': date_constraint,
                                    'papers_found': len(papers),
                                    'timestamp': datetime.utcnow().isoformat(),
                                }
                            }

                        elif response.status == 429:
                            delay = self.BASE_DELAY * (2 ** attempt)
                            logger.warning(f"[ArXiv Async] Rate limited, retrying in {delay}s")
                            await asyncio.sleep(delay)

                        else:
                            logger.error(f"[ArXiv Async] API error: {response.status}")
                            return {
                                'success': False,
                                'error': f'API error: {response.status}',
                                'papers': [],
                            }

            except asyncio.TimeoutError:
                logger.warning(f"[ArXiv Async] Timeout, attempt {attempt + 1}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.BASE_DELAY * (2 ** attempt))

            except Exception as e:
                logger.error(f"[ArXiv Async] Search error: {e}")
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

    def fetch_by_id(self, arxiv_id: str) -> Dict:
        """
        根据 ArXiv ID 获取单篇文献

        Args:
            arxiv_id: ArXiv ID

        Returns:
            Dict: 文献信息
        """
        # 验证 ID
        is_valid, validated_id = validate_arxiv_id(arxiv_id)

        if not is_valid:
            return {
                'success': False,
                'error': f'Invalid ArXiv ID: {arxiv_id}',
            }

        # 构建 ID 查询
        query = f"id:{validated_id}"

        result = self.search(query, max_results=1)

        if result['success'] and result['papers']:
            return {
                'success': True,
                'paper': result['papers'][0],
            }

        return {
            'success': False,
            'error': 'Paper not found',
        }


# ==================== 便捷函数 ====================

def search_arxiv(query: str, max_results: int = 20, start_year: int = None, end_year: int = None) -> Dict:
    """
    快捷 ArXiv 搜索函数

    V7.1 新增：日期过滤参数

    Args:
        query: 搜索关键词
        max_results: 最大结果数
        start_year: 起始年份（V7.1 新增）
        end_year: 结束年份（V7.1 新增）

    Returns:
        Dict: 搜索结果
    """
    searcher = ArXivSearcher()
    return searcher.search(query, max_results=max_results, start_year=start_year, end_year=end_year)


async def search_arxiv_async(query: str, max_results: int = 20, start_year: int = None, end_year: int = None) -> Dict:
    """
    快捷异步 ArXiv 搜索函数

    V7.1 新增：日期过滤参数

    Args:
        query: 搜索关键词
        max_results: 最大结果数
        start_year: 起始年份（V7.1 新增）
        end_year: 结束年份（V7.1 新增）

    Returns:
        Dict: 搜索结果
    """
    searcher = ArXivSearcher()
    return await searcher.search_async(query, max_results=max_results, start_year=start_year, end_year=end_year)


# ==================== 测试 ====================

if __name__ == '__main__':
    print("=" * 60)
    print("V7.1 ArXiv 搜索适配器 - 测试")
    print("=" * 60)

    searcher = ArXivSearcher()

    # 测试搜索
    print("\n测试 1: 搜索 'deep learning' (2020-2026)")
    result = searcher.search("deep learning", max_results=5, start_year=2020, end_year=2026)

    if result['success']:
        print(f"找到 {len(result['papers'])} 篇文献")
        for paper in result['papers'][:2]:
            print(f"  - {paper['arxiv_id']}: {paper['title'][:50]}... (year={paper['year']})")
        print(f"审计信息: {result.get('audit_info', {})}")
    else:
        print(f"搜索失败: {result['error']}")

    # 测试 ID 验证
    print("\n测试 2: ArXiv ID 验证")
    test_ids = ['2101.12345', 'arxiv:2101.12345', 'https://arxiv.org/abs/2101.12345']
    for test_id in test_ids:
        is_valid, validated = validate_arxiv_id(test_id)
        print(f"  {test_id} -> {validated} (valid: {is_valid})")

    print("\n" + "=" * 60)
    print("测试完成")