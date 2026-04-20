# -*- coding: utf-8 -*-
"""测试 array在前 dict在后的场景"""
import sys
import os
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from dotenv import dotenv_values
env = dotenv_values('C:/Users/PC/research-hypothesis-agent/.env')
for k, v in env.items():
    os.environ[k] = v

from src.agents.validation_agent import ValidationAgent

agent = ValidationAgent()

# 测试响应: array在前，dict在后（这是出问题的场景）
test_response = '''
推荐数据集:
```json
["UK Biobank (500,000+)", "MIMIC-IV (200,000+ ICU住院)", "GTEx (50,000+, 多组织)"]
```

评审结果如下:
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
        "breadth": "跨领域创新研究"
    }
}
```
'''

print("测试 array在前 dict在后 的场景")
print("="*60)

result = agent._parse_nature_response(test_response)

print("\n结果类型: {}".format(type(result)))
if isinstance(result, dict):
    print("结果keys: {}".format(list(result.keys())))
    if 'scores' in result:
        print("\nSUCCESS: 正确跳过array，提取到dict评审结果")
        print("scores: {}".format(result['scores']))
    else:
        print("\nFAILED: 提取到dict但没有scores字段")
else:
    print("\nFAILED: 返回的不是dict类型")