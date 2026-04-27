# -*- coding: utf-8 -*-
"""
V7.5 Celery 异步任务分发系统 - 凤凰协议版

核心改进：
1. 集成凤凰协议状态机（演化型逻辑替代阻断型）
2. 物理公理冲突触发重写而非拦截
3. Science Score 趋势检测 + 外部补偿触发
4. 版本演进追踪 + Promise Score 计算
5. 最大迭代次数 8 次（比之前 4 次多一倍）

作者: V7.5 架构工程师
日期: 2026-04-19
"""

from celery import Celery, Task
from celery.result import AsyncResult
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import os
import re
import sys
import traceback
import logging
import numpy as np

# ==================== 加载 .env 文件 ====================
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
env_file = project_root / '.env'

if env_file.exists():
    load_dotenv(env_file, encoding='utf-8', override=True)

# ==================== 日志系统 ====================
from src.utils.logger import (
    get_central_logger,
    set_task_context,
    clear_task_context,
    AUDIT_LEVEL
)

logger = get_central_logger()

# ==================== V7.5 凤凰协议模块导入 ====================
from src.core.phoenix_state_machine import (
    PhoenixState,
    PhoenixTransitionTrigger,
    PhoenixStateMachine,
    PhoenixContext,
    PHOENIX_CONFIG,
    is_terminal_state,
    is_evolution_state,
    get_state_description,
)

from src.core.hypothesis_version_manager import (
    HypothesisVersionManager,
    HypothesisVersion,
)

from src.core.score_trend_detector import (
    ScoreTrendDetector,
    ScoreTrendAnalysis,
)

from src.core.alternative_path_generator import (
    AlternativePathGenerator,
)

from src.core.promise_score_calculator import (
    PromiseScoreCalculator,
    PromiseScoreResult,
)

from src.core.methodology_patch_priority import (
    MethodologyPatchPriorityManager,
    PatchPriority,
    get_solution_keywords_for_search,
)

from src.prompts.phoenix_rewrite_prompt import (
    generate_phoenix_rewrite_prompt,
    generate_methodology_patch_prompt,
    generate_external_compensation_prompt,
    increment_version,
)

# ==================== V7.5 输出增强模块 ====================
from src.core.output_enhancer import (
    OutputEnhancer,
    ImplementationRoadmap,
    InnovationAnalysis,
    FrontierAnalysis,
    create_output_enhancer,
)

# ==================== JSON 序列化辅助函数 ====================
def convert_numpy_types(obj):
    """将 numpy 类型转换为 Python 原生类型，以便 JSON 序列化"""
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return convert_numpy_types(obj.tolist())
    else:
        return obj

# ==================== 阶段输出留档辅助函数 ====================
def _get_stage_output_dir(task_id: str) -> Path:
    """获取阶段输出目录"""
    stage_dir = project_root / 'outputs' / 'stages' / task_id
    stage_dir.mkdir(parents=True, exist_ok=True)
    return stage_dir


def _build_stage_markdown(title: str, data: Any) -> str:
    """将阶段数据转为可读 Markdown"""
    normalized = convert_numpy_types(data)
    if isinstance(normalized, str):
        body = normalized
    else:
        try:
            body = json.dumps(normalized, ensure_ascii=False, indent=2)
            body = f"```json\n{body}\n```"
        except Exception:
            body = f"```\n{str(normalized)}\n```"

    return f"# {title}\n\n{body}\n"


def _write_stage_output(task_id: str, order: int, stage_name: str, data: Any) -> Dict[str, str]:
    """写入阶段输出文件"""
    stage_dir = _get_stage_output_dir(task_id)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]+', '_', stage_name.strip().lower())
    base_name = f"stage_{order:02d}_{safe_name}"
    json_path = stage_dir / f"{base_name}.json"
    md_path = stage_dir / f"{base_name}.md"

    normalized = convert_numpy_types(data)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(_build_stage_markdown(stage_name, normalized))

    return {
        'order': order,
        'stage': stage_name,
        'json_path': str(json_path),
        'markdown_path': str(md_path),
    }


def _write_stage_index(task_id: str, stage_outputs: List[Dict[str, str]]) -> str:
    """写入阶段输出索引"""
    stage_dir = _get_stage_output_dir(task_id)
    index_path = stage_dir / 'INDEX.md'

    sorted_outputs = sorted(stage_outputs, key=lambda item: item.get('order', 999))
    lines = [
        f"# Task {task_id} 阶段输出索引",
        '',
        '## 阶段文件',
        ''
    ]

    for item in sorted_outputs:
        stage = item.get('stage', 'unknown')
        json_name = Path(item.get('json_path', '')).name
        md_name = Path(item.get('markdown_path', '')).name
        order = item.get('order', '-')
        lines.append(f"### {order}. {stage}")
        lines.append(f"- Markdown: [{md_name}](./{md_name})")
        lines.append(f"- JSON: [{json_name}](./{json_name})")
        lines.append('')

    with open(index_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    return str(index_path)


# ==================== 默认值常量 ====================
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_SOFT_TIME_LIMIT = 600  # V7.5: 增加到 10 分钟（演化迭代更多）
DEFAULT_HARD_TIME_LIMIT = 900  # V7.5: 增加到 15 分钟
DEFAULT_MAX_RETRIES = 3
DEFAULT_WEBHOOK_TIMEOUT = 30

# ==================== Celery 应用实例（延迟初始化） ====================
_celery_app: Optional[Celery] = None
_celery_lock = None


def get_celery_app() -> Celery:
    """获取 Celery 应用实例（延迟初始化）"""
    global _celery_app, _celery_lock

    if _celery_lock is None:
        import threading
        _celery_lock = threading.Lock()

    if _celery_app is None:
        with _celery_lock:
            if _celery_app is None:
                redis_url = os.getenv('REDIS_URL', DEFAULT_REDIS_URL)
                soft_limit = int(os.getenv('TASK_SOFT_TIME_LIMIT', str(DEFAULT_SOFT_TIME_LIMIT)))
                hard_limit = int(os.getenv('TASK_HARD_TIME_LIMIT', str(DEFAULT_HARD_TIME_LIMIT)))
                max_retries = int(os.getenv('TASK_MAX_RETRIES', str(DEFAULT_MAX_RETRIES)))

                logger.info(
                    f"[Celery V7.5] 配置加载:\n"
                    f"  Redis: {redis_url}\n"
                    f"  Soft Timeout: {soft_limit}s\n"
                    f"  Hard Timeout: {hard_limit}s\n"
                    f"  Phoenix Max Iterations: {PHOENIX_CONFIG['MAX_PHOENIX_ITERATIONS']}"
                )

                # 自定义 JSON encoder 处理 numpy 类型
                import json
                from kombu.serialization import register

                class NumpyJSONEncoder(json.JSONEncoder):
                    def default(self, obj):
                        import numpy as np
                        if isinstance(obj, (np.integer, np.int64, np.int32)):
                            return int(obj)
                        elif isinstance(obj, (np.floating, np.float64, np.float32)):
                            return float(obj)
                        elif isinstance(obj, np.ndarray):
                            return obj.tolist()
                        return super().default(obj)

                def numpy_json_dumps(data):
                    return json.dumps(data, cls=NumpyJSONEncoder)

                # 注册自定义序列化器
                register('numpy_json', numpy_json_dumps, json.loads,
                         content_type='application/json',
                         content_encoding='utf-8')

                _celery_app = Celery(
                    'research_hypothesis_agent_v75',
                    broker=redis_url,
                    backend=redis_url,
                    includes=['src.core.celery_tasks_v75'],
                )

                _celery_app.conf.update(
                    task_serializer='numpy_json',
                    accept_content=['numpy_json', 'json'],
                    result_serializer='numpy_json',
                    timezone='Asia/Shanghai',
                    enable_utc=True,
                    task_soft_time_limit=soft_limit,
                    task_time_limit=hard_limit,
                    task_max_retries=max_retries,
                    task_default_retry_delay=60,
                    task_acks_late=True,
                    task_reject_on_worker_lost=True,
                    result_expires=3600,
                    worker_prefetch_multiplier=1,
                    worker_max_tasks_per_child=100,
                    broker_pool_limit=10,
                    broker_connection_max_retry=5,
                    task_default_queue='research',
                    task_queues={
                        'research': {
                            'exchange': 'research',
                            'routing_key': 'research',
                        }
                    },
                )

    return _celery_app


celery_app = None  # 临时占位


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
    phoenix_protocol: Optional[Dict] = None  # V7.5 新增
    version_evolution: Optional[Dict] = None  # V7.5 新增
    promise_score: Optional[Dict] = None  # V7.5 新增

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
            'phoenix_protocol': self.phoenix_protocol,
            'version_evolution': self.version_evolution,
            'promise_score': self.promise_score,
        }


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


