# -*- coding: utf-8 -*-
"""
V7.1 全局迭代绝对熔断器 (Global Iteration Hard-Cap)

在 react_executor 顶层加入全局计数器。
当总模型调用次数达到上限，强制拉闸退出循环。

V7.1 核心修复（TWAFD 漏洞）：
- 随机化 TTL：防止攻击者精确计算时间窗口
- 自适应阈值：根据历史调用模式动态调整
- 滑动窗口计数：使用滑动时间窗口而非固定窗口
- 突发检测：检测异常高频调用并提前熔断

核心机制（继承）：
- 全局 API 调用计数器
- 熔断阈值：15 次（可配置）
- 抛出 ResourceExhaustedError
- 输出降级回复
"""
import threading
import time
import random
import logging
from typing import Dict, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)
from enum import Enum


class FuseState(Enum):
    """熔断器状态"""
    NORMAL = "normal"        # 正常运行
    WARNING = "warning"      # 接近阈值（警告）
    FUSED = "fused"          # 已熔断
    RECOVERING = "recovering" # 恢复中（可选）


@dataclass
class FuseStats:
    """熔断器统计数据"""
    total_api_calls: int = 0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    last_call_time: Optional[datetime] = None
    call_history: list = field(default_factory=list)


class ResourceExhaustedError(Exception):
    """资源耗尽异常"""
    def __init__(self, stats: FuseStats, threshold: int, message: str = None):
        self.stats = stats
        self.threshold = threshold
        self.message = message or self._build_message()
        super().__init__(self.message)



# ==================== V6.1 假设熔断类型 ====================

class HypothesisFuseType(Enum):
    """假设熔断类型"""
    PHYSICAL_VALIDATION = "physical_validation"  # 物理铁闸熔断
    SMILES_INVALID = "smiles_invalid"            # SMILES 非法
    UKB_FIELD_INVALID = "ukb_field_invalid"      # UKB 字段不存在
    COMPUTE_EXCEEDED = "compute_exceeded"        # 算力超限
    VECTOR_SIMILARITY_EXTREME = "vector_extreme"  # 向量相似度极端（洗稿/瞎编）
    RED_TEAM_RIGOR_FAIL = "rigor_fail"           # 红方严谨性熔断


class HypothesisFuseError(Exception):
    """
    假设熔断异常

    当假设评估触发物理铁闸或其他熔断条件时抛出
    """
    def __init__(
        self,
        fuse_type: HypothesisFuseType,
        hypothesis_id: str = None,
        reason: str = None,
        details: Dict = None
    ):
        self.fuse_type = fuse_type
        self.hypothesis_id = hypothesis_id or "unknown"
        self.reason = reason or fuse_type.value
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()
        self.message = self._build_message()
        super().__init__(self.message)

    def _build_message(self) -> str:
        type_messages = {
            HypothesisFuseType.PHYSICAL_VALIDATION: "物理铁闸校验失败",
            HypothesisFuseType.SMILES_INVALID: "SMILES 分子结构非法",
            HypothesisFuseType.UKB_FIELD_INVALID: "UK Biobank 字段不存在",
            HypothesisFuseType.COMPUTE_EXCEEDED: "算力需求超限",
            HypothesisFuseType.VECTOR_SIMILARITY_EXTREME: "向量相似度极端（洗稿/瞎编嫌疑）",
            HypothesisFuseType.RED_TEAM_RIGOR_FAIL: "红方严谨性审查失败"
        }
        type_desc = type_messages.get(self.fuse_type, self.fuse_type.value)

        msg = (
            f"[假设熔断] 类型: {type_desc}\n"
            f"  假设ID: {self.hypothesis_id}\n"
            f"  原因: {self.reason}\n"
            f"  时间: {self.timestamp}"
        )
        if self.details:
            msg += f"\n  详细信息: {self.details}"
        return msg

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'fuse_type': self.fuse_type.value,
            'hypothesis_id': self.hypothesis_id,
            'reason': self.reason,
            'details': self.details,
            'timestamp': self.timestamp,
            'message': self.message
        }


    def _build_message(self) -> str:
        elapsed = datetime.now() - self.stats.start_time
        return (
            f"🚨 全局熔断器触发：API 调用次数已达上限 ({self.stats.total_api_calls}/{self.threshold})\n"
            f"   耗时: {elapsed.total_seconds():.1f}秒 | "
            f"Token消耗: ~{self.stats.total_tokens_used} | "
            f"预估成本: ${self.stats.total_cost_usd:.2f}\n"
            f"   系统已强制退出循环，请检查研究问题复杂度或优化策略。"
        )


