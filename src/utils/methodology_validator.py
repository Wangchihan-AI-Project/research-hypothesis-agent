# -*- coding: utf-8 -*-
"""
V7.0 方法论语义验证器 (Methodology Semantic Validator)

防止甜点区逆向欺骗攻击 (SREA Vulnerability)

问题分析：
- hybrid_fitness.py 的 METHODOLOGY_KEYWORDS 使用简单字符串包含匹配
- 攻击者可在错误方法论中嵌入正确方法论关键词绕过校验
- 例如：声称分子对接却堆砌 Transformer/深度学习词汇获得高分

解决方案：
1. 工具-任务强制映射白名单（核心修复）
2. 否定语境检测（"不使用 X 而采用 Y"）
3. LLM 语义深度验证（可选）
4. 置信度分级熔断机制

作者: 架构师 V7.0
日期: 2026-04-17
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MethodologyValidationSource(Enum):
    """方法论验证来源"""
    TOOL_TASK_WHITELIST = "tool_task_whitelist"  # 工具-任务映射（高置信度）
    KEYWORD_MATCH = "keyword_match"              # 关键词匹配（中置信度）
    NEGATION_CONTEXT = "negation_context"        # 否定语境检测
    LLM_SEMANTIC = "llm_semantic"                # LLM语义验证
    UNKNOWN = "unknown"                          # 未知（低置信度）


class ValidationSeverity(Enum):
    """验证严重性级别"""
    PASS = "pass"              # 通过
    WARNING = "warning"        # 警告（降分）
    CRITICAL = "critical"      # 致命（熔断）
    FATAL = "fatal"            # 立即熔断


@dataclass
class MethodologyValidationResult:
    """方法论验证结果"""
    claimed_task: str                          # 检测到的声称任务类型
    mentioned_tools: List[str]                 # 提取的工具列表
    is_valid: bool                             # 是否通过验证
    severity: ValidationSeverity               # 严重性级别
    source: MethodologyValidationSource        # 验证来源
    confidence: float                          # 置信度 (0.0-1.0)
    score_multiplier: float = 1.0              # 分数乘数（熔断时为0）
    message: str = ""                          # 验证消息
    details: Dict = None                       # 详细信息

    def to_dict(self) -> Dict:
        return {
            'claimed_task': self.claimed_task,
            'mentioned_tools': self.mentioned_tools,
            'is_valid': self.is_valid,
            'severity': self.severity.value,
            'source': self.source.value,
            'confidence': self.confidence,
            'score_multiplier': self.score_multiplier,
            'message': self.message,
            'details': self.details or {}
        }


class MethodologySemanticValidator:
    """
    V7.0 方法论语义验证器 - 防止甜点区逆向欺骗

    核心机制：
    1. 工具-任务强制映射白名单
       - 声称某任务类型 → 必须使用对应的有效工具
       - 使用无效工具 → 立即熔断
    2. 否定语境检测
       - 检测"不使用 X 而采用 Y"的转折
    3. LLM 语义深度验证（可选）
    """

    # ==================== 工具-任务强制映射白名单 ====================
    # 这是核心修复：声称特定任务必须使用对应的工具

    TOOL_TASK_WHITELIST: Dict[str, Dict] = {
        # 分子对接任务
        'molecular_docking': {
            'name': '分子对接',
            'keywords': ['docking', 'binding', 'affinity', 'pose', 'score',
                        'ligand', 'receptor', 'protein-ligand', 'molecular docking'],
            'valid_tools': ['boltz', 'boltz2', 'autodock', 'vina', 'glide', 'gold',
                           'rdock', 'dockthor', 'surflex', 'flexx', 'ledock',
                           'pldock', 'gnina', 'diffdock', 'rfaa'],
            'invalid_tools': ['transformer', 'bert', 'gpt', 'llm', 'attention',
                              'lstm', 'rnn', 'cnn for docking', 'deep learning docking'],
            'required_evidence': ['binding energy', 'kd', 'ic50', 'rmsd', 'docking score'],
        },

        # GWAS 分析任务
        'gwas': {
            'name': 'GWAS 分析',
            'keywords': ['gwas', 'genome-wide', 'association study', 'snp',
                        'variant', 'allele', 'polygenic', 'prs'],
            'valid_tools': ['plink', 'gcta', 'saige', 'regenie', 'bolt-lmm',
                           'ldsc', 'gmt', 'megsa', 'fastgwa', 'reap'],
            'invalid_tools': ['transformer for gwas', 'bert for gwas',
                              'deep learning gwas', 'attention mechanism gwas'],
            'required_evidence': ['p-value', 'beta', 'se', 'maf', 'hwe'],
        },

        # QTL 分析任务
        'qtl': {
            'name': 'QTL 分析',
            'keywords': ['qtl', 'quantitative trait', 'loci', 'eqtl', 'pqtl',
                        'mqtl', 'colocalization'],
            'valid_tools': ['matrixeqtl', 'qtltools', 'fastqtl', 'smr',
                           'coloc', 'enloc', 'locuscomparer'],
            'invalid_tools': ['transformer qtl', 'neural network qtl'],
            'required_evidence': ['beta', 'se', 'p-value', 'fdr'],
        },

        # 单细胞分析任务
        'single_cell': {
            'name': '单细胞分析',
            'keywords': ['single-cell', 'single cell', 'scRNA-seq', 'scrna-seq',
                        'scRNA', 'cell type', 'cluster'],
            'valid_tools': ['seurat', 'scanpy', 'scvelo', 'celltypist',
                           'singlecellnet', 'scvi', 'cellranger', 'monocle'],
            'invalid_tools': [],  # 单细胞可以使用深度学习方法
            'required_evidence': ['umap', 'pca', 'cluster', 'gene expression'],
        },

        # 分子动力学任务
        'molecular_dynamics': {
            'name': '分子动力学',
            'keywords': ['molecular dynamics', 'md simulation', 'simulation',
                        'trajectory', 'force field'],
            'valid_tools': ['gromacs', 'amber', 'namd', 'charmm', 'openmm',
                           'lammps', 'desmond', 'acemd'],
            'invalid_tools': ['transformer md', 'bert for dynamics'],
            'required_evidence': ['rmsd', 'rmsf', 'trajectory', 'force'],
        },

        # 结构预测任务
        'structure_prediction': {
            'name': '结构预测',
            'keywords': ['protein structure', 'structure prediction',
                        'folding', 'alphaFold'],
            'valid_tools': ['alphafold', 'alphafold2', 'alphafold3', 'rosetta',
                           'rfold', 'esmfold', 'omegafold', 'deepfold'],
            'invalid_tools': [],  # 结构预测确实使用深度学习
            'required_evidence': ['plddt', 'rmsd', 'gdt-ts', 'tm-score'],
        },

        # 基因表达分析任务
        'gene_expression': {
            'name': '基因表达分析',
            'keywords': ['gene expression', 'expression analysis', 'rna-seq',
                        'transcriptome', 'differential expression'],
            'valid_tools': ['deseq2', 'edger', 'limma', 'cufflinks', 'kallisto',
                           'salmon', 'hisat2', 'star', 'featurecounts'],
            'invalid_tools': [],
            'required_evidence': ['logfc', 'padj', 'fdr', 'counts'],
        },

        # 临床预测任务
        'clinical_prediction': {
            'name': '临床预测',
            'keywords': ['clinical prediction', 'prognosis', 'survival',
                        'risk score', 'clinical outcome'],
            'valid_tools': ['cox', 'logistic', 'random forest', 'xgboost',
                           'survival model', 'kaplan-meier', 'c-index'],
            'invalid_tools': [],
            'required_evidence': ['hazard ratio', 'ci', 'p-value', 'auc'],
        },

        # 蛋白质-蛋白质相互作用任务
        'ppi': {
            'name': '蛋白质相互作用',
            'keywords': ['protein-protein', 'ppi', 'interaction', 'binding',
                        'protein interaction'],
            'valid_tools': ['string', 'biogrid', 'intact', 'dip', 'hppi',
                           'deepppi', 'dockq'],
            'invalid_tools': [],
            'required_evidence': ['interaction score', 'confidence', 'binding'],
        },

        # 因果推断任务
        'causal_inference': {
            'name': '因果推断',
            'keywords': ['causal', 'causality', 'mediation', 'instrumental',
                        'dag', 'confounder'],
            'valid_tools': ['dagitty', 'causaleffect', 'mediation', 'ivreg',
                           'twang', 'cbps', 'gformula', 'mediation analysis'],
            'invalid_tools': [],
            'required_evidence': ['causal effect', 'mediation effect', 'iv'],
        },
    }

    # 否定语境模式（检测"不使用 X 而采用 Y"）
    NEGATION_CONTEXT_PATTERNS = [
        r'不使用\s+([A-Za-z]+)\s+而采用',
        r'不用\s+([A-Za-z]+)\s+而是',
        r'而非\s+([A-Za-z]+)',
        r'instead\s+of\s+([A-Za-z]+)',
        r'not\s+using\s+([A-Za-z]+)',
        r'rather\s+than\s+([A-Za-z]+)',
        r'avoid\s+([A-Za-z]+)',
        r'skip\s+([A-Za-z]+)',
    ]

    def __init__(self, enable_llm_validation: bool = False, llm_client=None):
        """
        初始化方法论语义验证器

        Args:
            enable_llm_validation: 是否启用 LLM 语义验证
            llm_client: LLM 客户端（可选）
        """
        self.enable_llm_validation = enable_llm_validation
        self.llm_client = llm_client

        # 预编译正则模式
        self._compiled_negation_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.NEGATION_CONTEXT_PATTERNS
        ]

        # 构建工具词汇表（用于快速提取）
        self._all_valid_tools: Set[str] = set()
        self._all_invalid_tools: Set[str] = set()
        self._all_task_keywords: Set[str] = set()

        for task, config in self.TOOL_TASK_WHITELIST.items():
            self._all_valid_tools.update(config['valid_tools'])
            self._all_invalid_tools.update(config['invalid_tools'])
            self._all_task_keywords.update(config['keywords'])

        logger.info(
            f"[MethodologySemanticValidator V7.0] 初始化完成\n"
            f"  任务类型: {len(self.TOOL_TASK_WHITELIST)}\n"
            f"  有效工具: {len(self._all_valid_tools)}\n"
            f"  无效工具: {len(self._all_invalid_tools)}\n"
            f"  LLM验证: {enable_llm_validation}"
        )

    def validate_methodology_alignment(
        self,
        hypothesis_text: str,
        strict_mode: bool = True
    ) -> MethodologyValidationResult:
        """
        验证方法论一致性（核心方法）

        Args:
            hypothesis_text: 假设文本
            strict_mode: 严格模式（检测到无效工具立即熔断）

        Returns:
            MethodologyValidationResult: 验证结果
        """
        text_lower = hypothesis_text.lower()

        # Step 1: 检测声称的任务类型
        claimed_task = self._detect_claimed_task(text_lower)

        # Step 2: 提取提及的工具
        mentioned_tools = self._extract_tools(text_lower)

        # Step 3: 工具-任务强制映射验证（核心修复）
        if claimed_task and claimed_task in self.TOOL_TASK_WHITELIST:
            mapping_result = self._validate_tool_task_mapping(
                claimed_task, mentioned_tools, text_lower, strict_mode
            )
            if not mapping_result['is_valid']:
                return MethodologyValidationResult(
                    claimed_task=claimed_task,
                    mentioned_tools=mentioned_tools,
                    is_valid=False,
                    severity=ValidationSeverity.CRITICAL,
                    source=MethodologyValidationSource.TOOL_TASK_WHITELIST,
                    confidence=0.95,
                    score_multiplier=0.0,  # 熔断
                    message=mapping_result['message'],
                    details=mapping_result
                )

        # Step 4: 否定语境检测
        negation_result = self._detect_negation_context(text_lower)
        if negation_result['detected']:
            logger.warning(
                f"[MethodologyValidator] 检测到否定语境: {negation_result['negated_tools']}"
            )

        # Step 5: LLM 语义验证（可选）
        if self.enable_llm_validation and self.llm_client:
            llm_result = self._validate_with_llm(hypothesis_text, claimed_task, mentioned_tools)
            if llm_result and not llm_result['is_valid']:
                return MethodologyValidationResult(
                    claimed_task=claimed_task,
                    mentioned_tools=mentioned_tools,
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    source=MethodologyValidationSource.LLM_SEMANTIC,
                    confidence=llm_result['confidence'],
                    score_multiplier=0.5,  # 降分
                    message=llm_result['message'],
                    details=llm_result
                )

        # 通过验证
        return MethodologyValidationResult(
            claimed_task=claimed_task,
            mentioned_tools=mentioned_tools,
            is_valid=True,
            severity=ValidationSeverity.PASS,
            source=MethodologyValidationSource.KEYWORD_MATCH,
            confidence=0.8 if claimed_task else 0.5,
            score_multiplier=1.0,
            message=f"方法论验证通过，声称任务: {claimed_task or '未明确'}",
            details={
                'claimed_task': claimed_task,
                'mentioned_valid_tools': [t for t in mentioned_tools if t in self._all_valid_tools],
                'mentioned_other': [t for t in mentioned_tools if t not in self._all_valid_tools]
            }
        )

    def _detect_claimed_task(self, text_lower: str) -> Optional[str]:
        """
        检测声称的任务类型

        Args:
            text_lower: 小写文本

        Returns:
            Optional[str]: 检测到的任务类型
        """
        best_task = None
        best_score = 0

        for task, config in self.TOOL_TASK_WHITELIST.items():
            score = 0
            for keyword in config['keywords']:
                if keyword.lower() in text_lower:
                    score += 1

            if score > best_score:
                best_score = score
                best_task = task

        return best_task

    def _extract_tools(self, text_lower: str) -> List[str]:
        """
        提取文本中提及的工具

        Args:
            text_lower: 小写文本

        Returns:
            List[str]: 提取的工具列表
        """
        mentioned_tools = []

        # 检查所有已知工具
        for tool in self._all_valid_tools | self._all_invalid_tools:
            if tool.lower() in text_lower:
                mentioned_tools.append(tool)

        return mentioned_tools

    def _validate_tool_task_mapping(
        self,
        claimed_task: str,
        mentioned_tools: List[str],
        text_lower: str,
        strict_mode: bool
    ) -> Dict:
        """
        验证工具-任务强制映射（核心修复）

        核心规则：
        - 声称某任务类型 → 必须提及至少一个有效工具
        - 使用无效工具 → 立即熔断

        Args:
            claimed_task: 声称的任务类型
            mentioned_tools: 提取的工具列表
            text_lower: 小写文本
            strict_mode: 严格模式

        Returns:
            Dict: 验证结果
        """
        config = self.TOOL_TASK_WHITELIST[claimed_task]
        valid_tools = set(config['valid_tools'])
        invalid_tools = set(config['invalid_tools'])

        # 检查是否使用了无效工具（熔断条件）
        used_invalid = [t for t in mentioned_tools if t in invalid_tools]
        if used_invalid and strict_mode:
            return {
                'is_valid': False,
                'reason': 'invalid_tool_used',
                'message': f"工具-任务不匹配：声称 '{config['name']}' 任务却使用无效工具 {used_invalid}",
                'claimed_task': claimed_task,
                'used_invalid_tools': used_invalid,
                'valid_tools_expected': list(valid_tools)[:5],
                'severity': 'CRITICAL'
            }

        # 检查是否提及了有效工具
        used_valid = [t for t in mentioned_tools if t in valid_tools]

        # 如果声称某任务但完全没有提及相关工具，发出警告
        if not used_valid and not mentioned_tools:
            # 检查是否有其他证据（如 binding energy, p-value 等）
            has_evidence = False
            for evidence in config.get('required_evidence', []):
                if evidence.lower() in text_lower:
                    has_evidence = True
                    break

            if not has_evidence:
                return {
                    'is_valid': True,  # 不熔断，但降分
                    'reason': 'no_valid_tool_mentioned',
                    'message': f"声称 '{config['name']}' 任务但未提及相关工具",
                    'claimed_task': claimed_task,
                    'valid_tools_expected': list(valid_tools)[:5],
                    'severity': 'WARNING',
                    'score_penalty': 0.3
                }

        return {
            'is_valid': True,
            'reason': 'passed',
            'message': f"工具-任务映射验证通过",
            'claimed_task': claimed_task,
            'used_valid_tools': used_valid,
            'severity': 'PASS'
        }

    def _detect_negation_context(self, text_lower: str) -> Dict:
        """
        检测否定语境

        Args:
            text_lower: 小写文本

        Returns:
            Dict: 检测结果
        """
        negated_tools = []

        for pattern in self._compiled_negation_patterns:
            matches = pattern.findall(text_lower)
            for match in matches:
                negated_tools.append(match)

        return {
            'detected': len(negated_tools) > 0,
            'negated_tools': negated_tools
        }

    def _validate_with_llm(
        self,
        hypothesis_text: str,
        claimed_task: str,
        mentioned_tools: List[str]
    ) -> Optional[Dict]:
        """
        使用 LLM 进行语义深度验证

        Args:
            hypothesis_text: 假设文本
            claimed_task: 声称的任务类型
            mentioned_tools: 提取的工具列表

        Returns:
            Optional[Dict]: 验证结果
        """
        if not self.llm_client:
            return None

        try:
            import anthropic

            prompt = f"""
