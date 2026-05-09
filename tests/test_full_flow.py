import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re
import json
from src.agents.hypothesis_agent import HypothesisAgent, HypothesisOutput

# 读取日志
with open('logs/chief_response_20260413_014552_attempt1.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# 模拟 _extract_json_hypotheses
json_match = re.search(r'```json\s*(\[.*?\])\s*```', content, re.DOTALL)
if json_match:
    json_str = json_match.group(1)
    # 应用清理
    json_str = re.sub(r'\\(?![nrtbf\\"\\/])', '', json_str)

    data = json.loads(json_str)
    print(f"JSON解析成功，{len(data)} 个假设\n")

    agent = HypothesisAgent()
    validated = []

    for i, hyp_dict in enumerate(data[:3], 1):  # 只测试前3个
        print(f"=== 假设 {i} ===")
        print(f"  原始 technical_route 长度: {len(hyp_dict.get('technical_route', ''))}")
        print(f"  原始 internal_reasoning 长度: {len(hyp_dict.get('internal_reasoning', ''))}")

        try:
            # 检查 statistical_novelty
            if 'statistical_novelty' not in hyp_dict or not hyp_dict.get('statistical_novelty'):
                print(f"  ✗ 缺少 statistical_novelty")
                continue

            # 填充字段
            hyp_filled = agent._fill_hypothesis_to_meet_requirements(hyp_dict.copy())
            print(f"  填充后 technical_route 长度: {len(hyp_filled.get('technical_route', ''))}")
            print(f"  填充后 internal_reasoning 长度: {len(hyp_filled.get('internal_reasoning', ''))}")

            # Pydantic 验证
            validated_hyp = HypothesisOutput(**hyp_filled)
            validated.append(validated_hyp)
            print(f"  ✓ 验证通过\n")
        except Exception as e:
            print(f"  ✗ 验证失败: {type(e).__name__}: {e}\n")

    print(f"\n总共验证通过: {len(validated)}/3")
else:
    print("未找到JSON")
