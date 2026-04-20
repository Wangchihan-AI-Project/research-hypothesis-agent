# -*- coding: utf-8 -*-
"""
V7.5 凤凰协议伪科学检测引擎 (Phoenix Protocol Pseudoscience Detector)

核心功能：
1. 物理公理锚定验证
2. 信号捕获可行性检查
3. 能量转换逻辑验证
4. 效应度量可行性检查
5. 实验验证路径检查

V7.5 核心变更 - 凤凰协议集成：
- 物理公理冲突时不直接拦截
- 自动生成替代路径建议
- 判断冲突是否可恢复
- 提供 rewrite_instruction 注入 PI Agent

判定原则：
- 假说可以极其超前，但必须交代物理层面的传感器逻辑
- 检测到伪科学模式时，尝试自动生成科学替代路径
- 只有真正不可恢复的冲突才返回 HARD_FAILURE

作者: V7.5 架构工程师
日期: 2026-04-19
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== 伪科学类型枚举 ====================

class PseudoscienceType(Enum):
    """伪科学类型枚举"""
    QUANTUM_MAGIC = "quantum_magic"           # 量子神秘主义
    ENERGY_FIELD = "energy_field"             # 能量场伪科学
    RESONANCE_THERAPY = "resonance_therapy"   # 共振治疗伪科学
    SUPERNATURAL = "supernatural"             # 超自然主张
    TIME_REVERSAL = "time_reversal"           # 时间逆转主张
    CONSCIOUSNESS_FIELD = "consciousness_field"  # 意识场伪科学
    NO_SENSOR = "no_sensor"                   # 缺乏传感器
    NO_MEASUREMENT = "no_measurement"         # 缺乏度量机制
    ENERGY_VIOLATION = "energy_violation"     # 能量守恒违反


# ==================== 物理传感器注册表 ====================

PHYSICS_SENSOR_REGISTRY = {
    'optical': {
        'name': '光学传感器',
        'keywords': ['spectrometer', 'microscope', 'fluorescence', 'spr',
                    '光谱', '显微镜', '荧光', 'optical', 'imaging', '成像',
                    'laser', '激光', 'photodetector', '光检测'],
        'measurements': ['wavelength', 'intensity', 'fluorescence', 'absorbance'],
    },
    'electronic': {
        'name': '电学传感器',
        'keywords': ['electrode', 'patch clamp', 'ekg', 'eeg', 'ecg',
                    '电极', '脑电', '心电', 'voltage', 'current', 'impedance',
                    'potentiostat', 'electrochemical', '电化学'],
        'measurements': ['voltage', 'current', 'conductance', 'impedance'],
    },
    'magnetic': {
        'name': '磁学传感器',
        'keywords': ['mri', 'nmr', 'magnetometer', 'squid',
                    '磁共振', '核磁', 'magnetic', '磁场'],
        'measurements': ['magnetic field', 'resonance frequency', 'susceptibility'],
    },
    'mechanical': {
        'name': '力学传感器',
        'keywords': ['afm', 'force sensor', 'pressure', 'accelerometer',
                    '原子力显微镜', '力学', '压力', 'force', 'strain', '应力'],
        'measurements': ['force', 'pressure', 'displacement', 'strain'],
    },
    'thermal': {
        'name': '热学传感器',
        'keywords': ['thermometer', 'thermal camera', 'calorimeter', 'dsc',
                    '温度', '热像', '热力学', 'temperature', 'heat', '热量'],
        'measurements': ['temperature', 'heat flow', 'enthalpy'],
    },
    'chemical': {
        'name': '化学传感器',
        'keywords': ['ph meter', 'gas sensor', 'ion selective', 'biosensor',
                    'ph', '气体检测', '离子', '化学检测', '浓度'],
        'measurements': ['concentration', 'pH', 'ion activity', 'gas partial pressure'],
    },
    'sequencing': {
        'name': '测序传感器',
        'keywords': ['ngs', 'sequencer', 'sanger', 'single-cell',
                    '测序', '测序仪', 'rna-seq', 'dna-seq', '基因组', '转录组',
                    'scrna', 'bulk sequencing', '测序数据'],
        'measurements': ['sequence reads', 'coverage', 'gene expression'],
    },
    'mass_spectrometry': {
        'name': '质谱传感器',
        'keywords': ['mass spectrometry', 'lc-ms', 'gc-ms', 'ms',
                    '质谱', '色谱', 'mass spec', 'proteomics', '代谢组'],
        'measurements': ['mass', 'm/z', 'abundance', 'fragmentation'],
    },
}


# ==================== 伪科学模式库 ====================

PSEUDOSCIENCE_PATTERNS = {
    'quantum_magic': [
        '量子共振', 'quantum resonance', '量子能量', 'quantum energy healing',
        '量子治愈', 'quantum healing', '量子意识', 'quantum consciousness',
        '量子场治疗', 'quantum field therapy', '量子波', 'quantum wave therapy',
    ],
    'energy_field': [
        '生物场', 'biofield', '能量场', 'energy field',
        '气场', 'aura', '人体能量场', 'human energy field',
        '能量扫描', 'energy scan', '能量平衡', 'energy balance',
    ],
    'resonance_therapy': [
        '共振治疗', 'resonance therapy', '频率治愈', 'frequency healing',
        '振动治愈', 'vibration healing', '能量共振', 'energy resonance',
    ],
    'consciousness_field': [
        '意识探测', 'consciousness detection', '意念影响', 'thought influence',
        '意念治疗', 'thought therapy', '远端意识', 'remote consciousness',
        '意识干扰', 'consciousness interference', '心灵感应', 'telepathy',
    ],
    'supernatural': [
        '超自然', 'supernatural', '灵性治疗', 'spiritual healing',
        '神秘力量', 'mystical power', '玄学', 'metaphysics healing',
    ],
    'time_reversal': [
        '时间逆转', 'time reversal', '逆熵', 'negative entropy',
        '时间穿越', 'time travel', '跨时空', 'cross-temporal',
        '逆转时间', 'reverse time',
    ],
    'energy_violation': [
        '永动', 'perpetual', '无限能量', 'infinite energy',
        '能量守恒违反', 'violate energy conservation',
        '零能量', 'zero energy consumption',
    ],
}


# ==================== 物理公理锚定规则库 ====================

PHYSICAL_AXIOM_CHECKS = {
    'signal_capture': {
        'name': '信号捕获',
        'required_patterns': [
            r'(sensor|探测器|传感器|detector|measurement device)',
            r'(spectrometer|光谱|nmr|ct|pet|mri|ultrasound|成像)',
            r'(sequencing|测序|测序仪|sequencer|rna-seq|dna)',
            r'(microscope|显微镜|imaging|荧光|fluorescence)',
            r'(electrode|电极|patch|贴片|probe|探针)',
            r'(mass spectrometry|质谱|lc-ms|gc-ms)',
            r'(pcr|qpcr|western blot|elisa|流式细胞|flow cytometry)',
            # V7.4-F 新增：临床数据源作为信号捕获方式
            r'(uk biobank|biobank|电子病历|ehr|electronic health record)',
            r'(database|数据库|dataset|数据集|data source|数据源)',
            r'(clinical data|临床数据|health record|健康记录)',
            r'(registry|登记|survey|调查问卷|questionnaire)',
            r'(omics|组学|multi-omics|多组学|genomics|基因组)',
        ],
        'failure_message': '缺乏信号捕获机制：未指定物理传感器/探测器或数据源',
        'weight': 0.35,  # 最高权重
    },
    'energy_conversion': {
        'name': '能量转换',
        'required_patterns': [
            r'(energy|能量|power|功率|watt|joule|calorie)',
            r'(binding energy|结合能|binding affinity|亲和力|kd)',
            r'(thermodynamics|热力学|entropy|熵|enthalpy|焓)',
            r'(conversion|转换|transform|变换|efficiency|效率)',
            r'(interaction|相互作用|binding|结合|docking)',
        ],
        'forbidden_patterns': [
            r'(能量无限|infinite energy|永动|perpetual)',
            r'(负熵|negative entropy|逆熵|时间逆转|time reversal)',
            r'(能量共振治疗|energy resonance therapy)',
        ],
        'failure_message': '能量转换逻辑缺失或违反能量守恒定律',
        'weight': 0.25,
    },
    'effect_measurement': {
        'name': '效应度量',
        'required_patterns': [
            r'(outcome|结局|endpoint|终点|指标|indicator|metric)',
            r'(survival|生存率|mortality|死亡率|response rate|响应率)',
            r'(biomarker|生物标志物|gene expression|基因表达|protein level)',
            r'(clinical|临床|patient|患者|cohort|队列|trial|试验)',
            r'(statistical|统计|significance|显著性|p-value|confidence)',
            r'(concentration|浓度|level|水平|expression|表达)',
            r'(binding|结合|affinity|亲和力|kd|ic50|ec50)',
            # V7.4-F 新增：临床研究关键词
            r'(risk|风险|prediction|预测|assessment|评估|screening|筛查)',
            r'(diabetes|糖尿病|cancer|癌症|disease|疾病|health|健康)',
            r'(biobank|cohort|队列|population|人群|sample|样本)',
            r'(model|模型|xgboost|机器学习|machine learning|ai)',
        ],
        'failure_message': '效应度量机制缺失：未指定可量化的生物/临床指标',
        'weight': 0.25,
    },
    'experimental_path': {
        'name': '实验验证路径',
        'required_patterns': [
            r'(experiment|实验|study|研究|trial|试验|protocol|方案)',
            r'(sample|样本|n=|样本量|cohort size|队列规模)',
            r'(control|对照|placebo|安慰剂|randomization|随机)',
            r'(validation|验证|test|测试|verify|校验|benchmark)',
            r'(in vitro|体外|in vivo|体内|cell line|细胞系|animal model)',
            # V7.4-F 新增：临床研究关键词
            r'(uk biobank|biobank|队列|cohort|population|人群)',
            r'(data|数据|dataset|数据集|analysis|分析)',
            r'(study|研究|investigate|调查|examine|检验)',
        ],
        'forbidden_patterns': [
            r'(无需实验|no experiment needed|无法验证|cannot be verified)',
            r'(理论推导即真理|theory is truth|超越实验|beyond experiment)',
        ],
        'failure_message': '实验验证路径缺失：无法设计可执行的实验方案',
        'weight': 0.15,
    },
}


# ==================== 检测结果数据类 ====================

@dataclass
class PhysicalAnchorResult:
    """
    物理锚定检测结果（V7.5 凤凰协议增强版）

    核心变更：
    - 物理公理冲突时不直接拦截
    - 提供替代路径建议和重写指令
    - 判断冲突是否可恢复
    """
    passed: bool
    failure_reason: str
    missing_elements: List[str] = field(default_factory=list)
    pseudoscience_type: Optional[PseudoscienceType] = None
    pseudoscience_patterns_detected: List[str] = field(default_factory=list)
    sensors_detected: List[str] = field(default_factory=list)
    measurements_detected: List[str] = field(default_factory=list)
    suggested_fix: str = ""
    score: float = 0.0  # 0-1 评分

    # ===== V7.5 凤凰协议新增字段 =====
    is_recoverable: bool = True                     # 是否可恢复（有替代路径）
    alternative_path_suggestions: List[Dict] = field(default_factory=list)  # 替代路径列表
    rewrite_instruction: str = ""                   # 重写指令（注入 PI Agent）
    phoenix_state: str = "UNKNOWN"                  # 凤凰协议状态建议


# ==================== 伪科学检测引擎 ====================

class PseudoscienceDetector:
    """
    V7.5 凤凰协议伪科学检测引擎

    核心方法：
    1. perform_physical_anchor_check() - 物理公理锚定检测（凤凰协议版）
    2. detect_pseudoscience_patterns() - 伪科学模式检测
    3. detect_sensors() - 物理传感器检测
    4. generate_rejection_reason() - 生成科学拒绝原因

    V7.5 核心变更：
    - 检测到伪科学模式时，不直接拦截
    - 自动调用 AlternativePathGenerator 生成替代路径
    - 判断是否可恢复，提供 rewrite_instruction
    """

    def __init__(self):
        """初始化检测引擎"""
        # 导入替代路径生成器
        try:
            from .alternative_path_generator import AlternativePathGenerator
            self.path_generator = AlternativePathGenerator()
            logger.info("[V7.5] PseudoscienceDetector 初始化完成（凤凰协议版，替代路径生成器已装载）")
        except ImportError:
            self.path_generator = None
            logger.warning("[V7.5] 替代路径生成器导入失败，凤凰协议降级运行")

    def perform_physical_anchor_check(self, hypothesis_text: str) -> PhysicalAnchorResult:
        """
        执行物理公理锚定检测

        检测顺序：
        1. 伪科学模式检测（立即拒绝）
        2. 物理传感器检测
        3. 四要素验证：信号捕获 → 能量转换 → 效应度量 → 实验验证

        Returns:
            PhysicalAnchorResult: 检测结果
        """
        hypothesis_lower = hypothesis_text.lower()
        missing_elements = []
        sensors_detected = []
        measurements_detected = []
        pseudoscience_patterns_detected = []
        detected_pseudoscience = None

        # ==================== Step 1: 伪科学模式检测 ====================
        for ptype, patterns in PSEUDOSCIENCE_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in hypothesis_lower:
                    pseudoscience_patterns_detected.append(pattern)
                    try:
                        detected_pseudoscience = PseudoscienceType(ptype)
                    except ValueError:
                        detected_pseudoscience = PseudoscienceType.SUPERNATURAL

        # 如果检测到伪科学模式，尝试生成替代路径（凤凰协议核心变更）
        if pseudoscience_patterns_detected:
            # ===== V7.5 凤凰协议：不直接拦截，尝试生成替代路径 =====
            alternative_paths = []
            is_recoverable = True
            rewrite_instruction = ""

            if self.path_generator:
                # 调用替代路径生成器
                alternative_paths, is_recoverable = self.path_generator.generate_alternative_paths(
                    pseudoscience_type=detected_pseudoscience,
                    hypothesis_text=hypothesis_text,
                    detected_patterns=pseudoscience_patterns_detected
                )

                # 如果可恢复，生成重写指令
                if is_recoverable and alternative_paths:
                    rewrite_instruction = self.path_generator.generate_rewrite_instruction(
                        alternative_paths=alternative_paths,
                        original_hypothesis=hypothesis_text,
                        current_version="v1.0"
                    )

            # 转换替代路径为字典格式
            alternative_path_dicts = [
                {
                    'original_pattern': path.original_pattern,
                    'scientific_replacement': path.scientific_replacement,
                    'sensor_type': path.sensor_type,
                    'measurement_method': path.measurement_method,
                    'confidence': path.confidence,
                    'rationale': path.rationale,
                }
                for path in alternative_paths
            ]

            # 判断凤凰协议状态
            phoenix_state = "PHOENIX_REWRITE" if is_recoverable else "HARD_FAILURE"

            return PhysicalAnchorResult(
                passed=False,
                failure_reason=f"检测到伪科学模式: {pseudoscience_patterns_detected[0]}",
                missing_elements=['伪科学术语需要替换为科学测量手段'],
                pseudoscience_type=detected_pseudoscience,
                pseudoscience_patterns_detected=pseudoscience_patterns_detected,
                sensors_detected=sensors_detected,
                measurements_detected=measurements_detected,
                suggested_fix=self._generate_pseudoscience_fix(detected_pseudoscience),
                score=0.0,
                # V7.5 凤凰协议新增字段
                is_recoverable=is_recoverable,
                alternative_path_suggestions=alternative_path_dicts,
                rewrite_instruction=rewrite_instruction,
                phoenix_state=phoenix_state
            )

        # ==================== Step 2: 物理传感器检测 ====================
        for sensor_type, registry in PHYSICS_SENSOR_REGISTRY.items():
            for keyword in registry['keywords']:
                if keyword.lower() in hypothesis_lower:
                    sensors_detected.append(f"{registry['name']}: {keyword}")
                    for measurement in registry['measurements']:
                        if measurement.lower() in hypothesis_lower:
                            measurements_detected.append(measurement)

        # ==================== Step 3: 四要素验证 ====================
        total_score = 0.0

        for element_name, rules in PHYSICAL_AXIOM_CHECKS.items():
            element_passed = False
            element_score = 0.0

            # 检查必需模式
            for pattern in rules['required_patterns']:
                if re.search(pattern, hypothesis_lower, re.IGNORECASE):
                    element_passed = True
                    element_score = rules['weight']
                    break

            # 检查禁止模式（能量转换元素）
            if 'forbidden_patterns' in rules:
                for pattern in rules['forbidden_patterns']:
                    if re.search(pattern, hypothesis_lower, re.IGNORECASE):
                        element_passed = False
                        element_score = 0.0
                        missing_elements.append(f"{element_name}: 检测到禁止模式")
                        break

            if not element_passed:
                missing_elements.append(f"{element_name}: {rules['failure_message']}")

            total_score += element_score

        # ==================== Step 4: 综合判��� ====================
        # 有传感器的情况下，即使部分要素缺失也可以通过（宽容原则）
        if sensors_detected:
            # 有传感器加分
            total_score += 0.15 * len(sensors_detected)

        # 如果缺失超过2个关键要素且无传感器，拒绝
        if len(missing_elements) >= 3 and not sensors_detected:
            return PhysicalAnchorResult(
                passed=False,
                failure_reason=f"物理公理锚定失败: 缺失 {len(missing_elements)} 个关键要素且无物理传感器",
                missing_elements=missing_elements,
                pseudoscience_type=PseudoscienceType.NO_SENSOR if not sensors_detected else None,
                sensors_detected=sensors_detected,
                measurements_detected=measurements_detected,
                suggested_fix=self._generate_missing_elements_fix(missing_elements),
                score=min(1.0, total_score)
            )

        # 信号捕获缺失但其他要素完整 → 部分通过（需要补充传感器）
        if 'signal_capture' in [elem.split(':')[0] for elem in missing_elements]:
            if len(missing_elements) == 1 and measurements_detected:
                # 有度量机制但未明确传感器 → 给予警告性通过
                return PhysicalAnchorResult(
                    passed=True,
                    failure_reason="",
                    missing_elements=['建议明确指定物理传感器类型'],
                    sensors_detected=sensors_detected,
                    measurements_detected=measurements_detected,
                    suggested_fix="建议补充具体的物理传感器信息（如：测序仪型号、光谱仪类型等）",
                    score=max(0.5, total_score)
                )
            elif not sensors_detected:
                return PhysicalAnchorResult(
                    passed=False,
                    failure_reason="信号捕获机制缺失：未指定物理传感器/探测器",
                    missing_elements=missing_elements,
                    pseudoscience_type=PseudoscienceType.NO_SENSOR,
                    sensors_detected=sensors_detected,
                    suggested_fix=self._generate_sensor_fix(),
                    score=total_score
                )

        # 通过检测
        return PhysicalAnchorResult(
            passed=True,
            failure_reason="",
            missing_elements=missing_elements,
            sensors_detected=sensors_detected,
            measurements_detected=measurements_detected,
            suggested_fix="",
            score=min(1.0, total_score)
        )

    def detect_sensors(self, hypothesis_text: str) -> List[str]:
        """
        检测假说中的物理传感器

        Returns:
            List[str]: 检测到的传感器列表
        """
        hypothesis_lower = hypothesis_text.lower()
        sensors = []

        for sensor_type, registry in PHYSICS_SENSOR_REGISTRY.items():
            for keyword in registry['keywords']:
                if keyword.lower() in hypothesis_lower:
                    sensors.append(f"{registry['name']}: {keyword}")

        return sensors

    def detect_pseudoscience_patterns(self, hypothesis_text: str) -> Tuple[bool, List[str]]:
        """
        检测伪科学模式

        Returns:
            Tuple[bool, List[str]]: (是否检测到, 检测到的模式列表)
        """
        hypothesis_lower = hypothesis_text.lower()
        detected = []

        for ptype, patterns in PSEUDOSCIENCE_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in hypothesis_lower:
                    detected.append(pattern)

        return len(detected) > 0, detected

    def _generate_pseudoscience_fix(self, pseudoscience_type: PseudoscienceType) -> str:
        """生成伪科学修正建议"""
        fixes = {
            PseudoscienceType.QUANTUM_MAGIC: """
