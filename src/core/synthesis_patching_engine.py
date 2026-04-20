# -*- coding: utf-8 -*-
"""
V7.4-D SynthesisPatchingEngine - 补丁合成引擎

根据 SearchSupplementAgent 的跨学科检索结果，自主合成针对性补丁。

核心原则：
1. **禁止万能模板** - 补丁必须针对具体攻击类型定制
2. **必须注明来源** - 参考 [arXiv:xxxx.xxxx] 或 [IEEE 标准]
3. **可操作性** - 补丁内容必须可直接注入 PI Agent 的 methodology.technical_safeguards
4. **跨学科融合** - 结合算法、生物医学、临床规范多域证据

作者: V7.4-D 架构工程师
日期: 2026-04-19
"""

import sys
import os
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path

# 项目路径设置
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv(project_root / '.env', encoding='utf-8')


# ==================== 补丁模板库（针对性，非万能） ====================

PATCH_TEMPLATES = {
    # 针对 AlphaFold3 训练集泄漏的补丁模板
    'AF3_LEAKAGE': {
        'template_id': 'AF3_LEAKAGE_v1',
        'description': '针对 AlphaFold3 训练集 PDB 同源性泄漏的防御补丁',
        'structure': """
### 🔧 【自动注入补丁：AF3 训练集泄漏防御】

**参考证据来源**:
{evidence_citations}

**核心问题**: AlphaFold3 使用截至 2024-01-15 的 PDB 数据进行训练，若验证集蛋白与训练集存在同源性，会导致预测性能虚高（训练集泄漏）。

**防御方案**（参考 {primary_reference}）:

```json
"methodology": {{
  "technical_safeguards": {{
    "af3_training_leakage_prevention": {{
      "strategy": "MMseqs2 超敏感同源性过滤 + 时间截止验证",
      "implementation": "对所有输入蛋白序列执行 MMseqs2 ultra-sensitive mode 搜索，排除与 PDB 截止日期 2024-01-15 前入库序列 >25% identity 的样本",
      "validation_criterion": "确保验证集与训练集序列相似度 <25%，从物理上杜绝同源性泄漏",
      "reference": "{primary_reference}"
    }}
  }}
}}
```

**算法层约束**: 使用序列同源性阈值（{homology_threshold}%）作为硬性准入门槛，任何超过阈值的样本自动剔除。

**临床规范对冲**: 参考 UK Biobank 队列验证 SOP，对罕见突变样本执行独立外部验证。
""",
        'required_evidence': ['arxiv', 'pubmed'],
        'homology_threshold': 25,
    },

    # 针对数据泄漏的补丁模板
    'LEAKAGE': {
        'template_id': 'DATA_LEAKAGE_v1',
        'description': '针对 CV 外特征选择 / 预处理泄漏的防御补丁',
        'structure': """
### 🔧 【自动注入补丁：数据泄漏防御】

**参考证据来源**:
{evidence_citations}

**核心问题**: 特征选择或预处理在全数据集上进行，导致测试集信息泄漏到训练过程。

**防御方案**（参考 {primary_reference}）:

```json
"methodology": {{
  "technical_safeguards": {{
    "data_leakage_prevention": {{
      "strategy": "嵌套交叉验证 + 预处理隔离",
      "implementation": "所有预处理参数（均值/方差归一化、特征选择阈值）仅在训练折叠（Training Folds）内计算，测试集仅使用训练集统计量进行转换",
      "validation_protocol": "外层 5-fold 评估泛化性能，内层 5-fold 优化超参���，两层完全独立",
      "pipeline_control": "使用 scikit-learn Pipeline 确保 transform 仅在训练集拟合",
      "reference": "{primary_reference}"
    }}
  }}
}}
```

**算法层约束**: 强制使用 Pipeline 模式，禁止在 CV 外执行任何 preprocessing.fit() 操作。

**IEEE 标准对冲**: 参考 IEEE Model Evaluation Standard，对所有数据流执行审计追踪。
""",
        'required_evidence': ['arxiv', 'ieee'],
    },

    # 针对过拟合的补丁模板
    'OVERFITTING': {
        'template_id': 'OVERFITTING_v1',
        'description': '针对深度学习��型过拟合的防御补丁',
        'structure': """
### 🔧 【自动注入补丁：过拟合防御】

**参考证据来源**:
{evidence_citations}

**核心问题**: 模型参数量过大或训练时间过长，导致在验证集表现虚高但泛化能力不足。

**防御方案**（参考 {primary_reference}）:

```json
"methodology": {{
  "technical_safeguards": {{
    "overfitting_prevention": {{
      "regularization": "Dropout (p=0.3) + L2 正则化 (λ=1e-4) + 早停机制",
      "early_stopping_criterion": "当验证损失连续 3 个 epoch 上升时触发早停",
      "model_complexity_control": "限制模型层数 ≤ {max_layers}, attention heads ≤ {max_heads}",
      "validation_strategy": "独立 holdout 验证集监控损失曲线，不参与任何超参数搜索",
      "reference": "{primary_reference}"
    }}
  }}
}}
```

**算法层约束**: 强制早停机制，patience=3，min_delta=0.001。

**物理验证对冲**: 参考 {physics_reference}，对关键预测执行分子动力学稳定性验证。
""",
        'required_evidence': ['arxiv'],
        'max_layers': 3,
        'max_heads': 4,
    },

    # 针对缺乏动态物理验证的补丁模板
    'DYNAMIC_VALIDATION': {
        'template_id': 'DYNAMIC_VALIDATION_v1',
        'description': '针对静态结构预测缺乏动态验证的补丁',
        'structure': """
### 🔧 【自动注入补丁：动态物理验证】

**参考证据来源**:
{evidence_citations}

**核心问题**: AlphaFold3 仅提供静态结构预测，缺乏对构象稳定性和结合亲和力的物理动力学验证。

**防御方案**（参考 {primary_reference}）:

```json
"methodology": {{
  "technical_safeguards": {{
    "dynamic_validation": {{
      "strategy": "分子动力学 (MD) 模拟 + MM-PBSA 结合自由能计算",
      "implementation": "对每个预测结构执行 ≥500ns 全原子 MD 模拟（AMBER ff14SB/GAFF2），显式溶剂，恒温恒压",
      "conformational_stability_criterion": "RMSD 波动 <2Å 且二级结构保持率 >90%",
      "binding_energy_validation": "MM-PBSA 计算 ΔG_bind，要求与实验 ΔΔG 相关性 Pearson r>0.6",
      "software_versions": "GROMACS 2024.x, AMBER 23, APBS 3.0",
      "reference": "{primary_reference}"
    }}
  }}
}}
```

**算法层约束**: 强制执行 500ns MD 验证，RMSD 阈值 2Å。

**生物医学对冲**: 参考 {biomedical_reference}，对突变蛋白执行功能位点保守性分析。
""",
        'required_evidence': ['pubmed', 'arxiv'],
    },

    # 针对偏倚的补丁模板
    'BIAS': {
        'template_id': 'BIAS_v1',
        'description': '针对样本偏倚 / 内生性问题的补丁',
        'structure': """
### 🔧 【自动注入补丁：偏倚校正】

**参考证据来源**:
{evidence_citations}

**核心问题**: 样本选择非随机，存在混杂因素导致因果推断偏倚。

**防御方案**（参考 {primary_reference}）:

```json
"methodology": {{
  "technical_safeguards": {{
    "bias_correction": {{
      "strategy": "倾向得分匹配 (PSM) + 分层分析",
      "implementation": "使用 logistic regression 计算倾向得分，1:1 匹配对照组，卡尺宽度 0.2",
      "confounder_control": "年龄、性别、种族、BMI 作为协变量纳入模型",
      "sensitivity_analysis": "E-value 计算评估未测量混杂影响",
      "stratified_validation": "按疾病亚型分层验证结论稳健性",
      "reference": "{primary_reference}"
    }}
  }}
}}
```

**算法层约束**: 强制 PSM 匹配，卡尺宽度 0.2 SD。

**临床规范对冲**: 参考 UK Biobank 队列研究 SOP，执行标准化协变量定义。
""",
        'required_evidence': ['pubmed', 'ukbiobank'],
    },

    # 针对验证方法问题的补���模板
    'VALIDATION': {
        'template_id': 'VALIDATION_v1',
        'description': '针对验证方法不严谨的补丁',
        'structure': """
### 🔧 【自动注入补丁：验证方法强化】

**参考证据来源**:
{evidence_citations}

**核心问题**: 验证方法缺乏独立性或基准不透明。

**防御方案**（参考 {primary_reference}）:

```json
"methodology": {{
  "technical_safeguards": {{
    "validation_framework": {{
      "strategy": "嵌套交叉验证 + 时间留出验证",
      "nested_cv": "外层 5-fold 留一评估，内层 5-fold 超参数搜索",
      "temporal_holdout": "按时间戳排序，最新 20% 数据作为测试集",
      "external_benchmark": "使用独立外部数据集（{external_dataset})验证",
      "metric_threshold": "Pearson r > 0.6, RMSE < {rmse_threshold}",
      "seed_control": "固定随机种子 seed=42 确保可复现",
      "reference": "{primary_reference}"
    }}
  }}
}}
```

**算法层约束**: 强制使用嵌套 CV，禁止简单 k-fold。

**IEEE 标准对冲**: 参考 IEEE Validation Standard，执行完整审计��踪。
""",
        'required_evidence': ['arxiv', 'ieee'],
        'external_dataset': 'CASP15 / independent cohort',
        'rmse_threshold': 'domain-specific',
    },

    # V7.4-G 新增：针对伪科学/缺乏物理锚定的补丁模板
    'PSEUDOSCIENCE': {
        'template_id': 'PSEUDOSCIENCE_v1',
        'description': '针对缺乏物理锚定的主张提供科学验证补丁',
        'structure': """
### 🔧 【自动注入补丁：物理锚定增强】

**参考证据来源**:
{evidence_citations}

**核心问题**: 研究方案缺乏明确的物理传感器逻辑或实验验证路径。

**防御方案**（参考 {primary_reference}）:

```json
"methodology": {{
  "technical_safeguards": {{
    "physical_anchor_enforcement": {{
      "strategy": "信号捕获 + 效应度量双验证",
      "signal_capture": "明确指定物理传感器（测序仪/光谱仪/电极/MRI）",
      "effect_measurement": "量化效应指标（生存率/响应率/基因表达变化）",
      "experimental_validation": "可重复实验设计，第三方验证",
      "validation_criterion": "第三方实验验证成功率 >90%",
      "reference": "{primary_reference}"
    }}
  }}
}}
```

**算法层约束**: 强制物理传感器验证，禁止无测量手段的主张。

**学术标准对冲**: 参考 Nature Methods 实验可重复性标准，要求所有关键主张至少有独立验证。
""",
        'required_evidence': ['pubmed', 'ieee'],
    },
}


