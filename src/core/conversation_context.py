# -*- coding: utf-8 -*-
"""
V8.0 对话上下文管理器 (Conversation Context Manager)

核心功能：
1. 管理多轮对话的上下文信息
2. 记录用户意图、领域、查询、结果
3. 支持上���文引用（如"把刚才的搜索扩大"）
4. 与 Orchestrator 的 session 集成

作者: V8.0 发版工程师
日期: 2026-04-24
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from src.core.intent_parser import UserIntent, ResearchDomain, ParsedIntent

logger = logging.getLogger(__name__)


# ==================== 数据结构定义 ====================

@dataclass
class TurnRecord:
    """单轮对话记录"""
    turn_id: int
    timestamp: str
    user_input: str
    parsed_intent: Dict  # ParsedIntent 的字典形式
    action_taken: str  # 执行的动作
    result_summary: Optional[Dict] = None  # 结果摘要
    error: Optional[str] = None  # 错误信息

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)


@dataclass
class ConversationContext:
    """
    对话上下文

    管理多轮对话的状态信息
    """
    session_id: str
    started_at: str
    last_turn: int = 0

    # 上一轮的信息
    last_intent: Optional[UserIntent] = None
    last_domains: List[ResearchDomain] = field(default_factory=list)
    last_query: Optional[str] = None
    last_parameters: Optional[Dict] = None
    last_results_count: Optional[int] = None
    last_results_summary: Optional[Dict] = None

    # 当前会话状态
    current_papers: List[Dict] = field(default_factory=list)
    generated_hypotheses: List[Dict] = field(default_factory=list)
    hypothesis_ids: List[int] = field(default_factory=list)
    pending_hypotheses: List[Dict] = field(default_factory=list)  # 待用户选择的假设
    selected_hypothesis: Optional[Dict] = None

    # 对话历史
    turns: List[TurnRecord] = field(default_factory=list)

    # 配置状态
    config_snapshot: Optional[Dict] = None  # 配置快照

    def add_turn(
        self,
        user_input: str,
        parsed_intent: ParsedIntent,
        action_taken: str,
        result_summary: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> TurnRecord:
        """
        添加一轮对话记录

        Args:
            user_input: 用户输入
            parsed_intent: 解析后的意图
            action_taken: 执行的动作
            result_summary: 结果摘要
            error: 错误信息

        Returns:
            TurnRecord: 新增的对话记录
        """
        self.last_turn += 1

        turn = TurnRecord(
            turn_id=self.last_turn,
            timestamp=datetime.now().isoformat(),
            user_input=user_input,
            parsed_intent=parsed_intent.to_dict(),
            action_taken=action_taken,
            result_summary=result_summary,
            error=error
        )

        self.turns.append(turn)

        # 更新上一轮信息
        self.last_intent = parsed_intent.intent
        self.last_domains = [dd.domain for dd in parsed_intent.detected_domains]
        if parsed_intent.parameters:
            self.last_query = parsed_intent.parameters.query
            self.last_parameters = {
                'query': parsed_intent.parameters.query,
                'max_results': parsed_intent.parameters.max_results,
                'date_range': parsed_intent.parameters.date_range,
                'min_if': parsed_intent.parameters.min_if,
                'sources': parsed_intent.parameters.sources,
            }

        return turn

    def update_search_results(
        self,
        papers: List[Dict],
        results_count: int,
        summary: Optional[Dict] = None
    ):
        """
        更新搜索结果

        Args:
            papers: 论文列表
            results_count: 结果数量
            summary: 结果摘要
        """
        self.current_papers = papers
        self.last_results_count = results_count
        self.last_results_summary = summary or {
            'papers_found': results_count,
            'timestamp': datetime.now().isoformat()
        }

    def update_hypotheses(
        self,
        hypotheses: List[Dict],
        hypothesis_ids: List[int] = None
    ):
        """
        更新生成的假设

        Args:
            hypotheses: 假设列表
            hypothesis_ids: 假设ID列表
        """
        self.generated_hypotheses = hypotheses
        self.pending_hypotheses = hypotheses.copy()  # 待用户选择
        if hypothesis_ids:
            self.hypothesis_ids = hypothesis_ids

    def select_hypothesis(self, index: int) -> Optional[Dict]:
        """
        选择假设

        Args:
            index: 假设索引（0-based）

        Returns:
            选中的假设，如果索引无效则返回 None
        """
        if 0 <= index < len(self.pending_hypotheses):
            self.selected_hypothesis = self.pending_hypotheses[index]
            return self.selected_hypothesis
        return None

    def clear_pending_hypotheses(self):
        """清除待选择的假设（用户选择后调用）"""
        self.pending_hypotheses = []

    def get_context_for_parser(self) -> Dict:
        """
        获取供 IntentParser 使用的上下文

        Returns:
            Dict: 包含上一轮信息的上下文字典
        """
        context = {}

        if self.last_intent:
            context['last_intent'] = self.last_intent
        if self.last_domains:
            context['last_domains'] = [d.value for d in self.last_domains]
        if self.last_query:
            context['last_query'] = self.last_query
        if self.last_results_count is not None:
            context['last_results_count'] = self.last_results_count
        if self.selected_hypothesis:
            context['selected_hypothesis'] = self.selected_hypothesis.get('title', '')

        return context

    def to_dict(self) -> Dict:
        """转换为字典（用于序列化）"""
        d = asdict(self)
        # 转换枚举类型
        if self.last_intent:
            d['last_intent'] = self.last_intent.value
        d['last_domains'] = [d.value for d in self.last_domains]
        if self.selected_hypothesis:
            d['selected_hypothesis'] = self.selected_hypothesis
        return d

    def get_summary(self) -> str:
        """
        获取上下文摘要（用于显示）

        Returns:
            str: 上下文摘要
        """
        parts = []

        if self.last_query:
            parts.append(f"上次搜索: {self.last_query}")

        if self.last_results_count:
            parts.append(f"结果数: {self.last_results_count}")

        if self.pending_hypotheses:
            parts.append(f"待选择假设: {len(self.pending_hypotheses)} 个")

        if self.last_domains:
            domains_str = ', '.join([d.value for d in self.last_domains])
            parts.append(f"领域: {domains_str}")

        return ' | '.join(parts) if parts else "新会话"


# ==================== ContextManager 管理器 ====================

class ContextManager:
    """
    上下文管理器

    管理多个会话的上下文
    """

    def __init__(self):
        """初始化上下文管理器"""
        self._contexts: Dict[str, ConversationContext] = {}
        self._current_session_id: Optional[str] = None

    def create_context(self, session_id: str) -> ConversationContext:
        """
        创建新上下文

        Args:
            session_id: 会话ID

        Returns:
            ConversationContext: 新创建的上下文
        """
        context = ConversationContext(
            session_id=session_id,
            started_at=datetime.now().isoformat()
        )
        self._contexts[session_id] = context
        self._current_session_id = session_id
        logger.info(f"[ContextManager] 创建上下文: {session_id}")
        return context

    def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """
        获取上下文

        Args:
            session_id: 会话ID

        Returns:
            ConversationContext: 上下文，如果不存在则返回 None
        """
        return self._contexts.get(session_id)

    def get_current_context(self) -> Optional[ConversationContext]:
        """
        获取当前上下文

        Returns:
            ConversationContext: 当前上下文，如果不存在则返回 None
        """
        if self._current_session_id:
            return self._contexts.get(self._current_session_id)
        return None

    def set_current_session(self, session_id: str):
        """
        设置当前会话

        Args:
            session_id: 会话ID
        """
        if session_id in self._contexts:
            self._current_session_id = session_id
            logger.info(f"[ContextManager] 切换到会话: {session_id}")
        else:
            logger.warning(f"[ContextManager] 会话不存在: {session_id}")

    def remove_context(self, session_id: str):
        """
        移除上下文

        Args:
            session_id: 会话ID
        """
        if session_id in self._contexts:
            del self._contexts[session_id]
            if self._current_session_id == session_id:
                self._current_session_id = None
            logger.info(f"[ContextManager] 移除上下文: {session_id}")

    def list_sessions(self) -> List[str]:
        """
        列出所有会话ID

        Returns:
            List[str]: 会话ID列表
        """
        return list(self._contexts.keys())

    def clear_all(self):
        """清除所有上下文"""
        self._contexts.clear()
        self._current_session_id = None
        logger.info("[ContextManager] 清除所有上下文")


# ==================== 便捷函数 ====================

_global_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取全局上下文管理器实例"""
    global _global_context_manager
    if _global_context_manager is None:
        _global_context_manager = ContextManager()
    return _global_context_manager


