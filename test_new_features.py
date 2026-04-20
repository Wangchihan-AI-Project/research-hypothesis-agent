# -*- coding: utf-8 -*-
"""
测试新功能：日期范围过滤、IF范围过滤、想法检索
"""
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from src.utils.pubmed import PubMedSearcher
from src.core.db_manager import get_db_manager
from src.core.database import Paper
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 80)
print("新功能测试：日期范围、IF范围、想法检索")
print("=" * 80)

searcher = PubMedSearcher(email="test@example.com")

# 测试1: 从数据库获取论文用于测试
print("\n[测试1] 从数据库获取论文用于测试...")
db_manager = get_db_manager()
with db_manager.get_session() as session:
    papers = session.query(Paper).limit(20).all()
    papers_data = []
    for p in papers:
        papers_data.append({
            'id': p.id,
            'pmid': p.pmid,
            'title': p.title,
            'journal': p.journal,
            'publication_date': p.publication_date
        })

print(f"  获取 {len(papers_data)} 篇论文")

# 显示一些论文信息
print("\n  论文样例:")
for p in papers_data[:5]:
    print(f"    - {p['title'][:50]}... | {p['journal']} | {p['publication_date']}")

# 测试2: 日期范围过滤
print("\n[测试2] 日期范围过滤...")
print("  过滤条件: 2020-2024年")

filtered = searcher.filter_papers_by_date_range(papers_data, start_year=2020, end_year=2024)
print(f"  结果: {len(papers_data)} -> {len(filtered)} 篇")

for p in filtered[:3]:
    print(f"    - {p['title'][:50]}... ({p['publication_date']})")

# 测试3: IF范围过滤
print("\n[测试3] 影响因子范围过滤...")
print("  过滤条件: IF >= 10.0")

filtered = searcher.filter_papers_by_if_range(papers_data, min_if=10.0)
print(f"  结果: {len(papers_data)} -> {len(filtered)} 篇")

for p in filtered[:3]:
    journal = p['journal']
    from src.utils.journal_if import get_journal_if
    if_val = get_journal_if(journal)
    print(f"    - {journal} (IF: {if_val})")

# 测试4: IF范围过滤（双向）
print("\n[测试4] 影响因子范围过滤（5.0 <= IF <= 20.0）...")

filtered = searcher.filter_papers_by_if_range(papers_data, min_if=5.0, max_if=20.0)
print(f"  结果: {len(papers_data)} -> {len(filtered)} 篇")

for p in filtered[:3]:
    journal = p['journal']
    from src.utils.journal_if import get_journal_if
    if_val = get_journal_if(journal)
    print(f"    - {journal} (IF: {if_val})")

# 测试5: 想法检索
print("\n[测试5] 想法检索（AI辅助）...")
idea = "我想研究用深度学习分析基因测序数据来预测疾病风险"
print(f"  用户想法: {idea}")

from dotenv import load_dotenv
load_dotenv()

result = searcher.search_by_idea(idea, max_results=3)
print(f"  AI生成的搜索词: {result.get('search_terms', 'N/A')}")
print(f"  找到论文: {len(result.get('papers', []))} 篇")

for p in result.get('papers', [])[:2]:
    print(f"    - {p.get('title', 'N/A')[:60]}...")

# 测试6: 想法检索 + 过滤
print("\n[测试6] 想法检索 + 高级过滤...")
idea2 = "CRISPR 基因编辑治疗癌症"
print(f"  用户想法: {idea2}")
print(f"  过滤条件: 2020年后, IF >= 5.0")

result2 = searcher.search_by_idea(
    idea2,
    max_results=10,
    start_year=2020,
    min_if=5.0
)
print(f"  AI生成的搜索词: {result2.get('search_terms', 'N/A')}")
print(f"  找到论文: {len(result2.get('papers', []))} 篇")

print("\n" + "=" * 80)
print("测试完成!")
print("=" * 80)