# ==================== V7.5 主任务：假设生成（凤凰���议版） ====================
def hypothesis_generation_task_v75_impl(
    self: ProgressTrackingTask,
    user_input: str,
    user_domain: str = None,
    webhook_url: str = None,
    session_id: str = None,
    **kwargs
) -> Dict:
    """
    V7.5 主任务实现：假设生成全流程（凤凰协议版）

    核心改进：
    1. 使用凤凰协议状态机驱动迭代循环
    2. 物理公理冲突触发重写而非拦截
    3. Science Score 趋势检测 + 外部补偿触发
    4. 版本演进追踪 + Promise Score 计算
    """
    task_id = str(self.request.id)
    start_time = datetime.now()

    set_task_context(task_id=task_id, agent_name='PhoenixProtocol')

    logger.info(f"[Task {task_id}] V7.5 凤凰协议启动")
    logger.info(f"[Task {task_id}] User input: {user_input[:100]}...")
    logger.info(f"[Task {task_id}] Phoenix Config: MAX_ITERATIONS={PHOENIX_CONFIG['MAX_PHOENIX_ITERATIONS']}")

    # ==================== 前端参数读取 ====================
    frontend_hard_cap = kwargs.get('hard_cap')
    frontend_min_score_threshold = kwargs.get('min_score_threshold')
    frontend_max_iterations = kwargs.get('max_iterations')
    frontend_v7_defenses = kwargs.get('v7_defenses', {})

    # 文献检索筛选参数
    literature_min_if = kwargs.get('min_if', 3.0)
    literature_start_year = kwargs.get('start_year', 2020)
    literature_end_year = kwargs.get('end_year', datetime.now().year)
    literature_min_citations = kwargs.get('min_citations', 10)

    logger.info(f"[Task {task_id}] Literature filters: IF>={literature_min_if}, years={literature_start_year}-{literature_end_year}, citations>={literature_min_citations}")

    # ==================== 配置加载 ====================
    try:
        from src.core.program_config import get_current_config
        config = get_current_config(force_reload=True)
        config_version = config.config_version
    except Exception as e:
        logger.warning(f"[Task {task_id}] 配置加载失败，使用默认值: {e}")
        config = None
        config_version = 'v7.5-default'

    # ==================== V7.5 核心组件初始化 ====================
    phoenix_machine = PhoenixStateMachine()
    version_manager = HypothesisVersionManager()
    trend_detector = ScoreTrendDetector()
    alternative_generator = AlternativePathGenerator()
    promise_calculator = PromiseScoreCalculator()

    # V7.6: 设置原研究主题（用于 Level 3 检索）
    phoenix_machine.context.original_research_topic = user_input

    # V7.7: 检测笼统输入（从 sanitization 结果中获取）
    if 'classification' in dir() and hasattr(classification, 'is_broad_input'):
        phoenix_machine.context.is_broad_input = classification.is_broad_input
        phoenix_machine.context.broad_input_type = classification.broad_input_type
        if classification.is_broad_input:
            logger.info(f"[Task {task_id}] 检测到笼统输入: {classification.broad_input_type}")

    logger.info(f"[Task {task_id}] 凤凰协议组件初始化完成")

    try:
        # ==================== Phase 1: 语义分类预检 ====================
        self.update_progress(5, "语义分类预检")

        try:
            from src.core.semantic_classifier import classify_intent
            classification = classify_intent(user_input)

            if not classification.is_valid:
                logger.warning(f"[Task {task_id}] 语义分类拦截: {classification.reasoning}")
                return TaskResult(
                    task_id=task_id,
                    state=TaskState.FAILURE,
                    result_type='sanitization_blocked',
                    error=f"输入被系统安全网关拦截: {classification.reasoning}",
                    start_time=start_time.isoformat(),
                    end_time=datetime.now().isoformat(),
                ).to_dict()

            logger.info(f"[Task {task_id}] 语义分类通过: type={classification.intent_type.value}")
            user_input = classification.cleaned_input

        except ImportError:
            logger.warning(f"[Task {task_id}] 语义分类器不可用，跳过预检")

        # ==================== Phase 2: Global Fuse 初始化 ====================
        self.update_progress(10, "Global Fuse 初始化")

        hard_cap = frontend_hard_cap if frontend_hard_cap is not None else 10

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
        except ImportError:
            detected_domain = user_domain or 'unknown'
            sources = ['pubmed']

        logger.info(f"[Task {task_id}] Domain: {detected_domain}, Sources: {sources}")

        # ==================== Phase 4: 异步文献检索 ====================
        self.update_progress(25, "异步文献检索启动")

        verified_ids = {'pmids': [], 'arxiv_ids': [], 'dois': []}
        all_papers = []

        pubmed_max = 50
        arxiv_max = 20

        try:
            import concurrent.futures

            def fetch_pubmed():
                try:
                    from src.utils.pubmed import PubMedSearcher
                    pubmed_searcher = PubMedSearcher()
                    search_result = pubmed_searcher.search_by_idea(
                        user_input,
                        max_results=pubmed_max,
                        start_year=literature_start_year,
                        end_year=literature_end_year,
                        min_if=literature_min_if
                    )
                    papers = search_result.get('papers', [])
                    for p in papers:
                        p['source'] = 'pubmed'
                    pmids = [p.get('pmid') for p in papers if p.get('pmid')]
                    logger.info(f"[Task {task_id}] PubMed 检索: {len(papers)}篇 (IF>={literature_min_if}, {literature_start_year}-{literature_end_year})")
                    return {'source': 'pubmed', 'papers': papers, 'pmids': pmids, 'success': bool(papers)}
                except Exception as e:
                    logger.error(f"[Task {task_id}] PubMed error: {e}")
                    return {'source': 'pubmed', 'papers': [], 'pmids': [], 'success': False}

            def fetch_arxiv():
                try:
                    from src.data_sources.arxiv_searcher import ArXivSearcher
                    arxiv_searcher = ArXivSearcher()
                    # ArXiv支持时间范围筛选，但不支持min_citations参数，需要在结果中筛选
                    arxiv_result = arxiv_searcher.search(
                        user_input,
                        max_results=arxiv_max,
                        start_year=literature_start_year,
                        end_year=literature_end_year
                    )
                    papers = arxiv_result.get('papers', [])
                    # 对ArXiv论文进行引用数筛选（因为ArXiv无IF，使用引用数作为替代指标）
                    filtered_papers = [p for p in papers if p.get('citation_count', 0) >= literature_min_citations]
                    for p in filtered_papers:
                        p['source'] = 'arxiv'
                    arxiv_ids = [p.get('arxiv_id') for p in filtered_papers if p.get('arxiv_id')]
                    logger.info(f"[Task {task_id}] ArXiv 检索: {len(filtered_papers)}篇 (引用>={literature_min_citations}, 原始{len(papers)}篇, {literature_start_year}-{literature_end_year})")
                    return {'source': 'arxiv', 'papers': filtered_papers, 'arxiv_ids': arxiv_ids, 'success': bool(filtered_papers)}
                except Exception as e:
                    logger.error(f"[Task {task_id}] ArXiv error: {e}")
                    return {'source': 'arxiv', 'papers': [], 'arxiv_ids': [], 'success': False}

            search_tasks = [fetch_pubmed, fetch_arxiv]

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future_to_task = {executor.submit(task): task for task in search_tasks}

                futures_done, _ = concurrent.futures.wait(future_to_task.keys(), timeout=120)

                for future in futures_done:
                    result = future.result(timeout=5)
                    if result['source'] == 'pubmed':
                        verified_ids['pmids'] = result['pmids']
                        all_papers.extend(result['papers'])
                    elif result['source'] == 'arxiv':
                        verified_ids['arxiv_ids'] = result['arxiv_ids']
                        all_papers.extend(result['papers'])

            logger.info(f"[Task {task_id}] 文献检索完成: PMIDs={len(verified_ids['pmids'])}, ArXiv={len(verified_ids['arxiv_ids'])}")

        except Exception as e:
            logger.error(f"[Task {task_id}] 文献检索异常: {e}")

        # 断链熔断检查
        total_verified = len(verified_ids['pmids']) + len(verified_ids['arxiv_ids']) + len(verified_ids['dois'])
        if total_verified == 0:
            logger.critical(f"[Task {task_id}] 断链熔断：所有数据源均未返回文献")
            return TaskResult(
                task_id=task_id,
                state=TaskState.FAILURE,
                result_type='literature_unavailable',
                error='文献检索服务不可用：PubMed/ArXiv 均无响应',
                start_time=start_time.isoformat(),
                end_time=datetime.now().isoformat(),
            ).to_dict()

        # ==================== Phase 5-10: 凤凰协议演化循环 ====================
        self.update_progress(50, "启动凤凰协议演化循环")

        stage_outputs = []
        stage_outputs.append(_write_stage_output(task_id, 0, 'user_input', {
            'user_input': user_input,
            'user_domain': user_domain,
            'detected_domain': detected_domain,
            'sources': sources,
            'verified_ids': verified_ids,
        }))

        # 初始化演化上下文
        hypothesis_result = None
        fitness_result = None
        red_team_result = None
        defense_result = None
        current_hypothesis_str = None

        # 创建初始版本
        version_manager.create_initial_version({}, iteration=1)

        # 主演化循环（凤凰协议驱动）
        phoenix_context = phoenix_machine.context

        while not is_terminal_state(phoenix_context.current_state):
            phoenix_context.phoenix_iterations += 1
            iteration = phoenix_context.phoenix_iterations

            if iteration > PHOENIX_CONFIG['MAX_PHOENIX_ITERATIONS']:
                logger.warning(f"[Task {task_id}] 超过凤凰迭代上限，强制终止")
                phoenix_machine.transition(PhoenixTransitionTrigger.MAX_ITERATIONS_EXCEEDED)
                break

            logger.info(f"[Task {task_id}] === 凤凰迭代 #{iteration} | 状态: {get_state_description(phoenix_context.current_state)} ===")

            # ------------------- 状态处理分发 -------------------
            current_state = phoenix_context.current_state

            if current_state == PhoenixState.INITIAL:
                # 初始状态 → 生成假设
                phoenix_machine.transition(PhoenixTransitionTrigger.HYPOTHESIS_READY)
                continue

            elif current_state == PhoenixState.HYPOTHESIS_GEN:
                # 假设生成阶段
                self.update_progress(50 + (iteration * 4), f"迭代#{iteration}: PI 假设生成")

                hypothesis_result = _execute_hypothesis_gen(
                    self, task_id, user_input, detected_domain, sources, verified_ids,
                    phoenix_context, iteration
                )

                if hypothesis_result:
                    current_hypothesis_str = hypothesis_result

                    # 解析并保存假设内容到版本管理器
                    try:
                        import json
                        # 尝试解析 JSON（hypothesis_result 是字符��）
                        hypothesis_dict = json.loads(hypothesis_result) if isinstance(hypothesis_result, str) else hypothesis_result
                        version_manager.update_hypothesis_content(
                            version_manager.current_version,
                            hypothesis_dict
                        )
                        logger.info(f"[Task {task_id}] 假设内容已保存到版本 {version_manager.current_version}")
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"[Task {task_id}] 假设内容解析失败: {e}，将保存原始字符串")
                        # 如果解析失败，将原始字符串保存为字典
                        version_manager.update_hypothesis_content(
                            version_manager.current_version,
                            {'raw_content': hypothesis_result}
                        )

                    stage_outputs.append(_write_stage_output(task_id, iteration * 10 + 1, f'iteration_{iteration}_hypothesis', hypothesis_result))

                    # 物理锚定校验（V7.5: 不拦截，触发重写）
                    physical_result = _check_physical_anchor(
                        hypothesis_result, phoenix_context, alternative_generator
                    )

                    if not physical_result.passed and physical_result.is_recoverable:
                        logger.warning(f"[Task {task_id}] 物理冲突检测，触发 PHOENIX_REWRITE")
                        phoenix_context.physical_conflict_detected = True
                        phoenix_context.alternative_paths = physical_result.alternative_path_suggestions
                        phoenix_context.rewrite_instruction = physical_result.rewrite_instruction
                        phoenix_machine.transition(PhoenixTransitionTrigger.PHYSICAL_AXIOM_CONFlict)
                        continue

                    elif not physical_result.passed and not physical_result.is_recoverable:
                        logger.critical(f"[Task {task_id}] 不可恢复物理冲突，触发 HARD_FAILURE")
                        phoenix_machine.transition(PhoenixTransitionTrigger.UNRECOVERABLE_CONFLICT)
                        continue

                    # 适应度评估
                    fitness_result = _evaluate_fitness(hypothesis_result, all_papers)

                    if fitness_result:
                        score = fitness_result.hybrid_fitness
                        phoenix_context.record_score(score)
                        version_manager.update_version_scores(
                            version_manager.current_version,
                            score,
                            fitness_result.hybrid_fitness,
                            False,
                        )

                        logger.info(f"[Task {task_id}] Science Score: {score:.2f}")

                        # 趋势检测
                        trend_analysis = trend_detector.analyze_trend(phoenix_context.score_history)

                        if trend_analysis.should_trigger_compensation:
                            logger.warning(f"[Task {task_id}] 分数停滞检测，触发 EXTERNAL_COMPENSATION")
                            phoenix_machine.transition(PhoenixTransitionTrigger.SCORE_STagnant_DETECTED)
                            continue

                    # 进入红方攻击
                    phoenix_machine.transition(PhoenixTransitionTrigger.RED_ATTACK_START)
                    continue

                else:
                    logger.warning(f"[Task {task_id}] 假设生成失败")
                    if iteration >= PHOENIX_CONFIG['MAX_PHOENIX_ITERATIONS']:
                        phoenix_context.failure_reason = "PI 假设生成失败且达到最大迭代次数"
                        phoenix_machine.transition(PhoenixTransitionTrigger.MAX_ITERATIONS_EXCEEDED)
                        break
                    continue

            elif current_state == PhoenixState.RED_ATTACK:
                # 红方攻击阶段
                self.update_progress(60 + (iteration * 4), f"迭代#{iteration}: 红方攻击审计")

                red_team_result = _execute_red_attack(hypothesis_result, fitness_result)

                if red_team_result:
                    attack_report = red_team_result.get('attack_report', {})
                    phoenix_context.red_attack_report = attack_report
                    phoenix_context.red_attack_types = _extract_attack_types(attack_report)

                    logger.info(f"[Task {task_id}] 红方 verdict: {attack_report.get('verdict', 'unknown')}")
                    stage_outputs.append(_write_stage_output(task_id, iteration * 10 + 2, f'iteration_{iteration}_red_team', red_team_result))

                # V7.7: 记录攻击类型失败（用于回溯检测）
                if red_team_result and attack_report.get('verdict') == 'failed':
                    phoenix_context.record_attack_type_failure(phoenix_context.red_attack_types)

                    # 检查是否需要触发回溯
                    if phoenix_context.should_trigger_rollback():
                        logger.warning(f"[Task {task_id}] 攻击类型连续失败，触发回溯")
                        phoenix_machine.transition(PhoenixTransitionTrigger.ATTACK_TYPE_UNSOLVABLE)
                        continue

                # 进入蓝方答辩
                phoenix_machine.transition(PhoenixTransitionTrigger.BLUE_DEFENSE_START)
                continue

            elif current_state == PhoenixState.BLUE_DEFENSE:
                # 蓝方答辩阶段
                self.update_progress(70 + (iteration * 4), f"迭代#{iteration}: 防御委员会终审")

                defense_result = _execute_defense_committee(hypothesis_result, fitness_result, red_team_result)
                stage_outputs.append(_write_stage_output(task_id, iteration * 10 + 3, f'iteration_{iteration}_defense', defense_result or {}))

                defense_passed = defense_result.get('defense_passed', False) if defense_result else False

                logger.info(f"[Task {task_id}] 防御委员会: {'PASSED' if defense_passed else 'FAILED'}")

                if defense_passed:
                    logger.info(f"[Task {task_id}] 凤凰协议成功！迭代次数: {iteration}")
                    phoenix_machine.transition(PhoenixTransitionTrigger.SUCCESS_THRESHOLD_REACHED)
                    continue
                else:
                    # 检查分数趋势
                    trend_analysis = trend_detector.analyze_trend(phoenix_context.score_history)

                    if trend_analysis.should_trigger_compensation:
                        phoenix_machine.transition(PhoenixTransitionTrigger.SCORE_STagnant_DETECTED)
                    else:
                        phoenix_machine.transition(PhoenixTransitionTrigger.BLUE_DEFENSE_FAILURE)
                    continue

            elif current_state == PhoenixState.PHOENIX_REWRITE:
                # 物理锚定重写阶段（凤凰协议核心创新）
                self.update_progress(55 + (iteration * 4), f"迭代#{iteration}: 物理锚定重写")

                phoenix_context.rewrite_attempts += 1
                logger.info(f"[Task {task_id}] PHOENIX_REWRITE 第 {phoenix_context.rewrite_attempts} 次尝试")

                # 生成重写指令
                rewrite_prompt, new_version = generate_phoenix_rewrite_prompt(
                    current_hypothesis_str,
                    phoenix_context.alternative_paths,
                    phoenix_context.current_version
                )

                # 执行重写
                hypothesis_result = _execute_rewrite(
                    self, task_id, rewrite_prompt, phoenix_context
                )

                if hypothesis_result:
                    phoenix_context.current_version = new_version
                    version_manager.create_rewrite_version(
                        rewrite_type='physical_fix',
                        rewrite_log=[phoenix_context.alternative_paths[0]] if phoenix_context.alternative_paths else [],
                        new_hypothesis={},
                        iteration=iteration,
                    )
                    # 保存重写后的假设内容
                    try:
                        import json
                        hypothesis_dict = json.loads(hypothesis_result) if isinstance(hypothesis_result, str) else hypothesis_result
                        version_manager.update_hypothesis_content(
                            new_version,
                            hypothesis_dict
                        )
                        logger.info(f"[Task {task_id}] 物理重写内容已保存到版本 {new_version}")
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"[Task {task_id}] 物理重写内容解析失败: {e}")
                        version_manager.update_hypothesis_content(
                            new_version,
                            {'raw_content': hypothesis_result}
                        )
                    logger.info(f"[Task {task_id}] 物理重写完成，版本: {new_version}")
                    stage_outputs.append(_write_stage_output(task_id, iteration * 10 + 4, f'iteration_{iteration}_rewrite', hypothesis_result))
                    phoenix_machine.transition(PhoenixTransitionTrigger.REWRITE_COMPLETED)
                else:
                    if phoenix_context.rewrite_attempts >= PHOENIX_CONFIG['MAX_REWRITE_ATTEMPTS']:
                        phoenix_machine.transition(PhoenixTransitionTrigger.UNRECOVERABLE_CONFLICT)
                continue

            elif current_state == PhoenixState.PHOENIX_PATCH:
                # 方法论补丁注入阶段 - V7.6 分级检索增强
                self.update_progress(65 + (iteration * 4), f"迭代#{iteration}: 方法论补丁注入")

                phoenix_context.patch_attempts += 1
                logger.info(f"[Task {task_id}] PHOENIX_PATCH 第 {phoenix_context.patch_attempts} 次尝试")

                # V7.6: 获取当前检索级别（根据补丁有效性历史动态调整）
                search_level = phoenix_context.get_next_search_level()
                logger.info(f"[Task {task_id}] 使用检索级别: Level {search_level}")

                # V7.6: 分级检索解决方案文献
                solution_papers = _search_methodology_solutions(
                    phoenix_context.red_attack_types,
                    search_level=search_level,
                    original_topic=phoenix_context.original_research_topic
                )

                # 生成补丁指令
                patch_prompt, new_version = generate_methodology_patch_prompt(
                    phoenix_context.red_attack_types,
                    _build_attack_summary(phoenix_context.red_attack_report),
                    solution_papers,
                    phoenix_context.current_version
                )

                # 执行补丁注入
                hypothesis_result = _execute_patch(
                    self, task_id, patch_prompt, hypothesis_result, phoenix_context
                )

                if hypothesis_result:
                    phoenix_context.current_version = new_version
                    version_manager.create_rewrite_version(
                        rewrite_type='methodology_patch',
                        rewrite_log=[],
                        new_hypothesis={},
                        iteration=iteration,
                        red_attack_types=phoenix_context.red_attack_types,
                    )
                    # 保存补丁后的假设内容
                    try:
                        import json
                        hypothesis_dict = json.loads(hypothesis_result) if isinstance(hypothesis_result, str) else hypothesis_result
                        version_manager.update_hypothesis_content(
                            new_version,
                            hypothesis_dict
                        )
                        logger.info(f"[Task {task_id}] 补丁注入内容已保存到版本 {new_version}")
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"[Task {task_id}] 补丁注入内容解析失败: {e}")
                        version_manager.update_hypothesis_content(
                            new_version,
                            {'raw_content': hypothesis_result}
                        )
                    logger.info(f"[Task {task_id}] 补丁注入完成，版本: {new_version}")
                    logger.info(f"[Task {task_id}] 使用检索级别: Level {search_level}, 解决方案数: {len(solution_papers)}")
                    stage_outputs.append(_write_stage_output(task_id, iteration * 10 + 5, f'iteration_{iteration}_patch', {
                        'hypothesis': hypothesis_result,
                        'search_level': search_level,
                        'solution_papers': solution_papers[:5],
                    }))
                    phoenix_machine.transition(PhoenixTransitionTrigger.PATCH_APPLIED)
                else:
                    if phoenix_context.patch_attempts >= PHOENIX_CONFIG['MAX_PATCH_ATTEMPTS']:
                        phoenix_context.failure_reason = "方法论补丁注入失败且达到最大尝试次数"
                        phoenix_machine.transition(PhoenixTransitionTrigger.MAX_ITERATIONS_EXCEEDED)
                        break
                continue

            elif current_state == PhoenixState.PHOENIX_RETRY:
                # 补丁后重试阶段 - V7.6/V7.7 补丁有效性追踪 + 回溯检测
                self.update_progress(75 + (iteration * 4), f"迭代#{iteration}: 重试验证")

                # 记录补丁前分数
                pre_retry_score = phoenix_context.current_science_score

                # 重新评估
                fitness_result = _evaluate_fitness(hypothesis_result, all_papers)

                if fitness_result:
                    score = fitness_result.hybrid_fitness
                    phoenix_context.record_score(score)
                    logger.info(f"[Task {task_id}] 重试 Science Score: {score:.2f}")

                    # V7.6: 记录补丁有效性
                    score_delta = score - pre_retry_score
                    phoenix_context.record_patch_effectiveness(
                        phoenix_context.red_attack_types,
                        score_delta,
                        phoenix_context.search_level_used
                    )
                    logger.info(f"[Task {task_id}] 补丁有效性: delta={score_delta:.2f}, search_level={phoenix_context.search_level_used}")

                    # 检查是否达到成功阈值
                    if score >= PHOENIX_CONFIG['MIN_SUCCESS_SCORE']:
                        phoenix_machine.transition(PhoenixTransitionTrigger.DEFENSE_PASSED)
                        continue

                # 进入红方攻击重新验证
                phoenix_machine.transition(PhoenixTransitionTrigger.RED_ATTACK_START)
                continue

            elif current_state == PhoenixState.PHOENIX_ROLLBACK:
                # V7.7: 补丁无效累积回溯阶段
                self.update_progress(78 + (iteration * 4), f"迭代#{iteration}: 补丁无效回溯")

                unsolvable_types = phoenix_context.get_unsolvable_attack_types()
                logger.warning(f"[Task {task_id}] PHOENIX_ROLLBACK: 无法解决的攻击类型: {unsolvable_types}")

                # 获取回溯目标版本（该攻击类型首次出现前的版本）
                # 传入当前分数用于评分保护
                current_score = phoenix_context.current_science_score
                rollback_target = _find_rollback_target(version_manager, unsolvable_types, current_score)

                if rollback_target:
                    # 记录回溯
                    phoenix_context.record_rollback(
                        phoenix_context.current_version,
                        rollback_target.version_number,
                        unsolvable_types
                    )

                    # 创建回溯版本（而不是直接覆盖版本号）
                    rollback_version = version_manager.create_rewrite_version(
                        base_version=rollback_target,
                        rewrite_type="rollback",
                        rewrite_log=[{
                            'type': 'rollback',
                            'from_version': phoenix_context.current_version,
                            'to_version': rollback_target.version_number,
                            'reason': f"攻击类型 {unsolvable_types} 无法解决"
                        }],
                        new_hypothesis=rollback_target.hypothesis_content,
                        iteration=iteration,
                        red_attack_types=[]  # 回溯版本没有攻击类型
                    )

                    if rollback_version:
                        hypothesis_result = rollback_version.hypothesis_content
                        phoenix_context.current_version = rollback_version.version_number
                        logger.info(f"[Task {task_id}] 创建回溯版本: {rollback_version.version_number}")
                    else:
                        # 如果创建版本失败，直接使用目标版本
                        hypothesis_result = rollback_target.hypothesis_content
                        phoenix_context.current_version = rollback_target.version_number

                    # 重置该攻击类型的失败计数
                    phoenix_context.reset_attack_type_failure_count(unsolvable_types)

                    # 使用不同的预设解决方案（跳过之前用的）
                    phoenix_context.search_level_used = 1  # 重置检索级别

                    logger.info(f"[Task {task_id}] 回溯完成: {rollback_target.version_number}, 已重置攻击类型计数")
                    stage_outputs.append(_write_stage_output(task_id, iteration * 10 + 7, f'iteration_{iteration}_rollback', {
                        'rollback_from': phoenix_context.current_version,
                        'rollback_to': rollback_target.version_number,
                        'unsolvable_types': unsolvable_types,
                        'avoidance_prompt': phoenix_context.get_avoidance_prompt()[:500] if phoenix_context.failed_attack_blacklist else '',
                    }))

                    phoenix_machine.transition(PhoenixTransitionTrigger.ROLLBACK_COMPLETED)
                else:
                    # 无法找到回溯目标，进入硬性失败
                    logger.error(f"[Task {task_id}] 无法找到有效的回溯目标版本")
                    phoenix_context.failure_reason = f"攻击类型 {unsolvable_types} 无法解决且无法回溯"
                    phoenix_machine.transition(PhoenixTransitionTrigger.UNRECOVERABLE_CONFLICT)
                continue

            elif current_state == PhoenixState.SCORE_STagnant:
                # 分数停滞阶段
                self.update_progress(68 + (iteration * 4), f"迭代#{iteration}: 分数停滞检测")

                logger.warning(f"[Task {task_id}] 分数连续停滞 {phoenix_context.stagnant_count} 次")

                # 触发外部补偿
                phoenix_machine.transition(PhoenixTransitionTrigger.SCORE_STagnant_DETECTED)
                continue

            elif current_state == PhoenixState.EXTERNAL_COMPENSATION:
                # 外部算法补偿阶段
                self.update_progress(72 + (iteration * 4), f"迭代#{iteration}: 外部算法补偿")

                logger.info(f"[Task {task_id}] EXTERNAL_COMPENSATION 启动")

                # 搜索外部算法
                external_algorithms = _search_external_algorithms(detected_domain)

                # 生成补偿指令
                compensation_prompt, new_version = generate_external_compensation_prompt(
                    phoenix_context.current_science_score,
                    PHOENIX_CONFIG['SCORE_RISE_MIN_DELTA'],
                    phoenix_context.stagnant_count,
                    external_algorithms,
                    phoenix_context.current_version
                )

                # 执行补偿注入
                hypothesis_result = _execute_compensation(
                    self, task_id, compensation_prompt, hypothesis_result, phoenix_context
                )

                if hypothesis_result:
                    phoenix_context.current_version = new_version
                    phoenix_context.compensation_sources = [a.get('name') for a in external_algorithms[:3]]
                    logger.info(f"[Task {task_id}] 外部补偿完成，版本: {new_version}")
                    stage_outputs.append(_write_stage_output(task_id, iteration * 10 + 6, f'iteration_{iteration}_compensation', {
                        'hypothesis': hypothesis_result,
                        'external_algorithms': external_algorithms,
                        'compensation_sources': phoenix_context.compensation_sources,
                    }))
                    phoenix_machine.transition(PhoenixTransitionTrigger.COMPENSATION_COMPLETED)
                else:
                    phoenix_context.failure_reason = "外部算法补偿执行失败"
                    phoenix_machine.transition(PhoenixTransitionTrigger.BLUE_DEFENSE_FAILURE)
                continue

            # 迭代上限检查
            if phoenix_context.phoenix_iterations >= PHOENIX_CONFIG['MAX_PHOENIX_ITERATIONS']:
                logger.warning(f"[Task {task_id}] 达到凤凰迭代上限")
                phoenix_machine.transition(PhoenixTransitionTrigger.MAX_ITERATIONS_EXCEEDED)
                break

        # ==================== Phase 11: 结果生成 ====================
        self.update_progress(90, "生成最终结果")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        final_state = phoenix_context.current_state

        # V7.7: 笼统输入特殊处理 - 即使失败也返回最佳版本
        if final_state in [PhoenixState.MAX_PHOENIX_EXCEEDED, PhoenixState.HARD_FAILURE]:
            if phoenix_context.is_broad_input:
                best_version = version_manager.get_best_version()
                if best_version and best_version.science_score > 0:
                    logger.info(f"[Task {task_id}] 笼统输入模式：返回最佳版本 {best_version.version_number}")
                    final_state = PhoenixState.SUCCESS  # 标记为成功以便返回结果
                    phoenix_context.failure_reason = ""  # 清除失败原因
                    # 使用最佳版本的假设
                    if best_version.hypothesis_content:
                        hypothesis_result = best_version.hypothesis_content

        # 获取版本演进链
        version_chain = version_manager.get_version_evolution_chain()

        # 计算 Promise Score（成功时）
        promise_score_result = None
        if final_state == PhoenixState.SUCCESS and hypothesis_result:
            promise_score_result = promise_calculator.calculate(
                {'hypothesis': hypothesis_result, 'scores': fitness_result.to_dict() if fitness_result else {}},
                fitness_result.to_dict() if fitness_result else {},
                verified_ids,
                version_chain
            )

        # 凤凰协议摘要
        phoenix_summary = phoenix_machine.get_evolution_summary()

        # ==================== V7.5 输出增强 ====================
        # 生成落地指南、创新点分析、前沿溯源分析
        enhanced_output = {}
        if final_state == PhoenixState.SUCCESS and hypothesis_result:
            try:
                output_enhancer = create_output_enhancer()

                # 1. 生成落地指南
                logger.info(f"[Task {task_id}] 生成落地指南...")
                implementation_roadmap = output_enhancer.generate_implementation_roadmap(
                    hypothesis_result,
                    detected_domain,
                    fitness_result.to_dict() if fitness_result else {}
                )

                # 2. 生成创新点分析
                logger.info(f"[Task {task_id}] 生成创新点分析...")
                patch_log = hypothesis_result.get('patch_log', [])
                innovation_analysis = output_enhancer.generate_innovation_analysis(
                    hypothesis_result,
                    fitness_result.to_dict() if fitness_result else {},
                    patch_log
                )

                # 3. 生成前沿溯源分析
                logger.info(f"[Task {task_id}] 生成前沿溯源分析...")
                frontier_analysis = output_enhancer.generate_frontier_analysis(
                    hypothesis_result,
                    verified_ids,
                    detected_domain,
                    promise_score_result.to_dict() if promise_score_result else {}
                )

                enhanced_output = {
                    'implementation_roadmap': implementation_roadmap.to_dict(),
                    'innovation_analysis': innovation_analysis.to_dict(),
                    'frontier_analysis': frontier_analysis.to_dict(),
                }

                stage_outputs.append(_write_stage_output(task_id, 90, 'enhanced_output', enhanced_output))

                logger.info(f"[Task {task_id}] 输出增强完成")

            except Exception as e:
                logger.warning(f"[Task {task_id}] 输出增强失败: {e}")
                enhanced_output = {}

        if final_state == PhoenixState.SUCCESS:
            result_type = 'hypothesis'
            payload = {
                'hypothesis': hypothesis_result,
                'fitness': fitness_result.to_dict() if fitness_result else None,
                'verified_ids': verified_ids,
                'domain': detected_domain,
                'sources': sources,
                'audit_context': {
                    'iterations': phoenix_context.phoenix_iterations,
                    'rewrites': phoenix_context.rewrite_attempts,
                    'patches': phoenix_context.patch_attempts,
                    'score_history': phoenix_context.score_history,
                    'red_attack_types': phoenix_context.red_attack_types,
                },
                # V7.5 新增：红蓝方对抗详细信息（用于详细报告生成）
                'red_team_report': red_team_result.get('attack_report', {}) if red_team_result else {},
                'defense_report': defense_result if defense_result else {},
            }
            # 添加增强输出
            if enhanced_output:
                payload.update(enhanced_output)
            payload['stage_outputs'] = stage_outputs
            # 转换 numpy 类型
            payload = convert_numpy_types(payload)
            state = TaskState.SUCCESS
        else:
            result_type = 'phoenix_failure'
            payload = {
                'failure_state': final_state.name,
                'iterations': phoenix_context.phoenix_iterations,
                'score_history': phoenix_context.score_history,
                'version_chain': version_chain,
                'reason': phoenix_context.failure_reason,
            }
            # 转换 numpy 类型
            payload = convert_numpy_types(payload)
            state = TaskState.FAILURE

        # Webhook 回调
        if webhook_url:
            try:
                import requests
                webhook_payload = WebhookPayload(
                    task_id=task_id,
                    task_type='hypothesis_generation_v75',
                    state=state,
                    result=payload,
                    timestamp=end_time.isoformat(),
                )
                requests.post(webhook_url, json=webhook_payload.to_dict(), timeout=30)
            except Exception as e:
                logger.warning(f"[Task {task_id}] Webhook 发送失败: {e}")

        stage_index_path = _write_stage_index(task_id, stage_outputs)
        if state == TaskState.SUCCESS:
            payload['stage_index_path'] = stage_index_path
            payload['stage_outputs'] = stage_outputs

        self.update_progress(100, "凤凰协议任务完成")

        logger.info(f"[Task {task_id}] 凤凰协议终态: {final_state.name}")
        logger.info(f"[Task {task_id}] 总迭代: {phoenix_context.phoenix_iterations}")
        logger.info(f"[Task {task_id}] 耗时: {duration:.2f}s")

        # 生成详细报告（仅在成功时）
        if final_state == PhoenixState.SUCCESS:
            try:
                stage_outputs.append(_write_stage_output(task_id, 99, 'final_payload', payload))
                from src.core.report_generator import generate_phoenix_report
                task_result_for_report = {
                    'task_id': task_id,
                    'state': state.value if hasattr(state, 'value') else state,
                    'duration': duration,
                    'payload': payload,
                }
                report_path = generate_phoenix_report(task_result_for_report, user_input)
                logger.info(f"[Task {task_id}] 详细报告已生成: {report_path}")
            except Exception as e:
                logger.warning(f"[Task {task_id}] 报告生成失败: {e}")

        clear_task_context()

        return TaskResult(
            task_id=task_id,
            state=state,
            result_type=result_type,
            payload=payload,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration=duration,
            api_calls_used=fuse.get_stats().total_api_calls if fuse else 0,
            tokens_used=fuse.get_stats().total_tokens_used if fuse else 0,
            phoenix_protocol=phoenix_summary,
            version_evolution={'chain': version_chain},
            promise_score=promise_score_result.to_dict() if promise_score_result else None,
        ).to_dict()

    except SoftTimeLimitExceeded:
        logger.warning(f"[Task {task_id}] 任务软超时")
        clear_task_context()
        return TaskResult(
            task_id=task_id,
            state=TaskState.TIMEOUT,
            result_type='timeout',
            error='任务执行超过软时间限制',
            start_time=start_time.isoformat(),
            end_time=datetime.now().isoformat(),
        ).to_dict()

    except Exception as e:
        logger.exception(f"[Task {task_id}] 任务执行异常: {e}")
        clear_task_context()
        return TaskResult(
            task_id=task_id,
            state=TaskState.FAILURE,
            result_type='error',
            error=str(e),
            traceback=traceback.format_exc(),
            start_time=start_time.isoformat(),
            end_time=datetime.now().isoformat(),
        ).to_dict()


