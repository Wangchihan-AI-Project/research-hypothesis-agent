# -*- coding: utf-8 -*-
"""
测试首席科学家智能体
"""
import os
import sys

# 设置环境变量
os.environ['ANTHROPIC_API_KEY'] = 'sk-y3WE6cIOgqbsg7tXs2LNSKXZkeh9E1zfJvdC763KraN3lTDw'
os.environ['ANTHROPIC_BASE_URL'] = 'https://cloud.hongqiye.com'
os.environ['CLAUDE_MODEL'] = 'claude-opus-4-6'
os.environ['DATABASE_URL'] = 'sqlite:///./data/research.db'

sys.path.insert(0, 'src')

from agents.hypothesis_agent import ChiefScientistAgent


def test_basic_analysis():
    """测试基础分析功能（不调用API）"""
    print("=" * 60)
    print("测试1: 领域自适应分析")
    print("=" * 60)

    agent = ChiefScientistAgent()

    # 测试文献报告
    test_report = """
    # 阿尔茨海默病的多组学研究进展

    ## 研究现状

    近年来，阿尔茨海默病(AD)的基因组学研究取得了显著进展。多项全基因组关联研究(GWAS)
    识别了超过40个与AD风险相关的基因座。然而，这些研究主要基于欧洲人群，缺乏多样性。

    转录组学研究显示，AD患者大脑中存在显著的基因表达变化，特别是涉及突触功能和
    免疫反应的通路。单细胞RNA测序揭示了小胶质细胞和星形胶质细胞的特定亚型在AD中
    的作用。

    蛋白质组学分析发现了淀粉样蛋白和tau蛋白的修饰变化。

    ## 方法学挑战

    1. 样本量限制：多数研究样本量不足，影响统计功效
    2. 批次效应：多中心数据整合存在显著批次效应
    3. 多组学整合：缺乏有效的基因组、转录组和蛋白质组数据联合分析框架
    4. 过拟合风险：机器学习模型在小样本上容易过拟合

    ## 数据来源

    - ROSMAP队列：纵向临床数据和脑组织转录组
    - AMP-AD共识：多中心蛋白质组学数据
    - 单细胞atlas：人类脑细胞单核RNA测序数据
    """

    test_papers = [
        {
            'pmid': '12345678',
            'title': 'Multi-omics analysis of Alzheimer disease reveals novel pathways',
            'abstract': 'This study integrates genomics, transcriptomics, and proteomics data from brain tissue. Single-cell RNA sequencing reveals microglia subtypes. Machine learning classification shows 85% accuracy.',
            'journal': 'Nature Neuroscience',
            'publication_date': '2024-01-15'
        },
        {
            'pmid': '87654321',
            'title': 'Deep learning for protein structure prediction in neurodegenerative diseases',
            'abstract': 'We apply neural networks to predict protein folding patterns. Cross-validation shows robust performance.',
            'journal': 'Cell',
            'publication_date': '2024-02-20'
        }
    ]

    # 测试领域分析
    domain_analysis = agent._analyze_domains(test_report, test_papers)

    print(f"检测到的领域: {domain_analysis['detected_domains']}")
    print(f"领域得分: {domain_analysis['domain_scores']}")
    print(f"主要数据类型: {domain_analysis['primary_data_types']}")
    print(f"分析方法: {domain_analysis['analysis_methods']}")
    print(f"摘要: {domain_analysis['summary']}")
    print()

    # 测试Gap分析
    print("=" * 60)
    print("测试2: 计算/统计Gap分析")
    print("=" * 60)

    gap_analysis = agent._detect_computational_gaps(test_report, test_papers)

    print(f"检测到的问题: {gap_analysis['detected_gaps']}")
    print(f"问题详情:")
    for gap, details in gap_analysis['gap_details'].items():
        print(f"  - {gap}: 关键词={details['keywords_found']}, 频次={details['frequency']}")
    print(f"改进建议: {gap_analysis['recommendations']}")
    print(f"摘要: {gap_analysis['summary']}")
    print()

    # 测试假设分类
    print("=" * 60)
    print("测试3: 假设分类与评估")
    print("=" * 60)

    sample_hyp = {
        'title': '基于图神经网络的蛋白质-药物相互作用预测',
        'description': '提出双通道GNN架构，结合分子图和蛋白质网络特征',
        'rationale': '现有方法忽略网络拓扑信息，GNN能捕获结构特征',
        'validation_plan': '使用DrugBank数据，5折交叉验证',
        'required_techniques': ['Python', 'PyTorch', 'NetworkX'],
        'novelty': '首次联合建模分子图和蛋白质网络',
        'expected_value': '提升药物重定位效率'
    }

    paradigm = agent._classify_hypothesis_paradigm(sample_hyp)
    data_reqs = agent._infer_data_requirements(sample_hyp, domain_analysis)
    complexity = agent._assess_computational_complexity(sample_hyp)
    techniques = agent._extract_required_techniques(sample_hyp)

    print(f"计算范式: {paradigm}")
    print(f"数据需求: {data_reqs}")
    print(f"计算复杂度: {complexity}")
    print(f"所需技术: {techniques}")
    print()

    return True


def test_full_execution():
    """测试完整执行（调用API）"""
    print("=" * 60)
    print("测试4: 完整执行（调用Claude API）")
    print("=" * 60)
    print("注意：此测试将调用Claude API，需要有效的API密钥")
    print()

    agent = ChiefScientistAgent()

    test_report = """
    # 阿尔茨海默病的多组学研究进展

    GWAS识别了40个AD风险基因座。单细胞RNA测序揭示小胶质细胞亚型。
    蛋白质组学发现淀粉样蛋白通路。存在样本量不足、批次效应、多组学整合困难等问题。
    """

    test_papers = [
        {
            'pmid': '12345678',
            'title': 'Multi-omics analysis of Alzheimer disease',
            'abstract': 'Integration of genomics, transcriptomics, and proteomics in Alzheimer disease.',
            'journal': 'Nature Neuroscience',
            'publication_date': '2024-01-15'
        }
    ]

    try:
        result = agent.execute({
            'literature_report': test_report,
            'papers': test_papers,
            'research_topic': '阿尔茨海默病的多组学机制研究',
            'output_dir': 'reports'
        })

        if result['success']:
            print(f"[OK] 生成了 {len(result['hypotheses'])} 个In Silico假设")
            print(f"[OK] 提案文档: {result['proposal_path']}")
            print()
            print("假设摘要:")
            for i, hyp in enumerate(result['hypotheses'], 1):
                print(f"  {i}. {hyp['title']}")
            return result
        else:
            print(f"[ERROR] {result.get('error')}")
            return None

    except Exception as e:
        print(f"[ERROR] 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true', help='运行完整API测试')
    args = parser.parse_args()

    # 测试1-3: 基础功能（不需要API）
    test_basic_analysis()

    # 测试4: 完整执行（需要API）
    if args.full:
        test_full_execution()
    else:
        print("\n跳过API测试。使用 --full 参数运行完整测试。")
