# -*- coding: utf-8 -*-
"""
测试范围输入解析功能
"""
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from src.cli.main import ResearchCLI
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 80)
print("范围输入解析测试")
print("=" * 80)

cli = ResearchCLI()

# 测试用例
test_cases = [
    # 日期范围测试
    ("2020-2024", "year", {"min": 2020, "max": 2024}),
    ("2020 ~ 2024", "year", {"min": 2020, "max": 2024}),
    ("2020+", "year", {"min": 2020, "max": None}),
    ("-2020", "year", {"min": None, "max": 2020}),
    ("..2020", "year", {"min": None, "max": 2020}),
    ("2024", "year", {"min": 2024, "max": 2024}),

    # IF范围测试
    ("5.0-20.0", "if", {"min": 5.0, "max": 20.0}),
    ("10+", "if", {"min": 10.0, "max": None}),
    ("-15", "if", {"min": None, "max": 15.0}),
    ("10.5", "if", {"min": 10.5, "max": 10.5}),
    ("IF 10-20", "if", {"min": 10.0, "max": 20.0}),

    # 边界情况
    ("", "year", {"min": None, "max": None}),
    ("invalid", "year", {"min": None, "max": None}),
]

print("\n日期范围测试:")
print("-" * 50)
date_tests = [t for t in test_cases if t[1] == "year"]
for input_str, type_info, expected in date_tests:
    result = cli._parse_range_input(input_str, type_info)
    status = "OK" if result == expected else "FAIL"
    print(f"  [{status}] '{input_str}' -> min={result['min']}, max={result['max']}")

print("\n影响因子范围测试:")
print("-" * 50)
if_tests = [t for t in test_cases if t[1] == "if"]
for input_str, type_info, expected in if_tests:
    result = cli._parse_range_input(input_str, type_info)
    status = "OK" if result == expected else "FAIL"
    print(f"  [{status}] '{input_str}' -> min={result['min']}, max={result['max']}")

# 测试实际过滤功能
print("\n" + "=" * 80)
print("实际过滤功能测试")
print("=" * 80)

from src.utils.pubmed import PubMedSearcher
from src.core.db_manager import get_db_manager
from src.core.database import Paper

searcher = PubMedSearcher()
db_manager = get_db_manager()

with db_manager.get_session() as session:
    papers = session.query(Paper).limit(30).all()
    papers_data = [{'pmid': p.pmid, 'title': p.title, 'journal': p.journal,
                    'publication_date': p.publication_date} for p in papers]

print(f"\n数据库论文: {len(papers_data)} 篇")

# 测试用户输入的各种格式
user_inputs = [
    ("2020-2024", None, "2020-2024年"),
    (None, "10+", "IF >= 10"),
    ("2018+", "5.0-15.0", "2018年后 且 IF 5-15"),
]

for date_str, if_str, desc in user_inputs:
    print(f"\n过滤条件: {desc}")

    # 解析日期范围
    start_year = end_year = None
    if date_str:
        date_result = cli._parse_range_input(date_str, 'year')
        start_year = date_result['min']
        end_year = date_result['max']
        print(f"  日期: {date_str} -> {start_year or '不限'}-{end_year or '不限'}")

    # 解析IF范围
    min_if = max_if = None
    if if_str:
        if_result = cli._parse_range_input(if_str, 'if')
        min_if = if_result['min']
        max_if = if_result['max']
        print(f"  IF: {if_str} -> {min_if or '不限'}-{max_if or '不限'}")

    # 应用过滤
    filtered = papers_data
    if start_year or end_year:
        filtered = searcher.filter_papers_by_date_range(filtered, start_year, end_year)
        print(f"  日期过滤后: {len(filtered)} 篇")

    if min_if is not None or max_if is not None:
        filtered = searcher.filter_papers_by_if_range(filtered, min_if, max_if)
        print(f"  IF过滤后: {len(filtered)} 篇")

    if filtered:
        print(f"  结果示例:")
        for p in filtered[:2]:
            print(f"    - {p['title'][:40]}... | {p['publication_date']} | {p['journal']}")

print("\n" + "=" * 80)
print("测试完成!")
print("=" * 80)

print("\n支持的输入格式:")
print("  日期范围: 2020-2024, 2020 ~ 2024, 2020+, -2024, ..2024")
print("  IF范围: 5.0-20.0, 10+, -15, IF 10-20")
