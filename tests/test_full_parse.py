# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.hypothesis_agent import HypothesisAgent, HypothesisOutput
from src.utils.llm_utils import SafeExtractor

# 模拟LLM返回的JSON
test_json = '''```json
[
  {
    "title": "基于非交换几何的电子病历高维张量流形解耦",
    "core_problem": "现有的EHR预测模型（如RNN、Transformer）将医疗事件视为离散时间序列，强行施加了线性时间顺序，忽略了医疗事件发生的'同时性'与'非线性拓扑结构'，导致在处理高维稀疏数据时存在严重的几何偏差。",
    "core_hypothesis": "患者的临床轨迹本质上是一个非交换的几何流形。利用非交换几何（NCG）理论构建高阶张量代数空间，解耦诊断、用药和手术之间的非线性算子关系，可捕获传统线性模型无法识别的深层病理模式。",
    "technical_route": "数据：MIMIC-IV或eICU-CRD；方法：构建非交换代数结构（C*-algebra）、谱聚类分析流形曲率、拓扑数据分析（TDA）量化持续性同调。",
    "expected_breakthrough": "突破EHR数据'特征独立性'的假设局限，首次建立基于医疗事件拓扑结构的预测范式，显著提升对罕见并发症的预警能力。",
    "clinical_value": "解决ICU中多器官衰竭的级联效应预测难题，实现从'单器官评分'（如SOFA）向'系统性拓扑风险'的跨越。",
    "statistical_novelty": "本研究的统计学核心突破在于将'非交换性'引入高维数据分析。传统的统计学方法（如Pearson相关、GLM）默认变量是可交换的，即$X \\cdot Y = Y \\cdot X$。然而在复杂的医疗系统中，'检查'与'治疗'的顺序不可交换（先检查后治疗 vs 先治疗后检查的结局截然不同）。本研究构建非交换概率空间，使用谱理论分析算子特征值的分布，从而在不需要假设数据分布的情况下（非参数统计），提取出医疗轨迹中蕴含的因果拓扑不变量。",
    "internal_reasoning": "技术降维分析：现有深度学习模型通过Attention机制强行拟合关系，计算成本高且缺乏可解释性。非交换几何直接从代数结构层面定义距离，数学上更优雅，且能处理非欧几里得距离的医疗数据。",
    "crack_mode": "降维打击",
    "paradigm_framework": "非交换几何 + 拓扑数据分析",
    "data_requirements": "包含诊断、用药、手术流程及时间戳的大型ICU电子病历数据库（MIMIC-IV/eICU）",
    "search_queries": ["non-commutative geometry AND electronic health records", "topological data analysis AND clinical trajectory"]
  }
]
```'''

print("="*60)
print("测试完整解析流程")
print("="*60)

# 1. 测试 SafeExtractor
print("\n1. 测试 SafeExtractor 解析...")
try:
    result = SafeExtractor.safe_extract_json(test_json)
    print(f"   解析成功，类型: {type(result)}, 列表长度: {len(result) if isinstance(result, list) else 'N/A'}")
except Exception as e:
    print(f"   解析失败: {e}")
    result = None

if result and isinstance(result, list) and len(result) > 0:
    # 2. 测试字段长度
    hyp = result[0]
    print("\n2. 检查字段长度:")
    min_lengths = {
        'title': 30,
        'core_problem': 200,
        'core_hypothesis': 150,
        'technical_route': 300,
        'expected_breakthrough': 200,
        'clinical_value': 150,
        'internal_reasoning': 500,
        'statistical_novelty': 150,
        'data_requirements': 100,
        'paradigm_framework': 10
    }
    for field, min_len in min_lengths.items():
        current_len = len(hyp.get(field, ''))
        status = "✓" if current_len >= min_len else "✗"
        print(f"   {field}: {current_len}/{min_len} {status}")

    # 3. 测试 Pydantic 验证（直接）
    print("\n3. 测试 Pydantic 验证（直接）...")
    try:
        validated = HypothesisOutput(**hyp)
        print(f"   验证成功！")
    except Exception as e:
        print(f"   验证失败: {e}")

    # 4. 测试 Pydantic 验证（经过 _fill_hypothesis_to_meet_requirements）
    print("\n4. 测试经过 _fill_hypothesis_to_meet_requirements 后的验证...")
    agent = HypothesisAgent()
    try:
        hyp_filled = agent._fill_hypothesis_to_meet_requirements(hyp.copy())
        print("   字段填充完成")

        # 再次检查字段长度
        print("\n   填充后字段长度:")
        for field, min_len in min_lengths.items():
            current_len = len(hyp_filled.get(field, ''))
            status = "✓" if current_len >= min_len else "✗"
            print(f"      {field}: {current_len}/{min_len} {status}")

        validated = HypothesisOutput(**hyp_filled)
        print(f"   验证成功！")
    except Exception as e:
        print(f"   验证失败: {type(e).__name__}: {e}")