class GlobalIterationFuse:
    """
    全局迭代熔断器（线程安全）

    监控：
    1. API 调用次数（主要熔断指标）
    2. Token 消耗估算（辅助指标）
    3. 成本估算（辅助指标）
    """

    # ==================== 熔断阈值配置 ====================
    DEFAULT_HARD_CAP = 15          # 默认硬上限（15次API调用）
    DEFAULT_TOKEN_CAP = 500_000    # Token上限（50万）
    DEFAULT_COST_CAP = 50.0        # 成本上限（$50）
    WARNING_THRESHOLD = 0.8        # 警告阈值比例（80%）

    # ==================== Token 估算系数 ====================
    # 基于 Claude 模型定价估算
    TOKEN_COST_PER_1K = {
        'claude-opus-4-6': {'input': 0.015, 'output': 0.075},
        'claude-opus-4-20250514': {'input': 0.015, 'output': 0.075},
        'claude-sonnet-4-6': {'input': 0.003, 'output': 0.015},
        'claude-haiku-4-5-20251001': {'input': 0.001, 'output': 0.005},
    }

    def __init__(
        self,
        hard_cap: int = DEFAULT_HARD_CAP,
        token_cap: int = DEFAULT_TOKEN_CAP,
        cost_cap: float = DEFAULT_COST_CAP,
        enable_warning: bool = True
    ):
        """
        初始化熔断器

        Args:
            hard_cap: API调用硬上限
            token_cap: Token消耗上限
            cost_cap: 成本上限（USD）
            enable_warning: 是否启用警告阶段
        """
        self.hard_cap = hard_cap
        self.token_cap = token_cap
        self.cost_cap = cost_cap
        self.enable_warning = enable_warning

        # 状态和统计
        self._state = FuseState.NORMAL
        self._stats = FuseStats()

        # 线程锁（确保线程安全）
        self._lock = threading.Lock()

        # 回调函数
        self._warning_callback: Optional[Callable] = None
        self._fuse_callback: Optional[Callable] = None

    def register_callbacks(
        self,
        warning_callback: Callable = None,
        fuse_callback: Callable = None
    ):
        """
        注册回调函数

        Args:
            warning_callback: 警告时触发
            fuse_callback: 熔断时触发
        """
        self._warning_callback = warning_callback
        self._fuse_callback = fuse_callback

    def increment(
        self,
        model: str = 'claude-opus-4-6',
        input_tokens: int = 0,
        output_tokens: int = 0,
        call_metadata: Dict = None
    ) -> FuseState:
        """
        递增计数器（线程安全）

        Args:
            model: 调用的模型名称
            input_tokens: 输入Token数
            output_tokens: 输出Token数
            call_metadata: 调用元数据（可选）

        Returns:
            FuseState: 当前熔断器状态

        Raises:
            ResourceExhaustedError: 当超过硬上限时抛出
        """
        with self._lock:
            # 递增计数
            self._stats.total_api_calls += 1
            self._stats.last_call_time = datetime.now()

            # Token统计
            total_tokens = input_tokens + output_tokens
            self._stats.total_tokens_used += total_tokens

            # 成本估算
            cost_per_1k = self.TOKEN_COST_PER_1K.get(model, {'input': 0.01, 'output': 0.03})
            cost = (input_tokens * cost_per_1k['input'] / 1000 +
                    output_tokens * cost_per_1k['output'] / 1000)
            self._stats.total_cost_usd += cost

            # 记录调用历史（最多保留50条）
            call_record = {
                'call_id': self._stats.total_api_calls,
                'model': model,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost': cost,
                'timestamp': self._stats.last_call_time.isoformat(),
                'metadata': call_metadata or {}
            }
            self._stats.call_history.append(call_record)
            if len(self._stats.call_history) > 50:
                self._stats.call_history = self._stats.call_history[-50:]

            # 检查状态
            new_state = self._check_state()

            # 状态变更处理
            if new_state != self._state:
                old_state = self._state
                self._state = new_state

                if new_state == FuseState.WARNING and self._warning_callback:
                    self._warning_callback(self._stats, self.hard_cap)

                if new_state == FuseState.FUSED:
                    if self._fuse_callback:
                        self._fuse_callback(self._stats, self.hard_cap)
                    # 抛出异常，强制退出循环
                    raise ResourceExhaustedError(self._stats, self.hard_cap)

            return self._state

    def _check_state(self) -> FuseState:
        """检查当前状态"""
        call_ratio = self._stats.total_api_calls / self.hard_cap
        token_ratio = self._stats.total_tokens_used / self.token_cap
        cost_ratio = self._stats.total_cost_usd / self.cost_cap

        # 检查硬上限
        if self._stats.total_api_calls >= self.hard_cap:
            return FuseState.FUSED

        # 检查Token上限
        if self._stats.total_tokens_used >= self.token_cap:
            return FuseState.FUSED

        # 检查成本上限
        if self._stats.total_cost_usd >= self.cost_cap:
            return FuseState.FUSED

        # 检查警告阈值
        if self.enable_warning:
            max_ratio = max(call_ratio, token_ratio, cost_ratio)
            if max_ratio >= self.WARNING_THRESHOLD:
                return FuseState.WARNING

        return FuseState.NORMAL

    def get_state(self) -> FuseState:
        """获取当前状态（线程安全）"""
        with self._lock:
            return self._state

    def get_stats(self) -> FuseStats:
        """获取统计数据（线程安全）"""
        with self._lock:
            return self._stats

    def is_fused(self) -> bool:
        """是否已熔断"""
        return self.get_state() == FuseState.FUSED

    def is_warning(self) -> bool:
        """是否处于警告状态"""
        return self.get_state() == FuseState.WARNING

    def remaining_calls(self) -> int:
        """剩余可用调用次数"""
        with self._lock:
            return max(0, self.hard_cap - self._stats.total_api_calls)

    def reset(self):
        """
        重置熔断器（谨慎使用）

        仅在明确需要重新开始时使用
        """
        with self._lock:
            self._state = FuseState.NORMAL
            self._stats = FuseStats()

    def generate_degradation_response(self) -> str:
        """
        生成降级回复

        当熔断触发时，返回一个友好的降级消息
        """
        stats = self.get_stats()
        elapsed = datetime.now() - stats.start_time

        return """
## ⚠️ 系统资源保护机制触发

由于研究问题复杂度较高，系统已触发全局熔断保护机制。

### 运行统计
- API 调用次数: {calls}/{cap}
- 运行时长: {elapsed:.1f}秒
- Token 消耗: ~{tokens}
- 预估成本: ${cost:.2f}

### 建议
1. **简化研究问题**: 尝试缩小研究范围，聚焦单一核心问题
2. **降低验证标准**: 临时降低假设评分阈值，减少迭代次数
3. **分批执行**: 将复杂研究拆分为多个独立子问题
4. **检查关键词**: 确保研究关键词足够具体，避免过宽泛的搜索

### 当前进度
{progress}

请根据以上建议调整研究策略，重新发起研究请求。
""".format(
            calls=stats.total_api_calls,
            cap=self.hard_cap,
            elapsed=elapsed.total_seconds(),
            tokens=stats.total_tokens_used,
            cost=stats.total_cost_usd,
            progress=self._build_progress_summary()
        )

    def _build_progress_summary(self) -> str:
        """构建进度摘要"""
        history = self._stats.call_history
        if not history:
            return "暂无有效进度记录"

        # 按调用类型分类（基于metadata）
        phases = {}
        for call in history:
            phase = call.get('metadata', {}).get('phase', 'unknown')
            phases[phase] = phases.get(phase, 0) + 1

        summary_parts = []
        for phase, count in phases.items():
            summary_parts.append(f"- {phase}: {count}次调用")

        return "\n".join(summary_parts) if summary_parts else "暂无有效进度记录"


