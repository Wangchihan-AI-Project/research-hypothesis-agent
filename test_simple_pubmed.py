"""
简单测试 - 使用简单的搜索词
"""
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

print("=" * 60)
print("简单PubMed搜索测试")
print("=" * 60)

from src.utils.pubmed import PubMedSearcher

try:
    # 初始化搜索器
    email = os.getenv("PUBMED_EMAIL", "test@example.com")
    api_key = os.getenv("PUBMED_API_KEY")

    print(f"使用邮箱: {email}")
    print(f"API Key: {'已设置' if api_key else '未设置'}")

    searcher = PubMedSearcher(email=email, api_key=api_key)

    # 测试1：非常简单的搜索
    print("\n[测试1] 简单搜索: 'cancer'")
    papers1 = searcher.search_papers("cancer", max_results=3)
    print(f"结果: 找到 {len(papers1)} 篇论文")
    for p in papers1:
        print(f"  - PMID: {p['pmid']}, 标题: {p['title'][:50]}...")

    # 测试2：稍微复杂一点的搜索
    print("\n[测试2] 布尔搜索: 'cancer AND treatment'")
    papers2 = searcher.search_papers("cancer AND treatment", max_results=2)
    print(f"结果: 找到 {len(papers2)} 篇论文")

    # 测试3：短语搜索
    print("\n[测试3] 短语搜索: '\"machine learning\"'")
    papers3 = searcher.search_papers('"machine learning"', max_results=2)
    print(f"结果: 找到 {len(papers3)} 篇论文")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

except Exception as e:
    print(f"\n测试失败: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n按回车键退出...")
input()
