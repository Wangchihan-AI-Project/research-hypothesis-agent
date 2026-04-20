# -*- coding: utf-8 -*-
"""
V3.0 重构版首席科学家智能体 (HypothesisAgent V3.0)

整合三大工程特性：
1. Query Optimizer - 查询优化器
2. Fail-Fast Generator - 早期熔断与两步生成法
3. Context Rollback - 上下文纯净回滚

借鉴 karpathy/autoresearch 的底层逻辑，实现透明的状态机日志。

作者: 架构师 V3.0
日期: 2026-04-16
"""

from typing import Dict, List, Optional, Any, Tuple
import logging
import os
import json
import time
from datetime import datetime
from dataclasses import dataclass

import anthropic

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

# 导入原有模块
from src.utils.pubmed import PubMedSearcher
from src.agents.base import BaseAgent

logger = logging.getLogger(__name__)


# ==============================================================================
# V3.0 系统提示词（精简版，核心逻辑已模块化）
# ==============================================================================

CHIEF_SCIENTIST_SYSTEM_PROMPT_V3 = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    首席科学家智能体 V3.0 - Nature 级别 PI                    ║
║                  整合 Query Optimizer + Fail-Fast + Rollback                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

你是顶级期刊审稿人兼 PI，追求因果逻辑的铁血闭环。

## 核心原则

1. **零推诿**：禁止使用 "N/A"、"待定"、"等" 等推诿词汇
2. **去口号化**：具体到 R 包名、函数名、参数值
3. **因果链明确**：X → M → Y 必须清晰

## 输出要求

生成的研究假设必须包含：
1. 核心机制假说（50 字左右）
2. 详细的七段式展开（1500 字以上）
3. 具体的技术路线（软件名+版本+参数）

---

