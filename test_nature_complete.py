# -*- coding: utf-8 -*-
"""完整模拟Nature评审流程，包含完整假设信息"""
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

# 模拟完整假设数据（包含所有必需字段）
hypothesis = {
    'title': '异质性孟德尔随机化与多效性解耦：破解炎症蛋白在自身免疫病中的双向因果悖论',
    'paradigm_framework': '异质性孟德尔随机化 + 网络解纠缠 + 混合专家模型',
    'grand_challenge': '同一炎症蛋白（如CD40）在不同自身免疫病中呈现截然相反的因果效应',
    'description': '传统MR假设所有样本具有同质性，计算平均因果效应，忽略了人群亚结构和多效性偏倚。本研究引入异质性MR框架，分离不同亚群的因果效应。',
    'expected_value': '发现CD40拮抗剂仅对TRAF6-高表达/HLA-DRB1阴性亚群有效，指导临床试验富集设计，挽救失败药物',
    'novelty': '首次引入异质性MR和多变量解纠缠框架，估计因果分布而非单一效应量'
}

# 构建完整prompt - 使用原始JSON模板格式（缩进 + 双大括号）
prompt_template = """你是《Nature》杂志的高级编辑兼顶尖数据科学专家，负责评审最具颠覆性的科研假设。

## 评审假设

**假设名称**: {title}

**前沿框架**: {framework}

**大挑战**: {challenge}

**方法论创新**: {desc}

**双重价值**:
- 计算革命性: {expected}
- 生物学/临床突破: {novelty}

## 评分维度 (每项1-10分)

1. **广度与深度的颠覆性**: 是否具备跨学科影响力
2. **方法论的原创性**: 是否是底层算法结构的创新
3. **验证的可行性**: 利用全球公开算力能否完成初步概念验证
4. **数据科学红线**: 数据泄露、泛化能力、样本量等问题
5. **统计验证严谨性**: Power Analysis、FDR校正等

## 请以JSON格式返回评审结果:

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
    "verdict": {{
        "decision": "accepted/revise/rejected",
        "rationale": "详细理由"
    }}
}}

请开始评审（必须返回JSON格式）：
"""

# 使用format替换参数和双大括号
prompt = prompt_template.format(
    title=hypothesis['title'],
    framework=hypothesis['paradigm_framework'],
    challenge=hypothesis['grand_challenge'],
    desc=hypothesis['description'],
    expected=hypothesis['expected_value'],
    novelty=hypothesis['novelty']
)

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

print("\n开始调用LLM (model: {})...".format(model))

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

print("\n" + "=" * 60)
print("LLM响应长度: {} 字符".format(len(response_text)))
print("=" * 60)

# 保存响应
with open('C:/Users/PC/research-hypothesis-agent/logs/nature_response_final.txt', 'w', encoding='utf-8') as f:
    f.write(response_text)

print("响应已保存")

# 显示响应
print("\n响应内容:")
print(response_text)

# 尝试解析 - 模拟validation_agent的_parse_nature_response逻辑
print("\n" + "=" * 60)
print("开始解析...")
print("=" * 60)

# 策略1: 找所有代码块，优先解析以 { 开头的
block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
block_matches = re.findall(block_pattern, response_text)
print("找到 {} 个代码块".format(len(block_matches)))

success = False
for i, match in enumerate(block_matches):
    match = match.strip()
    print("\n代码块 {} 开头: {}".format(i, match[:30] if len(match) > 30 else match))

    if match.startswith('{'):
        # 清理 LaTeX 反斜杠
        cleaned = re.sub(r'\\(?![nrtbf\"\\/])', '', match)
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                print("SUCCESS! 从代码块 {} 解析成功".format(i))
                print("Keys: {}".format(list(result.keys())))
                success = True
                break
        except json.JSONDecodeError as e:
            print("代码块 {} 解析失败: {}".format(i, str(e)))
            continue

# 策略2: 直接在文本中查找第一个完整的 JSON 对象
if not success:
    first_brace = response_text.find('{')
    if first_brace != -1:
        print("\n策略2: 找到第一个 { 在位置 {}".format(first_brace))
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
            print("提取JSON长度: {}".format(len(obj_text)))
            print("开头: {}".format(obj_text[:50]))
            cleaned = re.sub(r'\\(?![nrtbf\"\\/])', '', obj_text)
            try:
                result = json.loads(cleaned)
                if isinstance(result, dict):
                    print("SUCCESS! 从文本提取成功")
                    print("Keys: {}".format(list(result.keys())))
                    success = True
            except json.JSONDecodeError as e:
                print("直接提取失败: {}".format(str(e)))

                # 详细诊断
                error_pos = getattr(e, 'pos', 0)
                if error_pos > 0:
                    print("\n=== 错误诊断 ===")
                    print("错误位置: {}".format(error_pos))
                    start = max(0, error_pos - 30)
                    end = min(len(obj_text), error_pos + 30)
                    print("错误位置附近内容:")
                    print(obj_text[start:end])
                    print("错误字符: '{}'".format(obj_text[error_pos] if error_pos < len(obj_text) else 'N/A'))

if not success:
    print("\n最终结果: 解析失败")
    print("请检查响应内容是否包含有效JSON")