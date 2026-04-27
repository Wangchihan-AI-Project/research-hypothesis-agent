# -*- coding: utf-8 -*-
"""
V7.5 假设版本管理器 (Hypothesis Version Manager)

核心功能：
1. 假设版本生命周期管理
2. 版本演进链追踪
3. 分数记录与更新
4. 修改历史日志

设计理念：
- 每次物理重写/方法论补丁创建新版本
- 版本号递增：v1.0 → v1.1 → v1.2 → v2.0
- 记录每个版本的分数和修改内容

作者: V7.5 架构工程师
日期: 2026-04-19
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ==================== 版本类型枚举 ====================

VERSION_TYPES = {
    'initial': '初始版本',
    'physical_fix': '物理锚定修正',
    'methodology_patch': '方法论补丁',
    'external_compensation': '外部算法补偿',
    'major_rewrite': '重大重构',
    'rollback': '回溯恢复',
    'final': '最终版本',
}


# ==================== 假设版本数据类 ====================

@dataclass
class HypothesisVersion:
    """
    假设版本记录

    Attributes:
        version_number: 版本号 (v1.0, v1.1, v1.2, ...)
        version_type: 版本类型 (initial, physical_fix, methodology_patch, ...)
        created_at: 创建时间
        hypothesis_content: 假设内容字典
        science_score: 科学评分
        fitness_score: 适应度评分
        defense_passed: 防御是否通过
        rewrite_log: 修改记录列表
        iteration_number: 对应迭代次数
        red_attack_types: 红方攻击类型
        patch_applied: 是否应用了补丁
    """
    version_number: str
    version_type: str
    created_at: str
    hypothesis_content: Dict
    science_score: float = 0.0
    fitness_score: float = 0.0
    defense_passed: bool = False
    rewrite_log: List[Dict] = field(default_factory=list)
    iteration_number: int = 0
    red_attack_types: List[str] = field(default_factory=list)
    patch_applied: bool = False

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'version': self.version_number,
            'type': self.version_type,
            'type_display': VERSION_TYPES.get(self.version_type, self.version_type),
            'created_at': self.created_at,
            'hypothesis_content': self.hypothesis_content,  # 包含完整假设内容
            'science_score': self.science_score,
            'fitness_score': self.fitness_score,
            'defense_passed': self.defense_passed,
            'rewrite_log': self.rewrite_log,
            'iteration': self.iteration_number,
            'red_attack_types': self.red_attack_types,
            'patch_applied': self.patch_applied,
        }


# ==================== 假设版本管理器类 ====================

class HypothesisVersionManager:
    """
    假设版本管理器

    核心功能：
    1. create_initial_version - 创建初始版本
    2. create_rewrite_version - 创建重写版本
    3. update_version_scores - 更新版本分数
    4. get_version_evolution_chain - 获取版本演进链
    5. get_best_version - 获取最高分版本
    """

    def __init__(self):
        """初始化版本管理器"""
        self.versions: List[HypothesisVersion] = []
        self.current_version: str = "v1.0"
        self.version_counter: int = 0
        self.major_version: int = 1
        self.minor_version: int = 0

        logger.info("[V7.5] HypothesisVersionManager 初始化完成")

    def create_initial_version(
        self,
        hypothesis: Dict,
        iteration: int = 1
    ) -> HypothesisVersion:
        """
        创建初始版本

        Args:
            hypothesis: 假设内容字典
            iteration: 迭代次数

        Returns:
            HypothesisVersion: 创建的版本对象
        """
        self.version_counter += 1
        self.major_version = 1
        self.minor_version = 0
        self.current_version = "v1.0"

        version = HypothesisVersion(
            version_number="v1.0",
            version_type="initial",
            created_at=datetime.now().isoformat(),
            hypothesis_content=hypothesis,
            science_score=0.0,
            fitness_score=0.0,
            defense_passed=False,
            rewrite_log=[],
            iteration_number=iteration,
            red_attack_types=[],
            patch_applied=False
        )

        self.versions.append(version)
        logger.info(f"[V7.5] 创建初始版本: v1.0 (iteration={iteration})")

        return version

    def create_rewrite_version(
        self,
        base_version: Optional[HypothesisVersion] = None,
        rewrite_type: str = "physical_fix",
        rewrite_log: List[Dict] = None,
        new_hypothesis: Dict = None,
        iteration: int = 0,
        red_attack_types: List[str] = None
    ) -> HypothesisVersion:
        """
        创建重写版本

        Args:
            base_version: 基础版本（可选，默认使用最新版本）
            rewrite_type: 重写类型 (physical_fix, methodology_patch, ...)
            rewrite_log: 修改记录列表
            new_hypothesis: 新假设内容字典
            iteration: 迭代次数
            red_attack_types: 红方攻击类型列表

        Returns:
            HypothesisVersion: 创建的新版本对象
        """
        # 如果未指定基础版本，使用最新版本
        if base_version is None:
            base_version = self.versions[-1] if self.versions else None

        if base_version is None:
            logger.error("[V7.5] 无法创建重写版本：缺少基础版本")
            return None

        # 生成新版本号
        new_version_number = self._increment_version(base_version.version_number, rewrite_type)

        # 处理重写日志
        if rewrite_log is None:
            rewrite_log = []

        # 处理红方攻击类型
        if red_attack_types is None:
            red_attack_types = []

        version = HypothesisVersion(
            version_number=new_version_number,
            version_type=rewrite_type,
            created_at=datetime.now().isoformat(),
            hypothesis_content=new_hypothesis or {},
            science_score=0.0,
            fitness_score=0.0,
            defense_passed=False,
            rewrite_log=rewrite_log,
            iteration_number=iteration,
            red_attack_types=red_attack_types,
            patch_applied=rewrite_type in ['methodology_patch', 'external_compensation']
        )

        self.versions.append(version)
        self.current_version = new_version_number

        logger.info(f"[V7.5] 创建重写版本: {new_version_number} (type={rewrite_type}, iteration={iteration})")

        return version

    def update_version_scores(
        self,
        version_number: str,
        science_score: float,
        fitness_score: float,
        defense_passed: bool,
        red_attack_types: List[str] = None
    ) -> Optional[HypothesisVersion]:
        """
        更新版本分数

        Args:
            version_number: 版本号
            science_score: 科学评分
            fitness_score: 适应度评分
            defense_passed: 防御是否通过
            red_attack_types: 红方攻击类型列表

        Returns:
            Optional[HypothesisVersion]: 更新后的版本对象
        """
        for version in self.versions:
            if version.version_number == version_number:
                version.science_score = science_score
                version.fitness_score = fitness_score
                version.defense_passed = defense_passed

                if red_attack_types:
                    version.red_attack_types = red_attack_types

                logger.info(
                    f"[V7.5] 更新版本分数: {version_number} "
                    f"(science={science_score:.2f}, fitness={fitness_score:.2f}, passed={defense_passed})"
                )
                return version

        logger.warning(f"[V7.5] 未找到版本: {version_number}")
        return None

    def update_hypothesis_content(
        self,
        version_number: str,
        hypothesis_content: Dict
    ) -> Optional[HypothesisVersion]:
        """
        更新版本的假设内容

        Args:
            version_number: 版本号
            hypothesis_content: 假设内容字典

        Returns:
            Optional[HypothesisVersion]: 更新后的版本对象
        """
        for version in self.versions:
            if version.version_number == version_number:
                version.hypothesis_content = hypothesis_content
                logger.info(f"[V7.5] 更新假设内容: {version_number}")
                return version

        logger.warning(f"[V7.5] 未找到版本: {version_number}")
        return None

    def get_version_evolution_chain(self) -> List[Dict]:
        """
        获取版本演进链

        Returns:
            List[Dict]: 版本演进链列表，每个元素包含版本信息
        """
        return [version.to_dict() for version in self.versions]

    def get_best_version(self) -> Optional[HypothesisVersion]:
        """
        获取最高分版本

        Returns:
            Optional[HypothesisVersion]: 最高分版本对象
        """
        if not self.versions:
            return None

        return max(self.versions, key=lambda v: v.science_score)

    def get_current_version(self) -> Optional[HypothesisVersion]:
        """
        获取当前版本

        Returns:
            Optional[HypothesisVersion]: 当前版本对象
        """
        for version in self.versions:
            if version.version_number == self.current_version:
                return version
        return self.versions[-1] if self.versions else None

    def get_version_by_number(self, version_number: str) -> Optional[HypothesisVersion]:
        """
        根据版本号获取版本

        Args:
            version_number: 版本号

        Returns:
            Optional[HypothesisVersion]: 版本对象
        """
        for version in self.versions:
            if version.version_number == version_number:
                return version
        return None

    def _increment_version(self, current: str, rewrite_type: str) -> str:
        """
        版本号递增

        Args:
            current: 当前版本号 (如 "v1.0")
            rewrite_type: 重写类型

        Returns:
            str: 新版本号
        """
        # 解析当前版本号
        try:
            parts = current.replace('v', '').split('.')
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            major = 1
            minor = 0

        # 根据重写类型决定递增方式
        if rewrite_type in ['physical_fix', 'methodology_patch', 'external_compensation']:
            # 小版本递增
            minor += 1
        elif rewrite_type == 'major_rewrite':
            # 大版本递增
            major += 1
            minor = 0

        self.major_version = major
        self.minor_version = minor

        return f"v{major}.{minor}"

    def get_score_trend(self) -> List[float]:
        """
        获取分数趋势

        Returns:
            List[float]: 分数历史列表
        """
        return [version.science_score for version in self.versions if version.science_score > 0]

    def get_evolution_summary(self) -> Dict:
        """
        获取演化摘要

        Returns:
            Dict: 演化过程摘要
        """
        if not self.versions:
            return {
                'total_versions': 0,
                'evolution_chain': [],
                'score_trend': [],
                'best_score': 0.0,
                'final_passed': False,
            }

        best_version = self.get_best_version()
        latest_version = self.versions[-1]

        return {
            'total_versions': len(self.versions),
            'evolution_chain': self.get_version_evolution_chain(),
            'score_trend': self.get_score_trend(),
            'best_score': best_version.science_score if best_version else 0.0,
            'best_version_number': best_version.version_number if best_version else None,
            'final_passed': latest_version.defense_passed,
            'final_version_number': latest_version.version_number,
            'current_version': self.current_version,
        }

    def format_evolution_for_display(self) -> str:
        """
        格式化演进链用于 UI 显示

        Returns:
            str: 格式化后的显示文本
        """
        if not self.versions:
            return "无版本记录"

        display_lines = []
        display_lines.append("### 🔥 凤凰协议 - 假设演化路径")
        display_lines.append("")
        display_lines.append("| 版本 | 类型 | 分数 | 状态 | 修改记录 |")
        display_lines.append("|------|------|------|------|----------|")

        for version in self.versions:
            status = "✅ SUCCESS" if version.defense_passed else "🔄 继续演化"
            score_display = f"{version.science_score:.1f}" if version.science_score > 0 else "待评估"
            rewrite_display = version.rewrite_log[0].get('original', '-') if version.rewrite_log else '-'

            display_lines.append(
                f"| {version.version_number} | {VERSION_TYPES.get(version.version_type, version.version_type)} | "
                f"{score_display} | {status} | {rewrite_display} |"
            )

        return '\n'.join(display_lines)


# ==================== 辅助函数 ====================

def create_version_manager() -> HypothesisVersionManager:
    """
    创建版本管理器实例

    Returns:
        HypothesisVersionManager: 版本管理器实例
    """
    return HypothesisVersionManager()


def format_rewrite_log(rewrite_log: List[Dict]) -> str:
    """
    格式化重写日志

    Args:
        rewrite_log: 重写日志列表

    Returns:
        str: 格式化后的文本
    """
    if not rewrite_log:
        return "无修改记录"

    formatted = []
    for entry in rewrite_log:
        original = entry.get('original', '未知')
        replaced = entry.get('replaced_with', '未知')
        reason = entry.get('reason', '')

        formatted.append(f"- `{original}` → `{replaced}` ({reason})")

    return '\n'.join(formatted)


# ==================== 导出 ====================

__all__ = [
    'HypothesisVersionManager',
    'HypothesisVersion',
    'VERSION_TYPES',
    'create_version_manager',
    'format_rewrite_log',
]