# -*- coding: utf-8 -*-
"""使用完整prompt测试Nature评审，找出解析失败原因"""
import sys
import os
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from dotenv import dotenv_values
env = dotenv_values('C:/Users/PC/research-hypothesis-agent/.env')
for k, v in env.items():
    os.environ[k] = v

import anthropic
import json
import re

# 完整的ANTI_HALLUCINATION_PROTOCOL
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
db_list = """
- UK Biobank (n=500,000)
- All of Us Research Program (n=1,000,000+)
- FinnGen (n=500,000)
- GTEx (n=50,000+)
- BioBank Japan (n=200,000)
"""

# 模拟假设数据
hypothesis = {
    'title': '异质性孟德尔随机化与多效性解耦：破解炎症蛋白在自身免疫病中的双向因果悖论',
    'paradigm_framework': '异质性孟德尔随机化 + 网络解纠缠 + 混合专家模型',
    'grand_challenge': '同一炎症蛋白（如CD40）在不同自身免疫病中呈现截然相反的因果效应',
    'description': '传统MR假设所有样本具有同质性，忽略了人群亚结构和多效性偏倚',
    'expected_value': '发现CD40拮抗剂仅对特定亚群有效，指导临床试验富集设计',
    'novelty': '首次引入异质性MR和多变量解纠缠框架'
}

# 构建完整prompt（和validation_agent.py一致）
prompt = """你是《Nature》杂志的高级编辑**兼顶尖数据科学专家**，负责评审最具颠覆性的科研假设。

## 🚨 【极度重要警告】：Gap-Finding 盲区寻找机制

**严禁给总结、缝合现有文献的假设打高分！**

如果该假设只是将输入的顶刊文献内容杂糅，必须判定为 REJECT。

**你的核心任务是审查���假设是否击中了现有文献的【集体盲区 (Collective Blindspots)】。**

只有利用跨界思维（如非欧几何引入生物网络、拓扑数据分析、热力学时序建模）填补了盲区，才能给予高分。

**三个关键问题**：
1. 他们在做什么？
2. 他们都没做什么？（寻找盲区！）
3. 为什么没人做？（技术障碍？认知盲区？）

---

## 评审假设

**假设名称**: {title}

**前沿框架**: {framework}

**大挑战**: {challenge}

**方法论创新**: {desc}

**双重价值**:
- 计算革命性: {expected}
- 生物学/临床突破: {novelty}

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

{{"scores": {{ "transformative_impact": <1-10>, "methodological_originality": <1-10>, "poc_feasibility": <1-10>, "data_science_red_lines": <1-10>, "statistical_hardening": <1-10> }}, "impact_analysis": {{ "breadth": "跨学科影响力分析", "depth": "颠覆性分析", "textbook_impact": "教科书影响评估", "collective_bindspot": "现有文献的集体盲区是什么？该假设是否击中了盲区？" }}, "verdict": {{ "decision": "accepted/revise/rejected", "rationale": "详细理由" }} }}

请开始评审：
""".format(
    title=hypothesis['title'],
    framework=hypothesis['paradigm_framework'],
    challenge=hypothesis['grand_challenge'],
    desc=hypothesis['description'],
    expected=hypothesis['expected_value'],
    novelty=hypothesis['novelty'],
    db_list=db_list
) + ANTI_HALLUCINATION_PROTOCOL

print("=" * 60)
print("Prompt长度: {} 字符".format(len(prompt)))
print("=" * 60)

# 调用LLM
api_key = os.getenv("ANTHROPIC_API_KEY")
base_url = os.getenv("ANTHROPIC_BASE_URL") or None

if base_url:
    client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
else:
    client = anthropic.Anthropic(api_key=api_key)

model = os.getenv("MODEL_NAME", "claude-sonnet-4-6")

print("API配置:")
print("  base_url: {}".format(base_url))
print("  model: {}".format(model))
print("\n开始调用LLM...")

message = client.messages.create(
    model=model,
    max_tokens=5000,
    temperature=0.2,
    messages=[{"role": "user", "content": prompt}]
)

# 提取响应文本
response_text = ""
for block in message.content:
    if hasattr(block, 'text'):
        response_text += block.text

print("\n" + "=" * 60)
print("LLM响应长度: {} 字符".format(len(response_text)))
print("=" * 60)

# 保存完整响应
timestamp = '20260413_full'
with open('C:/Users/PC/research-hypothesis-agent/logs/nature_response_{}.txt'.format(timestamp), 'w', encoding='utf-8') as f:
    f.write("=== Nature Full Response ===\n\n")
    f.write("Prompt Length: {} chars\n".format(len(prompt)))
    f.write("Response Length: {} chars\n\n".format(len(response_text)))
    f.write(response_text)
    f.write("\n\n=== END ===\n")

print("\n响应已保存到 logs/nature_response_{}.txt".format(timestamp))

# 显示响应预览
print("\n响应前500字符:")
print(response_text[:500])

# 尝试解析 - 使用多种策略
print("\n" + "=" * 60)
print("尝试解析JSON...")
print("=" * 60)

# 策略1: 找代码块
block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
block_matches = re.findall(block_pattern, response_text)
print("找到 {} 个代码块".format(len(block_matches)))

for i, match in enumerate(block_matches):
    match = match.strip()
    print("\n代码块 {} 开头: {}".format(i, match[:30]))

    if match.startswith('{'):
        try:
            # 使用更安全的清理方式
            cleaned = match.replace('\n', ' ')  # 先压缩换行
            cleaned = re.sub(r'\\(?![nrtbf\"\\/])', '', cleaned)
            result = json.loads(cleaned)
            if isinstance(result, dict):
                print("SUCCESS: 解析成功!")
                print("Keys: {}".format(list(result.keys())))
                break
        except json.JSONDecodeError as e:
            print("解析失败: {}".format(str(e)))
            # 显示错误位置附近内容
            error_pos = e.pos if hasattr(e, 'pos') else 0
            if error_pos > 0:
                print("错误位置附近: {}".format(match[max(0, error_pos-20):error_pos+20]))

# 策略2: 如果没有代码块，尝试直接找JSON
if not block_matches or not any(m.strip().startswith('{') for m in block_matches):
    print("\n策略2: 直接查找JSON对象...")
    first_brace = response_text.find('{')
    if first_brace != -1:
        # 使用栈匹配
        brace_count = 0
        end_pos = -1
        for i in range(first_brace, len(response_text)):
            char = response_text[i]
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i
                    break

        if end_pos != -1:
            obj_text = response_text[first_brace:end_pos+1]
            print("找到JSON对象长度: {}".format(len(obj_text)))
            print("开头: {}".format(obj_text[:50]))

            try:
                cleaned = obj_text.replace('\n', ' ')
                result = json.loads(cleaned)
                print("SUCCESS: 策略2解析成功!")
            except json.JSONDecodeError as e:
                print("策略2失败: {}".format(str(e)))

                # 详细诊断
                print("\n=== 详细诊断 ===")
                print("尝试逐段检查...")

                # 可能是嵌套引号问题
                # 检查是否有未闭合的引号
                quote_count = 0
                for j, c in enumerate(obj_text):
                    if c == '"' and (j == 0 or obj_text[j-1] != '\\'):
                        quote_count += 1

                print("引号数量（应该是偶数）: {}".format(quote_count))

                # 检查错误位置附近
                error_pos = e.pos if hasattr(e, 'pos') else 0
                if error_pos > 0:
                    print("\n错误位置 {} 附近内容:".format(error_pos))
                    print(obj_text[max(0, error_pos-30):error_pos+30])