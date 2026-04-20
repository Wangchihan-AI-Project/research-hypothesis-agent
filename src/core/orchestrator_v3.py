# -*- coding: utf-8 -*-
"""
V3.0 协调器扩展模块 (Orchestrator V3.0 Extension)

将三大工程特性整合到现有的工作流协调器中：
1. Query Optimizer - 智能查询优化
2. Fail-Fast Generator - 早期熔断机制
3. Context Rollback - 上下文纯净回滚

使用方式：在现有 orchestrator.py 中导入并混入此模块

作者: 架构师 V3.0
日期: 2026-04-16
"""

from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

# 导入 V3.0 核心模块
from src.core.query_optimizer import QueryOptimizer, SearchPlan, create_search_plan
from src.core.fail_fast_generator import (
    FailFastGenerator,
    FailFastSession,
    GenerationPhase,
    create_fail_fast_generator
)
from src.core.context_rollback import (
    ContextRollbackManager,
    ConversationManager,
    RollbackTrigger,
    create_conversation_manager
)

logger = logging.getLogger(__name__)


class OrchestratorV3Mixin:
    """
    V3.0 功能混入类

    将 V3.0 的三大工程特性以 Mixin 的方式添加到现有 Orchestrator 中
    """

    # ==================== V3.0 初始化 ====================

    def _init_v3_components(self):
        """初始化 V3.0 组件（在 Orchestrator.__init__ 中调用）"""
        print("[V3.0] Initializing Query Optimizer...")
        self.v3_query_optimizer = QueryOptimizer()

        print("[V3.0] Initializing Fail-Fast Generator...")
        # 需要从 self 获取 LLM 客户端和 PubMed 搜索器
        import anthropic
        api_key = getattr(self, 'api_key', None) or self.hypothesis_agent.api_key
        base_url = getattr(self, 'base_url', None)

        if base_url:
            llm_client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        else:
            llm_client = anthropic.Anthropic(api_key=api_key)

        pubmed_searcher = getattr(self.paper_agent, 'searcher', None)

        self.v3_fail_fast_generator = create_fail_fast_generator(
            llm_client=llm_client,
            pubmed_searcher=pubmed_searcher
        )

        print("[V3.0] Initializing Context Rollback Manager...")
        self.v3_context_manager = ConversationManager()
        self.v3_context_manager.initialize(
            "You are a Chief Scientist Agent with V3.0 capabilities..."
        )

        # V3.0 统计
        self.v3_stats = {
            'total_v3_searches': 0,
            'total_early_stoppages': 0,
            'total_rollbacks': 0,
            'total_tokens_saved': 0
        }

        print("[V3.0] All components initialized successfully!")

    # ==================== V3.0 增强的论文搜索 ====================

    def search_papers_v3(
        self,
        query: str,
        max_results: int = 50,
        enable_v3_optimization: bool = True,
        **kwargs
    ) -> Dict:
        """
        V3.0 增强的论文搜索

        使用 Query Optimizer 生成优化的搜索计划，然后遍历查询直到获取有效数据
        """
        self.v3_stats['total_v3_searches'] += 1

        print("\n" + "="*70)
        print("[V3.0] Enhanced Paper Search with Query Optimization")
        print("="*70)

        if not enable_v3_optimization:
            # 回退到传统搜索
            return self.search_papers(query=query, max_results=max_results, **kwargs)

        # ========== 使用 Query Optimizer ==========
        print(f"\n[Query Optimization] Original query: {query[:60]}...")

        search_plan = self.v3_query_optimizer.optimize(
            research_topic=query,
            strategy='adaptive'
        )

        print(f"[Query Optimization] Generated {len(search_plan.queries)} optimized queries")

        # ========== 遍历查询计划 ==========
        all_papers = []
        current_query_idx = 0

        while search_plan.has_remaining() and len(all_papers) < max_results:
            search_query = search_plan.get_next_query()
            current_query_idx += 1

            print(f"\n[Query {current_query_idx}] Trying: {search_query.description}")
            print(f"  Query: {search_query.query}")

            # 调用原始搜索方法
            result = self.paper_agent.execute({
                'query': search_query.query,
                'max_results': max_results - len(all_papers),
                'date_range': kwargs.get('date_range'),
                'min_if': kwargs.get('min_if', 0)
            })

            if result.get('success') and result.get('papers'):
                papers = result['papers']
                print(f"  [SUCCESS] Found {len(papers)} papers")
                all_papers.extend(papers)

                # 记录搜索结果
                self.v3_query_optimizer.record_search_result(
                    query=search_query,
                    result_count=len(papers),
                    success=True
                )
            else:
                print(f"  [FAILED] No results, trying next query...")
                self.v3_query_optimizer.record_search_result(
                    query=search_query,
                    result_count=0,
                    success=False
                )

        # ========== 返回结果 ==========
        print(f"\n[V3.0] Search completed: {len(all_papers)} papers total")

        # 更新当前论文
        self.current_papers = all_papers

        return {
            'success': len(all_papers) > 0,
            'papers': all_papers,
            'total_count': len(all_papers),
            'queries_tried': current_query_idx,
            'v3_optimization_enabled': True
        }

    # ==================== V3.0 增强的假设生成 ====================

    def generate_hypotheses_v3(
        self,
        research_topic: str,
        papers: List[Dict],
        num_hypotheses: int = 3,
        enable_fail_fast: bool = True,
        enable_context_rollback: bool = True,
        **kwargs
    ) -> Dict:
        """
        V3.0 增强的假设生成

        使用 Fail-Fast 机制和 Context Rollback
        """
        print("\n" + "="*70)
        print("[V3.0] Enhanced Hypothesis Generation with Fail-Fast")
        print("="*70)

        final_hypotheses = []
        total_tokens_saved = 0
        generation_log = []

        for hyp_idx in range(num_hypotheses):
            print(f"\n{'='*70}")
            print(f"[V3.0] Generating Hypothesis {hyp_idx + 1}/{num_hypotheses}")
            print(f"{'='*70}")

            if enable_fail_fast:
                # ========== 使用 Fail-Fast 生成 ==========
                session = self.v3_fail_fast_generator.generate(
                    research_topic=research_topic,
                    literature_context=kwargs.get('literature_report', ''),
                    papers=papers
                )

                log_entry = {
                    'hypothesis_index': hyp_idx + 1,
                    'final_phase': session.final_phase.value,
                    'token_saved': session.token_saved
                }

                # 判断结果
                if session.final_phase == GenerationPhase.PHASE_3_EXPANSION:
                    # 成功生成
                    if session.phase3 and session.phase3.success:
                        final_hypotheses.append(session.phase3.full_hypothesis)
                        log_entry['status'] = 'success'
                        print(f"[V3.0] Hypothesis {hyp_idx + 1} generated successfully")
                else:
                    # 早期终止
                    self.v3_stats['total_early_stoppages'] += 1
                    log_entry['status'] = 'early_stopped'
                    log_entry['termination_reason'] = session.terminated_reason

                    print(f"[V3.0] Hypothesis {hyp_idx + 1} early stopped: {session.terminated_reason}")

                    # 如果启用了 Context Rollback，处理回滚
                    if enable_context_rollback:
                        self._handle_v3_rollback(session, research_topic)

                total_tokens_saved += session.token_saved
                generation_log.append(log_entry)

            else:
                # ========== 传统生成模式 ==========
                generation_params = {
                    'papers': papers,
                    'research_field': kwargs.get('research_field', '计算生物学'),
                    'num_hypotheses': 1
                }

                gen_result = self.hypothesis_agent.execute(generation_params)

                if gen_result.get('success') and gen_result.get('hypotheses'):
                    final_hypotheses.extend(gen_result['hypotheses'])

        # ========== 更新统计 ==========
        self.v3_stats['total_tokens_saved'] += total_tokens_saved

        print(f"\n{'='*70}")
        print("[V3.0] Generation Summary")
        print(f"{'='*70}")
        print(f"  Success: {len(final_hypotheses)}/{num_hypotheses}")
        print(f"  Tokens Saved: ~{total_tokens_saved:,}")
        print(f"{'='*70}\n")

        return {
            'success': len(final_hypotheses) > 0,
            'hypotheses': final_hypotheses,
            'hypothesis_ids': [f'v3_hyp_{i}' for i in range(len(final_hypotheses))],
            'generation_log': generation_log,
            'token_saved': total_tokens_saved,
            'v3_features_enabled': {
                'fail_fast': enable_fail_fast,
                'context_rollback': enable_context_rollback
            }
        }

    def _handle_v3_rollback(self, session: FailFastSession, research_topic: str):
        """处理 V3.0 回滚"""
        self.v3_stats['total_rollbacks'] += 1

        print(f"\n[Rollback] Handling early stopping with context rollback...")

        # 确定触发类型
        if session.final_phase == GenerationPhase.PHASE_2_COLLISION:
            trigger = RollbackTrigger.COLLISION_DETECTED
        elif session.final_phase == GenerationPhase.PHASE_1_PROPOSAL:
            trigger = RollbackTrigger.EARLY_STOPPING
        else:
            trigger = RollbackTrigger.VALIDATION_FAILED

        # 创建碰撞报告（简化逻辑）
        collision_report = None
        if session.phase2 and session.phase2.collision_papers:
            collision_report = {'high_collision': session.phase2.collision_papers}

        # 执行回滚
        result = self.v3_context_manager.handle_failure(
            trigger=trigger,
            collision_report=collision_report
        )

        print(f"[Rollback] Context rolled back, saved {result.token_saved} tokens")

    # ==================== V3.0 统计信息 ====================

    def get_v3_statistics(self) -> Dict:
        """获取 V3.0 统计信息"""
        query_stats = self.v3_query_optimizer.get_search_statistics()
        fail_fast_stats = self.v3_fail_fast_generator.get_session_statistics()
        rollback_stats = self.v3_context_manager.rollback_manager.get_statistics()

        return {
            'v3_execution_stats': self.v3_stats,
            'query_optimizer_stats': query_stats,
            'fail_fast_stats': fail_fast_stats,
            'rollback_stats': rollback_stats
        }

    def print_v3_summary(self):
        """打印 V3.0 功能摘要"""
        print("\n" + "="*70)
        print("[V3.0] Feature Summary")
        print("="*70)

        stats = self.v3_stats

        print(f"\nQuery Optimizer:")
        print(f"  - V3-optimized searches: {stats['total_v3_searches']}")
        print(f"  - Average success rate: {self.v3_query_optimizer.get_search_statistics().get('success_rate', 0):.1%}")

        print(f"\nFail-Fast Generator:")
        print(f"  - Early stoppings triggered: {stats['total_early_stoppages']}")
        fail_fast_stats = self.v3_fail_fast_generator.get_session_statistics()
        print(f"  - Termination rate: {fail_fast_stats.get('termination_rate', 0):.1%}")
        print(f"  - Tokens saved: ~{stats['total_tokens_saved']:,}")

        print(f"\nContext Rollback:")
        print(f"  - Rollbacks executed: {stats['total_rollbacks']}")
        rollback_stats = self.v3_context_manager.rollback_manager.get_statistics()
        print(f"  - Lessons learned: {rollback_stats.get('total_lessons', 0)}")

        print(f"\n{'='*70}\n")