建议修正方向：
1. 将"量子共振"替换为具体的量子测量手段（如：量子点荧光传感、量子干涉测量）
2. 指定实际物理传感器（如：SPR、荧光光谱仪、电化学传感器）
3. 给出可量化的测量指标（如：荧光强度、结合常数Kd、IC50/EC50）
""",
            PseudoscienceType.ENERGY_FIELD: """
建议修正方向：
1. 将"能量场"替换为具体的能量形式（如：电磁场、热能、机械能）
2. 指定能量测量设备（如：光谱仪、热像仪、力学传感器）
3. 给出能量转换效率的定量计算方法
""",
            PseudoscienceType.RESONANCE_THERAPY: """
建议修正方向：
1. 将"共振治疗"替换为具体的物理干预手段（如：射频消融、超声治疗）
2. 指定共振频率的具体数值和测量方法
3. 给出临床效应的可量化指标（如：肿瘤体积变化、生存率）
""",
            PseudoscienceType.CONSCIOUSNESS_FIELD: """
建议修正方向：
"意识探测"缺乏物理实现路径，建议：
1. 改用神经科学测量手段（如：EEG、fMRI、脑电信号）
2. 指定信号捕获设备（如：脑电极、神经探针）
3. 给出神经信号的量化指标（如：脑电波频率、神经放电率）
""",
            PseudoscienceType.TIME_REVERSAL: """