# ==================== 补丁数据类 ====================

@dataclass
class Patch:
    """单条补丁"""
    patch_id: str                          # 补丁 ID
    attack_type: str                       # 针对的攻击类型
    template_used: str                     # 使用的模板 ID
    evidence_citations: List[str]          # 证据引用列表
    primary_reference: str                 # 主要参考来源
    patch_content: str                     # 补丁完整内容
    injectable_json: Dict                  # 可注入的 JSON 片段
    created_timestamp: str                 # 创建时间

    def to_dict(self) -> Dict:
        return {
            'patch_id': self.patch_id,
            'attack_type': self.attack_type,
            'template_used': self.template_used,
            'evidence_citations': self.evidence_citations,
            'primary_reference': self.primary_reference,
            'patch_content': self.patch_content,
            'injectable_json': self.injectable_json,
            'created_timestamp': self.created_timestamp,
        }


@dataclass
class PatchingResult:
    """补丁合成结果"""
    attack_types_addressed: List[str]      # 已处理的攻击类型
    patches: List[Patch]                   # 生成的补丁列表
    combined_injection_prompt: str         # 合并后的注入 Prompt
    total_evidence_used: int               # 使用的证据总数
    synthesis_timestamp: str               # 合成时间

    def to_dict(self) -> Dict:
        return {
            'attack_types_addressed': self.attack_types_addressed,
            'patches': [p.to_dict() for p in self.patches],
            'combined_injection_prompt': self.combined_injection_prompt,
            'total_evidence_used': self.total_evidence_used,
            'synthesis_timestamp': self.synthesis_timestamp,
        }


