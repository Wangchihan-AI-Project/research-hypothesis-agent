# -*- coding: utf-8 -*-
"""
V7.5 完整输出演示

基于真实的成功任务数据，展示补齐后的完整输出结构
"""

import json
from pathlib import Path

# 读取之前成功的任务数据
project_root = Path(__file__).parent
input_file = project_root / "multifield_final.json"

with open(input_file, 'r', encoding='utf-8') as f:
    multifield_data = json.load(f)

# 使用心血管领域的数据
cardio_data = multifield_data[0]['data']
result = cardio_data['result']
payload = result['payload']

# 导入输出增强器
import sys
sys.path.insert(0, str(project_root))

from src.core.output_enhancer import create_output_enhancer

# 创建增强输出
enhancer = create_output_enhancer()

hypothesis = payload['hypothesis']
fitness = payload['fitness']
verified_ids = payload['verified_ids']
domain = payload['domain']
patch_log = hypothesis.get('patch_log', [])

# 生成增强输出
print("\n" + "="*80)
print("V7.5 完整输出演示")
print("="*80 + "\n")

print("原始假设标题:")
print(f"  {hypothesis['title']}\n")

# 1. 落地指南
print("-"*60)
print("1. 落地指南 (implementation_roadmap)")
print("-"*60)

roadmap = enhancer.generate_implementation_roadmap(
    hypothesis, domain, fitness
)

print(f"\n阶段规划 (共{len(roadmap.phases)}个阶段):")
for i, phase in enumerate(roadmap.phases, 1):
    print(f"  {i}. {phase['phase']}")
    print(f"     时长: {phase['duration']}")
    print(f"     里程碑: {', '.join(phase['milestones'][:2])}...")

print(f"\n资源需求:")
for resource_type, resources in roadmap.resources.items():
    print(f"  {resource_type}: {list(resources.keys())[:3]}...")

print(f"\n风险评估 (共{len(roadmap.risks)}项):")
for i, risk in enumerate(roadmap.risks[:3], 1):
    print(f"  {i}. [{risk['category']}] {risk['description'][:50]}...")

print(f"\n预算估算:")
print(f"  {roadmap.budget['estimated_total']}")
print(f"  分解: 人力 {roadmap.budget['breakdown']['人力成本']} | "
      f"设备 {roadmap.budget['breakdown']['设备使用']}")

# 2. 创新点分析
print("\n" + "-"*60)
print("2. 创新点分析 (innovation_analysis)")
print("-"*60)

innovation = enhancer.generate_innovation_analysis(
    hypothesis, fitness, patch_log
)

print(f"\n新颖度等级: {innovation.novelty_level}")
print(f"突破潜力: {innovation.breakthrough_potential['level']}")
print(f"  描述: {innovation.breakthrough_potential['description']}")

print(f"\n核心创新点 (共{len(innovation.core_innovations)}项):")
for i, item in enumerate(innovation.core_innovations, 1):
    print(f"  {i}. [{item['type']}]")
    print(f"     {item['description'][:60]}...")

print(f"\n差异化分析:")
for diff in innovation.differentiation[:3]:
    print(f"  - {diff[:70]}...")

print(f"\n方法论创新:")
method = innovation.methodology_analysis
print(f"  补丁数量: {method['patch_count']}")
print(f"  技术保障: {'是' if method['has_technical_safeguards'] else '否'}")
print(f"  验证协议: {'是' if method['has_validation_protocol'] else '否'}")
print(f"  偏倚控制: {'是' if method['has_bias_control'] else '否'}")

# 3. 前沿溯源分析
print("\n" + "-"*60)
print("3. 前沿溯源分析 (frontier_analysis)")
print("-"*60)

# 获取 Promise Score 组件
promise_components = result.get('promise_score', {}).get('components', {})

frontier = enhancer.generate_frontier_analysis(
    hypothesis, verified_ids, domain, promise_components
)

print(f"\n前沿定位:")
print(f"  {frontier.frontier_position}")

print(f"\n关键出版物 (共{len(frontier.key_publications)}项):")
for i, pub in enumerate(frontier.key_publications[:3], 1):
    print(f"  {i}. [{pub['type']}] {pub['content'][:60]}...")
    if pub.get('pmids'):
        print(f"     PMID: {', '.join(pub['pmids'])}")

print(f"\n研究趋势:")
for i, trend in enumerate(frontier.research_trends[:5], 1):
    print(f"  {i}. {trend}")

print(f"\n研究空白:")
for i, gap in enumerate(frontier.gap_analysis, 1):
    print(f"  {i}. {gap}")

print(f"\n前沿时间线:")
for item in frontier.timeline:
    print(f"  {item['period']}: {item['stage']}")
    print(f"    {item['description']}")

# 完整输出汇总
print("\n" + "="*80)
print("完整输出结构汇总")
print("="*80 + "\n")

full_output = {
    'hypothesis': {
        'title': hypothesis['title'],
        'details': hypothesis['details'][:100] + '...',
        'methodology': {
            'technical_safeguards': f"{len(hypothesis['methodology']['technical_safeguards'])}项",
            'validation_protocol': hypothesis['methodology']['validation_protocol'][:50] + '...',
            'bias_control': hypothesis['methodology']['bias_control'][:50] + '...',
        },
        'patch_log': f"{len(hypothesis['patch_log'])}个补丁"
    },
    'fitness': {
        'hybrid_fitness': f"{fitness['hybrid_fitness']:.2f}/10",
        'vector_novelty_score': f"{fitness['vector_novelty_score']:.2f}/10",
        'red_team_rigor_score': f"{fitness['red_team_rigor_score']:.2f}/10"
    },
    'implementation_roadmap': {
        'phases': f"{len(roadmap.phases)}个阶段",
        'resources': list(roadmap.resources.keys()),
        'risks': f"{len(roadmap.risks)}项风险",
        'budget': roadmap.budget['estimated_total']
    },
    'innovation_analysis': {
        'novelty_level': innovation.novelty_level,
        'core_innovations': f"{len(innovation.core_innovations)}项",
        'breakthrough_potential': innovation.breakthrough_potential['level']
    },
    'frontier_analysis': {
        'frontier_position': frontier.frontier_position,
        'key_publications': f"{len(frontier.key_publications)}项",
        'research_trends': f"{len(frontier.research_trends)}条趋势",
        'gap_analysis': f"{len(frontier.gap_analysis)}个空白"
    },
    'promise_score': {
        'total_score': f"{result['promise_score']['total_score']}/10",
        'grade': result['promise_score']['grade'],
        'components': list(result['promise_score']['components'].keys())
    },
    'phoenix_protocol': {
        'final_state': result['phoenix_protocol']['final_state'],
        'total_iterations': result['phoenix_protocol']['total_iterations'],
        'patch_attempts': result['phoenix_protocol']['patch_attempts']
    }
}

print(json.dumps(full_output, indent=2, ensure_ascii=False))

# 保存完整增强输出
enhanced_full_path = project_root / "enhanced_full_output_demo.json"
enhanced_full = {
    'original_payload': payload,
    'implementation_roadmap': roadmap.to_dict(),
    'innovation_analysis': innovation.to_dict(),
    'frontier_analysis': frontier.to_dict(),
}

with open(enhanced_full_path, 'w', encoding='utf-8') as f:
    json.dump(enhanced_full, f, ensure_ascii=False, indent=2)

print(f"\n\n完整增强输出已保存到: {enhanced_full_path}")

print("\n" + "="*80)
print("补齐完成！")
print("="*80 + "\n")
