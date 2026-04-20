# -*- coding: utf-8 -*-
"""全面测试：模拟完整的Nature评审流程"""
import sys
import os
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from dotenv import dotenv_values
env = dotenv_values('C:/Users/PC/research-hypothesis-agent/.env')
for k, v in env.items():
    os.environ[k] = v

import anthropic
import json

# 完整的假设数据（包含所有字段）
hypothesis_data = {
    'title': '异质性孟德尔随机化与多效性解耦：破解炎症蛋白在自身免疫病中的双向因果悖论',
    'paradigm_framework': '异质性孟德尔随机化 + 网络解纠缠 + 混合专家模型',
    'grand_challenge': '同一炎症蛋白（如CD40）在不同自身免疫病中呈现截然相反的因果效应',
    'description': '传统MR假设所有样本具有同质性，计算平均因果效应，忽略了人群亚结构和多效性偏倚。本研究引入异质性MR框架，分离不同亚群的因果效应。',
    'expected_value': '发现CD40拮抗剂仅对TRAF6-高表达/HLA-DRB1阴性亚群有效，指导临床试验富集设计，挽救失败药物',
    'novelty': '首次引入异质性MR和多变量解纠缠框架，估计因果分布而非单一效应量',
    'technical_route': '1. 整合pQTL和PPI数据；2. 构建网络约束MVMR；3. 使用MR-MoE框架聚类；4. 敏感性分析',
    'data_requirements': ['GWAS summary statistics', 'Olink pQTL数据', 'STRING/BioGRID PPI数据'],
    'statistical_novelty': '模态因果推断：估计因果分布而非标量，识别多峰分布的亚群',
    'feasibility_analysis': '利用公开数据集UK Biobank和FinnGen可完成初步验证'
}

source_papers = [
    {
        'title': 'Plasma proteome analyses identify individual proteins associated with autoimmune diseases',
        'journal': 'Nature Immunology',
        'publication_date': '2023-01-01',
        'pmid': '12345678'
    },
    {
        'title': 'Protein-protein interaction and evolutionary selection pressure',
        'journal': 'Science',
        'publication_date': '2022-01-01',
        'pmid': '87654321'
    }
]

# 构建完整的评审prompt（模拟validation_agent的_build_nature_review_prompt）
ANTI_HALLUCINATION_PROTOCOL = """
---

## 🚨 【检索终止协议：工具死循环防范】

当文献检索达到最大次数（3次）仍未找到直接支持时：

### ✅ 你必须做的：
1. **诚实声明**：明确说明"经过3次检索尝试，未找到直接相关的文献支持"
2. **标注推测**：如需进行逻辑推理，必须标注【基于有限文献的未证实推测】
3. **建议放弃**：如果证据严重不足，建议"该假设分支缺乏文献支持，建议放弃"

### 🚫 绝对禁止：
1. **捏造检索结果**：禁止编造"检索到X篇相关文献"（实际没有）
2. **虚构引用**：禁止编造PMID、DOI、作者名、期刊名
3. **伪造数据**：禁止编造样本量、效应量、p值等实验结果
4. **把推测当事实**：禁止将未证实的推测当作已证实事实陈述

**违反此协议属于学术不端，系统将终止你的输出并记录违规。**

---

"""

# Nature级数据库清单
db_list = "\n".join([
    "- UK Biobank (n=500,000)",
    "- All of Us Research Program (n=1,000,000+)",
    "- FinnGen (n=500,000)",
    "- GTEx (n=50,000+)",
    "- BioBank Japan (n=200,000)"
])

