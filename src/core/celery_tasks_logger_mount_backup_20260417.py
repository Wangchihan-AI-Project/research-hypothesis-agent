# -*- coding: utf-8 -*-
"""
V7.1 Celery 异步任务分发系统 - 集中式日志挂载版

V7.1 核心改进：
1. 集中式日志系统挂载：所有日志写入 logs/system_v7.log
2. Task ID 贯穿注入：格式 [TaskID: xxx] [Agent: xxx]
3. 深水区异常堆栈捕获：exc_info=True 自动捕获 traceback
4. 业务审计流隔离：ERROR (系统Bug) vs AUDIT (业务驳回)
"""

from celery import Celery, Task
from celery.result import AsyncResult
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
from typing import Dict, Optional, List, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import os
import sys
import traceback

# ==================== V7.1: 集中式日志挂载 ====================
from src.utils.logger import (
    get_central_logger,
    TaskLogContext,
    log_exceptions,
    AUDIT_LEVEL
)

# 获取集中式日志实例
logger = get_central_logger()

# ==================== V6.1 关键改进：禁止模块顶层实例化配置 ====================
# 旧版代码（已废弃）：
#   config = _get_config()  # 模块顶层实例化 → Celery 状态幽灵
#   REDIS_URL = config.get_redis_url()
#
# 新版代码（V6.1）：
#   任务入口第一行调用 get_current_config()
#   每次任务执行时动态拉取最新配置


# ==================== Pydantic 配置模型导入 ====================
def _import_config_module():
    """
    延迟导入配置模块（避免循环依赖）
    """
    try:
        from src.core.program_config import get_current_config, PYDANTIC_AVAILABLE
        return get_current_config, PYDANTIC_AVAILABLE
    except ImportError as e:
        logger.critical(f"[Celery] 配置模块导入失败: {e}")
        return None, False


# ==================== 默认值常量（仅作为极端回退） ====================
# 当 Pydantic 配置完全无法加载时使用
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_SOFT_TIME_LIMIT = 300
DEFAULT_HARD_TIME_LIMIT = 600
DEFAULT_MAX_RETRIES = 3
DEFAULT_WEBHOOK_TIMEOUT = 30


# ==================== Celery 应用实例（延迟初始化） ====================
_celery_app: Optional[Celery] = None
_celery_lock = None  # 延迟初始化


def get_celery_app() -> Celery:
    """
    获取 Celery 应用实例（延迟初始化）

    使用 get_current_config() 拉取最新配置参数

    Returns:
        Celery: Celery 应用实例
    """
    global _celery_app, _celery_lock

    if _celery_lock is None:
        import threading
        _celery_lock = threading.Lock()

    if _celery_app is None:
        with _celery_lock:
            if _celery_app is None:
                # V6.1: 调用 get_current_config() 获取最新配置
                get_current_config, pydantic_ok = _import_config_module()

                if get_current_config is not None:
                    config = get_current_config(force_reload=True)
                    redis_url = os.getenv('REDIS_URL', config.async_tasks.redis_url)
                    soft_limit = int(os.getenv('TASK_SOFT_TIME_LIMIT', str(config.async_tasks.task_soft_time_limit)))
                    hard_limit = int(os.getenv('TASK_HARD_TIME_LIMIT', str(config.async_tasks.task_hard_time_limit)))
                    max_retries = int(os.getenv('TASK_MAX_RETRIES', str(config.async_tasks.task_max_retries)))
                    webhook_timeout = int(os.getenv('WEBHOOK_TIMEOUT', str(config.async_tasks.webhook_timeout)))

                    logger.info(
                        f"[Celery V6.1] 配置从 Pydantic 模型加载:\n"
                        f"  Redis: {redis_url}\n"
                        f"  Soft Timeout: {soft_limit}s\n"
                        f"  Hard Timeout: {hard_limit}s\n"
                        f"  Pydantic: {pydantic_ok}"
                    )
                else:
                    # 回退到默认值
                    redis_url = os.getenv('REDIS_URL', DEFAULT_REDIS_URL)
                    soft_limit = int(os.getenv('TASK_SOFT_TIME_LIMIT', str(DEFAULT_SOFT_TIME_LIMIT)))
                    hard_limit = int(os.getenv('TASK_HARD_TIME_LIMIT', str(DEFAULT_HARD_TIME_LIMIT)))
                    max_retries = int(os.getenv('TASK_MAX_RETRIES', str(DEFAULT_MAX_RETRIES)))
                    webhook_timeout = int(os.getenv('WEBHOOK_TIMEOUT', str(DEFAULT_WEBHOOK_TIMEOUT)))

                    logger.critical(
                        f"[Celery V6.1] Pydantic 配置加载失败，使用默认值:\n"
                        f"  Redis: {redis_url}\n"
                        f"  Soft Timeout: {soft_limit}s\n"
                        f"  Hard Timeout: {hard_limit}s"
                    )

                # 创建 Celery 应用
                _celery_app = Celery(
                    'research_hypothesis_agent_v61',
                    broker=redis_url,
                    backend=redis_url,
                    includes=['src.core.celery_tasks'],
                )

                # Celery 配置
                _celery_app.conf.update(
                    task_serializer='json',
                    accept_content=['json'],
                    result_serializer='json',
                    timezone='Asia/Shanghai',
                    enable_utc=True,
                    task_soft_time_limit=soft_limit,
                    task_time_limit=hard_limit,
                    task_max_retries=max_retries,
                    task_default_retry_delay=60,
                    task_acks_late=True,
                    task_reject_on_worker_lost=True,
                    result_expires=3600,
                    result_backend_transport_options={'max_connections': 50},
                    worker_prefetch_multiplier=1,
                    worker_max_tasks_per_child=100,
                    broker_pool_limit=10,
                    broker_connection_max_retry=5,
                )

    return _celery_app


