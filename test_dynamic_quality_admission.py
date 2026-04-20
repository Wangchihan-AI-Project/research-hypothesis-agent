# -*- coding: utf-8 -*-
"""
动态质量准入制测试脚本
验证两阶段检索和相关性阈值筛选
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.pubmed import PubMedSearcher, ZeroResultsError

print("=" * 70)
print("动态质量准入制测试")
print("=" * 70)

searcher = PubMedSearcher()

# 测试1: 无限制模式（获取所有符合条件的文献）
print("\n[测试1] 无限制模式 - 应获取所有符合IF阈值的文献")
print("-" * 50)
try:
    papers = searcher.search_papers(
        query="CRISPR gene editing[Title/Abstract]",
        max_results=None,  # 无限制
        date_range=(2023, 2026),
        min_if=10.0
    )
    print(f"[成功] 获取到 {len(papers)} 篇文献")
    if papers:
        print(f"  第一篇: {papers[0].get('title', 'Unknown')[:60]}...")
        print(f"  期刊: {papers[0].get('journal', 'Unknown')}")
except ZeroResultsError as e:
    print(f"[零结果] {e}")
except Exception as e:
    print(f"[错误] {e}")

# 测试2: 固定数量模式（向后兼容）
print("\n[测试2] 固定数量模式 - 应限制在指定数量")
print("-" * 50)
try:
    papers = searcher.search_papers(
        query="machine learning[Title/Abstract]",
        max_results=5,  # 固定数量
        date_range=(2024, 2026),
        min_if=0  # 无IF限制
    )
    print(f"[成功] 获取到 {len(papers)} 篇文献 (限制5篇)")
    if len(papers) <= 5:
        print(f"  [通过] 数量符合限制")
    else:
        print(f"  [失败] 数量超出限制: {len(papers)} > 5")
except Exception as e:
    print(f"[错误] {e}")

# 测试3: 零结果检测
print("\n[测试3] 零结果检测 - 应抛出ZeroResultsError")
print("-" * 50)
try:
    papers = searcher.search_papers(
        query="xyzabc123nonexistentterm123456[Title/Abstract]",
        max_results=None,
        min_if=50.0  # 极高IF阈值，确保无结果
    )
    print(f"[失败] 应抛出ZeroResultsError，但返回了 {len(papers)} 篇")
except ZeroResultsError as e:
    print(f"[通过] 正确抛出ZeroResultsError")
    print(f"  消息: {e}")
except Exception as e:
    print(f"[其他错误] {e}")

# 测试4: search_by_idea 的动态质量准入
print("\n[测试4] search_by_idea - 动态质量准入")
print("-" * 50)
result = searcher.search_by_idea(
    idea="single cell sequencing CRISPR screening",
    max_results=None,  # 动态质量准入
    start_year=2023,
    min_if=10.0,
    relevance_threshold=7.0
)
print(f"  获取到 {len(result.get('papers', []))} 篇文献")
if 'suggestion' in result:
    print(f"  建议: {result['suggestion']}")
if result.get('papers'):
    print(f"  第一篇: {result['papers'][0].get('title', 'Unknown')[:60]}...")

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)
