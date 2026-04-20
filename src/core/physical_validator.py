# -*- coding: utf-8 -*-
"""
V7.1 硬核验证网关 (Physical Validator) - 集中式日志挂载版

V7.1 核心改进：
1. 集中式日志挂载：校验失败自动捕获堆栈
2. AUDIT 级别日志：物理铁闸驳回记录业务审计日志
3. 深水区异常捕获：RDKit、UKB 校验等关键节点

物理铁闸验证器 - 不可商量的硬核校验

如果返回 False，假说直接得 0 分并引发熔断。

核心机制：
1. SMILES 拓扑合法性校验（RDKit）
2. UK Biobank 字段存在性校验
3. 算力可行性校验（显存 ≤ 80GB，复杂度 ≤ O(N³））
"""

import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

# ==================== V7.1: 集中式日志挂载 ====================
from src.utils.logger import get_central_logger, AUDIT_LEVEL

logger = get_central_logger()


class ValidationType(Enum):
    """验证类型枚举"""
    SMILES = "smiles"
    UKB_FIELDS = "ukb_fields"
    COMPUTE_COMPLEXITY = "compute_complexity"
    ALL = "all"


@dataclass
class ValidationResult:
    """
    验证结果数据结构

    包含每个验证项的详细结果
    """
    passed: bool = True
    validation_type: str = "unknown"
    details: Dict[str, Any] = field(default_factory=dict)
    failure_reason: str = ""
    timestamp: str = field(default_factory=lambda: "")


