# -*- coding: utf-8 -*-
"""
两阶段漏��过滤搜索测试
Test Two-Stage Funnel Screening
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv(project_root / '.env', encoding='utf-8')

from src.agents.paper_search_agent import PaperSearchAgent
from src.utils.relevance_scorer import RelevanceScorer

print("=" * 70)
print("两阶段漏斗过滤搜索测试")
print("Two-Stage Funnel Screening Test")
print("=" * 70)

# 初始化智能体
agent = PaperSearchAgent()

# 测试参数
test_query = "machine learning cancer genomics"
stage1_max = 100  # 测试用，实际生产可用500
stage2_top_k = 10  # 测试用，实际生产可用40

print(f"\n测试参数:")
print(f"  查询: {test_query}")
print(f"  第一阶段粗筛: {stage1_max} 篇")
print(f"  第二阶段精选: {stage2_top_k} 篇")

# 执行两阶段漏斗搜索
print("\n开始执行...")

result = agent.execute_two_stage_funnel({
    'query': test_query,
    'stage1_max': stage1_max,
    'stage2_top_k': stage2_top_k,
    'fetch_full_text': False,  # 测试时暂不获取全文，加快速度
    'enable_filter': False
})

if result['success']:
    print("\n" + "=" * 70)
    print("✅ 测试成功!")
    print("=" * 70)

    # 显示第一阶段统计
    if result.get('stage1_stats'):
        s1 = result['stage1_stats']
        print(f"\n📊 第一阶段（粗筛）:")
        print(f"  获取文献: {s1.get('total_fetched', 0)} 篇")
        print(f"  评分筛选: {s1.get('selected_papers', 0)} 篇")
        print(f"  评分范围: {s1.get('min_score', 0):.3f} - {s1.get('max_score', 0):.3f}")

    # 显示第二阶段统计
    if result.get('stage2_stats'):
        s2 = result['stage2_stats']
        print(f"\n📊 第二阶段（精读）:")
        print(f"  处理文献: {s2.get('total_processed', 0)} 篇")

    # 显示精选论文
    papers = result['papers']
    print(f"\n📖 精选论文 Top {len(papers)}:")
    print("-" * 70)

    for i, paper in enumerate(papers, 1):
        score = paper.get('relevance_score', 0)
        title = paper.get('title', 'N/A')
        pmid = paper.get('pmid', 'N/A')
        journal = paper.get('journal', 'N/A')

        print(f"\n{i}. 评分: {score:.3f} | PMID: {pmid}")
        print(f"   标题: {title[:70]}...")
        print(f"   期刊: {journal}")

    # 验证关键功能
    print("\n" + "=" * 70)
    print("功能验证:")
    print("-" * 70)

    checks = [
        ("论文数量正确", len(papers) <= stage2_top_k),
        ("包含评分字段", all('relevance_score' in p for p in papers)),
        ("评分降序排列", papers == sorted(papers, key=lambda x: x.get('relevance_score', 0), reverse=True)),
        ("包含PMID", all(p.get('pmid') for p in papers)),
        ("包含标题", all(p.get('title') for p in papers)),
    ]

    for check_name, passed in checks:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {check_name}")

    all_passed = all(passed for _, passed in checks)

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ 所有测试通过!")
    else:
        print("❌ 部分测试失败，请检查")
    print("=" * 70)

else:
    print("\n" + "=" * 70)
    print("❌ 测试失败!")
    print("=" * 70)
    print(f"错误: {result.get('error')}")

print("\n测试完成")
