# -*- coding: utf-8 -*-
"""诊断 "unexpected '{' in field name" 错误"""
import json
import re

# 测试各种可能导致 "unexpected '{' in field name" 错误的情况

test_cases = [
    # 正常JSON - 应该成功
    '{"key": "value"}',

    # 字段名没有引号 - 会报错
    '{key: "value"}',

    # 字段值中包含未转义的大括号 - 会报错
    '{"key": "some {value} here"}',

    # 多行字符串（JSON不支持）
    '{"key": "line1\nline2"}',

    # 中文引号 - 会报错
    '{"key": "值"}',  # 中文引号

    # 字段名中有空格 - 会报错
    '{" key": "value"}',

    # 嵌套对象格式错误
    '{"outer": {"inner": {value}}}',
]

print("=" * 60)
print("测试各种会导致 JSON 解析错误的情况")
print("=" * 60)

for i, test in enumerate(test_cases):
    print("\n测试 {}:".format(i+1))
    print("内容: {}".format(test[:50] if len(test) > 50 else test))

    try:
        result = json.loads(test)
        print("成功: {}".format(result))
    except json.JSONDecodeError as e:
        print("失败: {}".format(str(e)))
        print("  错误类型: {}".format(type(e).__name__))

# 特别测试可能来自LLM的格式
print("\n" + "=" * 60)
print("模拟LLM可能返回的异常JSON")
print("=" * 60)

llm_test_cases = [
    # 多行缩进JSON
    '''
{
    "scores": {
        "transformative_impact": 8,
        "methodological_originality": 7
    },
    "verdict": {
        "decision": "accepted"
    }
}
    ''',

    # 嵌套对象中有中文
    '''
{
    "scores": {
        "transformative_impact": 8
    },
    "rationale": "这个假设很有创新性，因为它：
1. 首次引入异质性MR
2. 解决了因果悖论"
}
    ''',

    # 字段值中包含换行和特殊字符
    '''
{
    "scores": {
        "transformative_impact": 8
    },
    "rationale": "详细理由：
- 第一点
- 第二点
{关键发现}"
}
    ''',

    # 尝试修复的版本（压缩换行）
    '''
{
    "scores": {
        "transformative_impact": 8
    },
    "rationale": "这个假设很有创新性，因为它首次引入异质性MR，解决了因果悖论"
}
    ''',
]

for i, test in enumerate(llm_test_cases):
    print("\nLLM测试 {}:".format(i+1))
    print("内容长度: {}".format(len(test)))

    # 先尝试原始
    try:
        result = json.loads(test)
        print("原始解析成功!")
    except json.JSONDecodeError as e:
        print("原始失败: {}".format(str(e)[:80]))

        # 尝试压缩换行
        try:
            cleaned = test.replace('\n', ' ')
            result = json.loads(cleaned)
            print("压缩换行后成功!")
        except json.JSONDecodeError as e2:
            print("压缩换行后仍失败: {}".format(str(e2)[:80]))

            # 检查错误位置
            if hasattr(e2, 'pos'):
                print("错误位置: {}".format(e2.pos))
                print("错误附近: {}".format(cleaned[max(0, e2.pos-20):e2.pos+20]))