# ==================== SynthesisPatchingEngine ====================

class SynthesisPatchingEngine:
    """
    V7.4-D 补丁合成引擎

    根据跨学科检索结果，自主合成针对性补丁：
    - 禁止万能模板
    - 必须注明参考来源
    - 生成的补丁可直接注入 PI Agent
    """

    def __init__(self):
        """初始化补丁合成引擎"""
        self.patch_history: List[Patch] = []
        print("[V7.4-D] SynthesisPatchingEngine 初始化完成")

    def execute(self, input_data: Dict) -> Dict:
        """
        执行补丁合成

        Args:
            input_data: {
                'retrieval_result': dict - SearchSupplementAgent 的检索结果
                'patch_materials': List[Dict] - 补丁素材
                'attack_types': List[str] - 检测到的攻击类型
                'original_hypothesis': str - 原始假设（可选，用于上下文）
            }

        Returns:
            {
                'success': bool,
                'patching_result': PatchingResult,
            }
        """
        retrieval_result = input_data.get('retrieval_result', {})
        patch_materials = input_data.get('patch_materials', [])
        attack_types = input_data.get('attack_types', [])
        original_hypothesis = input_data.get('original_hypothesis', '')

        print(f"[V7.4-D] 启动补丁合成引擎...")
        print(f"[V7.4-D] 待处理攻击类型: {attack_types}")
        print(f"[V7.4-D] 可用补丁素材: {len(patch_materials)} 条")

        start_time = datetime.now()

        # Step 1: 按攻击类型分组补丁素材
        materials_by_attack_type = self._group_materials_by_attack_type(
            patch_materials, attack_types
        )

        # Step 2: 为每个攻击类型生成针对性补丁
        patches = []
        for attack_type in attack_types:
            materials = materials_by_attack_type.get(attack_type, [])

            if not materials:
                print(f"[V7.4-D] 警告: 攻击类型 {attack_type} 无可用证据素材")
                continue

            patch = self._synthesize_patch(attack_type, materials)
            if patch:
                patches.append(patch)
                self.patch_history.append(patch)
                print(f"[V7.4-D] 补丁合成成功: {patch.patch_id}")

        # Step 3: 合并所有补丁为注入 Prompt
        combined_prompt = self._combine_patches_to_prompt(patches, original_hypothesis)

        result = PatchingResult(
            attack_types_addressed=attack_types,
            patches=patches,
            combined_injection_prompt=combined_prompt,
            total_evidence_used=len(patch_materials),
            synthesis_timestamp=datetime.now().isoformat(),
        )

        print(f"[V7.4-D] 补丁合成完成: 共生成 {len(patches)} 条补丁")

        return {
            'success': len(patches) > 0,
            'patching_result': result.to_dict(),
        }

    def _group_materials_by_attack_type(
        self,
        materials: List[Dict],
        attack_types: List[str]
    ) -> Dict[str, List[Dict]]:
        """
        按攻击类型分组补丁素材

        Returns:
            Dict[str, List[Dict]]: {attack_type: [materials]}
        """
        grouped = {}

        for attack_type in attack_types:
            grouped[attack_type] = []

            for m in materials:
                # 检查素材是否与该攻击类型相关
                relevant_types = m.get('attack_type_relevant', [])
                if attack_type in relevant_types:
                    grouped[attack_type].append(m)

                # 也可以根据方法论关键词判断相关性
                methodology = m.get('key_methodology', '').lower()
                if self._is_methodology_relevant(methodology, attack_type):
                    grouped[attack_type].append(m)

        return grouped

    def _is_methodology_relevant(self, methodology: str, attack_type: str) -> bool:
        """
        判断方法论是否与攻击类型相关

        Returns:
            bool: 是否相关
        """
        relevance_map = {
            'LEAKAGE': ['nested', 'cross', 'validation', 'isolation', 'pipeline', 'leak'],
            'OVERFITTING': ['dropout', 'regularization', 'early stopping', 'overfit'],
            'BIAS': ['propensity', 'matching', 'confounder', 'stratified', 'bias'],
            'VALIDATION': ['benchmark', 'external', 'holdout', 'validation', 'nested'],
            'AF3_LEAKAGE': ['mmseqs', 'homology', 'alphafold', 'pdb', 'sequence'],
            'DYNAMIC_VALIDATION': ['molecular dynamics', 'md', 'mm-pbsa', 'conformational', 'binding'],
            # V7.4-G 新增
            'PSEUDOSCIENCE': ['reproducibility', 'validation', 'physical', 'sensor', 'measurement', 'anchor', 'feasibility'],
        }

        keywords = relevance_map.get(attack_type, [])
        for kw in keywords:
            if kw in methodology:
                return True

        return False

    def _synthesize_patch(self, attack_type: str, materials: List[Dict]) -> Optional[Patch]:
        """
        为单个攻击类型合成补丁

        Returns:
            Patch: 生成的补丁
        """
        # 选择合适的模板
        template = PATCH_TEMPLATES.get(attack_type)
        if not template:
            print(f"[V7.4-D] 警告: 无针对 {attack_type} 的补丁模板")
            return None

        # 从素材中提取证据引用
        evidence_citations = []
        primary_reference = ""

        for m in materials[:5]:  # Top 5 素材
            citation = m.get('citation', '')
            if citation:
                evidence_citations.append(citation)

            # 选择相关性最高的作为主要参考
            if m.get('relevance_score', 0) > 0.5 and not primary_reference:
                primary_reference = citation

        # 如果没有高相关性素材，使用第一个
        if not primary_reference and evidence_citations:
            primary_reference = evidence_citations[0]

        # 构建证据引用文本
        evidence_text = "\n".join([f"- {c}" for c in evidence_citations])

        # 从素材中提取方法论关键词（用于补充模板）
        extracted_methodologies = []
        for m in materials:
            methodology = m.get('key_methodology', '')
            if methodology:
                extracted_methodologies.append(methodology)

        methodology_supplement = ', '.join(extracted_methodologies[:3]) if extracted_methodologies else ""

        # 渲染补丁模板
        template_structure = template['structure']

        # 替换模板变量
        patch_content = template_structure.format(
            evidence_citations=evidence_text,
            primary_reference=primary_reference,
            homology_threshold=template.get('homology_threshold', 25),
            max_layers=template.get('max_layers', 3),
            max_heads=template.get('max_heads', 4),
            physics_reference=primary_reference,
            biomedical_reference=primary_reference,
            external_dataset=template.get('external_dataset', 'independent benchmark'),
            rmse_threshold=template.get('rmse_threshold', 'domain-specific'),
        )

        # 提取可注入的 JSON 片段
        injectable_json = self._extract_injectable_json(patch_content, attack_type)

        # 生成补丁 ID
        patch_id = f"PATCH_{attack_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        return Patch(
            patch_id=patch_id,
            attack_type=attack_type,
            template_used=template['template_id'],
            evidence_citations=evidence_citations,
            primary_reference=primary_reference,
            patch_content=patch_content,
            injectable_json=injectable_json,
            created_timestamp=datetime.now().isoformat(),
        )

    def _extract_injectable_json(self, patch_content: str, attack_type: str) -> Dict:
        """
        从补丁内容中提取可注入的 JSON 片段

        V7.4-D 修复：处理模板中部分 JSON 的情况

        Returns:
            Dict: 可注入 methodology.technical_safeguards 的 JSON
        """
        # 尝试解析补丁中的 JSON ���码块
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, patch_content, re.DOTALL)

        if matches:
            try:
                # 取第一个 JSON 代码块
                json_str = matches[0].strip()

                print(f"[V7.4-D Debug] 原始 JSON 字符串长度: {len(json_str)}")
                print(f"[V7.4-D Debug] JSON 前200字符: {json_str[:200]}")

                # V7.4-D: 模板中的 JSON 是片段，需要构建完整对象
                # 模板格式通常是: "methodology": { ... }
                # 需要将其包装成: { "methodology": { ... } }

                # 检查是否包含 methodology 字段
                if '"methodology"' in json_str:
                    # 提取从第一个 { 开始的内容
                    start_idx = json_str.find('{')
                    if start_idx != -1:
                        json_str = json_str[start_idx:]

                    # 计算括号平衡
                    open_braces = json_str.count('{')
                    close_braces = json_str.count('}')
                    missing_braces = open_braces - close_braces

                    print(f"[V7.4-D Debug] 开括号: {open_braces}, 闭括号: {close_braces}, 缺失: {missing_braces}")

                    # 补全缺失的闭合括号
                    if missing_braces > 0:
                        json_str = json_str + '}' * missing_braces

                    # 如果字符串以 "methodology": 开头而不是 {，添加外层包装
                    if not json_str.startswith('{'):
                        json_str = '{' + json_str
                        # 需要再添加一个闭合括号
                        json_str = json_str + '}'

                    print(f"[V7.4-D Debug] 修复后 JSON 长度: {len(json_str)}")
                    print(f"[V7.4-D Debug] 修复后 JSON 前200字符: {json_str[:200]}")

                    parsed = json.loads(json_str)

                    # 验证解析结果是否包含 methodology 字段
                    if 'methodology' in parsed:
                        print(f"[V7.4-D] JSON 解析成功，包含 methodology 字段")
                        return parsed
                    else:
                        print(f"[V7.4-D] 警告: JSON 解析成功但不包含 methodology 字段")
                        return {'methodology': parsed}

            except json.JSONDecodeError as e:
                print(f"[V7.4-D] JSON 解析失败: {e}")
                print(f"[V7.4-D] 错误位置 JSON 片段: {json_str[min(e.pos-50, 0):e.pos+50] if hasattr(e, 'pos') else json_str[:200]}")
                pass

        # 如果解析失败，返回默认结构
        print(f"[V7.4-D] 使用默认结构作为后备")
        return {
            'methodology': {
                'technical_safeguards': {
                    attack_type.lower(): {
                        'strategy': '自动注入防御',
                        'reference': '见补丁详情',
                    }
                }
            }
        }

    def _combine_patches_to_prompt(
        self,
        patches: List[Patch],
        original_hypothesis: str
    ) -> str:
        """
        合并所有补丁为 PI Agent 可用的注入 Prompt

        Returns:
            str: 合并后的注入 Prompt
        """
        if not patches:
            return ""

        prompt_header = """
## ╔══════════════════════════════════════════════════════════════════════════════╗
## ║           V7.4-D 自动补丁注入系统 (Auto-Patch Injection)                        ║
## ╚══════════════════════════════════════════════════════════════════════════════╝

**系统警告**: 红方在第 3 轮迭代中发现了严重方法论问题。系统已自动执行跨学科检索并合成针对性补丁。

**你必须在新版本的假设中整合以下技术防范措施！**

---

"""

        combined_content = prompt_header

        for i, patch in enumerate(patches, 1):
            combined_content += f"\n### 补丁 #{i}: {patch.attack_type}\n\n"
            combined_content += patch.patch_content
            combined_content += "\n---\n"

        # 添加硬性要求
        combined_content += """
## ⚠️⚠️⚠️ 【V7.4-D 硬性注入要求】

1. **必须整合**: 以上所有补丁中的 `technical_safeguards` 必须出现在你输出 JSON 的 `methodology.technical_safeguards` 字段中

2. **证据引用**: 你必须在 `references` 字段中引用上述证据来源（如 [arXiv:xxxx.xxxx], [PMID: xxxxx]）

3. **禁止泛化**: 不要使用模糊的防御语言（如"加强验证"），必须使用补丁中指定的具体技术方案（如 "MMseqs2 ultra-sensitive mode", "nested 5-fold CV"）

4. **保持创新**: 补丁只是方法论补强，不应削弱你的核心创新架构

---

**现在，请提交整合了所有自动补丁的优化版假设！**

"""

        return combined_content


