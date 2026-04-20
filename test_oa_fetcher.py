# -*- coding: utf-8 -*-
"""
测试开放获取文献下载和PDF解析功能
"""
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

from src.utils.oa_paper_fetcher import OAPaperFetcher
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 80)
print("开放获取文献下载和PDF解析测试")
print("=" * 80)

fetcher = OAPaperFetcher()

# 测试1: PMC开放获取论文
print("\n[测试1] PMC开放获取���文")
print("-" * 50)
test_pmid = "30390086"  # Nature Communications OA论文
print(f"PMID: {test_pmid}")

result = fetcher.fetch_paper_content(test_pmid)
print(f"  成功: {result['success']}")
print(f"  来源: {result['source']}")
print(f"  字数: {result.get('word_count', 0)}")

if result['content']:
    preview = result['content'][:300].replace('\n', ' ')
    print(f"  内容预览: {preview}...")
else:
    print(f"  错误: {result.get('error', 'Unknown')}")

# 测试2: 摘要备用方案
print("\n[测试2] 摘要备用方案")
print("-" * 50)
test_pmid2 = "32479800"  # 非OA论文
print(f"PMID: {test_pmid2}")

result2 = fetcher.fetch_paper_content(test_pmid2)
print(f"  成功: {result2['success']}")
print(f"  来源: {result2['source']}")
print(f"  消息: {result2.get('message', 'N/A')}")

# 获取详细摘要
abstract_result = fetcher.get_paper_abstract_fallback(test_pmid2)
if abstract_result['success']:
    metadata = abstract_result.get('metadata', {})
    print(f"  标题: {metadata.get('title', 'N/A')[:60]}...")
    print(f"  摘要长度: {len(metadata.get('abstract', ''))} 字符")
    print(f"  关键词: {metadata.get('keywords', 'N/A')}")

# 测试3: PDF解析功能
print("\n[测试3] PDF解析功能测试")
print("-" * 50)

# 检查是否有缓存的PDF文件
import os
cache_dir = "C:/Users/PC/research-hypothesis-agent/data/papers"
if os.path.exists(cache_dir):
    pdf_files = [f for f in os.listdir(cache_dir) if f.endswith('.pdf')]
    if pdf_files:
        print(f"  找到 {len(pdf_files)} 个缓存PDF文件")
        for pdf in pdf_files[:3]:
            print(f"    - {pdf}")

        # 测试解析第一个PDF
        if pdf_files:
            test_pdf = os.path.join(cache_dir, pdf_files[0])
            print(f"\n  解析测试: {pdf_files[0]}")

            content = fetcher._parse_pdf(test_pdf)
            if content:
                words = len(content.split())
                chars = len(content)
                print(f"    成功! 字数: {words}, 字符数: {chars}")
                print(f"    预览: {content[:150]}...")
            else:
                print(f"    解析失败")
    else:
        print("  没有缓存的PDF文件")
else:
    print("  缓存目录不存在")

# 测试4: 批量获取
print("\n[测试4] 批量获取功能")
print("-" * 50)

test_pmids = ["30390086", "32479800"]
print(f"  PMID列表: {test_pmids}")

batch_results = fetcher.batch_fetch_papers(test_pmids)
print(f"\n  批量获取结果:")
for r in batch_results:
    pmid = r['pmid']
    success = r['result']['success']
    source = r['result']['source']
    words = r['result'].get('word_count', 0)
    print(f"    PMID {pmid}: {source} ({words} 字)")

print("\n" + "=" * 80)
print("测试完成!")
print("=" * 80)

print("\n功能说明:")
print("  1. 自动从PMC下载OA论文PDF")
print("  2. 通过DOI查找OA版本")
print("  3. 搜索bioRxiv等预印本")
print("  4. PDF下载失败时自动使用摘要作为备用")
print("  5. 支持批量获取")
