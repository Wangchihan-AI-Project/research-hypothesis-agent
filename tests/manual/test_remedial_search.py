# -*- coding: utf-8 -*-
"""
测试补救检索反馈循环

验证：
1. 关键词提取
2. 补救检索
3. 增强反馈提示生成
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.remedial_search import RemedialSearchEngine, create_remedial_search_prompt
import asyncio


def test_keyword_extraction():
    """测试关键词提取"""
    print("=" * 60)
    print("测试1: 关键词提取")
    print("=" * 60)

    engine = RemedialSearchEngine()

    feedback_context = {
        'attack_report': {
            'critical_flaws': [
                '缺少因���推断框架',
                '未进行样本量计算',
                '中介分析不完整'
            ],
            'methodological_issues': [
                '未考虑混杂因素',
                '缺少敏感性分析'
            ],
            'statistical_concerns': [
                '统计功效不足',
                '未进行多重检验校正'
            ]
        },
        'defense_result': {
            'critical_issues': [
                '需要补充 Bootstrap 置信区间',
                'E-value 敏感性分析缺失'
            ],
            'final_verdict': '假设存在严重统计学缺陷，需要补充因果推断和统计功效分析。'
        }
    }

    keywords = engine.extract_deficiency_keywords(feedback_context)
    print(f"提取到的关键词 ({len(keywords)} 个):")
    for kw in keywords:
        print(f"  - {kw}")

    print()
    return keywords


def test_remedial_search():
    """测试补救检索（模拟模式）"""
    print("=" * 60)
    print("测试2: 补救检索 (模拟模式)")
    print("=" * 60)

    engine = RemedialSearchEngine(pubmed_searcher=None)

    feedback_context = {
        'attack_report': {
            'critical_flaws': ['缺少因果推断框架', '未进行样本量计算'],
            'methodological_issues': [],
            'statistical_concerns': []
        },
        'defense_result': {
            'critical_issues': [],
            'final_verdict': '需要补充因果推断和功效分析'
        }
    }

    research_topic = "ADNI MRI Alzheimer biomarkers"

    async def run_search():
        return await engine.execute_remedial_search(
            feedback_context=feedback_context,
            research_topic=research_topic,
            max_results=3,
            year_start=2020
        )

    result = asyncio.run(run_search())

    print(f"补救检索结果:")
    print(f"  成功: {result.get('success')}")
    print(f"  关键词: {result.get('keywords', [])}")
    print(f"  查询: {result.get('query', '')}")
    print(f"  论文数: {len(result.get('papers', []))}")

    for i, paper in enumerate(result.get('papers', [])[:2], 1):
        print(f"\n  论文 {i}:")
        print(f"    标题: {paper.get('title', 'N/A')[:60]}...")
        print(f"    期刊: {paper.get('journal', 'N/A')}")

    print()
    return result


def test_enhanced_feedback():
    """测试增强反馈提示生成"""
    print("=" * 60)
    print("测试3: 增强反馈提示生成")
    print("=" * 60)

    hypothesis_data = {
        'title': 'ADNI MRI 中的海马体积与认知衰退关系研究',
        'description': '本研究拟探索海马体积变化与MMSE评分下降的关联...'
    }

    feedback_context = {
        'attack_report': {
            'critical_flaws': ['缺少因果推断框架', '未进行样本量计算']
        },
        'defense_result': {
            'critical_issues': ['需要补充 Bootstrap 置信区间'],
            'final_verdict': '需要补充因果推断和功效分析'
        }
    }

    remedial_result = {
        'remedial_context': '''
## 📚 补救检索结果

**提取的关键词**: causal inference, power analysis

**检索到的最新方法学文献**:

### 文献 1
**标题**: Modern Causal Inference Frameworks for Observational Studies
**期刊**: Nature Methods
**发表日期**: 2024-01-15
**摘要**: This systematic review examines recent advances in causal inference...
'''
    }

    enhanced_prompt = create_remedial_search_prompt(
        original_hypothesis=hypothesis_data,
        feedback_context=feedback_context,
        remedial_search_result=remedial_result
    )

    print("增强反馈提示（前800字符）:")
    print("-" * 60)
    print(enhanced_prompt[:800] + "...")

    print()
    return enhanced_prompt


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    print("\n" + "=" * 60)
    print("补救检索反馈循环测试")
    print("=" * 60 + "\n")

    # 运行测试
    test_keyword_extraction()
    test_remedial_search()
    test_enhanced_feedback()

    print("=" * 60)
    print("所有测试完成！")
    print("=" * 60)
