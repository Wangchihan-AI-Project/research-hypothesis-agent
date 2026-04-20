# -*- coding: utf-8 -*-
"""直接测试 ValidationAgent 的 _parse_nature_response 方法"""
import sys
import os
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

# 加载环境变量
from dotenv import dotenv_values
env = dotenv_values('C:/Users/PC/research-hypothesis-agent/.env')
for k, v in env.items():
    os.environ[k] = v

from src.agents.validation_agent import ValidationAgent

# 创建agent实例
agent = ValidationAgent()

# 测试响应（模拟实际LLM返回）
test_response = '''
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
'''

print("测试 _parse_nature_response 方法")
print("="*60)

result = agent._parse_nature_response(test_response)

print("\n结果类型: {}".format(type(result)))
print("结果keys: {}".format(list(result.keys()) if isinstance(result, dict) else "不是dict"))

if isinstance(result, dict) and 'scores' in result:
    print("\nSUCCESS: 正确解析到评审结果")
    print("scores: {}".format(result['scores']))
else:
    print("\nFAILED: 解析结果不正确")