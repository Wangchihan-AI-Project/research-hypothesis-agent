# -*- coding: utf-8 -*-
"""
Test Thesis Writer Agent
博士论文开题指导专家智能体测试
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv(project_root / '.env', encoding='utf-8')

from src.agents.thesis_writer_agent import ThesisWriterAgent

print("=" * 70)
print("Thesis Writer Agent Test")
print("Testing: 博士论文开题指导专家")
print("=" * 70)

# Initialize
thesis_writer = ThesisWriterAgent()

# Test data: Simulating a validated hypothesis about Causal Discovery
hypothesis_data = {
    'title': 'CausalSC: 因果发现与深度学习耦合的单细胞因果推断���架',
    'description': '传统单细胞分析主要基于相关性分析，无法区分因果关系与混杂因素。本项目提出CausalSC框架，将因果推断（双样本工具变量、反事实学习）与深度学习（变分自编码器、图神经网络）耦合，实现对细胞命运决定过程的因果机制解析。',
    'rationale': '单细胞测序技术革命性地揭示了细胞的异质性，但现有分析方法（如Seurat, Scanpy）主要基于相关性分析，无法回答"什么因果什么"的问题。例如，发现基因A与基因B表达相关，但无法确定是A调控B还是B调控A，或者两者都受上游因子C的调控（混杂）。这导致对细胞分化、药物反应等动态过程的理解停留在表面。',
    'novelty': '首次将因果推断的严格数学框架（Pearl因果三层级：关联、干预、反事实）引入单细胞分析。与现有深度学习方法（如scVI）相比，CausalSC不仅预测细胞状态，更估计干预效果（如敲除基因X对细胞轨迹的影响），支持"假如...会怎样"的反事实推理。',
    'expected_value': '揭示细胞命运决定过程中的关键因果调控关系，为干细胞重编程、癌症耐药机制研究提供新的分析工具。可预测基因干预的下游效应，指导实验设计，减少wet-lab试错成本。',
    'validation_plan': '使用已知因果关系的基准数据集（如 yeast gene knockout 数据）验证因果发现准确性；在真实scRNA-seq数据上预测基因敲除效应，与CRISPR筛选实验结果对比。',
    'paradigm_framework': '因果推断 + 深度学习 + 单细胞组学',
    'grand_challenge': '单细胞数据的因果盲区：如何从观测数据中推断基因调控的因果关系？'
}

# Simulated validation result
validation_result = {
    'validation': {
        'scores': {
            'transformative_impact': 8.5,
            'methodological_originality': 9.0,
            'poc_feasibility': 7.5
        },
        'impact_analysis': {
            'breadth': '该研究将因果推断引入单细胞分析，具有跨学科影响力。方法学上可推广到空间组学、多组学整合等领域；生物学上可直接应用于干细胞、癌症、免疫等研究。'
        },
        'originality_analysis': {
            'core_innovation': '首次将Pearl因果框架与深度变分推断结合，提出端到端的单细胞因果发现算法。',
            'comparison': '与现有方法（如GRNBoost, SCENIC）相比，CausalSC估计的是因果效应而非相关系数，支持反事实推理；与纯因果方法相比，能处理高维单细胞数据。'
        },
        'feasibility_analysis': {
            'strengths': '因果推断理论成熟；深度学习框架（PyTorch）完善；公开单细胞数据丰富。',
            'challenges': '因果可识别性需要满足假设；高维数据的因果发现计算复杂度高。'
        }
    }
}

# Simulated papers (real literature)
papers = [
    {'pmid': '30102808', 'title': 'High-performance medicine: the convergence of human and artificial intelligence', 'journal': 'Nat Med', 'publication_date': '2019', 'authors': 'Topol EJ'},
    {'pmid': '32800297', 'title': 'The practical implementation of artificial intelligence in medicine', 'journal': 'Nat Med', 'publication_date': '2019', 'authors': 'He J et al.'},
    {'pmid': '34560276', 'title': 'Machine learning for cardiology', 'journal': 'Nat Rev Cardiol', 'publication_date': '2021', 'authors': 'Krittanawong C'},
    {'pmid': '34265844', 'title': 'Highly accurate protein structure prediction with AlphaFold', 'journal': 'Nature', 'publication_date': '2021', 'authors': 'Jumper J et al.'},
    {'pmid': '33184163', 'title': 'Deep generative model for molecular graphs', 'journal': 'Science', 'publication_date': '2020', 'authors': 'Yang X et al.'},
    {'pmid': '32703866', 'title': 'Single-cell RNA sequencing: technical advances and biomedical applications', 'journal': 'Nat Rev Genet', 'publication_date': '2020', 'authors': 'Luecken MD and Theis MN'},
    {'pmid': '33452126', 'title': 'Current best practices in single-cell RNA-seq analysis', 'journal': 'Nat Rev Genet', 'publication_date': '2021', 'authors': 'Luecken MD and Theis MN'},
    {'pmid': '32889023', 'title': 'Causal inference for biomedical research', 'journal': 'Nat Med', 'publication_date': '2020', 'authors': 'Rosenbaum PR'}
]

# Simulated datasets (would come from data_hound agent)
datasets = [
    {
        'name': 'Tabula Sapiens',
        'accession': 'GSE238078',
        'samples': '~500K cells',
        'description': '几乎涵盖所有人体细胞类型的单细胞参考图谱'
    },
    {
        'name': 'Human Cell Atlas',
        'accession': 'HCA Portal',
        'samples': '>10M cells',
        'description': '跨组织单细胞参考图谱'
    },
    {
        'name': 'Perturb-seq',
        'accession': 'GSE132610',
        'samples': '~100K cells',
        'description': 'CRISPR干扰后的单细胞测序数据，适合验证因果发现'
    },
    {
        'name': 'TCGA (The Cancer Genome Atlas)',
        'accession': 'GDC Portal',
        'samples': '~11K patients',
        'description': '癌症基因组多组学数据'
    }
]

print("\n[Input Data]")
print(f"  Hypothesis: {hypothesis_data['title'][:50]}...")
print(f"  Paradigm: {hypothesis_data['paradigm_framework']}")
print(f"  Papers: {len(papers)}")
print(f"  Datasets: {len(datasets)}")

print("\n[Generating Thesis Proposal...]")
print("  (This may take a few minutes...)")

# Execute
result = thesis_writer.execute({
    'hypothesis_data': hypothesis_data,
    'validation_result': validation_result,
    'papers': papers,
    'datasets': datasets,
    'output_dir': 'reports'
})

if result['success']:
    proposal = result['thesis_proposal']
    proposal_path = result.get('proposal_path', '')

    print(f"\n  [SUCCESS] Thesis proposal generated!")
    print(f"    Length: {len(proposal)} characters")
    print(f"    Saved to: {proposal_path}")

    # Show preview
    print("\n[Preview - First 1200 characters]")
    print("-" * 70)
    print(proposal[:1200])
    print("...")
    print("-" * 70)

    # Check for required sections
    required_sections = [
        '课题名称', '立项依据', '研究目标', '研究内容',
        '技术路线', '创新点', '可行性', '研究计划'
    ]

    print("\n[Checking Required Sections]")
    for section in required_sections:
        found = section in proposal
        status = "[OK]" if found else "[MISSING]"
        print(f"  {status} {section}")

    # Check for Mermaid diagram
    if 'mermaid' in proposal.lower():
        print("  [OK] Mermaid flowchart included")
    else:
        print("  [WARNING] Mermaid flowchart not found")

else:
    print(f"\n  [FAILED] {result.get('error')}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)

print(f"""
Summary:
  - Hypothesis: CausalSC
  - Paradigm: {hypothesis_data['paradigm_framework']}
  - Papers used: {len(papers)}
  - Datasets used: {len(datasets)}
  - Thesis proposal: {'Generated' if result['success'] else 'Failed'}
  - Length: {len(proposal) if result['success'] else 'N/A'} chars
""")