建议修正方向：
"跨时空"违反物理定律，建议：
1. 改用时间序列分析（temporal analysis）而非"时间逆转"
2. 使用纵向队列研究（longitudinal cohort study）
3. 指定时间维度的测量方式（如：随访时间点、生存时间）
""",
            PseudoscienceType.NO_SENSOR: """
建议修正方向：
请明确指定物理传感器/探测器：
- 生物分子测量：测序仪、质谱仪、显微镜
- 信号检测：电极、光谱仪、荧光检测器
- 临床指标：影像设备（CT/MRI/PET）、生化分析仪
""",
        }
        return fixes.get(pseudoscience_type, "请引入物理传感器和可量化的测量指标")

    def _generate_missing_elements_fix(self, missing_elements: List[str]) -> str:
        """生成缺失要素修正建议"""
        fix_text = """
物理公理锚定修正建议：
"""
        for elem in missing_elements[:3]:
            fix_text += f"- {elem}\n"

        fix_text += """
请补充上述缺失的物理公理要素，确保假设具备实验可验证性。
"""
        return fix_text

    def _generate_sensor_fix(self) -> str:
        """生成传感器缺失修正建议"""
        return """
信号捕获机制缺失修正建议：
请明确指定以下任一类别的物理传感器：

1. 生物分子层面：
   - 测序仪（NGS/RNA-seq/单细胞测序）
   - 质谱仪（LC-MS/GC-MS）
   - 显微镜（荧光显微镜/电子显微镜）

