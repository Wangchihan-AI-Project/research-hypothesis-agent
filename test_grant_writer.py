# -*- coding: utf-8 -*-
"""
Test Grant Writer Agent
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv(project_root / '.env', encoding='utf-8')

from src.agents.grant_writer_agent import GrantWriterAgent

print("=" * 70)
print("Chief Grant Writer Agent Test")
print("=" * 70)

# Initialize agent
agent = GrantWriterAgent()

# Mock hypothesis data (CausalSC)
hypothesis_data = {
    'title': 'CausalSC (Single-Cell Causal Discovery):脱离标记基因的单细胞因果网络大规模自动发现引擎',
    'description': '构建基于加性噪声模型与变分自编码器(VAE)混合的深度因果框架。利用拓扑约束的因果排序，��耦混淆因子，实现反事实推理。',
    'rationale': '目前的单细胞分析主要依赖聚类，假设细胞类型是离散的。相关性不等于因果性，高表达基因不一定导致疾病。',
    'novelty': '首个不依赖先验知识，直接从数据中"涌现"出因果调控网络的计算框架。发现非编码RNA与代谢基因之间的双向因果调控环。',
    'expected_value': '发现非编码RNA与代谢基因之间的双向因果调控环，挑战传统中心法则单向流动认知。',
    'validation_plan': '使用Perturb-seq (CRISPR干扰后的单细胞测序数据)作为金标准进行因果验证。',
    'paradigm_framework': '从相关到因果',
    'grand_challenge': '打破"细胞类型"的定义瓶颈：从离散聚类走向连续的因果动力学流形'
}

# Mock validation result
validation_result = {
    'validation': {
        'final_decision': 'accepted',
        'scores': {
            'transformative_impact': 9,
            'methodological_originality': 8,
            'poc_feasibility': 8
        },
        'impact_analysis': {
            'breadth': '跨越计算生物学、因果推断和系统生物学三个领域',
            'depth': '极深。从分类学向动力学的范式转移'
        },
        'originality_analysis': {
            'core_innovation': '将加性噪声模型（ANM）与变分自编码器（VAE）在拓扑约束下结合',
            'comparison': '与SCENIC或GRNBoost2（基于相关性）有本质区别，回答因果而非相关'
        },
        'feasibility_analysis': {
            'data_scale': '极高，HCA等项目的数据量（10^7+细胞）',
            'recommended_databases': ['Human Cell Atlas', 'Perturb-seq', 'GTEx']
        },
        'verdict': {
            'rationale': '该工作极具Nature风范，试图通过因果视角打破细胞类型离散分类瓶颈'
        },
        'report_path': 'reports/test_validation.md'
    }
}

# Mock papers
papers = [
    {'pmid': '30102808', 'title': 'eDoctor: machine learning and the future of medicine', 'journal': 'Lancet Digital Health', 'publication_date': '2018-01-01', 'authors': 'Topol EJ'},
    {'pmid': '32800297', 'title': 'Supervised Machine Learning: A Brief Primer', 'journal': 'JAMIA', 'publication_date': '2019-01-01', 'authors': 'He J et al.'},
    {'pmid': '34560276', 'title': 'Machine learning for cardiology', 'journal': 'Nature Reviews Cardiology', 'publication_date': '2020-01-01', 'authors': 'Krittanawong C et al.'}
]

print("\n[Chief Grant Writer - Writing Grant Proposal]")
print("  (This may take a few minutes...)")

result = agent.execute({
    'hypothesis_data': hypothesis_data,
    'validation_result': validation_result,
    'papers': papers,
    'output_dir': 'reports'
})

if result['success']:
    proposal = result['grant_proposal']
    proposal_path = result.get('proposal_path', '')

    print(f"\n[OK] Grant proposal generated")
    print(f"    Length: {len(proposal)} characters")
    print(f"    Saved: {proposal_path}")

    # Show preview
    print("\n[Preview - First 1000 characters]")
    print("-" * 70)
    print(proposal[:1000])
    print("...")
    print("-" * 70)
else:
    print(f"\n[FAIL] {result.get('error')}")

print("\n" + "=" * 70)
print("Test Complete")
print("=" * 70)
