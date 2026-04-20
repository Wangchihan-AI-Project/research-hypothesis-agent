# -*- coding: utf-8 -*-
"""
简单的语法检查脚本
验证所有新增文件的语法正确性
"""
import sys
import py_compile
from pathlib import Path

print("=" * 70)
print("语法检查 - 验证 Python 文件语法")
print("=" * 70)

files_to_check = [
    "src/utils/relevance_scorer.py",
    "src/agents/paper_search_agent.py",
    "src/agents/genai_expert_agent.py",
    "test_genai_expert.py",
    "test_two_stage_funnel.py"
]

project_root = Path(__file__).parent
all_ok = True

for file_path in files_to_check:
    full_path = project_root / file_path
    if not full_path.exists():
        print(f"[SKIP] {file_path} - 文件不存在")
        continue

    try:
        py_compile.compile(str(full_path), doraise=True)
        print(f"[OK] {file_path}")
    except py_compile.PyCompileError as e:
        print(f"[ERROR] {file_path}")
        print(f"  {e}")
        all_ok = False

print("\n" + "=" * 70)
if all_ok:
    print("✅ 所有文件语法检查通过!")
else:
    print("❌ 部分文件存在语法错误")
print("=" * 70)

# 检查关键类和方法
print("\n检查关键类和方法...")
print("-" * 70)

checks = [
    ("RelevanceScorer", "src/utils/relevance_scorer.py"),
    ("BatchScorer", "src/utils/relevance_scorer.py"),
    ("GenAIExpertAgent", "src/agents/genai_expert_agent.py"),
    ("execute_two_stage_funnel", "src/agents/paper_search_agent.py"),
]

for class_name, file_path in checks:
    full_path = project_root / file_path
    content = full_path.read_text(encoding='utf-8')
    if class_name in content:
        print(f"[OK] {class_name} 在 {file_path}")
    else:
        print(f"[MISSING] {class_name} 不在 {file_path}")

print("\n" + "=" * 70)
print("检查完成!")
print("=" * 70)
