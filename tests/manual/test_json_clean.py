import re
import json

with open('C:/Users/PC/research-hypothesis-agent/logs/chief_response_20260413_014552_attempt1.txt', 'r', encoding='utf-8') as f:
    content = f.read()

json_match = re.search(r'```json\s*(\[.*?\])\s*```', content, re.DOTALL)
if json_match:
    json_str = json_match.group(1)
    print(f'原始JSON长度: {len(json_str)}')

    # 应用清理 - 移除无效的反斜杠
    # 保留有效的JSON转义序列 \\n, \\t, \\r, \\b, \\f, \\", \\\, \\/
    cleaned = re.sub(r'\\(?![nrtbf\\"\\/])', '', json_str)
    print(f'清理后长度: {len(cleaned)}')
    print(f'移除了 {len(json_str) - len(cleaned)} 个字符')

    try:
        result = json.loads(cleaned)
        print(f'\n解析成功！')
        print(f'类型: {type(result)}')
        print(f'列表长度: {len(result)}')

        if len(result) > 0:
            hyp = result[0]
            print(f'\n第一个假设:')
            print(f'  title: {hyp.get("title", "N/A")}')
            print(f'  technical_route: {len(hyp.get("technical_route", ""))} 字符')
    except json.JSONDecodeError as e:
        print(f'\n解析失败: {e}')
        # 显示错误位置附近的内容
        if hasattr(e, 'pos'):
            pos = e.pos
            print(f'错误位置 {pos} 附近: {repr(cleaned[max(0,pos-20):pos+20])}')
else:
    print('未找到JSON')