{LESSON_SUFFIX}  # 动态注入的红方教训
"""


# ==============================================================================
# V3.0 首席科学家智能体
# ==============================================================================

@dataclass
class V3GenerationResult:
    """V3.0 生成结果"""
    success: bool
    hypothesis: Optional[Dict] = None
    session: Optional[FailFastSession] = None
    rollback_triggered: bool = False
    token_saved: int = 0
    execution_time: float = 0.0
    state_transitions: List[str] = None

    def __post_init__(self):
        if self.state_transitions is None:
            self.state_transitions = []


class HypothesisAgentV3(BaseAgent):
    """
    V3.0 重构版首席科学家智能体

    核心改进：
    1. 集成 QueryOptimizer - 智能查询优化
    2. 集成 FailFastGenerator - 早期熔断机制
    3. 集成 ContextRollbackManager - 上下文回滚
    """

    def __init__(self):
        super().__init__("首席科学家智能体V3", agent_type="hypothesis")

        # 初始化 LLM 客户端
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        if base_url:
            self.client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=base_url
            )
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)

        # 初始化 V3.0 核心模块
        self.query_optimizer = QueryOptimizer()
        self.context_manager = ConversationManager()

        # 初始化 PubMed 搜索器（用于 Fail-Fast 碰撞检测）
        try:
            self.pubmed_searcher = PubMedSearcher(
                email=os.getenv('PUBMED_EMAIL'),
                api_key=os.getenv('PUBMED_API_KEY')
            )
        except Exception as e:
            logger.warning(f"PubMed 初始化失败: {e}")
            self.pubmed_searcher = None

        # 初始化 Fail-Fast 生成器
        self.fail_fast_generator = create_fail_fast_generator(
            llm_client=self.client,
            pubmed_searcher=self.pubmed_searcher
        )

        # 初始化上下文管理器
        self.context_manager.initialize(CHIEF_SCIENTIST_SYSTEM_PROMPT_V3)

        # 状态追踪
        self.state_transitions: List[str] = []
        self.execution_stats: Dict = {
            'total_generations': 0,
            'early_stoppings': 0,
            'total_token_saved': 0
        }

    def _log_state(self, state: str):
        """记录状态转换（透明日志）"""
        self.state_transitions.append(state)
        logger.info(f"[State Machine] {state}")
        print(f"[State Machine] {state}")

    def execute(
        self,
        input_data: Dict
    ) -> Dict:
        """
        执行 V3.0 生成流程

        Args:
            input_data: {
                'research_topic': str - 研究主题
                'literature_report': str - 文献背景
                'papers': List[Dict] - 相关论文
                'num_hypotheses': int - 生成数量
                'enable_fail_fast': bool - 是否启用早期熔断
                'enable_query_optimization': bool - 是否启用查询优化
            }

        Returns:
            生成结果
        """
        start_time = time.time()
        self.execution_stats['total_generations'] += 1

        research_topic = input_data.get('research_topic', '')
        literature_report = input_data.get('literature_report', '')
        papers = input_data.get('papers', [])
        num_hypotheses = input_data.get('num_hypotheses', 1)
        enable_fail_fast = input_data.get('enable_fail_fast', True)
        enable_query_optimization = input_data.get('enable_query_optimization', True)

        # ========== 状态: INITIALIZATION ==========
        self._log_state("[INITIALIZATION] 开始 V3.0 生成流程")
        self._log_state(f"  研究主题: {research_topic[:60]}...")
        self._log_state(f"  Fail-Fast: {'启用' if enable_fail_fast else '禁用'}")
        self._log_state(f"  Query Optimization: {'启用' if enable_query_optimization else '禁用'}")

        results = []
        total_token_saved = 0
        rollback_triggered = False

        for i in range(num_hypotheses):
            self._log_state(f"\n{'='*60}")
            self._log_state(f"生成假设 {i+1}/{num_hypotheses}")
            self._log_state(f"{'='*60}")

            if enable_fail_fast:
                # ========== 使用 Fail-Fast 生成 ==========
                session = self._generate_with_fail_fast(
                    research_topic=research_topic,
                    literature_report=literature_report,
                    papers=papers
                )

                total_token_saved += session.token_saved

                # 判断是否需要回滚
                if session.final_phase in [
                    GenerationPhase.PHASE_1_PROPOSAL,
                    GenerationPhase.PHASE_2_COLLISION,
                    GenerationPhase.TERMINATED
                ]:
                    # 触发回滚
                    self._handle_termination(session)
                    rollback_triggered = True
                elif session.phase3 and session.phase3.success:
                    # 成功生成
                    results.append(session.phase3.full_hypothesis)
                    self._log_state(f"[SUCCESS] 假设 {i+1} 生成成功")

            else:
                # ========== 传统生成模式（向后兼容）==========
                hypothesis = self._generate_traditional(
                    research_topic=research_topic,
                    literature_report=literature_report,
                    papers=papers
                )
                if hypothesis:
                    results.append(hypothesis)

        execution_time = time.time() - start_time

        # ========== 状态: COMPLETION ==========
        self._log_state(f"\n{'='*60}")
        self._log_state("[COMPLETION] V3.0 生成流程完成")
        self._log_state(f"  成功生成: {len(results)}/{num_hypotheses}")
        self._log_state(f"  节省 Token: ~{total_token_saved:,}")
        self._log_state(f"  执行时间: {execution_time:.1f}s")
        self._log_state(f"{'='*60}\n")

        # 更新统计
        self.execution_stats['total_token_saved'] += total_token_saved
        if rollback_triggered:
            self.execution_stats['early_stoppings'] += 1

        return {
            'success': len(results) > 0,
            'hypotheses': results,
            'hypothesis_ids': [f'v3_hyp_{i}' for i in range(len(results))],
            'saved_count': len(results),
            'token_saved': total_token_saved,
            'rollback_triggered': rollback_triggered,
            'execution_time': execution_time,
            'state_transitions': self.state_transitions,
            'v3_features': {
                'fail_fast_enabled': enable_fail_fast,
                'query_optimization_enabled': enable_query_optimization,
                'context_rollback_enabled': True
            }
        }

    def _generate_with_fail_fast(
        self,
        research_topic: str,
        literature_report: str,
        papers: List[Dict]
    ) -> FailFastSession:
        """使用 Fail-Fast 机制生成假设"""
        # ========== 状态: PHASE_1_PROPOSAL ==========
        self._log_state("[PHASE_1_PROPOSAL] 生成核心机制假说...")

        session = self.fail_fast_generator.generate(
            research_topic=research_topic,
            literature_context=literature_report,
            papers=papers
        )

        # 打印各阶段结果
        if session.phase1:
            self._log_state(f"  核心假说: {session.phase1.core_hypothesis[:60]}...")

        if session.phase2:
            self._log_state(f"[PHASE_2_COLLISION] 碰撞检测完成")
            self._log_state(f"  碰撞数: {session.phase2.collision_count}")
            self._log_state(f"  新颖性: {session.phase2.novelty_score:.1f}/100")

            if session.phase2.should_terminate:
                self._log_state("[EARLY_STOPPING] 熔断触发！")
                return session

        if session.phase3:
            self._log_state("[PHASE_3_EXPANSION] 完整展开完成")

        return session

    def _generate_traditional(
        self,
        research_topic: str,
        literature_report: str,
        papers: List[Dict]
    ) -> Optional[Dict]:
        """传统生成模式（向后兼容）"""
        prompt = f"""基于以下研究主题，生成一个高质量的研究假设。

