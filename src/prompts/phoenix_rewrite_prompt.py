# -*- coding: utf-8 -*-
"""
V7.5 凤凰协议重写 Prompt 模板 (Phoenix Rewrite Prompt Template)

核心功能：
1. 生成物理锚定重写指令
2. 提供��制替代路径表格
3. 指定重写输出格式
4. 版本号管理

设计理念：
- 清晰展示检测问题
- 强制替换伪科学表述
- 提供物理传感器建议
- 版本演进记录

作者: V7.5 架构工程师
日期: 2026-04-19
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# ==================== 重写 Prompt 模板 ====================

PHOENIX_PHYSICAL_REWRITE_PROMPT_TEMPLATE = """
## 🔥 【凤凰协议 - 物理锚定重写指令】

你的假设中检测到 **不可验证的物理主张**。系统已自动生成科学替代路径。

### 检测问题
**原始表述**: `%(original_pattern)s`
**问题类型**: `%(pseudoscience_type)s` - 缺乏可验证的物理传感器逻辑
**置信度**: `%(confidence)s`

### 强制替代路径
你必须将原始表述替换为以下科学验证方案：

| 原表述 | 科学替代 | 物理传感器 | 效应度量 |
|--------|----------|------------|----------|
| `%(original_pattern)s` | `%(scientific_replacement)s` | `%(sensor_type)s` | `%(measurement_method)s` |

### 替代路径理由
%(rationale)s

### 物理原理
%(physical_principle)s

### 参考示例
%(example_reference)s

### 重写要求
1. **强制替换**: 将 `%(original_pattern)s` 替换为 `%(scientific_replacement)s`
2. **传感器明确化**: 在 methodology 中指定 `%(sensor_type)s`
3. **度量指标量化**: 在 expected_results 中给出 `%(measurement_method)s` 的具体数值范围

### 输出格式
请输出 **V%(new_version)s** 版本假设（基于 V%(current_version)s 重写）：

```json
{
  "title": "... (更新后的标题)",
  "details": "... (替换伪科学表述后的完整内容)",
  "methodology": {
    "sensor_type": "%(sensor_type)s",
    "measurement_protocol": "...",
    "technical_safeguards": "..."
  },
  "expected_results": {
    "primary_outcome": "...",
    "measurement_range": "...",
    "statistical_power": "..."
  },
  "version": "%(new_version)s",
  "rewrite_log": [
    {
      "original": "%(original_pattern)s",
      "replaced_with": "%(scientific_replacement)s",
      "reason": "物理锚定重写"
    }
  ]
}
```

**警告**: 如果不执行替换，假设将被判定为 HARD_FAILURE，无法继续演化。
"""


# ==================== 方法论补丁 Prompt 模板 ====================

PHOENIX_METHODLOGY_PATCH_PROMPT_TEMPLATE = """
## 🧬 【凤凰协议 - 方法论补丁注入指令】

红方检测到以下方法论缺陷，系统已检索到最新的解决方案文献。

### 检测到的攻击类型
%(attack_types_list)s

### 红方攻击摘要
%(red_attack_summary)s

### 检索到的解决方案文献
%(solution_papers)s

### 补丁注入要求

#### 针对 %(attack_type_primary)s 的修复方案：
%(patch_instructions)s

### 输出格式
请输出 **V%(new_version)s** 版本假设（基于 V%(current_version)s 补丁注入）：

```json
{
  "title": "... (更新后的标题)",
  "details": "... (补丁注入后的完整内容)",
  "methodology": {
    "technical_safeguards": [
      "... (具体技术保障措施 1)",
      "... (具体技术保障措施 2)"
    ],
    "validation_protocol": "... (验证协议)",
    "bias_control": "... (偏差控制)"
  },
  "version": "%(new_version)s",
  "patch_log": [
    {
      "attack_type": "... (攻击类型名称)",
      "patch_applied": "... (应用的补丁描述)",
      "supporting_reference": "PMID: ..."
    }
  ]
}
```

---

*凤凰协议自动生成 | 检索源: %(search_sources)s*
"""


# ==================== 外部补偿 Prompt 模板 ====================

PHOENIX_EXTERNAL_COMPENSATION_PROMPT_TEMPLATE = """
## 📡 【凤凰协议 - 外部算法补偿指令】

Science Score 连续停滞，系统已触发跨学科检索获取外部算法补偿。

### 分数停滞分析
- **最近分数**: %(latest_score)s
- **目标增加**: +%(target_increase)s
- **连续停滞次数**: %(stagnant_count)d