# ==================== 辅助函数 ====================
def _execute_hypothesis_gen(self, task_id, user_input, domain, sources, verified_ids, phoenix_context, iteration):
    """执行假设生成"""
    try:
        from src.prompts.pi_system_prompt import format_pi_prompt_v60, format_pi_prompt_v732
        from src.utils.llm_utils import call_llm

        # 构建红方反馈（迭代 > 1）
        if iteration > 1 and phoenix_context.red_attack_report:
            red_feedback = _build_red_feedback(phoenix_context.red_attack_report, iteration)
            augmented_input = f"{user_input}\n\n{red_feedback}"
        else:
            augmented_input = user_input

        # 选择 Prompt 版本
        if iteration > 1:
            pi_prompt = format_pi_prompt_v732(
                user_domain=domain,
                user_idea=augmented_input,
                data_sources=sources,
                verified_ids=verified_ids,
                iteration=iteration,
            )
        else:
            pi_prompt = format_pi_prompt_v60(
                user_domain=domain,
                user_idea=augmented_input,
                data_sources=sources,
                verified_ids=verified_ids,
            )

        llm_response = call_llm(pi_prompt)

        if llm_response.get('success'):
            return llm_response.get('content')
        else:
            logger.error(f"[Task {task_id}] LLM 调用失败: {llm_response.get('error')}")
            return None

    except Exception as e:
        logger.error(f"[Task {task_id}] 假设生成异常: {e}")
        return None


