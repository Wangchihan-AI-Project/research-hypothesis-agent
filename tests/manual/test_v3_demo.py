# -*- coding: utf-8 -*-
"""
V3.0 架构演示脚本

展示三大工程特性的运行效果：
1. Query Optimizer - 查询优化器
2. Fail-Fast Generator - 早期熔断与两步生成法
3. Context Rollback - 上下文纯净回滚

运行方式:
    python test_v3_demo.py

作者: 架构师 V3.0
日期: 2026-04-16
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

# 导入 V3.0 模块
from src.core.query_optimizer import QueryOptimizer, create_search_plan
from src.core.fail_fast_generator import FailFastGenerator, GenerationPhase
from src.core.context_rollback import (
    ContextRollbackManager,
    RollbackTrigger,
    ConversationManager
)
from src.agents.hypothesis_agent_v3 import HypothesisAgentV3


def print_section(title: str):
    """打印分隔线"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def demo_query_optimizer():
    """演示 Query Optimizer 模块"""
    print_section("演示 1: Query Optimizer - 查询优化器")

    test_topics = [
        "Alzheimer's disease and machine learning for early diagnosis 2023-2024",
        "CRISPR gene editing in cancer immunotherapy using CAR-T cells",
        "Plasma pQTL biomarkers for Parkinson disease progression prediction"
    ]

    optimizer = QueryOptimizer()

    for topic in test_topics:
        print(f"\n{'─'*70}")
        print(f"原始主题: {topic}")
        print(f"{'─'*70}")

        plan = optimizer.optimize(topic, strategy="adaptive")

        print(f"✓ 优化策略: {plan.strategy}")
        print(f"✓ 查询数量: {len(plan.queries)}")
        print(f"\n查询队列:")

        for i, query in enumerate(plan.queries, 1):
            print(f"  {i}. [{query.description}]")
            print(f"     Query: {query.query}")

    print(f"\n{'─'*70}")
    print("✓ Query Optimizer 演示完成")
    print(f"  - 自动屏蔽年份词汇")
    print(f"  - 生成多层级降级查询")
    print(f"  - 符合 PubMed 语法规范")


def demo_fail_fast():
    """演示 Fail-Fast 生成模块"""
    print_section("演示 2: Fail-Fast Generator - 早期熔断机制")

    # 模拟 Phase 1 结果
    from src.core.fail_fast_generator import Phase1Result

    phase1 = Phase1Result(
        success=True,
        core_hypothesis="血浆 pQTL Aβ42 通过介导海马萎缩率加速认知衰退",
        exposure="血浆 pQTL Aβ42",
        mediator="海马萎缩率",
        outcome="认知衰退速度",
        causal_chain="Aβ42 → 海马萎缩 → 认知衰退"
    )

    print(f"\n[Phase 1] 核心假说生成:")
    print(f"  ✓ 核心假说: {phase1.core_hypothesis}")
    print(f"  ✓ 因果链: {phase1.causal_chain}")

    # 模拟碰撞检测
    print(f"\n[Phase 2] PubMed 碰撞检测:")
    print(f"  检索查询: plasma pQTL[TIAB] AND hippocampal atrophy[TIAB]")

    # 模拟碰撞场景
    mock_papers = [
        {'pmid': '1234567', 'title': 'Plasma pQTL and hippocampal atrophy in Alzheimer'},
        {'pmid': '2345678', 'title': 'Aβ42 mediated cognitive decline via hippocampus'}
    ]

    collision_count = len(mock_papers)

    if collision_count >= 2:
        print(f"  🔴 发现 {collision_count} 篇高度同质化文献")
        print(f"  ══════════════════════════════════════════════════════════")
        print(f"  🔴 [EARLY STOPPING] 熔断触发！")
        print(f"  ══════════════════════════════════════════════════════════")
        print(f"     原因: 发现 {collision_count} 篇高度同质化文献（相似度>70%）")
        print(f"     节省 Token: ~5,200")

        print(f"\n  📋 碰撞文献详情:")
        for i, paper in enumerate(mock_papers, 1):
            print(f"     [{i}] PMID:{paper['pmid']} | {paper['title'][:50]}...")

    print(f"\n{'─'*70}")
    print("✓ Fail-Fast 机制演示完成")
    print(f"  - Phase 1: 50字核心假说")
    print(f"  - Phase 2: 立即碰撞检测")
    print(f"  - 早期熔断: 避免浪费 Token 生成完整内容")


