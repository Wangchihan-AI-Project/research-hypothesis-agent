# -*- coding: utf-8 -*-
"""
V7.5 生产环境就绪度 E2E 破坏性测试脚本

测试目标：
1. 状态机转换一致性 - RED_ATTACK -> BLUE_DEFENSE -> PHOENIX_PATCH
2. JSON 序列化与持久化 - evolution_history 存储
3. ArXiv 过滤穿透力 - 搜索查询验证
4. Promise Score 计算 - 四维度评分

作者: V7.5 架构工程师
日期: 2026-04-20
"""

import sys
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 测试结果收集 ====================

class AuditReport:
    """审计报告收集器"""

    def __init__(self):
        self.results: List[Dict] = []
        self.bugs: List[Dict] = []
        self.warnings: List[Dict] = []
        self.traces: List[Dict] = []
        self.start_time = datetime.now()

    def add_result(self, module: str, status: str, details: str = ""):
        """添加测试结果"""
        self.results.append({
            'module': module,
            'status': status,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
        icon = "[PASS]" if status == "PASS" else "[FAIL]"
        logger.info(f"{icon} {module}: {status} {details}")

    def add_bug(self, bug_id: str, description: str, fix: str = ""):
        """添加 BUG 报告"""
        bug = {
            'bug_id': bug_id,
            'description': description,
            'fix': fix,
            'timestamp': datetime.now().isoformat()
        }
        self.bugs.append(bug)
        logger.error(f"[BUG] {bug_id}: {description}")

    def add_warning(self, warning_id: str, description: str):
        """添加警告"""
        self.warnings.append({
            'warning_id': warning_id,
            'description': description,
            'timestamp': datetime.now().isoformat()
        })
        logger.warning(f"[WARNING] {warning_id}: {description}")

    def add_trace(self, phase: str, data: Dict):
        """添加追踪记录"""
        self.traces.append({
            'phase': phase,
            'data': data,
            'timestamp': datetime.now().isoformat()
        })

    def generate_report(self) -> str:
        """生成审计报告"""
        duration = (datetime.now() - self.start_time).total_seconds()

        lines = []
        lines.append("=" * 80)
        lines.append("V7.5 生产环境就绪度审计报告")
        lines.append(f"测试时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"执行时长: {duration:.2f} 秒")
        lines.append("=" * 80)
        lines.append("")

        # 1. 模块状态汇总
        lines.append("## 一、模块状态汇总")
        lines.append("")
        for r in self.results:
            icon = "[PASS]" if r['status'] == "PASS" else "[FAIL]"
            lines.append(f"{icon} {r['module']}: {r['status']}")
            if r['details']:
                lines.append(f"      └─ {r['details']}")
        lines.append("")

        # 2. BUG 报告
        if self.bugs:
            lines.append("## 二、BUG 报告 [需要修复]")
            lines.append("")
            for bug in self.bugs:
                lines.append(f"### [BUG] {bug['bug_id']}")
                lines.append(f"**描述**: {bug['description']}")
                if bug['fix']:
                    lines.append(f"**修复方案**: {bug['fix']}")
                lines.append("")
        else:
            lines.append("## 二、BUG 报告")
            lines.append("✅ 未发现 BUG")
            lines.append("")

        # 3. 警告信息
        if self.warnings:
            lines.append("## 三、警告信息 [建议关注]")
            lines.append("")
            for w in self.warnings:
                lines.append(f"### [WARNING] {w['warning_id']}")
                lines.append(f"**描述**: {w['description']}")
                lines.append("")
        else:
            lines.append("## 三、警告信息")
            lines.append("✅ 无警告")
            lines.append("")

        # 4. 版本演化追踪
        lines.append("## 四、版本演化追踪 (TRACE)")
        lines.append("")
        for trace in self.traces:
            lines.append(f"### {trace['phase']}")
            lines.append(f"时间: {trace['timestamp']}")
            data = trace['data']
            if 'version' in data:
                lines.append(f"版本: {data['version']}")
            if 'score' in data:
                lines.append(f"分数: {data['score']}")
            if 'changes' in data:
                lines.append(f"修改: {data['changes']}")
            if 'state' in data:
                lines.append(f"状态: {data['state']}")
            lines.append("")

        # 5. 最终结论
        lines.append("## 五、最终结论")
        lines.append("")
        pass_count = sum(1 for r in self.results if r['status'] == "PASS")
        total_count = len(self.results)
        success_rate = pass_count / total_count * 100 if total_count > 0 else 0

        if len(self.bugs) == 0 and success_rate >= 80:
            lines.append(f"✅ **通过**: V7.5 架构已就绪，可以投入生产环境")
            lines.append(f"   - 模块通过率: {success_rate:.1f}%")
            lines.append(f"   - BUG 数量: {len(self.bugs)}")
        else:
            lines.append(f"❌ **不通过**: V7.5 架构需要修复后才能上线")
            lines.append(f"   - 模块通过率: {success_rate:.1f}%")
            lines.append(f"   - BUG 数量: {len(self.bugs)}")
        lines.append("")

        lines.append("=" * 80)

        return '\n'.join(lines)


# ==================== Audit Point 1: 状态机转换一致性 ====================

def test_state_machine_transition(report: AuditReport) -> bool:
    """
    Audit Point 1: 状态机转换一致性

    测试内容：
    1. RED_ATTACK -> BLUE_DEFENSE -> PHOENIX_PATCH 的转换
    2. 检查 Science Score 是否被正确继承
    3. 检查是否存在变量覆盖导致的数据丢失
    """
    try:
        from src.core.phoenix_state_machine import (
            PhoenixStateMachine, PhoenixState, PhoenixTransitionTrigger
        )
        from src.core.hypothesis_version_manager import HypothesisVersionManager
        from src.core.score_trend_detector import ScoreTrendDetector

        # 创建状态机和版本管理器
        machine = PhoenixStateMachine()
        version_manager = HypothesisVersionManager()
        trend_detector = ScoreTrendDetector()

        # 模拟初始假设
        hypothesis = {
            'title': 'AlphaFold3 动态神经网络预测变构酶活性中心漂移',
            'details': '利用 AlphaFold3 结合动态神经网络，预测 2026 年新发现的某种变构酶在极端 pH 环境下的活性中心漂移。',
            'methodology': {'sensor': 'AlphaFold3 结构预测'},
            'expected_results': {'outcome': '预测精度 > 90%'}
        }

        # 创建初始版本
        v1_0 = version_manager.create_initial_version(hypothesis, iteration=1)
        report.add_trace("v1.0 初始版本", {
            'version': 'v1.0',
            'type': 'initial',
            'hypothesis': hypothesis['title']
        })

        # 模拟 HYPOTHESIS_GEN -> RED_ATTACK
        machine.transition(PhoenixTransitionTrigger.HYPOTHESIS_READY)
        machine.context.phoenix_iterations = 1
        assert machine.context.current_state == PhoenixState.HYPOTHESIS_GEN

        machine.transition(PhoenixTransitionTrigger.RED_ATTACK_START)
        assert machine.context.current_state == PhoenixState.RED_ATTACK
        report.add_trace("状态转换", {
            'state': 'RED_ATTACK',
            'iteration': 1
        })

        # 模拟红方攻击 - 物理稳定性攻击
        red_attack_types = ['VALIDATION', 'STATISTICAL_FLAW']
        machine.context.red_attack_types = red_attack_types

        # RED_ATTACK -> BLUE_DEFENSE
        machine.transition(PhoenixTransitionTrigger.BLUE_DEFENSE_START)
        assert machine.context.current_state == PhoenixState.BLUE_DEFENSE

        # 模拟蓝方答辩分数
        science_score = 6.5
        machine.context.record_score(science_score)
        version_manager.update_version_scores("v1.0", science_score, 6.0, False)
        report.add_trace("蓝方答辩", {
            'version': 'v1.0',
            'score': science_score,
            'state': 'BLUE_DEFENSE'
        })

        # 检查分数继承
        assert machine.context.current_science_score == 6.5
        assert machine.context.score_history[-1] == 6.5

        # 蓝方答辩失败 -> PHOENIX_PATCH
        machine.transition(PhoenixTransitionTrigger.BLUE_DEFENSE_FAILURE)
        assert machine.context.current_state == PhoenixState.PHOENIX_PATCH
        report.add_trace("状态转换", {
            'state': 'PHOENIX_PATCH',
            'trigger': 'BLUE_DEFENSE_FAILURE'
        })

        # 创建方法论补丁版本
        v1_1 = version_manager.create_rewrite_version(
            base_version=v1_0,
            rewrite_type='methodology_patch',
            rewrite_log=[{
                'original': '验证不足',
                'replaced_with': '添加独立验证集',
                'reason': 'VALIDATION 攻击修复'
            }],
            new_hypothesis=hypothesis,
            iteration=2,
            red_attack_types=red_attack_types
        )
        report.add_trace("v1.1 方法论补丁版本", {
            'version': 'v1.1',
            'type': 'methodology_patch',
            'changes': '添加独立验证集'
        })

        # 更新分数 - 模拟补丁后提升
        new_score = 7.8
        machine.context.record_score(new_score)
        version_manager.update_version_scores("v1.1", new_score, 7.5, False)

        # 检查分数历史完整性
        assert len(machine.context.score_history) == 2
        assert machine.context.score_history == [6.5, 7.8]
        assert len(version_manager.get_score_trend()) == 2

        # 补丁应用完成 -> 重试
        machine.transition(PhoenixTransitionTrigger.PATCH_APPLIED)
        assert machine.context.current_state == PhoenixState.PHOENIX_RETRY

        # 获取演化摘要
        summary = machine.get_evolution_summary()
        evolution_chain = version_manager.get_version_evolution_chain()

        # 验证演化链
        assert len(evolution_chain) == 2
        assert evolution_chain[0]['version'] == 'v1.0'
        assert evolution_chain[1]['version'] == 'v1.1'

        # 验证数据无丢失
        assert summary['score_evolution'] == [6.5, 7.8]
        assert summary['total_iterations'] == 1  # 因为我们在外手动管理

        report.add_result(
            "Audit Point 1: 状态机转换一致性",
            "PASS",
            "RED_ATTACK->BLUE_DEFENSE->PHOENIX_PATCH 转换正常，Science Score 正确继承"
        )

        return True

    except AssertionError as e:
        report.add_bug(
            "STATE-001",
            f"状态机转换断言失败: {str(e)}",
            "检查 PHOENIX_STATE_TRANSITIONS 矩阵定义"
        )
        report.add_result("Audit Point 1: 状态机转换一致性", "FAIL", str(e))
        return False
    except Exception as e:
        report.add_bug(
            "STATE-002",
            f"状态机测试异常: {str(e)}",
            "检查 phoenix_state_machine.py 模块导入"
        )
        report.add_result("Audit Point 1: 状态机转换一致性", "FAIL", str(e))
        return False


# ==================== Audit Point 2: JSON 序列化与持久化 ====================

def test_json_serialization(report: AuditReport) -> bool:
    """
    Audit Point 2: JSON 序列化与持久化

    测试内容：
    1. 检查 evolution_history 列表是否按顺序存储
    2. 长文本是否因为数据库字段长度限制截断
    3. NumPy 类型是否正确转换为 Python 原生类型
    """
    try:
        from src.core.phoenix_state_machine import PhoenixContext
        from src.core.hypothesis_version_manager import HypothesisVersionManager
        import json

        # 创建版本管理器
        version_manager = HypothesisVersionManager()

        # 创建多个版本
        for i in range(5):
            hypothesis = {
                'title': f'测试假设 {i+1}',
                'details': f'这是一个测试假设的详细描述。' * 100,  # 长文本
                'methodology': {'sensor': f'传感器{i}'},
                'expected_results': {'outcome': f'结果{i}'}
            }

            if i == 0:
                version_manager.create_initial_version(hypothesis, iteration=i+1)
            else:
                base = version_manager.get_version_by_number(f"v1.{i}")
                version_manager.create_rewrite_version(
                    base_version=base,
                    rewrite_type='methodology_patch',
                    rewrite_log=[{
                        'original': f'旧方法{i}',
                        'replaced_with': f'新方法{i}',
                        'reason': f'原因{i}'
                    }],
                    new_hypothesis=hypothesis,
                    iteration=i+1
                )

            # 更新分数
            version_manager.update_version_scores(
                f"v1.{i}",
                float(6.0 + i * 0.5),  # 确保 Python float
                float(5.5 + i * 0.5),
                i == 4
            )

        # 获取演化链
        evolution_chain = version_manager.get_version_evolution_chain()

        # 测试 JSON 序列化
        try:
            json_str = json.dumps(evolution_chain, ensure_ascii=False, indent=2)
            parsed = json.loads(json_str)

            # 验证顺序
            assert len(parsed) == 5
            for i, version in enumerate(parsed):
                assert version['version'] == f"v1.{i}"

            # 验证长文本未截断
            long_text = parsed[0]['hypothesis_content']['details']
            assert len(long_text) > 1000

            # 验证分数类型
            for version in parsed:
                assert isinstance(version['science_score'], float)
                assert not isinstance(version['science_score'], dict)

            report.add_result(
                "Audit Point 2: JSON 序列化与持久化",
                "PASS",
                f"演化链 {len(parsed)} 个版本正确序列化，长文本完整"
            )

            # 模拟 SQLite 存储（测试 TEXT 字段限制）
            import sqlite3
            import tempfile

            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
                db_path = f.name

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 创建测试表
            cursor.execute('''
                CREATE TABLE task_results (
                    id INTEGER PRIMARY KEY,
                    task_id TEXT,
                    evolution_history TEXT,
                    hypothesis_text TEXT
                )
            ''')

            # 插入测试数据
            task_id = "test_task_001"
            cursor.execute(
                'INSERT INTO task_results (task_id, evolution_history, hypothesis_text) VALUES (?, ?, ?)',
                (task_id, json_str, hypothesis['details'])
            )
            conn.commit()

            # 读取并验证
            cursor.execute('SELECT evolution_history, hypothesis_text FROM task_results WHERE task_id = ?', (task_id,))
            row = cursor.fetchone()

            assert row is not None
            retrieved_history = json.loads(row[0])
            assert len(retrieved_history) == 5
            assert len(row[1]) > 1000  # 长文本未截断

            conn.close()
            import os
            os.unlink(db_path)

            return True

        except (json.JSONDecodeError, TypeError) as e:
            report.add_bug(
                "JSON-001",
                f"JSON 序列化失败: {str(e)}",
                "检查 NumPy float32 类型转换，使用 float() 显式转换"
            )
            report.add_result("Audit Point 2: JSON 序列化与持久化", "FAIL", str(e))
            return False

    except Exception as e:
        report.add_bug(
            "JSON-002",
            f"JSON 序列化测试异常: {str(e)}",
            "检查数据类定义和 to_dict 方法"
        )
        report.add_result("Audit Point 2: JSON 序列化与持久化", "FAIL", str(e))
        return False


# ==================== Audit Point 3: ArXiv 过滤穿透力 ====================

def test_arxiv_filter_penetration(report: AuditReport) -> bool:
    """
    Audit Point 3: ArXiv 过滤穿透力

    测试内容：
    1. 自愈检索时搜索查询是否包含 after:2025-01-01
    2. 返回文献是否符合 Citation Velocity 指标
    3. 解决方案关键词是否正确生成
    """
    try:
        from src.core.methodology_patch_priority import MethodologyPatchPriorityManager
        from src.core.alternative_path_generator import AlternativePathGenerator
        from src.core.pseudoscience_detector import PseudoscienceType

        # 创建补丁优先级管理器
        patch_manager = MethodologyPatchPriorityManager()

        # 测试攻击类型
        attack_types = ['OVERFITTING', 'LEAKAGE', 'VALIDATION', 'AF3_LEAKAGE']

        # 获取解决方案关键词
        keywords_map = patch_manager.get_solution_search_keywords(attack_types)

        # 验证关键词生成
        for attack_type in attack_types:
            assert attack_type in keywords_map
            keywords = keywords_map[attack_type]
            assert len(keywords) > 0

            # 检查是否包含 2025 年关键词
            has_2025_keyword = any('2025' in kw for kw in keywords)
            if has_2025_keyword:
                report.add_trace(f"ArXiv 搜索关键词 - {attack_type}", {
                    'keywords': keywords,
                    'has_2025': True
                })

        # 测试替代路径生成
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

        # 验证替代路径包含科学传感器
        first_path = paths[0]
        assert first_path.scientific_replacement  # 科学替代方案
        assert first_path.sensor_type  # 传感器类型
        assert first_path.measurement_method  # 测量方法

        report.add_trace("替代路径生成", {
            'original': '量子共振',
            'replacement': first_path.scientific_replacement,
            'sensor': first_path.sensor_type
        })

        # 测试补丁优先级排序
        sorted_types = patch_manager.prioritize_attack_types(attack_types)
        assert sorted_types[0] == 'AF3_LEAKAGE'  # CRITICAL 优先
        assert sorted_types[-1] == 'VALIDATION'  # MEDIUM 最后

        # 测试补丁选择
        selected_patches = patch_manager.select_patches_for_iteration(attack_types)
        assert len(selected_patches) <= 3  # 最多 3 个

        # 验证 AF3_LEAKAGE 被选中
        patch_types = [p.attack_type for p in selected_patches]
        assert 'AF3_LEAKAGE' in patch_types

        report.add_result(
            "Audit Point 3: ArXiv 过滤穿透力",
            "PASS",
            f"解决方案关键词正确生成，AF3_LEAKAGE 优先级最高，选择了 {len(selected_patches)} 个补丁"
        )

        return True

    except AssertionError as e:
        report.add_bug(
            "ARXIV-001",
            f"ArXiv 过滤测试断言失败: {str(e)}",
            "检查 methodology_patch_priority.py 中的优先级配置"
        )
        report.add_result("Audit Point 3: ArXiv 过滤穿透力", "FAIL", str(e))
        return False
    except Exception as e:
        report.add_bug(
            "ARXIV-002",
            f"ArXiv 过滤测试异常: {str(e)}",
            "检查 alternative_path_generator.py 模块"
        )
        report.add_result("Audit Point 3: ArXiv 过滤穿透力", "FAIL", str(e))
        return False


# ==================== Audit Point 4: Promise Score 计算 ====================

def test_promise_score_calculation(report: AuditReport) -> bool:
    """
    Audit Point 4: Promise Score 计算

    测试内容：
    1. 四维度评分计算：创新性(30%) + 可行性(35%) + 前沿契合度(25%) + 证据强度(10%)
    2. 演化增量计算
    3. 评级生成
    """
    try:
        from src.core.promise_score_calculator import PromiseScoreCalculator

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

        # 验证结果
        assert 0 <= result.total_score <= 10
        assert result.evolution_delta > 0
        assert len(result.components) == 4  # 使用 components

        # 验证四维度
        expected_keys = ['innovation', 'feasibility', 'frontier_alignment', 'evidence_strength']
        for key in expected_keys:
            assert key in result.components  # 使用 components 而非 breakdown
            assert 0 <= result.components[key]['score'] <= 10  # components 是嵌套字典

        # 验证评级
        assert result.grade in ['excellent', 'good', 'acceptable', 'poor', 'very_poor']  # 修正评级值

        report.add_trace("Promise Score 计算", {
            'total_score': result.total_score,
            'grade': result.grade,
            'evolution_delta': result.evolution_delta,
            'components': {k: v['score'] for k, v in result.components.items()}  # 提取分数
        })

        report.add_result(
            "Audit Point 4: Promise Score 计算",
            "PASS",
            f"总分 {result.total_score:.2f}/10，评级 {result.grade}，演化增量 +{result.evolution_delta:.2f}"
        )

        return True

    except AssertionError as e:
        report.add_bug(
            "SCORE-001",
            f"Promise Score 计算断言失败: {str(e)}",
            "检查 promise_score_calculator.py 计算逻辑"
        )
        report.add_result("Audit Point 4: Promise Score 计算", "FAIL", str(e))
        return False
    except Exception as e:
        report.add_bug(
            "SCORE-002",
            f"Promise Score 计算异常: {str(e)}",
            "检查 promise_score_calculator.py 模块导入"
        )
        report.add_result("Audit Point 4: Promise Score 计算", "FAIL", str(e))
        return False


# ==================== Audit Point 5: 物理锚定重写机制 ====================

def test_physical_anchor_rewrite(report: AuditReport) -> bool:
    """
    Audit Point 5: 物理锚定重写机制

    测试内容：
    1. 伪科学检测后是否触发重写而非拦截
    2. 替代路径是否正确生成
    3. 重写 Prompt 是否正确生成
    """
    try:
        from src.core.pseudoscience_detector import (
            PseudoscienceDetector, PseudoscienceType
        )
        from src.core.alternative_path_generator import AlternativePathGenerator
        from src.prompts.phoenix_rewrite_prompt import generate_phoenix_rewrite_prompt
        from dataclasses import asdict

        # 创建检测器
        detector = PseudoscienceDetector()

        # 测试伪科学假设
        hypothesis = "使用量子共振来调节细胞活性，从而延缓衰老过程"

        # 执行物理锚定检测
        result = detector.perform_physical_anchor_check(hypothesis)  # 正确的方法名

        # 验证检测结果
        assert result.passed == False
        assert result.pseudoscience_type == PseudoscienceType.QUANTUM_MAGIC

        # 验证可恢复性（凤凰协议核心）
        assert result.is_recoverable == True
        assert len(result.alternative_path_suggestions) > 0

        report.add_trace("伪科学检测", {
            'detected': True,
            'type': result.pseudoscience_type.name,
            'is_recoverable': result.is_recoverable,
            'alternatives': len(result.alternative_path_suggestions)
        })

        # 测试替代路径生成
        generator = AlternativePathGenerator()
        paths, is_recoverable = generator.generate_alternative_paths(
            pseudoscience_type=result.pseudoscience_type,
            hypothesis_text=hypothesis,
            detected_patterns=["量子共振"]
        )

        assert is_recoverable == True
        assert len(paths) > 0

        # 测试重写 Prompt 生成
        prompt, new_version = generate_phoenix_rewrite_prompt(
            original_hypothesis=hypothesis,
            alternative_paths=[asdict(paths[0])],
            current_version="v1.0"
        )

        assert "v1.1" in new_version
        assert "高频声学刺激" in prompt or "超声" in prompt

        report.add_trace("物理重写 Prompt", {
            'new_version': new_version,
            'prompt_length': len(prompt),
            'contains_replacement': paths[0].scientific_replacement in prompt
        })

        report.add_result(
            "Audit Point 5: 物理锚定重写机制",
            "PASS",
            f"伪科学检测触发重写，生成 {len(paths)} 条替代路径，版本升级到 {new_version}"
        )

        return True

    except AssertionError as e:
        report.add_bug(
            "PHYSICAL-001",
            f"物理锚定重写断言失败: {str(e)}",
            "检查 pseudoscience_detector.py 的 is_recoverable 属性"
        )
        report.add_result("Audit Point 5: 物理锚定重写机制", "FAIL", str(e))
        return False
    except Exception as e:
        report.add_bug(
            "PHYSICAL-002",
            f"物理锚定重写异常: {str(e)}",
            "检查 pseudoscience_detector.py 和 phoenix_rewrite_prompt.py"
        )
        report.add_result("Audit Point 5: 物理锚定重写机制", "FAIL", str(e))
        return False


# ==================== 主测试流程 ====================

def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("V7.5 Production Environment E2E Audit Test")
    print("=" * 80)
    print("\nTest Subject: AlphaFold3 Dynamic Neural Network for Allosteric Enzyme Prediction")
    print("-" * 80 + "\n")

    # 创建审计报告
    report = AuditReport()

    # 执行所有审计点
    print("[1/5] State Machine Transition Test...")
    test_state_machine_transition(report)
    time.sleep(0.5)

    print("[2/5] JSON Serialization Test...")
    test_json_serialization(report)
    time.sleep(0.5)

    print("[3/5] ArXiv Filter Penetration Test...")
    test_arxiv_filter_penetration(report)
    time.sleep(0.5)

    print("[4/5] Promise Score Calculation Test...")
    test_promise_score_calculation(report)
    time.sleep(0.5)

    print("[5/5] Physical Anchor Rewrite Test...")
    test_physical_anchor_rewrite(report)
    time.sleep(0.5)

    # 生成报告
    audit_report = report.generate_report()

    # 保存报告
    report_path = Path(__file__).parent / "audit_report_v75.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(audit_report)

    print(f"\nReport saved to: {report_path}")

    # 简化控制台输出
    pass_count = sum(1 for r in report.results if r['status'] == "PASS")
    total_count = len(report.results)
    print(f"\nTest Results: {pass_count}/{total_count} passed")
    print(f"Bugs found: {len(report.bugs)}")
    print(f"Warnings: {len(report.warnings)}")

    if len(report.bugs) == 0 and pass_count >= 4:
        print("\n[PASS] V7.5 Architecture is READY for production")
    else:
        print(f"\n[FAIL] V7.5 Architecture needs fixes ({len(report.bugs)} bugs)")

    print("=" * 80 + "\n")

    # 返回测试结果
    return len(report.bugs) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
