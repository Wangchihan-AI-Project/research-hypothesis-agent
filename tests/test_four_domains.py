# -*- coding: utf-8 -*-
"""
测试四大核心领域聚焦系统
"""
import os
import sys

# 设置环境变量
os.environ['ANTHROPIC_API_KEY'] = 'sk-y3WE6cIOgqbsg7tXs2LNSKXZkeh9E1zfJvdC763KraN3lTDw'
os.environ['ANTHROPIC_BASE_URL'] = 'https://cloud.hongqiye.com'
os.environ['CLAUDE_MODEL'] = 'claude-opus-4-6'
os.environ['PUBMED_EMAIL'] = 'wanghan3698@gmail.com'
os.environ['PUBMED_API_KEY'] = '2ee2706d111ff8ff5ccce94a25d883fb5709'

# 获取脚本所在目录并添加src到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(script_dir, 'src')
sys.path.insert(0, src_path)

from utils.pubmed import PubMedSearcher
from agents.hypothesis_agent import ChiefScientistAgent
from agents.validation_agent import ValidationAgent


def test_biomedical_informatics():
    """测试生物医学信息学领域 - EHR败血症预测"""
    print("=" * 70)
    print("测试领域 1/4: Biomedical Informatics (生物医学信息学)")
    print("研究主题: 基于EHR的败血症早期预警模型")
    print("=" * 70)
    print()

    searcher = PubMedSearcher(
        email=os.getenv('PUBMED_EMAIL'),
        api_key=os.getenv('PUBMED_API_KEY')
    )

    query = "sepsis prediction electronic health record machine learning"
    print(f"搜索关键词: {query}")
    print()

    papers = searcher.search_papers(query, max_results=8)
    print(f"找到 {len(papers)} 篇论文")

    if not papers:
        print("[ERROR] 未找到论文")
        return None

    # 构建文献报告
    literature_report = f"""
# EHR败血症早期预测研究现状

## 主要发现
通过对{len(papers)}篇相关论文的分析：

1. **方法过时**: 多数研究使用logistic regression或随���森林，未利用现代深度学习方法
2. **静态建模**: 忽略患者状态的时序演化特征
3. **统计问题**: 部分研究样本量不足，缺乏功效分析
4. **数据泄露**: 特征选择可能包含未来信息

## 代表性论文摘要
"""
    for p in papers[:3]:
        literature_report += f"\n- {p['title']}\n  {p.get('abstract', 'N/A')[:200]}...\n"

    # 首席科学家生成假设
    chief = ChiefScientistAgent()
    result = chief.execute({
        'literature_report': literature_report,
        'papers': papers[:5],
        'research_topic': '基于EHR的败血症早期预警模型优化',
        'output_dir': 'reports'
    })

    if result['success']:
        print(f"[OK] 生成了 {len(result['hypotheses'])} 个假设")
        for i, hyp in enumerate(result['hypotheses'], 1):
            print(f"  假设 {i}: {hyp['title']}")
        print(f"\n提案: {result['proposal_path']}")
        return result['hypotheses'][0]
    return None


def test_computational_biology():
    """测试计算生物学领域 - 单细胞聚类"""
    print("\n" + "=" * 70)
    print("测试领域 2/4: Computational Biology (计算生物学)")
    print("研究主题: 单细胞RNA测序聚类算法优化")
    print("=" * 70)
    print()

    searcher = PubMedSearcher()
    query = "single-cell rna clustering algorithm"
    papers = searcher.search_papers(query, max_results=8)

    print(f"找到 {len(papers)} 篇论文")

    literature_report = f"""
# 单细胞RNA测序聚类方法研究现状

## 主要发现
1. 现有聚类方法在高维数据中效果有限
2. 批次效应影响聚类质量
3. 缺乏考虑细胞发育轨迹的聚类方法
"""

    chief = ChiefScientistAgent()
    result = chief.execute({
        'literature_report': literature_report,
        'papers': papers[:5],
        'research_topic': '单细胞RNA测序聚类算法优化',
        'output_dir': 'reports'
    })

    if result['success']:
        print(f"[OK] 生成了 {len(result['hypotheses'])} 个假设")
        return result['hypotheses'][0]
    return None


def test_validation():
    """测试评审智能体"""
    print("\n" + "=" * 70)
    print("测试评审智能体: Bioinformatics/Lancet Digital Health级别")
    print("=" * 70)
    print()

    # 测试假设
    test_hypothesis = {
        'title': '基于图神经网络的EHR时态建模用于败血症早期预测',
        'description': '提出Temporal Graph Attention Network框架，将患者就诊历史构建为动态图，节点为患者，边为临床相似性。引入医疗事件编码器捕捉诊断、用药、检验的时序依赖。',
        'rationale': '现有EHR预测多使用静态特征或简单RNN，忽略了患者状态演化中的复杂医疗干预关系。GNN能同时建模患者相似性网络和时间依赖模式。',
        'novelty': '首次将动态患者网络建模与医疗事件时序编码结合；引入对抗学习增强模型对败血症早期微小信号的敏感性',
        'expected_value': '可提前6-24小时预测败血症，为临床干预争取宝贵时间，降低ICU死亡率',
        'validation_plan': '使用MIMIC-IV数据集，按时间分割训练/测试集。与LSTM、XGBoost、logistic regression对比AUC-ROC、AUPRC。提前预测窗口：败血症发作前6/12/24小时。',
        'required_techniques': ['Python', 'PyTorch Geometric', 'scikit-learn']
    }

    validator = ValidationAgent()
    result = validator.execute({
        'hypothesis_id': None,
        'hypothesis_data': test_hypothesis,
        'source_papers': [],
        'enable_literature_check': True,
        'output_dir': 'reports'
    })

    if result['success']:
        validation = result['validation']
        print("[OK] 评审完成")
        print()
        print("评审结果:")
        print(f"  最终决议: {validation['final_decision']}")
        print(f"  算法创新与统计严谨性: {validation['scores']['novelty']}/10")
        print(f"  数据获取性: {validation['scores']['feasibility']}/10")
        print(f"  科研价值: {validation['scores']['impact']}/10")
        print(f"\n决议书: {validation.get('report_path', 'N/A')}")
        print("\n优势:")
        for s in validation.get('strengths', [])[:2]:
            print(f"  - {s}")
    return result


def main():
    """主测试函数"""
    print()
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*  生物医学计算与统计自动化科研引擎 - 四大核心领域测试  *")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print()
    print("四大核心领域:")
    print("  1. Biomedical Informatics (生物医学信息学)")
    print("  2. Computational Biology (计算生物学)")
    print("  3. Health Data Science (健康数据科学)")
    print("  4. Biostatistics (生物统计学)")
    print()

    # 测试1: 生物医学信息学
    hyp1 = test_biomedical_informatics()

    # 测试2: 计算生物学
    hyp2 = test_computational_biology()

    # 测试3: 评审
    test_validation()

    print()
    print("=" * 70)
    print("测试完成!")
    print("=" * 70)
    print()
    print("系统已聚焦于四大核心领域，")
    print("专门针对计算生物与健康数据科学的方法论创新。")


if __name__ == '__main__':
    main()
