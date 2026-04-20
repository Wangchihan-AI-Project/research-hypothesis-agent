# -*- coding: utf-8 -*-
"""
自动化全流程测试
关键词: machine learning
人工干预部分自动选择假设1
"""
import sys
import os
import json

sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent/src')

print("=" * 70)
print("自动化全流程测试 - Human-in-the-Loop")
print("关键词: machine learning")
print("自动选择: 假设 1")
print("=" * 70)

# Import components
from core.orchestrator import Orchestrator
from agents.hypothesis_agent import ChiefScientistAgent
from agents.validation_agent import ValidationAgent

# Initialize
print("\n[Step 1] 初始化系统...")
orchestrator = Orchestrator()
hypothesis_agent = ChiefScientistAgent()
validation_agent = ValidationAgent()
print("  [OK] 所有智能体初始化完成")

# Step 2: Start session
print("\n[Step 2] 启动研究会话...")
query = "machine learning"
session_result = orchestrator.start_session(query)
if session_result['success']:
    session_id = session_result['session_id']
    print(f"  [OK] 会话已启动 (ID: {session_id})")
else:
    print(f"  [FAIL] {session_result.get('error')}")
    sys.exit(1)

# Step 3: Search papers (减少搜索数量加快速度)
print("\n[Step 3] 文献侦察员搜索 PubMed...")
print("  (搜索中...)")

search_result = orchestrator.search_papers(
    query,
    max_results=10,  # 减少搜索数量
    enable_filter=False,
    fetch_full_text=True,
    max_full_text=3  # 减少全文获取数量
)

if not search_result['success']:
    print(f"  [FAIL] {search_result.get('error')}")
    sys.exit(1)

papers = search_result['papers']
print(f"  [OK] 找到 {len(papers)} 篇文献")

# Show paper titles
print("\n  论文标题 (前5篇):")
for i, paper in enumerate(papers[:5], 1):
    title = paper.get('title', 'N/A')
    if len(title) > 60:
        title = title[:60] + "..."
    print(f"    {i}. {title}")

# Step 4: Generate hypotheses
print("\n[Step 4] 首席科学家生成 Nature 级别假设...")
print("  (Claude API 调用中，可能需要几分钟...)")

hyp_result = hypothesis_agent.execute({
    'literature_report': f"搜索关键词: {query}\n找到 {len(papers)} 篇相关文献",
    'papers': papers,
    'research_topic': query,
    'output_dir': 'reports'
})

if not hyp_result['success']:
    print(f"  [FAIL] {hyp_result.get('error')}")
    sys.exit(1)

hypotheses = hyp_result['hypotheses']
hypothesis_ids = hyp_result.get('hypothesis_ids', [])
proposal_path = hyp_result.get('proposal_path')

print(f"  [OK] 生成 {len(hypotheses)} 个假设")
if proposal_path:
    print(f"  [OK] 提案已保存: {proposal_path}")

# Step 5: Display hypotheses for user selection
print("\n" + "=" * 70)
print("[Step 5] 假设摘要 - Human-in-the-Loop 决策点")
print("=" * 70)

for i, hyp in enumerate(hypotheses, 1):
    title = hyp.get('title', 'N/A')
    paradigm = hyp.get('paradigm_framework', 'N/A')
    description = hyp.get('description', 'N/A')
    if len(description) > 120:
        description = description[:120] + "..."

    print(f"\n[ 假设 {i} ]")
    print(f"  标题: {title}")
    print(f"  前沿框架: {paradigm}")
    print(f"  概要: {description}")

print("\n" + "-" * 70)
print("老板，初步假设已生成。")
print("选择最有潜力的假设进入终审阶段。")
print("-" * 70)

# 自动选择假设1
user_choice = 1
print(f"\n[自动化选择: 假设 {user_choice}]")

selected_hyp = hypotheses[user_choice - 1]
selected_hyp_id = hypothesis_ids[user_choice - 1] if user_choice - 1 < len(hypothesis_ids) else None

