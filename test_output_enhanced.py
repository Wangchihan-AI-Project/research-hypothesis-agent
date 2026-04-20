# -*- coding: utf-8 -*-
"""
V7.5 输出增强功能验证���试

验证新增的输出内容：
1. 落地指南 (implementation_roadmap)
2. 创新点分析 (innovation_analysis)
3. 前沿溯源分析 (frontier_analysis)
"""

import sys
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.output_enhancer import (
    OutputEnhancer,
    create_output_enhancer,
)


def test_output_enhancer():
    """测试输出增强器"""

    print("\n" + "="*80)
    print("V7.5 输出增强功能验证测试")
    print("="*80 + "\n")

    # 模拟假设数据
    mock_hypothesis = {
        'title': '基于因果推断与严格数据流管的预测模型构建方案 v1.1',
        'details': '本方案旨在解决原 v1.0 版本中存在的严重数据泄露风险与内生性偏倚问题。通过引入有向无环图（DAG）进行因果结构定义，并实施严格的数据流管��确保所有统计变换仅基于训练集计算。',
        'methodology': {
            'technical_safeguards': [
                '建立严格的数据流管：在Pipeline中明确划分 Fit 阶段与 Transform 阶段',
                '实施双重验证机制：除传统的 K-fold 交叉验证外，引入敏感性分析'
            ],
            'validation_protocol': '采用 Nested Cross-Validation（嵌套交叉验证）策略',
            'bias_control': '构建基于领域知识的因果图（DAG）'
        },
        'patch_log': [
            {
                'attack_type': '数据穿越',
                'patch_applied': '实施了严格的数据隔离策略，强制所有基于数据分布的统计量计算仅限于训练集'
            },
            {
                'attack_type': '内生性偏倚',
                'patch_applied': '引入因果推断框架，通过构建 DAG 显式建模变量间的因果关系'
            }
        ]
    }

    # 模拟适应度结果
    mock_fitness = {
        'hybrid_fitness': 8.94,
        'vector_novelty_score': 9.9,
        'red_team_rigor_score': 7.5,
        'similarity': 0.51,
        'similarity_interpretation': '创新甜点区（恰到好处的创新度）',
        'physical_validation': {
            'passed': True
        }
    }

    # 模拟验证ID
    mock_verified_ids = {
        'pmids': ['24762253', '31826347'],
        'arxiv_ids': [],
        'dois': []
    }

    # 模拟 Promise Score 组件
    mock_promise_components = {
        'innovation': {'score': 8.94},
        'feasibility': {'score': 7.5},
        'frontier_alignment': {
            'score': 8.0,
            'details': '年份: 2025, 引用速度: normal'
        }
    }

    # 创建输出增强器
    enhancer = create_output_enhancer()

    # 测试1: 落地指南
    print("[TEST 1] 生成落地指南...")
    roadmap = enhancer.generate_implementation_roadmap(
        mock_hypothesis,
        '心血管疾病',
        mock_fitness
    )

    print(f"  - 阶段数量: {len(roadmap.phases)}")
    print(f"  - 资源类别: {list(roadmap.resources.keys())}")
    print(f"  - 风险数量: {len(roadmap.risks)}")
    print(f"  - 预算估算: {roadmap.budget.get('estimated_total', 'N/A')}")
    print("  [PASS] 落地指南生成成功\n")

    # 测试2: 创新点分��
    print("[TEST 2] 生成创新点分析...")
    innovation = enhancer.generate_innovation_analysis(
        mock_hypothesis,
        mock_fitness,
        mock_hypothesis.get('patch_log', [])
    )

    print(f"  - 核心创新点: {len(innovation.core_innovations)}")
    print(f"  - 新颖度等级: {innovation.novelty_level}")
    print(f"  - 突破潜力: {innovation.breakthrough_potential.get('level', 'N/A')}")
    print(f"  - 向量评分: {innovation.vector_analysis.get('score', 0):.2f}")
    print("  [PASS] 创新点分析生成成功\n")

    # 测试3: 前沿溯源分析
    print("[TEST 3] 生成前沿溯源分析...")
    frontier = enhancer.generate_frontier_analysis(
        mock_hypothesis,
        mock_verified_ids,
        '心血管疾病',
        mock_promise_components
    )

    print(f"  - 前沿定位: {frontier.frontier_position}")
    print(f"  - 关键出版物: {len(frontier.key_publications)}")
    print(f"  - 研究趋势: {len(frontier.research_trends)}")
    print(f"  - 研究空白: {len(frontier.gap_analysis)}")
    print("  [PASS] 前沿溯源分析生成成功\n")

    # 汇总输出
    print("="*80)
    print("输出结构验证")
    print("="*80 + "\n")

    full_output = {
        'implementation_roadmap': roadmap.to_dict(),
        'innovation_analysis': innovation.to_dict(),
        'frontier_analysis': frontier.to_dict(),
    }

    print("完整输出结构:")
    print(json.dumps(full_output, indent=2, ensure_ascii=False))

    # 保存测试结果
    test_output_path = project_root / "test_output_enhanced.json"
    with open(test_output_path, 'w', encoding='utf-8') as f:
        json.dump(full_output, f, ensure_ascii=False, indent=2)

    print(f"\n测试结果已保存到: {test_output_path}")

    # 验证完整性
    print("\n" + "="*80)
    print("完整性检查")
    print("="*80 + "\n")

    checks = [
        ('落地指南 - 阶段', len(roadmap.phases) > 0),
        ('落地指南 - 资源', len(roadmap.resources) > 0),
        ('落地指南 - 风险', len(roadmap.risks) > 0),
        ('落地指南 - 预算', roadmap.budget is not None),
        ('创新点 - 核心创新', len(innovation.core_innovations) > 0),
        ('创新点 - 新颖度', innovation.novelty_level != 'unknown'),
        ('创新点 - 突破潜力', innovation.breakthrough_potential.get('level') is not None),
        ('前沿分析 - 定位', bool(frontier.frontier_position)),
        ('前沿分析 - 出版物', len(frontier.key_publications) > 0),
        ('前沿分析 - 趋势', len(frontier.research_trends) > 0),
    ]

    all_passed = True
    for check_name, check_result in checks:
        status = "[PASS]" if check_result else "[FAIL]"
        print(f"  {status} {check_name}")
        if not check_result:
            all_passed = False

    print("\n" + "="*80)
    if all_passed:
        print("[SUCCESS] 所有检查通过！输出增强功能正常工作")
    else:
        print("[WARNING] 部分检查未通过，请检查输出")
    print("="*80 + "\n")

    return all_passed


if __name__ == "__main__":
    try:
        success = test_output_enhancer()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
