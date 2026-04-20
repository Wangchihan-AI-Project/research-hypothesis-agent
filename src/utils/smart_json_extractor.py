# -*- coding: utf-8 -*-
"""
智能JSON提取器 - 考虑字符串边界

解决的核心问题：
当JSON字段值中包含类似JSON格式的文本时（如 rationale 字段中有 {"key": "value"}），
简单的大括号计数匹配会错误地把字符串内的内容当作JSON结构的一部分。

解决方案：
使用逐字符解析，正确处理字符串边界，不把字符串内的内容当作JSON结构。
"""
import re
import json
from typing import Dict, Optional, Union

class SmartJSONExtractor:
    """智能JSON提取器 - 正确处理字符串内的大括号"""

    @staticmethod
    def extract_first_dict(text: str) -> Optional[Dict]:
        """
        从文本中提取第一个完整的JSON字典对象

        关键改进：正确处理字符串边界，不会把字符串内的 { } 当作JSON结构

        Args:
            text: 包含JSON的文本

        Returns:
            解析后的字典，或None
        """
        if not text:
            return None

        # 找到第一个 {
        start = text.find('{')
        if start == -1:
            return None

        # 使用逐字符解析，正确处理字符串
        try:
            end = SmartJSONExtractor._find_dict_end(text, start)
            if end == -1:
                return None

            json_str = text[start:end+1]

            # 清理可能的问题
            cleaned = SmartJSONExtractor._clean_json(json_str)

            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError as e:
            print("[SmartJSONExtractor] 解析失败: {}".format(str(e)[:50]))
            # 尝试更激进的清理
            try:
                cleaned = SmartJSONExtractor._aggressive_clean(json_str)
                result = json.loads(cleaned)
                if isinstance(result, dict):
                    print("[SmartJSONExtractor] 激进清理后成功")
                    return result
            except:
                pass

        return None

    @staticmethod
    def _find_dict_end(text: str, start: int) -> int:
        """
        找到JSON字典的结束位置

        核心逻辑：正确处理字符串边界
        - 在字符串内时，不计算大括号
        - 正确处理转义字符（如 \", \\, \n）
        """
        brace_count = 0
        in_string = False
        escape_next = False

        for i in range(start, len(text)):
            char = text[i]

            if escape_next:
                # 当前字符被转义，不处理特殊含义
                escape_next = False
                continue

            if char == '\\' and in_string:
                # 进入转义模式
                escape_next = True
                continue

            if char == '"' and not escape_next:
                # 字符串边界切换
                in_string = not in_string
                continue

            # 只有不在字符串内时，才计算大括号
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return i

        return -1

    @staticmethod
    def _clean_json(json_str: str) -> str:
        """清理JSON字符串"""
        # 清理无效的LaTeX反斜杠
        cleaned = re.sub(r'\\(?![nrtbf\"\\/u])', '', json_str)
        return cleaned

    @staticmethod
    def _aggressive_clean(json_str: str) -> str:
        """
        激进清理 - 处理更复杂的问题

        包括：
        - 修复未转义的换行符（在字符串值内）
        - 修复字符串内未转义的引号
        """
        # 替换字符串值内的未转义换行符
        # 这是一个复杂的操作，需要逐��符处理

        result = []
        in_string = False
        escape_next = False

        for char in json_str:
            if escape_next:
                result.append(char)
                escape_next = False
                continue

            if char == '\\':
                result.append(char)
                escape_next = True
                continue

            if char == '"':
                in_string = not in_string
                result.append(char)
                continue

            if in_string and char == '\n':
                # 在字符串内遇到未转义换行，替换为空格
                result.append(' ')
                continue

            result.append(char)

        return ''.join(result)


# 测试
if __name__ == "__main__":
    test_cases = [
        # 正常JSON
        '{"key": "value"}',

        # 字符串内有类似JSON的内容（核心问题）
        '{"scores": {"impact": 8}, "rationale": "根据分析结果\\"{\\\"sub\\\": \\\"data\\\"}\\"，我们可以得出结论"}',

        # 字段值中有引号问题
        '{"scores": {"impact": 8}, "rationale": "这是\\"一个\\"问题"}',

        # 多行格式
        '''
{
    "scores": {
        "impact": 8
    },
    "rationale": "简单理由"
}
        ''',

        # 复杂嵌套
        '{"outer": {"inner": {"deep": "value"}}, "text": "说明文字"}',
    ]

    print("=" * 60)
    print("SmartJSONExtractor 测试")
    print("=" * 60)

    for i, test in enumerate(test_cases):
        print("\n测试 {}: {} 字符".format(i+1, len(test)))

        result = SmartJSONExtractor.extract_first_dict(test)
        if result:
            print("SUCCESS! Keys: {}".format(list(result.keys())))
        else:
            print("FAILED")

            # 对比：使用简单大括号匹配
            print("\n对比简单大括号匹配:")
            first_brace = test.find('{')
            brace_count = 0
            end = -1
            for j in range(first_brace, len(test)):
                c = test[j]
                if c == '{':
                    brace_count += 1
                elif c == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = j
                        break
            if end != -1:
                simple_str = test[first_brace:end+1]
                print("简单匹配长度: {} 字符".format(len(simple_str)))
                try:
                    simple_result = json.loads(simple_str)
                    print("简单匹配解析成功: {}".format(simple_result))
                except json.JSONDecodeError as e:
                    print("简单匹配解析失败: {}".format(str(e)[:50]))