# ==================== 全局熔断器实例 ====================

_global_fuse: Optional[GlobalIterationFuse] = None
_fuse_lock = threading.Lock()

# 默认值常量（全局定义）
FUSE_HARD_CAP_DEFAULT = 15


def get_global_fuse(
    hard_cap: int = None,
    force_new: bool = False
) -> GlobalIterationFuse:
    """
    获取全局熔断器实例

    Args:
        hard_cap: API调用硬上限（默认15）
        force_new: 是否强制创建新实例

    Returns:
        GlobalIterationFuse: 全局熔断器实例
    """
    global _global_fuse

    # 使用默认值如果未指定
    if hard_cap is None:
        hard_cap = FUSE_HARD_CAP_DEFAULT

    with _fuse_lock:
        if _global_fuse is None or force_new:
            _global_fuse = GlobalIterationFuse(hard_cap=hard_cap)
            print(f"[V5.0] 全局熔断器初始化: 硬上限 = {hard_cap} 次 API 调用")

        return _global_fuse


def reset_global_fuse():
    """重置全局熔断器"""
    global _global_fuse
    with _fuse_lock:
        if _global_fuse is not None:
            _global_fuse.reset()
            print("[V5.0] 全局熔断器已重置")


# ==================== V7.1 分布式熔断器（Redis 状态共享 + TWAFD修复） ====================