# 为了兼容旧代码，提供 celery_app 别名（将在模块末尾重新定义）
celery_app = None  # 临时占位，后续会被真实实例覆盖


# ==================== 任务状态枚举 ====================

class TaskState(Enum):
    """任务状态"""
    PENDING = "pending"
    STARTED = "started"
    PROGRESS = "progress"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"
    TIMEOUT = "timeout"


# ==================== 任务结果数据类 ====================

@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str
    state: TaskState
    result_type: str
    payload: Dict = field(default_factory=dict)
    error: Optional[str] = None
    traceback: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration: Optional[float] = None
    api_calls_used: int = 0
    tokens_used: int = 0
    progress: Optional[int] = None
    progress_message: Optional[str] = None
    config_version: Optional[str] = None  # V6.1 新增：记录使用的配置版本

    def to_dict(self) -> Dict:
        return {
            'task_id': self.task_id,
            'state': self.state.value,
            'result_type': self.result_type,
            'payload': self.payload,
            'error': self.error,
            'traceback': self.traceback,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'api_calls_used': self.api_calls_used,
            'tokens_used': self.tokens_used,
            'progress': self.progress,
            'progress_message': self.progress_message,
            'config_version': self.config_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class WebhookPayload:
    """Webhook 回调数据包"""
    task_id: str
    task_type: str
    state: TaskState
    result: Dict
    timestamp: str
    signature: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'state': self.state.value,
            'result': self.result,
            'timestamp': self.timestamp,
            'signature': self.signature,
        }


# ==================== 进度跟踪基类 ====================

class ProgressTrackingTask(Task):
    """带进度跟踪的任务基类"""

    def update_progress(self, progress: int, message: str = None):
        self.update_state(
            state='PROGRESS',
            meta={
                'progress': progress,
                'message': message or f'执行进度: {progress}%',
                'timestamp': datetime.now().isoformat(),
            }
        )
        logger.info(f"[Task {self.request.id}] Progress: {progress}% - {message}")


# ==================== Webhook 发送器 ====================

