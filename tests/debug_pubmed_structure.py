"""
查看 PubMed API 返回的原始数据结构
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
print("查看PubMed API返回数据结构")
print("=" * 60)

# 搜索
query = "cancer"
print(f"\n搜索: {query}")

search_handle = Entrez.esearch(db="pubmed", term=query, retmax=2, retmode="xml")
search_results = Entrez.read(search_handle)
search_handle.close()

id_list = search_results.get('IdList', [])
print(f"找到ID: {id_list}")

if id_list:
    fetch_handle = Entrez.efetch(db="pubmed", id=id_list, retmode="xml")
    fetch_results = Entrez.read(fetch_handle)
    fetch_handle.close()

    print(f"\nEFetch结果类型: {type(fetch_results)}")

    # 检查属性
    if hasattr(fetch_results, '__dict__'):
        print(f"__dict__ keys: {list(fetch_results.__dict__.keys())}")

    # 检查是否可以像字典一样访问
    if hasattr(fetch_results, 'keys'):
        print(f"keys(): {list(fetch_results.keys())}")

    # 尝试不同的访问方式
    print("\n尝试访问方式:")

    # 方式1: 属性
    if hasattr(fetch_results, 'PubmedArticle'):
        print("1. fetch_results.PubmedArticle - 存在")
    else:
        print("1. fetch_results.PubmedArticle - 不存在")

    # 方式2: 字典键
    if hasattr(fetch_results, '__getitem__'):
        try:
            if 'PubmedArticle' in fetch_results.keys():
                print("2. fetch_results['PubmedArticle'] - 存在")
                pa = fetch_results['PubmedArticle']
                print(f"   类型: {type(pa)}, 长度: {len(pa) if hasattr(pa, '__len__') else 'N/A'}")
        except Exception as e:
            print(f"2. fetch_results['PubmedArticle'] - 错误: {e}")

    # 方式3: 直接迭代
    print("\n3. 尝试直接迭代:")
    try:
        for item in fetch_results:
            print(f"   项目类型: {type(item)}")
            break
    except Exception as e:
        print(f"   错误: {e}")

    # 打印前500个字符
    print(f"\n原始内容预览:")
    print(str(fetch_results)[:500])

print("\n" + "=" * 60)
