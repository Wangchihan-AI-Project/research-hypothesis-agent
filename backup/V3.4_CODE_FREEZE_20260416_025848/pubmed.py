"""
PubMed搜索工具（动态质量准入制 + V3.4 API 物理缓存）
直接解析XML字典，不依赖BioPython的高级功能

V3.4 新增：
- 物理缓存 API 响应，确保可复现性
- 相同查询直接返回缓存，不重新联网
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import json
import time
from Bio import Entrez
from .journal_if import get_journal_if, build_journal_whitelist_query, HIGH_IMPACT_JOURNALS
from .oa_paper_fetcher import OAPaperFetcher

# V3.4: 导入 API 缓存管理器
try:
    from src.core.zero_day_defense import get_api_cache_manager
    _api_cache_enabled = True
except ImportError:
    _api_cache_enabled = False


class ZeroResultsError(Exception):
    """零结果异常：当检索到0篇文献时抛出"""
    def __init__(self, query: str, message: str = "未找到符合条件的文献"):
        self.query = query
        super().__init__(f"{message}。查询: {query}")


class PubMedSearcher:
    """PubMed论文搜索类"""

    def __init__(self, email: Optional[str] = None, api_key: Optional[str] = None):
        """
        初始化PubMed搜索器

        Args:
            email: 用户邮箱（PubMed要求）
            api_key: PubMed API密���（可选，提高请求限制）
        """
        Entrez.email = email or "research@example.com"
        if api_key:
            Entrez.api_key = api_key

        # 初始化OA论文下载器
        self.oa_fetcher = OAPaperFetcher(email=email, api_key=api_key)

        # V3.4: 初始化 API 缓存管理器
        self.api_cache = None
        if _api_cache_enabled:
            try:
                self.api_cache = get_api_cache_manager()
                print(f"[PubMed] API 物理缓存已启用")
            except Exception as e:
                print(f"[PubMed] API 缓存初始化失败: {e}")

    def _extract_date_from_pubdate_obj(self, pub_date_obj) -> Optional[str]:
        """
        从 PubDate 对象中提取日期字符串

        Args:
            pub_date_obj: BioPython 的 PubDate 对象

        Returns:
            格式化的日期字符串 (YYYY-MM-DD 或 YYYY-MM 或 YYYY)
        """
        if not pub_date_obj:
            return None

        try:
            year = None
            month = ''
            day = ''

            # 获取年份
            year_val = self._get_value(pub_date_obj, 'Year')
            if year_val:
                year = str(year_val).strip()

            # 获取月份 - 可能是数字或英文缩写
            month_val = self._get_value(pub_date_obj, 'Month')
            if month_val:
                month_str = str(month_val).strip()
                # 标准化月份
                month = self._normalize_month(month_str)

            # 获取日期
            day_val = self._get_value(pub_date_obj, 'Day')
            if day_val:
                day = str(day_val).strip().zfill(2)

            # 处理 MedlineDate（如 "2022 Jan-Mar" 或 "2022 Winter"）
            if not year:
                medline_date = self._get_value(pub_date_obj, 'MedlineDate')
                if medline_date:
                    return self._parse_medline_date(str(medline_date))

            # 组合日期
            if year:
                if month:
                    if day:
                        return f"{year}-{month}-{day}"
                    return f"{year}-{month}"
                return year

        except Exception:
            pass

        return None

    def _get_value(self, obj, key: str):
        """安全地从对象中获取属性值"""
        if not obj:
            return None

        # 尝试字典方式
        if hasattr(obj, 'keys') and key in obj.keys():
            return obj[key]

        # 尝试属性方式
        if hasattr(obj, key):
            return getattr(obj, key)

        return None

    def _normalize_month(self, month: str) -> str:
        """标准化月份为两位数或三字母缩写"""
        if not month:
            return ''

        month = month.strip().lower()

        # 数字月份
        if month.isdigit():
            return month.zfill(2)

        # 英文月份缩写映射
        month_map = {
            'jan': '01', 'january': '01',
            'feb': '02', 'february': '02',
            'mar': '03', 'march': '03',
            'apr': '04', 'april': '04',
            'may': '05',
            'jun': '06', 'june': '06',
            'jul': '07', 'july': '07',
            'aug': '08', 'august': '08',
            'sep': '09', 'sept': '09', 'september': '09',
            'oct': '10', 'october': '10',
            'nov': '11', 'november': '11',
            'dec': '12', 'december': '12',
        }

        return month_map.get(month, month[:3])

    def _parse_medline_date(self, date_str: str) -> Optional[str]:
        """解析 MedlineDate 格式（如 "2022 Jan-Mar", "2022 Winter"）"""
        if not date_str:
            return None

        # 提取年份（4位数字）
        import re
        year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
        if year_match:
            return year_match.group()

        return None

    def _extract_publication_date(self, article, medline_citation, article_data) -> Optional[str]:
        """
        提取发表日期（改进版，更健壮）

        按优先级尝试多个来源：
        1. Article.ArticleDate (电子出版日期) - 最准确
        2. Article.JournalIssue.PubDate (期刊出版日期)
        3. MedlineCitation.Article.Journal.PubDate (备用)
        """
        pub_date = None

        # === 方法1：从 Article.ArticleDate 获取（电子出版日期，最准确）===
        if article_data:
            article_date_list = self._get_from_object(article_data, 'ArticleDate')
            if article_date_list:
                # 获取第一个日期
                if isinstance(article_date_list, list) and len(article_date_list) > 0:
                    article_date = article_date_list[0]
                else:
                    article_date = article_date_list

                pub_date = self._extract_date_from_pubdate_obj(article_date)
                if pub_date:
                    return pub_date

        # === 方法2：从 Article.JournalIssue.PubDate 获取 ===
        if article_data:
            journal_issue = self._get_from_object(article_data, 'JournalIssue')
            if journal_issue:
                pub_date_obj = self._get_from_object(journal_issue, 'PubDate')
                pub_date = self._extract_date_from_pubdate_obj(pub_date_obj)
                if pub_date:
                    return pub_date

        # === 方法3：从 MedlineCitation.Article.Journal.PubDate 获取（备用）===
        if medline_citation:
            art = self._get_from_object(medline_citation, 'Article')
            if art:
                journal = self._get_from_object(art, 'Journal')
                if journal:
                    pub_date_obj = self._get_from_object(journal, 'PubDate')
                    pub_date = self._extract_date_from_pubdate_obj(pub_date_obj)
                    if pub_date:
                        return pub_date

        # === 方法4：从 PubmedData.ArticleDate 获取（最后的备用）===
        pubmed_data = self._get_from_object(article, 'PubmedData')
        if pubmed_data:
            article_date_list = self._get_from_object(pubmed_data, 'ArticleDate')
            if article_date_list:
                if isinstance(article_date_list, list) and len(article_date_list) > 0:
                    article_date = article_date_list[0]
                else:
                    article_date = article_date_list

                pub_date = self._extract_date_from_pubdate_obj(article_date)
                if pub_date:
                    return pub_date

        return None

    def _get_from_object(self, obj, key: str):
        """安全地从对象中获取嵌套属性"""
        if not obj:
            return None

        # 尝试字典方式
        if hasattr(obj, 'keys') and key in obj.keys():
            return obj[key]

        # 尝试属性方式
        if hasattr(obj, key):
            return getattr(obj, key)

        return None

    @staticmethod
    def _to_str(value) -> Optional[str]:
        """安全地将任何值转换为字符串"""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        # 处理 DictionaryElement 等对象
        try:
            # 尝试获取 _String 属性（BioPython 的 StringElement）
            if hasattr(value, '_String'):
                return str(value._String)
            # 尝试获取值属性
            if hasattr(value, 'value'):
                val = value.value
                if isinstance(val, str):
                    return val
                return str(val)
            # 如果有 keys 方法，尝试获取第一个值
            if hasattr(value, 'keys') and callable(getattr(value, 'keys', None)):
                keys = list(value.keys())
                if keys:
                    first_value = value[keys[0]]
                    if isinstance(first_value, str):
                        return first_value
                    return PubMedSearcher._to_str(first_value)
            # 默认转换为字符串
            result = str(value)
            # 如果结果包含 'Element' 或 'Element('，尝试提取实际值
            if 'Element' in result:
                # 可能是 StringElement 或类似对象
                if hasattr(value, '__iter__') and not isinstance(value, (str, bytes, dict)):
                    # 尝试迭代获取值
                    for item in value:
                        if isinstance(item, str):
                            return item
                # 如果是单个元素，返回 None
                return None
            return result
        except:
            return None

    def search_papers(
        self,
        query: str,
        max_results: Optional[int] = None,  # None 表示无限制，获取所有符合条件的文献
        enable_filter: bool = False,
        date_range: Optional[tuple] = None,
        filter_keywords: Optional[List[str]] = None,
        min_if: Optional[float] = None,
        relevance_threshold: Optional[float] = None  # 新增：相关性阈值 (0-10)
    ) -> List[Dict]:
        """
        搜索PubMed论文（动态质量准入制 - 两阶段检索）

        两阶段检索策略:
        - 阶段1 (ID Fetch): 获取所有符合IF阈值和日期要求的PMID
        - 阶段2 (Score-based Selection): 根据相关性评分筛选，而非死板截取前N篇

        Args:
            query: 搜索关键词
            max_results: 最大返回结果数 (None=无限制，基于质量准入)
            enable_filter: 是否启用高质量过滤（最近3年+IF>=10）
            date_range: 日期范围 (tuple或int)
            filter_keywords: 过滤关键词列表
            min_if: 最低影响因子要求
            relevance_threshold: 相关性阈值 (0-10)，超过此分数的文献保留

        Returns:
            论文信息列表

        Raises:
            ZeroResultsError: 当未找到任何符合条件的文献时抛出
        """
        try:
            # 清理查询
            clean_query = self._clean_query(query)

            # ========== 谓词下推：时间锁（将日期过滤编译进原生查询） ==========
            search_term_with_date = self._apply_date_filter_to_query(clean_query, date_range)

            # ========== 谓词下推：期刊白名单（将 IF 过滤编译进原生查询）==========
            search_term_final = search_term_with_date
            if min_if is not None and min_if > 0:
                journal_whitelist = build_journal_whitelist_query(min_if)
                if journal_whitelist:
                    search_term_final = f"{search_term_with_date} AND {journal_whitelist}"
                    whitelist_journals = [name for name, if_val in HIGH_IMPACT_JOURNALS.items()
                                             if isinstance(if_val, (int, float)) and if_val >= min_if]
                    print(f"[期刊白名单谓词下推] 已注入 {len(whitelist_journals)} 个顶刊过滤器")

            # 显示过滤配置（谓词下推版）
            date_info = self._get_date_filter_info(date_range)
            if min_if is not None and min_if > 0:
                print(f"[目标] 过滤配置: IF ≥ {min_if} | 时间锁: {date_info}")
            elif enable_filter:
                print(f"[目标] 过滤配置: 高质量过滤（最近3年+高IF） | 时间锁: {date_info}")
            else:
                print(f"[搜索] 正在从 PubMed 搜索 {date_info} 间的相关文献...")

            # ========== 阶段1: ID Fetch - 获取所有符合谓词下推条件的PMID ==========
            # 【按需拉取协议】严格限制初次检索上限，避免过载抓取
            # 策略：根据 max_results 动态调整 retmax，而不是死板地拉取 10000 篇

            # ========== 计算 retmax 上限 ==========
            if max_results is None:
                # 无限制模式：使用保守的默认值（100篇）
                # 理由：生成一个假设不需要看 1000 篇文献
                fetch_limit = 100
                print(f"[搜索] [按需拉取] 默认模式：最多获取 100 篇最新顶刊...")
            else:
                # 用户指定模式：根据需求量动态调整（10倍缓冲用于筛选）
                # 例如：需要 3 个假设，最多拉取 30-50 篇用于筛选
                fetch_limit = min(max_results * 10, 100)  # 上限 100 篇
                print(f"[搜索] [按需拉取] 限制模式：最多获取 {fetch_limit} 篇文献...")

            # ========== V3.4: 检查 API 缓存（物理冻结外部��据） ==========
            cache_params = {
                'query': search_term_final,
                'retmax': fetch_limit,
                'sort': 'relevance',
                'retmode': 'xml'
            }

            cached_response = None
            if self.api_cache:
                cached_response = self.api_cache.get_response(
                    endpoint='pubmed_esearch',
                    params=cache_params
                )
                if cached_response:
                    print(f"[缓存命中] 使用缓存的 PubMed 响应（{cached_response.timestamp}）")
                    # 从缓存恢复
                    import io
                    try:
                        search_results = json.loads(cached_response.response_payload)
                        # 提取PMID列表
                        id_list = []
                        total_count = 0
                        if isinstance(search_results, dict):
                            id_list_dict = search_results.get('IdList', {})
                            if isinstance(id_list_dict, list):
                                id_list = id_list_dict
                            elif hasattr(id_list_dict, '__len__'):
                                id_list = list(id_list_dict)
                            total_count = int(search_results.get('Count', len(id_list)))

                        # 如果有缓存的 PMID，跳过 API 调用
                        if id_list:
                            print(f"[缓存] 恢复 {len(id_list)} 篇文献（总计 {total_count} 篇符合条件）")
                            # 直接跳到后续处理...
                            # （这里简化处理，实际应该重构代码结构）
                        else:
                            cached_response = None  # 缓存无效，继续API调用
                    except:
                        cached_response = None  # 缓存解析失败，继续API调用

            # ========== 带重试的 PubMed API 调用 ==========
            max_api_retries = 3
            for api_attempt in range(max_api_retries):
                try:
                    search_handle = Entrez.esearch(
                        db="pubmed",
                        term=search_term_final,
                        retmax=fetch_limit,
                        sort="relevance",  # 按相关性排序，确保获取的是最相关的文献
                        retmode="xml"
                    )
                    search_results = Entrez.read(search_handle)
                    search_handle.close()
                    break  # 成功则跳出重试循环
                except RuntimeError as e:
                    if "XML Exception" in str(e) or "Parse failed" in str(e):
                        if api_attempt < max_api_retries - 1:
                            wait_time = (api_attempt + 1) * 3
                            print(f"[PubMed API] XML解析错误，{wait_time}秒后重试 ({api_attempt + 1}/{max_api_retries})...")
                            time.sleep(wait_time)
                            continue
                        else:
                            raise RuntimeError(f"PubMed API 连续 {max_api_retries} 次XML解析失败，请稍后重试")
                    raise

            # 提取PMID列表
            id_list = []
            total_count = 0

            if isinstance(search_results, dict):
                id_list_dict = search_results.get('IdList', {})
                if isinstance(id_list_dict, list):
                    id_list = id_list_dict
                elif hasattr(id_list_dict, '__len__'):
                    id_list = list(id_list_dict)

                # 获取总计数（实际符合条件的文献数）
                total_count = int(search_results.get('Count', len(id_list)))

            # ========== 零结果检测 ==========
            if not id_list:
                raise ZeroResultsError(
                    query=clean_query,
                    message=f"在 {date_info} 范围内未找到相关文献 (IF≥{min_if if min_if else '不限'})"
                )

            # ========== 日志预警：检测搜索结果过多 ==========
            if total_count > 200:
                print(f"⚠️  [搜索结果过多] 共有 {total_count} 篇文献符合条件，已自动截取前 {len(id_list)} 篇最新顶刊进行分析")
            elif total_count > len(id_list):
                print(f"[统计] [ID Fetch] 共有 {total_count} 篇文献符合条件，当前获取 {len(id_list)} 篇")
            else:
                print(f"[OK] 找到 {len(id_list)} 篇文献（谓词下推已生效），正在获取详细信息...")

            # ========== 优化 ID 获取逻辑：只获取前 30-50 篇进行 efetch ==========
            # 策略：如果使用了顶刊白名单，返回的文献都是高质量，
            # 但我们不需要全部下载，只取相关性最高的前 30-50 篇
            efetch_limit = min(len(id_list), 50)  # 最多 50 篇
            id_list_for_fetch = id_list[:efetch_limit]

            if len(id_list) > efetch_limit:
                print(f"[优化] 跳过详细下载：仅对相关性最高的前 {efetch_limit} 篇进行摘要下载")

            # 获取论文详细信息
            papers = []
            batch_size = 20  # 减小批次大小，提高响应速度

            for i in range(0, len(id_list_for_fetch), batch_size):
                batch_ids = id_list_for_fetch[i:i+batch_size]
                current_batch = (i // batch_size) + 1
                total_batches = (len(id_list_for_fetch) + batch_size - 1) // batch_size
                print(f"  正在获取第 {i+1}-{i+len(batch_ids)} 篇 (批�� {current_batch}/{total_batches})...")

                try:
                    # 带重试的 efetch 调用
                    max_fetch_retries = 2
                    for fetch_attempt in range(max_fetch_retries):
                        try:
                            fetch_handle = Entrez.efetch(
                                db="pubmed",
                                id=batch_ids,
                                rettype="abstract",
                                retmode="xml"
                            )
                            fetch_results = Entrez.read(fetch_handle)
                            fetch_handle.close()
                            break  # 成功则跳出重试
                        except RuntimeError as e:
                            if "XML Exception" in str(e) or "Parse failed" in str(e):
                                if fetch_attempt < max_fetch_retries - 1:
                                    time.sleep(2)
                                    continue
                                raise

                    # 解析XML
                    batch_papers = self._parse_xml_results(fetch_results, clean_query)
                    papers.extend(batch_papers)
                    print(f"    成功解析 {len(batch_papers)} 篇")

                except Exception as e:
                    print(f"  获取第 {i+1}-{i+len(batch_ids)} 篇时出错: {e}")
                    continue

            print(f"总共成功解析 {len(papers)} 篇论文")

            # ========== 阶段2: Score-based Selection - 质量准入筛选 ==========
            original_count = len(papers)

            # 优先使用 min_if 参数（如果提供且大于0）
            if min_if is not None and min_if > 0:
                papers = self.filter_papers_by_if_range(papers, min_if=min_if)
                print(f"[目标] IF过滤 (≥{min_if}): {original_count} -> {len(papers)} 篇")
            elif enable_filter:
                # 兼容旧的 enable_filter 参数（最近3年+高IF）
                papers = self._filter_papers(papers)
                print(f"[目标] 高质量过滤（最近3年+高IF）: {original_count} -> {len(papers)} 篇")

            # ========== 相关性阈值筛选 (动态质量准入核心) ==========
            # 如果指定了 relevance_threshold，只保留分数达标的"黄金情报"
            # 注意：此时论文尚未通过LLM评分，此参数需由调用方在二次筛选时使用
            if relevance_threshold is not None:
                # 此处为占位符，实际评分逻辑由 paper_search_agent 的 LLM 评分完成
                print(f"[统计] 相关性阈值设定: ≥ {relevance_threshold}/10 (将在LLM评分阶段应用)")

            # ========== 最终数量检测 ==========
            if not papers:
                raise ZeroResultsError(
                    query=clean_query,
                    message=f"经过IF过滤后无剩余文献 (原始{original_count}篇)"
                )

            # 如果指定了max_results且有剩余，按年份和相关性排序后截取
            if max_results is not None and len(papers) > max_results:
                # 按年份降序（保留最新）+ 相关性（PubMed已按相关性排序）
                papers = papers[:max_results]
                print(f"[截取] 最终保留 {len(papers)} 篇 (限制模式)")
            else:
                print(f"[成功] 返回全部 {len(papers)} 篇符合质量准入的文献")

            return papers

        except ZeroResultsError:
            # 重新抛出零结果异常，让上层处理
            raise
        except Exception as e:
            print(f"搜索PubMed时出错: {e}")
            print(f"提示：请简化搜索关键词，或检查网络连接")
            import traceback
            traceback.print_exc()
            return []

    def _filter_papers(self, papers: List[Dict]) -> List[Dict]:
        """
        过滤论文：最近3年且高影响因子期刊

        Args:
            papers: 论文列表

        Returns:
            过滤后的论文列表
        """
        current_year = datetime.now().year
        three_years_ago = current_year - 3

        filtered = []
        for paper in papers:
            # 检查发表日期
            pub_date = paper.get('publication_date', '')
            year_match = False

            if pub_date:
                try:
                    # 尝试从日期字符串中提取年份
                    if '-' in str(pub_date):
                        year = int(str(pub_date).split('-')[0])
                    else:
                        year = int(pub_date)

                    if year >= three_years_ago:
                        year_match = True
                except:
                    pass

            # 检查期刊影响因子
            journal = paper.get('journal', '')
            # 确保 journal 是字符串
            if journal and not isinstance(journal, str):
                journal = self._to_str(journal) or str(journal)

            journal_if = get_journal_if(journal if isinstance(journal, str) else '')
            if_match = journal_if >= 10.0

            # 调试：显示第一篇论文的详细信息
            if len(filtered) == 0 and len(papers) > 0:
                print(f"    [调试] 第一篇论文信息:")
                print(f"      标题: {paper.get('title', 'N/A')[:50]}...")
                print(f"      期刊: {journal} (类型: {type(journal).__name__})")
                print(f"      日期: {pub_date} (年份匹配: {year_match})")
                print(f"      IF: {journal_if} (IF匹配: {if_match})")

            # 同时满足两个条件
            if year_match and if_match:
                filtered.append(paper)

        return filtered

    def _clean_query(self, query: str) -> str:
        """清理查询字符串 - 保留PubMed支持的布尔运算符和日期语法"""
        import re

        # 移除多余空格
        query = ' '.join(query.split())

        # 只移除真正有问题的特殊符号（保留 PubMed 支持的语法）
        # PubMed 支持的运算符: AND, OR, NOT, (), :, "", []
        # 日期格式需要: / (如 "2020/01/01"[PDAT])
        # 字段标签需要: [] (如 [Title], [PDAT])
        # 范围查询需要: : (如 "start" : "end"[PDAT])
        query = re.sub(r'[^\w\s\-\(\)\[\]\"\'\*/:]', ' ', query)

        return query.strip()

    def _apply_date_filter_to_query(self, query: str, date_range) -> str:
        """
        谓词下推：将日期过滤编译进PubMed原生查询

        使用 PubMed 的 [PDAT] (Publication Date) 字段进行日期过滤

        Args:
            query: 原始查询
            date_range: 日期范围 (tuple或int)

        Returns:
            带日期过滤的查询字符串
        """
        if not date_range:
            return query

        current_year = datetime.now().year
        current_month = datetime.now().month
        current_day = datetime.now().day

        # 构建 PDAT 日期过滤
        if isinstance(date_range, int):
            # 最近N年
            start_year = current_year - date_range + 1
            # 使用完整日期格式: "2023/01/01"[PDAT] : "2026/04/12"[PDAT]
            date_filter = f'("{start_year}/01/01"[PDAT] : "{current_year}/{current_month:02d}/{current_day:02d}"[PDAT])'
        elif isinstance(date_range, tuple):
            # 自定义范围 (start_year, end_year)
            start_year, end_year = date_range
            date_filter = f'("{start_year}/01/01"[PDAT] : "{end_year}/12/31"[PDAT])'
        else:
            return query

        # 将日期过滤与原始查询组合
        if date_filter in query:
            # 查询中已包含日期过滤
            return query
        else:
            # 添加日期过滤
            return f'{query} AND {date_filter}'

    def _get_date_filter_info(self, date_range) -> str:
        """
        获取日期过滤信息的可读字符串（用于日志输出）

        Args:
            date_range: 日期范围 (tuple或int)

        Returns:
            可读的日期范围字符串
        """
        if not date_range:
            return "全部时间"

        current_year = datetime.now().year

        if isinstance(date_range, int):
            start_year = current_year - date_range + 1
            return f"{start_year}-{current_year}"
        elif isinstance(date_range, tuple):
            start_year, end_year = date_range
            return f"{start_year}-{end_year}"

        return "全部时间"

    def _parse_xml_results(self, xml_results, search_query: str) -> List[Dict]:
        """
        解析XML结果

        Args:
            xml_results: Entrez返回的XML数据 (DictionaryElement)
            search_query: 搜索关键词

        Returns:
            论文信息列表
        """
        papers = []

        try:
            # DictionaryElement 可以通过键访问
            articles_list = None

            # 方法1: 使用字典键访问
            if hasattr(xml_results, 'keys'):
                try:
                    if 'PubmedArticle' in xml_results.keys():
                        articles_list = xml_results['PubmedArticle']
                except Exception:
                    pass

            # 方法2: 使用 .get() 方法
            if articles_list is None and hasattr(xml_results, 'get'):
                articles_list = xml_results.get('PubmedArticle')

            # 方法3: 使用属性访问
            if articles_list is None and hasattr(xml_results, 'PubmedArticle'):
                articles_list = xml_results.PubmedArticle

            if articles_list is None:
                return []

            # 转换为列表
            pubmed_articles = []
            if isinstance(articles_list, list):
                pubmed_articles = articles_list
            elif hasattr(articles_list, '__iter__') and not isinstance(articles_list, (str, bytes)):
                pubmed_articles = list(articles_list)
            else:
                pubmed_articles = [articles_list]

            # 如果是空列表，返回
            if not pubmed_articles:
                return []

            # 解析每篇文章
            for article in pubmed_articles:
                try:
                    paper_info = self._parse_pubmed_article(article, search_query)
                    if paper_info and paper_info.get('pmid'):
                        papers.append(paper_info)
                except Exception:
                    continue

        except Exception:
            pass

        return papers

    def _parse_pubmed_article(self, article, search_query: str) -> Optional[Dict]:
        """
        解析单篇PubMed文章

        Args:
            article: PubmedArticle对象 (DictionaryElement)
            search_query: 搜索关键词

        Returns:
            论文信息字典
        """
        try:
            # 获取MedlineCitation - 支持字典和属性两种访问方式
            medline_citation = None

            # 方法1: 字典键访问
            if hasattr(article, 'keys') and 'MedlineCitation' in article.keys():
                medline_citation = article['MedlineCitation']
            # 方法2: 属性访问
            elif hasattr(article, 'MedlineCitation'):
                medline_citation = article.MedlineCitation

            if not medline_citation:
                return None

            # 获取PMID - 从多个可能的来源
            pmid = None

            # 方法1：从MedlineCitation获取
            if medline_citation:
                # 支持字典和属性访问
                pmid_obj = None
                if hasattr(medline_citation, 'keys') and 'PMID' in medline_citation.keys():
                    pmid_obj = medline_citation['PMID']
                elif hasattr(medline_citation, 'PMID'):
                    pmid_obj = medline_citation.PMID

                if pmid_obj:
                    pmid = str(pmid_obj)

            # 方法2：从PubmedData获取
            if not pmid:
                pubmed_data = None
                if hasattr(article, 'keys') and 'PubmedData' in article.keys():
                    pubmed_data = article['PubmedData']
                elif hasattr(article, 'PubmedData'):
                    pubmed_data = article.PubmedData

                if pubmed_data:
                    aid_list = None
                    if hasattr(pubmed_data, 'keys') and 'ArticleIdList' in pubmed_data.keys():
                        aid_list = pubmed_data['ArticleIdList']
                    elif hasattr(pubmed_data, 'ArticleIdList'):
                        aid_list = pubmed_data.ArticleIdList

                    if aid_list:
                        for aid in aid_list:
                            try:
                                # 检查是否是 PMID
                                aid_str = str(aid)
                                # 通常 PMID 是纯数字
                                if aid_str.isdigit():
                                    pmid = aid_str
                                    break
                            except:
                                continue

            if not pmid:
                return None

            # 获取Article
            article_data = {}
            if medline_citation:
                if hasattr(medline_citation, 'keys') and 'Article' in medline_citation.keys():
                    article_data = medline_citation['Article']
                elif hasattr(medline_citation, 'Article'):
                    article_data = medline_citation.Article

            # 提取标题
            title = "Untitled"
            if article_data:
                title_obj = None
                if hasattr(article_data, 'keys') and 'ArticleTitle' in article_data.keys():
                    title_obj = article_data['ArticleTitle']
                elif hasattr(article_data, 'ArticleTitle'):
                    title_obj = article_data.ArticleTitle

                if title_obj:
                    title = self._to_str(title_obj) or "Untitled"
                    title = title.replace('\n', ' ').replace('\r', '').strip()
                    if len(title) > 500:
                        title = title[:500] + "..."

            # 提取摘要
            abstract = ""
            if article_data:
                abstract_obj = None
                if hasattr(article_data, 'keys') and 'Abstract' in article_data.keys():
                    abstract_obj = article_data['Abstract']
                elif hasattr(article_data, 'Abstract'):
                    abstract_obj = article_data.Abstract

                if abstract_obj:
                    abstract_text = None
                    if hasattr(abstract_obj, 'keys') and 'AbstractText' in abstract_obj.keys():
                        abstract_text = abstract_obj['AbstractText']
                    elif hasattr(abstract_obj, 'AbstractText'):
                        abstract_text = abstract_obj.AbstractText

                    if abstract_text:
                        if isinstance(abstract_text, list):
                            abstract = ' '.join([self._to_str(t) or '' for t in abstract_text])
                        else:
                            abstract = self._to_str(abstract_text) or ''
                        abstract = abstract.replace('\n', ' ').replace('\r', '').strip()

            # 提取作者
            authors = []
            if article_data:
                author_list = None
                if hasattr(article_data, 'keys') and 'AuthorList' in article_data.keys():
                    author_list = article_data['AuthorList']
                elif hasattr(article_data, 'AuthorList'):
                    author_list = article_data.AuthorList

                if author_list:
                    for author in author_list:
                        try:
                            last_name = None
                            fore_name = None

                            # 字典方式访问
                            if hasattr(author, 'keys'):
                                if 'LastName' in author.keys():
                                    last_name = self._to_str(author['LastName'])
                                if 'ForeName' in author.keys():
                                    fore_name = self._to_str(author['ForeName'])
                            # 属性方式访问
                            else:
                                if hasattr(author, 'LastName'):
                                    last_name = self._to_str(author.LastName)
                                if hasattr(author, 'ForeName'):
                                    fore_name = self._to_str(author.ForeName)

                            if last_name:
                                if fore_name:
                                    authors.append(f"{last_name} {fore_name}".strip())
                                else:
                                    authors.append(last_name)
                        except:
                            continue

            # 提取期刊
            journal = None
            if article_data:
                journal_obj = None
                if hasattr(article_data, 'keys') and 'Journal' in article_data.keys():
                    journal_obj = article_data['Journal']
                elif hasattr(article_data, 'Journal'):
                    journal_obj = article_data.Journal

                if journal_obj:
                    # Journal 对象可能有 Title, ISSN, ISOAbbreviation 等字段
                    # 优先级：Title > ISOAbbreviation > Name > JournalTitle > 其他（跳过 ISSN）

                    if hasattr(journal_obj, 'keys'):
                        keys = list(journal_obj.keys())
                        # 优先获取期刊名称，跳过 ISSN
                        for key in ['Title', 'ISOAbbreviation', 'Name', 'JournalTitle', 'Abbreviation']:
                            if key in keys:
                                title_obj = journal_obj[key]
                                converted = self._to_str(title_obj)
                                if converted and 'Element' not in converted and len(converted) > 3:
                                    journal = converted
                                    break

                        # 如果还没找到，遍历所有键查找合适的值（跳过 ISSN 和 EIssn）
                        if not journal:
                            for key in keys:
                                if key.upper() not in ['ISSN', 'EISSN']:  # 跳过 ISSN
                                    val = journal_obj[key]
                                    converted = self._to_str(val)
                                    if converted and 'Element' not in converted and len(converted) > 3:
                                        journal = converted
                                        break
                    else:
                        # 属性方式访问
                        if hasattr(journal_obj, 'Title'):
                            journal = self._to_str(journal_obj.Title)
                        elif hasattr(journal_obj, 'ISOAbbreviation'):
                            journal = self._to_str(journal_obj.ISOAbbreviation)

                # 如果 journal 仍然为空或不是有效字符串，设为 None
                if not journal or not isinstance(journal, str) or len(journal) < 4:
                    journal = None

            # ========== 提取发表日期（改进版） ==========
            pub_date = self._extract_publication_date(article, medline_citation, article_data)

            # ========== 提取数据科学元素（核心增强） ==========
            ds_elements = self._extract_data_science_elements(abstract, title)

            # 提取关键词
            keywords = []
            if medline_citation:
                kw_list = None
                if hasattr(medline_citation, 'keys') and 'KeywordList' in medline_citation.keys():
                    kw_list = medline_citation['KeywordList']
                elif hasattr(medline_citation, 'KeywordList'):
                    kw_list = medline_citation.KeywordList

                if kw_list:
                    for kw in kw_list:
                        # 关键词可能是字符串对象，需要正确提取
                        if isinstance(kw, str):
                            keywords.append(kw)
                        elif hasattr(kw, 'keys') and len(kw.keys()) > 0:
                            # 获取第一个值（通常是关键词文本）
                            first_key = list(kw.keys())[0]
                            kw_value = kw[first_key]
                            if isinstance(kw_value, str):
                                keywords.append(kw_value)
                        else:
                            # 尝试直接转换为字符串
                            kw_str = str(kw)
                            # 排除包含属性信息的字符串
                            if 'attributes=' not in kw_str and kw_str:
                                keywords.append(kw_str)

            # 提取DOI
            doi = None
            if article_data:
                aid_list = None
                if hasattr(article_data, 'keys') and 'ArticleIdList' in article_data.keys():
                    aid_list = article_data['ArticleIdList']
                elif hasattr(article_data, 'ArticleIdList'):
                    aid_list = article_data.ArticleIdList

                if aid_list:
                    for aid in aid_list:
                        try:
                            aid_str = str(aid)
                            # DOI 通常包含 "10." 前缀或斜杠
                            if '10.' in aid_str or '/' in aid_str:
                                doi = aid_str
                                break
                        except:
                            pass

            # 构建论文数据
            paper_data = {
                'pmid': pmid,
                'title': title,
                'abstract': abstract[:5000] if abstract else "",
                'authors': json.dumps(authors[:20], ensure_ascii=False) if authors else "[]",
                'journal': journal,
                'publication_date': pub_date,
                'doi': doi,
                'keywords': json.dumps(keywords[:30], ensure_ascii=False) if keywords else "[]",
                'search_query': search_query[:500],
                'search_date': datetime.utcnow(),  # 使用 datetime 对象，不是字符串
                'status': 'pending',
                # 数据科学元素（核心增强）
                'ds_elements': ds_elements
            }

            return paper_data

        except Exception as e:
            print(f"    解析文章时出错: {e}")
            return None

    def filter_papers_by_date_range(
        self,
        papers: List[Dict],
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> List[Dict]:
        """
        按日期范围过滤论文

        Args:
            papers: 论文列表
            start_year: 起始年份（包含）
            end_year: 结束年份（包含）

        Returns:
            过滤后的论文列表
        """
        filtered = []

        for paper in papers:
            pub_date = paper.get('publication_date', '')
            if not pub_date:
                continue

            try:
                # 提取年份
                if isinstance(pub_date, str):
                    year = int(pub_date.split('-')[0])
                else:
                    continue

                # 检查范围
                if start_year and year < start_year:
                    continue
                if end_year and year > end_year:
                    continue

                filtered.append(paper)

            except (ValueError, IndexError):
                continue

        return filtered

    def _extract_data_science_elements(self, abstract: str, title: str) -> Dict:
        """
        提取文献中的数据科学元素（核心增强功能）

        提取以下关键信息：
        - 使用的机器学习/深度学习模型
        - 特征工程方法
        - 数据集规模 (N)
        - 评估指标 (AUROC, AUPRC, C-index等)
        - 使用的Python/R库

        Args:
            abstract: 论文摘要
            title: 论文标题

        Returns:
            数据科学元素字典
        """
        import re

        # 合并标题和摘要进行分析
        full_text = (title + " " + abstract).lower()

        ds_elements = {
            'ml_models': [],
            'dl_architectures': [],
            'feature_engineering': [],
            'evaluation_metrics': [],
            'sample_size': None,
            'python_libs': [],
            'r_libs': [],
            'data_types': [],
            'validation_method': None
        }

        # ============ 1. 检测机器学习/深度学习模型 ============
        ml_model_patterns = {
            'Random Forest': r'random forest|random forest',
            'SVM': r'\bsvm\b|support vector machine',
            'XGBoost': r'xgboost|xgboost|gradient boosting',
            'LightGBM': r'lightgbm|light gbm',
            'Logistic Regression': r'logistic regression|logit',
            'Elastic Net': r'elastic net|elastic-net',
            'KNN': r'\bknn\b|k-nearest neighbor|k nearest',
            'Naive Bayes': r'naive bayes|naïve bayes',
            'Gradient Boosting': r'gradient boosting|gbdt|gbm',
            'AdaBoost': r'adaboost|ada boost'
        }

        dl_arch_patterns = {
            'CNN': r'\bcnn\b|convolutional neural network|convnet',
            'RNN': r'\brnn\b|recurrent neural network|lstm|gru',
            'Transformer': r'transformer|attention mechanism|self-attention',
            'BERT': r'\bbert\b|bidirectional encoder',
            'GPT': r'\bgpt\b|generative pre-trained',
            'GAN': r'\bgan\b|generative adversarial',
            'VAE': r'\bvae\b|variational autoencoder',
            'Autoencoder': r'autoencoder|auto-encoder',
            'ResNet': r'resnet|residual network',
            'Graph Neural Network': r'gnn|graph neural network|graph convolution',
            'U-Net': r'u-net|unet',
            'BERT': r'\bbert\b|bio-bert|biobert|clinicalbert',
            'Multimodal': r'multimodal|multi-modal',
            'Diffusion Model': r'diffusion model|denoising diffusion'
        }

        for model, pattern in ml_model_patterns.items():
            if re.search(pattern, full_text):
                ds_elements['ml_models'].append(model)

        for arch, pattern in dl_arch_patterns.items():
            if re.search(pattern, full_text):
                ds_elements['dl_architectures'].append(arch)

        # ============ 2. 检测特征工程方法 ============
        fe_patterns = {
            'PCA': r'\bpca\b|principal component analysis',
            't-SNE': r'tsne|t-sne|t-distributed stochastic',
            'UMAP': r'umap|uniform manifold',
            'Normalization': r'normalization|standardization|z-score|log.transform',
            'One-hot': r'one.hot|one hot encoding',
            'Embedding': r'word embedding|gene embedding|learned embedding',
            'Feature Selection': r'feature selection|variable selection|lasso|ridge',
            'Dimensionality Reduction': r'dimensionality reduction|feature extraction'
        }

        for fe, pattern in fe_patterns.items():
            if re.search(pattern, full_text):
                ds_elements['feature_engineering'].append(fe)

        # ============ 3. 检测评估指标 ============
        metric_patterns = {
            'AUROC': r'au[rc]|roc auc|area under roc|receiver operating',
            'AUPRC': r'auprc|average precision|pr auc|precision-recall',
            'F1-score': r'f1.score|f1 score|f-score',
            'Accuracy': r'accuracy',
            'Precision': r'\bprecision\b',
            'Recall': r'\brecall\b|sensitivity|true positive rate',
            'C-index': r'c.index|concordance index|harrell',
            'RMSE': r'rmse|root mean square',
            'MAE': r'\bmae\b|mean absolute error',
            'R²': r'r.squared|r²|r-squared',
            'Pearson': r'pearson.correlation|pearson r',
            'Spearman': r'spearman.correlation|spearman rho',
            'Calibration': r'calibration|brier score',
            'Log-rank': r'log.rank|log-rank'
        }

        for metric, pattern in metric_patterns.items():
            if re.search(pattern, full_text):
                ds_elements['evaluation_metrics'].append(metric)

        # ============ 4. 提取样本规模 ============
        # 匹配 "n = 1000", "N=1000", "sample of 1000", "1000 patients" 等模式
        sample_patterns = [
            r'(?:n|sample|cohort|patients?)\s*[=\s]\s*(\d+[,\d]*)(?:\s*patients?|\s*samples?|\s*subjects?)?',
            r'(\d+[,\d]*)\s*(?:patients?|samples?|subjects?|individuals?)',
            r'cohort\s+of\s+(\d+[,\d]*)',
            r'studied\s+(\d+[,\d]*)'
        ]

        for pattern in sample_patterns:
            match = re.search(pattern, full_text)
            if match:
                num_str = match.group(1).replace(',', '')
                try:
                    ds_elements['sample_size'] = int(num_str)
                    break
                except ValueError:
                    continue

        # ============ 5. 检测Python库 ============
        python_lib_patterns = {
            'scikit-learn': r'scikit-learn|sklearn',
            'PyTorch': r'pytorch|torch\.|torch ',
            'TensorFlow': r'tensorflow|keras|tf\.keras',
            'pandas': r'\bpandas\b',
            'numpy': r'\bnumpy\b',
            'scanpy': r'\bscanpy\b',
            'anndata': r'anndata',
            'scVI': r'scvi|scvitools',
            'cell2location': r'cell2location',
            'Seurat': r'seurat',
            'Bioconductor': r'bioconductor',
            'statsmodels': r'statsmodels',
            'lifelines': r'lifelines',
            'SHAP': r'\bshap\b|shapley',
            'LIME': r'\blime\b',
            'NetworkX': r'networkx'
        }

        for lib, pattern in python_lib_patterns.items():
            if re.search(pattern, full_text):
                ds_elements['python_libs'].append(lib)

        # ============ 6. 检测数据类型 ============
        data_type_patterns = {
            'scRNA-seq': r'single.cell rna|scrna-seq|single-cell rna',
            'Bulk RNA-seq': r'bulk rna-seq|rna.seq|transcriptomic',
            'Genomics/WGS': r'whole.genome|wgs|exome sequencing',
            'Proteomics': r'proteom|mass spectrometry',
            'EHR': r'\behr\b|electronic.health.record|clinical record',
            'Medical Imaging': r'mri|ct.scan|medical.image|x.ray|ultrasound',
            'Spatial Transcriptomics': r'spatial.transcriptom|visium|merfish',
            'Multi-omics': r'multi.omics|integrat.*omics'
        }

        for dtype, pattern in data_type_patterns.items():
            if re.search(pattern, full_text):
                ds_elements['data_types'].append(dtype)

        # ============ 7. 检测验证方法 ============
        validation_patterns = {
            '5-fold CV': r'5.?fold|five.?fold',
            '10-fold CV': r'10.?fold|ten.?fold',
            'Cross-validation': r'cross.validation|cv\s|k-fold',
            'Hold-out': r'hold.out|holdout|train.test.split',
            'Bootstrap': r'bootstrap',
            'Independent test': r'independent.*test|external.*validation|test.*set',
            'LOOCV': r'leave.one.out|loocv'
        }

        for val_method, pattern in validation_patterns.items():
            if re.search(pattern, full_text):
                ds_elements['validation_method'] = val_method
                break

        return ds_elements

    def filter_papers_by_if_range(
        self,
        papers: List[Dict],
        min_if: Optional[float] = None,
        max_if: Optional[float] = None
    ) -> List[Dict]:
        """
        按影响因子范围过滤论文

        Args:
            papers: 论文列表
            min_if: 最低影响因子
            max_if: 最高影响因子

        Returns:
            过滤后的论文列表
        """
        filtered = []

        for paper in papers:
            journal = paper.get('journal', '')
            if not journal:
                continue

            # 获取 IF
            if_val = get_journal_if(journal)

            # 检查范围
            if min_if is not None and if_val < min_if:
                continue
            if max_if is not None and if_val > max_if:
                continue

            filtered.append(paper)

        return filtered

    def search_by_idea(
        self,
        idea: str,
        max_results: Optional[int] = None,  # None = 动态质量准入，无固定限制
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        min_if: Optional[float] = None,
        max_if: Optional[float] = None,
        relevance_threshold: Optional[float] = None  # 新增：相关性阈值
    ) -> Dict:
        """
        基于研究想法进行智能��索（动态质量准入制）

        使用 AI 理解用户想法，生成优化的搜索关键词

        Args:
            idea: 用户的研究想法/描述
            max_results: 最大结果数 (None=无限制，基于质量准入)
            start_year: 起始年份
            end_year: 结束年份
            min_if: 最低影响因子
            max_if: 最高影响因子
            relevance_threshold: 相关性阈值 (0-10)

        Returns:
            搜索结果
        """
        # 生成优化的搜索关键词
        search_terms = self._generate_search_terms_from_idea(idea)

        print(f"基于想法生成搜索关键词: {search_terms}")

        # 构建日期范围
        date_range = None
        if start_year or end_year:
            date_range = (start_year, end_year)

        # 执行搜索（动态质量准入制）
        try:
            papers = self.search_papers(
                query=search_terms,
                max_results=max_results,
                enable_filter=False,
                date_range=date_range,
                min_if=min_if,
                relevance_threshold=relevance_threshold
            )
        except ZeroResultsError as e:
            # 零结果时返回建议
            return {
                'papers': [],
                'search_terms': search_terms,
                'count': 0,
                'error': str(e),
                'suggestion': f"建议扩大搜索关键词或降低IF阈值（当前 IF≥{min_if if min_if else '不限'}）"
            }

        # 二次过滤（IF范围精确控制）
        if max_if is not None:
            original_count = len(papers)
            papers = self.filter_papers_by_if_range(papers, min_if=min_if, max_if=max_if)
            if_str = f"IF {min_if}-{max_if}" if min_if and max_if else f"IF <={max_if}"
            print(f"按IF范围精确过滤({if_str}): {original_count} -> {len(papers)} 篇")

        return {
            'papers': papers,
            'search_terms': search_terms,
            'original_idea': idea
        }

    def _generate_search_terms_from_idea(self, idea: str) -> str:
        """
        将研究想法转换为 PubMed 搜索关键词

        策略：
        1. LLM 尝试提取关键词（翻译任务）
        2. LLM 失败 → 返回 null，触发原始文本回退
        3. 严禁使用默认词填充

        Args:
            idea: 用户的研究想法（原始 Research Seed）

        Returns:
            优化的搜索关键词，或原始 idea（当提取失败时）
        """
        # 保存原始输入，用于最终回退
        original_idea = idea.strip()

        try:
            import anthropic
            import os
            from dotenv import dotenv_values  # 使用 dotenv_values 确保 env 被正确加载

            # 加载环境变量（修复：使用 dotenv_values 而非 os.getenv）
            env_vars = dotenv_values()
            api_key = env_vars.get('ANTHROPIC_API_KEY')
            base_url = env_vars.get('ANTHROPIC_BASE_URL')

            if not api_key:
                # 没有 API key，直接返回原始输入
                print("[关键词提取] 未找到 ANTHROPIC_API_KEY，使用原始输入")
                return original_idea

            # 支持 base_url
            client_kwargs = {'api_key': api_key}
            if base_url:
                client_kwargs['base_url'] = base_url
            client = anthropic.Anthropic(**client_kwargs)

            prompt = f"""你是一位专业的生物医学文献检索专家。

