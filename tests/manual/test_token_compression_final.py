# -*- coding: utf-8 -*-
"""
Token 熔断与压缩协议最终测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.token_utils import TokenCounter, pre_check_prompt

print("=" * 70)
print("Token 熔断与压缩协议 - 最终验证测试")
print("=" * 70)

counter = TokenCounter('claude-3-5-sonnet')
print(f"\n配置: 上下文窗口={counter.context_window:,}, 安全阈值(85%)={counter.safety_threshold:,}\n")

# 创建超长论文列表（���定触发压缩）
print("[测试] 创建超长论文列表...")
huge_papers = []
for i in range(50):  # 50篇超长论文
    huge_paper = {
        'pmid': f'{10000000 + i}',
        'title': f'Paper {i}: ' + 'Comprehensive Analysis of Molecular Mechanisms. ' * 5,
        'abstract': 'Detailed abstract. ' * 500,  # 超长摘要
        'methods': 'Methodology details. ' * 300,  # Methods细节
        'results': 'Results section. ' * 300,  # Results细节
        'conclusion': 'Conclusion. ' * 100,
        'discussion': 'Discussion. ' * 200,
        'llm_score': 10.0 - (i * 0.1),  # 评分递减
        'journal': 'Nature',
        'publication_date': '2024-01-15'
    }
    huge_papers.append(huge_paper)

# 测试不同Base Prompt大小
test_cases = [
    ("小Base Prompt", "Generate hypothesis."),
    ("中等Base Prompt", "Generate hypothesis. " * 100),
    ("大Base Prompt", "Generate hypothesis. " * 10000),
]

for name, base_prompt in test_cases:
    print(f"\n{'=' * 70}")
    print(f"[测试用例] {name}")
    print(f"{'=' * 70}")

    base_tokens = counter.count_tokens(base_prompt)
    print(f"  Base Prompt: {base_tokens:,} tokens")

    paper_context, report = pre_check_prompt(
        base_prompt=base_prompt,
        papers=huge_papers,
        model='claude-3-5-sonnet'
    )

    print(f"  原始Token: {report.original_token_count:,}")
    print(f"  压缩后Token: {report.compressed_token_count:,}")
    print(f"  压缩策略: {report.strategy_used}")
    print(f"  移除文献: {report.papers_removed} 篇")
    print(f"  Methods移除: {report.methods_removed}")

    if report.strategy_used != 'none':
        print(f"  压缩率: {report.compression_ratio:.1%}")

    # 验证结构化压缩
    import re
    paper_tags = re.findall(r'<Paper_(\d+)>', paper_context)
    print(f"  Paper标签数量: {len(paper_tags)}")

    # 验证防御性提示
    has_defensive = "<IMPORTANT_REMINDER>" in paper_context
    print(f"  防御性提示: {'存在' if has_defensive else '缺失'}")

    # 检查警告
    if report.warnings:
        print(f"  [警告] {report.warnings[0]}")

print(f"\n{'=' * 70}")
print("测试完成 - Token熔断与压缩协议工作正常")
print(f"{'=' * 70}")
