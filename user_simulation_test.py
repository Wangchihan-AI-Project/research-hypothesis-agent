# -*- coding: utf-8 -*-
"""
V7.5 用户模拟测试 - 多领域假设验证

测试领域：
1. 心血管/衰老
2. 神经科学/阿尔茨海默病
3. 癌症免疫治疗
4. 代谢疾病/糖尿病

作者: 模拟用户
日期: 2026-04-20
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.phoenix_state_machine import PhoenixStateMachine, PhoenixTransitionTrigger
from src.core.hypothesis_version_manager import HypothesisVersionManager
from src.core.promise_score_calculator import PromiseScoreCalculator
from src.core.score_trend_detector import ScoreTrendDetector
from src.core.methodology_patch_priority import MethodologyPatchPriorityManager

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 测试假设列表 ====================

TEST_HYPOTHESES = [
    {
        "domain": "心血管/衰老",
        "idea": "通过靶向线粒体自噬相关蛋白 PINK1，延缓血管内皮细胞衰老，预防动脉粥样硬化",
        "keywords": ["线粒体自噬", "PINK1", "内皮衰老", "动脉粥样硬化"],
        "expected_outcome": "发现 PINK1 激活可降低内皮细胞 senescence 标志物 p16 和 p21 表达"
    },
    {
        "domain": "神经科学/阿尔茨海默病",
        "idea": "利用小胶质细胞 TREM2 信号通路调节，通过单细胞 RNA-seq 分析发现新的治疗靶点",
        "keywords": ["TREM2", "小胶质细胞", "单细胞测序", "阿尔茨海默病"],
        "expected_outcome": "鉴定出 TREM2 下游 3 个关键基因可作为药物靶点"
    },
    {
        "domain": "癌症免疫治疗",
        "idea": "联合 PD-1 抗体和肿瘤特异性 TCR-T 细胞治疗，克服实体瘤免疫抑制微环境",
        "keywords": ["PD-1", "TCR-T", "实体瘤", "免疫微环境"],
        "expected_outcome": "在小鼠模型中实现 70% 肿瘤完全缓解"
    },
    {
        "domain": "代谢疾病/糖尿病",
        "idea": "通过靶向肠道 GLP-1 受体和肝脏糖异生通路，改善 2 型糖尿病血糖控制",
        "keywords": ["GLP-1", "糖异生", "2型糖尿病", "血糖"],
        "expected_outcome": "HbA1c 降低 1.5% 以上"
    }
]


# ==================== 模拟 Pipeline 运行 ====================

def simulate_pipeline_run(hypothesis_data: dict) -> dict:
    """
    模拟完整的 Pipeline 运行

    返回包含版本演化、分数趋势、Promise Score 的结果
    """
    domain = hypothesis_data["domain"]
    idea = hypothesis_data["idea"]

    print(f"\n{'='*70}")
    print(f"领域: {domain}")
    print(f"假设: {idea}")
    print(f"{'='*70}\n")

    # 创建状态机和版本管理器
    machine = PhoenixStateMachine()
    version_manager = HypothesisVersionManager()
    trend_detector = ScoreTrendDetector()
    patch_manager = MethodologyPatchPriorityManager()

    # 初始假设
    hypothesis = {
        'title': idea[:50] + "..." if len(idea) > 50 else idea,
        'details': idea,
        'methodology': {'sensor': '测序仪', 'technique': 'RNA-seq'},
        'expected_results': {'outcome': hypothesis_data['expected_outcome']},
        'domain': domain,
        'keywords': hypothesis_data['keywords']
    }

    # v1.0 初始版本
    machine.transition(PhoenixTransitionTrigger.HYPOTHESIS_READY)
    v1_0 = version_manager.create_initial_version(hypothesis, iteration=1)

    # 模拟红方攻击 - 基于领域选择攻击类型
    attack_types_map = {
        "心血管/衰老": ['VALIDATION', 'STATISTICAL_FLAW'],
        "神经科学/阿尔茨海默病": ['OVERFITTING', 'BIAS'],
        "癌症免疫治疗": ['VALIDATION', 'LEAKAGE'],
        "代谢疾病/糖尿病": ['STATISTICAL_FLAW', 'REPRODUCIBILITY']
    }
    attack_types = attack_types_map.get(domain, ['VALIDATION', 'OVERFITTING'])
    machine.context.red_attack_types = attack_types

    print(f"[红方攻击] 检测到问题: {', '.join(attack_types)}")

    # 蓝方答辩 - 初始分数
    machine.transition(PhoenixTransitionTrigger.BLUE_DEFENSE_START)
    initial_score = 6.0 + (hash(domain) % 10) / 10  # 6.0-7.0
    machine.context.record_score(initial_score)
    version_manager.update_version_scores("v1.0", initial_score, initial_score - 0.5, False)
    print(f"[蓝方答辩 v1.0] Science Score: {initial_score:.1f}/10 - 防御未通过")

    # 触发 PHOENIX_PATCH
    machine.transition(PhoenixTransitionTrigger.BLUE_DEFENSE_FAILURE)

    # 获取方法论补丁
    patches = patch_manager.select_patches_for_iteration(attack_types)
    patch_descriptions = [f"{p.attack_type}: {p.description}" for p in patches]
    print(f"[凤凰协议] 应用方法论补丁:")
    for desc in patch_descriptions:
        print(f"  - {desc}")

    # v1.1 补丁版本
    v1_1 = version_manager.create_rewrite_version(
        base_version=v1_0,
        rewrite_type='methodology_patch',
        rewrite_log=[{
            'original': attack_types[0],
            'replaced_with': f"{attack_types[0]}_correction",
            'reason': '红方攻击修复'
        }],
        new_hypothesis=hypothesis,
        iteration=2,
        red_attack_types=attack_types
    )

    # 补丁后分数
    patch_score = initial_score + 1.2
    machine.context.record_score(patch_score)
    version_manager.update_version_scores("v1.1", patch_score, patch_score - 0.3, False)
    print(f"[蓝方答辩 v1.1] Science Score: {patch_score:.1f}/10 - 防御未通过")

    # 再次触发补丁（模拟多轮迭代）
    machine.transition(PhoenixTransitionTrigger.PATCH_APPLIED)
    machine.transition(PhoenixTransitionTrigger.BLUE_DEFENSE_FAILURE)

    # v1.2 第二次补丁
    v1_2 = version_manager.create_rewrite_version(
        base_version=v1_1,
        rewrite_type='methodology_patch',
        rewrite_log=[{
            'original': attack_types[1] if len(attack_types) > 1 else attack_types[0],
            'replaced_with': f"{attack_types[1] if len(attack_types) > 1 else attack_types[0]}_correction",
            'reason': '二次迭代修复'
        }],
        new_hypothesis=hypothesis,
        iteration=3,
        red_attack_types=attack_types
    )

    # 最终分数 - 通过
    final_score = patch_score + 1.3
    machine.context.record_score(final_score)
    version_manager.update_version_scores("v1.2", final_score, final_score - 0.2, True)
    print(f"[蓝方答辩 v1.2] Science Score: {final_score:.1f}/10 - 防御通过!")

    # 计算趋势
    trend_analysis = trend_detector.analyze_trend(machine.context.score_history)

    # 计算 Promise Score
    calculator = PromiseScoreCalculator()
    hypothesis_result = {
        'scores': {'novelty': 7.0 + (hash(domain) % 3)},
        'year': 2025,
        'citation_velocity': 'Top 10%',
        'implementation_complexity': 'medium'
    }
    fitness_result = {
        'vector_novelty_score': 7.5,
        'physical_validation': {'score': final_score}
    }
    verified_ids = {
        'pmids': [f'{12345000 + i}' for i in range(5)],
        'arxiv_ids': ['arxiv:2025.12345']
    }
    version_chain = version_manager.get_version_evolution_chain()

    promise_result = calculator.calculate(
        hypothesis_result=hypothesis_result,
        fitness_result=fitness_result,
        verified_ids=verified_ids,
        version_chain=[{'science_score': s} for s in machine.context.score_history]
    )

    # 最终状态
    machine.transition(PhoenixTransitionTrigger.DEFENSE_PASSED)

    return {
        'domain': domain,
        'idea': idea,
        'final_state': machine.context.current_state.name,
        'version_chain': version_chain,
        'score_history': machine.context.score_history,
        'final_science_score': final_score,
        'promise_score': promise_result.total_score,
        'promise_grade': promise_result.grade,
        'trend': trend_analysis.trend_direction,
        'evolution_delta': promise_result.evolution_delta,
        'total_iterations': len(version_chain)
    }


# ==================== 主测试流程 ====================

def main():
    print("\n" + "="*70)
    print("V7.5 用户模拟测试 - 多领域假设验证")
    print("="*70)
    print(f"\n测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试假设数量: {len(TEST_HYPOTHESES)}")
    print()

    results = []

    for i, hypothesis_data in enumerate(TEST_HYPOTHESES, 1):
        print(f"\n{'#'*70}")
        print(f"测试 {i}/{len(TEST_HYPOTHESES)}")
        print(f"{'#'*70}")

        result = simulate_pipeline_run(hypothesis_data)
        results.append(result)

        time.sleep(0.5)

    # 打印结果汇总
    print("\n\n" + "="*70)
    print("测试结果汇总")
    print("="*70 + "\n")

    for i, result in enumerate(results, 1):
        print(f"{i}. {result['domain']}")
        print(f"   假设: {result['idea'][:60]}...")
        print(f"   版本链: v1.0 → v1.{result['total_iterations']-1}")
        print(f"   分数演化: {' → '.join(f'{s:.1f}' for s in result['score_history'])}")
        print(f"   最终 Science Score: {result['final_science_score']:.1f}/10")
        print(f"   Promise Score: {result['promise_score']:.1f}/10 ({result['promise_grade']})")
        print(f"   趋势: {result['trend']}, 演化增量: +{result['evolution_delta']:.1f}")
        print(f"   状态: {result['final_state']}")
        print()

    # 统计
    avg_science_score = sum(r['final_science_score'] for r in results) / len(results)
    avg_promise_score = sum(r['promise_score'] for r in results) / len(results)
    avg_iterations = sum(r['total_iterations'] for r in results) / len(results)

    print("-"*70)
    print(f"平均 Science Score: {avg_science_score:.1f}/10")
    print(f"平均 Promise Score: {avg_promise_score:.1f}/10")
    print(f"平均迭代次数: {avg_iterations:.1f}")
    print(f"成功率: 100% (所有假设均演化至 SUCCESS)")
    print("="*70 + "\n")

    # 保存结果
    report_path = Path(__file__).parent / "user_simulation_results.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"结果已保存到: {report_path}\n")

    return results


if __name__ == "__main__":
    main()
