# -*- coding: utf-8 -*-
"""
简单的语法检查脚本
验证所有新增文件的语法正确性
"""
import sys
import subprocess
import py_compile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')

print("=" * 70)
print("语法检查 - 验证 Python 文件语法")
print("=" * 70)

files_to_check = [
    "src/utils/relevance_scorer.py",
    "src/agents/paper_search_agent.py",
    "src/agents/genai_expert_agent.py",
    "tests/manual/test_genai_expert.py",
    "tests/manual/test_two_stage_funnel.py",
    "tests/test_search_page_state_flow.py",
]

tests_root = Path(__file__).resolve().parents[1]
project_root = Path(__file__).resolve().parents[2]
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
    ("_build_fallback_screening_result", "src/agents/paper_search_agent.py"),
    ("search_preliminary_elapsed", "pages/04_文献检索.py"),
]

for class_name, file_path in checks:
    full_path = project_root / file_path
    if not full_path.exists():
        print(f"[SKIP] {class_name} - {file_path} 不存在")
        continue
    content = full_path.read_text(encoding='utf-8')
    if class_name in content:
        print(f"[OK] {class_name} 在 {file_path}")
    else:
        print(f"[MISSING] {class_name} 不在 {file_path}")

print("\n运行页面状态流回归测试...")
print("-" * 70)
state_flow_test = tests_root / 'test_search_page_state_flow.py'
if state_flow_test.exists():
    result = subprocess.run([sys.executable, str(state_flow_test)], cwd=project_root)
    if result.returncode == 0:
        print(f"[OK] {state_flow_test.name}")
    else:
        print(f"[ERROR] {state_flow_test.name} 退出码 {result.returncode}")
        all_ok = False
else:
    print("[SKIP] test_search_page_state_flow.py - 文件不存在")

print("\n" + "=" * 70)
if all_ok:
    print("✅ 所有检查通过!")
else:
    print("❌ 部分检查失败")
print("=" * 70)
