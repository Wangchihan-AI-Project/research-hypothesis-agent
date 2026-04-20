# -*- coding: utf-8 -*-
"""
V7.5 方法论补丁优先级配置 (Methodology Patch Priority)

核心功能：
1. 定义不同攻击类型的补丁优先级
2. 配置补丁关键词映射
3. 提供补丁来源推荐
4. 管理补丁应用策略

设计理念：
- 算法级问题优先级最高
- 统计学问题次之
- 流水线问题最后
- 每种攻击类型配置解决方案检索关键词

作者: V7.5 架构工程师
日期: 2026-04-20
"""

from enum import Enum, auto
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# ==================== 补丁优先级枚举 ====================

class PatchPriority(Enum):
    """补丁优��级"""
    CRITICAL = auto()    # 关键级（算法缺陷）
    HIGH = auto()        # 高级（统计学缺陷）
    MEDIUM = auto()      # 中级（流水线问题）
    LOW = auto()         # 低级（建议性改进）


# ==================== 攻击类型到补丁优先级映射 ====================

ATTACK_TYPE_PRIORITY_MAP = {
    # ========== 关键级（算法缺陷）==========
    'AF3_LEAKAGE': {
        'priority': PatchPriority.CRITICAL,
        'category': 'algorithm_correction',
        'description': 'AlphaFold3 结构预测信息泄露',
        'urgency': '必须修复',
        'solution_search': [
            'AlphaFold3 error compensation method',
            'protein structure confidence calibration',
            'pLDDT score correction protocol 2025',
            'structure prediction bias correction',
        ],
        'methodology_sources': ['arxiv', 'pubmed'],
        'patch_template': 'af3_leakage_patch',
    },

    'ALGORITHM_BIAS': {
        'priority': PatchPriority.CRITICAL,
        'category': 'algorithm_correction',
        'description': '算法偏差导致结果失真',
        'urgency': '必须修复',
        'solution_search': [
            'algorithm bias correction method',
            'model fairness calibration 2025',
            'bias mitigation in machine learning',
        ],
        'methodology_sources': ['arxiv', 'pubmed'],
        'patch_template': 'algorithm_bias_patch',
    },

    # ========== 高级（统计学缺陷）==========
    'OVERFITTING': {
        'priority': PatchPriority.HIGH,
        'category': 'statistical_correction',
        'description': '模型过度拟合，泛化能力差',
        'urgency': '强烈建议修复',
        'solution_search': [
            'overfitting prevention protocol 2025',
            'cross-validation leak-free design',
            'regularization technique best practice',
            'model generalization improvement',
        ],
        'methodology_sources': ['arxiv', 'pubmed'],
        'patch_template': 'overfitting_patch',
    },

    'LEAKAGE': {
        'priority': PatchPriority.HIGH,
        'category': 'statistical_correction',
        'description': '数据泄露导致评估虚高',
        'urgency': '强烈建议修复',
        'solution_search': [
            'data leakage prevention protocol',
            'temporal data split methodology',
            'feature leakage detection method',
        ],
        'methodology_sources': ['arxiv', 'pubmed'],
        'patch_template': 'leakage_patch',
    },

    'STATISTICAL_FLAW': {
        'priority': PatchPriority.HIGH,
        'category': 'statistical_correction',
        'description': '统计方法使用不当',
        'urgency': '强烈建议修复',
        'solution_search': [
            'statistical power analysis method',
            'sample size determination protocol',
            'multiple testing correction approach',
        ],
        'methodology_sources': ['arxiv', 'pubmed'],
        'patch_template': 'statistical_flaw_patch',
    },

    # ========== 中级（流水线问题）==========
    'BIAS': {
        'priority': PatchPriority.MEDIUM,
        'category': 'pipeline_correction',
        'description': '选择偏差影响结果可靠性',
        'urgency': '建议修复',
        'solution_search': [
            'selection bias correction method',
            'covariate balance technique',
            'propensity score matching protocol',
        ],
        'methodology_sources': ['arxiv', 'pubmed'],
        'patch_template': 'bias_patch',
    },

    'VALIDATION': {
        'priority': PatchPriority.MEDIUM,
        'category': 'pipeline_correction',
        'description': '验证不足导致结论不稳健',
        'urgency': '建议修复',
        'solution_search': [
            'independent validation set design',
            'external validation methodology',
            'reproducibility assessment protocol',
        ],
        'methodology_sources': ['arxiv', 'pubmed'],
        'patch_template': 'validation_patch',
    },

    'REPRODUCIBILITY': {
        'priority': PatchPriority.MEDIUM,
        'category': 'pipeline_correction',
        'description': '可重复性问题',
        'urgency': '建议修复',
        'solution_search': [
            'reproducibility enhancement protocol',
            'experiment standardization method',
            'code sharing best practice 2025',
        ],
        'methodology_sources': ['arxiv', 'pubmed'],
        'patch_template': 'reproducibility_patch',
    },

    # ========== 低级（建议性改进）==========
    'CLARITY': {
        'priority': PatchPriority.LOW,
        'category': 'documentation_improvement',
        'description': '方法论描述不够清晰',
        'urgency': '可选改进',
        'solution_search': [
            'methodology documentation template',
            'experimental design reporting standard',
        ],
        'methodology_sources': [],
        'patch_template': 'clarity_patch',
    },

    'COMPLETENESS': {
        'priority': PatchPriority.LOW,
        'category': 'documentation_improvement',
        'description': '方法论不够完整',
        'urgency': '可选改进',
        'solution_search': [
            'complete methodology checklist',
            'experimental design components guide',
        ],
        'methodology_sources': [],
        'patch_template': 'completeness_patch',
    },
}