class DistributedGlobalFuse:
    """
    V7.1 分布式全局熔断器 - Redis 状态共享 + TWAFD漏洞修复

    解决 Celery Worker 状态幽灵问题：
    - Worker 重启后状态丢失
    - 多 Worker 并行时状态分散
    - 无法统计全局 API 调用数

    V7.1 TWAFD漏洞修复：
    - 随机化 TTL：TTL 在基础值 ±30% 范围内随机，防止精确计算
    - 自适应阈值：根据历史调用频率动态调整 hard_cap
    - 滑动窗口计数：60秒滑动窗口内的调用计数
    - 突发检测：短时间内高频调用 → 提前熔断

    使用 Redis WATCH/MULTI/EXEC 事务保证原子性
    """

    REDIS_KEY_PREFIX = "research_agent_fuse_v71:"
    DEFAULT_TTL_BASE = 3600  # 状态过期时间基准（秒）
    DEFAULT_TTL_RANDOM_RANGE = 0.3  # TTL随机范围 ±30%

    # V7.1: 突发检测阈值
    BURST_WINDOW_SECONDS = 60  # 突发检测窗口（60秒）
    BURST_THRESHOLD = 5  # 60秒内超过5次调用 → 突发警告
    BURST_HARD_LIMIT = 8  # 60秒内超过8次调用 → 突发熔断

    # V7.1: 自适应阈值参数
    ADAPTIVE_MIN_CAP = 10  # 自适应最小硬上限
    ADAPTIVE_MAX_CAP = 30  # 自适应最大硬上限
    ADAPTIVE_WINDOW_SIZE = 10  # 用于自适应计算的窗口大小

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        hard_cap: int = 15,
        backend: str = "redis",
        ttl: int = None,
        enable_heartbeat: bool = True,
        enable_random_ttl: bool = True,  # V7.1: 随机TTL开关
        enable_adaptive_threshold: bool = True,  # V7.1: 自适应阈值开关
        enable_burst_detection: bool = True  # V7.1: 突发检测开关
    ):
        """
        初始化分布式熔断器

        V7.1 TWAFD修复新增参数：
        - enable_random_ttl: 是否启用随机化TTL
        - enable_adaptive_threshold: 是否启用自适应阈值
        - enable_burst_detection: 是否启用突发检测

        Args:
            redis_url: Redis 连接 URL
            hard_cap: API调用硬上限
            backend: 后端类型 ("redis" 或 "memory")
            ttl: 状态过期时间（秒）
            enable_heartbeat: 是否启用心跳续期
        """
        self.hard_cap_base = hard_cap  # 基准硬上限
        self.hard_cap = hard_cap  # 当前硬上限（可能被自适应调整）
        self.backend = backend
        self.enable_heartbeat = enable_heartbeat
        self.enable_random_ttl = enable_random_ttl
        self.enable_adaptive_threshold = enable_adaptive_threshold
        self.enable_burst_detection = enable_burst_detection

        # V7.1: 计算随机化 TTL
        if ttl is None:
            ttl = self._calculate_random_ttl()
        self.ttl = ttl

        self._warning_threshold = hard_cap * 0.8

        # V7.1: 滑动窗口调用历史（内存缓存）
        self._call_timestamps: deque = deque(maxlen=100)  # 最近100次调用时间戳
        self._burst_window_calls: deque = deque(maxlen=50)  # 突发检测窗口内的调用

        # V7.1: 心跳线程控制
        self._heartbeat_running = False
        self._heartbeat_thread: Optional[threading.Thread] = None

        if backend == "redis":
            try:
                import redis
                self.redis_client = redis.from_url(redis_url)
                self._ensure_redis_keys()

                # V7.1 核心修复：启动心跳续期线程
                if enable_heartbeat:
                    self._start_heartbeat_thread()

                logger.info(
                    f"[V7.1] 分布式熔断器初始化完成\n"
                    f"  Redis模式, 基准硬上限={hard_cap}\n"
                    f"  随机TTL={ttl}秒 (随机化={enable_random_ttl})\n"
                    f"  自适应阈值={enable_adaptive_threshold}\n"
                    f"  突发检测={enable_burst_detection}\n"
                    f"  心跳续期={enable_heartbeat}"
                )
            except ImportError:
                logger.warning("[V7.1] Redis 未安装，回退到内存模式")
                self.backend = "memory"
                self._local_stats = FuseStats()
                self._lock = threading.Lock()
            except Exception as e:
                logger.warning(f"[V7.1] Redis 连接失败: {e}, 回退到内存模式")
                self.backend = "memory"
                self._local_stats = FuseStats()
                self._lock = threading.Lock()
        else:
            # 回退到内存模式
            self._local_stats = FuseStats()
            self._lock = threading.Lock()
            logger.info(f"[V7.1] 熔断器初始化: 内存模式, 硬上限={hard_cap}")

    def _calculate_random_ttl(self) -> int:
        """
        V7.1 计算随机化 TTL

        核心：TTL 在基础值 ±30% 范围内随机
        防止攻击者精确计算 TTL 过期时间

        Returns:
            int: 随机化的 TTL 值
        """
        if not self.enable_random_ttl:
            return self.DEFAULT_TTL_BASE

        base_ttl = self.DEFAULT_TTL_BASE
        random_range = self.DEFAULT_TTL_RANDOM_RANGE

        # 计算 TTL 范围
        min_ttl = int(base_ttl * (1 - random_range))
        max_ttl = int(base_ttl * (1 + random_range))

        # 随机选择
        random_ttl = random.randint(min_ttl, max_ttl)

        logger.debug(f"[V7.1] 随机TTL计算: {random_ttl}秒 (范围: {min_ttl}-{max_ttl})")
        return random_ttl

    def _check_burst_detection(self) -> Tuple[bool, str]:
        """
        V7.1 突发检测

        检测短时间内的高频调用：
        - 60秒内 > 5次 → 突发警告
        - 60秒内 > 8次 → 突发熔断

        Returns:
            Tuple[是否触发, 原因]
        """
        if not self.enable_burst_detection:
            return False, ""

        now = datetime.now()
        burst_window_start = now - timedelta(seconds=self.BURST_WINDOW_SECONDS)

        # 清理过期的时间戳
        while self._burst_window_calls and self._burst_window_calls[0] < burst_window_start:
            self._burst_window_calls.popleft()

        burst_count = len(self._burst_window_calls)

        if burst_count >= self.BURST_HARD_LIMIT:
            return True, f"突发熔断：{self.BURST_WINDOW_SECONDS}秒内{burst_count}次调用"

        if burst_count >= self.BURST_THRESHOLD:
            return False, f"突发警告：{self.BURST_WINDOW_SECONDS}秒内{burst_count}次调用"

        return False, ""

    def _update_adaptive_threshold(self) -> int:
        """
        V7.1 自适应阈值更新

        根据历史调用频率动态调整 hard_cap：
        - 高频调用场景 → 降低阈值（更严格）
        - 低频调用场景 → 提高阈值（更宽松）

        Returns:
            int: 新的 hard_cap 值
        """
        if not self.enable_adaptive_threshold:
            return self.hard_cap_base

        # 检查是否有足够的历史数据
        if len(self._call_timestamps) < self.ADAPTIVE_WINDOW_SIZE:
            return self.hard_cap_base

        # 计算平均调用间隔
        recent_timestamps = list(self._call_timestamps)[-self.ADAPTIVE_WINDOW_SIZE:]
        intervals = []

        for i in range(1, len(recent_timestamps)):
            interval = (recent_timestamps[i] - recent_timestamps[i-1]).total_seconds()
            intervals.append(interval)

        avg_interval = sum(intervals) / len(intervals) if intervals else 60

        # 根据调用间隔调整阈值
        if avg_interval < 10:  # 高频调用（每10秒一次）
            # 降低阈值
            new_cap = max(self.ADAPTIVE_MIN_CAP, int(self.hard_cap_base * 0.7))
            reason = "高频调用场景"
        elif avg_interval > 60:  # 低频调用（每60秒一次）
            # 提高阈值
            new_cap = min(self.ADAPTIVE_MAX_CAP, int(self.hard_cap_base * 1.3))
            reason = "低频调用场景"
        else:
            # 正常频率
            new_cap = self.hard_cap_base
            reason = "正常频率"

        logger.debug(f"[V7.1] 自适应阈值: {new_cap} ({reason}, 平均间隔={avg_interval:.1f}秒)")
        return new_cap

    def _ensure_redis_keys(self):
        """确保 Redis 键存在"""
        try:
            if not self.redis_client.exists(self.REDIS_KEY_PREFIX + "calls"):
                self.redis_client.set(self.REDIS_KEY_PREFIX + "calls", 0)
                self.redis_client.expire(self.REDIS_KEY_PREFIX + "calls", self.ttl)

            if not self.redis_client.exists(self.REDIS_KEY_PREFIX + "tokens"):
                self.redis_client.set(self.REDIS_KEY_PREFIX + "tokens", 0)
                self.redis_client.expire(self.REDIS_KEY_PREFIX + "tokens", self.ttl)

            if not self.redis_client.exists(self.REDIS_KEY_PREFIX + "cost"):
                self.redis_client.set(self.REDIS_KEY_PREFIX + "cost", 0.0)
                self.redis_client.expire(self.REDIS_KEY_PREFIX + "cost", self.ttl)

            if not self.redis_client.exists(self.REDIS_KEY_PREFIX + "start_time"):
                self.redis_client.set(
                    self.REDIS_KEY_PREFIX + "start_time",
                    datetime.now().isoformat()
                )
                self.redis_client.expire(self.REDIS_KEY_PREFIX + "start_time", self.ttl)
        except Exception as e:
            print(f"[V7.1] Redis 键初始化失败: {e}")

    # ==================== V7.1 核心修复：心跳续期 ====================

    def _start_heartbeat_thread(self):
        """
        V7.1 启动心跳续期线程

        解决问题：
        - Redis TTL 过期后状态丢失
        - Worker 重启后状态不一致

        解决方案：
        - 每 TTL/3 秒检查并续期
        - 使用分布式锁保证原子性
        """
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="fuse_heartbeat"
        )
        self._heartbeat_thread.start()
        logger.info("[V7.1] 心跳续期线程已启动")

    def _stop_heartbeat_thread(self):
        """停止心跳线程"""
        self._heartbeat_running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        logger.info("[V7.1] 心跳续期线程已停止")

    def _heartbeat_loop(self):
        """
        V7.1 心跳续期循环

        核心逻辑：
        - 每 TTL/3 秒检查 Redis 键 TTL
        - 如果 TTL < TTL/2，自动续期
        - 使用分布式锁防止并发续期
        - V7.1 TWAFD修复：续期时使用新的随机TTL
        """
        heartbeat_interval = self.ttl / 3

        while self._heartbeat_running:
            try:
                time.sleep(heartbeat_interval)

                if not self._heartbeat_running:
                    break

                # 使用分布式锁进行续期
                with self._acquire_distributed_lock(timeout=5) as lock_acquired:
                    if lock_acquired:
                        self._renew_ttl_if_needed()
                    else:
                        logger.warning("[V7.1] 心跳续期：无法获取分布式锁")

            except Exception as e:
                logger.warning(f"[V7.1] 心跳续期异常: {e}")
                time.sleep(5)  # 异常后等待再重试

    def _renew_ttl_if_needed(self):
        """
        V7.1 检查并续期 TTL（带随机化）

        如果 TTL 即将过期，自动续期到新的随机 TTL
        核心改进：每次续期使用新的随机值，防止攻击者预测
        """
        try:
            # V7.1: 计算新的随机 TTL
            new_ttl = self._calculate_random_ttl()

            keys_to_check = ["calls", "tokens", "cost", "start_time"]

            for key in keys_to_check:
                full_key = self.REDIS_KEY_PREFIX + key
                current_ttl = self.redis_client.ttl(full_key)

                # 如果 TTL < TTL/2 或 TTL == -1（无过期），续期
                if current_ttl < self.ttl / 2 or current_ttl == -1:
                    # V7.1 TWAFD修复：使用新的随机 TTL
                    self.redis_client.expire(full_key, new_ttl)
                    logger.debug(f"[V7.1] TTL 续期: {key}, 新TTL={new_ttl}秒 (随机化)")

            # 更新本地 TTL 变量
            self.ttl = new_ttl

        except Exception as e:
            logger.warning(f"[V7.1] TTL 续期失败: {e}")

    def _acquire_distributed_lock(self, timeout: int = 10):
        """
        V7.1 获取分布式锁

        使用 Redis SET NX EX 原子获取锁

        Args:
            timeout: 锁持有时间（秒）

        Returns:
            DistributedLockContext: 锁上下文管理器
        """
        lock_key = self.REDIS_KEY_PREFIX + "lock"
        return DistributedLockContext(
            redis_client=self.redis_client,
            lock_key=lock_key,
            timeout=timeout
        )

    def increment(
        self,
        model: str = 'claude-opus-4-6',
        input_tokens: int = 0,
        output_tokens: int = 0,
        call_metadata: Dict = None
    ) -> FuseState:
        """
        V7.1 递增计数器（原子性操作 + TWAFD修复）

        新增逻辑：
        1. 滑动窗口更新：记录调用时间戳
        2. 突发检测：检查短时间内高频调用
        3. 自适应阈值：根据历史频率动态调整 hard_cap

        Args:
            model: 调用的模型名称
            input_tokens: 输入Token数
            output_tokens: 输出Token数
            call_metadata: 调用元数据（可选）

        Returns:
            FuseState: 当前熔断器状态

        Raises:
            ResourceExhaustedError: 当超过硬上限或突发熔断时抛出
        """
        now = datetime.now()

        # V7.1: 更新滑动窗口
        self._call_timestamps.append(now)
        self._burst_window_calls.append(now)

        # V7.1: 突发检测
        burst_triggered, burst_reason = self._check_burst_detection()
        if burst_triggered:
            stats = self._get_redis_stats() if self.backend == "redis" else self._local_stats
            logger.warning(f"[V7.1 TWAFD] 突发熔断触发: {burst_reason}")
            raise ResourceExhaustedError(stats, self.hard_cap, message=burst_reason)

        if burst_reason:  # 突发警告
            logger.warning(f"[V7.1 TWAFD] 突发警告: {burst_reason}")

        # V7.1: 自适应阈值更新
        self.hard_cap = self._update_adaptive_threshold()

        # 原有递增逻辑
        if self.backend == "redis":
            return self._increment_redis(model, input_tokens, output_tokens, call_metadata)
        else:
            return self._increment_memory(model, input_tokens, output_tokens, call_metadata)

    def _increment_redis(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        call_metadata: Dict
    ) -> FuseState:
        """
        Redis 事务递增

        使用 WATCH/MULTI/EXEC 确保原子性
        """
        import redis

        calls_key = self.REDIS_KEY_PREFIX + "calls"
        tokens_key = self.REDIS_KEY_PREFIX + "tokens"
        cost_key = self.REDIS_KEY_PREFIX + "cost"

        # 计算成本
        cost_per_1k = GlobalIterationFuse.TOKEN_COST_PER_1K.get(
            model, {'input': 0.01, 'output': 0.03}
        )
        call_cost = (
            input_tokens * cost_per_1k['input'] / 1000 +
            output_tokens * cost_per_1k['output'] / 1000
        )

        max_retries = 10
        for retry in range(max_retries):
            try:
                # WATCH 监听键变化
                self.redis_client.watch(calls_key)

                current_calls = int(self.redis_client.get(calls_key) or 0)

                # 检查是否已达上限
                if current_calls >= self.hard_cap:
                    self.redis_client.unwatch()
                    stats = self._get_redis_stats()
                    raise ResourceExhaustedError(stats, self.hard_cap)

                # MULTI 事务
                pipe = self.redis_client.pipeline()
                pipe.multi()
                pipe.incr(calls_key)
                pipe.incrbyfloat(tokens_key, input_tokens + output_tokens)
                pipe.incrbyfloat(cost_key, call_cost)
                pipe.execute()

                self.redis_client.unwatch()
                break

            except redis.WatchError:
                # 键被其他进程修改，重试
                if retry < max_retries - 1:
                    continue
                else:
                    # 最后一次重试失败，获取当前状态
                    self.redis_client.unwatch()
                    current_calls = int(self.redis_client.get(calls_key) or 0)
                    if current_calls >= self.hard_cap:
                        stats = self._get_redis_stats()
                        raise ResourceExhaustedError(stats, self.hard_cap)
                    break

            except Exception as e:
                self.redis_client.unwatch()
                logger.warning(f"[V7.1] Redis 操作失败: {e}")
                break

        # 返回状态
        return self._check_state_redis()

    def _increment_memory(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        call_metadata: Dict
    ) -> FuseState:
        """内存模式递增（回退）"""
        with self._lock:
            self._local_stats.total_api_calls += 1
            self._local_stats.total_tokens_used += input_tokens + output_tokens

            # 成本估算
            cost_per_1k = GlobalIterationFuse.TOKEN_COST_PER_1K.get(
                model, {'input': 0.01, 'output': 0.03}
            )
            call_cost = (
                input_tokens * cost_per_1k['input'] / 1000 +
                output_tokens * cost_per_1k['output'] / 1000
            )
            self._local_stats.total_cost_usd += call_cost

            # 检查状态
            return self._check_state_memory()

    def _check_state_redis(self) -> FuseState:
        """检查 Redis 状态"""
        calls = int(self.redis_client.get(self.REDIS_KEY_PREFIX + "calls") or 0)

        if calls >= self.hard_cap:
            return FuseState.FUSED

        if calls >= self._warning_threshold:
            return FuseState.WARNING

        return FuseState.NORMAL

    def _check_state_memory(self) -> FuseState:
        """检查内存状态"""
        calls = self._local_stats.total_api_calls

        if calls >= self.hard_cap:
            return FuseState.FUSED

        if calls >= self._warning_threshold:
            return FuseState.WARNING

        return FuseState.NORMAL

    def get_state(self) -> FuseState:
        """获取当前状态"""
        if self.backend == "redis":
            return self._check_state_redis()
        else:
            return self._check_state_memory()

    def get_stats(self) -> FuseStats:
        """获取统计数据"""
        if self.backend == "redis":
            return self._get_redis_stats()
        else:
            return self._local_stats

    def _get_redis_stats(self) -> FuseStats:
        """从 Redis 获取统计数据"""
        stats = FuseStats()
        try:
            stats.total_api_calls = int(
                self.redis_client.get(self.REDIS_KEY_PREFIX + "calls") or 0
            )
            stats.total_tokens_used = int(
                self.redis_client.get(self.REDIS_KEY_PREFIX + "tokens") or 0
            )
            stats.total_cost_usd = float(
                self.redis_client.get(self.REDIS_KEY_PREFIX + "cost") or 0.0
            )

            start_time_str = self.redis_client.get(self.REDIS_KEY_PREFIX + "start_time")
            if start_time_str:
                try:
                    stats.start_time = datetime.fromisoformat(start_time_str.decode())
                except Exception:
                    stats.start_time = datetime.now()

            stats.last_call_time = datetime.now()
        except Exception as e:
            logger.warning(f"[V7.1] Redis 获取统计失败: {e}")

        return stats

    def is_fused(self) -> bool:
        """是否已熔断"""
        return self.get_state() == FuseState.FUSED

    def is_warning(self) -> bool:
        """是否处于警告状态"""
        return self.get_state() == FuseState.WARNING

    def remaining_calls(self) -> int:
        """剩余可用调用次数"""
        if self.backend == "redis":
            current = int(self.redis_client.get(self.REDIS_KEY_PREFIX + "calls") or 0)
        else:
            current = self._local_stats.total_api_calls
        return max(0, self.hard_cap - current)

    def reset(self):
        """重置熔断器"""
        if self.backend == "redis":
            try:
                self.redis_client.set(self.REDIS_KEY_PREFIX + "calls", 0)
                self.redis_client.set(self.REDIS_KEY_PREFIX + "tokens", 0)
                self.redis_client.set(self.REDIS_KEY_PREFIX + "cost", 0.0)
                self.redis_client.set(
                    self.REDIS_KEY_PREFIX + "start_time",
                    datetime.now().isoformat()
                )
                # 重置 TTL（使用新的随机值）
                new_ttl = self._calculate_random_ttl()
                for key in ["calls", "tokens", "cost", "start_time"]:
                    self.redis_client.expire(self.REDIS_KEY_PREFIX + key, new_ttl)
                self.ttl = new_ttl
                logger.info("[V7.1] 分布式熔断器已重置")
            except Exception as e:
                logger.warning(f"[V7.1] Redis 重置失败: {e}")
        else:
            with self._lock:
                self._local_stats = FuseStats()
            logger.info("[V7.1] 内存熔断器已重置")

        # 清空滑动窗口
        self._call_timestamps.clear()
        self._burst_window_calls.clear()

    def generate_degradation_response(self) -> str:
        """生成降级回复"""
        stats = self.get_stats()
        elapsed = datetime.now() - stats.start_time

        return """
## ⚠️ 系统资源保护机制触发（V7.1 TWAFD修复版）

由于研究问题复杂度较高，系统已触发全局熔断保护机制。

### 运行统计
- API 调用次数: {calls}/{cap}
- 运行时长: {elapsed:.1f}秒
- Token 消耗: ~{tokens}
- 预估成本: ${cost:.2f}
- 熔断器模式: {backend}
- 当前TTL: {ttl}秒（随机化）

### 建议
1. **简化研究问题**: 尝试缩小研究范围，聚焦单一核心问题
2. **降低验证标准**: 临时降低假设评分阈值，减少迭代次数
3. **分批执行**: 将复杂研究拆分为多个独立子问题
4. **检查关键词**: 确保研究关键词足够具体，避免过宽泛的搜索

请根据以上建议调整研究策略，重新发起研究请求。
""".format(
            calls=stats.total_api_calls,
            cap=self.hard_cap,
            elapsed=elapsed.total_seconds(),
            tokens=stats.total_tokens_used,
            cost=stats.total_cost_usd,
            backend=self.backend,
            ttl=self.ttl
        )


