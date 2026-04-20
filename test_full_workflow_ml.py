# -*- coding: utf-8 -*-
"""
完整流程测试：从文献搜索到假设生成再到评审
使用 "machine learning" 作为测试关键词
"""
import os
import sys

# 设置环境变量
os.environ['ANTHROPIC_API_KEY'] = 'sk-y3WE6cIOgqbsg7tXs2LNSKXZkeh9E1zfJvdC763KraN3lTDw'
os.environ['ANTHROPIC_BASE_URL'] = 'https://cloud.hongqiye.com'
os.environ['CLAUDE_MODEL'] = 'claude-opus-4-6'
os.environ['PUBMED_EMAIL'] = 'wanghan3698@gmail.com'
os.environ['PUBMED_API_KEY'] = '2ee2706d111ff8ff5ccce94a25d883fb5709'

sys.path.insert(0, 'src')

from utils.pubmed import PubMedSearcher
from agents.hypothesis_agent import ChiefScientistAgent
from agents.validation_agent import ValidationAgent


def test_full_workflow():
    """测试完整工作流程"""

    print("=" * 70)
    print("完整流程测试: Machine Learning in Bioinformatics")
    print("=" * 70)
    print()

    # 步骤1: 文献搜索
    print("[步骤 1/3] 文献搜索")
    print("-" * 70)

    searcher = PubMedSearcher(
        email=os.getenv('PUBMED_EMAIL'),
        api_key=os.getenv('PUBMED_API_KEY')
    )

    # 搜索机器学习在生物信息学中的应用
    query = "machine learning bioinformatics genomics"
    print(f"搜索关键词: {query}")
    print()

    papers = searcher.search_papers(
        query=query,
        max_results=10,
        enable_filter=False  # 不过滤，获取更多结果
    )

    print(f"找到 {len(papers)} 篇论文")
    print()

    if not papers:
        print("[ERROR] 未找到论文，终止测试")
        return

    # 显示前3篇论文
    print("前3篇论文摘要:")
    for i, paper in enumerate(papers[:3], 1):
        print(f"  {i}. {paper['title'][:60]}...")
        print(f"     期刊: {paper.get('journal', 'N/A')} | PMID: {paper['pmid']}")
    print()

    # 步骤2: 生成假设
    print("[步骤 2/3] 首席科学家 - 生成In Silico假设")
    print("-" * 70)

    # 构建文献报告
    literature_report = f"""
# 机器学习在生物信息学中的应用 - 文献调研报告

## 研究现状

机器学习技术已广泛应用于生物信息学的各个领域。通过对{len(papers)}篇相关论文的分析，发现以下主要趋势：

1. **深度学习在基因组学中的应用**: 卷积神经网络(CNN)和循环神经网络(RNN)被用于序列分析、变异预测等任务。

2. **多组学数据整合**: 集成基因组、转录组、蛋白质组数据成为研究热点，但缺乏有效的整合框架。

3. **单细胞数据分析**: 随着单细胞测序技术的发展，机器学习方法在细胞类型识别、轨迹推断等方面发挥重要作用。

## 方法学挑战

1. **高维小样本问题**: 生物数据特征维度高但样本量有限，容易导致过拟合
2. **数据异质性**: 多中心、多批次数据存在显著的批次效应
3. **模型可解释性**: 复杂的深度学习模型缺乏生物学可解释性
4. **验证困难**: 缺乏独立的验证数据集

## 代表性论文

"""

    for i, paper in enumerate(papers[:5], 1):
        literature_report += f"""
### 论文 {i}
- **标题**: {paper['title']}
- **期刊**: {paper.get('journal', 'N/A')}
- **发表时间**: {paper.get('publication_date', 'N/A')}
- **摘要**: {paper.get('abstract', 'N/A')[:300]}...
"""

    print(f"文献报告已生成 ({len(literature_report)} 字符)")
    print()

    # 使用首席科学家智能体生成假设
    chief_scientist = ChiefScientistAgent()

    hypothesis_result = chief_scientist.execute({
        'literature_report': literature_report,
        'papers': papers[:5],
        'research_topic': '机器学习在生物信息学中的应用',
        'output_dir': 'reports'
    })

    if hypothesis_result['success']:
        print(f"[OK] 生成了 {len(hypothesis_result['hypotheses'])} 个In Silico假设")
        print(f"提案文档: {hypothesis_result['proposal_path']}")
        print()
        print("生成的假设:")
        for i, hyp in enumerate(hypothesis_result['hypotheses'], 1):
            print(f"  假设 {i}: {hyp['title']}")
        print()
    else:
        print(f"[ERROR] 假设生成失败: {hypothesis_result.get('error')}")
        return

    # 步骤3: 评审假设
    print("[步骤 3/3] 假设评审 - 评估第一个假设")
    print("-" * 70)

    validator = ValidationAgent()

    # 评审第一个假设
    first_hypothesis = hypothesis_result['hypotheses'][0]

    validation_result = validator.execute({
        'hypothesis_id': None,
        'hypothesis_data': first_hypothesis,
        'source_papers': papers[:3],
        'enable_literature_check': True,
        'output_dir': 'reports'
    })

    if validation_result['success']:
        validation = validation_result['validation']
        print(f"[OK] 评审完成")
        print()
        print("评审结果:")
        print(f"  最终决议: {validation['final_decision']}")
        print(f"  新颖性: {validation['scores']['novelty']}/10")
        print(f"  可行性: {validation['scores']['feasibility']}/10")
        print(f"  科研价值: {validation['scores']['impact']}/10")
        print()
        print(f"决议书: {validation.get('report_path', 'N/A')}")
        print()

        # 显示优势和建议
        if validation.get('strengths'):
            print("优势:")
            for s in validation['strengths'][:2]:
                print(f"  - {s}")
        print()
        if validation.get('suggestions'):
            print("改进建议:")
            for s in validation['suggestions'][:2]:
                print(f"  - {s}")
    else:
        print(f"[ERROR] 评审失败: {validation_result.get('error')}")

    print()
    print("=" * 70)
    print("测试完成!")
    print("=" * 70)
    print()
    print("生成的文件:")
    print(f"  1. 假设提案: {hypothesis_result.get('proposal_path', 'N/A')}")
    print(f"  2. 评审决议: {validation_result.get('validation', {}).get('report_path', 'N/A')}")


if __name__ == '__main__':
    test_full_workflow()
