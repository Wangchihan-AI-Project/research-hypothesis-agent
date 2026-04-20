"""
诊断PubMed解析问题
"""
import sys
import os
from Bio import Entrez
import json

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

print("=" * 60)
print("诊断PubMed解析问题")
print("=" * 60)

# 从环境变量获取配置
email = os.getenv("PUBMED_EMAIL", "test@example.com")
api_key = os.getenv("PUBMED_API_KEY")

if api_key:
    Entrez.api_key = api_key
Entrez.email = email

# 使用一个简单的查询
query = "bioinformatics"

print(f"\n[1] 搜索关键词: {query}")
try:
    search_handle = Entrez.esearch(
        db="pubmed",
        term=query,
        retmax=3,
        sort="relevance",
        retmode="xml"
    )
    search_results = Entrez.read(search_handle)
    search_handle.close()

    # 提取PMID列表
    id_list = search_results.get('IdList', [])
    print(f"找到 {len(id_list)} 篇论文的ID: {id_list}")

    if not id_list:
        print("没有找到论文，退出。")
        sys.exit(1)

    print(f"\n[2] 获取详细信息...")
    fetch_handle = Entrez.efetch(
        db="pubmed",
        id=id_list,
        rettype="abstract",
        retmode="xml"
    )
    fetch_results = Entrez.read(fetch_handle)
    fetch_handle.close()

    print(f"EFetch返回类型: {type(fetch_results)}")
    print(f"EFetch属性: {[a for a in dir(fetch_results) if not a.startswith('_')]}")

    # 检查PubmedArticle
    if hasattr(fetch_results, 'PubmedArticle'):
        articles_list = fetch_results.PubmedArticle
        print(f"\nPubmedArticle类型: {type(articles_list)}")
        print(f"PubmedArticle是列表: {isinstance(articles_list, list)}")

        # 尝试转换为列表
        if hasattr(articles_list, '__iter__'):
            pubmed_articles = list(articles_list)
            print(f"转换后列表长度: {len(pubmed_articles)}")
        else:
            print("PubmedArticle不可迭代")
            pubmed_articles = []

        # 解析第一篇
        if pubmed_articles:
            print(f"\n[3] 解析第一篇论文...")
            article = pubmed_articles[0]
            print(f"Article类型: {type(article)}")
            print(f"Article属性: {[a for a in dir(article) if not a.startswith('_')][:20]}")

            # 检查MedlineCitation
            if hasattr(article, 'MedlineCitation'):
                medline = article.MedlineCitation
                print(f"\nMedlineCitation类型: {type(medline)}")

                if hasattr(medline, 'PMID'):
                    pmid = medline.PMID
                    print(f"PMID: {pmid} (类型: {type(pmid)})")

                if hasattr(medline, 'Article'):
                    art = medline.Article
                    print(f"Article类型: {type(art)}")

                    if hasattr(art, 'ArticleTitle'):
                        title = art.ArticleTitle
                        print(f"标题: {title} (类型: {type(title)})")

                    if hasattr(art, 'Abstract'):
                        abstract = art.Abstract
                        print(f"Abstract类型: {type(abstract)}")
                        if hasattr(abstract, 'AbstractText'):
                            abs_text = abstract.AbstractText
                            print(f"AbstractText类型: {type(abs_text)}")
                            if isinstance(abs_text, list):
                                print(f"AbstractText是列表，长度: {len(abs_text)}")
                            else:
                                print(f"AbstractText内容(前100字符): {str(abs_text)[:100]}")
    else:
        print("\n[错误] fetch_results没有PubmedArticle属性!")
        print(f"实际内容: {fetch_results}")

except Exception as e:
    print(f"\n[错误] {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