class WebhookSender:
    """Webhook 回调发送器"""

    def __init__(self, timeout: int = DEFAULT_WEBHOOK_TIMEOUT):
        self.timeout = timeout

    def send(self, webhook_url: str, payload: WebhookPayload) -> bool:
        if not webhook_url:
            logger.warning("Webhook URL not provided, skipping callback")
            return False

        try:
            import requests
            response = requests.post(
                webhook_url,
                json=payload.to_dict(),
                timeout=self.timeout,
                headers={
                    'Content-Type': 'application/json',
                    'X-Task-ID': payload.task_id,
                }
            )

            if response.status_code in [200, 201, 202]:
                logger.info(f"[Webhook] Successfully sent to {webhook_url}")
                return True
            else:
                logger.warning(f"[Webhook] Failed with status {response.status_code}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"[Webhook] Error: {e}")
            return False


# 全局 Webhook 发送器（延迟初始化）
_webhook_sender: Optional[WebhookSender] = None


def get_webhook_sender() -> WebhookSender:
    """获取 Webhook 发送器实例"""
    global _webhook_sender
    if _webhook_sender is None:
        # V6.1: 从配置获取 timeout
        get_current_config, _ = _import_config_module()
        if get_current_config is not None:
            config = get_current_config()
            timeout = config.async_tasks.webhook_timeout
        else:
            timeout = DEFAULT_WEBHOOK_TIMEOUT
        _webhook_sender = WebhookSender(timeout=timeout)
    return _webhook_sender


# ==================== 核心任务定义 ====================

def _create_task_decorator():
    """
    创建任务装饰器（延迟绑定 Celery app）
    """
    app = get_celery_app()
    return app.task


# ==================== V6.1 主任务：假设生成 ====================

def hypothesis_generation_task_impl(
    self: ProgressTrackingTask,
    user_input: str,
    user_domain: str = None,
    webhook_url: str = None,
    session_id: str = None,
    **kwargs
) -> Dict:
    """
    主任务实现：假设生成全流程 (V7.1)

    V7.1 核心改进：
    1. Task ID 贯穿注入：使用 TaskLogContext 自动注入日志上下文
    2. 深水区异常捕获：网络请求、验证、打分等关键节点记录完整堆栈
    3. AUDIT 级别日志：红方驳回、验证失败等业务决策单独记录

    流程：
    1. TaskLogContext 进入（注入 Task ID）
    2. get_current_config() 拉取最新配置
    3. Intent Sanitizer 预检
    4. Global Fuse 初始化
    5. RAG Router 数据源路由（深水区：网络请求）
    6. 异步文献检索（深水区：并发检索）
    7. PI 生成假设
    8. Hard-Link Anchor 校验
    9. Auditor 红方审计（AUDIT 级别）
    10. 混合适应度评估（深水区：计算）
    11. 生成报告 + Webhook 回调
    """
    task_id = str(self.request.id)
    start_time = datetime.now()

    # ==================== V7.1: 进入 Task 日志上下文 ====================
    # 所有后续日志自动包含 [TaskID: {task_id}] [Agent: hypothesis_generation_task]
    with TaskLogContext(task_id=task_id, agent_name='HypothesisGenerator'):

    # ==================== V7.0 新增：从 kwargs 读取前端参数 ====================
    # 前端参数优先级高于 Pydantic 配置（允许动态覆盖）
    frontend_hard_cap = kwargs.get('hard_cap')
    frontend_min_score_threshold = kwargs.get('min_score_threshold')
    frontend_max_iterations = kwargs.get('max_iterations')
    frontend_execution_mode = kwargs.get('execution_mode', 'autonomous')
    frontend_v7_defenses = kwargs.get('v7_defenses', {})
    # V7.1 新增：文献质量过滤参数（从前端 kwargs 读取）
    frontend_min_if = kwargs.get('min_if')
    frontend_date_range_start = kwargs.get('date_range_start')
    frontend_date_range_end = kwargs.get('date_range_end')

    logger.info(f"[Task {task_id}] V7.0 前端参数:")
    logger.info(f"[Task {task_id}]   hard_cap: {frontend_hard_cap} (前端覆盖)")
    logger.info(f"[Task {task_id}]   min_score_threshold: {frontend_min_score_threshold} (前端覆盖)")
    logger.info(f"[Task {task_id}]   max_iterations: {frontend_max_iterations}")
    logger.info(f"[Task {task_id}]   execution_mode: {frontend_execution_mode}")
    logger.info(f"[Task {task_id}]   v7_defenses: {frontend_v7_defenses}")
    # V7.1 新增：文献质量过滤参数日志
    logger.info(f"[Task {task_id}]   min_if: {frontend_min_if} (前端覆盖)")
    logger.info(f"[Task {task_id}]   date_range: {frontend_date_range_start}-{frontend_date_range_end} (前端覆盖)")

    # ==================== V6.1 关键：第一行调用 get_current_config() ====================
    # 消灭 Celery 状态幽灵，确保每次任务使用磁盘最新配置
    get_current_config, pydantic_ok = _import_config_module()
    if get_current_config is None:
        logger.critical(f"[Task {task_id}] 配置模块加载失败，任务终止")
        return TaskResult(
            task_id=task_id,
            state=TaskState.FAILURE,
            result_type='config_error',
            error='配置模块加载失败，无法执行任务',
            start_time=start_time.isoformat(),
            end_time=datetime.now().isoformat(),
        ).to_dict()

    # 强制 I/O 读取最新配置
    config = get_current_config(force_reload=True)
    config_version = config.config_version

    logger.info(f"[Task {task_id}] V7.0 配置加载成功:")
    logger.info(f"[Task {task_id}]   Pydantic: {pydantic_ok}")
    logger.info(f"[Task {task_id}]   版本: {config_version}")

    # ==================== V7.0 核心改进：前端参数覆盖 Pydantic ====================
    # 确定最终使用的参数值（前端 > Pydantic > 默认值）
    final_hard_cap = frontend_hard_cap if frontend_hard_cap is not None else config.defense_layer.hard_cap
    final_min_score_threshold = frontend_min_score_threshold if frontend_min_score_threshold is not None else config.hypothesis_generation.min_score_threshold
    # V7.1 新增：文献质量过滤最终参数（前端覆盖优先）
    final_min_if = frontend_min_if if frontend_min_if is not None else config.paper_search.min_if
    final_date_start = frontend_date_range_start if frontend_date_range_start is not None else config.paper_search.date_range_start
    final_date_end = frontend_date_range_end if frontend_date_range_end is not None else config.paper_search.date_range_end

    logger.info(f"[Task {task_id}] 最终参数:")
    logger.info(f"[Task {task_id}]   hard_cap: {final_hard_cap} (最终值)")
    logger.info(f"[Task {task_id}]   min_score_threshold: {final_min_score_threshold} (最终值)")
    # V7.1 新增：文献质量过滤最终参数日志
    logger.info(f"[Task {task_id}]   min_if: {final_min_if} (最终值)")
    logger.info(f"[Task {task_id}]   date_range: {final_date_start}-{final_date_end} (最终值)")

    logger.info(f"[Task {task_id}] Starting hypothesis generation")
    logger.info(f"[Task {task_id}] User input: {user_input[:100]}...")
    logger.info(f"[Task {task_id}] User domain: {user_domain or 'auto-detect'}")

    try:
        # ==================== Phase 1: Intent Sanitizer 预检 ====================
        self.update_progress(5, "Intent Sanitizer 预检")

        # V7.0: 检查是否启用 Intent Sanitizer（前端覆盖优先）
        intent_sanitizer_enabled = frontend_v7_defenses.get('intent_sanitizer', config.defense_layer.intent_sanitizer_enabled)

        if intent_sanitizer_enabled:
            try:
                from src.core.intent_sanitizer import sanitize_user_input
                strict_mode = config.defense_layer.intent_sanitizer_strict_mode
                is_valid, cleaned_input, blocked_message = sanitize_user_input(user_input, strict_mode=strict_mode)

                if not is_valid:
                    logger.warning(f"[Task {task_id}] Intent sanitization failed: {blocked_message}")
                    result = TaskResult(
                        task_id=task_id,
                        state=TaskState.FAILURE,
                        result_type='sanitization_blocked',
                        error=blocked_message,
                        start_time=start_time.isoformat(),
                        end_time=datetime.now().isoformat(),
                        config_version=config_version,
                    )

                    if webhook_url:
                        payload = WebhookPayload(
                            task_id=task_id,
                            task_type='hypothesis_generation',
                            state=TaskState.FAILURE,
                            result=result.to_dict(),
                            timestamp=datetime.now().isoformat(),
                        )
                        get_webhook_sender().send(webhook_url, payload)

                    return result.to_dict()

                logger.info(f"[Task {task_id}] Intent sanitization passed")
                user_input = cleaned_input

            except ImportError:
                logger.warning(f"[Task {task_id}] Intent Sanitizer not available, skipping")

        # ==================== Phase 2: Global Fuse 重置 ====================
        self.update_progress(10, "Global Fuse 初始化")

        # V7.0: 使用最终参数值（前端覆盖优先）
        hard_cap = final_hard_cap  # ✅ 使用前端覆盖后的值
        logger.info(f"[Task {task_id}] Global Fuse hard_cap: {hard_cap} (前端覆盖后)")

        try:
            from src.core.global_fuse import reset_global_fuse, get_global_fuse
            reset_global_fuse()
            fuse = get_global_fuse(hard_cap=hard_cap)
            logger.info(f"[Task {task_id}] Global Fuse initialized with cap={hard_cap}")
        except ImportError:
            logger.warning(f"[Task {task_id}] Global Fuse not available")
            fuse = None

        # ==================== Phase 3: RAG Router 数据源选择 ====================
        self.update_progress(15, "RAG Router 数据源路由")

        try:
            from src.core.rag_router import DynamicRAGRouter
            rag_router = DynamicRAGRouter()
            routing_result = rag_router.route(user_input, user_domain)

            detected_domain = routing_result.domain
            sources = routing_result.sources
            logger.info(f"[Task {task_id}] Domain detected: {detected_domain}")
            logger.info(f"[Task {task_id}] Data sources: {sources}")

        except ImportError:
            logger.warning(f"[Task {task_id}] RAG Router not available, using default PubMed")
            detected_domain = user_domain or 'unknown'
            sources = ['pubmed']

        # ==================== Phase 4: 异步文献检索（V7.1 并发版）====================
        self.update_progress(25, "异步文献检索启动（并发模式）")

        verified_ids = {'pmids': [], 'arxiv_ids': [], 'dois': []}
        all_papers = []  # V7.1 新增：统一论文池（用于 Source-Aware 过滤）

        # V6.1: 从 Pydantic 模型读取检索上限
        source_limits = config.data_source_routing.source_limits
        pubmed_max = source_limits.get('pubmed', config.paper_search.pubmed_max_results)
        arxiv_max = source_limits.get('arxiv', 20)
        s2_max = source_limits.get('semantic_scholar', 20)

        logger.info(f"[Task {task_id}] Source limits from Pydantic: pubmed={pubmed_max}, arxiv={arxiv_max}, s2={s2_max}")
        logger.info(f"[Task {task_id}] 数据源路由: {sources} (并发检索模式)")

        try:
            # V7.1: 使用 ThreadPoolExecutor 实现并发检索
            import concurrent.futures

            @log_exceptions(agent_name='PubMedSearcher', capture_vars=True)
            def fetch_pubmed():
                """PubMed 检索任务 - 深水区网络请求"""
                try:
                    from src.utils.pubmed import PubMedSearcher
                    pubmed_searcher = PubMedSearcher()
                    search_result = pubmed_searcher.search_by_idea(
                        user_input,
                        max_results=pubmed_max,
                        start_year=final_date_start,
                        end_year=final_date_end,
                        min_if=final_min_if if final_min_if > 0 else None,
                    )

                    papers = search_result.get('papers', [])
                    # 添加数据源标记（用于 Source-Aware 过滤）
                    for p in papers:
                        p['source'] = 'pubmed'

                    pmids = [p.get('pmid') for p in papers if p.get('pmid')]

                    return {
                        'source': 'pubmed',
                        'papers': papers,
                        'pmids': pmids,
                        'raw_query': search_result.get('search_terms', 'N/A'),
                        'audit_info': search_result.get('audit_info', {}),
                        'success': bool(papers)
                    }
                except Exception as e:
                    # V7.1: 深水区异常捕获 - 记录完整堆栈和关键变量
                    logger.exception(
                        "[PubMed] 检索异常（深水区）",
                        extra_vars={
                            'user_input': user_input[:100],
                            'pubmed_max': pubmed_max,
                            'date_range': f"{final_date_start}-{final_date_end}",
                            'min_if': final_min_if
                        }
                    )
                    return {'source': 'pubmed', 'papers': [], 'pmids': [], 'success': False, 'error': str(e)}

            @log_exceptions(agent_name='ArXivSearcher', capture_vars=True)
            def fetch_arxiv():
                """ArXiv 检索任务 - 深水区网络请求（Source-Aware：不传递 min_if）"""
                try:
                    from src.data_sources.arxiv_searcher import ArXivSearcher
                    arxiv_searcher = ArXivSearcher()
                    arxiv_result = arxiv_searcher.search(
                        user_input,
                        max_results=arxiv_max,
                        start_year=final_date_start,
                        end_year=final_date_end,
                    )

                    papers = arxiv_result.get('papers', [])
                    # 添加数据源标记（用于 Source-Aware 过滤）
                    for p in papers:
                        p['source'] = 'arxiv'

                    arxiv_ids = [p.get('arxiv_id') for p in papers if p.get('arxiv_id')]

                    return {
                        'source': 'arxiv',
                        'papers': papers,
                        'arxiv_ids': arxiv_ids,
                        'raw_query': arxiv_result.get('query', 'N/A'),
                        'audit_info': arxiv_result.get('audit_info', {}),
                        'success': arxiv_result.get('success', False)
                    }
                except Exception as e:
                    # V7.1: 深水区异常捕获 - 记录完整堆栈和关键变量
                    logger.exception(
                        "[ArXiv] 检索异常（深水区）",
                        extra_vars={
                            'user_input': user_input[:100],
                            'arxiv_max': arxiv_max,
                            'date_range': f"{final_date_start}-{final_date_end}",
                            'note': 'ArXiv 为预印本库，IF 豁免'
                        }
                    )
                    return {'source': 'arxiv', 'papers': [], 'arxiv_ids': [], 'success': False, 'error': str(e)}

            @log_exceptions(agent_name='SemanticScholarSearcher', capture_vars=True)
            def fetch_semantic_scholar():
                """Semantic Scholar 检索任务 - 深水区网络请求"""
                try:
                    from src.data_sources.semantic_scholar_searcher import SemanticScholarSearcher
                    s2_searcher = SemanticScholarSearcher()
                    s2_result = s2_searcher.search(user_input, max_results=s2_max)

                    papers = s2_result.get('papers', [])
                    # 添加数据源标记（用于 Source-Aware 过滤）
                    for p in papers:
                        p['source'] = 'semantic_scholar'

                    dois = [p.get('doi') for p in papers if p.get('doi')]

                    return {
                        'source': 'semantic_scholar',
                        'papers': papers,
                        'dois': dois,
                        'success': s2_result.get('success', False)
                    }
                except Exception as e:
                    # V7.1: 深水区异常捕获 - 记录完整堆栈和关键变量
                    logger.exception(
                        "[SemanticScholar] 检索异常（深水区）",
                        extra_vars={
                            'user_input': user_input[:100],
                            's2_max': s2_max
                        }
                    )
                    return {'source': 'semantic_scholar', 'papers': [], 'dois': [], 'success': False, 'error': str(e)}

            # 构建并发任务列表（根据 sources 动态决定）
            search_tasks = []
            if 'pubmed' in sources:
                search_tasks.append(fetch_pubmed)
            if 'arxiv' in sources:
                search_tasks.append(fetch_arxiv)
            if 'semantic_scholar' in sources:
                search_tasks.append(fetch_semantic_scholar)

            # V7.1: 并发执行所有检索任务
            logger.info(f"[Task {task_id}] 启动 {len(search_tasks)} 个并发检索任务...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(search_tasks), 3)) as executor:
                future_to_task = {executor.submit(task): task for task in search_tasks}

                for future in concurrent.futures.as_completed(future_to_task):
                    task_name = future_to_task[future]
                    try:
                        result = future.result()
                        source = result['source']

                        # 聚合结果到统一上下文
                        if source == 'pubmed':
                            self.update_progress(30, "PubMed 检索完成")
                            verified_ids['pmids'] = result['pmids']
                            all_papers.extend(result['papers'])
                            logger.info(f"[Task {task_id}] PubMed returned {len(result['pmids'])} PMIDs")
                            # V7.1 审计日志
                            logger.info(f"[Task {task_id}] [PubMed] 原始查询: '{result['raw_query']}'")
                            logger.info(f"[Task {task_id}] [PubMed] 执行约束: IF ≥ {final_min_if}, Date: {final_date_start}-{final_date_end}")

                        elif source == 'arxiv':
                            self.update_progress(40, "ArXiv 检索完成")
                            verified_ids['arxiv_ids'] = result['arxiv_ids']
                            all_papers.extend(result['papers'])
                            logger.info(f"[Task {task_id}] ArXiv returned {len(result['arxiv_ids'])} IDs")
                            # V7.1 Source-Aware 审计日志（注明 IF 豁免）
                            audit = result.get('audit_info', {})
                            logger.info(f"[Task {task_id}] [ArXiv] 原始查询: '{audit.get('raw_query', result['raw_query'])}'")
                            logger.info(f"[Task {task_id}] [ArXiv] 执行约束: Date: {final_date_start}-{final_date_end} (IF 豁免：ArXiv 为预印本库)")

                        elif source == 'semantic_scholar':
                            self.update_progress(45, "Semantic Scholar 检索完成")
                            verified_ids['dois'] = result['dois']
                            all_papers.extend(result['papers'])
                            logger.info(f"[Task {task_id}] Semantic Scholar returned {len(result['dois'])} DOIs")

                    except Exception as e:
                        logger.error(f"[Task {task_id}] 检索任务异常: {e}")

            logger.info(f"[Task {task_id}] 多源聚合完成: 统一论文池包含 {len(all_papers)} 篇文献")

        except Exception as e:
            logger.error(f"[Task {task_id}] Literature search error: {e}")
            traceback.print_exc()

        # ==================== V7.1 新增：Source-Aware 过滤验证 ====================
        if all_papers and (final_min_if > 0 or final_date_start or final_date_end):
            self.update_progress(47, "Source-Aware 过滤验证")

            try:
                from src.core.source_aware_filter import SourceAwareFilter

                # 对统一论文池应用 Source-Aware 过滤
                date_range = (final_date_start, final_date_end) if final_date_start or final_date_end else None
                filtered_papers = SourceAwareFilter.filter_papers(
                    all_papers,
                    min_if=final_min_if,
                    date_range=date_range
                )

                logger.info(f"[Task {task_id}] Source-Aware 过滤结果: {len(all_papers)} -> {len(filtered_papers)} 篇")

                # 更新 all_papers 为过滤后的结果
                all_papers = filtered_papers

                # 重新计算 verified_ids（基于过滤后的论文）
                verified_ids = {'pmids': [], 'arxiv_ids': [], 'dois': []}
                for p in all_papers:
                    if p.get('source') == 'pubmed' and p.get('pmid'):
                        verified_ids['pmids'].append(p['pmid'])
                    elif p.get('source') == 'arxiv' and p.get('arxiv_id'):
                        verified_ids['arxiv_ids'].append(p['arxiv_id'])
                    elif p.get('doi'):
                        verified_ids['dois'].append(p['doi'])

                logger.info(f"[Task {task_id}] 过滤后 verified_ids: PMIDs={len(verified_ids['pmids'])}, ArXiv={len(verified_ids['arxiv_ids'])}, DOIs={len(verified_ids['dois'])}")

            except ImportError:
                logger.warning(f"[Task {task_id}] Source-Aware 过滤器不可用，跳过后处理")

        # ==================== V7.1 P0 修复：文献检索健康检查 ====================
        # 防止断链退化漏洞：所有数据源失败时强制熔断，避免 LLM "脑补"
        total_verified = (
            len(verified_ids.get('pmids', [])) +
            len(verified_ids.get('arxiv_ids', [])) +
            len(verified_ids.get('dois', []))
        )

        logger.info(f"文献检索健康检查: 总计 {total_verified} 篇文献")

        if total_verified == 0:
            # 所有数据源均失败 → 触发断链熔断
            # V7.1: AUDIT 级别日志（业务驳回，供科研人员查阅）
            logger.audit(
                f"[驳回] 断链熔断触发：所有数据源均未返回文献\n"
                f"  查询: {user_input[:100]}...\n"
                f"  数据源: {sources}\n"
                f"  原因: PubMed/ArXiv/Semantic Scholar 均无响应\n"
                f"  建议: 请稍后重试或检查网络连接"
            )

            # V7.1: ERROR 级别日志（系统异常，供研发排查）
            logger.critical(
                "断链熔断触发",
                extra_vars={
                    'sources': sources,
                    'date_range': f"{final_date_start}-{final_date_end}",
                    'min_if': final_min_if
                }
            )

            result = TaskResult(
                task_id=task_id,
                state=TaskState.FAILURE,
                result_type='literature_unavailable',
                error=(
                    '文献检索服务不可用：PubMed/ArXiv/Semantic Scholar 均无响应。'
                    '为避免幻觉生成，任务已强制终止。请稍后重试或检查网络连接。'
                ),
                start_time=start_time.isoformat(),
                end_time=datetime.now().isoformat(),
                config_version=config_version,
            )

            # 尝试 Webhook 通知
            if webhook_url:
                payload = WebhookPayload(
                    task_id=task_id,
                    task_type='hypothesis_generation',
                    state=TaskState.FAILURE,
                    result=result.to_dict(),
                    timestamp=datetime.now().isoformat(),
                )
                get_webhook_sender().send(webhook_url, payload)

            return result.to_dict()

        # ==================== Phase 5: PI 生成假设 ====================
        self.update_progress(50, "PI 假设生成")

        hypothesis_result = None
        try:
            from src.prompts.pi_system_prompt import format_pi_prompt_v60
            from src.utils.llm_utils import call_llm

            pi_prompt = format_pi_prompt_v60(
                user_domain=detected_domain,
                user_idea=user_input,
                data_sources=sources,
                verified_ids=verified_ids,
            )

            self.update_progress(55, "调用 PI Agent")
            hypothesis_result = call_llm(pi_prompt)

            if hypothesis_result:
                logger.info(f"[Task {task_id}] PI hypothesis generated")
            else:
                logger.warning(f"[Task {task_id}] PI hypothesis generation failed")

        except ImportError as e:
            logger.warning(f"[Task {task_id}] PI Prompt V6.0 not available: {e}")

        except Exception as e:
            logger.error(f"[Task {task_id}] PI generation error: {e}")

        # ==================== Phase 6: Hard-Link Anchor 校验 ====================
        self.update_progress(70, "Hard-Link Anchor 锚定校验")

        anchor_passed = True
        anchor_message = ""

        # V7.0: 检查是否启用 Hard-Link Anchor（前端覆盖优先）
        hard_link_anchor_enabled = frontend_v7_defenses.get('hard_link_anchor', config.defense_layer.hard_link_anchor_enabled)

        if hypothesis_result and hard_link_anchor_enabled:
            try:
                from src.core.hard_link_anchor import perform_anchor_check
                strict_mode = config.defense_layer.hard_link_anchor_strict_mode

                is_valid, anchor_message = perform_anchor_check(
                    hypothesis_result,
                    verified_ids.get('pmids', []),
                    verified_ids.get('arxiv_ids', []),
                    verified_ids.get('dois', []),
                    strict_mode=strict_mode,
                )

                anchor_passed = is_valid
                logger.info(f"[Task {task_id}] Anchor check: {anchor_passed}")

                if not anchor_passed:
                    logger.warning(f"[Task {task_id}] Anchor check failed: {anchor_message}")

            except ImportError:
                logger.warning(f"[Task {task_id}] Hard-Link Anchor not available, skipping check")
            except Exception as e:
                logger.error(f"[Task {task_id}] Anchor check error: {e}")

        # ==================== Phase 7: V7.1 混合适应度评估 ====================
        self.update_progress(80, "V7.1 混合适应度评估")

        fitness_result = None
        if hypothesis_result and anchor_passed:
            try:
                from src.core.hybrid_fitness import HybridFitnessScorer
                from src.core.physical_validator import PhysicalValidator

                # V7.1: 物理铁闸校验（深水区）
                validator = PhysicalValidator()
                physical_result = validator.validate_hypothesis_physical(hypothesis_result)

                if not physical_result.passed:
                    # V7.1: AUDIT 级别日志（业务驳回）
                    logger.audit(
                        f"[驳回] 物理铁闸校验失败\n"
                        f"  失败原因: {physical_result.failure_reason}\n"
                        f"  校验详情: {physical_result.details}"
                    )
                    logger.warning(f"物理验证失败: {physical_result.failure_reason}")
                    anchor_passed = False
                    anchor_message = physical_result.failure_reason
                else:
                    # V7.1: 混合适应度计算（深水区）
                    scorer = HybridFitnessScorer()
                    fitness_result = scorer.calculate_fitness(
                        hypothesis_json=hypothesis_result,
                        retrieved_docs=all_papers if all_papers else [],  # V7.1: 使用统一论文池
                    )

                    logger.info(f"混合适应度评估完成: fitness={fitness_result.hybrid_fitness}")
                    logger.debug(f"  向量创新分: {fitness_result.vector_novelty_score}")
                    logger.debug(f"  红方严谨分: {fitness_result.red_team_rigor_score}")

                    # V7.1: 检查是否达到阈值
                    min_threshold = final_min_score_threshold
                    if fitness_result.hybrid_fitness < min_threshold:
                        # V7.1: AUDIT 级别日志（业务驳回）
                        logger.audit(
                            f"[驳回] 混合适应度不达标\n"
                            f"  得分: {fitness_result.hybrid_fitness}\n"
                            f"  阈值: {min_threshold}\n"
                            f"  差距: {min_threshold - fitness_result.hybrid_fitness}"
                        )
                        logger.warning(f"混合适应度得分 {fitness_result.hybrid_fitness} < 阈值 {min_threshold}")
                        anchor_passed = False
                        anchor_message = f"混合适应度得分 {fitness_result.hybrid_fitness} 未达到阈值 {min_threshold}"

            except ImportError as e:
                logger.warning(f"V7.1 Hybrid Fitness 模块不可用: {e}")
            except Exception as e:
                # V7.1: 深水区异常捕获 - 记录完整堆栈
                logger.exception(
                    "混合适应度评估异常（深水区）",
                    extra_vars={
                        'hypothesis_keys': list(hypothesis_result.keys()) if hypothesis_result else [],
                        'papers_count': len(all_papers) if all_papers else 0,
                        'min_threshold': final_min_score_threshold
                    }
                )

        # ==================== Phase 8: Auditor 红方审计（降权版） ====================
        self.update_progress(85, "Auditor 红方审计 V6.1")

        audit_result = None
        if hypothesis_result and anchor_passed:
            try:
                from src.agents.red_team_agent import execute_v61_rigor_audit
                audit_result = execute_v61_rigor_audit(hypothesis_result)
                logger.info(f"[Task {task_id}] V6.1 Auditor audit completed")
            except ImportError:
                logger.warning(f"[Task {task_id}] V6.1 Auditor not available")
            except Exception as e:
                logger.error(f"[Task {task_id}] Auditor error: {e}")

        # ==================== Phase 9: 生成最终报告 ====================
        self.update_progress(90, "生成最终报告")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        api_calls_used = 0
        tokens_used = 0
        if fuse:
            stats = fuse.get_stats()
            api_calls_used = stats.total_api_calls
            tokens_used = stats.total_tokens_used

        if not hypothesis_result or not anchor_passed:
            result_type = 'rejection'
            try:
                from src.core.rejection_report import generate_rejection_report
                payload = generate_rejection_report(
                    user_input=user_input,
                    domain=detected_domain,
                    rejection_type='insufficient_support' if not hypothesis_result else 'validation_failed',
                    primary_reason='文献支撑不足，无法生成有效假设' if not hypothesis_result else anchor_message,
                    collision_papers=[],
                    logical_flaws=[],
                    api_calls_used=api_calls_used,
                    time_elapsed=duration,
                )
            except ImportError:
                payload = {
                    'rejection_type': 'insufficient_support',
                    'reason': '无法生成有效假设',
                    'domain': detected_domain,
                }
            state = TaskState.FAILURE

        else:
            result_type = 'hypothesis'
            payload = {
                'hypothesis': hypothesis_result,
                'audit': audit_result,
                'fitness': fitness_result.to_dict() if fitness_result else None,
                'verified_ids': verified_ids,
                'domain': detected_domain,
                'sources': sources,
            }
            state = TaskState.SUCCESS

        result = TaskResult(
            task_id=task_id,
            state=state,
            result_type=result_type,
            payload=payload,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration=duration,
            api_calls_used=api_calls_used,
            tokens_used=tokens_used,
            config_version=config_version,
        )

        # ==================== Phase 10: Webhook 回调 ====================
        self.update_progress(95, "Webhook 回调通知")

        if webhook_url:
            payload = WebhookPayload(
                task_id=task_id,
                task_type='hypothesis_generation',
                state=state,
                result=result.to_dict(),
                timestamp=end_time.isoformat(),
            )
            get_webhook_sender().send(webhook_url, payload)

        self.update_progress(100, "任务完成")

        logger.info(f"[Task {task_id}] Completed in {duration:.2f}s")
        logger.info(f"[Task {task_id}] State: {state.value}")
        logger.info(f"[Task {task_id}] API calls: {api_calls_used}")
        logger.info(f"[Task {task_id}] Config version: {config_version}")

        return result.to_dict()

    except SoftTimeLimitExceeded:
        # V7.1: 超时异常捕获
        logger.warning("任务软超时触发")
        return TaskResult(
            task_id=task_id,
            state=TaskState.TIMEOUT,
            result_type='timeout',
            error='任务执行超过软时间限制',
            start_time=start_time.isoformat(),
            end_time=datetime.now().isoformat(),
            config_version=config_version,
        ).to_dict()

    except TimeLimitExceeded:
        # V7.1: 超时异常捕获
        logger.critical("任务硬超时触发")
        return TaskResult(
            task_id=task_id,
            state=TaskState.TIMEOUT,
            result_type='timeout',
            error='任务执行超过硬时间限制',
            start_time=start_time.isoformat(),
            end_time=datetime.now().isoformat(),
            config_version=config_version,
        ).to_dict()

    except Exception as e:
        # V7.1: 深水区异常捕获 - 记录完整堆栈和关键变量
        logger.exception(
            "任务执行异常（未预期）",
            extra_vars={
                'user_input': user_input[:100] if 'user_input' in dir() else 'N/A',
                'user_domain': user_domain,
                'sources': sources if 'sources' in dir() else 'N/A',
                'exception_type': type(e).__name__
            }
        )

        return TaskResult(
            task_id=task_id,
            state=TaskState.FAILURE,
            result_type='error',
            error=str(e),
            traceback=traceback.format_exc(),
            start_time=start_time.isoformat(),
            end_time=datetime.now().isoformat(),
            config_version=config_version,
        ).to_dict()


# ==================== 任务注册（延迟绑定） ====================

def register_tasks():
    """
    注册所有 Celery 任务（延迟绑定到 Celery app）
    """
    app = get_celery_app()

    # 注册假设生成任务
    app.task(
        bind=True,
        base=ProgressTrackingTask,
        max_retries=3,
    )(hypothesis_generation_task_impl, name='hypothesis_generation_task')

    logger.info("[Celery] 任务注册完成: hypothesis_generation_task")

    return app


# ==================== Celery CLI 发现入口 ====================
# Celery CLI 需要 'celery' 属性在模块级别可访问
# 这里使用延迟初始化的 app，避免模块顶层实例化配置
_celery_for_cli = None


def _get_celery_for_cli():
    """为 Celery CLI 提供已注册任务的 app"""
    global _celery_for_cli
    if _celery_for_cli is None:
        app = get_celery_app()
        # 自动注册任务 - 使用正确的注册方式
        task_obj = app.task(
            hypothesis_generation_task_impl,
            bind=True,
            base=ProgressTrackingTask,
            max_retries=3,
            name='hypothesis_generation_task'
        )
        _celery_for_cli = app
        logger.info(f"[Celery CLI] 自动注册任务完成: {task_obj.name}")
    return _celery_for_cli


# Celery CLI 发现入口
celery = _get_celery_for_cli()

# 为了兼容旧代码，提供 celery_app 别名
celery_app = celery  # 现在指向同一个实例

def submit_hypothesis_generation(
    user_input: str,
    user_domain: str = None,
    webhook_url: str = None,
    session_id: str = None,
) -> Dict:
    """
    提交假设生成任务

    Args:
        user_input: 用户研究想法
        user_domain: 学科领域
        webhook_url: Webhook 回调URL
        session_id: 会话ID

    Returns:
        Dict: 包含 task_id 和预估完成时间
    """
    # V6.1: 获取最新配置
    get_current_config, _ = _import_config_module()
    if get_current_config is not None:
        config = get_current_config()
        soft_limit = config.async_tasks.task_soft_time_limit
    else:
        soft_limit = DEFAULT_SOFT_TIME_LIMIT

    app = get_celery_app()
    task = app.send_task(
        'hypothesis_generation_task',
        kwargs={
            'user_input': user_input,
            'user_domain': user_domain,
            'webhook_url': webhook_url,
            'session_id': session_id,
        }
    )

    return {
        'task_id': task.id,
        'state': 'pending',
        'estimated_duration': f'{soft_limit // 60} 分钟',
        'webhook_url': webhook_url,
        'message': '任务已提交，请通过 task_id 查询状态或等待 Webhook 回调',
    }


def get_task_status(task_id: str) -> Dict:
    """查询任务状态"""
    app = get_celery_app()
    result = AsyncResult(task_id, app=app)

    state_map = {
        'PENDING': TaskState.PENDING,
        'STARTED': TaskState.STARTED,
        'PROGRESS': TaskState.PROGRESS,
        'SUCCESS': TaskState.SUCCESS,
        'FAILURE': TaskState.FAILURE,
        'RETRY': TaskState.RETRY,
        'REVOKED': TaskState.REVOKED,
    }

    state = state_map.get(result.state, TaskState.PENDING)

    response = {
        'task_id': task_id,
        'state': state.value,
        'ready': result.ready(),
        'successful': result.successful() if result.ready() else None,
    }

    if result.ready():
        response['result'] = result.result
    elif result.state == 'PROGRESS':
        response['progress'] = result.info.get('progress', 0)
        response['progress_message'] = result.info.get('message', '')

    return response


def revoke_task(task_id: str, terminate: bool = False) -> bool:
    """撤销任务"""
    try:
        app = get_celery_app()
        app.control.revoke(task_id, terminate=terminate)
        logger.info(f"[Revoke] Task {task_id} revoked (terminate={terminate})")
        return True
    except Exception as e:
        logger.error(f"[Revoke] Failed to revoke task {task_id}: {e}")
        return False


# ==================== 初始化入口 ====================

def init_celery_tasks():
    """
    初始化 Celery 任务系统

    在 Worker 启动时调用
    """
    app = get_celery_app()
    register_tasks()
    logger.info("[Celery V6.1] 任务系统初始化完成")
    return app


# ==================== 测试 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V6.1 Celery 异步任务系统测试 - Pydantic 强校验版")
    print("=" * 70)

    # 测试配置加载
    get_current_config, pydantic_ok = _import_config_module()
    if get_current_config:
        config = get_current_config()
        print(f"\n[测试 1] 配置加载:")
        print(f"  Pydantic: {pydantic_ok}")
        print(f"  版本: {config.config_version}")
        print(f"  hard_cap: {config.defense_layer.hard_cap}")
        print(f"  min_score_threshold: {config.hypothesis_generation.min_score_threshold}")
        print(f"  autodock_energy_threshold: {config.molecular_docking.autodock_energy_threshold}")

    # 测试 Celery app 初始化
    print(f"\n[测试 2] Celery App 初始化:")
    app = get_celery_app()
    print(f"  Broker: {app.conf.broker_url}")
    print(f"  Soft Timeout: {app.conf.task_soft_time_limit}s")
    print(f"  Hard Timeout: {app.conf.task_time_limit}s")

    # 测试任务结果
    result = TaskResult(
        task_id='test-v61-123',
        state=TaskState.SUCCESS,
        result_type='hypothesis',
        payload={'test': 'data'},
        duration=30.5,
        api_calls_used=5,
        config_version='v6.1',
    )
    print(f"\n[测试 3] 任务结果:")
    print(result.to_json())

    print("\n" + "=" * 70)
    print("V6.1 Celery 任务系统测试完成")
    print("=" * 70)