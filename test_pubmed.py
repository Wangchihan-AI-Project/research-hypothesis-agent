"""
快速测试PubMed搜索
"""
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

print("=" * 60)
print("测试PubMed搜索")
print("=" * 60)

from src.utils.pubmed import PubMedSearcher

try:
    # 初始化搜索器
    searcher = PubMedSearcher(
        email="wanghan3698@gmail.com",
        api_key="2ee2706d111ff8ff5ccce94a25d883fb5709"
    )

    # 测试1：简单搜索
    print("\n[测试1] 简单搜索: 'bioinformatics'")
    papers1 = searcher.search_papers("bioinformatics", max_results=3)
    print(f"结果: 找到 {len(papers1)} 篇论文")

    # 测试2：带引号的搜索
    print("\n[测试2] 带引号的搜索（应该自动清理）")
    test_query = 'Find papers exploring "drug repurposing" in networks'
    papers2 = searcher.search_papers(test_query, max_results=2)
    print(f"结果: 找到 {len(papers2)} 篇论文")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

except Exception as e:
    print(f"\n测试失败: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n按任意键退出...")
input()