def _check_physical_anchor(hypothesis, phoenix_context, alternative_generator):
    """物理锚定校验（V7.5: 返回替代���径而非拦截）"""
    try:
        from src.core.pseudoscience_detector import perform_physical_anchor_check

        result = perform_physical_anchor_check(hypothesis)

        # V7.5: 如果检测到伪科学，生成替代路径
        if not result.passed:
            alternative_paths = alternative_generator.generate_alternative_paths(
                result.pseudoscience_type,
                result.detected_patterns[:3] if hasattr(result, 'detected_patterns') else []
            )

            result.is_recoverable = len(alternative_paths) > 0
            result.alternative_path_suggestions = alternative_paths
            result.rewrite_instruction = alternative_generator.generate_rewrite_instruction(alternative_paths)

        return result

    except Exception as e:
        logger.warning(f"物理锚定校验异常: {e}")
        return type('obj', (object,), {'passed': True, 'is_recoverable': True})()


def _evaluate_fitness(hypothesis, papers):
    """适应度评估"""
    try:
        from src.core.hybrid_fitness import HybridFitnessScorer
        from src.core.physical_validator import PhysicalValidator

        validator = PhysicalValidator()
        physical_result = validator.validate_hypothesis_physical(hypothesis)

        if not physical_result.passed:
            logger.warning(f"物理验证失败: {physical_result.failure_reason}")
            return None

        scorer = HybridFitnessScorer()
        fitness_result = scorer.calculate_fitness(
            hypothesis_json=hypothesis,
            retrieved_docs=papers,
        )

        return fitness_result

    except Exception as e:
        logger.warning(f"适应度评估异常: {e}")
        return None


