"""
智能体工具箱 - 全自动文献获取器

接收 DOI 或关键词，自动获取文献全文内容。
优先���载开放获取 PDF，失败时回退到详细摘要。
"""
import os
import re
import time
import requests
from typing import Dict, Optional, List
from urllib.parse import urljoin, urlparse
from pathlib import Path
from datetime import datetime

# 导入记忆管理器
try:
    from memory_manager import save_to_memory, get_memory_stats
    HAS_MEMORY_MANAGER = True
except ImportError:
    HAS_MEMORY_MANAGER = False
    print("警告: memory_manager 未找到，文献将不会自动存储到记忆库")

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from Bio import Entrez
    HAS_BIOPYTHON = True
except ImportError:
    HAS_BIOPYTHON = False


class AutoPaperFetcher:
    """
    全自动文献获取器

    特性：
    - 接收 DOI 或关键词
    - 自动寻找 OA PDF
    - 下载失败时回退到摘要
    - 全自动运行，不抛出异常
    """

    def __init__(self, email: str = "research@example.com", papers_dir: str = "papers"):
        """
        初始化获取器

        Args:
            email: PubMed 邮箱
            papers_dir: 论文保存目录
        """
        self.email = email
        self.papers_dir = Path(papers_dir)
        self.papers_dir.mkdir(exist_ok=True)

        # 配置 PubMed
        if HAS_BIOPYTHON:
            Entrez.email = email

        # 请求���（模拟浏览器）
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        # 请求超时设置
        self.timeout = 30

    def fetch(self, identifier: str) -> Dict:
        """
        主入口：获取文献内容

        Args:
            identifier: DOI 或关键词

        Returns:
            {
                'success': True/False,
                'content': str,  # 全文或摘要
                'source': 'pdf'/'abstract_fallback'/'abstract',
                'identifier': str,
                'word_count': int,
                'warning': str,  # 摘要模式的警告
                'error': str  # 错误信息（如果完全失败）
            }
        """
        result = {
            'identifier': identifier,
            'success': False,
            'content': '',
            'source': 'unknown',
            'word_count': 0,
            'warning': '',
            'error': ''
        }

        try:
            # 判断输入类型
            if self._is_doi(identifier):
                doi = identifier
                pmid = None
            else:
                # 关键词搜索，获取第一篇论文的 DOI
                search_result = self._search_first_paper(identifier)
                if search_result['success']:
                    doi = search_result.get('doi')
                    pmid = search_result.get('pmid')
                else:
                    # 搜索失败，直接使用搜索结果摘要
                    return self._format_abstract_fallback(
                        search_result.get('abstract', ''),
                        identifier,
                        search_result.get('error', '')
                    )

            # 尝试多种方式获取 PDF
            pdf_result = self._try_all_pdf_sources(doi, pmid)

            if pdf_result['success']:
                # PDF 下载成功
                result['success'] = True
                result['content'] = pdf_result['content']
                result['source'] = 'pdf'
                result['word_count'] = pdf_result['word_count']
                result['pdf_path'] = pdf_result['pdf_path']
                result['doi'] = doi  # 保存 DOI 用于记忆存储

                # 自动存储到记忆库
                self._save_to_memory_if_enabled(
                    pdf_result['content'],
                    doi=doi,
                    title=search_result.get('title', '') if 'search_result' in dir() else '',
                    source='pdf',
                    identifier=identifier
                )
            else:
                # PDF 获取失败，回退到摘要
                abstract_result = self._get_abstract_fallback(doi, pmid, identifier)
                return abstract_result

        except Exception as e:
            # 任何异常都不抛出，返回错误信息
            result['error'] = f'处理过程异常: {str(e)}'

        return result

    def _is_doi(self, identifier: str) -> bool:
        """判断是否为 DOI"""
        doi_patterns = [
            r'^10\.\d{4,}/',  # 标准DOI
            r'^doi:10\.\d{4,}/',  # 带doi前缀
            r'^https?://doi\.org/10\.',  # DOI URL
        ]
        return any(re.match(pattern, identifier.lower()) for pattern in doi_patterns)

    def _extract_doi(self, identifier: str) -> Optional[str]:
        """从输入中提取 DOI"""
        # 移除 doi.org 前缀
        if 'doi.org/' in identifier.lower():
            match = re.search(r'10\.\d{4,}/[^\s]+', identifier)
            return match.group() if match else None
        # 移除 doi: 前缀
        identifier = re.sub(r'^doi:', '', identifier.lower())
        if identifier.startswith('10.'):
            return identifier
        return None

    def _search_first_paper(self, query: str) -> Dict:
        """
        搜索第一篇论文

        Args:
            query: 搜索关键词

        Returns:
            {'success': bool, 'doi': str, 'pmid': str, 'title': str, 'abstract': str}
        """
        result = {'success': False, 'doi': None, 'pmid': None, 'title': None, 'abstract': None}

        if not HAS_BIOPYTHON:
            return result

        try:
            # 搜索 PubMed
            handle = Entrez.esearch(db="pubmed", term=query, retmax=1, retmode="xml")
            search_results = Entrez.read(handle)
            handle.close()

            id_list = search_results.get('IdList', [])
            if not id_list:
                return result

            pmid = id_list[0]

            # 获取详细信息
            handle = Entrez.efetch(db="pubmed", id=pmid, rettype="abstract", retmode="xml")
            record = Entrez.read(handle)
            handle.close()

            # 解析
            if 'PubmedArticle' in record.keys():
                article = record['PubmedArticle']
                if isinstance(article, list):
                    article = article[0]

                medline_citation = article.get('MedlineCitation', article)
                article_data = medline_citation.get('Article', {})

                # 提取 DOI
                doi = None
                aid_list = article_data.get('ArticleIdList', [])
                if aid_list:
                    for aid in aid_list:
                        aid_str = str(aid)
                        if '10.' in aid_str and '/' in aid_str:
                            doi = aid_str
                            break

                # 提取摘要
                abstract_obj = article_data.get('Abstract')
                abstract_text = ''
                if abstract_obj:
                    abstract_list = abstract_obj.get('AbstractText')
                    if abstract_list:
                        if isinstance(abstract_list, list):
                            abstract_text = ' '.join([self._to_str(t) for t in abstract_list])
                        else:
                            abstract_text = self._to_str(abstract_list)

                result = {
                    'success': True,
                    'pmid': pmid,
                    'doi': doi,
                    'title': self._to_str(article_data.get('ArticleTitle')),
                    'abstract': abstract_text
                }

        except Exception as e:
            result['error'] = str(e)

        return result

    def _try_all_pdf_sources(self, doi: str, pmid: Optional[str] = None) -> Dict:
        """
        尝试所有可能的 PDF 来源

        Args:
            doi: DOI
            pmid: PMID（可选）

        Returns:
            {'success': bool, 'content': str, 'word_count': int, 'pdf_path': str}
        """
        # 来源列表（按优先级）
        sources = []

        # 1. PMC（如果 PMID 可用）
        if pmid:
            sources.append(('PMC', lambda: self._fetch_from_pmc_by_pmid(pmid)))

        # 2. DOI 解析
        if doi:
            sources.append(('DOI_PMC', lambda: self._fetch_pmc_by_doi(doi)))
            sources.append(('DOI_Direct', lambda: self._fetch_pdf_by_doi(doi)))

        # 3. 预印本服务器
        if doi:
            sources.append(('bioRxiv', lambda: self._fetch_from_biorxiv(doi)))
            sources.append(('arXiv', lambda: self._fetch_from_arxiv(doi)))

        # 尝试每个来源
        for source_name, fetch_func in sources:
            try:
                result = fetch_func()
                if result['success']:
                    result['source'] = source_name
                    return result
            except Exception:
                continue

        return {'success': False, 'content': '', 'word_count': 0}

    def _fetch_from_pmc_by_pmid(self, pmid: str) -> Dict:
        """通过 PMID 从 PMC 获取 PDF"""
        try:
            # 搜索 PMC ID
            handle = Entrez.esearch(db="pmc", term=f"{pmid}[pmid]", retmax=1)
            search_result = Entrez.read(handle)
            handle.close()

            pmcid_list = search_result.get('IdList', [])
            if not pmcid_list:
                return {'success': False, 'content': '', 'word_count': 0}

            pmcid = pmcid_list[0]
            pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf"

            return self._download_and_parse_pdf(pdf_url, f"PMC_{pmcid}")

        except Exception:
            return {'success': False, 'content': '', 'word_count': 0}

    def _fetch_pmc_by_doi(self, doi: str) -> Dict:
        """通过 DOI 查找 PMC 版本"""
        try:
            # 使用 PMC ID 转换 API
            url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={doi}"
            response = requests.get(url, timeout=self.timeout, headers=self.headers)

            if response.status_code != 200:
                return {'success': False, 'content': '', 'word_count': 0}

            # 解析响应（简单文本格式）
            pmcid = None
            for line in response.text.split('\n'):
                if line.startswith('PMC'):
                    pmcid = line.split()[0]
                    break

            if pmcid:
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf"
                return self._download_and_parse_pdf(pdf_url, f"PMC_{pmcid}")

        except Exception:
            pass

        return {'success': False, 'content': '', 'word_count': 0}

    def _fetch_pdf_by_doi(self, doi: str) -> Dict:
        """直接通过 DOI 获取 PDF"""
        try:
            doi_url = f"https://doi.org/{doi}"

            # 获取重定向后的 URL
            response = requests.get(doi_url, timeout=self.timeout, headers=self.headers, allow_redirects=True)
            final_url = response.url

            # 检查常见 OA 出版商
            if 'nature.com' in final_url:
                return self._fetch_nature_pdf(final_url)
            elif 'science.org' in final_url:
                return self._fetch_science_pdf(final_url)
            elif 'cell.com' in final_url:
                return self._fetch_cell_pdf(final_url)
            elif 'pnas.org' in final_url:
                return self._fetch_pnas_pdf(final_url)

            # 尝试找 PDF 链接
            soup = self._parse_html(response.text)
            if soup:
                pdf_links = soup.find_all('a', href=re.compile(r'\.pdf$', re.I))
                if pdf_links:
                    pdf_url = urljoin(final_url, pdf_links[0]['href'])
                    return self._download_and_parse_pdf(pdf_url, f"DOI_{doi.replace('/', '_')}")

        except Exception:
            pass

        return {'success': False, 'content': '', 'word_count': 0}

    def _fetch_from_biorxiv(self, doi: str) -> Dict:
        """从 bioRxiv 获取"""
        try:
            # bioRxiv 内容协商 API
            url = f"https://www.biorxiv.org/content/{doi}"
            headers = self.headers.copy()
            headers['Accept'] = 'application/pdf'

            response = requests.get(url, headers=headers, timeout=self.timeout, allow_redirects=True)

            if response.status_code == 200 and 'application/pdf' in response.headers.get('content-type', ''):
                filename = f"biorxiv_{doi.replace('/', '_')}"
                return self._download_and_parse_pdf_from_content(response.content, filename)

        except Exception:
            pass

        return {'success': False, 'content': '', 'word_count': 0}

    def _fetch_from_arxiv(self, doi: str) -> Dict:
        """从 arXiv 获取"""
        try:
            # arXiv 通常有直接 PDF 链接
            arxiv_id = None

            # 从 DOI 尝试提取 arXiv ID
            if 'arxiv' in doi.lower():
                arxiv_id = doi.split('arxiv.')[-1] if '.' in doi else None

            if arxiv_id:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                return self._download_and_parse_pdf(pdf_url, f"arxiv_{arxiv_id}")

        except Exception:
            pass

        return {'success': False, 'content': '', 'word_count': 0}

    def _fetch_nature_pdf(self, url: str) -> Dict:
        """获取 Nature PDF"""
        try:
            soup = self._parse_html(requests.get(url, headers=self.headers, timeout=self.timeout).text)

            # Nature 的 PDF 链接
            pdf_link = soup.find('a', {'data-track-action': 'download pdf'}) if soup else None
            if not pdf_link:
                pdf_link = soup.find('a', href=re.compile(r'\.pdf', re.I))

            if pdf_link:
                pdf_url = pdf_link.get('href') or pdf_link['href']
                if not pdf_url.startswith('http'):
                    pdf_url = urljoin(url, pdf_url)
                return self._download_and_parse_pdf(pdf_url, f"Nature_{url.split('/')[-2]}")

        except Exception:
            pass

        return {'success': False, 'content': '', 'word_count': 0}

    def _fetch_science_pdf(self, url: str) -> Dict:
        """获取 Science PDF"""
        try:
            soup = self._parse_html(requests.get(url, headers=self.headers, timeout=self.timeout).text)

            # Science 的 PDF 链接
            pdf_link = soup.find('a', href=re.compile(r'\.pdf', re.I))
            if pdf_link:
                pdf_url = urljoin(url, pdf_link['href'])
                return self._download_and_parse_pdf(pdf_url, f"Science_{url.split('/')[-2]}")

        except Exception:
            pass

        return {'success': False, 'content': '', 'word_count': 0}

    def _fetch_cell_pdf(self, url: str) -> Dict:
        """获取 Cell PDF"""
        try:
            soup = self._parse_html(requests.get(url, headers=self.headers, timeout=self.timeout).text)

            # Cell PDF
            pdf_link = soup.find('a', href=re.compile(r'\.pdf', re.I))
            if pdf_link:
                pdf_url = urljoin(url, pdf_link['href'])
                return self._download_and_parse_pdf(pdf_url, f"Cell_{url.split('/')[-2]}")

        except Exception:
            pass

        return {'success': False, 'content': '', 'word_count': 0}

    def _fetch_pnas_pdf(self, url: str) -> Dict:
        """获取 PNAS PDF"""
        try:
            soup = self._parse_html(requests.get(url, headers=self.headers, timeout=self.timeout).text)

            # PNAS PDF
            pdf_link = soup.find('a', href=re.compile(r'\.pdf', re.I))
            if pdf_link:
                pdf_url = urljoin(url, pdf_link['href'])
                return self._download_and_parse_pdf(pdf_url, f"PNAS_{url.split('/')[-2]}")

        except Exception:
            pass

        return {'success': False, 'content': '', 'word_count': 0}

    def _download_and_parse_pdf(self, pdf_url: str, filename_base: str) -> Dict:
        """下载并解析 PDF"""
        try:
            response = requests.get(pdf_url, headers=self.headers, timeout=self.timeout, stream=True)

            if response.status_code != 200:
                return {'success': False, 'content': '', 'word_count': 0}

            # 保存文件
            filename = self.papers_dir / f"{filename_base}.pdf"
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # 解析 PDF
            content = self._parse_pdf_file(filename)

            return {
                'success': True,
                'content': content,
                'word_count': len(content.split()),
                'pdf_path': str(filename)
            }

        except Exception:
            return {'success': False, 'content': '', 'word_count': 0}

    def _download_and_parse_pdf_from_content(self, content: bytes, filename: str) -> Dict:
        """从内容解析 PDF"""
        try:
            filepath = self.papers_dir / filename
            with open(filepath, 'wb') as f:
                f.write(content)

            text = self._parse_pdf_file(filepath)

            return {
                'success': True,
                'content': text,
                'word_count': len(text.split()),
                'pdf_path': str(filepath)
            }

        except Exception:
            return {'success': False, 'content': '', 'word_count': 0}

    def _parse_pdf_file(self, filepath: Path) -> str:
        """解析 PDF 文件"""
        content = ''

        # 方法1: pdfplumber
        if HAS_PDFPLUMBER:
            try:
                with pdfplumber.open(filepath) as pdf:
                    # 限制页数，避免超大文件
                    max_pages = min(len(pdf.pages), 50)

                    for page in pdf.pages[:max_pages]:
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                content += page_text + '\n'
                        except:
                            continue
            except Exception:
                pass

        # 方法2: PyMuPDF（如果 pdfplumber 失败）
        if not content:
            try:
                import fitz
                doc = fitz.open(str(filepath))
                for page_num in range(min(len(doc), 50)):
                    try:
                        page = doc[page_num]
                        page_text = page.get_text()
                        if page_text.strip():
                            content += page_text + '\n'
                    except:
                        continue
                doc.close()
            except Exception:
                pass

        return self._clean_text(content)

    def _clean_text(self, text: str) -> str:
        """清理提取的文本"""
        if not text:
            return ''

        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)

        # 移除页码等干扰信息
        text = re.sub(r'\bPage\s*\d+\s*of\s*\d+\b', '', text)
        text = re.sub(r'\b\d+\s*[Bb]io[Rr]xi[vv]\b', '', text)

        # 移除引用标记
        text = re.sub(r'\[\d+\]', '', text)

        # 限制长度
        if len(text) > 100000:
            text = text[:100000] + "..."

        return text.strip()

    def _get_abstract_fallback(self, doi: Optional[str], pmid: Optional[str], identifier: str) -> Dict:
        """
        获取摘要作为备用方案（核心功能）

        这是当 PDF 获取失败时必须执行的保底逻辑
        """
        abstract_text = ''
        extracted_title = ''
        extracted_doi = doi

        try:
            # 如果有 PMID，直接从 PubMed 获取
            if pmid and HAS_BIOPYTHON:
                handle = Entrez.efetch(db="pubmed", id=pmid, rettype="abstract", retmode="xml")
                record = Entrez.read(handle)
                handle.close()

                if 'PubmedArticle' in record.keys():
                    article = record['PubmedArticle']
                    if isinstance(article, list):
                        article = article[0]

                    medline_citation = article.get('MedlineCitation', article)
                    article_data = medline_citation.get('Article', {})

                    # 提取标题
                    extracted_title = self._to_str(article_data.get('ArticleTitle', ''))

                    # 提取摘要
                    abstract_obj = article_data.get('Abstract')
                    if abstract_obj:
                        abstract_list = abstract_obj.get('AbstractText')
                        if abstract_list:
                            if isinstance(abstract_list, list):
                                abstract_text = ' '.join([self._to_str(t) for t in abstract_list])
                            else:
                                abstract_text = self._to_str(abstract_list)

                    # 如果仍然没有摘要，尝试用标题和关键词
                    if not abstract_text:
                        title = extracted_title
                        keywords = medline_citation.get('KeywordList', [])
                        if keywords:
                            kw_text = ', '.join([self._to_str(k) for k in keywords[:10]])
                            abstract_text = f"标题: {title}\n关键词: {kw_text}"
                        else:
                            abstract_text = f"标题: {title}"

        except Exception:
            pass

        # 如果仍然没有内容
        if not abstract_text:
            abstract_text = f"未能获取到文献 '{identifier}' 的详细摘要。请尝试直接访问文献页面。"

        return self._format_abstract_fallback(
            abstract_text, identifier,
            doi=extracted_doi,
            title=extracted_title
        )

    def _format_abstract_fallback(self, abstract: str, identifier: str, error: str = '', doi: str = None, title: str = '') -> Dict:
        """格式化摘要备用结果"""
        warning = "【未能获取免费全文，以下仅为文献摘要，请基于摘要完成你的推测】\n\n"

        result = {
            'success': True,  # 仍然返回 True，让智能体能继续工作
            'content': warning + abstract,
            'source': 'abstract_fallback',
            'identifier': identifier,
            'word_count': len(abstract.split()) if abstract else 0,
            'warning': warning.strip(),
            'error': error,
            'doi': doi or 'unknown'
        }

        # 自动存储摘要到记忆库
        self._save_to_memory_if_enabled(
            abstract,
            doi=doi or 'unknown',
            title=title,
            source='abstract_fallback',
            identifier=identifier
        )

        return result

    def _save_to_memory_if_enabled(self, text: str, doi: str = None, title: str = '',
                                    source: str = 'unknown', identifier: str = '') -> None:
        """
        如果记忆管理器可用，将文本存储到记忆库

        Args:
            text: 文献内容
            doi: DOI 标识符
            title: 文献标题
            source: 来源类型 (pdf/abstract_fallback)
            identifier: 原始输入标识符
        """
        if not HAS_MEMORY_MANAGER:
            return

        if not text or not text.strip():
            return

        try:
            metadata = {
                'doi': doi or identifier or 'unknown',
                'title': title or f'文献_{identifier}',
                'source': source,
                'fetch_time': datetime.now().isoformat(),
                'identifier': identifier
            }

            save_result = save_to_memory(text, metadata)
            if save_result.get('success'):
                print(f"[记忆库] 文献已自动存储: {doi or identifier}")
            else:
                print(f"[记忆库] 存储失败: {save_result.get('message')}")
        except Exception as e:
            print(f"[记忆库] 存储异常: {e}")

    def _parse_html(self, html: str):
        """解析 HTML"""
        try:
            from bs4 import BeautifulSoup
            return BeautifulSoup(html, 'html.parser')
        except Exception:
            return None

    @staticmethod
    def _to_str(value) -> str:
        """安全转换为字符串"""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        try:
            if hasattr(value, '_String'):
                return str(value._String)
            if hasattr(value, 'value'):
                val = value.value
                if isinstance(val, str):
                    return val
                return str(val)
            return str(value)
        except Exception:
            return ""

    def batch_fetch(self, identifiers: List[str], delay: float = 1.0) -> List[Dict]:
        """
        批量获取文献

        Args:
            identifiers: DOI 或关键词列表
            delay: 请求间隔（秒）

        Returns:
            结果列表
        """
        results = []

        for i, identifier in enumerate(identifiers):
            print(f"[{i+1}/{len(identifiers)}] 正在获取: {identifier[:50]}...")

            result = self.fetch(identifier)
            results.append(result)

            # 避免请求过快
            if delay > 0:
                time.sleep(delay)

            # 显示简要结果
            if result['success']:
                if result['source'] == 'pdf':
                    print(f"  ✓ PDF 获取成功 ({result['word_count']} 字)")
                elif 'fallback' in result['source']:
                    print(f"  ⚠ 使用摘要备用 ({result['word_count']} 字)")
            else:
                print(f"  ✗ 获取失败: {result.get('error', 'Unknown')}")

        return results