# ==================== 补丁优先级顺序配置 ====================

PRIORITY_ORDER = {
    PatchPriority.CRITICAL: 1,
    PatchPriority.HIGH: 2,
    PatchPriority.MEDIUM: 3,
    PatchPriority.LOW: 4,
}


# ==================== 补丁应用策略配置 ====================

PATCH_STRATEGY_CONFIG = {
    'max_patches_per_iteration': 3,        # 每次迭代最多应用补丁数
    'priority_threshold': PatchPriority.MEDIUM,  # 优先级阈值（低于此优先级的补丁不自动应用）
    'allow_multiple_same_priority': True,  # 是否允许多个相同优先级的补丁
    'fallback_to_manual': True,            # 自动补丁失败时是否回退到手动
}


# ==================== 补丁数据类 ====================

@dataclass
class MethodologyPatch:
    """方法论补丁"""
    attack_type: str                       # 攻击类型
    priority: PatchPriority                # 优先级
    category: str                          # 类别
    description: str                       # 描述
    urgency: str                           # 紧迫性
    solution_keywords: List[str]           # 解决方案关键词
    search_sources: List[str]              # 搜索来源
    patch_template: str                    # 补丁模板
    patch_instructions: str = ""           # 补丁指令
    supporting_references: List[str] = None  # 支持参考文献

    def __post_init__(self):
        if self.supporting_references is None:
            self.supporting_references = []

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'attack_type': self.attack_type,
            'priority': self.priority.name,
            'category': self.category,
            'description': self.description,
            'urgency': self.urgency,
            'solution_keywords': self.solution_keywords,
            'search_sources': self.search_sources,
            'patch_template': self.patch_template,
            'patch_instructions': self.patch_instructions,
            'supporting_references': self.supporting_references,
        }


# ==================== 方法论补丁优先级管理器 ====================

