# -*- coding: utf-8 -*-
"""
Complete validation and grant proposal test
Hypothesis 1: ThermoNet
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv(project_root / '.env', encoding='utf-8')

from src.core.orchestrator import Orchestrator
from src.agents.grant_writer_agent import GrantWriterAgent

print("=" * 70)
print("Complete Test: Validation + Grant Proposal")
print("Hypothesis: ThermoNet")
print("=" * 70)

# Initialize
orchestrator = Orchestrator()
grant_writer = GrantWriterAgent()

# Hypothesis 1 data (ThermoNet)
hypothesis_data = {
    'title': 'ThermoNet: 热力学第一原理驱动的生物分子大形变动力学模拟器',
    'description': '不再预测坐标，而是预测自由能面。将热力学不可逆性作为约束项嵌入损失函数，迫使模型不仅预测结构，更要预测能量分布。',
    'rationale': '当前方法将结构预测视为"几何问题"，但这违反了物理事实：蛋白质是能量最小化的热力学系统。',
    'novelty': '从"拟合几何"跨越到"计算物理"，这是 AI + Science 的终极形态。首次将物理守恒定律硬编码到AI架构中。',
    'expected_value': '解释"相分离"这一细胞生物学的前沿机制，揭示无序蛋白如何在病理条件下聚集。',
    'validation_plan': '预测 FUS 或 TDP-43 蛋白在不同盐浓度、温度下的相分离临界浓度。',
    'paradigm_framework': '物理/化学约束深度学习',
    'grand_challenge': '蛋白质折叠的"盲点"：如何预测细胞环境中的动力学行为与无序区域'
}

# Mock papers
papers = [
    {'pmid': '30102808', 'title': 'eDoctor: machine learning and the future of medicine', 'journal': 'Lancet Digital Health', 'publication_date': '2018', 'authors': 'Topol EJ'},
    {'pmid': '32800297', 'title': 'Supervised Machine Learning: A Brief Primer', 'journal': 'JAMIA', 'publication_date': '2019', 'authors': 'He J et al.'},
    {'pmid': '34560276', 'title': 'Machine learning for cardiology', 'journal': 'Nature Reviews Cardiology', 'publication_date': '2020', 'authors': 'Krittanawong C'}
]

print("\n[Step 1] Validation...")
validation_result = orchestrator.validation_agent.execute({
    'hypothesis_id': 25,
    'hypothesis_data': hypothesis_data,
    'source_papers': papers,
    'enable_literature_check': True,
    'output_dir': 'reports'
})

if not validation_result['success']:
    print(f"  [FAIL] {validation_result.get('error')}")
    sys.exit(1)

validation = validation_result.get('validation', {})
scores = validation.get('scores', {})
final_decision = validation.get('final_decision', 'unknown')
avg = sum(scores.values()) / len(scores) if scores else 0

print(f"  [OK] Validation complete")
print(f"    Decision: {final_decision.upper()}")
print(f"    Average: {avg:.1f}/10")

print("\n[Step 2] Grant Writer generating proposal...")
grant_result = grant_writer.execute({
    'hypothesis_data': hypothesis_data,
    'validation_result': validation_result,
    'papers': papers,
    'output_dir': 'reports'
})

if grant_result['success']:
    proposal = grant_result['grant_proposal']
    proposal_path = grant_result.get('proposal_path', '')

    print(f"  [OK] Grant proposal generated")
    print(f"    Length: {len(proposal)} characters")
    print(f"    Saved: {proposal_path}")

    # Show preview
    print("\n[Preview - First 1000 characters]")
    print("-" * 70)
    print(proposal[:1000])
    print("...")
    print("-" * 70)
else:
    print(f"  [FAIL] {grant_result.get('error')}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)

print(f"""
Summary:
  - Hypothesis: ThermoNet
  - Validation: {final_decision.upper()} ({avg:.1f}/10)
  - Grant proposal: {'Generated' if grant_result['success'] else 'Failed'}
  - Length: {len(proposal) if grant_result['success'] else 'N/A'} chars
""")