### 检索到的外部算法
%(external_algorithms)s

### 补偿注入要求
%(compensation_instructions)s

### 输出格式
请更新方法论部分，整合上述外部算法：

```json
{
  "methodology": {
    "algorithm_integration": [
      {
        "algorithm_name": "... (算法名称)",
        "application_method": "... (应用方法)",
        "expected_improvement": "... (预期改进)"
      }
    ],
    "technical_safeguards": "... (技术保障)"
  },
  "version": "%(new_version)s",
  "compensation_log": [
    {
      "source": "... (来源名称)",
      "algorithm": "... (算法名称)",
      "integration_method": "... (整合方法)"
    }
  ]
}
```

---

*凤凰协议自动生成 | 触发原因: 分数连续停滞*
"""


# ==================== Prompt 生成函数 ====================

def generate_phoenix_rewrite_prompt(
    original_hypothesis: str,
    alternative_paths: List[Dict],
    current_version: str = "v1.0"
) -> str:
    """
    生成凤凰协议物理锚定重写 Prompt

    Args:
        original_hypothesis: 原始假设文本
        alternative_paths: 替代路径列表
        current_version: 当前版本号

    Returns:
        str: 完整的重写指令 Prompt
    """
    if not alternative_paths:
        return ""

    # 选择最佳替代路径（按置信度排序）
    best_path = max(alternative_paths, key=lambda x: x.get('confidence', 0))

    # 计算新版本号
    new_version = increment_version(current_version, "physical_fix")

    # 生成攻击类型列表
    attack_types_list = format_attack_types(best_path.get('attack_types', []))

    # 使用 % 格式化避免花括号冲突
    prompt = PHOENIX_PHYSICAL_REWRITE_PROMPT_TEMPLATE % {
        'original_pattern': best_path.get('original_pattern', '未知'),
        'pseudoscience_type': best_path.get('pseudoscience_type', '未知'),
        'confidence': f"{best_path.get('confidence', 0.8):.0%}",
        'scientific_replacement': best_path.get('scientific_replacement', '未知'),
        'sensor_type': best_path.get('sensor_type', '未知'),
        'measurement_method': best_path.get('measurement_method', '未知'),
        'rationale': best_path.get('rationale', '无理由'),
        'physical_principle': best_path.get('physical_principle', '无物理原理说明'),
        'example_reference': best_path.get('example_reference', '无参考'),
        'current_version': current_version,
        'new_version': new_version,
        'attack_types_list': attack_types_list
    }

    return prompt.strip(), new_version


def generate_methodology_patch_prompt(
    attack_types: List[str],
    red_attack_summary: str,
    solution_papers: List[Dict],
    current_version: str = "v1.0",
    search_sources: List[str] = None
) -> str:
    """
    生成方法论补丁注入 Prompt

    Args:
        attack_types: 攻击类型列表
        red_attack_summary: 红方攻击摘要
        solution_papers: 解决方案文献列表
        current_version: 当前版本号
        search_sources: 搜索来源列表

    Returns:
        str: 完整的补丁注入 Prompt
    """
    new_version = increment_version(current_version, "methodology_patch")

    # 格式化攻击类型列表
    attack_types_list = '\n'.join([
        f"- **{attack_type}**: {get_attack_type_description(attack_type)}"
        for attack_type in attack_types
    ])

    # 格式化解决方案文献
    solution_papers_formatted = '\n'.join([
        f"- [{paper.get('title', '未知')}] (PMID: {paper.get('pmid', 'N/A')}) - {paper.get('key_methodology', '')}"
        for paper in solution_papers[:5]
    ])

    # 生成补丁指令
    patch_instructions = generate_patch_instructions(attack_types)

    # 格式化搜索来源
    sources_str = ', '.join(search_sources) if search_sources else 'arxiv, pubmed'

    # 使用 % 格式化避免花括号冲突
    prompt = PHOENIX_METHODLOGY_PATCH_PROMPT_TEMPLATE % {
        'attack_types_list': attack_types_list,
        'red_attack_summary': red_attack_summary[:500],
        'solution_papers': solution_papers_formatted,
        'attack_type_primary': attack_types[0] if attack_types else 'UNKNOWN',
        'patch_instructions': patch_instructions,
        'current_version': current_version,
        'new_version': new_version,
        'search_sources': sources_str
    }

    return prompt.strip(), new_version


def generate_external_compensation_prompt(
    latest_score: float,
    target_increase: float,
    stagnant_count: int,
    external_algorithms: List[Dict],
    current_version: str = "v1.0"
) -> str:
    """
    生成外部算法补偿 Prompt

    Args:
        latest_score: 最近分数
        target_increase: 目标增加分数
        stagnant_count: 连续停滞次数
        external_algorithms: 外部算法列表
        current_version: 当前版本号

    Returns:
        str: 完整的外部补偿 Prompt
    """
    new_version = increment_version(current_version, "external_compensation")

    # 格式化外部算法
    algorithms_formatted = '\n'.join([
        f"- **{algo.get('name', '未知')}**: {algo.get('description', '')} (来源: {algo.get('source', '')})"
        for algo in external_algorithms[:5]
    ])

    # 生成补偿指令
    compensation_instructions = generate_compensation_instructions(external_algorithms)

    prompt = PHOENIX_EXTERNAL_COMPENSATION_PROMPT_TEMPLATE % {
        'latest_score': latest_score,
        'target_increase': target_increase,
        'stagnant_count': stagnant_count,
        'external_algorithms': algorithms_formatted,
        'compensation_instructions': compensation_instructions,
        'current_version': current_version,
        'new_version': new_version
    }

    return prompt.strip(), new_version


# ==================== 辅助函数 ====================

def increment_version(current_version: str, change_type: str) -> str:
    """递增版本号"""
    try:
        # 解析版本号 (如 "v1.0" -> 1, 0)
        major, minor = map(int, current_version.replace('v', '').split('.'))
        if change_type == "physical_fix":
            return f"v{major}.{minor + 1}"
        elif change_type == "methodology_patch":
            return f"v{major}.{minor + 1}"
        elif change_type == "external_compensation":
            return f"v{major}.{minor + 1}"
        else:
            return f"v{major + 1}.0"
    except:
        return "v1.1"


def format_attack_types(attack_types: List[str]) -> str:
    """格式化攻击类型列表"""
    if not attack_types:
        return "- 无"
    return '\n'.join([f"- {at}" for at in attack_types])


def get_attack_type_description(attack_type: str) -> str:
    """获取攻击类型描述"""
    descriptions = {
        'OVERFITTING': '过度拟合 - 模型在训练集上表现过好，泛化能力差',
        'LEAKAGE': '数据泄露 - 测试集信息意外进入训练过程',
        'BIAS': '选择偏差 - 样本选择不当导致系统性偏差',
        'VALIDATION': '验证不足 - 缺乏独立验证集或验证方法不当',
        'AF3_LEAKAGE': 'AlphaFold3 泄露 - 结构预测信息泄露到训练数据',
        'STATISTICAL_FLAW': '统计缺陷 - 统计方法使用不当或样本量不足',
    }
    return descriptions.get(attack_type, '未知攻击类型')


def generate_patch_instructions(attack_types: List[str]) -> str:
    """生成补丁指令"""
    instructions = []

    for attack_type in attack_types[:3]:
        if attack_type == 'OVERFITTING':
            instructions.append("- 添加交叉验证协议")
            instructions.append("- 增加正则化技术说明")
        elif attack_type == 'LEAKAGE':
            instructions.append("- 明确数据划分边界")
            instructions.append("- 添加时序划分说明")
        elif attack_type == 'BIAS':
            instructions.append("- 添加协变量平衡方法")
            instructions.append("- 说明样本代表性评估")
        elif attack_type == 'VALIDATION':
            instructions.append("- 设计独立验证队列")
            instructions.append("- 添加外部验证计划")
        else:
            instructions.append(f"- 针对 {attack_type} 的具体修复措施")

    return '\n'.join(instructions) if instructions else "- 通用方法论改进"


def generate_compensation_instructions(external_algorithms: List[Dict]) -> str:
    """生成补偿指令"""
    if not external_algorithms:
        return "- 整合外部最佳实践算法"

    instructions = []
    for algo in external_algorithms[:3]:
        name = algo.get('name', '未知算法')
        instructions.append(f"- 评估 {name} 的适用性")
        instructions.append(f"- 设计 {name} 的整合方案")

    return '\n'.join(instructions)


# ==================== 导出 ====================

__all__ = [
    'PHOENIX_PHYSICAL_REWRITE_PROMPT_TEMPLATE',
    'PHOENIX_METHODLOGY_PATCH_PROMPT_TEMPLATE',
    'PHOENIX_EXTERNAL_COMPENSATION_PROMPT_TEMPLATE',
    'generate_phoenix_rewrite_prompt',
    'generate_methodology_patch_prompt',
    'generate_external_compensation_prompt',
    'increment_version',
]
