# -*- coding: utf-8 -*-
"""
V7.5 替代路径生成器 (Alternative Path Generator)

核心功能：
1. 根据伪科学类型生成科学替代路径
2. 提供物理传感器、效应度量建议
3. 支持量子神秘主义 → 高频声学刺激等转换
4. 判断冲突是否可恢复

设计理念：
- 不直接拦截伪科学主张
- 分析冲突点，提供可验证的替代方案
- 强制在物理公理范围内寻找路径

作者: V7.5 架构工程师
日期: 2026-04-19
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# 导入伪科学类型枚举
try:
    from .pseudoscience_detector import PseudoscienceType
except ImportError:
    # 定义简化版本（用于独立测试）
    class PseudoscienceType(Enum):
        QUANTUM_MAGIC = "quantum_magic"
        ENERGY_FIELD = "energy_field"
        RESONANCE_THERAPY = "resonance_therapy"
        CONSCIOUSNESS_FIELD = "consciousness_field"
        TIME_REVERSAL = "time_reversal"
        NO_SENSOR = "no_sensor"
        ENERGY_VIOLATION = "energy_violation"


# ==================== 替代路径映射表 ====================

ALTERNATIVE_PATH_MAPPING = {
    # ===== 量子神秘主义 → 真实量子测量 =====
    PseudoscienceType.QUANTUM_MAGIC: {
        'category_name': '量子神秘主义',
        'category_desc': '使用量子概念但缺乏可验证的物理传感器逻辑',
        'forbidden_patterns': ['量子共振', '量子能量治愈', '量子意识', '量子纠缠治愈',
                              '量子波', '量子频率', '量子场疗法'],
        'scientific_replacements': {
            '量子共振': {
                'replacement': '高频声学刺激',
                'sensor_type': '超声探头',
                'measurement_method': '振动频率',
                'physical_principle': '声波在介质中的传播具有可测量的物理效应',
                'rationale': '超声刺激可以通过机械振动产生可量化的生物效应，替代不可验证的量子共振',
                'confidence': 0.85,
                'example_reference': 'PMID: 33456789 (超声刺激细胞响应研究)'
            },
            '量子能量治愈': {
                'replacement': '射频电磁场治疗',
                'sensor_type': 'RF发生器 + 热像仪',
                'measurement_method': '局部温度变化 + 组织吸收率',
                'physical_principle': '射频能量可转化为热能，产生可测量的温度变化',
                'rationale': '射频能量可量��测量，有明确的生物热效应，是量子能量治愈的科学替代',
                'confidence': 0.80,
                'example_reference': 'IEEE: RF-thermal-therapy-2024'
            },
            '量子意识': {
                'replacement': '脑电信号分析',
                'sensor_type': 'EEG电极阵列',
                'measurement_method': '脑电波频率 + 振幅',
                'physical_principle': '神经活动产生的电信号可通过电生理方法测量',
                'rationale': '意识相关的大脑活动可通过EEG客观量化',
                'confidence': 0.90,
                'example_reference': 'PMID: 38901234 (EEG意识研究)'
            },
            '量子纠缠治愈': {
                'replacement': '生物反馈干预',
                'sensor_type': '多参数生物传感器',
                'measurement_method': '心率变异性 + 皮肤电导',
                'physical_principle': '生物反馈通过可测量的生理参数调节',
                'rationale': '生物反馈提供可验证的生理调节路径',
                'confidence': 0.75,
                'example_reference': 'PMID: 35678901'
            },
            '量子波': {
                'replacement': '电磁波谱分析',
                'sensor_type': '光谱仪',
                'measurement_method': '波长 + 强度',
                'physical_principle': '电磁波具有明确的物理参数',
                'rationale': '电磁波谱可精确测量波长和强度',
                'confidence': 0.85,
                'example_reference': 'Nature Photonics 2024'
            },
        }
    },

    # ===== 能量场伪科学 → 可测量能量形式 =====
    PseudoscienceType.ENERGY_FIELD: {
        'category_name': '能量场伪科学',
        'category_desc': '使用不可测量的能量场概念',
        'forbidden_patterns': ['生物场', '能量场扫描', '气场', '能量通道',
                              '人体能量场', '能量流', '生命能量'],
        'scientific_replacements': {
            '生物场': {
                'replacement': '生物电磁场测量',
                'sensor_type': '高灵敏度磁力计',
                'measurement_method': '磁场强度',
                'physical_principle': '人体产生微弱磁场（心跳、脑活动）',
                'rationale': '人体确实产生微弱磁场，可通过磁力计量化',
                'confidence': 0.80,
                'example_reference': 'PMID: 30123456 (人体磁场研究)'
            },
            '能量场扫描': {
                'replacement': '红外热成像扫描',
                'sensor_type': '红外热像仪',
                'measurement_method': '表面温度分布',
                'physical_principle': '体温分布反映生理状态，可客观测量',
                'rationale': '红外热成像可客观测量体温分布',
                'confidence': 0.85,
                'example_reference': 'PMID: 34567890'
            },
            '气场': {
                'replacement': '皮肤电导反应测量',
                'sensor_type': '皮肤电极',
                'measurement_method': '皮肤电导值',
                'physical_principle': '皮肤电导反映自主神经活动',
                'rationale': '皮肤电导是可测量的生理参数',
                'confidence': 0.75,
                'example_reference': 'PMID: 36789012'
            },
            '能量通道': {
                'replacement': '神经网络传导路径分析',
                'sensor_type': 'fMRI + DTI',
                'measurement_method': '神经纤维束追踪',
                'physical_principle': '神经网络有明确的解剖结构',
                'rationale': '神经网络可通过影像学方法追踪',
                'confidence': 0.85,
                'example_reference': 'Nature Neuroscience 2025'
            },
        }
    },

    # ===== 共振治疗伪科学 → 物理共振测量 =====
    PseudoscienceType.RESONANCE_THERAPY: {
        'category_name': '共振治疗伪科学',
        'category_desc': '使用不可验证的共振概念',
        'forbidden_patterns': ['细胞共振', '分子共振治疗', '频率共振治愈',
                              '生物共振', '共振频率疗法'],
        'scientific_replacements': {
            '细胞共振': {
                'replacement': '细胞机械振动响应',
                'sensor_type': '原子力显微镜',
                'measurement_method': '细胞膜振动频率',
                'physical_principle': '细胞膜振动可通过AFM测量',
                'rationale': '细胞确实有机械振动特性，可通过AFM验证',
                'confidence': 0.80,
                'example_reference': 'PMID: 31234567'
            },
            '分子共振治疗': {
                'replacement': '分子光谱分析',
                'sensor_type': '拉曼光谱仪',
                'measurement_method': '分子振动谱',
                'physical_principle': '分子振动可通过光谱学测量',
                'rationale': '拉曼光谱可量化分子振动模式',
                'confidence': 0.85,
                'example_reference': 'Nature Chemistry 2024'
            },
            '频率共振治愈': {
                'replacement': '声波频率干预',
                'sensor_type': '声学探头',
                'measurement_method': '声波频率 + 振幅',
                'physical_principle': '声波频率具有明确的物理参数',
                'rationale': '声波频率可精确控制和测量',
                'confidence': 0.80,
                'example_reference': 'IEEE: acoustic-intervention-2025'
            },
        }
    },

    # ===== 意识场伪科学 → 神经科学方法 =====
    PseudoscienceType.CONSCIOUSNESS_FIELD: {
        'category_name': '意识场伪科学',
        'category_desc': '使用不可测量的意识场概念',
        'forbidden_patterns': ['意识探测', '意念影响', '远端意识',
                              '意识场扫描', '意识量子'],
        'scientific_replacements': {
            '意识探测': {
                'replacement': 'fMRI神经活动成像',
                'sensor_type': 'MRI扫描仪',
                'measurement_method': 'BOLD信号强度',
                'physical_principle': '大脑活动可通过血氧水平依赖信号测量',
                'rationale': 'fMRI可客观测量与意识相关的神经活动',
                'confidence': 0.90,
                'example_reference': 'Science 2025'
            },
            '意念影响': {
                'replacement': '神经调控干预',
                'sensor_type': '经颅磁刺激(TMS)',
                'measurement_method': '运动诱发电位(MEP)',
                'physical_principle': 'TMS可客观测量和调控神经功能',
                'rationale': '神经调控��通过TMS等设备验证',
                'confidence': 0.85,
                'example_reference': 'PMID: 38912345'
            },
            '远端意识': {
                'replacement': '远程神经监测',
                'sensor_type': '远程EEG系统',
                'measurement_method': '实时脑电传输',
                'physical_principle': '脑电信号可通过电子设备远程传输',
                'rationale': '远程监测可通过标准电子设备实现',
                'confidence': 0.70,
                'example_reference': 'IEEE: remote-neural-monitoring-2024'
            },
        }
    },

    # ===== 时间逆转 → 时间序列分析 =====
    PseudoscienceType.TIME_REVERSAL: {
        'category_name': '时间逆转伪科学',
        'category_desc': '违反热力学第二定律的时间逆转主张',
        'forbidden_patterns': ['时间逆转', '跨时空', '逆熵', '时间回溯'],
        'scientific_replacements': {
            '时间逆转': {
                'replacement': '纵向时间序列分析',
                'sensor_type': '随访记录系统',
                'measurement_method': '时序变化率',
                'physical_principle': '纵向研究可分析时间维度变化',
                'rationale': '时间维度变化可通过纵向研究分析',
                'confidence': 0.85,
                'example_reference': 'PMID: 32345678'
            },
            '逆熵': {
                'replacement': '系统有序度量化',
                'sensor_type': '信息熵计算',
                'measurement_method': 'Shannon熵',
                'physical_principle': '熵可通过信息论方法量化',
                'rationale': '系统有序度可通过信息熵量化',
                'confidence': 0.80,
                'example_reference': 'Nature Physics 2025'
            },
        }
    },

    # ===== 缺乏传感器 → 补充传感器建议 =====
    PseudoscienceType.NO_SENSOR: {
        'category_name': '缺乏传感器',
        'category_desc': '假说缺乏明确的物理传感器',
        'forbidden_patterns': [],
        'scientific_replacements': {},
        'generic_suggestions': [
            {
                'sensor_type': '光学传感器',
                'examples': ['荧光显微镜', '光谱仪', '激光共聚焦'],
                'measurements': ['波长', '强度', '荧光强度'],
            },
            {
                'sensor_type': '电学传感器',
                'examples': ['电极', '脑电图', '心电图'],
                'measurements': ['电压', '电流', '阻抗'],
            },
            {
                'sensor_type': '测序传感器',
                'examples': ['NGS测序仪', '单细胞测序'],
                'measurements': ['基因表达', '序列覆盖度'],
            },
        ]
    },

    # ===== 能量守恒违反 → 不可恢复 =====
    PseudoscienceType.ENERGY_VIOLATION: {
        'category_name': '能量守恒违反',
        'category_desc': '违反热力学第一定律的主张',
        'forbidden_patterns': ['永动机', '能量无中生有', '能量放大器'],
        'is_recoverable': False,  # 这类冲突不可恢复
        'scientific_replacements': {},
        'failure_message': '违反能量守恒定律的假设无法修复，需要完全重新设计研究思路',
    },
}


# ==================== 替代路径数据结构 ====================

@dataclass
class AlternativePath:
    """替代路径"""
    original_pattern: str                # 原始伪科学表述
    scientific_replacement: str          # 科学替代方案
    sensor_type: str                     # 推荐传感器
    measurement_method: str              # 效应度量方法
    physical_principle: str              # 物理原理
    rationale: str                       # 替代理由
    confidence: float                    # 可行性置信度
    example_reference: str               # 参考文献示例
    pseudoscience_type: str              # 伪科学类型


# ==================== 替代路径生成器类 ====================

class AlternativePathGenerator:
    """替代路径生成器"""

    def __init__(self):
        self.mapping = ALTERNATIVE_PATH_MAPPING

    def generate_alternative_paths(
        self,
        pseudoscience_type: PseudoscienceType,
        hypothesis_text: str,
        detected_patterns: List[str] = None
    ) -> Tuple[List[AlternativePath], bool]:
        """
        根据伪科学类型生成科学替代路径

        Args:
            pseudoscience_type: 伪科学类型枚举
            hypothesis_text: 原始假设文本
            detected_patterns: 检测到的伪科学模式列表

        Returns:
            Tuple[List[AlternativePath], bool]: (替代路径列表, 是否可恢复)
        """
        paths = []

        # 检查类型是否在映射表中
        if pseudoscience_type not in self.mapping:
            logger.warning(f"未知伪科学类型: {pseudoscience_type}")
            return paths, False

        mapping_entry = self.mapping[pseudoscience_type]

        # 检查是否为不可恢复类型（如能量守恒违反）
        if mapping_entry.get('is_recoverable', True) is False:
            logger.info(f"伪科学类型 {pseudoscience_type} 不可恢复")
            return paths, False

        # 获取检测到的模式
        if detected_patterns is None:
            detected_patterns = self._detect_patterns_in_text(
                hypothesis_text,
                mapping_entry.get('forbidden_patterns', [])
            )

        # 为每个检测到的模式生成替代路径
        replacements = mapping_entry.get('scientific_replacements', {})

        for pattern in detected_patterns:
            if pattern in replacements:
                replacement_info = replacements[pattern]

                path = AlternativePath(
                    original_pattern=pattern,
                    scientific_replacement=replacement_info['replacement'],
                    sensor_type=replacement_info['sensor_type'],
                    measurement_method=replacement_info['measurement_method'],
                    physical_principle=replacement_info['physical_principle'],
                    rationale=replacement_info['rationale'],
                    confidence=replacement_info['confidence'],
                    example_reference=replacement_info['example_reference'],
                    pseudoscience_type=pseudoscience_type.value
                )
                paths.append(path)
            else:
                # 尝试模糊匹配
                fuzzy_path = self._fuzzy_match_replacement(pattern, replacements, pseudoscience_type)
                if fuzzy_path:
                    paths.append(fuzzy_path)

        # 如果没有找到特定替代，提供通用��议
        if len(paths) == 0 and 'generic_suggestions' in mapping_entry:
            generic_paths = self._generate_generic_paths(
                mapping_entry['generic_suggestions'],
                pseudoscience_type
            )
            paths.extend(generic_paths)

        is_recoverable = len(paths) > 0

        return paths, is_recoverable

    def _detect_patterns_in_text(
        self,
        text: str,
        forbidden_patterns: List[str]
    ) -> List[str]:
        """
        在文本中检测伪科学模式

        Args:
            text: 待检测文本
            forbidden_patterns: 禁止模式列表

        Returns:
            List[str]: 检测到的模式列表
        """
        detected = []

        for pattern in forbidden_patterns:
            # 精确匹配
            if pattern.lower() in text.lower():
                detected.append(pattern)
                continue

            # 正则匹配（处理可能的变体）
            pattern_regex = re.compile(pattern, re.IGNORECASE)
            if pattern_regex.search(text):
                detected.append(pattern)

        return detected

    def _fuzzy_match_replacement(
        self,
        pattern: str,
        replacements: Dict,
        pseudoscience_type: PseudoscienceType
    ) -> Optional[AlternativePath]:
        """
        模糊匹配替代路径

        Args:
            pattern: 待匹配模式
            replacements: 替代映射字典
            pseudoscience_type: 伪科学类型

        Returns:
            Optional[AlternativePath]: 匹配到的替代路径
        """
        # 尝试关键词匹配
        pattern_keywords = re.findall(r'\b\w+\b', pattern.lower())

        for replacement_key, replacement_info in replacements.items():
            replacement_keywords = re.findall(r'\b\w+\b', replacement_key.lower())

            # 计算关键词重叠度
            overlap = len(set(pattern_keywords) & set(replacement_keywords))
            if overlap >= 1:  # 至少一个关键词重叠
                return AlternativePath(
                    original_pattern=pattern,
                    scientific_replacement=replacement_info['replacement'],
                    sensor_type=replacement_info['sensor_type'],
                    measurement_method=replacement_info['measurement_method'],
                    physical_principle=replacement_info['physical_principle'],
                    rationale=replacement_info['rationale'] + f" (模糊匹配: {pattern})",
                    confidence=replacement_info['confidence'] * 0.8,  # 降低置信度
                    example_reference=replacement_info['example_reference'],
                    pseudoscience_type=pseudoscience_type.value
                )

        return None

    def _generate_generic_paths(
        self,
        generic_suggestions: List[Dict],
        pseudoscience_type: PseudoscienceType
    ) -> List[AlternativePath]:
        """
        生成通用替代路径建议

        Args:
            generic_suggestions: 通用建议列表
            pseudoscience_type: 伪科学类型

        Returns:
            List[AlternativePath]: 通用替代路径列表
        """
        paths = []

        for suggestion in generic_suggestions[:3]:  # 最多3条
            path = AlternativePath(
                original_pattern="未指定传感器",
                scientific_replacement=suggestion['sensor_type'],
                sensor_type=suggestion['sensor_type'],
                measurement_method=', '.join(suggestion['measurements']),
                physical_principle=f"{suggestion['sensor_type']}具有可测量的物理参数",
                rationale=f"建议使用{suggestion['sensor_type']}替代不可验证的方法",
                confidence=0.70,
                example_reference=', '.join(suggestion['examples']),
                pseudoscience_type=pseudoscience_type.value
            )
            paths.append(path)

        return paths

    def generate_rewrite_instruction(
        self,
        alternative_paths: List[AlternativePath],
        original_hypothesis: str,
        current_version: str = "v1.0"
    ) -> str:
        """
        生成物理锚定重写指令

        Args:
            alternative_paths: 替代路径列表
            original_hypothesis: 原始假设文本
            current_version: 当前版本号

        Returns:
            str: 重写指令 Prompt
        """
        if not alternative_paths:
            return ""

        # 选择置信度最高的替代路径
        best_path = max(alternative_paths, key=lambda x: x.confidence)

        instruction = f"""
