# -*- coding: utf-8 -*-
"""
测试全文获取集成功能
"""
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

from src.core.orchestrator import Orchestrator
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 80)
print("全文获取集成测试")
print("=" * 80)

orchestrator = Orchestrator()

# 测试1: 搜索论文并获取全文
print("\n[测试1] 搜索论文 + 获取全文")
print("-" * 50)

session_result = orchestrator.start_session("machine learning bioinformatics")
session_id = session_result['session_id']
print(f"会话ID: {session_id}")

# 搜索少量论文进行测试
search_result = orchestrator.search_papers(
    query="bioinformatics",
    max_results=3,
    fetch_full_text=True,
    max_full_text=2
)

if search_result['success']:
    papers = search_result['papers']
    print(f"找到 {len(papers)} 篇论文")

    # 显示每篇论文的内容统计
    for i, paper in enumerate(papers, 1):
        title = paper.get('title', 'N/A')[:50]
        full_text_source = paper.get('full_text_source', 'N/A')
        full_text_len = paper.get('full_text_word_count', 0)
        abstract_len = len(paper.get('abstract', ''))

        print(f"\n  [论文 {i}]")
        print(f"    标题: {title}...")
        print(f"    内容来源: {full_text_source}")
        print(f"    字数: 全文={full_text_len}, 摘要={abstract_len}")

        # 如果有全文，显示预览
        full_text = paper.get('full_text', '')
        if full_text and len(full_text) > 100:
            print(f"    全文预览: {full_text[:150]}...")

# 测试2: 使用全文内容生成假设
print("\n[测试2] 使用全文内容生成假设")
print("-" * 50)

# 只使用有全文的论文
papers_with_full_text = [p for p in search_result['papers']
                          if p.get('full_text') and len(p.get('full_text', '')) > 200]

print(f"有足够内容的论文: {len(papers_with_full_text)} 篇")

if len(papers_with_full_text) >= 1:
    hypothesis_result = orchestrator.generate_hypotheses(
        papers=papers_with_full_text,
        research_field="生物信息学",
        focus_areas=["机器学习", "基因组学"]
    )

    if hypothesis_result['success']:
        hypotheses = hypothesis_result['hypotheses']
        print(f"成功生成 {len(hypotheses)} 个假设")

        for i, h in enumerate(hypotheses, 1):
            print(f"\n  [假设 {i}]")
            print(f"    标题: {h.get('title', 'N/A')[:60]}...")
            print(f"    描述: {h.get('description', 'N/A')[:100]}...")
            print(f"    新颖性: {h.get('novelty', 'N/A')[:80]}...")
    else:
        print(f"假设生成失败: {hypothesis_result.get('error')}")
else:
    print("论文内容不足，跳过假设生成")

# 测试3: 对比全文 vs 摘要的效果
print("\n[测试3] 全文 vs 摘要效果对比")
print("-" * 50)

# 选择一篇有足够摘要的论文
test_paper = None
for paper in search_result['papers']:
    abstract = paper.get('abstract', '')
    if len(abstract) > 200:
        test_paper = paper
        break

if test_paper:
    abstract_len = len(test_paper.get('abstract', ''))
    full_text_len = test_paper.get('full_text_word_count', 0)

    print(f"论文: {test_paper.get('title', 'N/A')[:40]}...")
    print(f"  摘要长度: {abstract_len} 字符")
    print(f"  全文长度: {full_text_len} 字")
    print(f"  扩展比: {full_text_len / abstract_len if abstract_len > 0 else 0:.1f}x")

    if full_text_len > abstract_len:
        print("  结论: 全文提供了更多信息，有助于生成更准确的假设")
    else:
        print("  结论: 摘要模式，全文获取失败或论文不可用")

# 完成会话
print("\n[总结] 完成会话")
print("-" * 50)

complete_result = orchestrator.complete_session()
summary = complete_result['summary']

print(f"  搜索论文: {summary['papers_found']} 篇")
print(f"  生成假设: {summary['hypotheses_generated']} 个")
print(f"  验证假设: {summary['hypotheses_validated']} 个")

print("\n" + "=" * 80)
print("测试完成!")
print("=" * 80)

print("\n集成功能:")
print("  1. 搜索论文时自动获取全文（可配置数量）")
print("  2. PDF下载失败时自动使用详细摘要")
print("  3. 假设生成时优先使用全文内容")
print("  4. 显示全文获取统计信息")