# ==================== 测试入口 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V7.4-D SynthesisPatchingEngine 测试")
    print("=" * 70)

    engine = SynthesisPatchingEngine()

    # 模拟输入数据（来自 SearchSupplementAgent）
    test_input = {
        'retrieval_result': {
            'total_found': 15,
        },
        'patch_materials': [
            {
                'citation': '[arXiv: 2501.12345] Nested Cross-Validation for Leakage-Free Model Evaluation (2025)',
                'key_methodology': 'nested cross-validation, preprocessing isolation',
                'source': 'arxiv',
                'relevance_score': 0.85,
                'attack_type_relevant': ['LEAKAGE', 'VALIDATION'],
            },
            {
                'citation': '[PMID: 38912345] AlphaFold3 Training Set Contamination: A Systematic Analysis (2025)',
                'key_methodology': 'MMseqs2 homology filtering, PDB temporal cutoff',
                'source': 'pubmed',
                'relevance_score': 0.90,
                'attack_type_relevant': ['AF3_LEAKAGE'],
            },
            {
                'citation': '[arXiv: 2502.56789] Molecular Dynamics Validation for Protein Structure Prediction (2026)',
                'key_methodology': 'molecular dynamics, MM-PBSA, conformational stability',
                'source': 'arxiv',
                'relevance_score': 0.78,
                'attack_type_relevant': ['DYNAMIC_VALIDATION'],
            },
        ],
        'attack_types': ['AF3_LEAKAGE', 'DYNAMIC_VALIDATION'],
        'original_hypothesis': 'AlphaFold3 augmented pipeline for rare mutation prediction',
    }

    result = engine.execute(test_input)

    print("\n=== 补丁合成结果 ===")
    print(f"成功: {result['success']}")
    print(f"处理攻击类型: {result['patching_result']['attack_types_addressed']}")
    print(f"生成补丁数: {len(result['patching_result']['patches'])}")

    for p in result['patching_result']['patches']:
        print(f"\n补丁 ID: {p['patch_id']}")
        print(f"攻击类型: {p['attack_type']}")
        print(f"主要参考: {p['primary_reference']}")
        print(f"证据引用: {p['evidence_citations']}")

    print("\n=== 合并注入 Prompt 预览 ===")
    print(result['patching_result']['combined_injection_prompt'][:1000] + "...")

    print("\n" + "=" * 70)
    print("测试完成")