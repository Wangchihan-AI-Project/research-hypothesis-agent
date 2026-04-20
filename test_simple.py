import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

from src.utils.pubmed import PubMedSearcher

print("=" * 60)
print("测试PubMed搜索")
print("=" * 60)

try:
    searcher = PubMedSearcher(
        email="wanghan3698@gmail.com",
        api_key="2ee2706d111ff8ff5ccce94a25d883fb5709"
    )

    print("\n测试搜索: 'bioinformatics'")
    papers = searcher.search_papers("bioinformatics", max_results=3)

    print(f"\n结果: 找到 {len(papers)} 篇论文")
    for i, paper in enumerate(papers[:3], 1):
        if paper.get('pmid'):
            print(f"\n{i}. PMID: {paper['pmid']}")
            print(f"   标题: {paper['title'][:70]}...")
        else:
            print(f"\n{i}. (无效)")

    print("\n" + "=" * 60)
    print("测试完成")

except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()