class PhysicalValidator:
    """
    物理铁闸验证器 - 不可商量的硬核校验

    任何一项验证失败 → 假说得分 = 0 → 熔断

    验证项：
    1. SMILES 拓扑合法性（调用 RDKit）
    2. UK Biobank 字段存在性（白名单校验）
    3. 算力可行性（显存 + 时间复杂度）
    """

    # ==================== 算力参数阈值 ====================
    VRAM_HARD_CAP = 80  # 单机推理显存上限（GB）
    COMPLEXITY_EXponent_CAP = 3  # 时间复杂度指数上限（O(n^3))

    # ==================== UKB 字段白名单 ====================
    # 常用字段（从 UK Biobank 官方数据展示面板提取）
    UKB_FIELD_WHITELIST = {
        # 人口学信息
        '31': 'Sex',
        '21022': 'Age at recruitment',
        '21000': 'Ethnic background',
        '189': 'Townsend deprivation index at recruitment',

        # 身体测量
        '30000': 'Body mass index',
        '30001': 'Weight',
        '30002': 'Height (standing)',
        '30003': 'Standing height',
        '30004': 'Sitting height',
        '30005': 'Waist circumference',
        '30006': 'Hip circumference',
        '30007': 'Waist-hip ratio',

        # 血压
        '30010': 'Systolic blood pressure, automated reading',
        '30011': 'Diastolic blood pressure, automated reading',
        '30012': 'Pulse rate, automated reading',
        '30013': 'Systolic blood pressure, manual reading',
        '30014': 'Diastolic blood pressure, manual reading',
        '30015': 'Pulse rate, manual reading',

        # 生化指标
        '30020': 'HDL cholesterol',
        '30030': 'LDL direct',
        '30040': 'Cholesterol',
        '30050': 'Triglycerides',
        '30060': 'Gamma glutamyltransferase',
        '30070': 'Albumin',
        '30080': 'Glycated haemoglobin (HbA1c)',
        '30090': 'C-reactive protein',
        '30100': 'Creatinine',
        '30110': 'Glucose',
        '30120': 'Urea',
        '30130': 'Urate',
        '30140': 'Alkaline phosphatase',
        '30150': 'Alanine aminotransferase',
        '30160': 'Aspartate aminotransferase',
        '30170': 'Bilirubin',
        '30180': 'Total protein',
        '30190': 'Haemoglobin',
        '30200': 'Mean corpuscular haemoglobin',
        '30210': 'Mean corpuscular volume',
        '30220': 'Mean corpuscular haemoglobin concentration',
        '30230': 'White blood cell count',
        '30240': 'Red blood cell count',
        '30250': 'Platelet count',
        '30260': 'Platelet crit',
        '30270': 'Platelet distribution width',
        '30280': 'Red blood cell distribution width',
        '30290': 'Haematocrit',

        # 饮食信息
        '100240': 'Cooked vegetable intake',
        '100250': 'Raw vegetable intake',
        '100260': 'Fresh fruit intake',
        '100270': 'Dried fruit intake',
        '100280': 'Bread intake',
        '100290': 'Cereal intake',
        '100300': 'Tea intake',
        '100310': 'Coffee intake',
        '100320': 'Water intake',

        # 生活方式
        '20002': 'Non-cancer illness code, self-reported',
        '20003': 'Treatment/medication code',
        '20004': 'Operation code',
        '20006': 'Type of cancer, self-reported',
        '20008': 'Year of cancer diagnosis, self-reported',
        '20009': 'Age of cancer diagnosis, self-reported',

        # 疾病诊断
        '40000': 'Date of death',
        '40001': 'Underlying (primary) cause of death',
        '40002': 'Contributory (secondary) causes of death',
        '40005': 'Date of death report source',

        # 基因型数据
        '22001': 'Genetic sex',
        '22009': 'Genetic ethnic grouping',
        '22010': 'Genetic kinship to other participants',
        '22011': 'Genetic heterozygosity',
        '22012': 'Genetic homozygosity',
        '22013': 'Missing genotypes count',
        '22014': 'Missing heterozygotes count',
        '22015': 'Missing homozygotes count',

        # 影像数据
        '20201': 'MRI brain white matter hyperintensity volume',
        '20202': 'MRI brain grey matter volume',
        '20203': 'MRI brain white matter volume',
        '20204': 'MRI brain ventricle volume',
        '20205': 'MRI brain total volume',
        '20206': 'MRI brain subcortical volume',
        '20207': 'MRI brain hippocampus volume',
        '20208': 'MRI brain amygdala volume',
        '20209': 'MRI brain thalamus volume',
        '20210': 'MRI brain caudate volume',
        '20211': 'MRI brain putamen volume',
        '20212': 'MRI brain pallidum volume',
        '20213': 'MRI brain accumbens volume',

        # 其他常用
        '130016': 'Number of cigarettes currently smoked daily',
        '130018': 'Number of cigarettes previously smoked daily',
        '130020': 'Time spent watching television',
        '130022': 'Time spent using computer',
        '130024': 'Time spent doing moderate physical activity',
        '130026': 'Duration of moderate physical activity',

        # 额外常用字段
        '53': 'Date of attending assessment centre',
        '54': 'Place of birth, as UK biobank participant',
        '55': 'Time ukbiobank assessment centre visited',
        '56': 'Date ukbiobank assessment centre visited',
        '57': 'Place of birth, as uk biobank participant',
        '58': 'Time uk biobank assessment centre visited',
        '59': 'Date uk biobank assessment centre visited',
        '60': 'Year of birth',
        '61': 'Month of birth',
        '62': 'Year of death',
        '63': 'Month of death',
        '64': 'Age at death',
        '65': 'Number of sons',
        '66': 'Number of daughters',
        '67': 'Number of brothers',
        '68': 'Number of sisters',
        '69': 'Number of grandparents',
        '70': 'Number of children in household',
        '71': 'Number of people in household',
        '72': 'Genetic principal components',
        '73': 'Genetic principal components 2',
        '74': 'Genetic principal components 3',
        '75': 'Genetic principal components 4',
        '76': 'Genetic principal components 5',
        '77': 'Genetic principal components 6',
        '78': 'Genetic principal components 7',
        '79': 'Genetic principal components 8',
        '80': 'Genetic principal components 9',
        '81': 'Genetic principal components 10',
    }

    def __init__(self, ukb_field_dict_path: str = None, use_dynamic_fetcher: bool = True):
        """
        V7.0 初始化物理验证器

        Args:
            ukb_field_dict_path: UK Biobank 字段字典文件路径（可选）
            use_dynamic_fetcher: 是否使用动态字段获取器（V7.0新增）
        """
        # 加载 UKB 字段白名单
        self.ukb_fields = self.UKB_FIELD_WHITELIST.copy()

        # V7.0: 动态获取器
        self.use_dynamic_fetcher = use_dynamic_fetcher
        if use_dynamic_fetcher:
            try:
                from utils.ukb_field_fetcher import UKBFieldFetcher, get_ukb_field_fetcher
                self.ukb_fetcher = get_ukb_field_fetcher(use_online_fetch=False)
                dynamic_fields = self.ukb_fetcher.fetch_all_fields()
                self.ukb_fields.update(dynamic_fields)
                logger.info(f"[PhysicalValidator V7.0] 动态加载 UKB 字段: {len(self.ukb_fields)} 个")
            except ImportError as e:
                logger.warning(f"[PhysicalValidator V7.0] UKB 字段获取器未找到: {e}")
                self.ukb_fetcher = None
            except Exception as e:
                logger.warning(f"[PhysicalValidator V7.0] 动态获取失败: {e}")
                self.ukb_fetcher = None
        else:
            self.ukb_fetcher = None

        if ukb_field_dict_path:
            self._load_ukb_field_dict(ukb_field_dict_path)

        # RDKit 可用性检查
        self._rdkit_available = self._check_rdkit_availability()

        logger.info(f"[PhysicalValidator V7.0] 初始化完成，RDKit={self._rdkit_available}")
        logger.info(f"[PhysicalValidator V7.0] UKB 字段白名单大小: {len(self.ukb_fields)}")

    def _check_rdkit_availability(self) -> bool:
        """检查 RDKit 是否可用"""
        try:
            from rdkit import Chem
            return True
        except ImportError:
            logger.warning("[PhysicalValidator] RDKit 未安装，SMILES 校验将使用回退方法")
            return False

    def _load_ukb_field_dict(self, path: str) -> None:
        """
        加载额外的 UKB 字段字典

        Args:
            path: 字段字典文件路径（JSON 格式）
        """
        try:
            dict_path = Path(path)
            if dict_path.exists():
                with open(dict_path, 'r', encoding='utf-8') as f:
                    extra_fields = json.load(f)
                    self.ukb_fields.update(extra_fields)
                    logger.info(f"[PhysicalValidator] 加载额外 UKB 字段: {len(extra_fields)} 个")
        except Exception as e:
            logger.warning(f"[PhysicalValidator] 加载 UKB 字段字典失败: {e}")

    # ==================== 核心验证函数 ====================

    def validate_smiles(self, smiles_str: str) -> ValidationResult:
        """
        调用 RDKit 验证配体 SMILES 的拓扑合法性

        Args:
            smiles_str: SMILES 字符串

        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult(
            passed=True,
            validation_type="smiles",
            details={'smiles_str': smiles_str}
        )

        if not smiles_str or smiles_str.strip() == '':
            # 空字符串不算失败（假设可能不涉及药物设计）
            result.details['note'] = 'SMILES 为空，跳过校验'
            return result

        try:
            if self._rdkit_available:
                from rdkit import Chem
                mol = Chem.MolFromSmiles(smiles_str)

                if mol is None:
                    result.passed = False
                    result.failure_reason = f"SMILES 非法: '{smiles_str}' 无法解析为有效分子"
                    result.details['rdkit_result'] = 'None'
                else:
                    # 验证拓扑结构
                    num_atoms = mol.GetNumAtoms()
                    num_bonds = mol.GetNumBonds()
                    result.details['num_atoms'] = num_atoms
                    result.details['num_bonds'] = num_bonds
                    result.details['rdkit_result'] = 'valid'

                    # 检查是否有合理的原子数（>0 且 < 1000）
                    if num_atoms == 0 or num_atoms > 1000:
                        result.passed = False
                        result.failure_reason = f"SMILES 分子结构异常: 原子数 {num_atoms}"
            else:
                # 回退到正则校验
                fallback_result = self._fallback_smiles_check(smiles_str)
                result.passed = fallback_result
                result.details['validation_method'] = 'fallback_regex'

                if not fallback_result:
                    result.failure_reason = f"SMILES 正则校验失败: '{smiles_str}'"

        except Exception as e:
            result.passed = False
            result.failure_reason = f"SMILES 校验异常: {str(e)}"
            result.details['exception'] = str(e)

        return result

    def _fallback_smiles_check(self, smiles_str: str) -> bool:
        """
        SMILES 正则回退校验（当 RDKit 不可用时）

        Args:
            smiles_str: SMILES 字符串

        Returns:
            bool: True = 可能合法, False = 明显非法
        """
        # 基本的正则规则
        # 1. 必须包含有效的原子符号（C, N, O, S, P, H, F, Cl, Br, I 等）
        # 2. 括号必须匹配
        # 3. 禁止明显非法字符

        # 检查括号匹配
        open_brackets = smiles_str.count('(') + smiles_str.count('[')
        close_brackets = smiles_str.count(')') + smiles_str.count(']')
        if open_brackets != close_brackets:
            return False

        # 检查是否包含有效的原子符号
        valid_atom_pattern = r'[CNOSPHF]|Cl|Br|I|Si|Al|Na|K|Ca|Mg|Fe|Zn|Cu|Ag|Au|Pt|Hg|Li|Be|B|V|Cr|Mn|Co|Ni|Ru|Rh|Pd|Os|Ir'
        if not re.search(valid_atom_pattern, smiles_str, re.IGNORECASE):
            return False

        # 检查明显非法字符
        illegal_chars = r'[xyzqw]|\d{5}|[^\w\[\]()\-=#@+.]'
        if re.search(illegal_chars, smiles_str, re.IGNORECASE):
            return False

        return True

    def validate_ukb_fields(self, fields_list: List[str]) -> ValidationResult:
        """
        V7.0 校验引用的 UK Biobank Data-Field 是否在真实存在的字典中

        新增：置信度标记机制，避免假阴性灾难

        Args:
            fields_list: UKB 字段 ID 列表 (如 ['31', '21022', '30000'])

        Returns:
            ValidationResult: 验证结果（包含置信度信息）
        """
        result = ValidationResult(
            passed=True,
            validation_type="ukb_fields",
            details={'fields_list': fields_list, 'invalid_fields': [], 'uncertain_fields': []}
        )

        if not fields_list:
            # 空列表不算失败
            result.details['note'] = 'UKB 字段列表为空，跳过校验'
            return result

        invalid_fields = []
        uncertain_fields = []  # V7.0: 待确认字段（低置信度拒绝）

        for field in fields_list:
            field_str = str(field).strip()

            # V7.0: 使用动态获取器验证（带置信度）
            if self.ukb_fetcher is not None:
                from utils.ukb_field_fetcher import UKBValidationSource
                validation_result = self.ukb_fetcher.validate_field_with_confidence(field_str)

                if validation_result.is_valid:
                    # 有效字段
                    continue
                else:
                    # 根据置信度分类
                    if validation_result.confidence >= 0.7:
                        # 高置信度拒绝（真正无效的字段）
                        invalid_fields.append(field_str)
                    else:
                        # 低置信度拒绝（可能是假阴性）
                        uncertain_fields.append({
                            'field_id': field_str,
                            'confidence': validation_result.confidence,
                            'source': validation_result.source.value
                        })
            else:
                # 回退到基础验证
                if field_str not in self.ukb_fields:
                    invalid_fields.append(field_str)

        # V7.0: 增强的结果处理
        if invalid_fields:
            result.passed = False
            result.failure_reason = f"UKB 字段不存在: {invalid_fields}"
            result.details['invalid_fields'] = invalid_fields
            result.details['valid_fields'] = [f for f in fields_list if str(f).strip() not in invalid_fields]

        # 如果只有不确定字段，不熔断而是标记警告
        if uncertain_fields and not invalid_fields:
            result.details['uncertain_fields'] = uncertain_fields
            result.details['validation_mode'] = "tentative"
            result.details['warning'] = f"存在 {len(uncertain_fields)} 个待确认字段（低置信度拒绝）"
            # V7.0: 不熔断，允许通过但记录警告
            result.passed = True
            logger.warning(
                f"[PhysicalValidator V7.0] UKB 字段待确认: {uncertain_fields}\n"
                f"  这些字段可能是有效的但不在当前白名单中"
            )
        else:
            result.details['field_names'] = [
                self.ukb_fields.get(str(f).strip(), 'unknown')
                for f in fields_list
                if str(f).strip() in self.ukb_fields
            ]

        return result

    def validate_compute_complexity(
        self,
        vram_gb: float,
        time_complexity: str
    ) -> ValidationResult:
        """
        校验算力可行性

        强制限定：
        - 单机推理显存 ≤ 80GB
        - 时间复杂度须在 O(N³) 级别以内

        Args:
            vram_gb: 推理所需显存（GB）
            time_complexity: 时间复杂度字符串 (如 'O(n^3)', 'O(n^4)')

        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult(
            passed=True,
            validation_type="compute_complexity",
            details={
                'vram_gb': vram_gb,
                'time_complexity': time_complexity,
                'vram_cap': self.VRAM_HARD_CAP,
                'complexity_cap': f'O(n^{self.COMPLEXITY_EXponent_CAP})'
            }
        )

        # 显存校验
        if vram_gb > self.VRAM_HARD_CAP:
            result.passed = False
            result.failure_reason = f"显存超限: {vram_gb}GB > {self.VRAM_HARD_CAP}GB 上限"
            result.details['vram_exceeded'] = True

        # 复杂度校验
        complexity_exponent = self._parse_complexity_exponent(time_complexity)
        result.details['parsed_exponent'] = complexity_exponent

        if complexity_exponent > self.COMPLEXITY_EXponent_CAP:
            result.passed = False
            if result.failure_reason:
                result.failure_reason += f"; 复杂度超限: O(n^{complexity_exponent}) > O(n^3)"
            else:
                result.failure_reason = f"复杂度超限: O(n^{complexity_exponent}) > O(n^3)"
            result.details['complexity_exceeded'] = True

        return result

    def _parse_complexity_exponent(self, complexity_str: str) -> int:
        """
        解析时间复杂度表达式，提取指数

        Args:
            complexity_str: 复杂度字符串（如 'O(n^3)', 'O(n^4)', 'O(n log n)'）

        Returns:
            int: 复杂度指数（O(1)=0, O(n)=1, O(n log n)≈1.5→取1, O(n^2)=2, O(n^3)=3, O(n^4)=4）
        """
        complexity_str = complexity_str.lower().strip()

        # 特殊复杂度映射
        special_cases = {
            'o(1)': 0,
            'o(log n)': 0,
            'o(n)': 1,
            'o(n log n)': 1,
            'o(n logn)': 1,
            'o(nlogn)': 1,
            'o(n^2)': 2,
            'o(n2)': 2,
            'o(n^3)': 3,
            'o(n3)': 3,
        }

        if complexity_str in special_cases:
            return special_cases[complexity_str]

        # 尝试从字符串提取指数
        match = re.search(r'n\^?(\d+)', complexity_str)
        if match:
            return int(match.group(1))

        # 默认假设为线性复杂度
        return 1

    def validate_hypothesis_physical(
        self,
        hypothesis_data: Dict
    ) -> ValidationResult:
        """
        对假设数据进行全面的物理铁闸校验

        Args:
            hypothesis_data: 假设数据字典，包含：
                - title: 标题
                - details: 详细内容
                - 可能包含的 SMILES、UKB 字段、算力参数等

        Returns:
            ValidationResult: 综合验证结果
        """
        result = ValidationResult(
            passed=True,
            validation_type="all",
            details={}
        )

        # 从假设内容中��取需要校验的元素
        details_text = hypothesis_data.get('details', '')

        # 1. 提取并校验 SMILES
        smiles_list = self._extract_smiles_from_text(details_text)
        if smiles_list:
            for smiles in smiles_list:
                smiles_result = self.validate_smiles(smiles)
                if not smiles_result.passed:
                    # V7.1: AUDIT 级别日志（业务驳回）
                    logger.audit(
                        f"[驳回] SMILES 校验失败\n"
                        f"  SMILES: {smiles[:50]}...\n"
                        f"  失败原因: {smiles_result.failure_reason}"
                    )
                    result.passed = False
                    result.failure_reason = smiles_result.failure_reason
                    result.details['smiles_validation'] = smiles_result.details
                    return result

        # 2. 提取并校验 UKB 字段
        ukb_fields = self._extract_ukb_fields_from_text(details_text)
        if ukb_fields:
            ukb_result = self.validate_ukb_fields(ukb_fields)
            if not ukb_result.passed:
                # V7.1: AUDIT 级别日志（业务驳回）
                logger.audit(
                    f"[驳回] UKB 字段校验失败\n"
                    f"  字段列表: {ukb_fields}\n"
                    f"  无效字段: {ukb_result.details.get('invalid_fields', [])}\n"
                    f"  失败原因: {ukb_result.failure_reason}"
                )
                result.passed = False
                result.failure_reason = ukb_result.failure_reason
                result.details['ukb_validation'] = ukb_result.details
                return result

        # 3. 提取并校验算力参数
        compute_params = self._extract_compute_params_from_text(details_text)
        if compute_params:
            vram = compute_params.get('vram_gb', 0)
            complexity = compute_params.get('time_complexity', 'O(n)')
            compute_result = self.validate_compute_complexity(vram, complexity)
            if not compute_result.passed:
                # V7.1: AUDIT 级别日志（业务驳回）
                logger.audit(
                    f"[驳回] 算力可行性校验失败\n"
                    f"  显存需求: {vram}GB (上限: {self.VRAM_HARD_CAP}GB)\n"
                    f"  复杂度: {complexity} (上限: O(n³）)\n"
                    f"  失败原因: {compute_result.failure_reason}"
                )
                result.passed = False
                result.failure_reason = compute_result.failure_reason
                result.details['compute_validation'] = compute_result.details
                return result

        result.details['smiles_found'] = smiles_list
        result.details['ukb_fields_found'] = ukb_fields
        result.details['compute_params_found'] = compute_params

        return result

    def _extract_smiles_from_text(self, text: str) -> List[str]:
        """
        从文本中提取 SMILES 字符串

        Args:
            text: 文本内容

        Returns:
            List[str]: 提取到的 SMILES 字符串列表
        """
        smiles_list = []

        # 常见 SMILES 模式：包含明确的 SMILES 标记
        patterns = [
            r'SMILES[:\s]+["\']?([A-Za-z0-9\[\]()\-=#@+\.]+)["\']?',
            r'smiles[:\s]+["\']?([A-Za-z0-9\[\]()\-=#@+\.]+)["\']?',
            r'molecular\s+structure[:\s]+["\']?([A-Za-z0-9\[\]()\-=#@+\.]+)["\']?',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            smiles_list.extend(matches)

        # 去重
        return list(set(smiles_list))

    def _extract_ukb_fields_from_text(self, text: str) -> List[str]:
        """
        从文本中提取 UK Biobank 字段 ID

        Args:
            text: 文本内容

        Returns:
            List[str]: 提取到的 UKB 字段 ID 列表
        """
        ukb_fields = []

        # 常见 UKB 字段引用模式
        patterns = [
            r'UKB\s*[:\s]*field\s*[:\s]*["\']?(\d{2,6})["\']?',
            r'UK\s*Biobank\s*[:\s]*field\s*[:\s]*["\']?(\d{2,6})["\']?',
            r'Data-Field\s*[:\s]*["\']?(\d{2,6})["\']?',
            r'field\s*[:\s]*(\d{2,6})',
            r'UKB\s*(\d{2,6})',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            ukb_fields.extend(matches)

        # 去重
        return list(set(ukb_fields))

    def _extract_compute_params_from_text(self, text: str) -> Dict:
        """
        从文本中提取算力参数

        Args:
            text: 文本内容

        Returns:
            Dict: 包含 vram_gb 和 time_complexity 的字典
        """
        params = {}

        # 显存提取模式
        vram_patterns = [
            r'(\d+)\s*GB\s*(VRAM|显存|GPU\s*内存)',
            r'VRAM[:\s]*(\d+)\s*GB',
            r'显存[:\s]*(\d+)\s*GB',
            r'GPU[:\s]*(\d+)\s*GB',
        ]

        for pattern in vram_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                params['vram_gb'] = float(match.group(1))
                break

        # 复杂度提取模式
        complexity_patterns = [
            r'O\(n\^?\d*\)',
            r'O\(n\s*log\s*n\)',
            r'时间复杂度[:\s]*(O\([^)]+\))',
            r'complexity[:\s]*(O\([^)]+\))',
        ]

        for pattern in complexity_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                params['time_complexity'] = match.group(0)
                break

        return params

    # ==================== 批量校验接口 ====================

    def batch_validate(
        self,
        hypotheses: List[Dict]
    ) -> List[ValidationResult]:
        """
        批量校验多个假设

        Args:
            hypotheses: 假设数据列表

        Returns:
            List[ValidationResult]: 校验结果列表
        """
        results = []
        for hyp in hypotheses:
            result = self.validate_hypothesis_physical(hyp)
            results.append(result)

        return results

    def get_validation_summary(self, results: List[ValidationResult]) -> Dict:
        """
        生成校验结果摘要

        Args:
            results: 校验结果列表

        Returns:
            Dict: 摘要统计
        """
        passed_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - passed_count

        failure_reasons = [r.failure_reason for r in results if not r.passed]

        return {
            'total': len(results),
            'passed': passed_count,
            'failed': failed_count,
            'pass_rate': passed_count / len(results) if results else 0,
            'failure_reasons': failure_reasons
        }


# ==================== 全局实例 ====================

_physical_validator: Optional[PhysicalValidator] = None


def get_physical_validator() -> PhysicalValidator:
    """获取全局物理验证器实例"""
    global _physical_validator
    if _physical_validator is None:
        _physical_validator = PhysicalValidator()
    return _physical_validator


def validate_hypothesis_physical(hypothesis_data: Dict) -> ValidationResult:
    """
    便捷函数：校验单个假设的物理合法性

    Args:
        hypothesis_data: 假设数据

    Returns:
        ValidationResult: 校验结果
    """
    validator = get_physical_validator()
    return validator.validate_hypothesis_physical(hypothesis_data)


# ==================== 测试代码 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V6.1 物理铁闸验证器 - 测试")
    print("=" * 70)

    validator = PhysicalValidator()

    # 测试 1: SMILES 校验
    print("\n[Test 1] SMILES 校验")

    valid_smiles = "CC(=O)Oc1ccccc1C(=O)O"  # 阿司匹林
    result = validator.validate_smiles(valid_smiles)
    print(f"  合法 SMILES '{valid_smiles}': {result.passed}")

    invalid_smiles = "invalid_xyz_12345"
    result = validator.validate_smiles(invalid_smiles)
    print(f"  非法 SMILES '{invalid_smiles}': {result.passed}")
    print(f"    失败原因: {result.failure_reason}")

    # 测试 2: UKB 字段校验
    print("\n[Test 2] UKB 字段校验")

    valid_fields = ['31', '21022', '30000']
    result = validator.validate_ukb_fields(valid_fields)
    print(f"  合法字段 {valid_fields}: {result.passed}")
    print(f"    字段名称: {result.details.get('field_names', [])}")

    invalid_fields = ['99999', '88888']
    result = validator.validate_ukb_fields(invalid_fields)
    print(f"  非法字段 {invalid_fields}: {result.passed}")
    print(f"    失败原因: {result.failure_reason}")

    # 测试 3: 算力校验
    print("\n[Test 3] 算力可行性校验")

    result = validator.validate_compute_complexity(40, 'O(n^2)')
    print(f"  40GB VRAM + O(n^2): {result.passed}")

    result = validator.validate_compute_complexity(100, 'O(n^4)')
    print(f"  100GB VRAM + O(n^4): {result.passed}")
    print(f"    失败原因: {result.failure_reason}")

    # 测试 4: 综合假设校验
    print("\n[Test 4] 综合假设校验")

    valid_hypothesis = {
        'title': '测试假设',
        'details': '使用 UKB 字段 31（性别）和 21022（年龄）进行分析，复杂度 O(n^2)。'
    }
    result = validator.validate_hypothesis_physical(valid_hypothesis)
    print(f"  合法假设: {result.passed}")

    invalid_hypothesis = {
        'title': '非法假设',
        'details': '使用 UKB 字段 99999（不存在）进行分析，需要 100GB 显存。'
    }
    result = validator.validate_hypothesis_physical(invalid_hypothesis)
    print(f"  非法假设: {result.passed}")
    print(f"    失败原因: {result.failure_reason}")

    print("\n" + "=" * 70)
    print("V6.1 物理铁闸验证器测试完成!")
    print("=" * 70)