# -*- coding: utf-8 -*-
"""精确模拟原始prompt格式，测试解析失败原因"""
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

# 模拟假设数据
hypothesis = {
    'title': '异质性孟德尔随机化与多效性解耦',
    'paradigm_framework': '异质性MR + 网络解纠缠',
    'grand_challenge': '同一蛋白在不同疾病中相反效应',
    'description': '传统MR忽略人群亚结构',
    'expected_value': '指导临床试验富集设计',
    'novelty': '首次引入异质性MR框架'
}

# 构建prompt - 使用原始格式（包括双大括号和缩进）
# 注意：在Python中使用双大括号 {{ }} 来保留单大括号
prompt_template = """你是《Nature》杂志的高级编辑，负责评审科研假设。

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
    }},
    "constructive_pivot": "如果REJECT/REVISE，提供降维打击建议"
}}

请开始评审：
"""

# 使用format替换双大括号为单大括号
prompt = prompt_template.format()

print("=" * 60)
print("Prompt内容:")
print("=" * 60)
print(prompt)
print("=" * 60)

# 调用LLM
api_key = os.getenv("ANTHROPIC_API_KEY")
base_url = os.getenv("ANTHROPIC_BASE_URL") or None

if base_url:
    client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
else:
    client = anthropic.Anthropic(api_key=api_key)

model = os.getenv("MODEL_NAME", "claude-sonnet-4-6")

print("\n开始调用LLM...")

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
print("LLM响应:")
print("=" * 60)
print(response_text)
print("=" * 60)

# 尝试解析
print("\n尝试解析JSON...")

block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
block_matches = re.findall(block_pattern, response_text)

if block_matches:
    print("找到 {} 个代码块".format(len(block_matches)))
    for i, match in enumerate(block_matches):
        match = match.strip()
        print("\n代码块 {}: {} 字符".format(i, len(match)))

        # 显示完整内容
        print("内容:")
        print(match)
        print("---")

        if match.startswith('{'):
            try:
                # 先尝试原始内容
                result = json.loads(match)
                print("SUCCESS (原始)! Keys: {}".format(list(result.keys())))
            except json.JSONDecodeError as e:
                print("原始解析失败: {}".format(str(e)))

                # 尝试清理换行
                try:
                    cleaned = match.replace('\n', ' ')
                    result = json.loads(cleaned)
                    print("SUCCESS (压缩换行)! Keys: {}".format(list(result.keys())))
                except json.JSONDecodeError as e2:
                    print("压缩换行失败: {}".format(str(e2)))

                    # 深度诊断
                    error_pos = getattr(e2, 'pos', 0)
                    print("\n=== 深度诊断 ===")
                    print("错误位置: {}".format(error_pos))
                    if error_pos > 0:
                        print("错误附近内容:")
                        print(cleaned[max(0, error_pos-30):error_pos+30])
                        print("错误字符: '{}'".format(cleaned[error_pos] if error_pos < len(cleaned) else 'N/A'))
else:
    print("没有找到代码块，尝试直接提取JSON对象...")
    first_brace = response_text.find('{')
    if first_brace != -1:
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
            print("找到JSON对象: {} 字符".format(len(obj_text)))
            try:
                result = json.loads(obj_text)
                print("SUCCESS! Keys: {}".format(list(result.keys())))
            except json.JSONDecodeError as e:
                print("失败: {}".format(str(e)))