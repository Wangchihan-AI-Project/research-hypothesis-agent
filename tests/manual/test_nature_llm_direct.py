# -*- coding: utf-8 -*-
"""直接测试Nature评审的LLM响应，找出解析失败原因"""
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

# 创建一个模拟的假设数据
hypothesis_data = {
    'title': '异质性孟德尔随机化与多效性解耦：破解炎症蛋白在自身免疫病中的双向因果悖论',
    'paradigm_framework': '异质性孟德尔随机化 + 网络解纠缠 + 混合专家模型',
    'grand_challenge': '同一炎症蛋白（如CD40）在不同自身免疫病中呈现截然相反的因果效应',
    'description': '传统MR假设所有样本具有同质性，忽略了人群亚结构和多效性偏倚',
    'expected_value': '发现CD40拮抗剂仅对特定亚群有效，指导临床试验富集设计',
    'novelty': '首次引入异质性MR和多变量解纠缠框架',
    'statistical_novelty': '模态因果推断：估计因果分布而非标量'
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

# 构建评审提示词（不使用format，直接拼接）
prompt_parts = [
    "你是《Nature》杂志的高级编辑，负责评审科研假设。请对以下假设进行评审。",
    "",
    "## 待评审假设",
    "",
    "**假设名称**: " + hypothesis_data['title'],
    "",
    "**前沿框架**: " + hypothesis_data['paradigm_framework'],
    "",
    "**大挑战**: " + hypothesis_data['grand_challenge'],
    "",
    "**方法论创新**: " + hypothesis_data['description'],
    "",
    "## 请以JSON格式返回评审结果:",
    "",
    '{"scores": {"transformative_impact": "<1-10>", "methodological_originality": "<1-10>", "poc_feasibility": "<1-10>", "data_science_red_lines": "<1-10>", "statistical_hardening": "<1-10>"}, "impact_analysis": {"breadth": "跨学科影响力分析", "depth": "颠覆性分析"}, "verdict": {"decision": "accepted/revise/rejected", "rationale": "详细理由"}}',
    "",
    "请开始评审："
]

prompt = "\n".join(prompt_parts)

print("=" * 60)
print("开始调用LLM...")
print("=" * 60)

# 调用LLM（使用和ValidationAgent相同的方式）
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

message = client.messages.create(
    model=model,
    max_tokens=4000,
    temperature=0.2,
    messages=[{"role": "user", "content": prompt}]
)

# 提取响应文本
response_text = ""
for block in message.content:
    if hasattr(block, 'text'):
        response_text += block.text

print("\n" + "=" * 60)
print("LLM响应 (前2000字符):")
print("=" * 60)
print(response_text[:2000])

print("\n" + "=" * 60)
print("LLM响应 (完整长度: {} 字符)".format(len(response_text)))
print("=" * 60)

# 保存完整响应
timestamp = '20260413_debug'
with open('C:/Users/PC/research-hypothesis-agent/logs/nature_response_{}.txt'.format(timestamp), 'w', encoding='utf-8') as f:
    f.write("=== Nature Response Debug ===\n\n")
    f.write("Length: {} characters\n\n".format(len(response_text)))
    f.write(response_text)
    f.write("\n\n=== END ===\n")

print("\n响应已保存到 logs/nature_response_{}.txt".format(timestamp))

# 尝试解析
print("\n" + "=" * 60)
print("尝试解析JSON...")
print("=" * 60)

# 找所有代码块
block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
block_matches = re.findall(block_pattern, response_text)
print("找到 {} 个代码块".format(len(block_matches)))

for i, match in enumerate(block_matches):
    match = match.strip()
    print("\n代码块 {}:".format(i))
    print("开头50字符: {}".format(match[:50]))

    # 尝试解析
    try:
        cleaned = re.sub(r'\\(?![nrtbf\"\\/])', '', match)
        result = json.loads(cleaned)
        print("解析成功! 类型: {}".format(type(result)))
        if isinstance(result, dict):
            print("Keys: {}".format(list(result.keys())[:5]))
    except json.JSONDecodeError as e:
        print("解析失败: {}".format(str(e)))

        # 打印问题区域
        error_pos = getattr(e, 'pos', 0)
        if error_pos > 0:
            start = max(0, error_pos - 30)
            end = min(len(match), error_pos + 30)
            print("\n错误位置附近的内容:")
            print("位置 {}: {}".format(error_pos, match[start:end]))
            print("错误字符: '{}'".format(match[error_pos] if error_pos < len(match) else 'N/A'))

        # 打印整个JSON内容（如果不太长）
        if len(match) < 500:
            print("\n完整代码块内容:")
            print(match)