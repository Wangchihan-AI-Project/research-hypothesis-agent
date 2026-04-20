# -*- coding: utf-8 -*-
"""
Token 熔断与压缩协议测试脚本（修正版）
验证 Token 预检、安全红线和分级压缩策略
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.token_utils import TokenCounter, PaperCompressor, pre_check_prompt

print("=" * 70)
print("Token 熔断与压缩协议测试")
print("=" * 70)

# 测试1: Token计数器
print("\n[测试1] Token计数器")
print("-" * 50)
counter = TokenCounter('claude-3-5-sonnet')
print(f"  模型: claude-3-5-sonnet")
print(f"  上下文窗口: {counter.context_window:,}")
print(f"  安全阈值(85%): {counter.safety_threshold:,}")

# 测试文本计数
test_texts = [
    ("短文本", "Hello world"),
    ("中文文本", "这是一个关于CRISPR基因编辑的研究"),
    ("混合文本", "CRISPR-Cas9 is a revolutionary gene-editing tool that has transformed 生物医学研究.")
]

for name, text in test_texts:
    tokens = counter.count_tokens(text)
    print(f"  {name}: {tokens} tokens")

# 测试2: 安全检查
print("\n[测试2] 安全红线检查")
print("-" * 50)
small_text = "A" * 1000
large_text = "B" * 200000  # 超过安全阈值

small_tokens = counter.count_tokens(small_text)
large_tokens = counter.count_tokens(large_text)

print(f"  小文本: {small_tokens} tokens - 安全: {counter.is_safe(small_tokens)}")
print(f"  大文本: {large_tokens} tokens - 安全: {counter.is_safe(large_tokens)}")
print(f"  溢出比例: {counter.get_overflow_ratio(large_tokens):.1%}")

# 测试3: 论文压缩 - 无需压缩场景
print("\n[测试3] 论文压缩 - 无需压缩")
print("-" * 50)

test_papers = [
    {
        'pmid': '12345678',
        'title': 'CRISPR gene editing in cancer therapy',
        'abstract': 'This study demonstrates the efficacy of CRISPR-Cas9 in targeting oncogenes.',
        'llm_score': 8.5,
        'llm_reason': 'Highly relevant to the research topic.'
    },
    {
        'pmid': '87654321',
        'title': 'Single-cell sequencing reveals tumor heterogeneity',
        'abstract': 'We used scRNA-seq to analyze tumor microenvironment.',
        'llm_score': 7.2,
        'llm_reason': 'Relevant methodology.'
    }
]

base_prompt = "Generate a research hypothesis based on the following papers."
paper_context, report = pre_check_prompt(
    base_prompt=base_prompt,
    papers=test_papers,
    model='claude-3-5-sonnet'
)

print(f"  压缩策略: {report.strategy_used}")
print(f"  最终Token: {report.compressed_token_count:,}")
print(f"  论文上下文长度: {len(paper_context)} 字符")

# 测试4: 论文压缩 - 需要压缩场景（真实场景）
print("\n[测试4] 论文压缩 - 需要压缩（真实场景）")
print("-" * 50)

# 创建大量测试论文（论文本身很长）
many_papers = []
for i in range(100):
    # 每篇论文的摘要都很长
    long_abstract = f"This is a comprehensive abstract for paper {i}. " \
                    f"The study investigates the molecular mechanisms of disease progression. " \
                    f"We performed extensive analysis using single-cell RNA sequencing, " \
                    f"proteomics, and metabolomics approaches. " * 15

    many_papers.append({
        'pmid': f'{10000000 + i}',
        'title': f'Paper {i}: Molecular mechanisms in disease progression',
        'abstract': long_abstract,
        'llm_score': 10.0 - (i * 0.05),  # 评分递减
        'journal': f'Nature Biotechnology',
        'publication_date': f'2024-{(i % 12) + 1:02d}-15'
    })

# 使用正常大小的base_prompt
large_base_prompt = """Generate a detailed research hypothesis based on the following papers.

Requirements:
1. Analyze the molecular mechanisms described in the papers
2. Identify gaps in current understanding
3. Propose a novel experimental approach
4. Include statistical considerations"""

paper_context, report = pre_check_prompt(
    base_prompt=large_base_prompt,
    papers=many_papers,
    model='claude-3-5-sonnet'
)

print(f"  原始Token: {report.original_token_count:,}")
print(f"  压缩后Token: {report.compressed_token_count:,}")
print(f"  压缩率: {report.compression_ratio:.1%}")
print(f"  压缩策略: {report.strategy_used}")
print(f"  移除文献: {report.papers_removed} 篇")
print(f"  移除Methods: {report.methods_removed}")
if report.warnings:
    for w in report.warnings:
        print(f"  [警告] {w}")

# 测试5: 结构化压缩验证
print("\n[测试5] 结构化压缩验证")
print("-" * 50)

import re
paper_tags = re.findall(r'<Paper_(\d+)>', paper_context)
print(f"  发现的Paper标签: {len(paper_tags)} 个")
if paper_tags:
    tag_numbers = sorted(list(set([int(t) for t in paper_tags])))
    expected_range = list(range(min(tag_numbers), max(tag_numbers) + 1))
    is_continuous = tag_numbers == expected_range
    print(f"  编号范围: Paper_{min(paper_tags)} 到 Paper_{max(paper_tags)}")
    print(f"  编号连续: {is_continuous}")
    if is_continuous:
        print(f"  [通过] Paper引用标记保持结构化")
else:
    if "无具体论文引用" in paper_context or not paper_context.strip():
        print(f"  [信息] 压缩后无论文内容（输入过大）")
    else:
        print(f"  [警告] 未找到Paper标签")

# 测试6: 防御性提示存在性
print("\n[测试6] 防御性提示检查")
print("-" * 50)
has_defensive_note = "<IMPORTANT_REMINDER>" in paper_context
has_warning = "严禁" in paper_context or "捏造" in paper_context
print(f"  防御性提示存在: {has_defensive_note}")
print(f"  警告关键词存在: {has_warning}")
if has_defensive_note and has_warning:
    print(f"  [通过] 防御性提示完整")

# 测试7: 分级压缩策略验证
print("\n[测试7] 分级压缩策略验证")
print("-" * 50)

# 测试轻微超标（应触发初级压缩）
light_test_papers = []
for i in range(30):  # 30篇论文，可能轻微超标
    light_test_papers.append({
        'pmid': f'{20000000 + i}',
        'title': f'Paper {i}: Study on disease mechanisms',
        'abstract': f'Detailed abstract for paper {i}. ' * 20,
        'llm_score': 8.0,
        'methods': 'We used single-cell RNA sequencing and proteomics analysis. ' * 10
    })

light_base = "Generate hypothesis. " * 500  # 较大的base prompt
light_context, light_report = pre_check_prompt(
    base_prompt=light_base,
    papers=light_test_papers,
    model='claude-3-5-sonnet'
)

print(f"  轻微超标场景:")
print(f"    策略: {light_report.strategy_used}")
print(f"    Methods移除: {light_report.methods_removed}")
print(f"    文献移除: {light_report.papers_removed} 篇")

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)