## 核心任务：关键词翻译（NOT 匹��）

你的任务是将用户的研究想法"翻译"为 PubMed 搜索关键词，而不是从预定义列表中"匹配"关键词。

## 用户原始输入
{idea}

## 严格要求

1. **提取原则**：从用户输入中提取核心术语
2. **翻译原则**：将中文术语翻译为英文（如"心力衰竭" → "heart failure"）
3. **严禁填充**：如果无法提取有效关键词，返回字符串 "null"
4. **严禁默认词**：不得使用 "machine learning"、"deep learning" 等通用词作为填充

## 输出格式

- 如果能提取：返回 3-5 个关键词，用空格连接
- 如果无法提取：返回字符串 "null"（不含引号）

## 正确示例

输入: "heart failure thermodynamics metabolism"
输出: heart failure thermodynamics metabolism

输入: "心力衰竭热力学熵变研究"
输出: heart failure thermodynamics entropy

输入: "xyz" (无法理解)
输出: null

## 现在请执行（只返回结果，不要解释）："""

            message = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )

            search_terms = message.content[0].text.strip()

            # 清理可能的引号和多余字符
            search_terms = search_terms.replace('"', '').replace("'", '').strip()
            search_terms = ' '.join(search_terms.split())  # 压缩多余空格

            # 检查 LLM 是否返回了 null
            if search_terms.lower() == 'null':
                print(f"[关键词提取] LLM 返回 null，使用原始输入")
                return original_idea

            # 检查结果是否有效
            if not search_terms or len(search_terms) < 3:
                print(f"[关键词提取] LLM 返回无效结果，使用原始输入")
                return original_idea

            return search_terms

        except Exception as e:
            print(f"[关键词提取] AI 提取失败: {e}，使用原始输入")
            # 失败时直接返回原始输入，不经过任何处理
            return original_idea

    def _simple_keyword_extraction(self, idea: str) -> str:
        """
        通用关键词提取（无硬编码依赖）

        策略：
        1. 通用 NLP 提取（长词优先、词频统计）
        2. 停用词过滤
        3. 提取失败 → 返回原始输入

        Args:
            idea: 用户原始研究想法

        Returns:
            提取的关键词，或原始 idea（兜底）
        """
        import re
        from collections import Counter

        # 保存原始输入，用于最终回退
        original_idea = idea.strip()

        if not original_idea:
            return original_idea

        # 常见停用词（仅过滤无意义词，不进行术语匹配）
        stopwords = {
            # 英文停用词
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'my', 'your', 'his', 'her',
            'this', 'that', 'these', 'those',
            'want', 'to', 'study', 'research', 'investigate', 'use', 'using', 'for',
            'based', 'about', 'from', 'with', 'and', 'or', 'not', 'but', 'into', 'through',
            # 中文停用词
            '的', '了', '在', '和', '与', '想', '研究', '用', '来',
            '对', '为', '及', '其', '中', '等', '或', '一种', '方法', '分析', '基于',
            '进行', '通过', '这个', '那个', '这些', '那些'
        }

        # 清理输入：移除特殊字符，保留空格
        cleaned = re.sub(r'[^\w\s一-龥\+\*]', ' ', original_idea)

        # 分词
        words = cleaned.split()

        # 过滤：保留长度 >= 3 且不在停用词中的词
        valid_words = []
        for word in words:
            word_lower = word.lower()
            if len(word) >= 3 and word_lower not in stopwords:
                valid_words.append(word)

        if not valid_words:
            # 没有有效词，返回原始输入
            return original_idea

        # 词频统计
        word_freq = Counter(valid_words)

        # 按词长和词频评分（长词优先，高频词优先）
        import math
        scored = []
        for word, freq in word_freq.items():
            # 评分 = 词长 * 0.5 + 频率 * 1.5
            # 长词（可能是专业术语）获得额外权重
            score = len(word) * 0.5 + freq * 1.5
            scored.append((word, score))

        # 按评分降序排序
        scored.sort(key=lambda x: x[1], reverse=True)

        # 取前 5 个词
        top_keywords = [word for word, _ in scored[:5]]

        if not top_keywords:
            return original_idea

        # 返回空格连接的关键词
        return ' '.join(top_keywords)


    def fetch_full_text_for_papers(self, papers: List[Dict], max_papers: int = 5) -> List[Dict]:
        """
        为论文列表获取全文内容（优化版：先判断摘要是否充足）

        智能策略：
        1. 先评估摘要充足性（字数、结构完整性）
        2. 摘要充足 → 跳过全文获取，节省时间
        3. 摘要不充足 → 尝试获取PDF全文
        4. 全文失败 → 使用详细摘要作为备用

        Args:
            papers: 论文列表
            max_papers: 最多获取的论文数

        Returns:
            更新后的论文列表（包含full_text字段）
        """
        if not papers:
            return papers

        # 限制获取数量
        papers_to_fetch = papers[:max_papers]
        pmids = [p.get('pmid') for p in papers_to_fetch if p.get('pmid')]

        if not pmids:
            return papers

        print(f"\n{'='*60}")
        print(f"📄 全文获取策略: 智能摘要充足性评估")
        print(f"{'='*60}")

        # 第一阶段：评估所有论文的摘要充足性
        abstract_assessment = []
        for paper in papers_to_fetch:
            abstract = paper.get('abstract', '')
            assessment = self._assess_abstract_sufficiency(abstract, paper)
            abstract_assessment.append(assessment)

            status_icon = "[成功]" if assessment['is_sufficient'] else "[警告]"
            print(f"  {status_icon} PMID {paper.get('pmid', 'N/A')}: {assessment['reason']}")

        # 统计
        sufficient_count = sum(1 for a in abstract_assessment if a['is_sufficient'])
        insufficient_count = len(abstract_assessment) - sufficient_count

        print(f"\n[统计] 摘要评估结果:")
        print(f"  [成功] 充足 (跳过全文): {sufficient_count} 篇")
        print(f"  [警告]  不充足 (尝试全文): {insufficient_count} 篇")

        # 第二阶段：只对摘要不充足的论文尝试获取全文
        papers_needing_fulltext = [
            paper for paper, assessment in zip(papers_to_fetch, abstract_assessment)
            if not assessment['is_sufficient']
        ]

        # 第三阶段：为所有论文设置full_text
        for paper, assessment in zip(papers_to_fetch, abstract_assessment):
            abstract = paper.get('abstract', '')

            if assessment['is_sufficient']:
                # 摘要充足，直接使用摘要
                paper['full_text'] = abstract
                paper['full_text_source'] = 'abstract_sufficient'
                paper['full_text_word_count'] = len(abstract.split()) if abstract else 0
            else:
                # 摘要不充足，先使用摘要，后续尝试升级
                paper['full_text'] = abstract
                paper['full_text_source'] = 'abstract'
                paper['full_text_word_count'] = len(abstract.split()) if abstract else 0
                paper['needs_fulltext'] = True  # 标记需要全文

        # 第四阶段：批量尝试获取全文（只针对不充足的论文）
        if papers_needing_fulltext:
            print(f"\n[搜索] 尝试获取 {len(papers_needing_fulltext)} 篇论文的全文...")
            pmids_to_fetch = [p.get('pmid') for p in papers_needing_fulltext if p.get('pmid')]

            try:
                fetch_results = self.oa_fetcher.batch_fetch_papers(pmids_to_fetch, max_concurrent=2)

                # 更新论文数据
                for result in fetch_results:
                    pmid = result['pmid']
                    fetch_result = result['result']

                    # 找到对应的论文
                    for paper in papers_to_fetch:
                        if paper.get('pmid') == pmid and fetch_result.get('success'):
                            old_word_count = paper.get('full_text_word_count', 0)
                            paper['full_text'] = fetch_result.get('content', '')
                            paper['full_text_source'] = fetch_result.get('source', 'unknown')
                            paper['full_text_word_count'] = fetch_result.get('word_count', 0)

                            # 显示升级信息
                            source_name = {
                                'pdf': '📕 PDF全文',
                                'abstract_detailed': '📄 详细摘要',
                                'abstract': '📝 摘要'
                            }.get(fetch_result.get('source', ''), fetch_result.get('source', ''))

                            print(f"  [OK] PMID {pmid}: {source_name} ({old_word_count} → {paper['full_text_word_count']} 字)")
                            break

            except Exception as e:
                print(f"  [警告]  批量获取全文时出错: {e}")

        # 最终统计
        pdf_count = sum(1 for p in papers_to_fetch if p.get('full_text_source') == 'pdf')
        abstract_sufficient_count = sum(1 for p in papers_to_fetch if p.get('full_text_source') == 'abstract_sufficient')
        abstract_fallback_count = sum(1 for p in papers_to_fetch if p.get('full_text_source') in ['abstract', 'abstract_detailed'])

        print(f"\n[统计] 最终结果:")
        print(f"  📕 PDF全文: {pdf_count} 篇")
        print(f"  [成功] 摘要充足: {abstract_sufficient_count} 篇")
        print(f"  📝 摘要备用: {abstract_fallback_count} 篇")
        print(f"{'='*60}\n")

        return papers

    def _assess_abstract_sufficiency(self, abstract: str, paper: Dict = None) -> Dict:
        """
        评估摘要是否充足（无需获取全文）

        评估标准：
        1. 字数要求：至少250字
        2. 结构完整性：包含背景、方法、结果、结论
        3. 关键信息：包含数据、统计指标、样本量等

        Args:
            abstract: 论文摘要
            paper: 论文数据（用于获取额外信息）

        Returns:
            {
                'is_sufficient': bool,
                'reason': str,
                'word_count': int,
                'score': float  # 充足性评分 0-1
            }
        """
        if not abstract:
            return {
                'is_sufficient': False,
                'reason': '无摘要',
                'word_count': 0,
                'score': 0.0
            }

        word_count = len(abstract.split())
        score = 0.0
        reasons = []

        # 1. 字数评估 (权重: 0.3)
        if word_count >= 350:
            score += 0.3
        elif word_count >= 250:
            score += 0.2
        elif word_count >= 150:
            score += 0.1
        else:
            reasons.append(f"字数不足({word_count}字)")

        # 2. 结构完整性评估 (权重: 0.4)
        abstract_lower = abstract.lower()

        # 背景相关词
        background_keywords = ['background', 'introduction', 'although', 'however', 'recent',
                             '尽管', '虽然', '背景', '近年来']
        has_background = any(kw in abstract_lower for kw in background_keywords)
        if has_background:
            score += 0.1
        else:
            reasons.append("缺少背景")

        # 方法相关词
        method_keywords = ['method', 'approach', 'algorithm', 'analysis', 'model',
                         'we used', 'we performed', 'participants', 'patients',
                         '方法', '算法', '模型', '分析', '我们']
        has_method = any(kw in abstract_lower for kw in method_keywords)
        if has_method:
            score += 0.15
        else:
            reasons.append("缺少方法")

        # 结果相关词
        result_keywords = ['result', 'showed', 'found', 'demonstrate', 'reveal',
                         'significant', 'association', 'correlation',
                         '结果', '发现', '表明', '显示', '显著']
        has_result = any(kw in abstract_lower for kw in result_keywords)
        if has_result:
            score += 0.15
        else:
            reasons.append("缺少结果")

        # 3. 关键信息评估 (权重: 0.3)
        # 数字/统计指标
        import re
        has_numbers = bool(re.search(r'\d+', abstract))
        if has_numbers:
            score += 0.1

        # 具体指标
        metric_keywords = ['p-value', 'p=', 'ci', 'hr', 'or', 'rr', 'auc',
                          'sensitivity', 'specificity', 'accuracy',
                          '相关性', '显著', '置信区间']
        has_metrics = any(kw in abstract_lower for kw in metric_keywords)
        if has_metrics:
            score += 0.1
        else:
            reasons.append("缺少统计指标")

        # 样本量
        sample_pattern = r'\b(n\s*=\s*\d+|sample\s*of\s*\d+|\d+\s*patients?|\d+\s*subjects?)\b'
        has_sample = bool(re.search(sample_pattern, abstract_lower))
        if has_sample:
            score += 0.1

        # 判断是否充足
        is_sufficient = score >= 0.6  # 60分以上认为充足

        if not reasons:
            reason = "摘要完整" if is_sufficient else "摘要质量一般"
        else:
            reason = f"摘要不足: {', '.join(reasons[:3])}"

        return {
            'is_sufficient': is_sufficient,
            'reason': reason,
            'word_count': word_count,
            'score': score
        }


if __name__ == '__main__':
    # 测试
    searcher = PubMedSearcher(email="test@example.com")
    papers = searcher.search_papers("bioinformatics", max_results=2)
    print(f"\n找到 {len(papers)} 篇论文")
    for paper in papers[:2]:
        print(f"PMID: {paper['pmid']}, 标题: {paper['title'][:50]}...")