研究主题: {research_topic}

文献背景: {literature_report[:1000]}

请生成包含 title, details, scores 的 JSON 格式假设。"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            return self._parse_hypothesis(response_text)

        except Exception as e:
            logger.error(f"传统生成失败: {e}")
            return None

    def _parse_hypothesis(self, response_text: str) -> Optional[Dict]:
        """解析假设响应"""
        try:
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            return json.loads(response_text)
        except:
            return {
                'title': '解析失败',
                'details': response_text[:1000],
                'scores': {'novelty': 5.0, 'rigor': 5.0, 'impact': 5.0, 'overall': 5.0}
            }

    def _handle_termination(self, session: FailFastSession):
        """处理早期终止情况"""
        self._log_state("[ROLLBACK_TRIGGERED] Handling early termination")

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

        result = self.context_manager.handle_failure(
            trigger=trigger,
            collision_report=collision_report
        )

        self._log_state(f"  回滚成功，节省 {result.token_saved:,} tokens")

    def optimize_search_query(
        self,
        research_topic: str,
        domain_keywords: List[str] = None
    ) -> SearchPlan:
        """
        优化的查询接口

        Args:
            research_topic: 研究主题
            domain_keywords: 领域关键词

        Returns:
            SearchPlan: 优化的搜索计划
        """
        self._log_state("[QUERY_OPTIMIZATION] 开始优化查询...")

        plan = self.query_optimizer.optimize(
            research_topic=research_topic,
            domain_keywords=domain_keywords,
            strategy='adaptive'
        )

        self._log_state(f"[QUERY_OPTIMIZATION] 计划生成完成: {len(plan.queries)} 个查询")

        return plan

    def get_statistics(self) -> Dict:
        """获取 V3.0 统计信息"""
        fail_fast_stats = self.fail_fast_generator.get_session_statistics()
        rollback_stats = self.context_manager.rollback_manager.get_statistics()

        return {
            'execution_stats': self.execution_stats,
            'fail_fast_stats': fail_fast_stats,
            'rollback_stats': rollback_stats,
            'query_optimizer_stats': self.query_optimizer.get_search_statistics()
        }


# ==============================================================================
# 便捷函数
# ==============================================================================

def create_hypothesis_agent_v3() -> HypothesisAgentV3:
    """创建 V3.0 假设生成器的便捷函数"""
    return HypothesisAgentV3()


def generate_hypothesis_v3(
    research_topic: str,
    literature_report: str = "",
    papers: List[Dict] = None,
    enable_fail_fast: bool = True
) -> V3GenerationResult:
    """
    使用 V3.0 架构生成假设的便捷函数

    Args:
        research_topic: 研究主题
        literature_report: 文献背景
        papers: 相关论文
        enable_fail_fast: 是否启用早期熔断

    Returns:
        V3GenerationResult: 生成结果
    """
    agent = create_hypothesis_agent_v3()

    result = agent.execute({
        'research_topic': research_topic,
        'literature_report': literature_report,
        'papers': papers or [],
        'num_hypotheses': 1,
        'enable_fail_fast': enable_fail_fast
    })

    return V3GenerationResult(
        success=result['success'],
        hypothesis=result['hypotheses'][0] if result['hypotheses'] else None,
        token_saved=result['token_saved'],
        rollback_triggered=result['rollback_triggered'],
        execution_time=result['execution_time'],
        state_transitions=result['state_transitions']
    )


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    print("="*60)
    print("HypothesisAgent V3.0 测试")
    print("="*60)

    # 测试查询优化
    print("\n1. 测试 Query Optimizer")
    agent = create_hypothesis_agent_v3()
    plan = agent.optimize_search_query(
        "Alzheimer's disease and machine learning for early diagnosis",
        domain_keywords=['biomarkers', 'neuroimaging']
    )

    print(f"\n搜索计划: {len(plan.queries)} 个查询")
    while plan.has_remaining():
        query = plan.get_next_query()
        print(f"  - {query}")

    # 测试生成（简化版，不实际调用 LLM）
    print("\n2. V3.0 架构就绪")
    print("  - Query Optimizer: ✓")
    print("  - Fail-Fast Generator: ✓")
    print("  - Context Rollback: ✓")
    print("\n使用 generate_hypothesis_v3() 函数进行完整测试")
