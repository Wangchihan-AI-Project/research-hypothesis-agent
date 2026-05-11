# -*- coding: utf-8 -*-
"""测试修复后的Nature评审解析逻辑"""
import sys
import os
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from dotenv import dotenv_values
env = dotenv_values('C:/Users/PC/research-hypothesis-agent/.env')
for k, v in env.items():
    os.environ[k] = v

import anthropic
import json

# 模拟假设数据
hypothesis = {
    'title': '异质性孟德尔随机化与多效性解耦',
    'paradigm_framework': '异质性MR + 网络解纠缠',
    'grand_challenge': '同一蛋白在不同疾病中相反效应',
    'description': '传统MR忽略人群亚结构',
    'expected_value': '指导临床试验富集设计',
    'novelty': '首次引入异质性MR框架'
}

# 使用完整prompt格式（包含可能导致问题的JSON模板）
prompt_template = """你是《Nature》杂志的高级编辑，负责评审科研假设。

## 评审假设

**假设名称**: {title}

**前沿框架**: {framework}

**大挑战**: {challenge}

**方法论创新**: {desc}

## 请以JSON格式返回评审结果:

{{"scores": {{ "transformative_impact": <1-10>, "methodological_originality": <1-10>, "poc_feasibility": <1-10>, "data_science_red_lines": <1-10>, "statistical_hardening": <1-10> }}, "impact_analysis": {{ "breadth": "跨学科影响力分析", "depth": "颠覆性分析" }}, "verdict": {{ "decision": "accepted/revise/rejected", "rationale": "详细理由（可以在rationale中包含详细分析，比如指出问题{{issue}}或建议{{suggestion}}" }} }}

请开始评审（确保返回有效的JSON格式）：
"""

prompt = prompt_template.format(
    title=hypothesis['title'],
    framework=hypothesis['paradigm_framework'],
    challenge=hypothesis['grand_challenge'],
    desc=hypothesis['description']
)

print("=" * 60)
print("测试修复后的Nature评审解析")
print("=" * 60)
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

print("\n" + "=" * 60)
print("LLM响应:")
print("=" * 60)
print(response_text[:1500] if len(response_text) > 1500 else response_text)
print("\n响应长度: {} 字符".format(len(response_text)))

# 保存响应
with open('C:/Users/PC/research-hypothesis-agent/logs/test_nature_fixed.txt', 'w', encoding='utf-8') as f:
    f.write(response_text)

# 使用修复后的 ValidationAgent 解析
print("\n" + "=" * 60)
print("使用修复后的 ValidationAgent 解析...")
print("=" * 60)

from src.agents.validation_agent import ValidationAgent

agent = ValidationAgent()

try:
    result = agent._parse_nature_response(response_text)
    print("\nSUCCESS! 解析成功!")
    print("Result keys: {}".format(list(result.keys())))
    if 'scores' in result:
        print("Scores: {}".format(result['scores']))
    if 'verdict' in result:
        print("Verdict: {}".format(result['verdict']))
except Exception as e:
    print("\nFAILED! 错误: {}".format(str(e)))

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)