def _execute_red_attack(hypothesis, fitness):
    """执行红方攻击"""
    try:
        from src.agents.red_team_agent import RedTeamAgent
        red_agent = RedTeamAgent()
        return red_agent.execute({
            'blue_package': {
                'hypothesis_data': hypothesis,
                'fitness_data': fitness.to_dict() if fitness else {},
            }
        })
    except Exception as e:
        logger.warning(f"红方攻击异常: {e}")
        return None


def _execute_defense_committee(hypothesis, fitness, red_attack):
    """执行防御委员会"""
    try:
        from src.agents.defense_committee_agent import DefenseCommitteeAgent
        committee = DefenseCommitteeAgent()
        return committee.execute({
            'blue_package': {
                'hypothesis_data': hypothesis,
                'fitness_data': fitness.to_dict() if fitness else {},
            },
            'red_attack': red_attack.get('attack_report', {}) if red_attack else {}
        })
    except Exception as e:
        logger.warning(f"防御委员会异常: {e}")
        return {'defense_passed': False}


def _extract_attack_types(attack_report):
    """提取攻击类型"""
    types = []
    if attack_report:
        critical_flaws = attack_report.get('critical_flaws', [])
        for flaw in critical_flaws:
            if isinstance(flaw, dict):
                types.append(flaw.get('type', 'UNKNOWN'))
            else:
                types.append(str(flaw))
    return types[:5]