class DistributedLockContext:
    """
    V7.1 分布式锁上下文管理器

    使用 Redis SET NX EX 实现分布式锁
    """

    def __init__(self, redis_client, lock_key: str, timeout: int = 10):
        """
        初始化分布式锁

        Args:
            redis_client: Redis 客户端
            lock_key: 锁键名
            timeout: 锁超时时间（秒）
        """
        self.redis_client = redis_client
        self.lock_key = lock_key
        self.timeout = timeout
        self.lock_value = f"locked_{datetime.now().isoformat()}"
        self._acquired = False

    def __enter__(self):
        """尝试获取锁"""
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                # SET NX EX 原子获取锁
                self._acquired = self.redis_client.set(
                    self.lock_key,
                    self.lock_value,
                    nx=True,
                    ex=self.timeout
                )
                if self._acquired:
                    return True

                # 等待后重试
                time.sleep(0.5)

            except Exception as e:
                logger.warning(f"[分布式锁] 获取失败 (尝试 {attempt + 1}): {e}")
                time.sleep(0.5)

        return False

    def __exit__(self, exc_type, exc_val, exc_tb):
        """释放锁"""
        if self._acquired:
            try:
                # 安全释放：检查锁值是否匹配
                current_value = self.redis_client.get(self.lock_key)
                if current_value and current_value.decode() == self.lock_value:
                    self.redis_client.delete(self.lock_key)
            except Exception as e:
                logger.warning(f"[分布式锁] 释放失败: {e}")

        return False  # 不抑制异常


