"""
简单测试 - 期刊IF
"""
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent/src/utils')

from journal_if import get_journal_if, get_journal_if_with_source

# 测试期刊
test_journals = [
    "Nature",
    "Science",
    "Cell",
    "Bioinformatics",
    "PLOS ONE",
    "Nature Communications",
    "Lancet",
    "JAMA",
    "Unknown Journal",
]

print("Journal IF Test")
print("-" * 50)
for j in test_journals:
    if_val, source = get_journal_if_with_source(j)
    print(f"{j:35s} IF={if_val:5.1f} ({source})")
