"""
测试PubMed搜索功能 - 使用简单关键词
"""
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

print("=" * 60)
print("测试PubMed搜索 - 简单关键词")
print("=" * 60)

from src.utils.pubmed import PubMedSearcher

# 从环境变量获取配置
email = os.getenv("PUBMED_EMAIL", "test@example.com")
api_key = os.getenv("PUBMED_API_KEY")

searcher = PubMedSearcher(email=email, api_key=api_key)

# 测试1：非常简单的关键词
print("\n[测试1] 搜索: 'cancer'")
papers1 = searcher.search_papers("cancer", max_results=5)
print(f"结果: {len(papers1)} 篇")
if papers1:
    print(f"第一篇: PMID={papers1[0]['pmid']}, 标题: {papers1[0]['title'][:60]}...")

# 测试2：稍微复杂一点
print("\n[测试2] 搜索: 'machine learning cancer'")
papers2 = searcher.search_papers("machine learning cancer", max_results=3)
print(f"结果: {len(papers2)} 篇")

# 测试3：使用布尔运算符
print("\n[测试3] 搜索: 'cancer AND treatment'")
papers3 = searcher.search_papers("cancer AND treatment", max_results=3)
print(f"结果: {len(papers3)} 篇")

# 测试4：使用引号的精确搜索
print("\n[测试4] 搜索: '\"neural networks\"'")
papers4 = searcher.search_papers('"neural networks"', max_results=3)
print(f"结果: {len(papers4)} 篇")

# 测试5：测试你原来的复杂查询
print("\n[测试5] 复杂查询（可能找不到）:")
complex_query = '("Neural ODEs" OR "Continuous-time Dynamic Graphs" OR "Temporal Graph Networks" OR "TGN") AND ("Disease Trajectories" OR "Multimorbidity Cascades" OR "Tipping Point") AND "Longitudinal"'
print(f"查询: {complex_query[:80]}...")
papers5 = searcher.search_papers(complex_query, max_results=10)
print(f"结果: {len(papers5)} 篇")

# 测试6：尝试简化版
print("\n[测试6] 简化版查询: 'temporal graphs disease'")
papers6 = searcher.search_papers("temporal graphs disease", max_results=5)
print(f"结果: {len(papers6)} 篇")

print("\n" + "=" * 60)
print("结论:")
print("- 如果测试1-4有结果，说明搜索功能正常")
print("- 复杂查询找不到结果是因为关键词太具体，PubMed中没有匹配的论文")
print("- 建议：简化搜索关键词，或者分开搜索")
print("=" * 60)
