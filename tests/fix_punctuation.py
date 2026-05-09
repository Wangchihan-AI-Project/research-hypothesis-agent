# -*- coding: utf-8 -*-
"""
Fix hypothesis_agent.py by removing problematic punctuation
"""
import re

# 读取文件
with open('src/agents/hypothesis_agent.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# 处理每一行
fixed_lines = []
for line in lines:
    # 替换中文标点为英文标点
    replacements = [
        ('\u3010', '['),  # 【
        ('\u3011', ']'),  # 】
        ('\uFF08', '('),  # （
        ('\uFF09', ')'),  # ）
        ('\uFF1A', ':'),  # ：
        ('\uFF1F', '?'),  # ？
        ('\uFF0C', ','),  # ，
        ('\u3002', '.'),  # 。
        ('\u3001', ','),  # 、
        ('\u2192', '->'), # →
        ('\u2265', '>='), # ≥
        ('\u2264', '<='), # ≤
        ('\uFF01', '!'),  # ！
        ('\uFF1B', ';'),  # ；
        ('\u201C', '"'),  # "
        ('\u201D', '"'),  # "
        ('\u2018', "'"),  # '
        ('\u2019', "'"),  # '
        ('\uFFFD', ''),   # 移除替换字符
    ]

    fixed = line
    for old, new in replacements:
        fixed = fixed.replace(old, new)

    fixed_lines.append(fixed)

# 写回文件
with open('src/agents/hypothesis_agent.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print('Fixed {} lines'.format(len(fixed_lines)))