# ==================== 分布式熔断器全局实例 ====================

_distributed_fuse: Optional[DistributedGlobalFuse] = None
_distributed_fuse_lock = threading.Lock()


def get_distributed_fuse(
    redis_url: str = None,
    hard_cap: int = None,
    backend: str = "redis",
    force_new: bool = False
) -> DistributedGlobalFuse:
    """
    获取分布式熔断器实例

    Args:
        redis_url: Redis 连接 URL（默认从配置读取）
        hard_cap: API调用硬上限（默认15）
        backend: 后端类型 ("redis" 或 "memory")
        force_new: 是否强制创建新实例

    Returns:
        DistributedGlobalFuse: 分布式熔断器实例
    """
    global _distributed_fuse

    # 尝试从配置读取默认值
    if redis_url is None or hard_cap is None:
        try:
            from core.program_config import get_current_config
            config = get_current_config()
            if redis_url is None:
                redis_url = config.async_tasks.redis_url
            if hard_cap is None:
                hard_cap = config.defense_layer.hard_cap
        except Exception:
            if redis_url is None:
                redis_url = "redis://localhost:6379/0"
            if hard_cap is None:
                hard_cap = FUSE_HARD_CAP_DEFAULT

    with _distributed_fuse_lock:
        if _distributed_fuse is None or force_new:
            _distributed_fuse = DistributedGlobalFuse(
                redis_url=redis_url,
                hard_cap=hard_cap,
                backend=backend
            )
        return _distributed_fuse


