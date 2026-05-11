# -*- coding: utf-8 -*-
"""精确测试 unexpected '{' in field name 错误"""
import json
import re

# 这个错误通常发生在：
# 1. 字段值中包含未转义的特殊字符，导致解析器认为这是新字段开始
# 2. 字段名中包含特殊字符

print("=" * 60)
print("测试 'unexpected' 类型的 JSON 错误")
print("=" * 60)

# 模拟LLM可能返回的有问题的JSON格式
problematic_cases = [
    # Case 1: 字段值中包含未转义的换行，后面跟着类似JSON的内容
    '''
{
    "scores": {"transformative_impact": 8},
    "rationale": "这个假设很有创新性：
    {
        "key": "value"
    }
    它解决了一个重要问题"
}
    ''',

    # Case 2: 字段值中有未转义的引号和大括号组合
    '''
{
    "scores": {"transformative_impact": 8},
    "rationale": "这是"{一个}"问题"
}
    ''',

    # Case 3: 字段值中有类似JSON格式的文本（未正确转义）
    '''
{
    "scores": {"transformative_impact": 8},
    "rationale": "根据分析结果{"sub": "data"}，我们可以得出结论"
}
    ''',

    # Case 4: 字段值直接包含了嵌套对象格式文本
    '''
{
    "scores": {"transformative_impact": 8},
    "rationale": "问题分析：
    {
        "issue": "数据问题",
        "solution": "新方法"
    }
    这是核心发现"
}
    ''',

    # Case 5: 使用中文冒号而不是英文冒号
    '''
{
    "scores"： {"transformative_impact": 8}
}
    ''',

    # Case 6: 字段名中包含大括号
    '''
{
    "{key}": "value"
}
    ''',
]

for i, test in enumerate(problematic_cases):
    print("\n问题案例 {}:".format(i+1))
    print("长度: {} 字符".format(len(test)))

    # 尝试原始解析
    try:
        result = json.loads(test)
        print("SUCCESS: 解析成功!")
        print("Keys: {}".format(list(result.keys()) if isinstance(result, dict) else result))
    except json.JSONDecodeError as e:
        print("FAILED: {}".format(str(e)))

        # 显示错误位置附近的内容
        if hasattr(e, 'pos') and e.pos > 0:
            print("错误位置: {}".format(e.pos))
            start = max(0, e.pos - 30)
            end = min(len(test), e.pos + 30)
            print("错误附近: '{}'".format(test[start:end]))

        # 尝试各种修复方法
        print("\n尝试修复...")

        # 方法1: 压缩换行
        try:
            cleaned = test.replace('\n', ' ')
            result = json.loads(cleaned)
            print("  方法1 (压缩换行) SUCCESS")
        except json.JSONDecodeError as e1:
            print("  方法1 FAILED: {}".format(str(e1)[:50]))

        # 方法2: 更激进的处理 - 替换字符串内的内容
        try:
            # 找到所有字符串值并清理
            cleaned = re.sub(r'"(?:[^"\\]|\\.)*"', '"placeholder"', test)
            result = json.loads(cleaned)
            print("  方法2 (替换字符串) SUCCESS (但内容丢失)")
        except json.JSONDecodeError as e2:
            print("  方法2 FAILED: {}".format(str(e2)[:50]))

# 真正的 "unexpected '{' in field name" 错误测试
print("\n" + "=" * 60)
print("寻找真正的 unexpected 错误")
print("=" * 60)

# 让我看看 validation_agent 的解析逻辑
# 它使用了 brace_count 来匹配大括号
# 这可能导致截取到不完整的JSON

partial_json_cases = [
    # Case A: 截取到不完整的JSON（大括号匹配可能出错）
    '{"scores": {"impact": 8}, "rationale": "有问题的内容{"more": "data"}',  # 缺少闭合

    # Case B: 使用正则提取可能截断的JSON
    '{"scores": {"impact": 8}, "rationale": "包含 "引号" 和 {大括号} 的内容"}, "verdict": {"decision": "accepted"}}',
]

for i, test in enumerate(partial_json_cases):
    print("\n截取测试 {}:".format(i+1))

    # 模拟 brace_count 匹配逻辑
    first_brace = test.find('{')
    if first_brace != -1:
        brace_count = 0
        end_pos = -1
        for j in range(first_brace, len(test)):
            char = test[j]
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = j
                    break

        if end_pos != -1:
            extracted = test[first_brace:end_pos+1]
            print("Brace匹配提取: {} 字符".format(len(extracted)))
            print("提取内容开头: {}".format(extracted[:50]))

            try:
                result = json.loads(extracted)
                print("解析成功!")
            except json.JSONDecodeError as e:
                print("解析失败: {}".format(str(e)))
        else:
            print("Brace匹配未找到闭合位置")

print("\n" + "=" * 60)
print("诊断总结")
print("=" * 60)
print("""
"unexpected '{' in field name" 错误通常发生在：
1. 字符串值中包含未正确转义的引号
2. 字符串值中包含类似JSON的文本（如 {key: value}）
3. 使用大括号匹配截取JSON时，截取到字符串内的虚假大括号

建议修复：
- 使用更智能的JSON提取，考虑字符串边界
- 或者在LLM prompt中明确要求不要在字符串值中使用大括号
""")