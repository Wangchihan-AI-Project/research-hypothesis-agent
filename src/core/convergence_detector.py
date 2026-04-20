# -*- coding: utf-8 -*-
"""
V7.1 收敛性检测器 (Convergence Detector)

防止红蓝循环论证陷阱 - 检测反馈修正是否实质改善

V7.1 CDE 漏洞修复：
- 维度逃逸检测：检测红方是否在改变攻击策略而非扩展维度
- 新维度合理性验证：新增维度必须与假设内容相关
- 维度语义相似度检查：防止用不同名称表达相同攻击意图
- 维度突变检测：短时间内维度剧烈变化触发警报

核心机制（继承）：
1. 分数改善检测（每轮至少提升 MIN_IMPROVEMENT_THRESHOLD）
2. 维度扩展检测（红方最多扩展攻击维度 MAX_DIMENSION_EXPANSION 次）
3. 震荡检测（分数交替升降）
4. 死锁预警

作者: 架构师 V7.0 → V7.1
日期: 2026-04-17
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import Counter

logger = logging.getLogger(__name__)


# ==================== V7.1: 维度语义等价映射 ====================
# 防止红方用不同名称表达相同攻击意图

DIMENSION_SEMANTIC_EQUIVALENCE = {
    # 数据相关攻击维度（等价组）
    'data_leakage': ['data_leak', 'information_leak', 'privacy_leak', 'data_exposure'],
    'data_quality': ['data_integrity', 'data_accuracy', 'data_reliability', 'measurement_error'],
    'missing_data': ['data_missing', 'incomplete_data', 'data_sparsity', 'missing_values'],

    # 方法论相关攻击维度（等价组）
    'endogeneity': ['endogenous', 'causality_issue', 'reverse_causation', 'causal_confusion'],
    'confounding': ['confounder', 'confounding_factor', 'omitted_variable', 'selection_bias'],
    'multiple_testing': ['p_hacking', 'multiple_comparison', 'false_discovery', 'statistical_inflation'],
    'overfitting': ['overfit', 'model_complexity', 'generalization_error', 'data_fitting'],

    # 可解释性相关攻击维度（等价组）
    'interpretability': ['explainability', 'black_box', 'interpretation_issue', 'semantic_clarity'],
    'reproducibility': ['replication', 'reproducible', 'reproducibility_issue', 'replication_failure'],

    # 证据相关攻击维度（等价组）
    'weak_evidence': ['insufficient_evidence', 'limited_evidence', 'evidence_gap', 'support_weak'],
    'contradictory_evidence': ['conflicting_evidence', 'evidence_conflict', 'counter_evidence'],
}

# V7.1: 合理维度扩展关键词映射
# 新增维度必须与假设内容相关
VALID_DIMENSION_CONTEXT_MAPPING = {
    'data_leakage': ['dataset', 'data', 'feature', 'variable', 'sample', 'cohort'],
    'endogeneity': ['causal', 'effect', 'relationship', 'association', 'correlation'],
    'multiple_testing': ['statistical', 'p-value', 'significance', 'test', 'comparison'],
    'overfitting': ['model', 'prediction', 'machine_learning', 'algorithm', 'fitting'],
    'confounding': ['factor', 'variable', 'covariate', 'adjustment', 'control'],
    'interpretability': ['mechanism', 'pathway', 'explanation', 'biological', 'clinical'],
}


class DimensionEscapeType(Enum):
    """V7.1 维度逃逸类型"""
    SEMANTIC_RENAME = "semantic_rename"  # 语义重命名（同一攻击意图换名）
    IRRELEVANT_EXTENSION = "irrelevant_extension"  # 无关扩展（新增维度与假设无关）
    RAPID_MUTATION = "rapid_mutation"  # 快速突变（短时间内维度剧变）
    STRATEGY_CHANGE = "strategy_change"  # 策略变更（改变攻击核心方向）
}


class ConvergenceState(Enum):
    """收敛状态"""
    CONTINUE = "continue"           # 继续迭代
    CONVERGED = "converged"          # 已收敛
    NO_IMPROVEMENT = "no_improvement"  # 无改善
    OSCILLATION = "oscillation"      # 震荡
    DIMENSION_OVERFLOW = "dimension_overflow"  # 维度溢出
    DEADLOCK = "deadlock"            # 死锁


@dataclass
class ConvergenceCheckResult:
    """收敛检测结果"""
    state: ConvergenceState
    should_continue: bool
    reason: str
    current_score: float
    previous_score: Optional[float] = None
    improvement: float = 0.0
    iteration_count: int = 0
    dimension_count: int = 0
    warning: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'state': self.state.value,
            'should_continue': self.should_continue,
            'reason': self.reason,
            'current_score': self.current_score,
            'previous_score': self.previous_score,
            'improvement': self.improvement,
            'iteration_count': self.iteration_count,
            'dimension_count': self.dimension_count,
            'warning': self.warning
        }


class ConvergenceDetector:
    """
    V7.0 收敛性检测器 - 防止红蓝循环论证陷阱

    问题：
    - DefenseCommittee 失败触发反馈循环
    - 红方攻击维度可能无限扩展
    - 每轮修正可能引入新问题而非改善
    - LLM 的"过度挑剔"与"过度防御"倾向形成死锁

    解决方案：
    1. 分数改善检测
    2. 维度扩展限制
    3. 震荡检测
    4. 死锁预警
    """

    # ==================== 收敛阈值配置 ====================

    MIN_IMPROVEMENT_THRESHOLD = 0.5  # 每轮至少提升 0.5 分
    MAX_DIMENSION_EXPANSION = 3      # 红方最多新增攻击维度 3 次
    OSCILLATION_WINDOW = 4           # 震荡检测窗口（连续4轮）
    MAX_ITERATIONS = 5               # 最大迭代次数
    DEADLOCK_SCORE_THRESHOLD = 6.0   # 死锁分数阈值（低于此值持续无法提升）
    DIMENSION_LOCK_ENABLED = True    # 维度锁定开关

    def __init__(self, config: Dict = None):
        """
        初始化收敛检测器

        Args:
            config: 配置参数（可选）
        """
        # 应用配置覆盖
        if config:
            self.MIN_IMPROVEMENT_THRESHOLD = config.get('min_improvement_threshold', 0.5)
            self.MAX_DIMENSION_EXPANSION = config.get('max_dimension_expansion', 3)
            self.OSCILLATION_WINDOW = config.get('oscillation_window', 4)
            self.MAX_ITERATIONS = config.get('max_iterations', 5)
            self.DEADLOCK_SCORE_THRESHOLD = config.get('deadlock_score_threshold', 6.0)

        # 历史记录
        self.score_history: List[float] = []
        self.dimension_history: List[Set[str]] = []
        self.iteration_count: int = 0
        self.start_time: datetime = datetime.now()

        # 维度锁定
        self._initial_dimensions: Optional[Set[str]] = None
        self._dimension_expansion_count: int = 0

        # V7.1: 维度逃逸追踪
        self._dimension_escape_count: int = 0
        self._last_dimensions: Optional[Set[str]] = None
        self._dimension_change_history: List[Dict] = []

        logger.info(
            f"[ConvergenceDetector V7.1] 初始化完成\n"
            f"  最小改善阈值: {self.MIN_IMPROVEMENT_THRESHOLD}\n"
            f"  最大维度扩展: {self.MAX_DIMENSION_EXPANSION}\n"
            f"  震荡检测窗口: {self.OSCILLATION_WINDOW}\n"
            f"  最大迭代次数: {self.MAX_ITERATIONS}\n"
            f"  V7.1 维度逃逸检测: 已启用"
        )

    def check_convergence(
        self,
        current_score: float,
        attack_dimensions: List[str]
    ) -> ConvergenceCheckResult:
        """
        检查是否收敛

        Args:
            current_score: 当前假设分数
            attack_dimensions: 红方攻击维度列表

        Returns:
            ConvergenceCheckResult: 收敛检测结果
        """
        self.iteration_count += 1
        current_dims = set(attack_dimensions)

        # 记录历史
        self.score_history.append(current_score)
        self.dimension_history.append(current_dims)

        # 初始化基准维度（第一轮）
        if self._initial_dimensions is None:
            self._initial_dimensions = current_dims

        # 计算改善量
        previous_score = self.score_history[-2] if len(self.score_history) >= 2 else None
        improvement = 0.0
        if previous_score is not None:
            improvement = current_score - previous_score

        # ==================== 检测逻辑 ====================

        # 1. 最大迭代次数检测
        if self.iteration_count >= self.MAX_ITERATIONS:
            return ConvergenceCheckResult(
                state=ConvergenceState.CONVERGED,
                should_continue=False,
                reason=f"达到最大迭代次数 ({self.iteration_count}/{self.MAX_ITERATIONS})",
                current_score=current_score,
                previous_score=previous_score,
                improvement=improvement,
                iteration_count=self.iteration_count,
                dimension_count=len(current_dims)
            )

        # 2. 分数改善检测
        if len(self.score_history) >= 2 and improvement < self.MIN_IMPROVEMENT_THRESHOLD:
            # 连续无改善检测
            no_improvement_count = 0
            for i in range(len(self.score_history) - 1):
                if self.score_history[i + 1] - self.score_history[i] < self.MIN_IMPROVEMENT_THRESHOLD:
                    no_improvement_count += 1

            if no_improvement_count >= 2:
                return ConvergenceCheckResult(
                    state=ConvergenceState.NO_IMPROVEMENT,
                    should_continue=False,
                    reason=f"连续 {no_improvement_count} 轮无实质改善 (提升 {improvement:.2f} < {self.MIN_IMPROVEMENT_THRESHOLD})",
                    current_score=current_score,
                    previous_score=previous_score,
                    improvement=improvement,
                    iteration_count=self.iteration_count,
                    dimension_count=len(current_dims),
                    warning="建议终止迭代或执行激进突变"
                )

        # 3. 维度扩展检测
        if self.DIMENSION_LOCK_ENABLED and self._initial_dimensions:
            new_dims = current_dims - self._initial_dimensions
            if new_dims:
                self._dimension_expansion_count += len(new_dims)

                # V7.1: 维度逃逸检测
                escape_result = self._detect_dimension_escape(
                    current_dims=current_dims,
                    previous_dims=self._last_dimensions or self._initial_dimensions,
                    new_dims=new_dims
                )

                if escape_result['detected']:
                    self._dimension_escape_count += 1
                    logger.warning(
                        f"[ConvergenceDetector V7.1] 维度逃逸检测触发\n"
                        f"  类型: {escape_result['escape_type']}\n"
                        f"  详情: {escape_result['details']}\n"
                        f"  累计逃逸次数: {self._dimension_escape_count}"
                    )

                    # 维度逃逸超过阈值 → 熔断
                    if self._dimension_escape_count >= 2:
                        return ConvergenceCheckResult(
                            state=ConvergenceState.DIMENSION_OVERFLOW,
                            should_continue=False,
                            reason=f"维度逃逸检测触发 ({escape_result['escape_type']})",
                            current_score=current_score,
                            previous_score=previous_score,
                            improvement=improvement,
                            iteration_count=self.iteration_count,
                            dimension_count=len(current_dims),
                            warning=f"红方攻击策略异常: {escape_result['details']}"
                        )

                logger.warning(
                    f"[ConvergenceDetector V7.1] 维度扩展: {new_dims}\n"
                    f"  总扩展次数: {self._dimension_expansion_count}/{self.MAX_DIMENSION_EXPANSION}"
                )

            if self._dimension_expansion_count > self.MAX_DIMENSION_EXPANSION:
                return ConvergenceCheckResult(
                    state=ConvergenceState.DIMENSION_OVERFLOW,
                    should_continue=False,
                    reason=f"攻击维度过度扩展 ({self._dimension_expansion_count} > {self.MAX_DIMENSION_EXPANSION})",
                    current_score=current_score,
                    previous_score=previous_score,
                    improvement=improvement,
                    iteration_count=self.iteration_count,
                    dimension_count=len(current_dims),
                    warning=f"新增维度: {new_dims}"
                )

            # V7.1: 更新上一轮维度记录
            self._last_dimensions = current_dims

            # V7.1: 记录维度变化历史
            self._dimension_change_history.append({
                'iteration': self.iteration_count,
                'dimensions': list(current_dims),
                'new_dims': list(new_dims),
                'removed_dims': list(self._last_dimensions - current_dims) if self._last_dimensions else []
            })

        # 4. V7.1 智能震荡检测（分数交替升降）
        if len(self.score_history) >= self.OSCILLATION_WINDOW:
            recent = self.score_history[-self.OSCILLATION_WINDOW:]

            # V7.1 改进：使用智能震荡检测而非简单升降交替
            oscillation_result = self._check_intelligent_oscillation(
                recent_scores=recent,
                current_dims=current_dims,
                iteration_count=self.iteration_count
            )

            if oscillation_result['is_true_oscillation']:
                return ConvergenceCheckResult(
                    state=ConvergenceState.OSCILLATION,
                    should_continue=False,
                    reason=oscillation_result['reason'],
                    current_score=current_score,
                    previous_score=previous_score,
                    improvement=improvement,
                    iteration_count=self.iteration_count,
                    dimension_count=len(current_dims),
                    warning=oscillation_result['warning']
                )

        # 5. 死锁检测（分数持续低于阈值且无改善趋势）
        if current_score < self.DEADLOCK_SCORE_THRESHOLD and len(self.score_history) >= 3:
            # 检查是否有改善趋势
            trend = self._calculate_trend()
            if trend < 0.1:  # 无明显改善趋势
                return ConvergenceCheckResult(
                    state=ConvergenceState.DEADLOCK,
                    should_continue=False,
                    reason=f"死锁预警：分数持续低于阈值 ({current_score:.2f} < {self.DEADLOCK_SCORE_THRESHOLD})",
                    current_score=current_score,
                    previous_score=previous_score,
                    improvement=improvement,
                    iteration_count=self.iteration_count,
                    dimension_count=len(current_dims),
                    warning="建议执行激进突变或终止迭代"
                )

        # ==================== 正常继续 ====================

        return ConvergenceCheckResult(
            state=ConvergenceState.CONTINUE,
            should_continue=True,
            reason="继续迭代",
            current_score=current_score,
            previous_score=previous_score,
            improvement=improvement,
            iteration_count=self.iteration_count,
            dimension_count=len(current_dims)
        )

    def _calculate_trend(self) -> float:
        """
        计算分数改善趋势

        使用简单线性回归斜率

        Returns:
            float: 趋势值（正值表示改善）
        """
        if len(self.score_history) < 2:
            return 0.0

        n = len(self.score_history)
        x_sum = sum(range(n))
        y_sum = sum(self.score_history)
        xy_sum = sum(i * self.score_history[i] for i in range(n))
        x2_sum = sum(i ** 2 for i in range(n))

        # 线性回归斜率
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum ** 2)
        return slope

    # ==================== V7.1 新增：智能震荡检测 ====================

    def _check_intelligent_oscillation(
        self,
        recent_scores: List[float],
        current_dims: Set[str],
        iteration_count: int
    ) -> Dict:
        """
        V7.1 智能震荡检测

        核心改进：
        1. 改善幅度感知：仅当升降幅度都 < MIN_IMPROVEMENT_THRESHOLD 时才视为震荡
        2. 维度扩展豁免：红方新增维度导致的分数下降不计入震荡
        3. 净改善计算：区分"无效震荡"和"有效改善但被攻击打断"

        Args:
            recent_scores: 最近分数序列
            current_dims: 当前攻击维度
            iteration_count: 当前迭代次数

        Returns:
            Dict: {
                'is_true_oscillation': bool,
                'reason': str,
                'warning': str,
                'net_improvement': float,
                'dimension_expansion_rounds': int
            }
        """
        result = {
            'is_true_oscillation': False,
            'reason': '',
            'warning': '',
            'net_improvement': 0.0,
            'dimension_expansion_rounds': 0
        }

        # Step 1: 检测升降交替模式
        is_alternating = True
        for i in range(len(recent_scores) - 2):
            diff1 = recent_scores[i + 1] - recent_scores[i]
            diff2 = recent_scores[i + 2] - recent_scores[i + 1]
            if not ((diff1 > 0 and diff2 < 0) or (diff1 < 0 and diff2 > 0)):
                is_alternating = False
                break

        if not is_alternating:
            return result  # 不是升降交替，不存在震荡

        # Step 2: 计算净改善
        total_improvement = 0.0
        total_decline = 0.0
        dimension_expansion_rounds = 0

        for i in range(len(recent_scores) - 1):
            diff = recent_scores[i + 1] - recent_scores[i]

            if diff > 0:
                # 检查是否超过改善阈值
                if diff >= self.MIN_IMPROVEMENT_THRESHOLD:
                    total_improvement += diff  # 有效改善
                else:
                    total_improvement += diff * 0.3  # 微小改善，降权
            else:
                # V7.1 核心：检查是否为维度扩展导致的下降
                if self._is_dimension_expansion_round(i + iteration_count - len(recent_scores)):
                    dimension_expansion_rounds += 1
                    # 维度扩展豁免：不计入真实下降
                    logger.info(f"[V7.1] 维度扩展豁免：第{i+1}轮下降 {-diff:.2f} 是红方新增维度导致的")
                else:
                    total_decline += abs(diff)  # 真实下降

        # Step 3: 计算净改善
        net_improvement = total_improvement - total_decline
        result['net_improvement'] = net_improvement
        result['dimension_expansion_rounds'] = dimension_expansion_rounds

        # Step 4: 判断是否为真实震荡
        # V7.1 核心规则：
        # - 净改善 > 0 → 不是震荡（有效改善）
        # - 净改善 < 0 且维度扩展豁免次数 >= 2 → 警告但不熔断
        # - 净改善 < 0 且无豁免 → 真实震荡

        if net_improvement > self.MIN_IMPROVEMENT_THRESHOLD:
            # 有净改善 → 不是震荡
            result['reason'] = f"有净改善（+{net_improvement:.2f}），非无效震荡"
            result['warning'] = f"分数序列看似震荡但存在实质性改善"
            return result

        if dimension_expansion_rounds >= 2:
            # 维度扩展导致的波动 → 警告但不熔断
            result['reason'] = f"维度扩展导致波动（豁免{dimension_expansion_rounds}轮），继续迭代"
            result['warning'] = f"分数下降是红方新增攻击维度导致的正常反馈"
            return result

        if net_improvement < 0:
            # 净下降 → 真实震荡
            result['is_true_oscillation'] = True
            result['reason'] = f"无效震荡（净下降 {net_improvement:.2f}）"
            result['warning'] = f"分数序列: {recent_scores}, 无实质性改善"
            return result

        # 边缘情况：净改善接近0
        if abs(net_improvement) < self.MIN_IMPROVEMENT_THRESHOLD:
            # 检查改善和下降的幅度是否都微小
            if total_improvement < self.MIN_IMPROVEMENT_THRESHOLD and total_decline < self.MIN_IMPROVEMENT_THRESHOLD:
                result['is_true_oscillation'] = True
                result['reason'] = f"微小幅度震荡（改善={total_improvement:.2f}, 下降={total_decline:.2f})"
                result['warning'] = f"分数变化幅度过小，无实质性进展"

        return result

    def _is_dimension_expansion_round(self, round_index: int) -> bool:
        """
        V7.1 判断某轮是否为维度扩展轮

        Args:
            round_index: 轮次索引

        Returns:
            bool: 是否为维度扩展轮
        """
        if round_index < 0 or round_index >= len(self.dimension_history):
            return False

        if round_index == 0:
            return False  # 第一轮是基准

        prev_dims = self.dimension_history[round_index - 1] if round_index > 0 else set()
        curr_dims = self.dimension_history[round_index]

        # 如果当前轮新增了维度
        new_dims = curr_dims - prev_dims
        return len(new_dims) > 0

    # ==================== V7.1: 维度逃逸检测 ====================

    def _detect_dimension_escape(
        self,
        current_dims: Set[str],
        previous_dims: Set[str],
        new_dims: Set[str]
    ) -> Dict:
        """
        V7.1 维度逃逸检测

        检测红方是否在改变攻击策略而非扩展维度：
        1. 语义重命名：同一攻击意图换名（如 data_leakage → privacy_leak）
        2. 无关扩展：新增维度与假设内容无关
        3. 快速突变：短时间内维度剧变
        4. 策略变更：改变攻击核心方向

        Args:
            current_dims: 当前维度集合
            previous_dims: 上一轮维度集合
            new_dims: 新增维度集合

        Returns:
            Dict: {'detected': bool, 'escape_type': str, 'details': str}
        """
        result = {
            'detected': False,
            'escape_type': '',
            'details': ''
        }

        # 检测 1: 语义重命名（等价维度检测）
        for new_dim in new_dims:
            for canonical_dim, equivalents in DIMENSION_SEMANTIC_EQUIVALENCE.items():
                # 检查新维度是否是某已知维度的等价表述
                if new_dim in equivalents:
                    # 检查该标准维度是否已在历史中出现过
                    for hist_dims in self.dimension_history[:-1]:  # 排除当前轮
                        if canonical_dim in hist_dims or any(eq in hist_dims for eq in equivalents):
                            result['detected'] = True
                            result['escape_type'] = DimensionEscapeType.SEMANTIC_RENAME.value
                            result['details'] = f"语义重命名: {new_dim} 是 {canonical_dim} 的等价表述"
                            logger.warning(f"[V7.1 CDE] 语义重命名检测: {new_dim} ≈ {canonical_dim}")
                            return result

        # 检测 2: 快速突变（维度剧烈变化）
        if previous_dims and len(previous_dims) > 0:
            # 计算维度变化率
            removed_dims = previous_dims - current_dims
            change_rate = (len(new_dims) + len(removed_dims)) / max(len(previous_dims), 1)

            # 如果变化率超过 50%（半数维度被替换），触发突变检测
            if change_rate > 0.5:
                result['detected'] = True
                result['escape_type'] = DimensionEscapeType.RAPID_MUTATION.value
                result['details'] = f"维度突变: 变化率 {change_rate:.1%}, 新增{len(new_dims)}, 移除{len(removed_dims)}"
                logger.warning(f"[V7.1 CDE] 维度突变检测: 变化率={change_rate:.1%}")
                return result

        # 检测 3: 策略变更（核心维度完全改变）
        if previous_dims and len(previous_dims) > 0:
            # 检查是否保留核心维度
            core_dims_preserved = len(current_dims & previous_dims) > 0

            if not core_dims_preserved and len(current_dims) > 0:
                # 所有上一轮维度被移除，完全新的维度集
                result['detected'] = True
                result['escape_type'] = DimensionEscapeType.STRATEGY_CHANGE.value
                result['details'] = f"策略变更: 完全替换攻击维度集 ({previous_dims} → {current_dims})"
                logger.warning(f"[V7.1 CDE] 策略变更检测: 维度集完全替换")
                return result

        # 检测 4: 无关扩展（新增维度不在合理映射中）
        # 注：此检测需要假设文本内容，此处仅做基础检查
        suspicious_new_dims = []
        for new_dim in new_dims:
            # 检查新维度是否有对应的合理映射
            if new_dim not in VALID_DIMENSION_CONTEXT_MAPPING:
                # 未知维度 → 可能是无关扩展
                suspicious_new_dims.append(new_dim)

        if len(suspicious_new_dims) > 0:
            # 不直接熔断，记录警告
            logger.warning(
                f"[V7.1 CDE] 潜在无关扩展: {suspicious_new_dims}\n"
                f"  建议: 验证这些维度是否与假设内容相关"
            )
            # 不设置 detected=True，仅警告

        return result

    def get_locked_dimensions(self) -> Optional[Set[str]]:
        """
        获取锁定的攻击维度

        红方应在锁定维度范围内进行后续评审

        Returns:
            Set[str]: 锁定的维度集合
        """
        return self._initial_dimensions

    def get_statistics(self) -> Dict:
        """
        获取收敛检测统计

        Returns:
            Dict: 统计信息
        """
        elapsed = datetime.now() - self.start_time

        return {
            'iteration_count': self.iteration_count,
            'elapsed_seconds': elapsed.total_seconds(),
            'score_history': self.score_history,
            'current_score': self.score_history[-1] if self.score_history else 0,
            'max_score': max(self.score_history) if self.score_history else 0,
            'min_score': min(self.score_history) if self.score_history else 0,
            'avg_improvement': sum(self.score_history[i+1] - self.score_history[i]
                                   for i in range(len(self.score_history) - 1)) / max(1, len(self.score_history) - 1),
            'dimension_expansion_count': self._dimension_expansion_count,
            'trend': self._calculate_trend()
        }

    def reset(self):
        """重置检测器"""
        self.score_history = []
        self.dimension_history = []
        self.iteration_count = 0
        self._initial_dimensions = None
        self._dimension_expansion_count = 0
        self.start_time = datetime.now()
        logger.info("[ConvergenceDetector V7.0] 已重置")

    def should_terminate(self) -> Tuple[bool, str]:
        """
        快速判断是否应终止迭代

        Returns:
            Tuple[bool, str]: (是否终止, 原因)
        """
        if self.iteration_count >= self.MAX_ITERATIONS:
            return True, f"达到最大迭代次数 {self.MAX_ITERATIONS}"

        if len(self.score_history) >= 2:
            improvement = self.score_history[-1] - self.score_history[-2]
            if improvement < self.MIN_IMPROVEMENT_THRESHOLD:
                return True, f"无实质改善 (提升 {improvement:.2f})"

        if self._dimension_expansion_count > self.MAX_DIMENSION_EXPANSION:
            return True, f"维度过度扩展 {self._dimension_expansion_count}"

        return False, ""


# ==================== 全局实例 ====================

_convergence_detector: Optional[ConvergenceDetector] = None


def get_convergence_detector(config: Dict = None) -> ConvergenceDetector:
    """
    获取收敛检测器实例

    Args:
        config: 配置参数

    Returns:
        ConvergenceDetector: 检测器实例
    """
    global _convergence_detector

    if _convergence_detector is None:
        _convergence_detector = ConvergenceDetector(config=config)

    return _convergence_detector


def reset_convergence_detector():
    """重置收敛检测器"""
    global _convergence_detector
    if _convergence_detector is not None:
        _convergence_detector.reset()


# ==================== 测试代码 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V7.0 收敛性检测器 - 测试")
    print("=" * 70)

    detector = ConvergenceDetector()

    # 测试 1: 正常改善
    print("\n[Test 1] 正常改善检测")
    scores = [6.0, 6.5, 7.0, 7.5]
    dims = [['data_leakage'], ['data_leakage'], ['data_leakage'], ['data_leakage']]
    for i, (score, dim) in enumerate(zip(scores, dims)):
        result = detector.check_convergence(score, dim)
        print(f"  轮次 {i+1}: score={score}, state={result.state.value}, continue={result.should_continue}")

    detector.reset()

    # 测试 2: 无改善检测
    print("\n[Test 2] 无改善检测")
    scores = [7.0, 7.1, 7.2]
    dims = [['data_leakage'], ['data_leakage'], ['data_leakage']]
    for i, (score, dim) in enumerate(zip(scores, dims)):
        result = detector.check_convergence(score, dim)
        print(f"  轮次 {i+1}: score={score}, improvement={result.improvement:.2f}, state={result.state.value}")

    detector.reset()

    # 测试 3: 维度扩展检测
    print("\n[Test 3] 维度扩展检测")
    scores = [6.0, 6.5, 7.0]
    dims = [['data_leakage'], ['data_leakage', 'endogeneity'], ['data_leakage', 'endogeneity', 'multiple_testing']]
    for i, (score, dim) in enumerate(zip(scores, dims)):
        result = detector.check_convergence(score, dim)
        print(f"  轮次 {i+1}: dims={len(dim)}, expansion={detector._dimension_expansion_count}, state={result.state.value}")

    detector.reset()

    # 测试 4: 震荡检测
    print("\n[Test 4] 震荡检测")
    scores = [7.0, 6.0, 7.0, 6.0]
    dims = [['data_leakage'], ['data_leakage'], ['data_leakage'], ['data_leakage']]
    for i, (score, dim) in enumerate(zip(scores, dims)):
        result = detector.check_convergence(score, dim)
        print(f"  轮次 {i+1}: score={score}, state={result.state.value}")

    detector.reset()

    # 测试 5: 统计信息
    print("\n[Test 5] 统计信息")
    for i in range(3):
        detector.check_convergence(7.0 + i * 0.5, ['data_leakage'])

    stats = detector.get_statistics()
    print(f"  迭代次数: {stats['iteration_count']}")
    print(f"  分数历史: {stats['score_history']}")
    print(f"  趋势: {stats['trend']:.3f}")

    print("\n" + "=" * 70)
    print("V7.0 收敛性检测器测试完成!")
    print("=" * 70)