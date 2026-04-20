# -*- coding: utf-8 -*-
"""
V7.5 凤凰协议状态机 (Phoenix Protocol State Machine)

核心功能：
1. 从"阻断型"逻辑重构为"演化型"逻辑
2. 物理公理冲突不拦截，触发重写
3. Science Score 趋势检测，停滞触发补偿
4. 最大迭代次数 8 次（比当前 4 次多一倍）

状态转换矩阵：
INITIAL → HYPOTHESIS_GEN → [PHOENIX_REWRITE] → PHOENIX_RETRY → [PHOENIX_PATCH] → SUCCESS

作者: V7.5 架构工程师
日期: 2026-04-19
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# ==================== 凤凰协议配置 ====================

PHOENIX_CONFIG = {
    'MAX_PHOENIX_ITERATIONS': 8,        # 最大演化迭代次数
    'MAX_REWRITE_ATTEMPTS': 3,          # 物理锚定重写最多 3 次
    'MAX_PATCH_ATTEMPTS': 5,            # 方法论补丁最多 5 次
    'SCORE_STagnant_THRESHOLD': 2,      # 连续 2 次停滞触发补偿
    'SCORE_RISE_MIN_DELTA': 0.5,        # 每轮最少上升 0.5 分
    'MIN_SUCCESS_SCORE': 8.5,           # 成功最低分数阈值
    'COMPENSATION_SEARCH_DEPTH': 3,     # 外部补偿检索深度
}


# ==================== 凤凰协议状态枚举 ====================

class PhoenixState(Enum):
    """凤凰协议状态枚举"""
    # 初始状态
    INITIAL = auto()                    # 初始输入

    # 正常流程状态
    HYPOTHESIS_GEN = auto()             # PI 假设生成
    RED_ATTACK = auto()                 # 红方攻击
    BLUE_DEFENSE = auto()               # 蓝方答辩

    # 凤凰演化状态（核心创新）
    PHOENIX_REWRITE = auto()            # 物理锚定重写（替代伪科学拦截）
    PHOENIX_PATCH = auto()              # 方法论补丁注入
    PHOENIX_RETRY = auto()              # 补丁后重试

    # 中间状态
    SCORE_STagnant = auto()             # 分数停滞（触发外部补偿）
    EXTERNAL_COMPENSATION = auto()      # 外部算法补偿进行中

    # 终态
    SUCCESS = auto()                    # 最终成功
    HARD_FAILURE = auto()               # 硬性失败（物理不可修复）
    MAX_PHOENIX_EXCEEDED = auto()       # 超过凤凰演化上限


class PhoenixTransitionTrigger(Enum):
    """状态转换触发器"""
    # 正常流程触发器
    HYPOTHESIS_READY = auto()           # 假设生成完成
    RED_ATTACK_START = auto()           # 红方攻击开始
    BLUE_DEFENSE_START = auto()         # 蓝方答辩开始

    # 凤凰协议触发器
    PHYSICAL_AXIOM_CONFlict = auto()    # 物理公理冲突
    RED_ATTACK_FAILURE = auto()         # 红方攻击失败
    BLUE_DEFENSE_FAILURE = auto()       # 蓝方答辩失败
    SCORE_STagnant_DETECTED = auto()    # 分数停滞检测
    DEFENSE_PASSED = auto()             # 防御通过
    PATCH_APPLIED = auto()              # 补丁已应用
    REWRITE_COMPLETED = auto()          # 重写完成
    COMPENSATION_COMPLETED = auto()     # 补偿完成

    # 终态触发器
    UNRECOVERABLE_CONFLICT = auto()     # 不可恢复冲突
    MAX_ITERATIONS_EXCEEDED = auto()    # 迭代上限
    SUCCESS_THRESHOLD_REACHED = auto()  # 成功阈值


# ==================== 状态转换矩阵 ====================

PHOENIX_STATE_TRANSITIONS = {
    # 正常流程
    (PhoenixState.INITIAL, PhoenixTransitionTrigger.HYPOTHESIS_READY):
        PhoenixState.HYPOTHESIS_GEN,
    (PhoenixState.HYPOTHESIS_GEN, PhoenixTransitionTrigger.RED_ATTACK_START):
        PhoenixState.RED_ATTACK,
    (PhoenixState.RED_ATTACK, PhoenixTransitionTrigger.BLUE_DEFENSE_START):
        PhoenixState.BLUE_DEFENSE,

    # 凤凰演化核心逻辑 - 物理冲突不拦截，触发重写
    (PhoenixState.HYPOTHESIS_GEN, PhoenixTransitionTrigger.PHYSICAL_AXIOM_CONFlict):
        PhoenixState.PHOENIX_REWRITE,

    # 蓝方答辩失败 → 补丁注入
    (PhoenixState.BLUE_DEFENSE, PhoenixTransitionTrigger.BLUE_DEFENSE_FAILURE):
        PhoenixState.PHOENIX_PATCH,

    # 分数停滞 → 外部补偿
    (PhoenixState.BLUE_DEFENSE, PhoenixTransitionTrigger.SCORE_STagnant_DETECTED):
        PhoenixState.SCORE_STagnant,

    # 外部补偿完成 → 补丁注入
    (PhoenixState.EXTERNAL_COMPENSATION, PhoenixTransitionTrigger.COMPENSATION_COMPLETED):
        PhoenixState.PHOENIX_PATCH,

    # 物理重写完成 → 重试
    (PhoenixState.PHOENIX_REWRITE, PhoenixTransitionTrigger.REWRITE_COMPLETED):
        PhoenixState.PHOENIX_RETRY,

    # 补丁应用完成 → 重试
    (PhoenixState.PHOENIX_PATCH, PhoenixTransitionTrigger.PATCH_APPLIED):
        PhoenixState.PHOENIX_RETRY,

    # 重试 → 成功（防御通过）
    (PhoenixState.PHOENIX_RETRY, PhoenixTransitionTrigger.DEFENSE_PASSED):
        PhoenixState.SUCCESS,

    # 重试失败 → 继续补丁循环
    (PhoenixState.PHOENIX_RETRY, PhoenixTransitionTrigger.BLUE_DEFENSE_FAILURE):
        PhoenixState.PHOENIX_PATCH,

    # 分数停滞 → 外部补偿
    (PhoenixState.SCORE_STagnant, PhoenixTransitionTrigger.COMPENSATION_COMPLETED):
        PhoenixState.PHOENIX_PATCH,

    # 终态触发
    (PhoenixState.PHOENIX_REWRITE, PhoenixTransitionTrigger.UNRECOVERABLE_CONFLICT):
        PhoenixState.HARD_FAILURE,
    (PhoenixState.HYPOTHESIS_GEN, PhoenixTransitionTrigger.MAX_ITERATIONS_EXCEEDED):
        PhoenixState.MAX_PHOENIX_EXCEEDED,
    (PhoenixState.PHOENIX_PATCH, PhoenixTransitionTrigger.MAX_ITERATIONS_EXCEEDED):
        PhoenixState.MAX_PHOENIX_EXCEEDED,
    (PhoenixState.EXTERNAL_COMPENSATION, PhoenixTransitionTrigger.MAX_ITERATIONS_EXCEEDED):
        PhoenixState.MAX_PHOENIX_EXCEEDED,
    (PhoenixState.PHOENIX_RETRY, PhoenixTransitionTrigger.MAX_ITERATIONS_EXCEEDED):
        PhoenixState.MAX_PHOENIX_EXCEEDED,
    (PhoenixState.BLUE_DEFENSE, PhoenixTransitionTrigger.SUCCESS_THRESHOLD_REACHED):
        PhoenixState.SUCCESS,
}


# ==================== 凤凰协议上下文 ====================

@dataclass
class PhoenixContext:
    """凤凰协议执行上下文"""
    # 基本状态
    current_state: PhoenixState = PhoenixState.INITIAL
    phoenix_iterations: int = 0
    rewrite_attempts: int = 0
    patch_attempts: int = 0

    # 分数追踪
    score_history: List[float] = field(default_factory=list)
    current_science_score: float = 0.0
    stagnant_count: int = 0

    # 假设版本
    current_version: str = "v1.0"
    version_history: List[Dict] = field(default_factory=list)

    # 物理冲突信息
    physical_conflict_detected: bool = False
    alternative_paths: List[Dict] = field(default_factory=list)
    rewrite_instruction: str = ""

    # 红方攻击信息
    red_attack_types: List[str] = field(default_factory=list)
    red_attack_report: Dict = field(default_factory=dict)

    # 补丁信息
    applied_patches: List[Dict] = field(default_factory=list)
    compensation_sources: List[str] = field(default_factory=list)

    # 结果
    final_result: Optional[Dict] = None
    failure_reason: str = ""

    def can_continue(self) -> bool:
        """检查是否可以继续演化"""
        return (
            self.current_state not in [PhoenixState.SUCCESS, PhoenixState.HARD_FAILURE,
                                       PhoenixState.MAX_PHOENIX_EXCEEDED]
            and self.phoenix_iterations < PHOENIX_CONFIG['MAX_PHOENIX_ITERATIONS']
            and self.rewrite_attempts < PHOENIX_CONFIG['MAX_REWRITE_ATTEMPTS']
            and self.patch_attempts < PHOENIX_CONFIG['MAX_PATCH_ATTEMPTS']
        )

    def is_stagnant(self) -> bool:
        """检查分数是否停滞"""
        if len(self.score_history) < 2:
            return False

        # 检查最近两次分数差异
        recent_delta = self.score_history[-1] - self.score_history[-2]
        return abs(recent_delta) < PHOENIX_CONFIG['SCORE_RISE_MIN_DELTA']

    def record_score(self, score: float):
        """记录分数"""
        # 确保 score 是 Python float 类型（避免 numpy float32 序列化问题）
        import numpy as np
        if isinstance(score, (np.floating, np.float32, np.float64)):
            score = float(score)

        self.score_history.append(score)
        self.current_science_score = score

        # 更新停滞计数
        if self.is_stagnant():
            self.stagnant_count += 1
        else:
            self.stagnant_count = 0


# ==================== 凤凰协议状态机 ====================

class PhoenixStateMachine:
    """凤凰协议状态机"""

    def __init__(self):
        self.context = PhoenixContext()
        self.transition_history: List[Dict] = []

    def get_next_state(self, trigger: PhoenixTransitionTrigger) -> PhoenixState:
        """
        根据触发器获取下一状态

        Args:
            trigger: 状态转换触发器

        Returns:
            PhoenixState: 下一状态
        """
        current = self.context.current_state
        transition_key = (current, trigger)

        if transition_key in PHOENIX_STATE_TRANSITIONS:
            next_state = PHOENIX_STATE_TRANSITIONS[transition_key]
            self._record_transition(current, trigger, next_state)
            return next_state

        # 默认行为：保持当前状态
        logger.warning(f"未定义的状态转换: {current} + {trigger}")
        return current

    def transition(self, trigger: PhoenixTransitionTrigger) -> PhoenixState:
        """
        执行状态转换

        Args:
            trigger: 状态转换触发器

        Returns:
            PhoenixState: 新状态
        """
        next_state = self.get_next_state(trigger)
        previous_state = self.context.current_state
        self.context.current_state = next_state

        if previous_state != next_state:
            logger.info(f"凤凰协议状态转换: {previous_state} → {next_state} (触发器: {trigger})")
        else:
            logger.info(f"凤凰协议状态保持: {previous_state} (触发器: {trigger})")

        return next_state

    def _record_transition(self, from_state: PhoenixState, trigger: PhoenixTransitionTrigger,
                          to_state: PhoenixState):
        """记录状态转换历史"""
        self.transition_history.append({
            'from': from_state.name,
            'trigger': trigger.name,
            'to': to_state.name,
            'iteration': self.context.phoenix_iterations,
            'timestamp': self._get_timestamp()
        })

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    def should_trigger_compensation(self) -> bool:
        """
        检查是否应该触发外部补偿

        Returns:
            bool: 是否触发补偿
        """
        return self.context.stagnant_count >= PHOENIX_CONFIG['SCORE_STagnant_THRESHOLD']

    def should_trigger_rewrite(self) -> bool:
        """
        检查是否应该触发物理重写

        Returns:
            bool: 是否触发重写
        """
        return (
            self.context.physical_conflict_detected
            and self.context.rewrite_attempts < PHOENIX_CONFIG['MAX_REWRITE_ATTEMPTS']
        )

    def get_evolution_summary(self) -> Dict:
        """
        获取演化摘要

        Returns:
            Dict: 演化过程摘要
        """
        return {
            'total_iterations': self.context.phoenix_iterations,
            'rewrite_attempts': self.context.rewrite_attempts,
            'patch_attempts': self.context.patch_attempts,
            'score_evolution': self.context.score_history,
            'version_chain': self.context.version_history,
            'transition_history': self.transition_history,
            'final_state': self.context.current_state.name,
            'success': self.context.current_state == PhoenixState.SUCCESS,
        }


# ==================== 状态判断辅助函数 ====================

def is_terminal_state(state: PhoenixState) -> bool:
    """检查是否为终态"""
    return state in [PhoenixState.SUCCESS, PhoenixState.HARD_FAILURE,
                     PhoenixState.MAX_PHOENIX_EXCEEDED]


def is_evolution_state(state: PhoenixState) -> bool:
    """检查是否为演化状态"""
    return state in [PhoenixState.PHOENIX_REWRITE, PhoenixState.PHOENIX_PATCH,
                     PhoenixState.PHOENIX_RETRY, PhoenixState.SCORE_STagnant,
                     PhoenixState.EXTERNAL_COMPENSATION]


def get_state_description(state: PhoenixState) -> str:
    """获取状态描述"""
    descriptions = {
        PhoenixState.INITIAL: "初始输入阶段",
        PhoenixState.HYPOTHESIS_GEN: "PI Agent 假设生成",
        PhoenixState.RED_ATTACK: "红方攻击审计",
        PhoenixState.BLUE_DEFENSE: "蓝方答辩审查",
        PhoenixState.PHOENIX_REWRITE: "🔥 物理锚定重写（替代伪科学拦截）",
        PhoenixState.PHOENIX_PATCH: "🧬 方法论补丁注入",
        PhoenixState.PHOENIX_RETRY: "🔄 补丁后重试验证",
        PhoenixState.SCORE_STagnant: "⚠️ 分数停滞检测",
        PhoenixState.EXTERNAL_COMPENSATION: "📡 外部算法补偿检索",
        PhoenixState.SUCCESS: "✅ 最终成功",
        PhoenixState.HARD_FAILURE: "❌ 硬性失败（物理不可修复）",
        PhoenixState.MAX_PHOENIX_EXCEEDED: "⏰ 超过演化上限",
    }
    return descriptions.get(state, "未知状态")


# ==================== 导出 ====================

__all__ = [
    'PhoenixState',
    'PhoenixTransitionTrigger',
    'PhoenixContext',
    'PhoenixStateMachine',
    'PHOENIX_CONFIG',
    'PHOENIX_STATE_TRANSITIONS',
    'is_terminal_state',
    'is_evolution_state',
    'get_state_description',
]