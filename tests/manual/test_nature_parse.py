# -*- coding: utf-8 -*-
"""直接测试 Nature评审解析逻辑"""
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

import json
import re

# 模拟实际LLM返回的响应（从日志中看到的格式）
test_responses = [
    # 测试1: dict代码块在前，array代码块在后
    '''
```json
{
    "scores": {
        "transformative_impact": 8,
        "methodological_originality": 7,
        "poc_feasibility": 9,
        "data_science_red_lines": 8,
        "statistical_hardening": 7
    },
    "impact_analysis": {
        "breadth": "该假设跨越了统计物理学、信息论与心血管病理学"
    }
}
```

推荐数据集:
```json
["UK Biobank (500,000+)", "MIMIC-IV (200,000+ ICU住院)", "GTEx (50,000+, 多组织)"]
```
''',

    # 测试2: array代码块在前，dict代码块在后（这是出问题的场景）
    '''
推荐数据集:
```json
["UK Biobank (500,000+)", "MIMIC-IV (200,000+ ICU住院)", "GTEx (50,000+, 多组织)"]
```

评审结果:
```json
{
    "scores": {
        "transformative_impact": 8,
        "methodological_originality": 7,
        "poc_feasibility": 9
    },
    "impact_analysis": {
        "breadth": "跨领域创新"
    }
}
```
''',

    # 测试3: 没有代码块，直接是JSON对象
    '''
这是评审结果:
{
    "scores": {
        "transformative_impact": 8,
        "methodological_originality": 7
    }
}
其他内容...
''',

    # 测试4: 多个dict代码块（取第一个）
    '''
```json
{"title": "数据集列表", "items": ["a", "b"]}
```

```json
{
    "scores": {
        "transformative_impact": 9,
        "methodological_originality": 8
    }
}
```
'''
]

def test_parse_nature_response(response_text):
    """模拟 _parse_nature_response 的逻辑"""
    print("\n" + "="*60)
    print("测试响应长度: {} 字符".format(len(response_text)))
    print("响应预览: {}...".format(response_text[:100].replace('\n', ' ')))

    # 策略1: 找到所有代码块，优先解析以 { 开头的
    block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    block_matches = re.findall(block_pattern, response_text)

    if block_matches:
        print("找到 {} 个代码块".format(len(block_matches)))
        for i, match in enumerate(block_matches):
            match = match.strip()
            print("  代码块 {} 开头: {}".format(i, match[:20] if len(match) > 20 else match))

            if match.startswith('{'):
                cleaned = re.sub(r'\\(?![nrtbf\"\\/])', '', match)
                try:
                    result = json.loads(cleaned)
                    if isinstance(result, dict):
                        print("  SUCCESS: 从代码块 {} 解析到dict".format(i))
                        return result
                except json.JSONDecodeError as e:
                    print("  代码块 {} 解析失败: {}".format(i, str(e)[:30]))
                    continue

    # 策略2: 直接在文本中找第一个完整的JSON对象
    first_brace = response_text.find('{')
    if first_brace != -1:
        print("找到第一个左括号在位置 {}".format(first_brace))
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
            cleaned = re.sub(r'\\(?![nrtbf\"\\/])', '', obj_text)
            try:
                result = json.loads(cleaned)
                if isinstance(result, dict):
                    print("SUCCESS: 从文本直接提取dict")
                    return result
            except json.JSONDecodeError as e:
                print("直接提取失败: {}".format(str(e)[:50]))

    print("FAILED: 无法解析")
    return None

# 运行测试
for i, response in enumerate(test_responses):
    print("\n>>> 测试用例 {}".format(i+1))
    result = test_parse_nature_response(response)
    if result and isinstance(result, dict):
        print("RESULT: dict with keys: {}".format(list(result.keys())))
    else:
        print("RESULT: FAILED")

print("\n" + "="*60)
print("测试完成")