2. 信号检测层面：
   - 光学传感器（光谱仪/SPR/荧光检测器）
   - 电学传感器（电极/电化学工作站）
   - 热学传感器（温度计/热像仪）

3. 临床影像层面：
   - CT/MRI/PET/超声
   - 内窥镜
   - 心电图/脑电图

4. 生化分析层面：
   - PCR仪
   - ELISA检测
   - 流式细胞仪
"""


# ==================== 便捷函数 ====================

_global_detector: Optional[PseudoscienceDetector] = None


def get_pseudoscience_detector() -> PseudoscienceDetector:
    """获取全局检测器实例"""
    global _global_detector
    if _global_detector is None:
        _global_detector = PseudoscienceDetector()
    return _global_detector


def check_physical_anchor(hypothesis_text: str) -> PhysicalAnchorResult:
    """
    检查物理公理锚定（便捷函数）

    Args:
        hypothesis_text: 假说文本

    Returns:
        PhysicalAnchorResult: 检测结果
    """
    detector = get_pseudoscience_detector()
    return detector.perform_physical_anchor_check(hypothesis_text)


# ==================== 测试用例 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V7.4-F 伪科学检测引擎测试")
    print("=" * 70)

    detector = PseudoscienceDetector()

    test_cases = [
        # 伪科学输入（应被拒绝）
        ("量子引力生物共振治愈癌症", False, PseudoscienceType.QUANTUM_MAGIC),
        ("量子意识场探测患者健康状态", False, PseudoscienceType.CONSCIOUSNESS_FIELD),
        ("能量场扫描诊断疾病", False, PseudoscienceType.ENERGY_FIELD),
        ("跨时空生物分子信号实时监测", False, PseudoscienceType.TIME_REVERSAL),
        ("远端意识干扰建模研究", False, PseudoscienceType.CONSCIOUSNESS_FIELD),

        # 有效科学假说（应通过）
        ("使用单细胞RNA测序(scRNA-seq)分析肿瘤微环境", True, None),
        ("基于AlphaFold3预测蛋白质结构并用SPR验证结合亲和力", True, None),
        ("利用UK Biobank数据构建XGBoost模型预测糖尿病风险", True, None),
        ("通过流式细胞术检测免疫细胞亚群变化", True, None),
        ("使用质谱分析代谢物浓度变化", True, None),

        # 边缘案例（部分通过）
        ("研究基因表达对癌症的影响", True, None),  # 有度量机制但无明确传感器
    ]

    print("\n测试结果：\n")

    for text, expected_pass, expected_type in test_cases:
        result = detector.perform_physical_anchor_check(text)

        pass_match = "[OK]" if result.passed == expected_pass else "[FAIL]"
        type_match = ""
        if expected_type:
            type_match = "[OK]" if result.pseudoscience_type == expected_type else "[FAIL]"
        else:
            type_match = "[OK]" if result.pseudoscience_type is None else "[WARN]"

        print(f"{pass_match} Input: {text[:50]}...")
        print(f"   Expected: pass={expected_pass}, type={expected_type}")
        print(f"   Actual: pass={result.passed}, type={result.pseudoscience_type} {type_match}")
        if not result.passed:
            print(f"   Reason: {result.failure_reason}")
            print(f"   Fix: {result.suggested_fix[:100]}...")
        if result.sensors_detected:
            print(f"   Sensors: {result.sensors_detected}")
        print()

    print("=" * 70)
    print("测试完成")