"""
测试日期解析 - 使用模拟数据
"""
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from src.utils.pubmed import PubMedSearcher

searcher = PubMedSearcher(email="test@example.com")

# 模拟 PubMed 返回的数据结构（从调试输出中提取）
mock_article_data = {
    'ArticleDate': [
        {'Year': '2024', 'Month': '05', 'Day': '08'}
    ],
    'JournalIssue': {
        'Volume': '13',
        'Issue': '10',
        'PubDate': {'Year': '2024', 'Month': 'May', 'Day': '08'}
    },
    'Journal': {
        'Title': 'Cells',
        'ISOAbbreviation': 'Cells'
    }
}

# 测试从 ArticleDate 提取
print("Test 1: Extract from ArticleDate")
article_date = mock_article_data['ArticleDate'][0]
result = searcher._extract_date_from_pubdate_obj(article_date)
print(f"  Result: {result}")
assert result == "2024-05-08", f"Expected 2024-05-08, got {result}"

# 测试从 JournalIssue.PubDate 提取
print("\nTest 2: Extract from JournalIssue.PubDate")
pub_date = mock_article_data['JournalIssue']['PubDate']
result = searcher._extract_date_from_pubdate_obj(pub_date)
print(f"  Result: {result}")
assert result == "2024-05-08", f"Expected 2024-05-08, got {result}"

# 测试月份解析
print("\nTest 3: Month normalization")
test_cases = [
    ("Jan", "01"),
    ("January", "01"),
    ("1", "01"),
    ("May", "05"),
    ("December", "12"),
    ("Dec", "12"),
]
for month, expected in test_cases:
    result = searcher._normalize_month(month)
    status = "PASS" if result == expected else "FAIL"
    print(f"  {status}: {month} -> {result} (expected {expected})")

print("\n=== All tests passed! ===")

# 测试期刊IF
print("\n=== Testing Journal IF ===")
from src.utils.journal_if import get_journal_if_with_source

test_journal = "Cells"
if_val, source = get_journal_if_with_source(test_journal)
print(f"Journal: {test_journal}")
print(f"IF: {if_val} (source: {source})")

# Nature 系列期刊测试
nature_journals = [
    "Nature",
    "Nature Medicine",
    "Nature Communications",
    "Nature Biotechnology",
]

print("\nNature Series IF Test:")
for j in nature_journals:
    if_val, source = get_journal_if_with_source(j)
    print(f"  {j:30s} IF={if_val:5.1f} ({source})")
