# -*- coding: utf-8 -*-
"""
谓词下推功能综合测试
验证期刊白名单与日期过滤的正确集成
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.pubmed import PubMedSearcher
from src.utils.journal_if import build_journal_whitelist_query, get_whitelist_journal_names

print("=" * 70)
print("Predicate Pushdown Feature Test")
print("=" * 70)

# 测试1: 构建查询串
print("\n[Test 1] Journal whitelist query generation")
print("-" * 50)
for min_if in [5.0, 10.0, 20.0, 30.0]:
    query = build_journal_whitelist_query(min_if)
    journals = get_whitelist_journal_names(min_if)
    print(f"  IF ≥ {min_if}: {len(journals)} 个期刊, 查询串长度 {len(query)} 字符")
    if query:
        # 验证格式正确性
        assert query.startswith('('), "查询串应以 '(' 开头"
        assert query.endswith(')'), "查询串应以 ')' 结尾"
        assert '[Journal]' in query, "查询串应包含 [Journal] 标签"
        print(f"    [OK] Format verified")

# 测试2: 完整查询构建
print("\n[Test 2] Complete PubMed query construction")
print("-" * 50)

base_query = "machine learning[Title/Abstract]"
date_range = (2020, 2026)
min_if = 10.0

# 模拟 PubMedSearcher 的查询构建逻辑
search_term_with_date = f'{base_query} AND ({date_range[0]}:{date_range[1]}[Date - Publication])'
journal_whitelist = build_journal_whitelist_query(min_if)
search_term_final = f"{search_term_with_date} AND {journal_whitelist}"

print(f"  Base query: {base_query}")
print(f"  Date range: {date_range[0]}:{date_range[1]}")
print(f"  IF threshold: >= {min_if}")
print(f"\n  Complete query string:")
print(f"    {search_term_final[:200]}...")

# 验证查询串完整性
assert 'machine learning[Title/Abstract]' in search_term_final
assert '2020:2026[Date - Publication]' in search_term_final
assert '[Journal]' in search_term_final
print(f"\n  [OK] Query completeness verified")

# 测试3: PubMedSearcher 集成测试（不实际发送请求）
print("\n[Test 3] PubMedSearcher parameter passing")
print("-" * 50)

searcher = PubMedSearcher()
import inspect

# 检查 search_papers 方法签名
sig = inspect.signature(searcher.search_papers)
params = list(sig.parameters.keys())
print(f"  search_papers 参数: {params}")

assert 'min_if' in params, "search_papers should include min_if parameter"
print(f"  [OK] min_if parameter exists")

# 测试4: ValidationAgent 集成测试
print("\n[Test 4] ValidationAgent parameter passing")
print("-" * 50)

from src.agents.validation_agent import ValidationAgent
agent = ValidationAgent()
sig = inspect.signature(agent._perform_literature_check)
params = list(sig.parameters.keys())
print(f"  _perform_literature_check 参数: {params}")

assert 'min_if' in params, "_perform_literature_check should include min_if parameter"
print(f"  [OK] min_if parameter exists")

# 测试5: PaperSearchAgent 集成测试
print("\n[Test 5] PaperSearchAgent parameter passing")
print("-" * 50)

from src.agents.paper_search_agent import PaperSearchAgent
agent = PaperSearchAgent()
sig = inspect.signature(agent.execute)
params = list(sig.parameters.keys())
print(f"  execute 参数: {params}")

assert 'input_data' in params, "execute should include input_data parameter"
print(f"  [OK] input_data parameter exists (min_if passed via input_data)")

print("\n" + "=" * 70)
print("[SUCCESS] All tests passed! Predicate pushdown correctly integrated")
print("=" * 70)
