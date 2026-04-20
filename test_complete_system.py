# -*- coding: utf-8 -*-
"""
完整测试 - PubMed 搜索 + 日期解析 + IF 获取
"""
import sys
import io
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

# 设置输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.utils.pubmed import PubMedSearcher
from src.utils.journal_if import get_journal_if_with_source
import json

print("=" * 70)
print("完整系统测试 - PubMed 搜索 + 日期解析 + IF 获取")
print("=" * 70)

# 初始化搜索器
searcher = PubMedSearcher(email="test@example.com")

# 测试搜索关键词
test_queries = [
    "Nature CRISPR",
    "Science machine learning",
]

for query in test_queries:
    print(f"\n{'=' * 70}")
    print(f"搜索关键词: {query}")
    print('=' * 70)

    try:
        papers = searcher.search_papers(query, max_results=3)

        if not papers:
            print("未找到论文")
            continue

        print(f"找到 {len(papers)} 篇论文\n")

        for i, paper in enumerate(papers, 1):
            print(f"[论文 {i}]")
            print(f"  PMID: {paper.get('pmid', 'N/A')}")

            # 标题
            title = paper.get('title', 'N/A')
            print(f"  标题: {title[:60]}{'...' if len(title) > 60 else ''}")

            # 期刊
            journal = paper.get('journal', 'N/A')
            print(f"  期刊: {journal}")

            # 期刊 IF
            if journal and journal != 'N/A':
                if_val, source = get_journal_if_with_source(journal)
                if if_val > 0:
                    print(f"  影响因子: {if_val:.1f} (来源: {source})")
                else:
                    print(f"  影响因子: 未知")

            # 发表日期
            pub_date = paper.get('publication_date', 'N/A')
            print(f"  发表日期: {pub_date}")

            # 日期质量评估
            if pub_date and pub_date != 'N/A':
                try:
                    year = int(pub_date[:4])
                    current_year = 2025
                    if 1990 <= year <= current_year + 1:
                        print(f"  日期状态: OK")
                    else:
                        print(f"  日期状态: 异常年份")
                except:
                    print(f"  日期状态: 解析失败")
            else:
                print(f"  日期状态: 未获取")

            print()

    except Exception as e:
        print(f"搜索出错: {e}")
        import traceback
        traceback.print_exc()

print("=" * 70)
print("测试完成")
print("=" * 70)