# ==================== V3.0 便捷包装类 ====================

class OrchestratorV3:
    """
    V3.0 完整版协调器

    整合所有 V3.0 功能的完整实现
    """

    def __init__(self, base_orchestrator=None):
        """
        初始化 V3.0 协调器

        Args:
            base_orchestrator: 现有的 Orchestrator 实例（可选）
                            如果提供，将混入 V3.0 功能
        """
        if base_orchestrator:
            # 混入模式：将 V3.0 功能添加到现有实例
            self.__dict__.update(base_orchestrator.__dict__)
            self._init_v3_components()
        else:
            # 独立模式：创建新的完整实例
            from src.core.orchestrator import Orchestrator
            base = Orchestrator()
            self.__dict__.update(base.__dict__)
            self._init_v3_components()

    # ========== V3.0 统一入口 ==========

    def run_v3_workflow(
        self,
        research_topic: str,
        num_hypotheses: int = 3,
        enable_all_v3_features: bool = True
    ) -> Dict:
        """
        运行完整的 V3.0 工作流

        Args:
            research_topic: 研究主题
            num_hypotheses: 生成假设数量
            enable_all_v3_features: 是否启用所有 V3.0 特性

        Returns:
            完整的工作流结果
        """
        print("\n" + "="*70)
        print("[V3.0] Starting Full Workflow")
        print(f"  Research Topic: {research_topic[:60]}...")
        print(f"  Hypotheses to Generate: {num_hypotheses}")
        print(f"  V3.0 Features: {'Enabled' if enable_all_v3_features else 'Disabled'}")
        print("="*70)

        # ========== Step 1: V3.0 优化的论文搜索 ==========
        print(f"\n[Step 1/3] V3.0 Optimized Paper Search...")

        search_result = self.search_papers_v3(
            query=research_topic,
            enable_v3_optimization=enable_all_v3_features
        )

        if not search_result['success']:
            return {
                'success': False,
                'error': 'Paper search failed',
                'stage': 'search'
            }

        papers = search_result['papers']
        print(f"  Found {len(papers)} papers")

        # ========== Step 2: V3.0 增强的假设生成 ==========
        print(f"\n[Step 2/3] V3.0 Enhanced Hypothesis Generation...")

        generation_result = self.generate_hypotheses_v3(
            research_topic=research_topic,
            papers=papers,
            num_hypotheses=num_hypotheses,
            enable_fail_fast=enable_all_v3_features,
            enable_context_rollback=enable_all_v3_features
        )

        if not generation_result['success']:
            return {
                'success': False,
                'error': 'Hypothesis generation failed',
                'stage': 'generation'
            }

        hypotheses = generation_result['hypotheses']

        # ========== Step 3: 打印 V3.0 统计 ==========
        print(f"\n[Step 3/3] V3.0 Statistics...")

        self.print_v3_summary()

        # ========== 返回结果 ==========
        return {
            'success': True,
            'hypotheses': hypotheses,
            'papers': papers,
            'v3_stats': self.get_v3_statistics(),
            'token_saved': generation_result['token_saved']
        }


