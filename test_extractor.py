# -*- coding: utf-8 -*-
from src.utils.llm_utils import SafeExtractor
import re

test_json = '''```json
[
  {
    "title": "Test"
  }
]
```'''

print("测试 SafeExtractor...")

# 手动测试正则
array_pattern = r'```(?:json)?\s*(\[[\s\S]*?\])\s*```'
matches = re.findall(array_pattern, test_json)
print(f"array_pattern 匹配: {len(matches)} 个")

# 尝试直接解析
import json
try:
    # 去掉 ```json 和 ```
    clean = test_json.strip()
    if clean.startswith('```json'):
        clean = clean[7:]
    if clean.startswith('```'):
        clean = clean[3:]
    if clean.endswith('```'):
        clean = clean[:-3]
    clean = clean.strip()
    result = json.loads(clean)
    print(f"手动清理后解析成功: {type(result)}")
except Exception as e:
    print(f"手动清理后解析失败: {e}")

# 使用 SafeExtractor
try:
    result = SafeExtractor.safe_extract_json(test_json)
    print(f"SafeExtractor 成功: {type(result)}")
except Exception as e:
    print(f"SafeExtractor 失败: {e}")
