# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')

from src.utils.llm_utils import SafeExtractor

extractor = SafeExtractor()

# Test with array response (simulating actual LLM output)
response = '''
```json
[
  {
    "title": "Test Hypothesis 1",
    "core_problem": "This is the core problem description for test 1"
  },
  {
    "title": "Test Hypothesis 2",
    "core_problem": "This is the core problem description for test 2"
  }
]
```
'''

result = extractor.safe_extract_json(response)
print(f'Type: {type(result)}')
print(f'Is list: {isinstance(result, list)}')
if isinstance(result, list):
    print(f'Length: {len(result)}')
    print(f'First item: {result[0]}')
else:
    print(f'Result: {result}')