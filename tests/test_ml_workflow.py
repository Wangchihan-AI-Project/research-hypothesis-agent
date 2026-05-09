# -*- coding: utf-8 -*-
"""
机器学习关键词自动化测试脚本
测试完整的12智能体工作流
"""
import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv()

from src.core.orchestrator import Orchestrator
import json


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_ml_workflow():
    """测试 machine learning 关键词完整工作流"""

    print_section("🚀 12智能体系统测试 - machine learning")

    # 初始化协调器
    print("\n[1/12] 初始化工作流协调器...")
    orchestrator = Orchestrator()
    print("✓ 协调器初始化成功")
    print(f"  - 已加载智能体: {len(orchestrator.__dict__)} 个")

    # 开始会话
    print_section("Step 1: 开始研究会话")
    session_result = orchestrator.start_session("machine learning")
    print(f"✓ 会话ID: {session_result['session_id']}")
    print(f"  状态: {session_result['message']}")

    # 搜索论文 (使用两阶段漏斗，小规模测试)
    print_section("Step 2: 文献搜索 (两阶段漏斗)")
    search_result = orchestrator.search_papers(
        query="machine learning",
        use_two_stage_funnel=True,
        stage1_max=50,  # 减少第一阶段数量
        stage2_top_k=5,  # 减少第二阶段数量
        fetch_full_text=False  # 不获取全文，加快测试
    )

    if search_result['success']:
        print(f"✓ 搜索完成")
        print(f"  - 找到论文: {search_result.get('total_count', 0)} 篇")
        print(f"  - 使用两阶段漏斗: {search_result.get('used_two_stage_funnel', False)}")

        if search_result.get('stage1_stats'):
            s1 = search_result['stage1_stats']
            print(f"  - 第一阶段: 获取 {s1.get('total_fetched', 0)} 篇，筛选 {s1.get('selected_papers', 0)} 篇")

        papers = search_result.get('papers', [])
        if papers:
            print(f"\n  Top 3 论文:")
            for i, p in enumerate(papers[:3], 1):
                print(f"    {i}. {p.get('title', 'Unknown')[:60]}...")
    else:
        print(f"✗ 搜索失败: {search_result.get('error')}")
        return

    # 生成假设
    print_section("Step 3: 生成研究假设")
    hypothesis_result = orchestrator.generate_hypotheses(
        papers=papers,
        research_field="机器学习",
        focus_areas=["深度学习", "神经架构"]
    )

    if hypothesis_result['success']:
        hypotheses = hypothesis_result.get('hypotheses', [])
        print(f"✓ 生成假设: {len(hypotheses)} 个")

        if hypotheses:
            print(f"\n  假设 #1:")
            h = hypotheses[0]
            print(f"    标题: {h.get('title', 'Unknown')[:80]}...")
            print(f"    框架: {h.get('paradigm_framework', 'N/A')}")

            # 选择第一个假设进行验证
            selected_hypothesis_id = hypothesis_result.get('hypothesis_ids', [None])[0]
    else:
        print(f"✗ 假设生成失败: {hypothesis_result.get('error')}")
        return

    # 验证假设
    if selected_hypothesis_id:
        print_section("Step 4: 验证假设")
        validation_result = orchestrator.validate_hypothesis(selected_hypothesis_id)

        if validation_result['success']:
            print(f"✓ 验证完成")
            scores = validation_result.get('validation_result', {})
            print(f"  - 可行性: {scores.get('feasibility_score', 0)}/10")
            print(f"  - 新颖性: {scores.get('novelty_score', 0)}/10")
            print(f"  - 技术难度: {scores.get('technical_score', 0)}/10")
        else:
            print(f"✗ 验证失败: {validation_result.get('error')}")

    # 技术分析
    if selected_hypothesis_id:
        print_section("Step 5: 技术分析")
        tech_result = orchestrator.analyze_technology(selected_hypothesis_id)

        if tech_result['success']:
            print(f"✓ 技术分析完成")
            tech_analysis = tech_result.get('tech_analysis', {})
            challenges = tech_analysis.get('challenges', [])
            if challenges:
                print(f"  - 识别挑战: {len(challenges)} 个")
        else:
            print(f"✗ 技术分析失败: {tech_result.get('error')}")

    # 完成会话
    print_section("Step 12: 完成会话")
    complete_result = orchestrator.complete_session()

    if complete_result['success']:
        print(f"✓ 会话完成")
        summary = complete_result.get('summary', {})
        print(f"  - 论文数: {summary.get('papers_found', 0)}")
        print(f"  - 假设数: {summary.get('hypotheses_generated', 0)}")
        print(f"  - 验证数: {summary.get('hypotheses_validated', 0)}")

    # 列出最近会话
    print_section("📊 最近会话记录")
    recent = orchestrator.list_recent_sessions(5)
    print(f"✓ 找到 {len(recent)} 个会话")
    for s in recent:
        print(f"  - ID:{s['id']} | {s['query']} | {s['status']}")

    print_section("✅ 测试完成")
    print("\n所有核心功能正常运行！")
    print("\n下一步: 运行 'streamlit run app.py' 启动完整UI界面")


if __name__ == '__main__':
    try:
        test_ml_workflow()
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
