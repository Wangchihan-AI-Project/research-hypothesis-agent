"""
开放获取文献下载和PDF解析工具
支持从多种来源下载开放获取论文全文，并解析PDF内容
"""
import os
import re
import time
import requests
from typing import Dict, Optional, List
from urllib.parse import urljoin, urlparse
import pdfplumber
from bs4 import BeautifulSoup
from Bio import Entrez


class OAPaperFetcher:
    """开放获取论文下载器"""

    def __init__(self, email: Optional[str] = None, api_key: Optional[str] = None, cache_dir: str = "data/papers"):
        """
        初始化下载器

        Args:
            email: PubMed邮箱
            api_key: PubMed API密钥
            cache_dir: PDF缓存目录
        """
        Entrez.email = email or "research@example.com"
        if api_key:
            Entrez.api_key = api_key

        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        # OA资源来源列表（按��先级）
        self.oa_sources = [
            "https://www.ncbi.nlm.nih.gov/pmc/",
            "https://doi.org/",
            "https://arxiv.org/",
            "https://www.biorxiv.org/",
            "https://www.medrxiv.org/",
        ]

    def fetch_paper_content(self, pmid: str, doi: Optional[str] = None, abstract: str = "") -> Dict:
        """
        获取论文全文内容

        优先尝试下载PDF，失败则返回详细摘要

        Args:
            pmid: PubMed ID
            doi: DOI
            abstract: 论文摘要（备用）

        Returns:
            {'success': bool, 'content': str, 'source': str, 'word_count': int}
        """
        # 1. 尝试从PMC下载
        pmc_result = self._fetch_from_pmc(pmid)
        if pmc_result['success']:
            return pmc_result

        # 2. 尝试通过DOI查找OA版本
        if doi:
            doi_result = self._fetch_by_doi(doi)
            if doi_result['success']:
                return doi_result

        # 3. 尝试从预印本服务器查找
        preprint_result = self._fetch_from_preprint(pmid)
        if preprint_result['success']:
            return preprint_result

        # 4. 所有方法失败，返回摘要作为备用
        return {
            'success': True,
            'content': abstract,
            'source': 'abstract_fallback',
            'word_count': len(abstract.split()) if abstract else 0,
            'message': 'PDF下载失败，使用摘要作为备用方案'
        }

    def _fetch_from_pmc(self, pmid: str) -> Dict:
        """从PubMed Central (PMC)下载"""
        try:
            # 直接使用PMC ID搜索
            # 首先尝试通过pmid获取pmcid
            search_handle = Entrez.esearch(db="pmc", term=f"{pmid}[pmid]", retmax=1)
            search_result = Entrez.read(search_handle)
            search_handle.close()

            pmcid = None
            if search_result.get('IdList'):
                pmcid = search_result['IdList'][0]

            if not pmcid:
                return {'success': False, 'error': '未找到PMC版本'}

            # 尝试下载PDF
            pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf"
            return self._download_and_parse_pdf(pdf_url, f"PMC_{pmcid}")

        except Exception as e:
            return {'success': False, 'error': f'PMC下载失败: {str(e)}'}

    def _fetch_by_doi(self, doi: str) -> Dict:
        """通过DOI查找OA版本"""
        try:
            # 使用Unpaywall API查找OA版本
            unpaywall_url = f"https://api.unpaywall.org/v2/{doi}"
            # 注意：Unpaywall需要API key，这里使用备用方案

            # 尝试直接访问DOI
            doi_url = f"https://doi.org/{doi}"
            response = requests.get(doi_url, timeout=10, allow_redirects=True)
            final_url = response.url

            # 检查是否是OA期刊
            if 'nature.com' in final_url or 'science.org' in final_url:
                # 这些期刊通常有OA选项
                return self._try_publisher_oa(final_url, doi)

            # 检查是否有PDF链接
            soup = BeautifulSoup(response.text, 'html.parser')
            pdf_links = soup.find_all('a', href=re.compile(r'\.pdf$', re.I))

            if pdf_links:
                pdf_url = urljoin(final_url, pdf_links[0]['href'])
                return self._download_and_parse_pdf(pdf_url, f"DOI_{doi.replace('/', '_')}")

            return {'success': False, 'error': '未找到OA版本'}

        except Exception as e:
            return {'success': False, 'error': f'DOI查找失败: {str(e)}'}

    def _fetch_from_preprint(self, pmid: str) -> Dict:
        """从预印本服务器查找"""
        try:
            # 获取论文信息
            handle = Entrez.efetch(db="pubmed", id=pmid, rettype="abstract", retmode="xml")
            record = Entrez.read(handle)
            handle.close()

            # 从标题中提取信息搜索预印本
            if 'PubmedArticle' not in record.keys():
                return {'success': False, 'error': '未找到论文'}

            article = record['PubmedArticle']
            if isinstance(article, list):
                article = article[0]

            # 获取标题
            medline_citation = article.get('MedlineCitation', article)
            article_data = medline_citation.get('Article', {})
            title = str(article_data.get('ArticleTitle', ''))

            # 搜索bioRxiv
            return self._search_biorxiv(title)

        except Exception as e:
            return {'success': False, 'error': f'预印本搜索失败: {str(e)}'}

    def _search_biorxiv(self, title: str) -> Dict:
        """搜索bioRxiv预印本"""
        try:
            # 使用标题搜索
            search_url = "https://www.biorxiv.org/search/"
            params = {
                'q': title[:100],  # 限制标题长度
                'jcode': 'biorxiv'
            }

            response = requests.get(search_url, params=params, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            # 查找结果中的PDF链接
            pdf_links = soup.find_all('a', href=re.compile(r'\.pdf$', re.I))

            if pdf_links:
                pdf_url = urljoin("https://www.biorxiv.org/", pdf_links[0]['href'])
                return self._download_and_parse_pdf(pdf_url, f"biorxiv_{title[:30]}")

            return {'success': False, 'error': '未找到预印本'}

        except Exception as e:
            return {'success': False, 'error': f'bioRxiv搜索失败: {str(e)}'}

    def _try_publisher_oa(self, url: str, doi: str) -> Dict:
        """尝试从出版商获取OA版本"""
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            # 查找PDF下载链接
            pdf_patterns = [
                r'/download\.pdf',
                r'/content/',
                r'\.full\.pdf',
                r'/article/',
            ]

            for pattern in pdf_patterns:
                links = soup.find_all('a', href=re.compile(pattern, re.I))
                if links:
                    pdf_url = urljoin(url, links[0]['href'])
                    return self._download_and_parse_pdf(pdf_url, f"OA_{doi.replace('/', '_')}")

            return {'success': False, 'error': '未找到PDF链接'}

        except Exception as e:
            return {'success': False, 'error': f'出版商OA失败: {str(e)}'}

    def _download_and_parse_pdf(self, pdf_url: str, filename_base: str) -> Dict:
        """
        下载并解析PDF文件

        Args:
            pdf_url: PDF文件URL
            filename_base: 文件名基础

        Returns:
            解析结果
        """
        try:
            # 下载PDF
            response = requests.get(pdf_url, timeout=30, stream=True)
            response.raise_for_status()

            # 保存到缓存
            filename = os.path.join(self.cache_dir, f"{filename_base}.pdf")
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # 解析PDF
            content = self._parse_pdf(filename)

            return {
                'success': True,
                'content': content,
                'source': 'pdf',
                'pdf_url': pdf_url,
                'cached_file': filename,
                'word_count': len(content.split())
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'PDF处理失败: {str(e)}',
                'pdf_url': pdf_url
            }

    def _parse_pdf(self, pdf_path: str) -> str:
        """
        解析PDF文件内容

        Args:
            pdf_path: PDF文件路径

        Returns:
            提取的文本内容
        """
        try:
            # 首选pdfplumber
            text = self._parse_with_pdfplumber(pdf_path)
            if text:
                return text

            # 备选：PyMuPDF (fitz)
            text = self._parse_with_pymupdf(pdf_path)
            if text:
                return text

            return ""

        except Exception as e:
            return f"PDF解析错误: {str(e)}"

    def _parse_with_pdfplumber(self, pdf_path: str) -> Optional[str]:
        """使用pdfplumber解析PDF"""
        try:
            import pdfplumber

            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                # 限制读取页数，避免超大文件
                max_pages = min(len(pdf.pages), 50)

                for i, page in enumerate(pdf.pages[:max_pages]):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                    except:
                        continue

            if text_parts:
                full_text = '\n'.join(text_parts)
                # 清理文本
                return self._clean_extracted_text(full_text)

            return None

        except Exception:
            return None

    def _parse_with_pymupdf(self, pdf_path: str) -> Optional[str]:
        """使用PyMuPDF解析PDF（备用方案）"""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(pdf_path)
            text_parts = []

            # 限制页数
            max_pages = min(len(doc), 50)

            for page_num in range(max_pages):
                try:
                    page = doc[page_num]
                    page_text = page.get_text()
                    if page_text.strip():
                        text_parts.append(page_text)
                except:
                    continue

            doc.close()

            if text_parts:
                full_text = '\n'.join(text_parts)
                return self._clean_extracted_text(full_text)

            return None

        except Exception:
            return None

    def _clean_extracted_text(self, text: str) -> str:
        """清理提取的文本"""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)

        # 移除页码等干扰信息
        text = re.sub(r'\b\d+\s*[Bb]io[Rr]xi[vv]\b', '', text)
        text = re.sub(r'\bPage\s*\d+\s*of\s*\d+\b', '', text)

        # 移除引用格式
        text = re.sub(r'\[\d+\]', '', text)

        # 限制长度
        if len(text) > 50000:  # 限制约50k字符
            text = text[:50000] + "..."

        return text.strip()

    def get_paper_abstract_fallback(self, pmid: str) -> Dict:
        """
        获取论文详细摘要（备用方案）

        当PDF下载失败时，使用更详细的摘要信息

        Args:
            pmid: PubMed ID

        Returns:
            详细摘要信息
        """
        try:
            handle = Entrez.efetch(db="pubmed", id=pmid, rettype="abstract", retmode="xml")
            record = Entrez.read(handle)
            handle.close()

            if 'PubmedArticle' not in record.keys():
                return {'success': False, 'error': '未找到论文'}

            article = record['PubmedArticle']
            if isinstance(article, list):
                article = article[0]

            medline_citation = article.get('MedlineCitation', article)
            article_data = medline_citation.get('Article', {})

            # 提取完整摘要
            abstract_obj = article_data.get('Abstract')
            abstract_text = ""

            if abstract_obj:
                abstract_text_list = abstract_obj.get('AbstractText')
                if abstract_text_list:
                    if isinstance(abstract_text_list, list):
                        abstract_text = ' '.join([self._to_str(t) for t in abstract_text_list])
                    else:
                        abstract_text = self._to_str(abstract_text_list)

            # 提取标题
            title_obj = article_data.get('ArticleTitle')
            title = self._to_str(title_obj) if title_obj else ""

            # 提取关键词
            keywords = []
            keyword_list = medline_citation.get('KeywordList', [])
            if keyword_list:
                for kw in keyword_list:
                    if isinstance(kw, str):
                        keywords.append(kw)
                    else:
                        keywords.append(self._to_str(kw))

            # 组合详细摘要
            detailed_abstract = {
                'title': title,
                'abstract': abstract_text,
                'keywords': ', '.join(keywords) if keywords else '',
                'full_content': abstract_text  # 作为全文内容的替代
            }

            return {
                'success': True,
                'content': abstract_text,
                'source': 'abstract_detailed',
                'word_count': len(abstract_text.split()) if abstract_text else 0,
                'metadata': detailed_abstract
            }

        except Exception as e:
            return {'success': False, 'error': f'摘要获取失败: {str(e)}'}

    @staticmethod
    def _to_str(value) -> str:
        """安全地将任何值转换为字符串"""
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
        except:
            return ""

    def batch_fetch_papers(self, pmids: List[str], max_concurrent: int = 3) -> List[Dict]:
        """
        批量获取论文全文

        Args:
            pmids: PMID列表
            max_concurrent: 最大并发数

        Returns:
            结果列表
        """
        results = []

        for i, pmid in enumerate(pmids):
            print(f"正在获取 {i+1}/{len(pmids)}: PMID {pmid}...")

            result = self.fetch_paper_content(pmid)
            results.append({
                'pmid': pmid,
                'result': result
            })

            # 避免请求过快
            time.sleep(0.5)

        return results


if __name__ == '__main__':
    # 测试
    fetcher = OAPaperFetcher()

    # 测试PMC论文
    print("测试PMC论文下载...")
    result = fetcher.fetch_paper_content("30390086")  # Nature论文
    print(f"成功: {result['success']}")
    print(f"来源: {result['source']}")
    print(f"字数: {result.get('word_count', 0)}")

    if result['content']:
        print(f"内容预览: {result['content'][:200]}...")