def _build_red_feedback(attack_report, iteration):
    """构建红方反馈"""
    verdict = attack_report.get('verdict', 'unknown')
    critical_flaws = attack_report.get('critical_flaws', [])
    flaws_text = '\n'.join([f"- {f}" for f in critical_flaws[:5]])

    return f"""## 【硬核博弈指令】(迭代 #{iteration})

红方攻击 verdict: {verdict}

核心攻击意见:
{flaws_text}

**你必须修复这些致命漏洞，但不允许牺牲核心学术创新性！**
"""


def _build_attack_summary(attack_report):
    """构建攻击摘要"""
    if not attack_report:
        return "无攻击报告"
    return attack_report.get('verdict', 'unknown') + ': ' + str(attack_report.get('critical_flaws', [])[:3])


def _search_methodology_solutions(attack_types, search_level: int = 1, original_topic: str = "") -> List[Dict]:
    """
    V7.6: 分级检索方法论解决方案

    Args:
        attack_types: 攻击类型列表
        search_level: 检索级别 (1=预设库, 2=方法论关键词, 3=原主题组合)
        original_topic: 原研究主题（Level 3 需要）

    Returns:
        List[Dict]: 解决方案列表
    """
    if not attack_types:
        return []

    logger.info(f"分级检索启动: Level {search_level}, 攻击类型: {attack_types}")

    # Level 1: 预设库（无 API 调用）
    if search_level == 1:
        solutions = _get_preset_solutions(attack_types)
        if solutions:
            logger.info(f"Level 1 预设库返回 {len(solutions)} 个解决方案")
            return solutions
        logger.info("Level 1 预设库无结果，升级到 Level 2")
        search_level = 2

    # Level 2: 方法论关键词检索
    if search_level == 2:
        solutions = _search_methodology_keywords(attack_types)
        if solutions:
            logger.info(f"Level 2 方法论检索返回 {len(solutions)} 个解决方案")
            return solutions
        if original_topic:
            logger.info("Level 2 无结果，升级到 Level 3")
            search_level = 3

    # Level 3: 原主题 + 方法论组合检索
    if search_level == 3 and original_topic:
        solutions = _search_topic_methodology_combo(attack_types, original_topic)
        logger.info(f"Level 3 组合检索返回 {len(solutions)} 个解决方案")
        if solutions:
            return solutions
        # Level 3 无结果，尝试回退到 Level 2（如果之前跳过了）
        logger.info("Level 3 无结果，回退到 Level 2")
        solutions = _search_methodology_keywords(attack_types)
        if solutions:
            return solutions

    return []


# ==================== V7.6: 分级检索预设方法论库 ====================