# ==================== 便捷函数 ====================

def create_v3_orchestrator(base_orchestrator=None) -> OrchestratorV3:
    """创建 V3.0 协调器的便捷函数"""
    return OrchestratorV3(base_orchestrator=base_orchestrator)


def run_v3_workflow(research_topic: str, num_hypotheses: int = 3) -> Dict:
    """
    运行 V3.0 工作流的便捷函数

    Args:
        research_topic: 研究主题
        num_hypotheses: 生成假设数量

    Returns:
        工作流结果
    """
    orchestrator = create_v3_orchestrator()
    return orchestrator.run_v3_workflow(
        research_topic=research_topic,
        num_hypotheses=num_hypotheses
    )


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    print("="*70)
    print("Orchestrator V3.0 Extension Test")
    print("="*70)

    # 测试 V3.0 工作流
    result = run_v3_workflow(
        research_topic="Alzheimer pQTL hippocampal atrophy causal mediation",
        num_hypotheses=2
    )

    print(f"\nResult:")
    print(f"  Success: {result['success']}")
    print(f"  Hypotheses: {len(result.get('hypotheses', []))}")
    print(f"  Papers: {len(result.get('papers', []))}")
    if 'v3_stats' in result:
        print(f"  Tokens Saved: ~{result['v3_stats']['v3_execution_stats']['total_tokens_saved']:,}")