def create_session_context(session_id: str) -> ConversationContext:
    """
    创建会话上下文（便捷函数）

    Args:
        session_id: 会话ID

    Returns:
        ConversationContext: 新创建的上下文
    """
    manager = get_context_manager()
    return manager.create_context(session_id)


def get_current_context() -> Optional[ConversationContext]:
    """
    获取当前上下文（便捷函数）

    Returns:
        ConversationContext: 当前上下文，如果不存在则返回 None
    """
    manager = get_context_manager()
    return manager.get_current_context()


# ==================== 测试用例 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V8.0 对话上下文管理器测试")
    print("=" * 70)

    # 创建上下文
    context = create_session_context("test_session_001")

    print(f"\n会话ID: {context.session_id}")
    print(f"开始时间: {context.started_at}")
    print(f"上下文摘要: {context.get_summary()}")

    # 模拟添加对话轮次
    from src.core.intent_parser import ParsedIntent, DomainDetection, SearchParameters

    parsed = ParsedIntent(
        intent=UserIntent.SEARCH_PAPERS,
        original_input="帮我找50篇关于CRISPR的论文",
        detected_domains=[
            DomainDetection(
                domain=ResearchDomain.GENOMICS,
                confidence=0.9,
                reasoning="匹配关键词 CRISPR"
            )
        ],
        inferred_techniques=["基因编辑"],
        inferred_applications=["基因治疗"],
        parameters=SearchParameters(
            query="CRISPR 基因编辑",
            max_results=50
        ),
        confidence=0.9,
        reasoning="用户想搜索 CRISPR 相关论文"
    )

    context.add_turn(
        user_input="帮我找50篇关于CRISPR的论文",
        parsed_intent=parsed,
        action_taken="search_papers",
        result_summary={"papers_found": 50, "sources": ["pubmed", "arxiv"]}
    )

    context.update_search_results(
        papers=[{"title": f"Paper {i}"} for i in range(50)],
        results_count=50,
        summary={"papers_found": 50}
    )

    print(f"\n第1轮对话后:")
    print(f"  上次意图: {context.last_intent.value}")
    print(f"  上次查询: {context.last_query}")
    print(f"  上次结果数: {context.last_results_count}")
    print(f"  上下文摘要: {context.get_summary()}")

    # 获取供解析器使用的上下文
    parser_context = context.get_context_for_parser()
    print(f"\n供解析器使用的上下文:")
    for key, value in parser_context.items():
        print(f"  {key}: {value}")

    # 模拟生成假设
    hypotheses = [
        {"title": "假设1", "description": "描述1"},
        {"title": "假设2", "description": "描述2"},
        {"title": "假设3", "description": "描述3"}
    ]
    context.update_hypotheses(hypotheses)

    print(f"\n生成假设后:")
    print(f"  待选择假设: {len(context.pending_hypotheses)} 个")

    # 模拟选择假设
    selected = context.select_hypothesis(1)
    print(f"  选中的假设: {selected['title']}")

    print("\n" + "=" * 70)
    print("测试完成")