PRESET_METHODOLOGY_LIBRARY = {
    'OVERFITTING': [
        {'name': 'Nested Cross-Validation', 'source': 'scikit-learn', 'description': '外层评估模型性能，内层进行超参数调优', 'key_steps': ['外层 CV 评估', '内层 CV 调参', '独立测试集验证'], 'reference': 'Varma 2006 BMC Bioinformatics'},
        {'name': 'Dropout + Early Stopping', 'source': 'Deep Learning', 'description': '训练时随机丢弃神经元，监控验证损失提前停止', 'key_steps': ['Dropout rate 0.3-0.5', 'Validation loss 监控', 'Patience 10-20 epochs'], 'reference': 'Srivastava 2014 JMLR'},
        {'name': 'L1/L2 Regularization', 'source': 'Statistical learning', 'description': '添加惩罚项约束模型复杂度', 'key_steps': ['L2 weight decay', 'L1 sparsity', 'Cross-validate lambda'], 'reference': 'Hastie 2009 ESL'},
    ],
    'LEAKAGE': [
        {'name': 'Nested CV Pipeline', 'source': 'ML pipeline', 'description': '所有预处理步骤必须在 CV 内部完成', 'key_steps': ['特征选择在 CV 内', '标准化在 CV 内', '降维在 CV 内'], 'reference': 'Kumar 2020 Nature Methods'},
        {'name': 'Temporal Split', 'source': 'Time series', 'description': '时间序列数据必须按时间顺序分割', 'key_steps': ['训练集早期', '验证集中期', '测试集最新'], 'reference': 'Bergmeir 2012 Neurocomputing'},
        {'name': 'Patient-level Split', 'source': 'Medical AI', 'description': '同一患者多次采样必须在同一集合', 'key_steps': ['GroupKFold by patient_id', '检查分割', '验证无交叉'], 'reference': 'Oakden-Rayner 2020 Nature Medicine'},
    ],
    'BIAS': [
        {'name': 'Propensity Score Matching', 'source': 'Causal inference', 'description': '通过倾向性评分匹配控制混杂因素', 'key_steps': ['估计倾向性得分', '最近邻匹配', '平衡性检验'], 'reference': 'Rosenbaum 1983 Biometrika'},
        {'name': 'Inverse Probability Weighting', 'source': 'Survey statistics', 'description': '使用逆概率加权校正选择偏倚', 'key_steps': ['计算选择概率', '构建权重', '加权分析'], 'reference': 'Hernan 2020 Causal Inference'},
        {'name': 'Stratified Sampling', 'source': 'Experimental design', 'description': '按关键变量分层抽样确保代表性', 'key_steps': ['识别分层变量', '按比例抽样', '层内分析'], 'reference': 'Cochran 1977 Sampling'},
    ],
    'VALIDATION': [
        {'name': 'External Validation Cohort', 'source': 'Clinical prediction', 'description': '在独立外部队列验证模型泛化性', 'key_steps': ['独立数据收集', '不同机构地区', '报告校准曲线'], 'reference': 'TRIPOD 2015 BMJ'},
        {'name': 'Bootstrap Validation', 'source': 'Resampling methods', 'description': '自助法评估模型稳定性', 'key_steps': ['B=200 bootstrap', '计算 optimism', '校正后报告'], 'reference': 'Harrell 1996 Statistics in Medicine'},
        {'name': 'Temporal Validation', 'source': 'Clinical AI', 'description': '使用未来时间段数据验证', 'key_steps': ['训练期数据', '验证期数据', '评估性能衰减'], 'reference': 'Sjoding 2020 Lancet Digital Health'},
    ],
    'ENDOGENEITY': [
        {'name': 'Instrumental Variable', 'source': 'Econometric methods', 'description': '使用工具变量解决内生性问题', 'key_steps': ['识别有效 IV', '两阶段最小二乘', '过度识别检验'], 'reference': 'Angrist 2001 NBER'},
        {'name': 'Difference-in-Differences', 'source': 'Causal inference', 'description': '双重差分法估计因果效应', 'key_steps': ['处理组对照组', '平行趋势检验', 'DID 估计量'], 'reference': 'Card 1994 AER'},
        {'name': 'Regression Discontinuity', 'source': 'Quasi-experimental', 'description': '利用断点识别因果效应', 'key_steps': ['识别断点', '局部线性回归', '带宽选择'], 'reference': 'Lee 2010 JEL'},
    ],
    'MULTIPLE_TESTING': [
        {'name': 'Benjamini-Hochberg FDR', 'source': 'Multiple comparison', 'description': '控制假发现率的多重检验校正', 'key_steps': ['排序 p 值', '计算阈值', '报告 q-value'], 'reference': 'Benjamini 1995 JRSS-B'},
        {'name': 'Bonferroni Correction', 'source': 'Conservative testing', 'description': '保守的多重检验校正方法', 'key_steps': ['p 值乘以检验次数', '阈值除以次数', '报告校正后 p'], 'reference': 'Bonferroni 1936'},
        {'name': 'Pre-registration', 'source': 'Open science', 'description': '预先注册分析计划防止 p-hacking', 'key_steps': ['注册假设', '预设分析方法', '报告所有结果'], 'reference': 'Nosek 2018 Science'},
    ],
    'CAUSAL_INFERENCE': [
        {'name': 'DAG Confounder Selection', 'source': 'Causal diagram', 'description': '基于有向无环图选择混杂因素', 'key_steps': ['绘制 DAG', '识别后门路径', '选择调整集'], 'reference': 'Pearl 2009 Causality'},
        {'name': 'E-value Sensitivity', 'source': 'Epidemiology', 'description': '评估未测量混杂的影响', 'key_steps': ['计算 E-value', '解释混杂强度', '敏感性报告'], 'reference': 'VanderWeele 2017 Annals IM'},
        {'name': 'Negative Control Outcomes', 'source': 'Pharmacoepidemiology', 'description': '使用阴性对照结局检验混杂', 'key_steps': ['选择阴性对照', '检验效应', '解释结果'], 'reference': 'Lipsitch 2010 IJE'},
    ],
    'REPRODUCIBILITY': [
        {'name': 'Random Seed Fixing', 'source': 'Reproducible research', 'description': '固定所有随机种子确保可复现', 'key_steps': ['numpy.random.seed', 'torch.manual_seed', 'tensorflow.random.set_seed'], 'reference': 'Pineau 2020 NeurIPS'},
        {'name': 'Docker Containerization', 'source': 'Software reproducibility', 'description': '使用容器封装完整运行环境', 'key_steps': ['编写 Dockerfile', '固定依赖版本', '发布镜像'], 'reference': 'Boettiger 2015 American Statistician'},
        {'name': 'Code & Data Sharing', 'source': 'Open science', 'description': '公开代码和数据以便验证', 'key_steps': ['GitHub 仓库', '数据可用性声明', 'DOI 引用'], 'reference': 'Wilkinson 2016 Scientific Data'},
    ],
}


def _get_preset_solutions(attack_types: List[str]) -> List[Dict]:
    """V7.6 Level 1: 从预设库获取解决方案（无 API 调用）"""
    solutions = []
    for attack_type in attack_types[:3]:
        if attack_type in PRESET_METHODOLOGY_LIBRARY:
            for solution in PRESET_METHODOLOGY_LIBRARY[attack_type][:2]:
                solutions.append({'source': 'preset_library', 'attack_type': attack_type, 'search_level': 1, **solution})
    return solutions


def _search_methodology_keywords(attack_types: List[str]) -> List[Dict]:
    """V7.6 Level 2: 方法论关键词检索（PubMed API 调用）"""
    try:
        from src.utils.pubmed import PubMedClient

        solution_keywords = {
            'OVERFITTING': ['overfitting prevention machine learning', 'cross-validation leak-free design'],
            'LEAKAGE': ['data leakage prevention machine learning', 'nested cross-validation best practices'],
            'BIAS': ['selection bias correction methods', 'propensity score matching tutorial'],
            'VALIDATION': ['external validation clinical prediction model', 'bootstrap validation statistics'],
            'ENDOGENEITY': ['instrumental variable analysis tutorial', 'endogeneity correction methods'],
            'MULTIPLE_TESTING': ['false discovery rate correction', 'multiple testing correction methods'],
            'CAUSAL_INFERENCE': ['causal inference DAG tutorial', 'sensitivity analysis unmeasured confounding'],
            'REPRODUCIBILITY': ['reproducible machine learning research', 'random seed fixing best practices'],
        }

        pubmed_client = PubMedClient()
        papers = []

        for attack_type in attack_types[:3]:
            keywords = solution_keywords.get(attack_type, [f'{attack_type} solution method'])
            for keyword in keywords[:2]:
                try:
                    result = pubmed_client.search(keyword, max_results=5)
                    if result and result.get('pmids'):
                        for pmid in result['pmids'][:3]:
                            papers.append({'pmid': pmid, 'title': f'PMID: {pmid}', 'key_methodology': f'Based on search: {keyword}', 'source': 'pubmed_level2', 'attack_type': attack_type, 'search_level': 2})
                except Exception:
                    pass

        return papers[:10]
    except Exception as e:
        logger.warning(f"Level 2 方法论搜索异常: {e}")
        return []


def _search_topic_methodology_combo(attack_types: List[str], original_topic: str) -> List[Dict]:
    """V7.6 Level 3: 原研究主题 + 方法论组合检索"""
    if not original_topic:
        logger.warning("Level 3 检索需要原研究主题，跳过")
        return []

    try:
        from src.utils.pubmed import PubMedClient

        methodology_keywords = {
            'OVERFITTING': ['cross-validation', 'overfitting prevention', 'regularization'],
            'LEAKAGE': ['nested cross-validation', 'data leakage', 'information leakage'],
            'BIAS': ['propensity score', 'selection bias', 'confounding'],
            'VALIDATION': ['external validation', 'bootstrap validation', 'temporal validation'],
            'ENDOGENEITY': ['instrumental variable', 'endogeneity', 'causal inference'],
            'MULTIPLE_TESTING': ['false discovery rate', 'multiple comparison', 'bonferroni'],
            'CAUSAL_INFERENCE': ['causal inference', 'directed acyclic graph', 'sensitivity analysis'],
            'REPRODUCIBILITY': ['reproducibility', 'replication', 'open science'],
        }

        pubmed_client = PubMedClient()
        papers = []

        topic_words = original_topic.lower().split()[:3]
        topic_core = ' '.join(topic_words)

        for attack_type in attack_types[:2]:
            method_keywords = methodology_keywords.get(attack_type, [])
            for method_kw in method_keywords[:2]:
                combo_query = f"{topic_core} {method_kw}"
                try:
                    logger.info(f"Level 3 检索: {combo_query}")
                    result = pubmed_client.search(combo_query, max_results=5)
                    if result and result.get('pmids'):
                        for pmid in result['pmids'][:3]:
                            papers.append({'pmid': pmid, 'title': f'PMID: {pmid}', 'key_methodology': f'Topic + Method: {combo_query}', 'source': 'pubmed_level3', 'attack_type': attack_type, 'search_level': 3, 'original_topic': original_topic})
                except Exception as e:
                    logger.warning(f"Level 3 检索异常 ({combo_query}): {e}")

        return papers[:8]
    except Exception as e:
        logger.warning(f"Level 3 组合检索异常: {e}")
        return []