def reset_distributed_fuse():
    """重置分布式熔断器"""
    global _distributed_fuse
    with _distributed_fuse_lock:
        if _distributed_fuse is not None:
            _distributed_fuse.reset()


# ==================== 便捷装饰器 ====================

def with_fuse_protection(model: str = 'claude-opus-4-6'):
    """
    熔断保护装饰器

    用于保护可能触发大量 API 调用的函数

    Usage:
        @with_fuse_protection('claude-opus-4-6')
        def my_llm_function():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            fuse = get_global_fuse()

            # 检查是否已熔断
            if fuse.is_fused():
                raise ResourceExhaustedError(
                    fuse.get_stats(),
                    fuse.hard_cap
                )

            # 执行函数
            result = func(*args, **kwargs)

            # 递增计数（假设每次调用约2000 input + 1000 output）
            # 实际使用时应在函数内部精确统计
            fuse.increment(
                model=model,
                input_tokens=2000,
                output_tokens=1000,
                call_metadata={'function': func.__name__}
            )

            return result

        return wrapper
    return decorator


# ==================== 测试用例 ====================

if __name__ == '__main__':
    print("=" * 60)
    print("V5.0 全局迭代熔断器 - 测试用例")
    print("=" * 60)

    # 创建熔断器（测试用小阈值）
    fuse = GlobalIterationFuse(hard_cap=5, enable_warning=True)

    # 注册回调
    def on_warning(stats, cap):
        print(f"⚠️ 警告: 已调用 {stats.total_api_calls}/{cap} 次")

    def on_fuse(stats, cap):
        print(f"🚨 熔断触发: 已调用 {stats.total_api_calls}/{cap} 次")

    fuse.register_callbacks(on_warning=on_warning, fuse_callback=on_fuse)

    # 模拟调用
    print("\n模拟 API 调用...")
    for i in range(10):
        try:
            state = fuse.increment(
                model='claude-opus-4-6',
                input_tokens=1000,
                output_tokens=500
            )
            print(f"  调用 {i+1}: 状态={state.value}")

        except ResourceExhaustedError as e:
            print(f"\n{e.message}")
            print("\n降级回复:")
            print(fuse.generate_degradation_response())
            break

    # 最终统计
    stats = fuse.get_stats()
    print(f"\n最终统计:")
    print(f"  总调用: {stats.total_api_calls}")
    print(f"  总Token: {stats.total_tokens_used}")
    print(f"  总成本: ${stats.total_cost_usd:.2f}")

    print("\n" + "=" * 60)
    print("测试完成")