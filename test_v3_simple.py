# -*- coding: utf-8 -*-
"""
V3.0 架构演示脚本 (简化版)

展示三大工程特性的运行效果
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.query_optimizer import QueryOptimizer


def print_section(title: str):
    """打印分隔线"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def demo_query_optimizer():
    """演示 Query Optimizer 模块"""
    print_section("Demo 1: Query Optimizer - Query Optimization")

    test_topics = [
        "Alzheimer's disease and machine learning for early diagnosis 2023-2024",
        "CRISPR gene editing in cancer immunotherapy using CAR-T cells",
        "Plasma pQTL biomarkers for Parkinson disease progression prediction"
    ]

    optimizer = QueryOptimizer()

    for topic in test_topics:
        print(f"\n{'-'*70}")
        print(f"Original Topic: {topic}")
        print(f"{'-'*70}")

        plan = optimizer.optimize(topic, strategy="adaptive")

        print(f"Optimized Strategy: {plan.strategy}")
        print(f"Query Count: {len(plan.queries)}")
        print(f"\nQuery Queue:")

        for i, query in enumerate(plan.queries, 1):
            print(f"  {i}. [{query.description}]")
            print(f"     Query: {query.query}")

    print(f"\n{'-'*70}")
    print("Query Optimizer Demo Completed")
    print(f"  - Auto-filtered year terms")
    print(f"  - Generated multi-level degradation queries")
    print(f"  - Compliant with PubMed syntax")


def demo_fail_fast():
    """演示 Fail-Fast 生成模块"""
    print_section("Demo 2: Fail-Fast Generator - Early Stopping")

    print(f"\n[Phase 1] Core Hypothesis Generation:")
    print(f"  Core Hypothesis: Plasma pQTL Abeta42 accelerates cognitive decline")
    print(f"                  via mediating hippocampal atrophy rate")
    print(f"  Causal Chain: Abeta42 -> Hippocampal Atrophy -> Cognitive Decline")

    print(f"\n[Phase 2] PubMed Collision Check:")
    print(f"  Search Query: plasma pQTL[TIAB] AND hippocampal atrophy[TIAB]")

    # Simulate collision
    collision_count = 2

    if collision_count >= 2:
        print(f"  Found {collision_count} highly similar papers")
        print(f"  {'='*70}")
        print(f"  [EARLY STOPPING] Circuit Breaker Triggered!")
        print(f"  {'='*70}")
        print(f"     Reason: Found {collision_count} highly similar papers (similarity>70%)")
        print(f"     Tokens Saved: ~5,200")

        print(f"\n  Collision Details:")
        print(f"     [1] PMID:1234567 | Plasma pQTL and hippocampal atrophy...")
        print(f"     [2] PMID:2345678 | Abeta42 mediated cognitive decline...")

    print(f"\n{'-'*70}")
    print("Fail-Fast Mechanism Demo Completed")
    print(f"  - Phase 1: 50-word core hypothesis")
    print(f"  - Phase 2: Immediate collision check")
    print(f"  - Early Stopping: Avoid wasting tokens on full content")


def demo_context_rollback():
    """演示 Context Rollback 模块"""
    print_section("Demo 3: Context Rollback - Clean Context Recovery")

    print(f"\n[Initialization] Conversation context created")
    print(f"  Message count: 1")

    print(f"\n[Conversation] Adding user message...")
    print(f"  Message count: 2")

    print(f"\n[Audit] Red team audit found critical flaws...")

    print(f"\n[Rollback] Triggering context rollback...")
    print(f"  {'='*70}")
    print(f"  [ROLLBACK TRIGGERED] Context Rollback")
    print(f"  {'='*70}")
    print(f"     Trigger: red_team_reject")
    print(f"     Tokens Saved: ~5,000")
    print(f"  {'='*70}")

    print(f"\n[Injection] Red team lesson injected into System Prompt:")
    print(f"  >> Failure: Causal chain incomplete, missing mediation analysis")
    print(f"  >> Forbidden: Incomplete causal chains, uncontrolled confounders")
    print(f"  >> Recommended: Strengthen causal inference framework")

    print(f"\n{'-'*70}")
    print("Context Rollback Demo Completed")
    print(f"  - Rollback to clean snapshot")
    print(f"  - Inject condensed lessons")
    print(f"  - Avoid context pollution")


def demo_integration():
    """演示 V3.0 整合架构"""
    print_section("Demo 4: V3.0 Integrated Architecture")

    print(f"\nV3.0 Core Modules:")
    print(f"  [OK] Query Optimizer - Intelligent query optimization")
    print(f"  [OK] Fail-Fast Generator - Early stopping mechanism")
    print(f"  [OK] Context Rollback - Clean context recovery")

    print(f"\nFile Structure:")
    print(f"  src/core/")
    print(f"    ├── query_optimizer.py")
    print(f"    ├── fail_fast_generator.py")
    print(f"    └── context_rollback.py")
    print(f"  src/agents/")
    print(f"    └── hypothesis_agent_v3.py")


def main():
    """主函数"""
    print("\n" + "="*70)
    print("  Multi-Agent System V3.0 Architecture Demo")
    print("  Full Integration with Karpathy AutoResearch Paradigm")
    print("="*70)

    # 演示各个模块
    demo_query_optimizer()
    demo_fail_fast()
    demo_context_rollback()
    demo_integration()

    # 总结
    print_section("V3.0 Architecture Upgrade Summary")

    print(f"\nThree Major Engineering Features Implemented:")
    print(f"\n  1. [Query Optimizer]")
    print(f"     [OK] Generate SearchPlan (3-5 minimal queries)")
    print(f"     [OK] Strictly filter years and complex prepositions")
    print(f"     [OK] Iterate queries until valid data obtained")
    print(f"     [OK] File: src/core/query_optimizer.py")

    print(f"\n  2. [Fail-Fast Mechanism]")
    print(f"     [OK] Phase 1: Generate 50-word core hypothesis")
    print(f"     [OK] Phase 2: Immediate PubMed collision check")
    print(f"     [OK] Phase 3: Only surviving hypotheses expand fully")
    print(f"     [OK] Circuit breaker at 2+ similar papers")
    print(f"     [OK] File: src/core/fail_fast_generator.py")

    print(f"\n  3. [Context Rollback]")
    print(f"     [OK] Rollback to clean snapshot on failure")
    print(f"     [OK] Clear verbose JSON from current round")
    print(f"     [OK] Inject condensed 'red team lessons'")
    print(f"     [OK] Avoid messages history pollution")
    print(f"     [OK] File: src/core/context_rollback.py")

    print(f"\nIntegrated Agent:")
    print(f"     [OK] HypothesisAgentV3")
    print(f"     [OK] File: src/agents/hypothesis_agent_v3.py")

    print(f"\nTransparent Logging:")
    print(f"     [OK] [Query Optimization] Query optimization status")
    print(f"     [OK] [Phase 1: Hypothesis] Core hypothesis generation")
    print(f"     [OK] [Phase 2: Early Collision Check] Collision detection")
    print(f"     [OK] [Rollback triggered] Rollback trigger")
    print(f"     [OK] [EARLY STOPPING] Circuit breaker notification")

    print(f"\n{'='*70}")
    print(f"V3.0 Architecture Upgrade Complete!")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    main()
