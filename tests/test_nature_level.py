# -*- coding: utf-8 -*-
"""
测试Nature/Science/Cell级别系统
"""
import os
import sys

# 设置环境变量
os.environ['ANTHROPIC_API_KEY'] = 'sk-y3WE6cIOgqbsg7tXs2LNSKXZkeh9E1zfJvdC763KraN3lTDw'
os.environ['ANTHROPIC_BASE_URL'] = 'https://cloud.hongqiye.com'
os.environ['CLAUDE_MODEL'] = 'claude-opus-4-6'
os.environ['PUBMED_EMAIL'] = 'wanghan3698@gmail.com'
os.environ['PUBMED_API_KEY'] = '2ee2706d111ff8ff5ccce94a25d883fb5709'

# 获取脚本所在目录并添加src到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(script_dir, 'src')
sys.path.insert(0, src_path)

from agents.hypothesis_agent import ChiefScientistAgent
from agents.validation_agent import ValidationAgent


def test_nature_level_system():
    """测试Nature级别系统"""
    print()
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*       Nature/Science/Cell 级别科研假设生成系统测试      *")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print()
    print("【Nature级别标准】")
    print("  拒绝增量，追求颠覆")
    print("  四大前沿框架:")
    print("    1. 生物学基础大模型")
    print("    2. 物理/化学约束深度学习")
    print("    3. 从相关到因果")
    print("    4. 时空多模态组学")
    print()

    # 测试文献报告 - 描述一个当前研究的局限性
    test_report = """
# 基因表达预测研究现状与局限性

## 当前研究的根本性缺陷

通过对近期发表在Nature、Cell、Science子刊上的50篇基因表达预测论文的分析，发现以下**根本性局限**：

### 1. 组织特异性局限
当前所有基因表达预测模型都是**组织特异性**的：
- 预测肝脏基因表达的模型无法用于预测心脏
- 预测原代细胞的模型无法用于预测iPSC衍生的细胞
- 这意味着需要为每种组织/细胞类型单独训练模型

### 2. 监督学习的依赖
当前方法严重依赖大量标记数据：
- 使用GTEx等数据库进行监督训练
- 无法处理从未见过的细胞类型或疾病状态
- 缺乏零样本泛化能力

### 3. 忽略生物学约束
现有方法将基因表达预测视为纯统计问题：
- 没有嵌入中心法则（DNA->RNA->蛋白）的因果约束
- 忽略了热力学和分子动力学的基本原理
- 将生物学系统视为黑盒，仅追求预测精度

### 4. 缺乏时间维度
现有研究使用静态快照数据：
- GTEx是静态的，无法捕捉细胞状态演化
- 无法预测发育过程中的基因表达变化
- 缺乏对细胞命运转换的建模能力

### 5. 多组学割裂
基因组、表观基因组、转录组、蛋白质组分别建模：
- 没有统一的表示空间
- 忽略了多组学之间的因果依赖关系
- 无法利用跨模态的互补信息

## 代表性论文的局限性

- Nature Biotechnology 2023: 仅预测肝脏基因表达，无法泛化
- Cell 2024: 使用深度学习但仍是监督学习范式
- Science 2024: 多组学研究但各模态独立分析

这些方法虽然在自己的领域内表现良好，但**未能实现范式转移**。
"""

    print("=" * 70)
    print("【步骤 1/2】首席科学家 - 生成Nature级别假设")
    print("=" * 70)
    print()

    chief = ChiefScientistAgent()
    result = chief.execute({
        'literature_report': test_report,
        'papers': [],
        'research_topic': '通用基因表达预测模型',
        'output_dir': 'reports'
    })

    if result['success']:
        print(f"[OK] 生成了 {len(result['hypotheses'])} 个Nature级别假设")
        print()
        print("假设摘要:")
        for i, hyp in enumerate(result['hypotheses'], 1):
            framework = hyp.get('paradigm_framework', '待明确')
            challenge = hyp.get('grand_challenge', '待明确')
            print(f"  假设 {i}: {hyp['title']}")
            print(f"    前沿框架: {framework}")
            print(f"    大挑战: {challenge}")
        print()
        print(f"提案文档: {result['proposal_path']}")

        # 测试评审
        print()
        print("=" * 70)
        print("【步骤 2/2】Nature高级编辑 - 评审假设")
        print("=" * 70)
        print()

        validator = ValidationAgent()
        first_hypothesis = result['hypotheses'][0]

        # 添加元数据
        first_hypothesis['paradigm_framework'] = first_hypothesis.get('technical_analysis', {}).get('paradigm_framework', '生物学基础大模型')
        first_hypothesis['grand_challenge'] = first_hypothesis.get('technical_analysis', {}).get('grand_challenge', '通用生物学法则')

        validation_result = validator.execute({
            'hypothesis_id': None,
            'hypothesis_data': first_hypothesis,
            'source_papers': [],
            'enable_literature_check': False,
            'output_dir': 'reports'
        })

        if validation_result['success']:
            validation = validation_result['validation']
            print("[OK] Nature评审完成")
            print()
            print("Nature级别评分:")
            scores = validation.get('scores', {})
            print(f"  广度与深度的颠覆性: {scores.get('transformative_impact', 'N/A')}/10")
            print(f"  方法论的原创性: {scores.get('methodological_originality', 'N/A')}/10")
            print(f"  验证的可行性: {scores.get('poc_feasibility', 'N/A')}/10")
            print()
            print(f"决议: {validation['final_decision']}")
            print(f"决议书: {validation.get('report_path', 'N/A')}")

    else:
        print(f"[ERROR] 假设生成失败: {result.get('error')}")

    print()
    print("=" * 70)
    print("测试完成!")
    print("=" * 70)


if __name__ == '__main__':
    test_nature_level_system()