class MethodologyPatchPriorityManager:
    """方法论补丁优先级管理器"""

    def __init__(self):
        self.priority_map = ATTACK_TYPE_PRIORITY_MAP
        self.strategy_config = PATCH_STRATEGY_CONFIG
        logger.info("[V7.5] MethodologyPatchPriorityManager 初始化完成")

    def get_patch_priority(self, attack_type: str) -> PatchPriority:
        """
        获取补丁优先级

        Args:
            attack_type: 攻击类型

        Returns:
            PatchPriority: 优先级枚举
        """
        if attack_type in self.priority_map:
            return self.priority_map[attack_type]['priority']
        return PatchPriority.LOW  # 默认低优先级

    def get_patch_config(self, attack_type: str) -> Optional[Dict]:
        """
        获取补丁配置

        Args:
            attack_type: 攻击类型

        Returns:
            Optional[Dict]: 补丁配置字典
        """
        return self.priority_map.get(attack_type)

    def create_methodology_patch(
        self,
        attack_type: str,
        supporting_references: List[str] = None
    ) -> Optional[MethodologyPatch]:
        """
        创建方法论补丁

        Args:
            attack_type: 攻击类型
            supporting_references: 支持参考文献

        Returns:
            Optional[MethodologyPatch]: 方法论补丁对象
        """
        config = self.get_patch_config(attack_type)
        if not config:
            logger.warning(f"[V7.5] 未知攻击类型: {attack_type}")
            return None

        patch = MethodologyPatch(
            attack_type=attack_type,
            priority=config['priority'],
            category=config['category'],
            description=config['description'],
            urgency=config['urgency'],
            solution_keywords=config['solution_search'],
            search_sources=config['methodology_sources'],
            patch_template=config['patch_template'],
            supporting_references=supporting_references or []
        )

        # 生成补丁指令
        patch.patch_instructions = self._generate_patch_instructions(patch)

        return patch

    def prioritize_attack_types(
        self,
        attack_types: List[str]
    ) -> List[str]:
        """
        按优先级排序攻击类型

        Args:
            attack_types: 攻击类型列表

        Returns:
            List[str]: 排序后的攻击类型列表
        """
        def get_priority_value(attack_type: str) -> int:
            priority = self.get_patch_priority(attack_type)
            return PRIORITY_ORDER.get(priority, 999)

        return sorted(attack_types, key=get_priority_value)

    def select_patches_for_iteration(
        self,
        attack_types: List[str]
    ) -> List[MethodologyPatch]:
        """
        选择本次迭代应用的补丁

        Args:
            attack_types: 攻击类型列表

        Returns:
            List[MethodologyPatch]: 选中的补丁列表
        """
        # 按优先级排序
        sorted_types = self.prioritize_attack_types(attack_types)

        selected_patches = []
        for attack_type in sorted_types:
            # 检查是否达到最大补丁数
            if len(selected_patches) >= self.strategy_config['max_patches_per_iteration']:
                break

            patch = self.create_methodology_patch(attack_type)
            if not patch:
                continue

            # 检查优先级是否满足阈值
            threshold = self.strategy_config['priority_threshold']
            if PRIORITY_ORDER.get(patch.priority, 999) > PRIORITY_ORDER.get(threshold, 999):
                logger.info(f"[V7.5] 补丁 {attack_type} 优先级过低，跳过")
                continue

            selected_patches.append(patch)

        logger.info(f"[V7.5] 选择了 {len(selected_patches)} 个补丁用于本次迭代")
        return selected_patches

    def get_solution_search_keywords(
        self,
        attack_types: List[str]
    ) -> Dict[str, List[str]]:
        """
        获取解决方案搜索关键词

        Args:
            attack_types: 攻击类型列表

        Returns:
            Dict[str, List[str]]: 按攻击类型分组的搜索关键词
        """
        keywords_map = {}

        for attack_type in attack_types:
            config = self.get_patch_config(attack_type)
            if config:
                keywords_map[attack_type] = config.get('solution_search', [])

        return keywords_map

    def get_recommended_sources(self, attack_type: str) -> List[str]:
        """
        获取推荐的搜索来源

        Args:
            attack_type: 攻击类型

        Returns:
            List[str]: 推荐来源列表
        """
        config = self.get_patch_config(attack_type)
        if config:
            return config.get('methodology_sources', ['arxiv', 'pubmed'])
        return ['arxiv', 'pubmed']

    def _generate_patch_instructions(self, patch: MethodologyPatch) -> str:
        """
        生成补丁指令

        Args:
            patch: 方法论补丁对象

        Returns:
            str: 补丁指令字符串
        """
        instructions = f"""
### 针对 {patch.attack_type} 的修复方案

**问题描述**: {patch.description}
**优先级**: {patch.priority.name}
**紧迫性**: {patch.urgency}

#### 建议修复措施

"""

        # 根据攻击类型生成具体指令
        if patch.attack_type == 'OVERFITTING':
            instructions += """
1. 添加交叉验证协议
   - 使用 k-fold 交叉验证（k=5 或 k=10）
   - 明确训练集、验证集、测试集划分

2. 增加正则化技术
   - L1/L2 正则化
   - Dropout（如果是神经网络）

3. 模型复杂度控制
   - 特征选择与降维
   - 参数数量限制
"""
        elif patch.attack_type == 'LEAKAGE':
            instructions += """
1. 明确数据划分边界
   - 时序数据按时间划分
   - 避免同一样本同时出现在训练和测试集

2. 特征泄露检查
   - 确保特征不包含未来信息
   - 移除高度相关但无因果关系的特征

3. 数据预处理分离
   - 统计量计算仅使用训练集
   - 避免全局标准化
"""
        elif patch.attack_type == 'BIAS':
            instructions += """
1. 协变量平衡方法
   - 倾向得分匹配 (PSM)
   - 逆概率加权 (IPW)

2. 样本代表性评估
   - 与总体人群对比
   - 亚组分析

3. 敏感性分析
   - E-value 计算
   - 偏差校正方法
"""
        elif patch.attack_type == 'VALIDATION':
            instructions += """
1. 独立验证队列设计
   - 外部中心验证
   - 时间独立验证集

2. 验证协议预先注册
   - 主要终点定义
   - 统计分析计划

3. 多中心验证计划
   - 不同人群验证
   - 可移植性评估
"""
        elif patch.attack_type == 'AF3_LEAKAGE':
            instructions += """
1. AlphaFold3 置信度校正
   - 使用 pLDDT 分数加权
   - 低置信度区域排除或降权

2. 结构预测误差补偿
   - 蒙特卡洛采样评估不确定性
   - 多模型集成预测

3. 实验验证优先级
   - 高置信度预测优先实验
   - 低置信度区域作为探索性分析
"""
        elif patch.attack_type == 'STATISTICAL_FLAW':
            instructions += """
1. 统计功效分析
   - 前瞻性样本量计算
   - 效应量估计

2. 多重检验校正
   - FDR 或 Bonferroni 校正
   - 预设主要终点

3. 敏感性分析
   - 不同统计方法对比
   - 亚组分析
"""
        else:
            instructions += f"""
1. 针对 {patch.attack_type} 的具体修复措施
2. 参考相关领域最佳实践
3. 预注册分析计划
"""

        if patch.supporting_references:
            instructions += f"\n#### 支持文献\n"
            for ref in patch.supporting_references[:3]:
                instructions += f"- {ref}\n"

        return instructions.strip()

    def format_priority_summary(self, attack_types: List[str]) -> str:
        """
        格式化优先级摘要

        Args:
            attack_types: 攻击类型列表

        Returns:
            str: 格式化后的摘要字符串
        """
        sorted_types = self.prioritize_attack_types(attack_types)

        lines = []
        lines.append("### 补丁优先级排序")
        lines.append("")
        lines.append("| 优先级 | 攻击类型 | 描述 | 紧迫性 |")
        lines.append("|--------|----------|------|--------|")

        priority_icons = {
            PatchPriority.CRITICAL: "🔴",
            PatchPriority.HIGH: "🟠",
            PatchPriority.MEDIUM: "🟡",
            PatchPriority.LOW: "🟢",
        }

        for attack_type in sorted_types:
            config = self.get_patch_config(attack_type)
            if config:
                priority = config['priority']
                icon = priority_icons.get(priority, "⚪")
                lines.append(
                    f"| {icon} {priority.name} | {attack_type} | {config['description']} | {config['urgency']} |"
                )

        return '\n'.join(lines)