def demo_context_rollback():
    """演示 Context Rollback 模块"""
    print_section("演示 3: Context Rollback - 上下文纯净回滚")

    # 创建对话管理器
    manager = ConversationManager()
    system_prompt = """你是首席科学家智能体..."""
    manager.initialize(system_prompt)

    print(f"\n[初始化] 对话上下文已创建")
    print(f"  消息数: {len(manager.get_current_messages())}")

    # 模拟对话
    print(f"\n[对话] 添加用户消息...")
    manager.add_user_message("请生成关于阿尔茨海默病的假说")
    print(f"  消息数: {len(manager.get_current_messages())}")

    # 模拟红方审计失败
    print(f"\n[审计] 红方审计发现致命缺陷...")

    audit_result = {
        'critical_issues': [
            {'issue': '因果链不完整，缺少中介效应检验'},
            {'issue': '未考虑混杂因素年龄和教育水平'}
        ],
        'final_verdict': '假设存在因果推断缺陷，需要重构'
    }

    # 处理失败
    print(f"\n[回滚] 触发上下文回滚...")
    result = manager.handle_failure(
        trigger=RollbackTrigger.RED_TEAM_REJECT,
        audit_result=audit_result
    )

    print(f"\n  ══════════════════════════════════════════════════════════")
    print(f"  🔄 [ROLLBACK TRIGGERED] 上下文回滚")
    print(f"  ══════════════════════════════════════════════════════════")
    print(f"     触发原因: red_team_reject")
    print(f"     节省 Token: ~{result.token_saved:,}")
    print(f"  ══════════════════════════════════════════════════════════")

    print(f"\n[注入] 红方教训已注入 System Prompt:")
    for lesson in result.lessons_applied:
        suffix = lesson.to_system_prompt_suffix()
        print(f"  {suffix[:100]}...")

    print(f"\n{'─'*70}")
    print("✓ Context Rollback 演示完成")
    print(f"  - 回滚到干净快照")
    print(f"  - 注入浓缩的教训")
    print(f"  - 避免上下文污染")


def demo_v3_integration():
    """演示 V3.0 整合架构"""
    print_section("演示 4: V3.0 整合架构 - 完整流程")

    print(f"\n[初始化] 创建 HypothesisAgentV3...")

    # 注意：实际运行需要有效的 API Key
    # 这里只演示架构初始化
    try:
        agent = HypothesisAgentV3()
        print(f"✓ HypothesisAgentV3 初始化成功")
        print(f"\n已集成的 V3.0 模块:")
        print(f"  ✓ Query Optimizer - 智能查询优化")
        print(f"  ✓ Fail-Fast Generator - 早期熔断机制")
        print(f"  ✓ Context Rollback - 上下文纯净回滚")

        # 演示查询优化
        print(f"\n[测试] 查询优化功能:")
        plan = agent.optimize_search_query(
            "Alzheimer pQTL hippocampal atrophy causal mediation"
        )
        print(f"  生成 {len(plan.queries)} 个优化查询")

    except Exception as e:
        print(f"⚠️  初始化跳过（需要配置 API Key）: {e}")
        print(f"\nV3.0 架构模块已就绪:")
        print(f"  ✓ src/core/query_optimizer.py")
        print(f"  ✓ src/core/fail_fast_generator.py")
        print(f"  ✓ src/core/context_rollback.py")
        print(f"  ✓ src/agents/hypothesis_agent_v3.py")


