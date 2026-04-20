# -*- coding: utf-8 -*-
"""
V7.5 Promise Score 计算模块 (Promise Score Calculator)

核心功能：
1. Promise Score 综合评分计算
2. 四维度评分分解
3. 演化增量计算
4. 前景趋势判断

设计理念：
- Promise Score = 创新性(30%) + 可行性(35%) + 前沿契合度(25%) + 证据强度(10%)
- 展示最终方案的综合前景评分
- 与 Science Score 独立但互补

作者: V7.5 架构工程师
日期: 2026-04-19
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ==================== Promise Score 配置 ====================

PROMISE_SCORE_CONFIG = {
    'weights': {
        'innovation': 0.30,          # 创新性权重
        'feasibility': 0.35,        # 可行性权重
        'frontier_alignment': 0.25, # 前沿契合度权重
        'evidence_strength': 0.10,  # 证据强度权重
    },
    'thresholds': {
        'excellent': 9.0,           # 优秀阈值
        'good': 8.0,                # 良好阈值
        'acceptable': 7.0,          # 可接受阈值
        'poor': 6.0,                # 较差阈值
    },
}


# ==================== Promise Score 结果数据类 ====================

@dataclass
class PromiseScoreResult:
    """
    Promise Score 评分结果

    Attributes:
        total_score: 总分 (0-10)
        components: 四维度评分字典
        trend: 趋势方向
        evolution_delta: 演化增量
        grade: 评级 (excellent, good, acceptable, poor)
        recommendation: 推荐建议
    """
    total_score: float
    components: Dict = field(default_factory=dict)
    trend: str = "unknown"
    evolution_delta: float = 0.0
    grade: str = "ungraded"
    recommendation: str = ""

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'total_score': self.total_score,
            'components': self.components,
            'trend': self.trend,
            'evolution_delta': self.evolution_delta,
            'grade': self.grade,
            'recommendation': self.recommendation,
        }


# ==================== Promise Score 计算器类 ====================

class PromiseScoreCalculator:
    """
    Promise Score 计算器

    核心方法：
    1. calculate - 计算 Promise Score
    2. get_grade - 获取评级
    3. generate_recommendation - 生成推荐建议
    """

    def __init__(self, config: Dict = None):
        """
        初始化计算器

        Args:
            config: 配置字典（可选）
        """
        self.config = config or PROMISE_SCORE_CONFIG.copy()
        logger.info("[V7.5] PromiseScoreCalculator 初始化完成")

    def calculate(
        self,
        hypothesis_result: Dict,
        fitness_result: Dict,
        verified_ids: Dict,
        version_chain: List[Dict]
    ) -> PromiseScoreResult:
        """
        计算 Promise Score

        Args:
            hypothesis_result: 假设结果字典
            fitness_result: 适应度结果字典
            verified_ids: 验证 ID 字典（包含 pmids 等）
            version_chain: 版本演进链

        Returns:
            PromiseScoreResult: Promise Score 结果
        """
        components = {}
        total = 0.0

        # 1. 创新性评分 (30%)
        innovation_score = self._calculate_innovation(hypothesis_result, fitness_result)
        components['innovation'] = {
            'score': innovation_score,
            'weight': self.config['weights']['innovation'],
            'description': '创新性',
            'details': self._get_innovation_details(hypothesis_result, fitness_result)
        }
        total += innovation_score * self.config['weights']['innovation']

        # 2. 可行性评分 (35%)
        feasibility_score = self._calculate_feasibility(fitness_result, hypothesis_result)
        components['feasibility'] = {
            'score': feasibility_score,
            'weight': self.config['weights']['feasibility'],
            'description': '可行性',
            'details': self._get_feasibility_details(fitness_result)
        }
        total += feasibility_score * self.config['weights']['feasibility']

        # 3. 前沿契合度评分 (25%)
        frontier_score = self._calculate_frontier_alignment(hypothesis_result, verified_ids)
        components['frontier_alignment'] = {
            'score': frontier_score,
            'weight': self.config['weights']['frontier_alignment'],
            'description': '前沿契合度',
            'details': self._get_frontier_details(hypothesis_result, verified_ids)
        }
        total += frontier_score * self.config['weights']['frontier_alignment']

        # 4. 证据强度评分 (10%)
        evidence_score = self._calculate_evidence_strength(verified_ids)
        components['evidence_strength'] = {
            'score': evidence_score,
            'weight': self.config['weights']['evidence_strength'],
            'description': '证据强度',
            'details': self._get_evidence_details(verified_ids)
        }
        total += evidence_score * self.config['weights']['evidence_strength']

        # 计算演化增量
        evolution_delta = self._calculate_evolution_delta(version_chain)

        # 判断趋势
        trend = self._determine_trend(evolution_delta, version_chain)

        # 获取评级
        grade = self.get_grade(total)

        # 生成推荐
        recommendation = self.generate_recommendation(total, grade, trend)

        return PromiseScoreResult(
            total_score=round(total, 2),
            components=components,
            trend=trend,
            evolution_delta=evolution_delta,
            grade=grade,
            recommendation=recommendation
        )

    def _calculate_innovation(self, hypothesis_result: Dict, fitness_result: Dict) -> float:
        """
        计算创新性评分

        Args:
            hypothesis_result: 假设结果字典
            fitness_result: 适应度结果字典

        Returns:
            float: 创新性评分
        """
        # 向量创新分
        vector_score = fitness_result.get('vector_novelty_score', 7.5)

        # 方法论创新分
        methodology_score = hypothesis_result.get('scores', {}).get('novelty', 7.5)

        # 加权平均
        innovation = vector_score * 0.6 + methodology_score * 0.4

        return min(10.0, max(0.0, innovation))

    def _calculate_feasibility(self, fitness_result: Dict, hypothesis_result: Dict) -> float:
        """
        计算可行性评分

        Args:
            fitness_result: 适应度结果字典
            hypothesis_result: 假设结果字典

        Returns:
            float: 可行性评分
        """
        # 物理可行性分
        physical_score = fitness_result.get('physical_validation', {}).get('score', 7.5)

        # 实现复杂度（越低越好）
        complexity = hypothesis_result.get('implementation_complexity', 'medium')
        complexity_score = {
            'low': 9.0,
            'medium': 7.5,
            'high': 5.0,
        }.get(complexity, 7.5)

        # 加权平均
        feasibility = physical_score * 0.7 + complexity_score * 0.3

        return min(10.0, max(0.0, feasibility))

    def _calculate_frontier_alignment(self, hypothesis_result: Dict, verified_ids: Dict) -> float:
        """
        计算前沿契合度评分

        Args:
            hypothesis_result: 假设结果字典
            verified_ids: 验证 ID 字典

        Returns:
            float: 前沿契合度评分
        """
        # 年份评分（2024+ 为高分）
        year = hypothesis_result.get('year', 2025)
        if year >= 2025:
            year_score = 9.0
        elif year >= 2024:
            year_score = 8.0
        elif year >= 2023:
            year_score = 7.0
        else:
            year_score = 6.0

        # 引用速度评分
        velocity = hypothesis_result.get('citation_velocity', 'normal')
        velocity_score = {
            'Top 5%': 9.5,
            'Top 10%': 8.5,
            'Top 20%': 7.5,
            'normal': 7.0,
        }.get(velocity, 7.0)

        # 加权平均
        frontier = year_score * 0.5 + velocity_score * 0.5

        return min(10.0, max(0.0, frontier))

    def _calculate_evidence_strength(self, verified_ids: Dict) -> float:
        """
        计算证据强度评分

        Args:
            verified_ids: 验证 ID 字典

        Returns:
            float: 证据强度评分
        """
        # PMID 数量
        pmid_count = len(verified_ids.get('pmids', []))

        # arXiv 数量
        arxiv_count = len(verified_ids.get('arxiv_ids', []))

        # 总证据数量
        total_evidence = pmid_count + arxiv_count

        # 计算评分（每篇 0.5 分，最高 10 分）
        evidence_score = min(10.0, total_evidence * 0.5)

        # 确保最低评分
        if total_evidence >= 5:
            evidence_score = max(7.0, evidence_score)

        return evidence_score

    def _calculate_evolution_delta(self, version_chain: List[Dict]) -> float:
        """
        计算演化增量

        Args:
            version_chain: 版本演进链

        Returns:
            float: 演化增量
        """
        if len(version_chain) < 2:
            return 0.0

        # 获取第一个版本和最后一个版本的分数
        first_score = version_chain[0].get('science_score', 0.0)
        last_score = version_chain[-1].get('science_score', 0.0)

        return last_score - first_score

    def _determine_trend(self, evolution_delta: float, version_chain: List[Dict]) -> str:
        """
        判断趋势

        Args:
            evolution_delta: 演化增量
            version_chain: 版本演进链

        Returns:
            str: 趋势字符串
        """
        if evolution_delta > 1.5:
            return "strong_rising"
        elif evolution_delta > 0.5:
            return "rising"
        elif evolution_delta > 0:
            return "stable_rising"
        elif evolution_delta == 0:
            return "stagnant"
        else:
            return "declining"

    def get_grade(self, score: float) -> str:
        """
        获取评级

        Args:
            score: 总分

        Returns:
            str: 评级字符串
        """
        thresholds = self.config['thresholds']

        if score >= thresholds['excellent']:
            return "excellent"
        elif score >= thresholds['good']:
            return "good"
        elif score >= thresholds['acceptable']:
            return "acceptable"
        elif score >= thresholds['poor']:
            return "poor"
        else:
            return "very_poor"

    def generate_recommendation(
        self,
        score: float,
        grade: str,
        trend: str
    ) -> str:
        """
        生成推荐建议

        Args:
            score: 总分
            grade: 评级
            trend: 趋势

        Returns:
            str: 推荐建议字符串
        """
        grade_messages = {
            'excellent': "方案前景极佳，建议直接进入实验验证阶段",
            'good': "方案前景良好，可进行小规模预实验后推进",
            'acceptable': "方案前景可接受，建议进一步优化方法论细节",
            'poor': "方案前景较差，需要重新评估研究方向",
            'very_poor': "方案前景不足，建议考虑转向其他研究方向",
        }

        trend_messages = {
            'strong_rising': "演化效果显著，分数大幅提升",
            'rising': "演化效果良好，分数稳步提升",
            'stable_rising': "演化效果稳定，分数小幅提升",
            'stagnant': "演化停滞，分数无明显变化",
            'declining': "演化���常，分数下降需要检查",
        }

        return f"{grade_messages.get(grade, '未知评级')}。{trend_messages.get(trend, '未知趋势')}"

    def _get_innovation_details(self, hypothesis_result: Dict, fitness_result: Dict) -> str:
        """获取创新性细节"""
        vector_score = fitness_result.get('vector_novelty_score', 7.5)
        methodology_score = hypothesis_result.get('scores', {}).get('novelty', 7.5)
        return f"向量创新分: {vector_score:.1f}, 方法论创新分: {methodology_score:.1f}"

    def _get_feasibility_details(self, fitness_result: Dict) -> str:
        """获取可行性细节"""
        physical_score = fitness_result.get('physical_validation', {}).get('score', 7.5)
        return f"物理可行性分: {physical_score:.1f}"

    def _get_frontier_details(self, hypothesis_result: Dict, verified_ids: Dict) -> str:
        """获取前沿契合度细节"""
        year = hypothesis_result.get('year', 2025)
        velocity = hypothesis_result.get('citation_velocity', 'normal')
        return f"年份: {year}, 引用速度: {velocity}"

    def _get_evidence_details(self, verified_ids: Dict) -> str:
        """获取证据强度细节"""
        pmid_count = len(verified_ids.get('pmids', []))
        arxiv_count = len(verified_ids.get('arxiv_ids', []))
        return f"PMID 数量: {pmid_count}, arXiv 数量: {arxiv_count}"


# ==================== 辅助函数 ====================

def calculate_promise_score(
    hypothesis_result: Dict,
    fitness_result: Dict,
    verified_ids: Dict,
    version_chain: List[Dict]
) -> PromiseScoreResult:
    """
    计算 Promise Score（便捷函数）

    Args:
        hypothesis_result: 假设结果字典
        fitness_result: 适应度结果字典
        verified_ids: 验证 ID 字典
        version_chain: 版本演进链

    Returns:
        PromiseScoreResult: Promise Score 结果
    """
    calculator = PromiseScoreCalculator()
    return calculator.calculate(hypothesis_result, fitness_result, verified_ids, version_chain)


def format_promise_score_for_display(result: PromiseScoreResult) -> str:
    """
    格式化 Promise Score 用于显示

    Args:
        result: Promise Score 结果

    Returns:
        str: 格式化后的显示文本
    """
    grade_icons = {
        'excellent': '🌟',
        'good': '✨',
        'acceptable': '📊',
        'poor': '⚠️',
        'very_poor': '❌',
    }

    trend_icons = {
        'strong_rising': '📈',
        'rising': '↗️',
        'stable_rising': '➡️',
        'stagnant': '📊',
        'declining': '📉',
    }

    grade_icon = grade_icons.get(result.grade, '📊')
    trend_icon = trend_icons.get(result.trend, '➡️')

    display_text = f"""
### {grade_icon} Promise Score: {result.total_score:.1f}/10

**评级**: {result.grade}
**趋势**: {trend_icon} {result.trend}
**演化增量**: +{result.evolution_delta:.1f}

#### 四维度评分

| 维度 | 分数 | 权重 | 详情 |
|------|------|------|------|
| 创新性 | {result.components['innovation']['score']:.1f} | {result.components['innovation']['weight']:.0%} | {result.components['innovation']['details']} |
| 可行性 | {result.components['feasibility']['score']:.1f} | {result.components['feasibility']['weight']:.0%} | {result.components['feasibility']['details']} |
| 前沿契合度 | {result.components['frontier_alignment']['score']:.1f} | {result.components['frontier_alignment']['weight']:.0%} | {result.components['frontier_alignment']['details']} |
| 证据强度 | {result.components['evidence_strength']['score']:.1f} | {result.components['evidence_strength']['weight']:.0%} | {result.components['evidence_strength']['details']} |

**推荐**: {result.recommendation}
"""

    return display_text.strip()


# ==================== 导出 ====================

__all__ = [
    'PromiseScoreCalculator',
    'PromiseScoreResult',
    'PROMISE_SCORE_CONFIG',
    'calculate_promise_score',
    'format_promise_score_for_display',
]