print(f"\n  已选择假设 {user_choice}:")
title = selected_hyp.get('title', 'N/A')
if len(title) > 60:
    title = title[:60] + "..."
print(f"  {title}")

# Step 6: Validation by Nature Editor
print("\n" + "=" * 70)
print("[Step 6] Nature 高级编辑 - 深度评估")
print("=" * 70)
print("  (Claude API 调用中，可能需要几分钟...)")

validation_result = validation_agent.execute({
    'hypothesis_id': selected_hyp_id,
    'hypothesis_data': {
        'title': selected_hyp.get('title', ''),
        'description': selected_hyp.get('description', ''),
        'rationale': selected_hyp.get('rationale', ''),
        'novelty': selected_hyp.get('novelty', ''),
        'expected_value': selected_hyp.get('expected_value', ''),
        'validation_plan': selected_hyp.get('validation_plan', ''),
        'paradigm_framework': selected_hyp.get('paradigm_framework', ''),
        'grand_challenge': selected_hyp.get('grand_challenge', '')
    },
    'source_papers': papers[:5],
    'enable_literature_check': True,
    'output_dir': 'reports'
})

if not validation_result['success']:
    print(f"  [FAIL] {validation_result.get('error')}")
    sys.exit(1)

validation = validation_result['validation']
scores = validation.get('scores', {})

# Display final report
print("\n" + "=" * 70)
print("最终评审报告")
print("=" * 70)

print("\n[ 评分详情 ]")
print(f"  广度与深度的颠覆性:       {scores.get('transformative_impact', 'N/A')}/10")
print(f"  方法论的原创性:           {scores.get('methodological_originality', 'N/A')}/10")
print(f"  验证的可行性:             {scores.get('poc_feasibility', 'N/A')}/10")

avg = sum(scores.values()) / len(scores) if scores else 0
print(f"  平均分:                   {avg:.1f}/10")

final_decision = validation.get('final_decision', 'unknown')
decision_display = {
    'accepted': '[ACCEPT]',
    'revise': '[REVISE]',
    'rejected': '[REJECT]'
}.get(final_decision.lower(), f'[{final_decision.upper()}]')

print(f"\n[ 最终决议: {decision_display} ]")

verdict = validation.get('verdict', {})
print(f"\n决策理由: {verdict.get('rationale', 'N/A')}")

if final_decision.lower() == 'revise':
    print(f"修改条件: {verdict.get('conditions', 'N/A')}")

# Impact analysis
impact = validation.get('impact_analysis', {})
print(f"\n[ 颠覆性分析 ]")
print(f"  跨学科影响力: {impact.get('breadth', 'N/A')}")
print(f"  颠覆性潜力: {impact.get('depth', 'N/A')}")

# Originality analysis
originality = validation.get('originality_analysis', {})
print(f"\n[ 原创性分析 ]")
print(f"  核心创新: {originality.get('core_innovation', 'N/A')}")

# Feasibility analysis
feasibility = validation.get('feasibility_analysis', {})
print(f"\n[ 可行性分析 ]")
print(f"  数据规模: {feasibility.get('data_scale', 'N/A')}")

recommended_dbs = feasibility.get('recommended_databases', [])
if recommended_dbs:
    print(f"  推荐数据库: {', '.join(recommended_dbs[:3])}")

# Report path
report_path = validation.get('report_path')
if report_path:
    print(f"\n[ 详细报告已保存: {report_path} ]")

# Complete session
print("\n" + "=" * 70)
print("工作流程完成")
print("=" * 70)

orchestrator.complete_session()

print(f"""
总结:
  - 搜索文献: {len(papers)} 篇
  - 生成假设: {len(hypotheses)} 个
  - 选择假设: {user_choice}
  - 最终决议: {final_decision.upper()}
  - 平均分: {avg:.1f}/10
""")