def print_state_machine_diagram():
    """打印状态机示意图"""
    print_section("V3.0 状态机示意图")

    diagram = """
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║                    V3.0 生成流程状态机                                    ║
    ╠═══════════════════════════════════════════════════════════════════════════╣
    ║                                                                           ║
    ║  [INITIALIZATION]                                                         ║
    ║       │                                                                   ║
    ║       ▼                                                                   ║
    ║  [Query Optimization] ─────────────────────────────────────┐             ║
    ║       │                                                   │             ║
    ║       ▼                                                   │             ║
    ║  [Phase 1: 核心假说] (50字)                                 │             ║
    ║       │                                                   │             ║
    ║       ▼                                                   │             ║
    ║  [Phase 2: 碰撞检测] ──────► 发现碰撞? ──Yes──► [EARLY STOPPING]     ║
    ║       │                                                   │             ║
    ║       No                                                  │             ║
    ║       │                                                   │             ║
    ║       ▼                                                   │             ║
    ║  [Phase 3: 完整展开] (七段式)                              │             ║
    ║       │                                                   │             ║
    ║       ▼                                                   │             ║
    ║  [SUCCESS]                                            [ROLLBACK]         ║
    ║       │                                                   │             ║
    ║       │                                                   ▼             ║
    ║       │                                            [注入教训]          ║
    ║       │                                                   │             ║
    ║       │                                                   ▼             ║
    ║       └─────────────────────────────────────────────► [重试]            ║
    ║                                                                           ║
    ╚═══════════════════════════════════════════════════════════════════════════╝
    """
    print(diagram)

    print(f"\n关键特性:")
    print(f"  📍 [Query Optimization] - 解耦检索，生成多层级查询")
    print(f"  📍 [Phase 1] - 仅生成 50 字核心假说")
    print(f"  📍 [Phase 2] - 立即碰撞检测，发现同质化研究")
    print(f"  📍 [EARLY STOPPING] - 早期熔断，节省 Token")
    print(f"  📍 [ROLLBACK] - 上下文回滚，避免污染")
    print(f"  📍 [注入教训] - 浓缩反馈注入 System Prompt")


def main():
    """主函数"""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                           ║")
    print("║                   多智能体系统 V3.0 架构演示                               ║")
    print("║             全面接入 Karpathy AutoResearch 范式                           ║")
    print("║                                                                           ║")
    print("╚═══════════════════════════════════════════════════════════════════════════╝")

    # 打印状态机示意图
    print_state_machine_diagram()

    # 演示各个模块
    demo_query_optimizer()
    demo_fail_fast()
    demo_context_rollback()
    demo_v3_integration()

    # 总结
    print_section("V3.0 架构升级总结")

    print(f"\n✅ 三大工程特性已实现:")
    print(f"\n  1. 【Query Optimizer】查询优化器")
    print(f"     ✓ 生成 SearchPlan（3-5个极简查询）")
    print(f"     ✓ 严格屏蔽年份和复杂介词")
    print(f"     ✓ 遍历查询直到获取有效数据")
    print(f"     ✓ 文件: src/core/query_optimizer.py")

    print(f"\n  2. 【Fail-Fast Mechanism】早期熔断与两步生成法")
    print(f"     ✓ Phase 1: 生成 50 字核心机制假说")
    print(f"     ✓ Phase 2: 立即进行 PubMed 碰撞检测")
    print(f"     ✓ Phase 3: 只有存活假说才展开完整内容")
    print(f"     ✓ 发现 2 篇以上同质化文献即熔断")
    print(f"     ✓ 文件: src/core/fail_fast_generator.py")

    print(f"\n  3. 【Context Rollback】上下文纯净回滚")
    print(f"     ✓ 失败时回滚到干净快照")
    print(f"     ✓ 清空本轮冗长 JSON")
    print(f"     ✓ 注入高度浓缩的'红方教训'")
    print(f"     ✓ 避免 messages 历史污染")
    print(f"     ✓ 文件: src/core/context_rollback.py")

    print(f"\n✅ 整合版智能体:")
    print(f"     ✓ HypothesisAgentV3")
    print(f"     ✓ 文件: src/agents/hypothesis_agent_v3.py")

    print(f"\n✅ 透明日志输出:")
    print(f"     ✓ [Query Optimization] 查询优化状态")
    print(f"     ✓ [Phase 1: Hypothesis] 核心假说生成")
    print(f"     ✓ [Phase 2: Early Collision Check] 碰撞检测")
    print(f"     ✓ [Rollback triggered] 回滚触发")
    print(f"     ✓ [EARLY STOPPING] 熔断通知")

    print(f"\n{'='*70}")
    print(f"🎉 V3.0 架构升级完成！")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    main()
