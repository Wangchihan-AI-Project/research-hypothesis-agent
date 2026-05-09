# -*- coding: utf-8 -*-
"""测试 safe_extract_json 对混合JSON响应的处理"""
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from src.utils.llm_utils import SafeExtractor

extractor = SafeExtractor()

# 模拟实际的LLM响应：开头是dict，中间有另一个array
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
        "breadth": "该假设跨越了多个领域"
    }
}
```

Recommended datasets:
```json
["UK Biobank (500,000+)", "MIMIC-IV (200,000+ ICU住院)", "GTEx (50,000+, 多组织)"]
```
'''

print("测试响应:")
print(test_response)
print("\n" + "="*50)

result = extractor.safe_extract_json(test_response)
print(f"\n解析结果类型: {type(result)}")
print(f"解析结果: {result}")

if isinstance(result, dict):
    print("\n✅ 成功！返回了dict格式")
else:
    print("\n❌ 失败！返回了array格式，需要修复")