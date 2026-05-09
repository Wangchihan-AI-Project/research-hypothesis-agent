# -*- coding: utf-8 -*-
"""
Complete validation step for Web UI test
Hypothesis 1: CausalSC
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
from memory_manager import MemoryManager

print("=" * 70)
print("Validation Step - Hypothesis 1: CausalSC")
print("=" * 70)

# Initialize
orchestrator = Orchestrator()
memory_manager = MemoryManager()

# Hypothesis 1 data (CausalSC)
hypothesis_data = {
    'title': 'CausalSC (Single-Cell Causal Discovery):脱离标记基因的单细胞因果网络大规模自动发现引擎',
    'description': '构建基于加性噪声模型与变分自编码器(VAE)混合的深度因果框架。利用拓扑约束的因果排序，解耦混淆因子，实现反事实推理。能够回答"如果敲除基因A，细胞B的命运会如何改变？"',
    'rationale': '目前的单细胞分析主要依赖聚类，假设细胞类型是离散的。相关性不等于因果性，高表达基因不一定导致疾病。需要将细胞视为因果动力系统的快照。',
    'novelty': '首个不依赖先验知识，直接从数据中"涌现"出因果调控网络的计算框架。发现非编码RNA与代谢基因之间的双向因果调控环。',
    'expected_value': '发现非编码RNA与代谢基因之间的双向因果调控环，挑战传统中心法则单向流动认知。',
    'validation_plan': '使用Perturb-seq (CRISPR干扰后的单细胞测序数据)作为金标准进行因果验证。',
    'paradigm_framework': '从相关到因果',
    'grand_challenge': '打破"细胞类型"的定义瓶颈：从离散聚类走向连续的因果动力学流形'
}

# Mock papers
source_papers = [
    {'title': 'eDoctor: machine learning and the future of medicine', 'abstract': 'ML transforming medicine...'},
    {'title': 'Supervised Machine Learning: A Brief Primer', 'abstract': 'Overview of supervised learning...'},
    {'title': 'Machine learning for cardiology', 'abstract': 'Applications in cardiovascular...'}
]

print("\n[Nature Editor - Deep Evaluation]")
print("  (Claude API calling...)")

validation_result = orchestrator.validation_agent.execute({
    'hypothesis_id': 24,
    'hypothesis_data': hypothesis_data,
    'source_papers': source_papers,
    'enable_literature_check': True,
    'output_dir': 'reports'
})

if not validation_result['success']:
    print(f"  [FAIL] {validation_result.get('error')}")
    sys.exit(1)

validation = validation_result['validation']
scores = validation.get('scores', {})

print("\n" + "=" * 70)
print("Final Review Report")
print("=" * 70)

print("\n[ Scores ]")
print(f"  Transformative Impact:      {scores.get('transformative_impact', 'N/A')}/10")
print(f"  Methodological Originality: {scores.get('methodological_originality', 'N/A')}/10")
print(f"  PoC Feasibility:            {scores.get('poc_feasibility', 'N/A')}/10")

avg = sum(scores.values()) / len(scores) if scores else 0
print(f"  Average Score:              {avg:.1f}/10")

final_decision = validation.get('final_decision', 'unknown')
decision_display = {
    'accepted': '[ACCEPT]',
    'revise': '[REVISE]',
    'rejected': '[REJECT]'
}.get(final_decision.lower(), f'[{final_decision.upper()}]')

print(f"\n[ Final Decision: {decision_display} ]")

verdict = validation.get('verdict', {})
print(f"\nRationale: {verdict.get('rationale', 'N/A')}")

# Report path
report_path = validation.get('report_path')
if report_path:
    print(f"\n[ Detailed report saved: {report_path} ]")

print("\n" + "=" * 70)
print("Validation Complete")
print("=" * 70)

print(f"""
Summary:
  - Selected Hypothesis: CausalSC (Single-Cell Causal Discovery)
  - Final Decision: {final_decision.upper()}
  - Average Score: {avg:.1f}/10

Web UI is running at http://localhost:8503
You can open in browser for interactive testing!
""")