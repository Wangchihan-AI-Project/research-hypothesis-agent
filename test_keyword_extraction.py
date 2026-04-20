# -*- coding: utf-8 -*-
"""
关键词提取回退逻辑测试
验证修复后的关键词提取不会回退到宽泛的默认词
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.validation_agent import ValidationAgent

print("=" * 70)
print("Keyword Extraction Fallback Logic Test")
print("=" * 70)

agent = ValidationAgent()

# 测试案例：心力衰竭 + 热力学
test_hypothesis = {
    'title': '基于热力学熵变的心力衰竭心脏能量代谢重构研究',
    'core_hypothesis': '心力衰竭患者心脏存在能量代谢异常，线粒体功能紊乱导致ATP合成不足。通过热力学第二定律分析心脏能量流动的熵增过程，识别能量代谢瓶颈。',
    'description': '本研究利用热力学原理分析心力衰竭过程中的能量代谢变化，重点关注线粒体氧化磷酸化效率下降和心肌细胞能量耗竭机制。',
    'expected_breakthrough': '首次将热力学熵变理论应用于心力衰竭的代谢分析',
    'data_requirements': '心力衰竭患者心肌组织样本和scRNA-seq数据'
}

print("\n[Test Case] Heart Failure + Thermodynamics")
print("-" * 50)
print(f"Title: {test_hypothesis['title']}")
print(f"Core Hypothesis: {test_hypothesis['core_hypothesis'][:60]}...")

keywords = agent._extract_keywords_from_title(test_hypothesis)
print(f"\nExtracted keywords ({len(keywords)}):")
for kw in keywords:
    print(f"  - {kw}")

# 验证关键词质量
print("\n[Validation]")
checks = {
    "Contains 'heart' or 'cardiac' or 'failure'": any(
        any(term in kw.lower() for term in ['heart', 'cardiac', 'failure', '心力衰竭'])
        for kw in keywords
    ),
    "Contains 'thermodynamic' or 'metabolism' or 'entropy'": any(
        any(term in kw.lower() for term in ['thermodynamic', 'metabolism', 'entropy', '热力学', '代谢'])
        for kw in keywords
    ),
    "NOT only generic ML terms": not all(
        any(term in kw.lower() for term in ['machine learning', 'deep learning', 'neural network', 'ai'])
        for kw in keywords
    ),
    "Has at least 3 keywords": len(keywords) >= 3
}

for check, result in checks.items():
    status = "[PASS]" if result else "[FAIL]"
    print(f"  {status} {check}")

all_passed = all(checks.values())
print("\n" + "=" * 70)
if all_passed:
    print("[SUCCESS] All keyword extraction tests passed!")
else:
    print("[WARNING] Some tests failed - please review")
print("=" * 70)

# 测试案例2：只有标题的情况（兜底方案）
print("\n\n[Test Case] Title-only fallback")
print("-" * 50)
simple_hypothesis = {
    'title': 'CRISPRa actinomycetes heteroresistance persister cells',
    'core_hypothesis': '',
    'description': ''
}

keywords2 = agent._extract_keywords_from_title(simple_hypothesis)
print(f"Title: {simple_hypothesis['title']}")
print(f"\nExtracted keywords ({len(keywords2)}):")
for kw in keywords2:
    print(f"  - {kw}")

# 验证至少返回了核心标题部分
if keywords2:
    print("\n[PASS] Fallback mechanism works - returned title-based keywords")
else:
    print("\n[FAIL] Fallback mechanism failed - no keywords returned")

print("\n" + "=" * 70)
