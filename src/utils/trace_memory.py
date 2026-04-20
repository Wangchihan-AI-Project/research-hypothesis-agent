# -*- coding: utf-8 -*-
"""
带边界限制的文件系统记忆 (Bounded Filesystem Trace Memory)

V6.0 升级强化：
- MAX_SUMMARY_LENGTH: 500 → 100（摘要压缩至100字）
- MAX_FAILURE_REASON_LENGTH: 200 → 100（失败原因压缩至100字）
- MAX_COLLISION_PAPERS: 5 → 3（碰撞文献最多3个）
- enforce_limit() 物理边界强制器

V4.1/V5.0 核心机制（继承）：
- 记录失败案例供PI学习
- 强制边界限制防止Token爆炸
- limit=3 最大读取限制
"""

import os
import json
import threading
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class FailureRecord:
    """失败记录数据结构"""
    timestamp: str
    session_id: str
    hypothesis_summary: str
    failure_reason: str
    collision_papers: List[str]
    hash: str
    domain: Optional[str] = None
    keywords: Optional[List[str]] = None


class BoundedTraceMemory:
    """
    带边界限制的失败追踪记忆

    核心约束：
    - 最大记录数: 100条（防止膨胀）
    - 单条摘要最大字数: 500字
    - 强制读取限制: limit=3（防止Token爆炸）
    - 失败原因最大字数: 200字
    - 碰撞文献最多记录: 5个PMID

    使用场景：
    - PI开题前检阅历史失败案例
    - 避免重复提出已被否决的假说方向
    - 了解哪些领域已有高度同质化研究
    """

    # ==================== V6.0 强化边界约束 ====================
    MAX_RECORDS = 100           # 最大记录数
    MAX_SUMMARY_LENGTH = 100    # V6.0: 摘要压缩至100字（从500降）
    MAX_REASON_LENGTH = 100     # V6.0: 失败原因压缩至100字（从200降）
    MAX_COLLISION_PAPERS = 3    # V6.0: 碰撞文献最多3个PMID（从5降）
    READ_LIMIT = 3              # V6.0: 强制读取限制（不可更改）

    @staticmethod
    def enforce_limit(limit: int) -> int:
        """
        V6.0 物理边界强制器

        任何传入的 limit 参数都会被强制锁定为 3，
        确保不会因参数错误导致 Token 爆炸。

        Args:
            limit: 用户传入的读取限制

        Returns:
            int: 强制锁定后的限制值（最大3）
        """
        return min(limit, BoundedTraceMemory.READ_LIMIT)

    def __init__(self, audit_dir: str = None):
        """
        初始化追踪记忆

        Args:
            audit_dir: 审计日志目录，默认为项目根目录下的 audit_logs
        """
        if audit_dir is None:
            # 默认路径
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            audit_dir = os.path.join(project_root, 'audit_logs')

        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        # 线程锁，防止并发写入冲突
        self._lock = threading.Lock()

        print(f"[TraceMemory] 初始化完成，审计目录: {self.audit_dir}")

    def serialize_failure(
        self,
        hypothesis_summary: str,
        failure_reason: str,
        collision_papers: List[str],
        session_id: str,
        domain: str = None,
        keywords: List[str] = None
    ) -> str:
        """
        序列化失败案例到文件

        Args:
            hypothesis_summary: 假说摘要（将被截断到500字���
            failure_reason: 失败原因（将被截断到200字）
            collision_papers: 碰撞文献PMID列表（将被截断到5个）
            session_id: 会话ID
            domain: 学科领域（可选）
            keywords: 关键词列表（可选）

        Returns:
            str: 写入的文件路径
        """
        # 边界约束：截断处理
        truncated_summary = hypothesis_summary[:self.MAX_SUMMARY_LENGTH]
        truncated_reason = failure_reason[:self.MAX_REASON_LENGTH]
        truncated_papers = collision_papers[:self.MAX_COLLISION_PAPERS]

        # 计算哈希值（用于快速检索）
        hash_value = self._compute_hash(truncated_summary)

        # 构建记录
        record = FailureRecord(
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            hypothesis_summary=truncated_summary,
            failure_reason=truncated_reason,
            collision_papers=truncated_papers,
            hash=hash_value,
            domain=domain,
            keywords=keywords[:10] if keywords else None
        )

        # 生成文件名
        filename = f"failure_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.audit_dir / filename

        # 线程安全写入
        with self._lock:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(asdict(record), f, ensure_ascii=False, indent=2)

        # 强制执行最大记录数限制
        self._enforce_max_records()

        print(f"[TraceMemory] 失败记录已保存: {filepath}")
        return str(filepath)

    def read_past_failures(
        self,
        limit: int = None,
        domain_filter: str = None
    ) -> List[Dict]:
        """
        读取历史失败案例

        V6.0 强化：limit 参数强制锁定为 3，任何大于 3 的值都会被截断。

        Args:
            limit: 读取数量限制（将被强制锁定为3）
            domain_filter: 领域过滤关键词（可选）

        Returns:
            List[Dict]: 失败记录列表（每条已精简）
        """
        # V6.0: 使用物理边界强制器
        actual_limit = self.enforce_limit(limit or self.READ_LIMIT)

        # 按时间倒序读取所有失败文件
        failure_files = sorted(
            self.audit_dir.glob("failure_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )

        records = []
        for filepath in failure_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    record = json.load(f)

                # 领域过滤（如果指定）
                if domain_filter:
                    record_domain = record.get('domain', '')
                    if domain_filter.lower() not in record_domain.lower():
                        continue

                # 精简记录（只保留关键信息）
                simplified_record = {
                    'timestamp': record.get('timestamp', ''),
                    'hypothesis_summary': record.get('hypothesis_summary', '')[:100],  # 进一步精简
                    'failure_reason': record.get('failure_reason', ''),
                    'collision_papers': record.get('collision_papers', []),
                    'domain': record.get('domain', 'unknown')
                }

                records.append(simplified_record)

                # 达到限制数量后停止
                if len(records) >= actual_limit:
                    break

            except Exception as e:
                print(f"[TraceMemory] 读取文件失败: {filepath}, 错误: {e}")
                continue

        print(f"[TraceMemory] 读取 {len(records)} 条历史失败记录 (限制: {actual_limit})")
        return records

    def get_failure_summary(self) -> str:
        """
        获取失败记录摘要（用于PI快速检阅）

        Returns:
            str: 格式化的失败记录摘要
        """
        records = self.read_past_failures()

        if not records:
            return "[TraceMemory] 无历史失败记录"

        summary_lines = [
            "╔══════════════════════════════════════════════════════════════════╗",
            "║              【历史失败案例检阅 - 最多3条】                         ║",
            "╚══════════════════════════════════════════════════════════════════╝",
            ""
        ]

        for i, record in enumerate(records, 1):
            summary_lines.extend([
                f"### 案例 {i}",
                f"**时间**: {record.get('timestamp', 'N/A')[:19]}",
                f"**领域**: {record.get('domain', 'unknown')}",
                f"**失败原因**: {record.get('failure_reason', 'N/A')}",
                f"**假说摘要**: {record.get('hypothesis_summary', 'N/A')}",
                f"**碰撞文献**: {', '.join(record.get('collision_papers', [])) or '无'}",
                ""
            ])

        summary_lines.append("**警示**: 请避免提出类���方向，已被否决。")

        return "\n".join(summary_lines)

    def clear_old_records(self, days: int = 30) -> int:
        """
        清理超过指定天数的旧记录

        Args:
            days: 保留天数

        Returns:
            int: 删除的记录数
        """
        deleted_count = 0
        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)

        for filepath in self.audit_dir.glob("failure_*.json"):
            try:
                if filepath.stat().st_mtime < cutoff_time:
                    filepath.unlink()
                    deleted_count += 1
            except Exception:
                continue

        print(f"[TraceMemory] 清理了 {deleted_count} 条超过 {days} 天的记录")
        return deleted_count

    def _compute_hash(self, text: str) -> str:
        """
        计算文本哈希值（用于快速检索）

        Args:
            text: 输入文本

        Returns:
            str: MD5哈希值（前8位）
        """
        return hashlib.md5(text.encode('utf-8')).hexdigest()[:8]

    def _enforce_max_records(self):
        """
        强制执行最大记录数限制

        当记录数超过MAX_RECORDS时，删除最旧的记录
        """
        all_files = sorted(
            self.audit_dir.glob("failure_*.json"),
            key=lambda f: f.stat().st_mtime
        )

        if len(all_files) > self.MAX_RECORDS:
            # 删除最旧的记录
            for old_file in all_files[:-self.MAX_RECORDS]:
                try:
                    old_file.unlink()
                    print(f"[TraceMemory] 删除旧记录: {old_file}")
                except Exception as e:
                    print(f"[TraceMemory] 删除失败: {e}")


# ==============================================================================
# PI 工具定义
# ==============================================================================

READ_PAST_FAILURES_TOOL = {
    "name": "read_past_failures",
    "description": """读取历史失败案例，避免重复犯相同错误。

    使用场景:
    - 开题前检阅: 避免提出已被否决的假说方向
    - 碰撞预防: 了解哪些领域已有高度同质化研究
    - 经验学习: 从失败案例中吸取教训

    强制约束:
    - 默认读取3条，最多读取3条（防止Token爆炸）
    - 每条记录已精简，仅保留关键信息

    输出:
    - 返回最多3条精简的失败记录
    - 包含: 失败原因、假说摘要、碰撞文献PMID
    """,
    "input_schema": {
        "type": "object",
        "properties": {
            "domain_filter": {
                "type": "string",
                "description": "领域过滤关键词（可选），如 'neuroscience' 或 'ADNI'"
            }
        },
        "required": []
    }
}


def create_read_failures_tool_implementation(trace_memory: BoundedTraceMemory) -> callable:
    """
    创建 read_past_failures 工具实现

    Args:
        trace_memory: BoundedTraceMemory 实例

    Returns:
        callable: 工具实现函数
    """
    def read_past_failures(domain_filter: str = None) -> str:
        """
        执行 read_past_failures 工具

        Args:
            domain_filter: 领域过滤关键词

        Returns:
            str: 格式化的失败记录摘要
        """
        records = trace_memory.read_past_failures(domain_filter=domain_filter)
        return trace_memory.get_failure_summary()

    return read_past_failures


# ==============================================================================
# 全局便捷函数
# ==============================================================================

_global_trace_memory = None


def get_trace_memory() -> BoundedTraceMemory:
    """
    获取全局 TraceMemory 实例（单例模式）

    Returns:
        BoundedTraceMemory 实例
    """
    global _global_trace_memory
    if _global_trace_memory is None:
        _global_trace_memory = BoundedTraceMemory()
    return _global_trace_memory


def serialize_failure(
    hypothesis_summary: str,
    failure_reason: str,
    collision_papers: List[str],
    session_id: str
) -> str:
    """
    全局便捷函数：序列化失败案例

    Args:
        hypothesis_summary: 假说摘要
        failure_reason: 失败原因
        collision_papers: 碰撞文献PMID列表
        session_id: 会话ID

    Returns:
        str: 文件路径
    """
    return get_trace_memory().serialize_failure(
        hypothesis_summary=hypothesis_summary,
        failure_reason=failure_reason,
        collision_papers=collision_papers,
        session_id=session_id
    )


def read_past_failures(limit: int = 3) -> List[Dict]:
    """
    全局便捷函数：读取历史失败案例

    Args:
        limit: 读取数量限制（强制最大3）

    Returns:
        List[Dict]: 失败记录列表
    """
    return get_trace_memory().read_past_failures(limit=limit)