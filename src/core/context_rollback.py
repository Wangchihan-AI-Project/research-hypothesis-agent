# -*- coding: utf-8 -*-
"""
上下文纯净回滚 (Context Rollback) - V3.0 架构升级核心模块

借鉴 karpathy/autoresearch 范式，重构反馈循环机制。

核心设计理念：
- 熔断或审计不通过时，严禁将冗长 JSON 追加到 messages 历史
- 执行类似 git revert 的状态清理
- 只在下一轮 System Prompt 末尾注入高度浓缩的"红方教训"

作者: 架构师 V3.0
日期: 2026-04-16
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


class RollbackTrigger(Enum):
    """回滚触发类型"""
    EARLY_STOPPING = "early_stopping"  # 早期熔断
    COLLISION_DETECTED = "collision_detected"  # 碰撞检测失败
    RED_TEAM_REJECT = "red_team_reject"  # 红方审计拒绝
    DEFENSE_FAILED = "defense_failed"  # 答辩失败
    VALIDATION_FAILED = "validation_failed"  # 验证失败
    MANUAL = "manual"  # 手动触发


@dataclass
class ContextSnapshot:
    """上下文快照"""
    snapshot_id: str
    timestamp: str
    messages: List[Dict]  # 当前的 messages 历史
    metadata: Dict = field(default_factory=dict)
    checksum: str = ""  # 用于验证完整性

    def __post_init__(self):
        # 计算校验和
        content = json.dumps(self.messages, sort_keys=True)
        self.checksum = hashlib.md5(content.encode()).hexdigest()[:8]


@dataclass
class LessonLearned:
    """红方教训 - 浓缩的反馈信息"""
    trigger_type: RollbackTrigger
    lesson_summary: str  # 一句话总结
    forbidden_patterns: List[str]  # 禁止的模式
    recommended_directions: List[str]  # 推荐的方向
    collision_evidence: List[Dict]  # 碰撞证据（如有）
    confidence: float = 0.8  # 教训的可信度

    def to_system_prompt_suffix(self) -> str:
        """
        转换为 System Prompt 后缀

        这是注入到下一轮的关键信息，格式高度浓缩
        """
        parts = []

        parts.append("\n" + "="*60)
        parts.append("🔴 【红方教训 - 上一轮失败反馈】")
        parts.append("="*60)

        # 一句话总结
        parts.append(f"\n💥 失败原因: {self.lesson_summary}")

        # 禁止模式
        if self.forbidden_patterns:
            parts.append("\n🚫 本轮禁止:")
            for i, pattern in enumerate(self.forbidden_patterns[:3], 1):
                parts.append(f"   {i}. {pattern}")

        # 推荐方向
        if self.recommended_directions:
            parts.append("\n✅ 推荐方向:")
            for i, direction in enumerate(self.recommended_directions[:2], 1):
                parts.append(f"   {i}. {direction}")

        # 碰撞证据（如有）
        if self.collision_evidence:
            parts.append("\n📋 碰撞证据（已被发表的研究）:")
            for paper in self.collision_evidence[:2]:
                parts.append(f"   - PMID:{paper.get('pmid', 'N/A')} {paper.get('title', '')[:50]}...")

        parts.append("\n" + "="*60 + "\n")

        return "\n".join(parts)


@dataclass
class RollbackResult:
    """回滚结果"""
    success: bool
    rollback_to_snapshot: str = ""  # 回滚到的快照 ID
    lessons_applied: List[LessonLearned] = field(default_factory=list)
    current_messages: List[Dict] = field(default_factory=list)
    token_saved: int = 0  # 节省的 token 数量


class ContextRollbackManager:
    """
    上下文回滚管理器

    实现类似 git revert 的状态管理：
    1. 在关键节点创建快照
    2. 失败时回滚到干净状态
    3. 注入浓缩的"红方教训"
    """

    def __init__(self):
        self.logger = logger
        self.snapshots: Dict[str, ContextSnapshot] = {}  # snapshot_id -> snapshot
        self.lesson_history: List[LessonLearned] = []
        self.current_snapshot_id: Optional[str] = None

    def _log_state(self, message: str):
        """记录状态日志"""
        self.logger.info(f"[ContextRollback] {message}")
        print(f"[ContextRollback] {message}")

    def create_snapshot(
        self,
        messages: List[Dict],
        metadata: Dict = None
    ) -> str:
        """
        创建上下文快照

        在关键节点（如生成前）调用，保存干净的上下文状态

        Args:
            messages: 当前的 messages 历史
            metadata: 元数据

        Returns:
            snapshot_id: 快照 ID
        """
        snapshot_id = hashlib.md5(
            f"{datetime.now().isoformat()}".encode()
        ).hexdigest()[:8]

        snapshot = ContextSnapshot(
            snapshot_id=snapshot_id,
            timestamp=datetime.now().isoformat(),
            messages=[m.copy() for m in messages],  # 深拷贝
            metadata=metadata or {}
        )

        self.snapshots[snapshot_id] = snapshot
        self.current_snapshot_id = snapshot_id

        self._log_state(f"✓ 快照已创建: {snapshot_id} ({len(messages)} 条消息)")

        return snapshot_id

    def rollback(
        self,
        to_snapshot: str = None,
        trigger: RollbackTrigger = RollbackTrigger.MANUAL,
        lesson: LessonLearned = None
    ) -> RollbackResult:
        """
        执行回滚操作

        Args:
            to_snapshot: 回滚到的快照 ID（默认为当前快照）
            trigger: 触发类型
            lesson: 红方教训

        Returns:
            RollbackResult: 回滚结果
        """
        target_snapshot_id = to_snapshot or self.current_snapshot_id

        if not target_snapshot_id or target_snapshot_id not in self.snapshots:
            self._log_state("❌ 无效的快照 ID")
            return RollbackResult(success=False)

        snapshot = self.snapshots[target_snapshot_id]

        # 计算节省的 token（估算）
        # 假设每次失败会避免约 5000 tokens 的冗长 JSON
        token_saved = 5000

        self._log_state("\n" + "="*60)
        self._log_state("🔄 [ROLLBACK TRIGGERED] 上下文回滚")
        self._log_state("="*60)
        self._log_state(f"   触发原因: {trigger.value}")
        self._log_state(f"   回滚到: {target_snapshot_id}")
        self._log_state(f"   节省 Token: ~{token_saved:,}")
        self._log_state("="*60 + "\n")

        # 记录教训
        if lesson:
            self.lesson_history.append(lesson)
            self._log_state(f"📚 红方教训已记录: {lesson.lesson_summary}")

        result = RollbackResult(
            success=True,
            rollback_to_snapshot=target_snapshot_id,
            lessons_applied=[lesson] if lesson else [],
            current_messages=[m.copy() for m in snapshot.messages],
            token_saved=token_saved
        )

        return result

    def get_clean_messages(
        self,
        snapshot_id: str = None,
        apply_lessons: bool = True
    ) -> List[Dict]:
        """
        获取清理后的 messages

        Args:
            snapshot_id: 快照 ID（默认为当前快照）
            apply_lessons: 是否应用历史教训

        Returns:
            清理后的 messages 列表
        """
        target_snapshot_id = snapshot_id or self.current_snapshot_id

        if not target_snapshot_id or target_snapshot_id not in self.snapshots:
            return []

        snapshot = self.snapshots[target_snapshot_id]
        messages = [m.copy() for m in snapshot.messages]

        # 如果需要应用教训，在 System Prompt 后添加
        if apply_lessons and self.lesson_history:
            # 获取最近的教训（最多 2 条）
            recent_lessons = self.lesson_history[-2:]

            # 找到 System Prompt 的位置（通常在开头）
            system_suffix = "\n".join([
                lesson.to_system_prompt_suffix()
                for lesson in recent_lessons
            ])

            # 在第一条 user 消息前插入
            for i, msg in enumerate(messages):
                if msg.get('role') == 'user':
                    # 创建包含教训的 system 消息（如果已有）
                    if i > 0 and messages[i-1].get('role') == 'system':
                        # 在现有 system 消息后追加
                        messages[i-1]['content'] += system_suffix
                    else:
                        # 插入新的 system 消息
                        messages.insert(i, {
                            'role': 'system',
                            'content': system_suffix
                        })
                    break

        return messages

    def create_lesson_from_failure(
        self,
        trigger: RollbackTrigger,
        audit_result: Dict = None,
        collision_report: Dict = None
    ) -> LessonLearned:
        """
        从失败中创建教训

        Args:
            trigger: 触发类型
            audit_result: 审计结果（如有）
            collision_report: 碰撞报告（如有）

        Returns:
            LessonLearned: 教训对象
        """
        if trigger == RollbackTrigger.COLLISION_DETECTED:
            return self._create_collision_lesson(collision_report)
        elif trigger == RollbackTrigger.RED_TEAM_REJECT:
            return self._create_red_team_lesson(audit_result)
        elif trigger == RollbackTrigger.DEFENSE_FAILED:
            return self._create_defense_lesson(audit_result)
        elif trigger == RollbackTrigger.EARLY_STOPPING:
            return self._create_early_stopping_lesson(audit_result)
        else:
            return LessonLearned(
                trigger_type=trigger,
                lesson_summary="生成失败，需要重新尝试",
                forbidden_patterns=[],
                recommended_directions=["改变研究角度", "使用不同的方法学"]
            )

    def _create_collision_lesson(self, collision_report: Dict) -> LessonLearned:
        """创建碰撞检测失败的教训"""
        high_collision = collision_report.get('high_collision', []) if collision_report else []

        forbidden = []
        evidence = []

        for paper in high_collision[:3]:
            title = paper.get('title', '')
            forbidden.append(f"避免与 '{title[:40]}...' 相同的研究角度")
            evidence.append(paper)

        return LessonLearned(
            trigger_type=RollbackTrigger.COLLISION_DETECTED,
            lesson_summary=f"发现 {len(high_collision)} 篇高度同质化文献",
            forbidden_patterns=forbidden,
            recommended_directions=[
                "选择未被研究的中介变量",
                "结合跨学科方法",
                "关注不同的人群或数据集"
            ],
            collision_evidence=evidence,
            confidence=0.9
        )

    def _create_red_team_lesson(self, audit_result: Dict) -> LessonLearned:
        """创建红方审计失败的教训"""
        critical_issues = audit_result.get('critical_issues', []) if audit_result else []

        forbidden = [
            issue.get('issue', '')[:80]
            for issue in critical_issues[:3]
        ]

        return LessonLearned(
            trigger_type=RollbackTrigger.RED_TEAM_REJECT,
            lesson_summary=f"红方审计发现 {len(critical_issues)} 个致命缺陷",
            forbidden_patterns=forbidden,
            recommended_directions=[
                "加强因果推断框架",
                "添加敏感性分析",
                "明确混杂控制策略"
            ],
            collision_evidence=[],
            confidence=0.85
        )

    def _create_defense_lesson(self, audit_result: Dict) -> LessonLearned:
        """创建答辩失败的教训"""
        verdict = audit_result.get('final_verdict', '') if audit_result else ''
        issues = audit_result.get('critical_issues', []) if audit_result else []

        return LessonLearned(
            trigger_type=RollbackTrigger.DEFENSE_FAILED,
            lesson_summary=f"答辩失败: {verdict[:50]}...",
            forbidden_patterns=[
                issue.get('issue', '')[:80]
                for issue in issues[:2]
            ],
            recommended_directions=[
                "根据委员会意见修改技术路线",
                "补充预实验数据支持",
                "简化假设以提升可行性"
            ],
            collision_evidence=[],
            confidence=0.8
        )

    def _create_early_stopping_lesson(self, audit_result: Dict) -> LessonLearned:
        """创建早期熔断的教训"""
        reason = audit_result.get('terminated_reason', '') if audit_result else ''

        return LessonLearned(
            trigger_type=RollbackTrigger.EARLY_STOPPING,
            lesson_summary=f"早期熔断: {reason[:50]}...",
            forbidden_patterns=[
                "重复已被研究的角度",
                "使用缺乏新颖性的方法"
            ],
            recommended_directions=[
                "寻找未被研究的因果路径",
                "引入跨学科创新",
                "关注边缘人群或特殊数据集"
            ],
            collision_evidence=[],
            confidence=0.95
        )

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            'total_snapshots': len(self.snapshots),
            'total_lessons': len(self.lesson_history),
            'current_snapshot': self.current_snapshot_id,
            'lesson_breakdown': {
                trigger.value: sum(1 for l in self.lesson_history if l.trigger_type == trigger)
                for trigger in RollbackTrigger
            }
        }

    def clear_old_snapshots(self, keep_recent: int = 5):
        """清理旧快照，只保留最近的几个"""
        if len(self.snapshots) <= keep_recent:
            return

        # 按时间排序
        sorted_snapshots = sorted(
            self.snapshots.items(),
            key=lambda x: x[1].timestamp,
            reverse=True
        )

        # 保留最近的
        to_keep = set([sid for sid, _ in sorted_snapshots[:keep_recent]])
        to_remove = [sid for sid in self.snapshots if sid not in to_keep]

        for sid in to_remove:
            del self.snapshots[sid]

        self._log_state(f"清理了 {len(to_remove)} 个旧快照")


class ConversationManager:
    """
    对话管理器 - 整合 Context Rollback 的高层接口

    提供简洁的 API 用于管理多轮对话
    """

    def __init__(self):
        self.rollback_manager = ContextRollbackManager()
        self.base_system_prompt = ""
        self.conversation_history: List[Dict] = []

    def initialize(self, system_prompt: str):
        """初始化对话"""
        self.base_system_prompt = system_prompt
        self.conversation_history = [
            {"role": "system", "content": system_prompt}
        ]
        # 创建初始快照
        self.rollback_manager.create_snapshot(
            self.conversation_history,
            metadata={'phase': 'initialization'}
        )

    def add_user_message(self, content: str) -> str:
        """添加用户消息"""
        self.conversation_history.append({
            "role": "user",
            "content": content
        })
        return self.rollback_manager.current_snapshot_id

    def add_assistant_message(self, content: str) -> str:
        """添加助手消息"""
        self.conversation_history.append({
            "role": "assistant",
            "content": content
        })
        return self.rollback_manager.current_snapshot_id

    def handle_failure(
        self,
        trigger: RollbackTrigger,
        audit_result: Dict = None,
        collision_report: Dict = None
    ) -> RollbackResult:
        """
        处理失败情况

        Args:
            trigger: 触发类型
            audit_result: 审计结果
            collision_report: 碰撞报告

        Returns:
            RollbackResult: 回滚结果
        """
        # 创建教训
        lesson = self.rollback_manager.create_lesson_from_failure(
            trigger=trigger,
            audit_result=audit_result,
            collision_report=collision_report
        )

        # 执行回滚
        result = self.rollback_manager.rollback(
            trigger=trigger,
            lesson=lesson
        )

        # 更新当前对话历史
        self.conversation_history = result.current_messages

        # 应用教训到 System Prompt
        enhanced_messages = self.rollback_manager.get_clean_messages(apply_lessons=True)
        self.conversation_history = enhanced_messages

        return result

    def get_current_messages(self) -> List[Dict]:
        """获取当前对话历史"""
        return self.conversation_history.copy()

    def get_token_efficiency(self) -> Dict:
        """获取 Token 效率统计"""
        stats = self.rollback_manager.get_statistics()
        # 估算节省的 token
        total_lessons = stats['total_lessons']
        estimated_saved = total_lessons * 5000  # 每次失败约节省 5000 tokens

        return {
            'total_lessons': total_lessons,
            'estimated_token_saved': estimated_saved,
            'efficiency_rate': f"{min(95, 50 + total_lessons * 5)}%"
        }


# ========== 便捷函数 ==========

def create_conversation_manager(system_prompt: str) -> ConversationManager:
    """创建对话管理器的便捷函数"""
    manager = ConversationManager()
    manager.initialize(system_prompt)
    return manager


def rollback_and_retry(
    messages: List[Dict],
    trigger: RollbackTrigger,
    audit_result: Dict = None
) -> List[Dict]:
    """
    回滚并重试的便捷函数

    Args:
        messages: 当前的 messages
        trigger: 触发类型
        audit_result: 审计结果

    Returns:
        清理后的 messages
    """
    manager = ConversationManager()
    manager.base_system_prompt = messages[0].get('content', '') if messages else ""
    manager.conversation_history = messages

    # 创建快照
    manager.rollback_manager.create_snapshot(messages)

    # 处理失败
    manager.handle_failure(trigger, audit_result)

    return manager.get_current_messages()


if __name__ == '__main__':
    # 测试 Context Rollback
    print("="*60)
    print("Context Rollback 测试")
    print("="*60)

    # 创建对话管理器
    system_prompt = """你是首席科学家智能体..."""

    manager = create_conversation_manager(system_prompt)

    # 模拟对话
    print("\n1. 初始化对话")
    print(f"   消息数: {len(manager.get_current_messages())}")

    print("\n2. 添加用户消息")
    manager.add_user_message("请生成关于阿尔茨海默病的假说")

    print("\n3. 模拟红方审计失败")
    audit_result = {
        'critical_issues': [
            {'issue': '因果链不完整，缺少中介效应检验'},
            {'issue': '未考虑混杂因素'}
        ],
        'final_verdict': '假设存在致命缺陷，需要重构'
    }

    result = manager.handle_failure(
        trigger=RollbackTrigger.RED_TEAM_REJECT,
        audit_result=audit_result
    )

    print(f"\n4. 回滚结果:")
    print(f"   成功: {result.success}")
    print(f"   节省 Token: {result.token_saved:,}")
    print(f"   应用教训数: {len(result.lessons_applied)}")

    print("\n5. 清理后的消息:")
    clean_messages = manager.get_current_messages()
    for i, msg in enumerate(clean_messages):
        role = msg.get('role', '')
        content = msg.get('content', '')[:100]
        print(f"   [{i}] {role}: {content}...")

    print("\n6. Token 效率:")
    efficiency = manager.get_token_efficiency()
    print(f"   估计节省: {efficiency['estimated_token_saved']:,} tokens")
    print(f"   效率提升: {efficiency['efficiency_rate']}")