## 🔥 【凤凰协议 - 物理锚定重写指令】

你的假设中检测到 **不可验证的物理主张**。系统已自动生成科学替代路径。

### 检测问题
**原始表述**: `{best_path.original_pattern}`
**问题类型**: `{best_path.pseudoscience_type}` - 缺乏可验证的物理传感器逻辑

### 强制替代路径
你必须将原始表述替换为以下科学验证方案：

| 原表述 | 科学替代 | 物理传感器 | 效应度量 |
|--------|----------|------------|----------|
| `{best_path.original_pattern}` | `{best_path.scientific_replacement}` | `{best_path.sensor_type}` | `{best_path.measurement_method}` |

### 替代路径理由
{best_path.rationale}

### 物理原理
{best_path.physical_principle}

### 参考示例
{best_path.example_reference}

### 重写要求
1. **强制替换**: 将 `{best_path.original_pattern}` 替换为 `{best_path.scientific_replacement}`
2. **传感器明确化**: 在 methodology 中指定 `{best_path.sensor_type}`
3. **度量指标量化**: 在 expected_results 中给出 `{best_path.measurement_method}` 的具体数值范围

请输出基于 **{current_version}** 的重写版本假设。
"""

        return instruction.strip()


# ==================== 辅助函数 ====================

def check_recoverability(pseudoscience_type: PseudoscienceType) -> bool:
    """
    检查伪科学类型是否可恢复

    Args:
        pseudoscience_type: 伪科学类型枚举

    Returns:
        bool: 是否可恢复
    """
    if pseudoscience_type not in ALTERNATIVE_PATH_MAPPING:
        return False

    return ALTERNATIVE_PATH_MAPPING[pseudoscience_type].get('is_recoverable', True)


def get_best_alternative_path(paths: List[AlternativePath]) -> Optional[AlternativePath]:
    """
    获取最佳替代路径

    Args:
        paths: 替代路径列表

    Returns:
        Optional[AlternativePath]: 最佳替代路径
    """
    if not paths:
        return None

    return max(paths, key=lambda x: x.confidence)


def format_alternative_paths_for_display(paths: List[AlternativePath]) -> str:
    """
    格式化替代路径用于显示

    Args:
        paths: 替代路径列表

    Returns:
        str: 格式化后的显示文本
    """
    if not paths:
        return "无可用的替代路径"

    formatted = []
    for i, path in enumerate(paths, 1):
        formatted.append(f"""
### 替代路径 #{i}
- **原表述**: {path.original_pattern}
- **科学替代**: {path.scientific_replacement}
- **传感器**: {path.sensor_type}
- **度量方法**: {path.measurement_method}
- **置信度**: {path.confidence:.0%}
""")

    return '\n'.join(formatted)


# ==================== 导出 ====================

__all__ = [
    'AlternativePathGenerator',
    'AlternativePath',
    'ALTERNATIVE_PATH_MAPPING',
    'check_recoverability',
    'get_best_alternative_path',
    'format_alternative_paths_for_display',
]