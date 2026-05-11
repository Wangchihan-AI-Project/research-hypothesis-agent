"""
调试日期解析 - 查看实际数据结构
"""
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from src.utils.pubmed import PubMedSearcher
from Bio import Entrez

Entrez.email = "test@example.com"

# 获取一篇论文的原始数据
pmid = "38786024"  # 刚才测试中的 PMID
print(f"Fetching PMID: {pmid}")

handle = Entrez.efetch(db="pubmed", id=pmid, rettype="abstract", retmode="xml")
records = Entrez.read(handle)
handle.close()

print("\n=== Raw PubMed Data Structure ===")
import pprint
pprint.pprint(dict(records))

# 尝试解析
searcher = PubMedSearcher(email="test@example.com")
article = records['PubmedArticle']
if isinstance(article, list):
    article = article[0]

print("\n=== Parsed Result ===")
paper = searcher._parse_pubmed_article(article, "test")
if paper:
    print(f"Title: {paper['title'][:60]}...")
    print(f"Journal: {paper.get('journal', 'N/A')}")
    print(f"Date: {paper.get('publication_date', 'N/A')}")