def _find_rollback_target(version_manager, unsolvable_types: List[str], current_score: float = 0.0) -> Optional[Any]:
    """
    V7.7: 查找回溯目标版本（增强版：评分保护 + 深度限制）

    找到该攻击类型首次出现之前的版本，同时满足：
    1. 目标版本分数 >= 当前分数 - 容忍度
    2. 只回溯最近的 N 个版本（深度限制）
    3. 不能是当前版本本身

    Args:
        version_manager: 版本管理器
        unsolvable_types: 无法解决的攻击类型列表
        current_score: 当前版本的分数，用于评分保护

    Returns:
        目标版本对象，或 None
    """
    from src.core.phoenix_state_machine import PHOENIX_CONFIG

    versions = version_manager.get_version_evolution_chain()
    depth_limit = PHOENIX_CONFIG.get('ROLLBACK_DEPTH_LIMIT', 3)
    score_tolerance = PHOENIX_CONFIG.get('ROLLBACK_SCORE_TOLERANCE', 1.0)

    if not versions or len(versions) < 2:
        # 如果只有一个版本，无法回溯
        logger.warning("[_find_rollback_target] 版本链太短，无法回溯")
        return None

    # 计算最低可接受的分数
    min_acceptable_score = max(0, current_score - score_tolerance)

    # 当前版本号（用于排除）
    current_version_number = version_manager.current_version

    # 限制回溯深度：只考虑最近的 N 个版本，排除当前版本
    # 版本链顺序：versions[0]=最早, versions[-1]=最新(当前)
    # 从版本链末尾往前取，跳过最后一个（当前版本）
    start_idx = max(0, len(versions) - depth_limit - 1)
    end_idx = len(versions) - 1  # 排除最后一个（当前版本）
    candidate_versions = versions[start_idx:end_idx]

    # 倒序遍历（从较新到较旧）
    candidate_versions_reversed = list(reversed(candidate_versions))

    logger.info(f"[_find_rollback_target] 回溯搜索范围: {len(candidate_versions_reversed)} 个候选版本, "
                f"最低可接受分数: {min_acceptable_score:.2f}, "
                f"排除当前版本: {current_version_number}")

    # 从候选版本倒序查找（优先选择较新的版本）
    for version_info in candidate_versions_reversed:
        version_number = version_info.get('version')
        version_attack_types = version_info.get('red_attack_types', [])
        version_score = version_info.get('science_score', 0.0)

        # 排除当前版本本身（双重检查）
        if version_number == current_version_number:
            continue

        # 如果该版本不包含这些攻击类型，且分数满足要求
        if not any(t in version_attack_types for t in unsolvable_types):
            # 评分保护：不回溯到分数太低的版本
            if version_score >= min_acceptable_score:
                # 获取完整的版本对象
                target_version = version_manager.get_version_by_number(version_number)
                if target_version and target_version.hypothesis_content:
                    logger.info(f"[_find_rollback_target] 找到回溯目标: {version_number} "
                               f"(分数: {version_score:.2f})")
                    return target_version
            else:
                logger.info(f"[_find_rollback_target] 跳过版本 {version_number}："
                           f"分数 {version_score:.2f} < 最低可接受 {min_acceptable_score:.2f}")

    # 如果没有找到满足条件的版本，尝试放宽限制：只要不含攻击类型即可
    logger.warning("[_find_rollback_target] 未找到满足评分保护的目标，尝试放宽限制...")
    for version_info in candidate_versions_reversed:
        version_number = version_info.get('version')
        version_attack_types = version_info.get('red_attack_types', [])

        # 排除当前版本
        if version_number == current_version_number:
            continue

        if not any(t in version_attack_types for t in unsolvable_types):
            target_version = version_manager.get_version_by_number(version_number)
            if target_version and target_version.hypothesis_content:
                logger.warning(f"[_find_rollback_target] 使用放宽条件的目标: {version_number} "
                              f"(分数: {version_info.get('science_score', 0):.2f})")
                return target_version

    # 最后的备选：返回最早的非当前版本
    if len(versions) > 1:
        earliest_version = version_manager.get_version_by_number(versions[0].get('version'))
        if earliest_version and earliest_version.version_number != current_version_number:
            logger.warning(f"[_find_rollback_target] 使用最早版本作为备选: {earliest_version.version_number}")
            return earliest_version

    return None


def _search_external_algorithms(domain):
    """搜索外部算法"""
    # V7.5: 简化的外部算法推荐
    algorithms = []

    if 'bioinformatics' in domain.lower() or 'genomics' in domain.lower():
        algorithms.extend([
            {'name': 'AlphaFold3 confidence calibration', 'source': 'DeepMind', 'description': '蛋白质结构置信度校正'},
            {'name': 'UK Biobank covariate correction', 'source': 'UKB Best Practices', 'description': '大规模队列协变量校正'},
        ])

    if 'drug' in domain.lower() or 'molecular' in domain.lower():
        algorithms.extend([
            {'name': 'Morgan fingerprint similarity', 'source': 'RDKit', 'description': '分子指纹相似性计算'},
            {'name': 'Scaffold splitting validation', 'source': 'ChemML', 'description': '骨架分割验证'},
        ])

    # 通用算法
    algorithms.extend([
        {'name': 'SHAP interpretability framework', 'source': 'GitHub', 'description': '模型可解释性分析'},
        {'name': 'Nested Cross-Validation', 'source': 'scikit-learn', 'description': '嵌套交叉验证'},
    ])

    return algorithms[:5]


def _execute_rewrite(self, task_id, rewrite_prompt, phoenix_context):
    """执行物理重写"""
    try:
        from src.utils.llm_utils import call_llm
        llm_response = call_llm(rewrite_prompt)

        if llm_response.get('success'):
            return llm_response.get('content')
        return None
    except Exception as e:
        logger.error(f"[Task {task_id}] 物理重写异常: {e}")
        return None


def _execute_patch(self, task_id, patch_prompt, current_hypothesis, phoenix_context):
    """执行补丁注入"""
    try:
        from src.utils.llm_utils import call_llm
        llm_response = call_llm(patch_prompt)

        if llm_response.get('success'):
            return llm_response.get('content')
        return current_hypothesis
    except Exception as e:
        logger.error(f"[Task {task_id}] 补丁注入异常: {e}")
        return current_hypothesis


def _execute_compensation(self, task_id, compensation_prompt, current_hypothesis, phoenix_context):
    """执行外部补偿"""
    try:
        from src.utils.llm_utils import call_llm
        llm_response = call_llm(compensation_prompt)

        if llm_response.get('success'):
            return llm_response.get('content')
        return current_hypothesis
    except Exception as e:
        logger.error(f"[Task {task_id}] 外部补偿异常: {e}")
        return current_hypothesis


# ==================== 任务注册 ====================
def register_tasks():
    """注册 Celery 任务"""
    app = get_celery_app()

    app.task(
        bind=True,
        base=ProgressTrackingTask,
        max_retries=3,
    )(hypothesis_generation_task_v75_impl, name='hypothesis_generation_task_v75')

    logger.info("[Celery V7.5] 任务注册完成: hypothesis_generation_task_v75")

    return app


# ==================== Celery CLI 发现入口 ====================
_celery_for_cli = None


def _get_celery_for_cli():
    """为 Celery CLI 提供已注册任务的 app"""
    global _celery_for_cli
    if _celery_for_cli is None:
        app = get_celery_app()
        task_obj = app.task(
            hypothesis_generation_task_v75_impl,
            bind=True,
            base=ProgressTrackingTask,
            max_retries=3,
            name='hypothesis_generation_task_v75'
        )
        _celery_for_cli = app
        logger.info(f"[Celery CLI V7.5] 任务注册: {task_obj.name}")
    return _celery_for_cli


celery = _get_celery_for_cli()
celery_app = celery


# ==================== 提交任务 ====================
def submit_hypothesis_generation_v75(
    user_input: str,
    user_domain: str = None,
    webhook_url: str = None,
    session_id: str = None,
    **kwargs
) -> Dict:
    """提交 V7.5 假设生成任务"""
    app = get_celery_app()
    task = app.send_task(
        'hypothesis_generation_task_v75',
        kwargs={
            'user_input': user_input,
            'user_domain': user_domain,
            'webhook_url': webhook_url,
            'session_id': session_id,
            **kwargs
        }
    )

    return {
        'task_id': task.id,
        'state': 'pending',
        'estimated_duration': '10 分钟',
        'webhook_url': webhook_url,
        'message': 'V7.5 凤凰协议任务已提交',
        'phoenix_enabled': True,
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
        logger.info(f"[Revoke V7.5] Task {task_id} revoked")
        return True
    except Exception as e:
        logger.error(f"[Revoke V7.5] Failed: {e}")
        return False


# ==================== 初始化 ====================
def init_celery_tasks_v75():
    """初始化 V7.5 Celery 任务系统"""
    app = get_celery_app()
    register_tasks()
    logger.info("[Celery V7.5] 凤凰协议任务系统初始化完成")
    return app


# ==================== 导出 ====================
__all__ = [
    'get_celery_app',
    'celery',
    'celery_app',
    'TaskState',
    'TaskResult',
    'submit_hypothesis_generation_v75',
    'get_task_status',
    'revoke_task',
    'init_celery_tasks_v75',
    'hypothesis_generation_task_v75_impl',
]