分析以下研究假设的方法论一致性：

假设内容（前800字符）：
{hypothesis_text[:800]}

检测到的任务类型: {claimed_task}
提及的工具: {mentioned_tools}

请判断：
1. 声称的任务类型是否与实际方法论匹配
2. 是否存在"声称 X 但实际做 Y"的欺骗模式
3. 提及的工具是否与任务类型相关

以 JSON 格式输出（仅输出 JSON）：
{
  "is_valid": true/false,
  "task_methodology_match": true/false,
  "confidence": 0.0-1.0,
  "message": "简要说明"
}
"""

            message = self.llm_client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=300,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text

            # 解析 JSON
            import json
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'is_valid': result.get('is_valid', True),
                    'confidence': result.get('confidence', 0.7),
                    'message': result.get('message', 'LLM验证完成'),
                    'task_methodology_match': result.get('task_methodology_match', True)
                }

        except Exception as e:
            logger.warning(f"[MethodologyValidator] LLM验证失败: {e}")

        return None

    def get_score_multiplier(
        self,
        validation_result: MethodologyValidationResult
    ) -> float:
        """
        获取分数乘数（用于调整适应度评分）

        Args:
            validation_result: 验证结果

        Returns:
            float: 分数乘数（0.0 = 熔断，1.0 = 正常）
        """
        return validation_result.score_multiplier

    def should_fuse(
        self,
        validation_result: MethodologyValidationResult
    ) -> Tuple[bool, str]:
        """
        判断是否应该熔断

        Args:
            validation_result: 验证结果

        Returns:
            Tuple[bool, str]: (是否熔断, 原因)
        """
        if validation_result.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.FATAL]:
            return True, validation_result.message

        return False, ""

    def batch_validate(
        self,
        hypotheses: List[str],
        strict_mode: bool = True
    ) -> List[MethodologyValidationResult]:
        """
        批量验证多个假设

        Args:
            hypotheses: 假设文本列表
            strict_mode: 严格模式

        Returns:
            List[MethodologyValidationResult]: 验证结果列表
        """
        results = []
        for hyp in hypotheses:
            results.append(self.validate_methodology_alignment(hyp, strict_mode))
        return results


# ==================== 全局实例 ====================

_methodology_validator: Optional[MethodologySemanticValidator] = None


def get_methodology_validator(
    enable_llm_validation: bool = False,
    llm_client=None
) -> MethodologySemanticValidator:
    """
    获取方法论验证器实例

    Args:
        enable_llm_validation: 是否启用 LLM 验证
        llm_client: LLM 客户端

    Returns:
        MethodologySemanticValidator: 验证器实例
    """
    global _methodology_validator

    if _methodology_validator is None:
        _methodology_validator = MethodologySemanticValidator(
            enable_llm_validation=enable_llm_validation,
            llm_client=llm_client
        )

    return _methodology_validator


def validate_methodology(
    hypothesis_text: str,
    strict_mode: bool = True
) -> MethodologyValidationResult:
    """
    便捷函数：验证方法论一致性

    Args:
        hypothesis_text: 假设文本
        strict_mode: 严格模式

    Returns:
        MethodologyValidationResult: 验证结果
    """
    validator = get_methodology_validator()
    return validator.validate_methodology_alignment(hypothesis_text, strict_mode)


# ==================== 测试代码 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V7.0 方法论语义验证器 - 测试")
    print("=" * 70)

    validator = MethodologySemanticValidator()

    # 测试 1: 正常分子对接假设
    print("\n[Test 1] 正常分子对接假设")
    normal_docking = """
    本研究使用 AutoDock Vina 进行分子对接预测，评估候选配体与靶标蛋白的结合亲和力。
    采用 Glide 进行交叉验证，计算 binding energy 和 docking score。
    """
    result = validator.validate_methodology_alignment(normal_docking)
    print(f"  声称任务: {result.claimed_task}")
    print(f"  提取工具: {result.mentioned_tools}")
    print(f"  验证结果: {result.severity.value}")
    print(f"  分数乘数: {result.score_multiplier}")
    print(f"  消息: {result.message}")

    # 测试 2: 欺骗性假设（声称对接但使用 Transformer）
    print("\n[Test 2] 欺骗性假设 - 工具-任务不匹配")
    deceptive_docking = """
    本研究使用 Transformer 架构和深度学习方法进行分子对接预测。
    采用 BERT 进行配体编码，结合注意力机制预测结合亲和力。
    """
    result = validator.validate_methodology_alignment(deceptive_docking)
    print(f"  声称任务: {result.claimed_task}")
    print(f"  提取工具: {result.mentioned_tools}")
    print(f"  验证结果: {result.severity.value}")
    print(f"  分数乘数: {result.score_multiplier}")
    print(f"  消息: {result.message}")

    # 测试 3: 正常 GWAS 假设
    print("\n[Test 3] 正常 GWAS 假设")
    normal_gwas = """
    本研究使用 PLINK 进行 GWAS 分析，采用 SAIGE 进行混合线性模型检验。
    计算 p-value 和 beta 系数，使用 LDSC 进行遗传相关性分析。
    """
    result = validator.validate_methodology_alignment(normal_gwas)
    print(f"  声称任务: {result.claimed_task}")
    print(f"  提取工具: {result.mentioned_tools}")
    print(f"  验证结果: {result.severity.value}")

    # 测试 4: 未明确任务类型的假设
    print("\n[Test 4] 未明确任务类型")
    ambiguous_text = """
    本研究探索蛋白质结构与功能的关系，分析氨基酸序列特征。
    """
    result = validator.validate_methodology_alignment(ambiguous_text)
    print(f"  声称任务: {result.claimed_task or '未明确'}")
    print(f"  验证结果: {result.severity.value}")
    print(f"  置信度: {result.confidence}")

    print("\n" + "=" * 70)
    print("V7.0 方法论语义验证器测试完成!")
    print("=" * 70)