# ==================== 辅助函数 ====================

def get_patch_priority_manager() -> MethodologyPatchPriorityManager:
    """获取补丁优先级管理器实例"""
    return MethodologyPatchPriorityManager()


def prioritize_red_team_attacks(attack_types: List[str]) -> List[str]:
    """
    按优先级排序红方攻击类型（便捷函数）

    Args:
        attack_types: 攻击类型列表

    Returns:
        List[str]: 排序后的攻击类型列表
    """
    manager = get_patch_priority_manager()
    return manager.prioritize_attack_types(attack_types)


def get_solution_keywords_for_search(attack_types: List[str]) -> Dict[str, List[str]]:
    """
    获取解决方案搜索关键词（便捷函数）

    Args:
        attack_types: 攻击类型列表

    Returns:
        Dict[str, List[str]]: 按攻击类型分组的搜索关键词
    """
    manager = get_patch_priority_manager()
    return manager.get_solution_search_keywords(attack_types)


# ==================== 导出 ====================

__all__ = [
    'PatchPriority',
    'ATTACK_TYPE_PRIORITY_MAP',
    'PRIORITY_ORDER',
    'PATCH_STRATEGY_CONFIG',
    'MethodologyPatch',
    'MethodologyPatchPriorityManager',
    'get_patch_priority_manager',
    'prioritize_red_team_attacks',
    'get_solution_keywords_for_search',
]
