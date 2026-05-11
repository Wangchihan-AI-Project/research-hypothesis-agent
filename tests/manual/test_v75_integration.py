# -*- coding: utf-8 -*-
"""
V7.5 凤凰协议集成测试脚本

测试内容：
1. 所有核心模块导入验证
2. 状态机状态转换验证
3. 版本管理器功能验证
4. 分数趋势检测器验证
5. 替代路径生成器验证
6. Promise Score 计算验证
7. 方法论补丁优先级验证

作者: V7.5 架构工程师
日期: 2026-04-20
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== 测试结果收集 ====================

test_results = []

def run_test(name: str, func):
    """运行测试并收集结果"""
    try:
        func()
        test_results.append((name, "PASS", None))
        logger.info(f"✅ {name} - PASS")
        return True
    except Exception as e:
        test_results.append((name, "FAIL", str(e)))
        logger.error(f"❌ {name} - FAIL: {e}")
        return False

# ==================== 测试 1: 核心模块导入 ====================

def test_imports():
    """测试所有核心模块导入"""
    from src.core.phoenix_state_machine import (
        PhoenixState, PhoenixTransitionTrigger, PhoenixStateMachine
    )
    from src.core.hypothesis_version_manager import HypothesisVersionManager
    from src.core.score_trend_detector import ScoreTrendDetector
    from src.core.alternative_path_generator import AlternativePathGenerator
    from src.core.promise_score_calculator import PromiseScoreCalculator
    from src.core.methodology_patch_priority import MethodologyPatchPriorityManager
    from src.prompts.phoenix_rewrite_prompt import generate_phoenix_rewrite_prompt

    logger.info("所有核心模块导入成功")

# ==================== 测试 2: 状态机验证 ====================

def test_state_machine():
    """测试凤凰协议状态机"""
    from src.core.phoenix_state_machine import (
        PhoenixStateMachine, PhoenixState, PhoenixTransitionTrigger
    )

    # 创建状态机
    machine = PhoenixStateMachine()

    # 测试初始状态
    assert machine.context.current_state == PhoenixState.INITIAL
    logger.info(f"初始状态: {machine.context.current_state.name}")

    # 测试状态转换
    next_state = machine.transition(PhoenixTransitionTrigger.HYPOTHESIS_READY)
    assert next_state == PhoenixState.HYPOTHESIS_GEN
    logger.info(f"转换后状态: {next_state.name}")

    # 测试物理冲突触发重写
    rewrite_state = machine.transition(PhoenixTransitionTrigger.PHYSICAL_AXIOM_CONFlict)
    assert rewrite_state == PhoenixState.PHOENIX_REWRITE
    logger.info(f"物理冲突后状态: {rewrite_state.name}")

    # 测试迭代计数
    machine.context.phoenix_iterations = 8
    assert not machine.context.can_continue()
    logger.info("迭代限制验证通过")

# ==================== 测试 3: 版本管理器验证 ====================

def test_version_manager():
    """测试假设版本管理器"""
    from src.core.hypothesis_version_manager import HypothesisVersionManager

    # 创建管理器
    manager = HypothesisVersionManager()

    # 创建初始版本
    hypothesis = {
        "title": "测试假设",
        "details": "这是一个测试假设",
        "methodology": {"sensor": "测试传感器"},
        "expected_results": {"outcome": "测试结果"}
    }
    initial = manager.create_initial_version(
        hypothesis=hypothesis,
        iteration=1
    )
    assert initial.version_number == "v1.0"
    logger.info(f"初始版本: {initial.version_number}")

    # 创建重写版本
    rewrite = manager.create_rewrite_version(
        base_version=initial,
        rewrite_type="physical_fix",
        rewrite_log=[{"original": "量子共振", "replaced_with": "高频声学刺激"}],
        new_hypothesis={"title": "修正后的假设"}
    )
    assert rewrite.version_number == "v1.1"
    logger.info(f"重写版本: {rewrite.version_number}")

    # 更新分数
    manager.update_version_scores("v1.1", science_score=8.5, fitness_score=7.8, defense_passed=True)
    assert manager.get_current_version().science_score == 8.5
    logger.info(f"版本分数更新: {manager.get_current_version().science_score}")

    # 获取版本链
    chain = manager.get_version_evolution_chain()
    assert len(chain) == 2
    logger.info(f"版本链长度: {len(chain)}")

# ==================== 测试 4: 分数趋势检测器验证 ====================

def test_trend_detector():
    """测试分数趋势检测器"""
    from src.core.score_trend_detector import ScoreTrendDetector, should_trigger_compensation

    # 创建检测器
    detector = ScoreTrendDetector()

    # 测试上升趋势
    rising_history = [6.0, 6.8, 7.5, 8.2, 8.8]
    analysis = detector.analyze_trend(rising_history)
    assert analysis.is_rising == True
    assert analysis.should_trigger_compensation == False
    logger.info(f"上升趋势检测: slope={analysis.slope:.2f}")

    # 测试停滞
    stagnant_history = [7.0, 7.1, 7.05, 7.08]
    analysis = detector.analyze_trend(stagnant_history)
    assert analysis.is_stagnant == True
    logger.info(f"停滞检测: consecutive_stagnant_count={analysis.consecutive_stagnant_count}")

    # 测试补偿触发（使用模块级函数）
    trigger_history = [7.0, 7.1, 7.05, 7.08]
    should_compensate = should_trigger_compensation(trigger_history)
    assert should_compensate == True
    logger.info(f"补偿触发: {should_compensate}")

# ==================== 测试 5: 替代路径生成器验证 ====================

def test_alternative_path_generator():
    """测试替代路径生成器"""
    from src.core.alternative_path_generator import AlternativePathGenerator
    from src.core.pseudoscience_detector import PseudoscienceType

    # 创建生成器
    generator = AlternativePathGenerator()

    # 测试量子神秘主义替代路径
    hypothesis_text = "使用量子共振来调节细胞活性"
    paths, is_recoverable = generator.generate_alternative_paths(
        pseudoscience_type=PseudoscienceType.QUANTUM_MAGIC,
        hypothesis_text=hypothesis_text,
        detected_patterns=["量子共振"]
    )

    assert is_recoverable == True
    assert len(paths) > 0
    assert "高频声学刺激" in paths[0].scientific_replacement
    logger.info(f"替代路径: {paths[0].scientific_replacement}")
    logger.info(f"传感器类型: {paths[0].sensor_type}")

# ==================== 测试 6: Promise Score 计算验证 ====================

def test_promise_score_calculator():
    """测试 Promise Score 计算"""
    from src.core.promise_score_calculator import PromiseScoreCalculator

    # 创建计算器
    calculator = PromiseScoreCalculator()

    # 模拟输入数据
    hypothesis_result = {
        'scores': {'novelty': 8.5},
        'year': 2025,
        'citation_velocity': 'Top 10%',
        'implementation_complexity': 'medium'
    }
    fitness_result = {
        'vector_novelty_score': 8.2,
        'physical_validation': {'score': 8.0}
    }
    verified_ids = {
        'pmids': ['12345678', '23456789', '34567890'],
        'arxiv_ids': ['arxiv:1234.5678']
    }
    version_chain = [
        {'science_score': 6.5},
        {'science_score': 7.2},
        {'science_score': 8.5}
    ]

    # 计算 Promise Score
    result = calculator.calculate(
        hypothesis_result=hypothesis_result,
        fitness_result=fitness_result,
        verified_ids=verified_ids,
        version_chain=version_chain
    )

    assert 0 <= result.total_score <= 10
    assert result.evolution_delta > 0
    logger.info(f"Promise Score: {result.total_score:.2f}/10")
    logger.info(f"评级: {result.grade}")
    logger.info(f"演化增量: +{result.evolution_delta:.2f}")

# ==================== 测试 7: 方法论补丁优先级验证 ====================

def test_methodology_patch_priority():
    """测试方法论补丁优先级管理器"""
    from src.core.methodology_patch_priority import MethodologyPatchPriorityManager

    # 创建管理器
    manager = MethodologyPatchPriorityManager()

    # 测试优先级获取
    af3_priority = manager.get_patch_priority('AF3_LEAKAGE')
    overfitting_priority = manager.get_patch_priority('OVERFITTING')
    logger.info(f"AF3_LEAKAGE 优先级: {af3_priority.name}")
    logger.info(f"OVERFITTING 优先级: {overfitting_priority.name}")

    # 测试优先级排序
    attack_types = ['VALIDATION', 'OVERFITTING', 'AF3_LEAKAGE', 'BIAS']
    sorted_types = manager.prioritize_attack_types(attack_types)
    assert sorted_types[0] == 'AF3_LEAKAGE'  # CRITICAL 优先
    logger.info(f"优先级排序: {sorted_types}")

    # 测试补丁选择
    patches = manager.select_patches_for_iteration(attack_types)
    assert len(patches) <= 3  # 最多 3 个
    logger.info(f"选择的补丁数: {len(patches)}")

    # 测试解决方案关键词
    keywords = manager.get_solution_search_keywords(['OVERFITTING'])
    assert 'OVERFITTING' in keywords
    assert len(keywords['OVERFITTING']) > 0
    logger.info(f"解决方案关键词: {keywords['OVERFITTING'][0]}")

# ==================== 测试 8: Prompt 生成验证 ====================

def test_prompt_generation():
    """测试 Prompt 生成"""
    from src.prompts.phoenix_rewrite_prompt import generate_phoenix_rewrite_prompt
    from src.core.alternative_path_generator import AlternativePath
    from dataclasses import asdict

    # 创建替代路径
    alternative_path = AlternativePath(
        original_pattern="量子共振",
        pseudoscience_type="QUANTUM_MAGIC",
        scientific_replacement="高频声学刺激",
        sensor_type="超声探头 (1-10 MHz)",
        measurement_method="激光多普勒测振仪测量细胞膜振动响应",
        rationale="声波可产生可量化的生物效应",
        confidence=0.85,
        physical_principle="机械波在生物组织中的传播",
        example_reference="PMID: 33456789"
    )

    # 生成重写 prompt（使用 asdict 转换）
    prompt, new_version = generate_phoenix_rewrite_prompt(
        original_hypothesis="使用量子共振调节基因表达",
        alternative_paths=[asdict(alternative_path)],
        current_version="v1.0"
    )

    assert "v1.1" in new_version
    assert "高频声学刺激" in prompt
    assert "超声探头" in prompt
    logger.info(f"生成版本: {new_version}")
    logger.info(f"Prompt 长度: {len(prompt)} 字符")

# ==================== 主测试运行 ====================

def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("V7.5 凤凰协议集成测试")
    print("="*60 + "\n")

    # 运行所有测试
    run_test("核心模块导入", test_imports)
    run_test("状态机验证", test_state_machine)
    run_test("版本管理器验证", test_version_manager)
    run_test("分数趋势检测器验证", test_trend_detector)
    run_test("替代路径生成器验证", test_alternative_path_generator)
    run_test("Promise Score 计算验证", test_promise_score_calculator)
    run_test("方法论补丁优先级验证", test_methodology_patch_priority)
    run_test("Prompt 生成验证", test_prompt_generation)

    # 打印结果摘要
    print("\n" + "="*60)
    print("测试结果摘要")
    print("="*60)

    pass_count = sum(1 for _, status, _ in test_results if status == "PASS")
    fail_count = sum(1 for _, status, _ in test_results if status == "FAIL")

    for name, status, error in test_results:
        icon = "[PASS]" if status == "PASS" else "[FAIL]"
        print(f"{icon} {name}: {status}")
        if error:
            print(f"   错误: {error}")

    print("\n" + "-"*60)
    print(f"总计: {len(test_results)} 个测试")
    print(f"通过: {pass_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"成功率: {pass_count/len(test_results)*100:.1f}%")
    print("="*60 + "\n")

    return fail_count == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