# 便捷函数
def fetch_paper(identifier: str, papers_dir: str = "papers") -> Dict:
    """
    单个文献获取（便捷函数）

    Args:
        identifier: DOI 或关键词
        papers_dir: 论文保存目录

    Returns:
        获取结果字典
    """
    fetcher = AutoPaperFetcher(papers_dir=papers_dir)
    return fetcher.fetch(identifier)


def batch_fetch_papers(identifiers: List[str], papers_dir: str = "papers", delay: float = 1.0) -> List[Dict]:
    """
    批量文献获取（便捷函数）

    Args:
        identifiers: DOI 或关键词列表
        papers_dir: 论文保存目录
        delay: 请求间隔

    Returns:
        结果列表
    """
    fetcher = AutoPaperFetcher(papers_dir=papers_dir)
    return fetcher.batch_fetch(identifiers, delay=delay)


if __name__ == '__main__':
    # 测试
    print("=" * 60)
    print("全自动文献获取器 - 测试")
    print("=" * 60)

    fetcher = AutoPaperFetcher()

    # 测试1: DOI
    print("\n[测试1] DOI 测试")
    test_doi = "10.1038/s41586-021-00922-6"  # Nature OA 论文
    result = fetcher.fetch(test_doi)
    print(f"DOI: {test_doi}")
    print(f"成功: {result['success']}")
    print(f"来源: {result['source']}")
    print(f"字数: {result['word_count']}")
    if result.get('warning'):
        print(f"警告: {result['warning']}")

    # 测试2: 关键词搜索
    print("\n[测试2] 关键词搜索测试")
    test_query = "CRISPR gene editing"
    result2 = fetcher.fetch(test_query)
    print(f"关键词: {test_query}")
    print(f"成功: {result2['success']}")
    print(f"来源: {result2['source']}")
    print(f"字数: {result2['word_count']}")

    # 显示内容预览
    if result2['content']:
        preview = result2['content'][:200].replace('\n', ' ')
        print(f"内容预览: {preview}...")
