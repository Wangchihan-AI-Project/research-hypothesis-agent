# -*- coding: utf-8 -*-
"""
验证步骤 - 假设1: Causal Geometry
"""
import sys
import os

sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent/src')

print("=" * 70)
print("验证步骤 - 假设1: Causal Geometry")
print("=" * 70)

from agents.validation_agent import ValidationAgent

validation_agent = ValidationAgent()

# 假设1的数据（Causal Geometry）
hypothesis_data = {
    'title': 'Causal Geometry: 基于非欧几何因果推断的时空细胞通讯图谱',
    'description': '将空间生物学从"基于相关性的可视化"转变为"基于反事实的因果动力学"。构建双层图神经网络：物理层处理真实物理空间坐标，因果层学习有向无环图（DAG），边代表因果强度的向量场。引入反应-扩散方程作为损失函数约束。',
    'rationale': '现有空间分析方法主要基于相关性（配体-受体共表达），假设"距离近=有交流"，忽略了组织复杂的物理屏障和远端作用。无法区分细胞间通讯是"原因"还是"结果"。',
    'novelty': '这是生物学中首次尝试在空间组学尺度上建立严格的因果模型，超越描述性统计。发现"非局部细胞通讯"机制，重塑对肿瘤微环境的认知。',
    'expected_value': '肿瘤免疫治疗将不再基于"细胞浸润率"，而是基于"因果通讯枢纽"的靶向干预，彻底改变联合用药策略。',
    'validation_plan': '使用10x Genomics Visium HD和MERFISH数据进行训练，通过类器官培养的CRISPR敲除实验验证模型预测的"因果边"。',
    'paradigm_framework': '时空多模态组学',
    'grand_challenge': '空间临近关系的因果解耦'
}

source_papers = [
    {'title': 'eDoctor: machine learning and the future of medicine', 'abstract': 'Machine learning is transforming medicine...'},
    {'title': 'Supervised Machine Learning: A Brief Primer', 'abstract': 'Overview of supervised learning methods...'},
    {'title': 'Machine learning for cardiology', 'abstract': 'Applications in cardiovascular disease...'}
]

print("\n[Nature 高级编辑 - 深度评估]")
print("  (Claude API 调用中...)")

validation_result = validation_agent.execute({
    'hypothesis_id': 23,
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

# Report path
report_path = validation.get('report_path')
if report_path:
    print(f"\n[ 详细报告已保存: {report_path} ]")

print("\n" + "=" * 70)
print("验证完成")
print("=" * 70)

print(f"""
总结:
  - 选择假设: Causal Geometry（时空因果推断）
  - 最终决议: {final_decision.upper()}
  - 平均分: {avg:.1f}/10
""")