# 构建完整prompt
prompt = f"""你是《Nature》杂志的高级编辑**兼顶尖数据科学专家**，负责评审最具颠覆性的科研假设。

## 🚨 【极度重要警告】：Gap-Finding 盲区寻找机制

**严禁给总结、缝合现有文献的假设打高分！**

如果该假设只是将输入的顶刊文献内容杂糅，必须判定为 REJECT。

**你的核心任务是审查该假设是否击中了现有文献的【集体盲区 (Collective Blindspots)】。**

只有利用跨界思维（如非欧几何引入生物网络、拓扑数据分析、热力学时序建模）填补了盲区，才能给予高分。

**三个关键问题**：
1. 他们在做什么？
2. 他们都没做什么？（寻找盲区！）
3. 为什么没人做？（技术障碍？认知盲区？）

---

## 评审假设

**假设名称**: {hypothesis_data['title']}

**前沿框架**: {hypothesis_data['paradigm_framework']}

**大挑战**: {hypothesis_data['grand_challenge']}

**方法论创新**: {hypothesis_data['description']}

**双重价值**:
- 计算革命性: {hypothesis_data['expected_value']}
- 生物学/临床突破: {hypothesis_data['novelty']}

## Nature级数据库清单

{db_list}

## 📏 【强制执行】绝对打分标准

**1-3分：常识性废话、增量研究、学术洗稿**
- 常识性推理
- 简单的增量改进（换个数据集跑老模型）
- 90%以上与现有文献重复

**4-6分：常规交叉，缺乏深度**
- A领域方法 + B领域数据，但没有深度融合
- 缺乏对盲区的识别

**7-8分：高质量的【跨界组合创新】**
- 成功将A领域的复杂算法降维应用解决B领域的顽疾
- 逻辑自洽，技术路线清晰
- **注意：一旦达到7-8分，必须判定为 ACCEPT / 放行，允许进入下游阶段！**

**9-10分：范式转移级（改写教科书）**
- 发现全新的生物学机制
- 发明全新的算法范式

## 🔒 【保底规则】Base Score Rubric

鉴于输入文献本身已是IF≥5的顶刊精华，该假设自带基础价值。

**只要满足以下条件，严禁打出低于7分的总评：**
- 逻辑自洽
- 提出一种新颖的跨学科验证方式
- 技术路线可行

## 评分维度 (每项1-10分)

1. **广度与深度的颠覆性**: 是否具备跨学科影响力，能否改写教科书或临床指南
2. **方法论的原创性**: 是否是底层算法结构的创新，而非微调或堆砌
3. **验证的可行性**: 利用全球公开算力和超级数据库能否完成初步概念验证
4. **数据科学红线**: 评估是否存在数据泄露、泛化能力缺失、样本量不足等问题
5. **统计验证严谨性**: 是否包含Power Analysis、FDR校正、Mediation分析等

## 请以JSON格式返回评审结果:

```json
{{
    "scores": {{
        "transformative_impact": <1-10>,
        "methodological_originality": <1-10>,
        "poc_feasibility": <1-10>,
        "data_science_red_lines": <1-10>,
        "statistical_hardening": <1-10>
    }},
    "impact_analysis": {{
        "breadth": "跨学科影响力分析",
        "depth": "颠覆性分析",
        "textbook_impact": "教科书影响评估",
        "collective_bindspot": "现有文献的集体盲区是什么？该假设是否击中了盲区？"
    }},
    "originality_analysis": {{
        "core_innovation": "核心创新点",
        "comparison": "与现有方法的区别",
        "derivative_check": "是否为衍生工作",
        "is_cross_domain_pivot": "是否为跨界降维打击"
    }},
    "feasibility_analysis": {{
        "data_scale": "数据规模评估",
        "computational_needs": "算力需求评估",
        "recommended_databases": ["推荐的数据库名称"]
    }},
    "ds_red_line_analysis": {{
        "data_leakage_risk": "数据泄露风险评估",
        "generalization_strategy": "泛化策略",
        "sample_size_adequacy": "样本量充足性",
        "evaluation_metrics": "评估指标科学性"
    }},
    "verdict": {{
        "decision": "accepted/revise/rejected",
        "rationale": "详细理由"
    }},
    "constructive_pivot": "如果判定为REJECT或REVISE，必须提供一个【主编的降维打击建议】"
}}
```

请开始评审：
""" + ANTI_HALLUCINATION_PROTOCOL

print("=" * 70)
print("完整Nature评审流程测试")
print("=" * 70)
print("Prompt长度: {} 字符".format(len(prompt)))

# 调用LLM
api_key = os.getenv("ANTHROPIC_API_KEY")
base_url = os.getenv("ANTHROPIC_BASE_URL") or None

if base_url:
    client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
else:
    client = anthropic.Anthropic(api_key=api_key)

model = os.getenv("MODEL_NAME", "claude-sonnet-4-6")

print("\n调用LLM (model: {})...".format(model))

message = client.messages.create(
    model=model,
    max_tokens=5000,
    temperature=0.2,
    messages=[{"role": "user", "content": prompt}]
)

response_text = ""
for block in message.content:
    if hasattr(block, 'text'):
        response_text += block.text

print("\n" + "=" * 70)
print("LLM响应长度: {} 字符".format(len(response_text)))
print("=" * 70)

# 保存完整响应
with open('C:/Users/PC/research-hypothesis-agent/logs/test_nature_complete_flow.txt', 'w', encoding='utf-8') as f:
    f.write("=== Nature Complete Flow Test ===\n\n")
    f.write("Prompt Length: {} chars\n".format(len(prompt)))
    f.write("Response Length: {} chars\n\n".format(len(response_text)))
    f.write(response_text)

print("响应已保存到 logs/test_nature_complete_flow.txt")

# 显示响应预览
print("\n响应预览 (前500字符):")
print(response_text[:500])

# 使用修复后的 ValidationAgent 解析
print("\n" + "=" * 70)
print("使用修复后的 ValidationAgent 解析...")
print("=" * 70)

from src.agents.validation_agent import ValidationAgent

agent = ValidationAgent()

try:
    result = agent._parse_nature_response(response_text)
    print("\n✅ SUCCESS! 解析成功!")
    print("-" * 70)
    print("Result keys: {}".format(list(result.keys())))
    print("-" * 70)

    if 'scores' in result:
        print("\n📊 Scores:")
        for key, value in result['scores'].items():
            print("  {}: {}".format(key, value))

    if 'verdict' in result:
        verdict = result['verdict']
        print("\n🎯 Verdict:")
        print("  Decision: {}".format(verdict.get('decision', 'N/A')))
        rationale = verdict.get('rationale', '')
        if rationale:
            print("  Rationale: {}...".format(rationale[:100]))

    if 'impact_analysis' in result:
        print("\n💡 Impact Analysis keys: {}".format(list(result['impact_analysis'].keys())))

    print("\n" + "=" * 70)
    print("✅ 测试通过！所有解析逻辑正常工作！")
    print("=" * 70)

except Exception as e:
    print("\n❌ FAILED! 错误: {}".format(str(e)))
    import traceback
    traceback.print_exc()