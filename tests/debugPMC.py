# -*- coding: utf-8 -*-
"""
调试PMC和摘要获取
"""
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

from Bio import Entrez
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 配置
Entrez.email = "test@example.com"

print("=" * 80)
print("PMC和摘要获取调试")
print("=" * 80)

# 测试1: 直接获取PubMed摘要
print("\n[测试1] 获取PubMed摘要")
print("-" * 50)
pmid = "30390086"

try:
    handle = Entrez.efetch(db="pubmed", id=pmid, rettype="abstract", retmode="xml")
    record = Entrez.read(handle)
    handle.close()

    print(f"记录键: {list(record.keys())}")

    if 'PubmedArticle' in record.keys():
        article = record['PubmedArticle']
        if isinstance(article, list):
            article = article[0]

        medline_citation = article.get('MedlineCitation', article)
        article_data = medline_citation.get('Article', {})

        # 标题
        title = article_data.get('ArticleTitle')
        print(f"标题类型: {type(title)}")
        print(f"标题: {title}")

        # 摘要
        abstract_obj = article_data.get('Abstract')
        print(f"摘要对象: {abstract_obj}")

        if abstract_obj:
            abstract_text = abstract_obj.get('AbstractText')
            print(f"摘要文本类型: {type(abstract_text)}")
            if abstract_text:
                if isinstance(abstract_text, list):
                    for i, t in enumerate(abstract_text):
                        print(f"摘要段落 {i+1}: {str(t)[:100]}...")
                else:
                    print(f"摘要: {str(abstract_text)[:200]}...")

except Exception as e:
    import traceback
    print(f"错误: {e}")
    traceback.print_exc()

# 测试2: 搜索PMC
print("\n[测试2] 搜索PMC")
print("-" * 50)

try:
    search_handle = Entrez.esearch(db="pmc", term=f"{pmid}[pmid]", retmax=1)
    search_result = Entrez.read(search_handle)
    search_handle.close()

    print(f"搜索结果: {search_result}")
    print(f"PMCID列表: {search_result.get('IdList', [])}")

    if search_result.get('IdList'):
        pmcid = search_result['IdList'][0]
        print(f"找到PMCID: {pmcid}")

        # 获取PMC记录
        pmc_handle = Entrez.efetch(db="pmc", id=pmcid, rettype="full", retmode="xml")
        pmc_record = Entrez.read(pmc_handle)
        pmc_handle.close()

        print(f"PMC记录键: {list(pmc_record.keys())}")

except Exception as e:
    import traceback
    print(f"PMC搜索错误: {e}")
    traceback.print_exc()

# 测试3: 使用已知有PMC版本的论文
print("\n[测试3] 已知OA论文")
print("-" * 50)

# 这是一个已知有PMC版本的论文
oa_pmid = "27525504"  # PLOS ONE 论文
print(f"测试PMID: {oa_pmid}")

try:
    handle = Entrez.efetch(db="pubmed", id=oa_pmid, rettype="abstract", retmode="xml")
    record = Entrez.read(handle)
    handle.close()

    if 'PubmedArticle' in record.keys():
        article = record['PubmedArticle']
        if isinstance(article, list):
            article = article[0]

        medline_citation = article.get('MedlineCitation', article)
        article_data = medline_citation.get('Article', {})

        title = article_data.get('ArticleTitle')
        print(f"标题: {title}")

        abstract_obj = article_data.get('Abstract')
        if abstract_obj:
            abstract_text = abstract_obj.get('AbstractText')
            if abstract_text:
                if isinstance(abstract_text, list):
                    full_abstract = ' '.join([str(t) for t in abstract_text])
                else:
                    full_abstract = str(abstract_text)
                print(f"摘要长度: {len(full_abstract)} 字符")
                print(f"摘要预览: {full_abstract[:200]}...")

except Exception as e:
    import traceback
    print(f"错误: {e}")
    traceback.print_exc()

print("\n" + "=" * 80)
