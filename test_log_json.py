# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.hypothesis_agent import HypothesisAgent, HypothesisOutput

# 从日志文件读取实际响应
with open('logs/chief_response_20260413_014552_attempt1.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取JSON部分
import re
json_match = re.search(r'```json\s*(\[.*?\])\s*```', content, re.DOTALL)
if json_match:
    json_str = json_match.group(1)
    print(f"找到JSON，长度: {len(json_str)}")

    import json
    try:
        data = json.loads(json_str)
        print(f"JSON解析成功，类型: {type(data)}, 长度: {len(data)}")
    except Exception as e:
        print(f"JSON解析失败: {e}")
        # 尝试找到错误位置
        import json.decoder
        try:
            json.decoder.JSONDecoder().decode(json_str)
        except json.JSONDecodeError as je:
            print(f"错误位置: 行{je.lineno}, 列{je.colno}: {je.msg}")

    # 测试 HypothesisOutput 验证
    if data and len(data) > 0:
        hyp = data[0]
        print(f"\n第一个假设的字段:")
        for key in hyp.keys():
            print(f"  - {key}: {len(hyp[key])} 字符")

        # 直接验证
        print(f"\n直接验证 HypothesisOutput...")
        try:
            validated = HypothesisOutput(**hyp)
            print(f"验证成功！")
        except Exception as e:
            print(f"验证失败: {type(e).__name__}: {e}")

        # 经过 _fill_hypothesis_to_meet_requirements 后验证
        print(f"\n经过 _fill_hypothesis_to_meet_requirements 后验证...")
        agent = HypothesisAgent()
        try:
            hyp_filled = agent._fill_hypothesis_to_meet_requirements(hyp.copy())
            print(f"字段填充完成")

            validated = HypothesisOutput(**hyp_filled)
            print(f"验证成功！")
        except Exception as e:
            print(f"验证失败: {type(e).__name__}: {e}")
else:
    print("未找到JSON")
