# -*- coding: utf-8 -*-
"""
Test GenAI Expert Agent
首席生成式AI架构师测试
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv(project_root / '.env', encoding='utf-8')

from src.agents.genai_expert_agent import GenAIExpertAgent

print("=" * 70)
print("GenAI Expert Agent Test")
print("Testing: 首席生成式AI架构师")
print("=" * 70)

# Initialize
genai_expert = GenAIExpertAgent()

# Test data: A hypothesis about causal discovery with small sample size
hypothesis_data = {
    'title': 'CausalSC: 因果发现与深度学习耦合的单细胞因果推断框架',
    'description': '小样本单细胞数据的因果推断，数据量不足（N<500），传统因果推断方法（如PC算法）在小样本下失效。需要生成合成数据或使用预训练语言模型来增强因果发现能力。',
    'rationale': '当前因果推断方法需要大量样本才能准确识别因果关系。单细胞数据获取成本高，样本量通常<1000，无法支撑复杂模型训练。同时，临床文本数据是非结构化的，包含丰富的表型信息但难以提取。',
    'novelty': '首次将扩散模型用于单细胞合成数据生成，结合ESM-2蛋白质语言模型进行zero-shot因果预测',
    'expected_value': '通过合成数据预训练，在小样本真实数据上微调，实现可靠的因果发现。同时使用ClinicalBERT从临床文本中提取复杂表型。',
    'validation_plan': '使用DiffusionModel生成合成单细胞数据，在合成数据上预训练因果模型，在真实数据上微调验证。',
    'paradigm_framework': '因果推断 + 深度学习 + 单细胞组学',
    'grand_challenge': '单细胞数据的因果盲区：小样本因果发现与非结构化文本利用'
}

tech_analysis = {
    'model_architecture': 'Transformer-based Causal Discovery Model',
    'features': 'gene_expression + clinical_embeddings',
    'sample_size': '~500 cells'
}

validation_result = {
    'validation': {
        'scores': {
            'transformative_impact': 8,
            'methodological_originality': 9,
            'poc_feasibility': 6
        },
        'feasibility_analysis': {
            'data_scale': '样本量偏小 (N~500)',
            'computational_needs': '需要大量算力进行扩散模型训练'
        }
    }
}

print("\n[Test Data]")
print(f"  Hypothesis: {hypothesis_data['title'][:60]}...")
print(f"  Paradigm: {hypothesis_data['paradigm_framework']}")
print(f"  Challenge: {hypothesis_data['grand_challenge']}")

print("\n[Generating GenAI Proposal...]")
print("  (This may take a few minutes...)")

# Execute
result = genai_expert.execute({
    'hypothesis_data': hypothesis_data,
    'tech_analysis': tech_analysis,
    'validation_result': validation_result,
    'output_dir': 'reports'
})

if result['success']:
    proposal = result['genai_proposal']
    proposal_path = result.get('proposal_path', '')

    print(f"\n  [SUCCESS] GenAI proposal generated!")
    print(f"    Length: {len(proposal)} characters")
    print(f"    Saved: {proposal_path}")

    # Show preview
    print("\n[Preview - First 1000 characters]")
    print("-" * 70)
    print(proposal[:1000])
    print("...")
    print("-" * 70)

    # Check for key sections
    required_sections = [
        'GenAI赋能机会分析',
        '生成式AI架构设计',
        '预训练/微调策略',
        'RAG架构',
        '合成数据生成',
        '技术路线图'
    ]

    print("\n[Checking Required Sections]")
    for section in required_sections:
        found = section in proposal
        status = "[OK]" if found else "[MISSING]"
        print(f"  {status} {section}")

    # Check for specific technologies
    tech_keywords = [
        'LoRA', 'ESM-2', 'ClinicalBERT', 'Diffusion', 'RAG',
        'Vector Database', 'Synthetic Data', 'Zero-shot'
    ]

    print("\n[Checking GenAI Technologies]")
    for tech in tech_keywords:
        found = tech in proposal
        status = "[OK]" if found else "[ ]"
        print(f"  {status} {tech}")

else:
    print(f"\n  [FAILED] {result.get('error')}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)

print(f"""
Summary:
  - Hypothesis: CausalSC
  - Challenge: {hypothesis_data['grand_challenge']}
  - GenAI proposal: {'Generated' if result['success'] else 'Failed'}
  - Length: {len(proposal) if result['success'] else 'N/A'} chars
""")
