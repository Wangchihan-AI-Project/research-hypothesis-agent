# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.llm_utils import SafeExtractor

test_json = '''```json
[
  {
    "title": "基于非交换几何的电子病历高维张量流形解耦",
    "core_problem": "测试内容",
    "core_hypothesis": "测试内容",
    "technical_route": "数据：MIMIC-IV或eICU-CRD；方法：构建非交换代数结构",
    "expected_breakthrough": "测试内容",
    "clinical_value": "测试内容",
    "statistical_novelty": "测试内容",
    "internal_reasoning": "测试内容",
    "crack_mode": "降维打击",
    "paradigm_framework": "测试框架",
    "data_requirements": "测试数据需求",
    "search_queries": ["test"]
  }
]
```'''

print("测试 SafeExtractor 解析...")
result = SafeExtractor.safe_extract_json(test_json)
print(f'解析结果类型: {type(result)}')
print(f'是否为列表: {isinstance(result, list)}')
print(f'列表长度: {len(result) if isinstance(result, list) else "N/A"}')
