"""
独立测试 - 绕过缓存
"""
import sys
import os

# 确保使用最新代码
if 'src.utils.pubmed' in sys.modules:
    del sys.modules['src.utils.pubmed']
if 'src.agents.paper_search_agent' in sys.modules:
    del sys.modules['src.agents.paper_search_agent']

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

# 直接导入并测试
from Bio import Entrez

email = os.getenv("PUBMED_EMAIL", "test@example.com")
api_key = os.getenv("PUBMED_API_KEY")

if api_key:
    Entrez.api_key = api_key
Entrez.email = email

print("测试PubMed API解析...")

# 搜索
query = "cancer"
search_handle = Entrez.esearch(db="pubmed", term=query, retmax=2, retmode="xml")
search_results = Entrez.read(search_handle)
search_handle.close()

id_list = search_results.get('IdList', [])
print(f"找到 {len(id_list)} 篇论文")

if id_list:
    fetch_handle = Entrez.efetch(db="pubmed", id=id_list, retmode="xml")
    fetch_results = Entrez.read(fetch_handle)
    fetch_handle.close()

    print(f"EFetch类型: {type(fetch_results)}")

    # 测试键访问
    if hasattr(fetch_results, 'keys'):
        keys = list(fetch_results.keys())
        print(f"键: {keys}")

        if 'PubmedArticle' in keys:
            articles = fetch_results['PubmedArticle']
            print(f"PubmedArticle类型: {type(articles)}, 长度: {len(articles) if hasattr(articles, '__len__') else 'N/A'}")

            if isinstance(articles, list) and len(articles) > 0:
                article = articles[0]
                print(f"\n第一篇文章:")

                # 测试解析
                if hasattr(article, 'MedlineCitation'):
                    medline = article.MedlineCitation
                    if hasattr(medline, 'PMID'):
                        print(f"  PMID: {medline.PMID}")
                    if hasattr(medline, 'Article'):
                        art = medline.Article
                        if hasattr(art, 'ArticleTitle'):
                            print(f"  标题: {str(art.ArticleTitle)[:60]}...")
                        if hasattr(art, 'Abstract'):
                            print(f"  有摘要: 是")
                else:
                    print(f"  article类型: {type(article)}")
                    print(f"  属性: {[a for a in dir(article) if not a.startswith('_')][:10]}")

    print("\n✓ 解析测试成功！")
else:
    print("✗ 没有找到论文")

input("\n按回车退出...")
