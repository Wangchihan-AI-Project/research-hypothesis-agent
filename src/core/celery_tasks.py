# -*- coding: utf-8 -*-
"""
V7.1 Celery 异步任务分发系统 - 集中式日志挂载版

V7.1 核心改进：
1. 集中式日志系统挂载：所有日志写入 logs/system_v7.log
2. Task ID 贯穿注入：使用 set_task_context()（避免缩进问题）
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

# ==================== 关键：加载 .env 文件（Worker 进程需要）====================
# Worker 是独立进程，不会继承 Streamlit 的环境变量
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
env_file = project_root / '.env'

if env_file.exists():
    load_dotenv(env_file, encoding='utf-8')

# ==================== V7.1: 集中式日志挂载 ====================
from src.utils.logger import (
    get_central_logger,
    set_task_context,
    clear_task_context,
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
                    # 队列配置
                    task_default_queue='research',
                    task_queues={
                        'research': {
                            'exchange': 'research',
                            'routing_key': 'research',
                        }
                    },
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
    主任务实现：假设生成全流程 (V7.0)

    **V7.0 核心改进：支持前端参数覆盖 Pydantic 默认值**

    流程：
    1. get_current_config() 拉取最新配置
    2. 从 kwargs 读取前端参数覆盖（优先级高于 Pydantic）
    3. Intent Sanitizer 预检
    4. Global Fuse 初始化（从 kwargs 或 Pydantic 读取 hard_cap）
    5. RAG Router 数据源路由
    6. 异步文献检索
    7. PI 生成假设
    8. Hard-Link Anchor 校验
    9. Auditor 红方审计
    10. 混合适应度评估（V7.0）
    11. 生成报告 + Webhook 回调
    """
    task_id = str(self.request.id)
    start_time = datetime.now()

    # ==================== V7.1: 设置 Task 日志上下文 ====================
    # 所有后续日志自动包含 [TaskID: {task_id}] [Agent: HypothesisGenerator]
    set_task_context(task_id=task_id, agent_name='HypothesisGenerator')

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
        # ==================== Phase 1: 语义分类预检 (V7.2) ====================
        self.update_progress(5, "语义分类预检")

        # V7.0: 检查是否启用 Intent Sanitizer（前端覆盖优先）
        intent_sanitizer_enabled = frontend_v7_defenses.get('intent_sanitizer', config.defense_layer.intent_sanitizer_enabled)

        if intent_sanitizer_enabled:
            try:
                # V7.2: 优先使用新的语义分类器
                from src.core.semantic_classifier import classify_intent
                classification = classify_intent(user_input)

                if not classification.is_valid:
                    logger.warning(f"[Task {task_id}] 语义分类拦截: {classification.reasoning}")
                    result = TaskResult(
                        task_id=task_id,
                        state=TaskState.FAILURE,
                        result_type='sanitization_blocked',
                        error=f"⚠️ 输入被系统���全网关拦截：{classification.reasoning}",
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

                # 记录意图类型
                logger.info(f"[Task {task_id}] 语义分类通过: type={classification.intent_type.value}, risk={classification.risk_level.value}")
                user_input = classification.cleaned_input

            except ImportError:
                # 降级到旧的 Intent Sanitizer
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

                    logger.info(f"[Task {task_id}] Intent sanitization passed (legacy)")
                    user_input = cleaned_input

                except ImportError:
                    logger.warning(f"[Task {task_id}] 所有分类器不可用，跳过预检")

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

            def fetch_pubmed():
                """PubMed 检索任务"""
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
                    logger.error(f"[Task {task_id}] PubMed error: {e}")
                    return {'source': 'pubmed', 'papers': [], 'pmids': [], 'success': False, 'error': str(e)}

            def fetch_arxiv():
                """ArXiv 检索任务（Source-Aware：不传递 min_if）"""
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
                    logger.error(f"[Task {task_id}] ArXiv error: {e}")
                    return {'source': 'arxiv', 'papers': [], 'arxiv_ids': [], 'success': False, 'error': str(e)}

            def fetch_semantic_scholar():
                """Semantic Scholar 检索任务"""
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
                    logger.error(f"[Task {task_id}] Semantic Scholar error: {e}")
                    return {'source': 'semantic_scholar', 'papers': [], 'dois': [], 'success': False, 'error': str(e)}

            # 构建并发任务列表（根据 sources 动态决定）
            search_tasks = []
            if 'pubmed' in sources:
                search_tasks.append(fetch_pubmed)
            if 'arxiv' in sources:
                search_tasks.append(fetch_arxiv)
            if 'semantic_scholar' in sources:
                search_tasks.append(fetch_semantic_scholar)

            # V7.1: 并发执行所有检索任务（带全局超时控制，防止卡死）
            logger.info(f"[Task {task_id}] 启动 {len(search_tasks)} 个并发检索任务...")

            # V7.1 修复：使用 concurrent.futures.wait 添加全局超时
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(search_tasks), 3)) as executor:
                future_to_task = {executor.submit(task): task for task in search_tasks}

                # 设置全局超时：120秒后强制返回已完成的结果
                try:
                    # 等待所有任务完成，最多等待120秒
                    futures_done, futures_pending = concurrent.futures.wait(
                        future_to_task.keys(),
                        timeout=120  # V7.1: 全局超时120秒
                    )

                    # 处理已完成的任务
                    for future in futures_done:
                        task_name = future_to_task[future]
                        try:
                            result = future.result(timeout=5)  # 单个结果获取超时5秒
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

                    # 处理超时的任务
                    if futures_pending:
                        logger.warning(f"[Task {task_id}] {len(futures_pending)} 个检索任务超时，已取消")
                        for future in futures_pending:
                            future.cancel()

                except Exception as e:
                    logger.error(f"[Task {task_id}] 并发检索异常: {e}")

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

        logger.info(f"[Task {task_id}] 文献检索健康检查: 总计 {total_verified} 篇文献")

        if total_verified == 0:
            # 所有数据源均失败 → 触发断链熔断
            logger.critical(f"[Task {task_id}] 断链熔断触发：所有数据源均未返回文献")

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

        # ==================== V7.3.1 辅助函数：构建红方反馈上下文（带锚点记忆锁）====================
        def _build_red_team_feedback_context(red_team_result: dict, defense_result: dict, iteration: int, verified_ids: dict = None) -> str:
            """
            V7.3.1 逻辑闭环突围反馈机制 + 锚点记忆锁（Anchor Lock）

            构建『方法论硬核补强』的高级博弈反馈上下文
            同时在 Prompt 末尾追加"锚点记忆锁"，防止 PI Agent 因注意力稀释遗忘已验证的文献 ID

            Args:
                red_team_result: 红方攻击结果
                defense_result: 防御委员会裁决结果
                iteration: 当前迭代次数
                verified_ids: 已验证的文献 ID 字典 {'pmids': [], 'arxiv_ids': [], 'dois': []}

            Returns:
                str: 格式化的高级博弈反馈上下文（含方法论补强协议 + 锚点记忆锁）
            """
            # ==================== V7.2 关键修复：正确提取红方攻击报告 ====================
            # Red Team Agent 返回的结构是 {'success': True, 'attack_report': {...}}
            attack_report = red_team_result.get('attack_report', {}) if red_team_result else {}

            # 收集红方攻击意见（从 attack_report 中提取）
            red_attacks = []
            if attack_report:
                verdict = attack_report.get('verdict', 'unknown')
                critical_flaws = attack_report.get('critical_flaws', [])
                if critical_flaws:
                    red_attacks.extend([f"- {f.get('issue', f) if isinstance(f, dict) else f}" for f in critical_flaws[:5]])

                severe_issues = attack_report.get('severe_issues', [])
                if severe_issues:
                    red_attacks.extend([f"- {iss.get('issue', iss) if isinstance(iss, dict) else iss}" for iss in severe_issues[:3]])

            # 收集委员会问题
            committee_issues = []
            if defense_result:
                final_verdict = defense_result.get('final_verdict', '')
                critical_issues = defense_result.get('critical_issues', [])
                if critical_issues:
                    committee_issues.extend([f"- {iss}" for iss in critical_issues[:5]])

            # 构建核心攻击文本
            attacks_text = "\n".join(red_attacks + committee_issues)
            if not attacks_text:
                attacks_text = "- 未见具体攻击点，但整体未通过审查"

            # ==================== V7.2 核心新增：方法论攻击检测 ====================
            # 检测红方是否攻击了方法论相关漏洞
            # 关键修复：覆盖红方 Agent 常用攻击词汇
            methodology_keywords = {
                'data_leak': ['数据泄漏', 'data leakage', '泄漏', 'leak', '预处理泄漏', 'preprocessing leak',
                             '信息泄露', 'information leakage', '泄露', '样本泄漏', 'sample leakage',
                             '数据泄露', '穿越', 'temporal', 'future', '泄漏风险', '数据穿越',
                             '未来信息', 'future information', '预处理泄漏', '泄露风险'],
                'overfitting': ['过拟合', 'overfit', 'overfitting', '泛化', 'generalization',
                              '泛化能力', 'generalize', '拟合过度', '泛化性', '过拟合风险'],
                'interpretability': ['不可解释', '黑盒', 'black box', 'interpretability', '可解释性', 'explainability',
                                    'interpret', 'explainable', '透明性', 'transparency', '黑盒模型'],
                'cross_validation': ['交叉验证', 'cross validation', 'CV', '验证集', 'validation',
                                    'nested', '嵌套', 'k-fold', '分层', 'stratified', 'cv策略',
                                    '交叉验证策略', '验证方法', 'cv策略', '验证方案', '具体cv', '具体cv策略'],
                'feature_selection': ['特征选择', 'feature selection', '选择泄漏', 'selection bias',
                                     '特征泄漏', '特征泄露', 'RFE', 'ANOVA', '特征工程'],
                'temporal_leak': ['时间泄漏', 'temporal leak', '时序泄漏', 'future data',
                                '时间穿越', 'temporal leakage', '时间泄露', '时间偏倚', '数据穿越'],
                'sample_bias': ['样本偏差', 'sample bias', '选择偏差', 'selection bias',
                              '非独立', 'independence', '独立性', '样本代表性', 'selection',
                              '内生性', '内生性偏倚', '混杂因素', 'confounding'],
                'preprocessing': ['预处理', 'preprocessing', '预处理泄漏', '隔离', '隔离方案',
                                '预处理隔离', '数据预处理', '预处理策略'],
            }

            detected_methodology_attacks = []
            for attack_type, keywords in methodology_keywords.items():
                for keyword in keywords:
                    if keyword.lower() in attacks_text.lower():
                        detected_methodology_attacks.append(attack_type)
                        break

            # 构建方法论补强指令（基于检测到的攻击类型）
            methodology_reinforcement = ""
            if detected_methodology_attacks:
                methodology_reinforcement = """### 🛡️ 【方法论补强协议】（强制执行）

**红方攻击了你的方法论！你不准回避！**

你必须在生成的 JSON 假说的 **`methodology`** 字段中，专门加入一段 **`technical_safeguards`**（技术防范措施）。

以下是针对红方攻击的硬核反击模板：

"""

                # 根据攻击类型生成针对性补强指令
                attack_countermeasures = {
                    'data_leak': """
**1. 针对「数据泄漏」攻击 → 必须写入：**
```json
"technical_safeguards": {
  "data_leak_prevention": {
    "strategy": "嵌套交叉验证 (Nested Cross-Validation)",
    "implementation": "所有预处理参数（均值/方差归一化、特征选择阈值）仅在训练折叠（Training Folds）内计算，严格隔离测试数据，从物理上杜绝数据泄漏",
    "validation_protocol": "外层5折评估泛化性能，内层5折优化超参数，两层完全独立"
  }
}
```
""",
                    'overfitting': """
**2. 针对「过拟合」攻击 → 必须写入：**
```json
"technical_safeguards": {
  "overfitting_prevention": {
    "regularization": "Dropout (p=0.3) + L2正则化 (λ=1e-4) + 早停机制",
    "validation_strategy": "独立验证集监控损失曲线，当验证损失连续3轮上升时触发早停",
    "model_complexity_control": "限制 MPNN 层数 ≤ 3，Transformer attention heads ≤ 4"
  }
}
```
""",
                    'interpretability': """
**3. 针对「不可解释性」攻击 → 必须写入：**
```json
"technical_safeguards": {
  "interpretability_framework": {
    "attribution_method": "SHAP (Shapley Additive Explanations) + LIME 局部归因",
    "graph_sensitivity": "对 MPNN 子图特征进行灵敏度分析，识别关键分子子结构",
    "biological_validation": "模型预测的疾病关联子图必须与已知通路数据库（KEGG/Reactome）交叉验证"
  }
}
```
""",
                    'cross_validation': """
**4. 针对「交叉验证」攻击 → 必须写入：**
```json
"technical_safeguards": {
  "cv_protocol": {
    "nested_cv": "外层10折留一评估，内层5折超参数搜索",
    "stratification": "按疾病类型分层采样，确保每折包含所有疾病类别",
    "seed_control": "固定随机种子 (seed=42)，确保实验可复现"
  }
}
```
""",
                    'feature_selection': """
**5. 针对「特征选择泄漏」攻击 → 必须写入：**
```json
"technical_safeguards": {
  "feature_selection_protocol": {
    "wrapper_method": "递归特征消除 (RFE) 仅在训练折叠内执行",
    "filter_method": "单变量统计检验（如 ANOVA）仅在训练集计算阈值",
    "embedded_method": "L1正则化自动特征选择，权重仅由训练数据决定"
  }
}
```
""",
                    'temporal_leak': """
**6. 针对「时序泄漏」攻击 → 必须写入：**
```json
"technical_safeguards": {
  "temporal_validation": {
    "time_aware_split": "按时间戳排序，训练集使用早期数据，验证集使用中期，测试集使用最新数据",
    "no_future_access": "严禁模型访问未来时刻的疾病诊断记录或药物处方信息",
    "temporal_window": "设置合理的时间窗口（如 6个月），避免边界泄漏"
  }
}
```
""",
                    'sample_bias': """
**7. 针对「样本偏差」攻击 → 必须写入：**
```json
"technical_safeguards": {
  "bias_correction": {
    "demographic_balance": "按年龄、性别、种族分层采样，确保样本代表性",
    "propensity_matching": "使用倾向得分匹配 (PSM) 消除混杂因素",
    "sensitivity_analysis": "对不同亚组进行分层分析，验证结论稳健性"
  }
}
```
""",
                    'preprocessing': """
**8. 针对「预处理泄漏」攻击 → 必须写入：**
```json
"technical_safeguards": {
  "preprocessing_isolation": {
    "strategy": "嵌套交叉验证内的预处理隔离",
    "implementation": "所有预处理步骤（归一化、标准化、特征工程）仅在训练折叠内拟合参数，测试集仅使用训练集的统计量进行转换",
    "pipeline": "使用 scikit-learn Pipeline 确保预处理与模型训练在同一 CV 折叠内执行",
    "data_leak_prevention": "严禁在全局数据上计算任何统计量（均值、方差、分位数），从源头上消除数据泄漏"
  }
}
```
""",
                }

                # 添加检测到的攻击类型的反击模板
                for attack_type in detected_methodology_attacks:
                    if attack_type in attack_countermeasures:
                        methodology_reinforcement += attack_countermeasures[attack_type]

                methodology_reinforcement += """
**⚠️ 硬性要求：**
- 必须使用上述 **专业术语**（如 Nested CV、SHAP、 propensity matching）
- 必须给出 **具体参数值**（如 5折、 seed=42）
- 必须明确 **实施细节**（如 "仅在训练折叠内计算"）
- 这些技术防范措施必须出现在你输出�� JSON 假说的 **methodology.technical_safeguards** 字段中！

"""

            # V7.2 进阶博弈指令模板（含方法论补强）
            ADVANCED_ITERATION_PROMPT = f"""## 【硬核博弈指令】

这是你的第 **{iteration} 次重试**。防御委员会刚才驳回了你的假说，红方的核心攻击意见如下：

{attacks_text}

### ⚠️ 硬性约束

**你必须修复这些致命漏洞，但绝对不允许牺牲核心的学术创新性！**
如果你的新假说退化成平庸的综述或过时的基线验证，你依然会被系统抹杀！

{methodology_reinforcement}

### 🎯 高级迭代策略

1. **精准切除而非全盘降级**
   - 不要抛弃你的核心架构（如 MPNN、Transformer、因果推断等）
   - 如果某条次要的因果链缺乏文献支撑，切除它
   - 如果某种模态的数据有瑕疵，替换它
   - **核心的创新引擎必须保留**

2. **相邻可能（Adjacent Possible）寻找平替**
   - 如果你的某步推演在物理上不可行，去寻找既有创新性又有文献支撑的等价替代路径
   - 不是直接退回到十年前的老旧算法
   - 而是在创新性与可行性之间找到最佳平衡点

3. **用证据做盾牌**
   - 在你的新版本中，必须用更密集的 exact_quote 提前堵住红方的嘴
   - 每个关键断言都要有具体的 PMID/ArxivID 支撑

---

**现在，请在保持高影响力的前提下，提交既有防守又具锋芒的优化版假说！**
"""

            # ==================== V7.3.1 锚点记忆锁（Anchor Memory Lock）====================
            # 防止 PI Agent 因注意力稀释遗忘已验证的文献 ID
            anchor_lock = ""

            if verified_ids and iteration > 1:
                pmids = verified_ids.get('pmids', [])
                arxiv_ids = verified_ids.get('arxiv_ids', [])
                dois = verified_ids.get('dois', [])

                # 只有存在已验证文献时才追加锚点锁
                if pmids or arxiv_ids or dois:
                    anchor_lock = """

---

### ⚠️⚠️⚠️ 【V7.3.1 生死红线：锚点记忆锁】（强制执行）

**系统警告：你必须在新生成的 JSON 中引用以下已验证的真实文献 ID！**

**已验证的文献锚点（绝对不能丢失）：**
"""

                    if pmids:
                        anchor_lock += f"""
**PMIDs（PubMed 文献 ID）**: {', '.join(map(str, pmids))}
"""
                    if arxiv_ids:
                        anchor_lock += f"""
**ArXiv IDs**: {', '.join(arxiv_ids)}
"""
                    if dois:
                        anchor_lock += f"""
**DOIs**: {', '.join(dois)}
"""

                    anchor_lock += """
**硬性要求：**
1. 你的 `references` 字段中必须包含上述文献 ID
2. 你的假设必须引用这些文献来支撑核心论断
3. **绝对禁止**编造不存在的文献 ID
4. **绝对禁止**遗漏上述已验证的真实文献

**Schema 约束提醒：**
- 防御协议只能写入 `methodology.technical_safeguards` 字段
- 文献引用必须写入 `references` 字段，格式为 `[{"pmid": "12345678", "citation": "..."}]`

**如果违反上述约束，将被系统直接拒绝，无法通过 Step 7 锚定校验！**
---
"""

            # 将锚点记忆锁追加到进阶博弈指令末尾
            ADVANCED_ITERATION_PROMPT += anchor_lock

            return ADVANCED_ITERATION_PROMPT

        # ==================== V7.2 Phase 5-10: 对抗收敛循环 ====================
        self.update_progress(50, "启动红蓝对抗收敛循环")

        # V7.2: 从前端参数读取最大迭代次数（优先级高于 Pydantic）
        max_iterations = frontend_max_iterations if frontend_max_iterations is not None else config.defense_layer.get('max_iterations', 3)
        logger.info(f"[Task {task_id}] 对抗收敛循环: 最大迭代次数 = {max_iterations}")

        # 初始化对抗状态
        iteration = 0
        defense_passed = False
        hypothesis_result = None
        fitness_result = None
        red_team_result = None
        defense_result = None
        convergence_result = None

        # 对抗历史追踪（用于收敛检测和审计）
        iteration_history = []
        anchor_passed = False  # 初始化锚定状态

        # ==================== 主对抗循环 ====================
        while iteration < max_iterations and not defense_passed:
            iteration += 1
            logger.info(f"[Task {task_id}] === 对抗迭代 #{iteration}/{max_iterations} ===")

            # ------------------- Sub-Step 6: PI 生成假设 -------------------
            self.update_progress(50 + (iteration * 3), f"迭代#{iteration}: PI 假设生成")

            current_hypothesis = None
            llm_system_error = None

            try:
                from src.prompts.pi_system_prompt import format_pi_prompt_v60, format_pi_prompt_v732
                from src.utils.llm_utils import call_llm

                # V7.1+: 如果不是第一次迭���，注入红方反馈上下文 - 进阶博弈指令 + V7.3.1 锚点记忆锁
                if iteration > 1 and red_team_result:
                    red_feedback = _build_red_team_feedback_context(red_team_result, defense_result, iteration, verified_ids)
                    logger.info(f"[Task {task_id}] 注入红方反馈上下文 (长度: {len(red_feedback)})")
                    augmented_user_input = f"{user_input}\n\n{red_feedback}"
                else:
                    augmented_user_input = user_input

                # V7.3.3 架构升级：迭代 2+ 使用 Schema 预注入 + 钛合金死锁机制
                if iteration > 1:
                    logger.info(f"[Task {task_id}] V7.3.3 启用 Schema 预注入 + 钛合金死锁 (iteration={iteration})")
                    pi_prompt = format_pi_prompt_v732(
                        user_domain=detected_domain,
                        user_idea=augmented_user_input,
                        data_sources=sources,
                        verified_ids=verified_ids,
                        iteration=iteration,
                    )
                    logger.info(f"[Task {task_id}] V7.3.3 Schema 预注入完成，Prompt 长度: {len(pi_prompt)}")
                else:
                    # 第一次迭代使用传统 V6.0 Prompt
                    pi_prompt = format_pi_prompt_v60(
                        user_domain=detected_domain,
                        user_idea=augmented_user_input,
                        data_sources=sources,
                        verified_ids=verified_ids,
                    )

                self.update_progress(55 + (iteration * 3), f"迭代#{iteration}: 调用 PI Agent")
                llm_response = call_llm(pi_prompt)

                # 检查 LLM 调用是否成功
                if not llm_response.get('success'):
                    llm_system_error = f"LLM API 调用失败: {llm_response.get('error', 'Unknown error')}"
                    logger.error(f"[Task {task_id}] {llm_system_error}")
                else:
                    current_hypothesis = llm_response.get('content')
                    if current_hypothesis:
                        hypothesis_result = current_hypothesis
                        logger.info(f"[Task {task_id}] 迭代#{iteration} PI hypothesis generated (tokens: {llm_response.get('tokens_used', 0)})")

                        # ==================== V7.3.3 钛合金死锁 (Titanium Lock) ====================
                        # Python-Level 物理拦截：强制覆写 references 数组为第一轮验证的真实文献
                        if iteration > 1 and verified_ids:
                            try:
                                import json
                                import re
                                import ast

                                # 增强的 JSON 提取方法
                                hypothesis_json = None
                                json_start_idx = -1
                                json_end_idx = -1
                                hypothesis_str = current_hypothesis

                                # 方法1: 查找 ```json 代码块
                                json_block_match = re.search(r'```json\s*', hypothesis_str, re.IGNORECASE)
                                if json_block_match:
                                    # 从代码块开始位置查找 JSON 对象
                                    search_start = json_block_match.end()
                                    # 找到第一个 {
                                    brace_start = hypothesis_str.find('{', search_start)
                                    if brace_start >= 0:
                                        # 使用括号匹配找到对应的 }
                                        depth = 0
                                        in_string = False
                                        escape_next = False
                                        for i in range(brace_start, len(hypothesis_str)):
                                            c = hypothesis_str[i]

                                            if escape_next:
                                                escape_next = False
                                                continue

                                            if c == '\\':
                                                escape_next = True
                                                continue

                                            if c == '"' and not escape_next:
                                                in_string = not in_string
                                                continue

                                            if not in_string:
                                                if c == '{':
                                                    depth += 1
                                                elif c == '}':
                                                    depth -= 1
                                                    if depth == 0:
                                                        json_start_idx = brace_start
                                                        json_end_idx = i + 1
                                                        break

                                # 方法2: 如果没找到代码块，直接查找 JSON 对象
                                if json_start_idx < 0:
                                    brace_start = hypothesis_str.find('{')
                                    if brace_start >= 0:
                                        depth = 0
                                        in_string = False
                                        escape_next = False
                                        for i in range(brace_start, len(hypothesis_str)):
                                            c = hypothesis_str[i]

                                            if escape_next:
                                                escape_next = False
                                                continue

                                            if c == '\\':
                                                escape_next = True
                                                continue

                                            if c == '"' and not escape_next:
                                                in_string = not in_string
                                                continue

                                            if not in_string:
                                                if c == '{':
                                                    depth += 1
                                                elif c == '}':
                                                    depth -= 1
                                                    if depth == 0:
                                                        json_start_idx = brace_start
                                                        json_end_idx = i + 1
                                                        break

                                # 尝试解析提取的 JSON
                                if json_start_idx >= 0 and json_end_idx > json_start_idx:
                                    try:
                                        hypothesis_json_str = hypothesis_str[json_start_idx:json_end_idx]

                                        # 尝试 JSON 解析（双引号）
                                        try:
                                            hypothesis_json = json.loads(hypothesis_json_str)
                                        except json.JSONDecodeError:
                                            # 回退到 Python 字典解析（单引号）
                                            try:
                                                hypothesis_json = ast.literal_eval(hypothesis_json_str)
                                                logger.info(f"[Task {task_id}] [V7.3.3] 📤 使用 Python 字典解析成功")
                                            except (ValueError, SyntaxError) as e:
                                                logger.warning(f"[Task {task_id}] [V7.3.3] ⚠️ Python 字典解析也失败: {e}")
                                                raise

                                        logger.info(f"[Task {task_id}] [V7.3.3] 📤 成功提取 JSON ({len(hypothesis_json_str)} 字符)")
                                    except Exception as je:
                                        logger.warning(f"[Task {task_id}] [V7.3.3] ⚠️ JSON 解析失败: {je}")
                                        hypothesis_json = None

                                if hypothesis_json and isinstance(hypothesis_json, dict):
                                    # 构建原始验证的真实引用列表（钛合金锁定的引用）
                                    titanium_locked_references = []

                                    # 添加 PMID（格式与 Schema 预注入一致）
                                    for pmid in verified_ids.get('pmids', [])[:10]:
                                        titanium_locked_references.append({
                                            "pmid": str(pmid),
                                            "citation": f"[PMID: {pmid}] (系统已验证，钛合金死锁保护)"
                                        })

                                    # 添加 ArXiv
                                    for arxiv_id in verified_ids.get('arxiv_ids', [])[:5]:
                                        titanium_locked_references.append({
                                            "arxiv_id": arxiv_id,
                                            "citation": f"[arXiv: {arxiv_id}] (系统已验证，钛合金死锁保护)"
                                        })

                                    # 添加 DOI
                                    for doi in verified_ids.get('dois', [])[:5]:
                                        titanium_locked_references.append({
                                            "doi": doi,
                                            "citation": f"[DOI: {doi}] (系统已验证，钛合金死锁保护)"
                                        })

                                    # 检测 PI Agent 是否尝试添加虚假引用
                                    original_refs = hypothesis_json.get('references', [])
                                    original_refs_count = len(original_refs)
                                    titanium_locked_count = len(titanium_locked_references)

                                    # 🔥 钛合金死锁：强制覆写！
                                    hypothesis_json['references'] = titanium_locked_references

                                    # 序列化回 JSON
                                    corrected_json_str = json.dumps(hypothesis_json, ensure_ascii=False, indent=2)

                                    # 替换原 hypothesis_result 中的 JSON 部分
                                    hypothesis_result = hypothesis_str[:json_start_idx] + corrected_json_str + hypothesis_str[json_end_idx:]

                                    # 🚨 关键日志：证明钛合金死锁已触发
                                    if original_refs_count > titanium_locked_count:
                                        logger.warning(f"[Task {task_id}] [V7.3.3] 钛合金死锁触发：检测到 PI Agent 试图添加 {original_refs_count - titanium_locked_count} 个虚假引用！已强制覆写。")
                                    elif original_refs_count < titanium_locked_count:
                                        logger.warning(f"[Task {task_id}] [V7.3.3] 钛合金死锁触发：检测到 PI Agent 丢失了 {titanium_locked_count - original_refs_count} 个真实引用！已强制覆写。")
                                    else:
                                        logger.info(f"[Task {task_id}] [V7.3.3] 钛合金死锁生效：已使用第一轮真实 PMID 强制覆写当前 JSON 的引用列表。")

                                    logger.info(f"[Task {task_id}] [V7.3.3] 钛合金锁定引用数: {titanium_locked_count}")

                                else:
                                    logger.warning(f"[Task {task_id}] [V7.3.3] 无法解析 hypothesis JSON，跳过钛合金死锁")
                                    logger.debug(f"[Task {task_id}] [V7.3.3] 假设内容预览: {hypothesis_str[:200]}...")

                            except Exception as lock_error:
                                logger.error(f"[Task {task_id}] [V7.3.3] 钛合金死锁执行异常: {lock_error}")
                                import traceback
                                traceback.print_exc()
                                # 即使死锁失败，也继续流程（使用原始 hypothesis_result）
                        # ==================== V7.3.3 钛合金死锁结束 ====================
                    else:
                        logger.warning(f"[Task {task_id}] 迭代#{iteration} PI hypothesis generation failed: empty content")

            except ImportError as e:
                llm_system_error = f"模块导入失败: {str(e)}"
                logger.error(f"[Task {task_id}] {llm_system_error}")
                traceback.print_exc()

            except ValueError as e:
                llm_system_error = f"配置错误: {str(e)}"
                logger.error(f"[Task {task_id}] {llm_system_error}")
                traceback.print_exc()

            except Exception as e:
                llm_system_error = f"LLM 调用异常: {str(e)}"
                logger.error(f"[Task {task_id}] {llm_system_error}")
                traceback.print_exc()

            # 如果是系统级错误，直接退出循环
            if llm_system_error:
                logger.critical(f"[Task {task_id}] 系统级错误，中止对抗循环")
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                return TaskResult(
                    task_id=task_id,
                    state=TaskState.FAILURE,
                    result_type='system_error',
                    payload={
                        'error_type': 'system_error',
                        'error_message': llm_system_error,
                        'user_input': user_input,
                        'domain': detected_domain,
                        'iteration': iteration,
                        'iteration_history': iteration_history,
                    },
                    start_time=start_time.isoformat(),
                    end_time=end_time.isoformat(),
                    duration=duration,
                    config_version=config_version,
                ).to_dict()

            # ------------------- Sub-Step 7: Hard-Link Anchor 校验 -------------------
            self.update_progress(65 + (iteration * 3), f"迭代#{iteration}: Hard-Link Anchor 锚定校验")

            anchor_passed = True
            anchor_message = ""

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
                    logger.info(f"[Task {task_id}] 迭代#{iteration} Anchor check: {anchor_passed}")

                    if not anchor_passed:
                        logger.warning(f"[Task {task_id}] 迭代#{iteration} Anchor check failed: {anchor_message}")

                except ImportError:
                    logger.warning(f"[Task {task_id}] Hard-Link Anchor not available, skipping check")
                except Exception as e:
                    logger.error(f"[Task {task_id}] Anchor check error: {e}")

            # ------------------- Sub-Step 8: Physical Validator + Hybrid Fitness -------------------
            self.update_progress(70 + (iteration * 3), f"迭代#{iteration}: V6.1 混合适应度评估")

            fitness_result = None
            if hypothesis_result and anchor_passed:
                try:
                    from src.core.hybrid_fitness import HybridFitnessScorer
                    from src.core.physical_validator import PhysicalValidator

                    # 物理铁闸校验
                    validator = PhysicalValidator()
                    physical_result = validator.validate_hypothesis_physical(hypothesis_result)

                    if not physical_result.passed:
                        logger.warning(f"[Task {task_id}] 迭代#{iteration} Physical validation failed: {physical_result.failure_reason}")
                        anchor_passed = False
                        anchor_message = physical_result.failure_reason
                    else:
                        # 混合适应度计算
                        scorer = HybridFitnessScorer()
                        fitness_result = scorer.calculate_fitness(
                            hypothesis_json=hypothesis_result,
                            retrieved_docs=all_papers if all_papers else [],
                        )

                        logger.info(f"[Task {task_id}] 迭代#{iteration} Hybrid fitness: {fitness_result.hybrid_fitness}")
                        logger.info(f"[Task {task_id}]   Vector novelty: {fitness_result.vector_novelty_score}")
                        logger.info(f"[Task {task_id}]   Rigor: {fitness_result.red_team_rigor_score}")

                        # 检查是否达到阈值
                        min_threshold = final_min_score_threshold
                        if fitness_result.hybrid_fitness < min_threshold:
                            logger.warning(f"[Task {task_id}] 迭代#{iteration} Hybrid fitness {fitness_result.hybrid_fitness} < threshold {min_threshold}")
                            anchor_passed = False
                            anchor_message = f"混合适应度得分 {fitness_result.hybrid_fitness} 未达到阈值 {min_threshold}"

                except ImportError as e:
                    logger.warning(f"[Task {task_id}] V6.1 Hybrid Fitness modules not available: {e}")
                except Exception as e:
                    logger.error(f"[Task {task_id}] Hybrid fitness evaluation error: {e}")

            # 如果 Anchor/Physical/Fitness 不及格，记录本次迭代并继续
            if not anchor_passed:
                logger.info(f"[Task {task_id}] 迭代#{iteration} 校验未通过，记录并继续下一轮...")

                iteration_history.append({
                    'iteration': iteration,
                    'status': 'validation_failed',
                    'anchor_passed': anchor_passed,
                    'anchor_message': anchor_message,
                    'fitness_score': fitness_result.hybrid_fitness if fitness_result else 0.0,
                })

                # 如果已经是最后一次迭代，不要继续
                if iteration >= max_iterations:
                    logger.warning(f"[Task {task_id}] 已达最大迭代次数，终止对抗循环")
                    break
                continue  # 继续下一轮迭代

            # ------------------- Sub-Step 9: Red Team Attack -------------------
            self.update_progress(80 + (iteration * 2), f"迭代#{iteration}: 红方攻击审计")

            red_team_result = None
            if hypothesis_result:
                try:
                    from src.agents.red_team_agent import RedTeamAgent
                    red_agent = RedTeamAgent()
                    red_team_result = red_agent.execute({
                        'blue_package': {
                            'hypothesis_data': hypothesis_result,
                            'fitness_data': fitness_result.to_dict() if fitness_result else {},
                            'verified_ids': verified_ids,
                        }
                    })
                    logger.info(f"[Task {task_id}] 迭代#{iteration} Red Team attack completed, verdict: {red_team_result.get('verdict', 'unknown')}")
                except ImportError as e:
                    logger.warning(f"[Task {task_id}] RedTeamAgent not available: {e}")
                except Exception as e:
                    logger.error(f"[Task {task_id}] Red Team error: {e}")

            # ------------------- Sub-Step 10: Defense Committee -------------------
            self.update_progress(87 + (iteration * 2), f"迭代#{iteration}: 防御委员会终审答辩")

            defense_result = None
            defense_passed = False

            if hypothesis_result and red_team_result:
                try:
                    from src.agents.defense_committee_agent import DefenseCommitteeAgent
                    committee = DefenseCommitteeAgent()
                    defense_result = committee.execute({
                        'blue_package': {
                            'hypothesis_data': hypothesis_result,
                            'fitness_data': fitness_result.to_dict() if fitness_result else {},
                        },
                        'red_attack': red_team_result.get('attack_report', {})
                    })
                    defense_passed = defense_result.get('defense_passed', False)
                    logger.info(f"[Task {task_id}] 迭代#{iteration} Defense Committee: {'PASSED ✓' if defense_passed else 'FAILED ✗'}")

                    if defense_passed:
                        logger.info(f"[Task {task_id}] 对抗收敛成功！迭代次数: {iteration}")
                    else:
                        logger.info(f"[Task {task_id}] 迭代#{iteration} 未通过委员会裁决，继续下一轮...")

                except ImportError as e:
                    logger.warning(f"[Task {task_id}] DefenseCommitteeAgent not available: {e}")
                except Exception as e:
                    logger.error(f"[Task {task_id}] Defense Committee error: {e}")

            # 记录本次迭代历史
            iteration_history.append({
                'iteration': iteration,
                'status': 'defense_passed' if defense_passed else 'defense_failed',
                'anchor_passed': anchor_passed,
                'fitness_score': fitness_result.hybrid_fitness if fitness_result else 0.0,
                'red_team_verdict': red_team_result.get('verdict', 'N/A') if red_team_result else 'N/A',
                'defense_verdict': defense_result.get('final_verdict', 'N/A') if defense_result else 'N/A',
            })

            # 如果通过防御委员会，退出循环
            if defense_passed:
                break

            # 如果未通过且未达到最大迭代次数，继续下一轮
            if iteration < max_iterations and not defense_passed:
                logger.info(f"[Task {task_id}] 对抗继续，准备进入迭代 #{iteration + 1}...")
                continue

        # 循环结束后的收敛检测
        self.update_progress(89, "收敛性检测")

        convergence_result = None
        if hypothesis_result and defense_passed:
            try:
                from src.core.convergence_detector import ConvergenceDetector, ConvergenceState
                detector = ConvergenceDetector()
                convergence_result = detector.check_convergence(
                    hypothesis_data=hypothesis_result,
                    fitness_score=fitness_result.hybrid_fitness if fitness_result else 0.0,
                    rigor_score=red_team_result.get('rigor_report', {}).get('rigor_score', 0.0) if red_team_result else 0.0,
                    defense_verdict=defense_result.get('final_verdict', '') if defense_result else ''
                )
                logger.info(f"[Task {task_id}] Convergence state: {convergence_result.state.value}")
            except ImportError as e:
                logger.warning(f"[Task {task_id}] ConvergenceDetector not available: {e}")
            except Exception as e:
                logger.error(f"[Task {task_id}] Convergence check error: {e}")

        # 如果达到最大迭代次数仍未通过，记录收敛失败
        if iteration >= max_iterations and not defense_passed:
            logger.warning(f"[Task {task_id}] 对抗收敛失败: 达到最大迭代次数 {max_iterations} 仍未通过委员会裁决")
            # 创建收敛失败结果对象
            try:
                from src.core.convergence_detector import ConvergenceState
                convergence_result = type('obj', (object,), {
                    'state': ConvergenceState.MAX_ITERATIONS_EXCEEDED if hasattr(ConvergenceState, 'MAX_ITERATIONS_EXCEEDED') else ConvergenceState.DIVERGENT,
                    'iteration': iteration
                })()
            except ImportError:
                convergence_result = type('obj', (object,), {
                    'state': type('obj', (object,), {'value': 'max_iterations_exceeded'}),
                    'iteration': iteration
                })()

        # ==================== Phase 11: 强制聚合打分数据 ====================
        self.update_progress(90, "聚合审计数据")

        # 强制构建完整的审计上下文（不能缺失）
        audit_context = {
            'hybrid_fitness': {
                'score': fitness_result.hybrid_fitness if fitness_result else 0.0,
                'vector_novelty': fitness_result.vector_novelty_score if fitness_result else 0.0,
                'red_team_rigor': fitness_result.red_team_rigor_score if fitness_result else 0.0,
                'breakdown': fitness_result.to_dict() if fitness_result else {}
            },
            'red_team_attack': {
                'enabled': red_team_result is not None,
                'verdict': red_team_result.get('verdict', 'not_executed') if red_team_result else 'not_executed',
                'critical_flaws': red_team_result.get('critical_flaws', []) if red_team_result else [],
                'severe_issues': red_team_result.get('severe_issues', []) if red_team_result else [],
                'rigor_score': red_team_result.get('rigor_report', {}).get('rigor_score', 0.0) if red_team_result else 0.0,
            },
            'defense_committee': {
                'enabled': defense_result is not None,
                'passed': defense_passed,
                'verdict': defense_result.get('final_verdict', 'not_executed') if defense_result else 'not_executed',
                'critical_issues': defense_result.get('critical_issues', []) if defense_result else [],
            },
            'convergence': {
                'state': convergence_result.state.value if convergence_result else 'not_checked',
                'iteration': iteration,  # V7.2: 使用实际迭代次数
                'max_iterations': max_iterations,
            },
            # V7.2 新增：对抗迭代历史
            'iteration_history': iteration_history,
        }

        # 记录完整审计数据到日志
        logger.info(f"[Task {task_id}] === V7.2 系统硬核审计面板 ===")
        logger.info(f"[Task {task_id}] 对抗迭代次数: {iteration}/{max_iterations}")
        logger.info(f"[Task {task_id}] Hybrid Fitness: {audit_context['hybrid_fitness']['score']:.2f}")
        logger.info(f"[Task {task_id}] Red Team Verdict: {audit_context['red_team_attack']['verdict']}")
        logger.info(f"[Task {task_id}] Red Team Rigor: {audit_context['red_team_attack']['rigor_score']:.2f}")
        logger.info(f"[Task {task_id}] Defense Passed: {audit_context['defense_committee']['passed']}")
        logger.info(f"[Task {task_id}] Convergence: {audit_context['convergence']['state']}")

        # ==================== Phase 12: 生成最终报告 ====================
        self.update_progress(95, "生成最终报告")

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
                'fitness': fitness_result.to_dict() if fitness_result else None,
                'verified_ids': verified_ids,
                'domain': detected_domain,
                'sources': sources,
                # V7.2 强制：完整审计上下文（包含迭代历史）
                'audit_context': audit_context,
                'red_team_result': red_team_result,
                'defense_result': defense_result,
                # V7.2: 使用实际迭代数据
                'convergence_result': {
                    'state': convergence_result.state.value if convergence_result else 'not_checked',
                    'iteration': iteration,
                    'max_iterations': max_iterations,
                    'iterations_used': iteration,
                },
                # V7.2 新增：对抗迭代历史（用于报告展示）
                'iteration_history': iteration_history,
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

        # ==================== Phase 13: Webhook 回调 ====================
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

        logger.info(f"任务完成: 耗时 {duration:.2f}s")
        logger.info(f"状态: {state.value}")
        logger.info(f"API调用次数: {api_calls_used}")
        logger.info(f"配置版本: {config_version}")

        # V7.1: 清除 Task 日志上下文
        clear_task_context()

        return result.to_dict()

    except SoftTimeLimitExceeded:
        logger.warning("任务软超时触发")
        clear_task_context()
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
        logger.critical("任务硬超时触发")
        clear_task_context()
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
                'exception_type': type(e).__name__
            }
        )
        clear_task_context()

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