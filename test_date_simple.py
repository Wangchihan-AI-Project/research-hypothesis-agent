"""
测试日期解析
"""
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from src.utils.pubmed import PubMedSearcher

searcher = PubMedSearcher(email="test@example.com")

# 测试日期提取方法
print("Testing date extraction methods")
print("-" * 40)

# 测试各种 PubDate 格式
test_cases = [
    # 模拟各种 PubDate 对象结构
    {"Year": "2023", "Month": "Jan", "Day": "15"},
    {"Year": "2023", "Month": "January"},
    {"Year": "2023", "Month": "1"},
    {"Year": "2022", "MedlineDate": "2022 Jan-Mar"},
    {"Year": "2021"},
    {"Year": "2023", "Month": "12", "Day": "1"},
]

for case in test_cases:
    result = searcher._extract_date_from_pubdate_obj(case)
    print(f"Input: {case} => Output: {result}")

print("\nSearching real papers from PubMed...")
papers = searcher.search_papers("CRISPR", max_results=3)
print(f"\nFound {len(papers)} papers")

for i, p in enumerate(papers, 1):
    print(f"\n[{i}] PMID: {p['pmid']}")
    print(f"    Journal: {p.get('journal', 'N/A')}")
    print(f"    Date: {p.get('publication_date', 'N/A')}")
    print(f"    Title: {p.get('title', 'N/A')[:50]}...")
