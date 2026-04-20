# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.journal_if import build_journal_whitelist_query, get_whitelist_journal_names

print("="*60)
print("顶刊白名单查询串生成器测试")
print("="*60)

# 测试不同的 IF 阈值
for if_threshold in [5.0, 10.0, 20.0, 30.0]:
    query = build_journal_whitelist_query(if_threshold)
    print(f"\nIF ≥ {if_threshold}:")
    print(f"  查询串长度: {len(query)} 字符")
    print(f"  前100字符: {query[:100]}...")
    if query:
        print(f"  后50字符: ...{query[-50:]}")

# 显示期刊列表
print("\n" + "="*60)
print("顶刊白名单示例 (IF ≥ 10):")
print("="*60)
journals = get_whitelist_journal_names(10.0)
print(f"共 {len(journals)} 个期刊:")
for journal in journals[:10]:
    print(f"  - {journal}")
if len(journals) > 10:
    print(f"  ... 还有 {len(journals) - 10} 个")
