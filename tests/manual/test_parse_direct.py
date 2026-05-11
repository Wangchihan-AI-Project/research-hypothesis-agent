"""
直接测试PubMed解析
"""
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

from Bio import Entrez

# 配置
email = os.getenv("PUBMED_EMAIL", "test@example.com")
api_key = os.getenv("PUBMED_API_KEY")

if api_key:
    Entrez.api_key = api_key
Entrez.email = email

print("=" * 60)
print("测试PubMed解析")
print("=" * 60)

# 搜索
query = "machine learning"
print(f"\n搜索: {query}")

search_handle = Entrez.esearch(db="pubmed", term=query, retmax=3, retmode="xml")
search_results = Entrez.read(search_handle)
search_handle.close()

id_list = search_results.get('IdList', [])
print(f"找到ID: {id_list}")

if id_list:
    fetch_handle = Entrez.efetch(db="pubmed", id=id_list, retmode="xml")
    fetch_results = Entrez.read(fetch_handle)
    fetch_handle.close()

    print(f"\nEFetch结果类型: {type(fetch_results)}")

    # 检查键
    if hasattr(fetch_results, 'keys'):
        keys = list(fetch_results.keys())
        print(f"键: {keys}")

        if 'PubmedArticle' in keys:
            articles = fetch_results['PubmedArticle']
            print(f"PubmedArticle类型: {type(articles)}")

            if isinstance(articles, list):
                print(f"文章数量: {len(articles)}")

                # 解析第一篇
                if articles:
                    article = articles[0]
                    print(f"\n第一篇文章类型: {type(article)}")

                    # 检查属性
                    if hasattr(article, 'MedlineCitation'):
                        medline = article.MedlineCitation
                        if hasattr(medline, 'PMID'):
                            print(f"PMID: {medline.PMID}")
                        if hasattr(medline, 'Article'):
                            art = medline.Article
                            if hasattr(art, 'ArticleTitle'):
                                print(f"标题: {art.ArticleTitle}")

print("\n" + "=" * 60)
