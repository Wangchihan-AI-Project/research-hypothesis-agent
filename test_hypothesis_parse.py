# -*- coding: utf-8 -*-
"""测试首席科学家解析逻辑"""
import sys
import os
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from dotenv import dotenv_values
env = dotenv_values('C:/Users/PC/research-hypothesis-agent/.env')
for k, v in env.items():
    os.environ[k] = v

from src.agents.hypothesis_agent import HypothesisAgent

# 读取实际的响应日志
with open('C:/Users/PC/research-hypothesis-agent/logs/chief_response_20260413_171540_attempt0.txt', 'r', encoding='utf-8') as f:
    response_text = f.read()

# 提取响应内容（去掉日志头）
lines = response_text.split('\n')
content_lines = []
start_found = False
for line in lines:
    if 'Response Length:' in line:
        start_found = True
        continue
    if start_found and '=== END ===' not in line:
        content_lines.append(line)

actual_response = '\n'.join(content_lines[2:])  # 去掉前两行空行

print("实际响应长度: {} 字符".format(len(actual_response)))
print("响应开头100字符: {}...".format(actual_response[:100]))

# 测试解析
agent = HypothesisAgent()

print("\n" + "="*60)
print("测试 _extract_json_hypotheses")
json_result = agent._extract_json_hypotheses(actual_response)
print("JSON提取结果: {}".format(json_result))

print("\n" + "="*60)
print("测试 _extract_markdown_hypotheses")
md_result = agent._extract_markdown_hypotheses(actual_response)
if md_result:
    print("Markdown提取成功，找到 {} 个假设".format(len(md_result)))
    for i, hyp in enumerate(md_result[:2]):
        print("  假设 {}: {}".format(i+1, hyp.get('title', 'N/A')[:50]))
else:
    print("Markdown提取失败")