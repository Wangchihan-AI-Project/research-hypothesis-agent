# -*- coding: utf-8 -*-
"""
V7.5 分数趋势检测器 (Score Trend Detector)

核心功能：
1. Science Score 趋势分析
2. 停滞检测（触发外部补偿）
3. 分数上升/下降判断
4. 推荐动作生成

设计理念：
- 每轮迭代 Science Score 必须上升
- 连续停滞触发外部算法补偿
- 分数下降发出警告

作者: V7.5 架构工程师
日期: 2026-04-19
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


# ==================== 趋势检测配置 ====================

TREND_CONFIG = {
    'stagnant_threshold': 0.3,      # 增长小于 0.3 视为停滞
    'stagnant_count_trigger': 2,    # 连续 2 次停滞触发补偿
    'min_rise_delta': 0.5,          # 每轮最少上升 0.5 分
    'decline_warning_threshold': -0.3,  # 下降超过 0.3 触发警告
    'window_size': 3,               # 趋势检测窗口大小
    'min_history_size': 2,          # 最少历史记录数
}


# ==================== 趋势分析结果数据类 ====================

@dataclass
class ScoreTrendAnalysis:
    """
    分数趋势分析结果

    Attributes:
        is_rising: 是否上升
        is_stagnant: 是否停滞
        is_declining: 是否下降
        trend_direction: 趋势方向字符串
        slope: 趋势斜率
        consecutive_stagnant_count: 连续停滞次数
        rise_delta: 最新上升幅度
        recommendation: 推荐动作
        should_trigger_compensation: 是否应触发外部补偿
        score_history: 分数历史
    """
    is_rising: bool
    is_stagnant: bool
    is_declining: bool
    trend_direction: str
    slope: float
    consecutive_stagnant_count: int
    rise_delta: float
    recommendation: str
    should_trigger_compensation: bool
    score_history: List[float]

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'is_rising': self.is_rising,
            'is_stagnant': self.is_stagnant,
            'is_declining': self.is_declining,
            'trend_direction': self.trend_direction,
            'slope': self.slope,
            'consecutive_stagnant_count': self.consecutive_stagnant_count,
            'rise_delta': self.rise_delta,
            'recommendation': self.recommendation,
            'should_trigger_compensation': self.should_trigger_compensation,
        }


# ==================== 分数趋势检测器类 ====================

class ScoreTrendDetector:
    """
    分数趋势检测器

    核心方法：
    1. analyze_trend - 分析分数趋势
    2. check_should_compensate - 检查是否需要补偿
    3. get_trend_summary - 获取趋势摘要
    """

    def __init__(self, config: Dict = None):
        """
        初始化趋势检测器

        Args:
            config: 配置字典（可选）
        """
        self.config = config or TREND_CONFIG.copy()
        self.score_history: List[float] = []
        self.compensation_history: List[Dict] = []

        logger.info("[V7.5] ScoreTrendDetector 初始化完成")

    def analyze_trend(self, score_history: List[float] = None) -> ScoreTrendAnalysis:
        """
        分析分数趋势

        Args:
            score_history: 分数历史列表（可选，默认使用内部历史）

        Returns:
            ScoreTrendAnalysis: 趋势分析结果
        """
        # 使用传入的历史或内部历史
        if score_history is None:
            score_history = self.score_history

        # 记录分数历史
        if score_history and score_history != self.score_history:
            self.score_history = score_history.copy()

        # 检查历史长度
        if len(score_history) < self.config['min_history_size']:
            return ScoreTrendAnalysis(
                is_rising=False,
                is_stagnant=False,
                is_declining=False,
                trend_direction="unknown",
                slope=0.0,
                consecutive_stagnant_count=0,
                rise_delta=0.0,
                recommendation="继续观察（历史数据不足）",
                should_trigger_compensation=False,
                score_history=score_history
            )

        # 计算最新增量
        latest_delta = score_history[-1] - score_history[-2]

        # 计算趋势斜率（线性回归）
        slope = self._calculate_slope(score_history)

        # 判断趋势方向
        is_stagnant = abs(latest_delta) < self.config['stagnant_threshold']
        is_rising = latest_delta >= self.config['min_rise_delta']
        is_declining = latest_delta < self.config['decline_warning_threshold']

        # 计算连续停滞次数
        consecutive_stagnant = self._count_consecutive_stagnant(score_history)

        # 判断是否触发外部补偿
        should_trigger_compensation = consecutive_stagnant >= self.config['stagnant_count_trigger']

        # 确定趋势方向字符串
        if is_rising:
            trend_direction = "rising"
        elif is_declining:
            trend_direction = "declining"
        elif is_stagnant:
            trend_direction = "stagnant"
        else:
            trend_direction = "stable"

        # 生成推荐动作
        recommendation = self._generate_recommendation(
            is_rising, is_stagnant, is_declining,
            consecutive_stagnant, should_trigger_compensation
        )

        return ScoreTrendAnalysis(
            is_rising=is_rising,
            is_stagnant=is_stagnant,
            is_declining=is_declining,
            trend_direction=trend_direction,
            slope=slope,
            consecutive_stagnant_count=consecutive_stagnant,
            rise_delta=latest_delta,
            recommendation=recommendation,
            should_trigger_compensation=should_trigger_compensation,
            score_history=score_history
        )

    def record_score(self, score: float) -> ScoreTrendAnalysis:
        """
        记录分数并分析趋势

        Args:
            score: 当前分数

        Returns:
            ScoreTrendAnalysis: 趋势分析结果
        """
        self.score_history.append(score)
        return self.analyze_trend()

    def check_should_compensate(self, score_history: List[float] = None) -> Tuple[bool, Dict]:
        """
        检查是否需要触发外部补偿

        Args:
            score_history: 分数历史列表（可选）

        Returns:
            Tuple[bool, Dict]: (是否需要补偿, 补偿配置)
        """
        analysis = self.analyze_trend(score_history)

        if analysis.should_trigger_compensation:
            # 记录补偿触发
            compensation_config = {
                'trigger_reason': 'score_stagnant',
                'stagnant_count': analysis.consecutive_stagnant_count,
                'last_score': self.score_history[-1] if self.score_history else 0.0,
                'target_score_increase': 1.0,  # 目标增加 1 分
                'slope': analysis.slope,
                'timestamp': datetime.now().isoformat() if 'datetime' in globals() else ''
            }

            self.compensation_history.append(compensation_config)

            return True, compensation_config

        return False, {}

    def get_trend_summary(self) -> Dict:
        """
        获取趋势摘要

        Returns:
            Dict: 趋势摘要字典
        """
        analysis = self.analyze_trend()

        return {
            'current_direction': analysis.trend_direction,
            'slope': analysis.slope,
            'latest_delta': analysis.rise_delta,
            'stagnant_count': analysis.consecutive_stagnant_count,
            'compensation_triggered': analysis.should_trigger_compensation,
            'score_history': self.score_history,
            'compensation_history': self.compensation_history,
        }

    def _calculate_slope(self, score_history: List[float]) -> float:
        """
        计算趋势斜率（线性回归）

        Args:
            score_history: 分数历史列表

        Returns:
            float: 趋势斜率
        """
        if len(score_history) < 2:
            return 0.0

        # 使用最近窗口计算斜率
        window_size = min(self.config['window_size'], len(score_history))
        window = score_history[-window_size:]

        x = np.arange(len(window))

        try:
            slope, _ = np.polyfit(x, window, 1)
            return float(slope)
        except (np.linalg.LinAlgError, ValueError):
            return window[-1] - window[0] if len(window) >= 2 else 0.0

    def _count_consecutive_stagnant(self, score_history: List[float]) -> int:
        """
        计算连续停滞次数

        Args:
            score_history: 分数历史列表

        Returns:
            int: 连续停滞次数
        """
        if len(score_history) < 2:
            return 0

        count = 0
        threshold = self.config['stagnant_threshold']

        # 从最近开始计数
        for i in range(len(score_history) - 1, 0, -1):
            delta = score_history[i] - score_history[i - 1]
            if abs(delta) < threshold:
                count += 1
            else:
                break

        return count

    def _generate_recommendation(
        self,
        is_rising: bool,
        is_stagnant: bool,
        is_declining: bool,
        stagnant_count: int,
        should_compensate: bool
    ) -> str:
        """
        生成推荐动作

        Args:
            is_rising: 是否上升
            is_stagnant: 是否停滞
            is_declining: 是否下降
            stagnant_count: 连续停滞次数
            should_compensate: 是否需要补偿

        Returns:
            str: 推荐动作字符串
        """
        if should_compensate:
            return "🔥 触发外部算法补偿：调用 SearchSupplementAgent 获取方法论补丁"

        if is_declining:
            return "⚠️ 分数下降警告：检查蓝方修改是否正确引入新的问题"

        if is_rising:
            return "✅ 分数上升正常，继续迭代演化"

        if is_stagnant:
            if stagnant_count >= 1:
                return f"📊 分数停滞（连续 {stagnant_count} 次）：观察下一轮，可能即将触发补偿"
            else:
                return "📊 分数停滞：继续观察"

        return "➡️ 分数稳定：继续迭代"


# ==================== 导入时间模块 ====================
from datetime import datetime
from typing import Tuple


# ==================== 辅助函数 ====================

def create_trend_detector(config: Dict = None) -> ScoreTrendDetector:
    """
    创建趋势检测器实例

    Args:
        config: 配置字典（可选）

    Returns:
        ScoreTrendDetector: 趋势检测器实例
    """
    return ScoreTrendDetector(config)


def analyze_score_history(score_history: List[float], config: Dict = None) -> ScoreTrendAnalysis:
    """
    分析分数历史（便捷函数）

    Args:
        score_history: 分数历史列表
        config: 配置字典（可选）

    Returns:
        ScoreTrendAnalysis: 趋势分析结果
    """
    detector = ScoreTrendDetector(config)
    return detector.analyze_trend(score_history)


def should_trigger_compensation(score_history: List[float]) -> bool:
    """
    判断是否应触发外部补偿（便捷函数）

    Args:
        score_history: 分数历史列表

    Returns:
        bool: 是否应触发补偿
    """
    detector = ScoreTrendDetector()
    analysis = detector.analyze_trend(score_history)
    return analysis.should_trigger_compensation


# ==================== 导出 ====================

__all__ = [
    'ScoreTrendDetector',
    'ScoreTrendAnalysis',
    'TREND_CONFIG',
    'create_trend_detector',
    'analyze_score_history',
    'should_trigger_compensation',
]