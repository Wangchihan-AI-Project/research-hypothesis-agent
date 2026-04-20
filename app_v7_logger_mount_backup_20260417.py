# -*- coding: utf-8 -*-
"""
V7.1 生物医学计算与统计自动化科研引擎 - 企业级异步 SaaS 控制台

V7.1 集中式日志挂载版：
- 所有 print() 改为集中式日志系统
- Task ID 贯穿注入
- 深水区异常堆栈捕获

核心架构升级：
1. 侧边栏动态调度中心 - execution_mode切换、熔断参数动态调整
2. 基于 Session State 的 Celery 异步轮询 - 无阻塞调用
3. V7.0 状态机透视雷达 - 实时进度显示（Terminal风格）
4. 成功/熔断的优雅结算 - Markdown报告渲染 / 科研否决报告

作者: 全栈架构师 V7.1
日期: 2026-04-17
"""
import sys
import os
import time
import json
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

# ==================== V7.1: 集中式日志挂载 ====================
from src.utils.logger import (
    get_central_logger,
    set_task_context,
    clear_task_context,
    AUDIT_LEVEL
)
logger = get_central_logger()

# ==================== 强制 UTF-8 编码环境（Streamlit 兼容版）====================
# 注意：Streamlit 环境下不应直接重定向 sys.stdout，否则会导致 I/O closed 错误
if sys.platform == "win32":
    try:
        # 仅设置环境变量，不修改 stdout（避免 Streamlit 冲突）
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
        # 检查 stdout 是否可用，仅在未关闭时才尝试编码设置
        if sys.stdout is not None and not sys.stdout.closed:
            try:
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, ValueError):
                pass  # Streamlit 环境可能不支持 reconfigure
        if sys.stderr is not None and not sys.stderr.closed:
            try:
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, ValueError):
                pass
    except Exception:
        pass  # 宽松策略：任何异常都静默忽略

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
env_path = project_root / '.env'
load_dotenv(env_path, encoding='utf-8')

import streamlit as st

# ==================== 尝试导入 Celery 相关组件 ====================
try:
    from celery.result import AsyncResult
    import redis
    from src.core.celery_tasks import (
        get_celery_app,
        TaskState,
        TaskResult,
        hypothesis_generation_task_impl,
    )
    CELERY_AVAILABLE = True
except ImportError as e:
    CELERY_AVAILABLE = False
    print(f"[Warning] Celery components not available: {e}")

# ==================== 尝试导入 st_autorefresh ====================
try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False
    print("[Warning] streamlit-autorefresh not available, using fallback polling")

# ==================== 尝试导入否决报告生成器 ====================
try:
    from src.core.rejection_report import (
        RejectionReportGenerator,
        RejectionType,
        ScientificRejectionReport,
    )
    REJECTION_REPORT_AVAILABLE = True
except ImportError:
    REJECTION_REPORT_AVAILABLE = False

# ==================== 尝试导入配置模块 ====================
try:
    from src.core.program_config import get_current_config, ProgramConfig
    PYDANTIC_CONFIG_AVAILABLE = True
except ImportError:
    PYDANTIC_CONFIG_AVAILABLE = False

# ==================== V7.1 常量定义 ====================
ZOMBIE_TASK_THRESHOLD_MINUTES = 60  # 僵尸任务阈值
MAX_POLL_ATTEMPTS = 100  # 最大轮询次数
POLL_INTERVAL_SECONDS = 3  # 轮询间隔
SUBMIT_COOLDOWN_SECONDS = 30  # 提交冷却期
SUBMIT_DEBOUNCE_SECONDS = 5  # 防抖间隔

# 持久化数据库路径
DATA_DIR = project_root / 'data'
DATA_DIR.mkdir(exist_ok=True)
PERSISTENCE_DB = DATA_DIR / 'task_persistence.db'
LOCAL_QUEUE_DB = DATA_DIR / 'local_task_queue.db'

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="V7.1 科研引擎 - 异步控制台",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "V7.1 生物医学计算与统计自动化科研引擎 - 企业级异步 SaaS 控制台（通信边界加固版）"
    }
)

# ==================== V7.0 Pipeline 15步状态定义 ====================
PIPELINE_STEPS = [
    {"step": 1, "name": "Intent Sanitizer", "icon": "🛡️", "description": "意图清洗预检"},
    {"step": 2, "name": "Celery Dispatch", "icon": "📨", "description": "任务派发"},
    {"step": 3, "name": "Global Fuse Init", "icon": "⚡", "description": "熔断器初始化"},
    {"step": 4, "name": "Dynamic RAG Router", "icon": "🔀", "description": "数据源路由"},
    {"step": 5, "name": "PubMed Search", "icon": "📚", "description": "PubMed检索"},
    {"step": 6, "name": "ArXiv/S2 Search", "icon": "📖", "description": "多源检索"},
    {"step": 7, "name": "Physical Validator", "icon": "🔒", "description": "物理铁闸校验"},
    {"step": 8, "name": "PI Hypothesis Gen", "icon": "🧪", "description": "假设生成"},
    {"step": 9, "name": "Hard-Link Anchor", "icon": "⚓", "description": "引用锚定校验"},
    {"step": 10, "name": "Hybrid Fitness", "icon": "📊", "description": "混合适应度评估"},
    {"step": 11, "name": "Red Team Attack", "icon": "⚔️", "description": "红方攻击审计"},
    {"step": 12, "name": "Defense Committee", "icon": "🛡️", "description": "蓝方答辩"},
    {"step": 13, "name": "Convergence Check", "icon": "🎯", "description": "收敛检测"},
    {"step": 14, "name": "Report Generation", "icon": "📝", "description": "报告生成"},
    {"step": 15, "name": "Webhook Callback", "icon": "🔔", "description": "结果回调"},
]

# ==================== V7.0 极客风格 CSS ====================
st.markdown("""
<style>
    /* 主标题 */
    .v7-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        border: 1px solid #3b82f6;
        margin-bottom: 1.5rem;
    }
    .v7-header h1 {
        color: #60a5fa;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: 0.05em;
    }
    .v7-header .subtitle {
        color: #94a3b8;
        font-size: 0.9rem;
        margin-top: 0.5rem;
    }

    /* Terminal 风格进度框 */
    .terminal-box {
        background: #0f172a;
        border: 1px solid #3b82f6;
        border-radius: 8px;
        padding: 1rem;
        font-family: 'Courier New', monospace;
        color: #10b981;
        overflow-x: auto;
        max-height: 400px;
    }
    .terminal-header {
        color: #60a5fa;
        font-weight: bold;
        margin-bottom: 0.5rem;
        border-bottom: 1px solid #334155;
        padding-bottom: 0.5rem;
    }
    .terminal-line {
        margin: 0.2rem 0;
        font-size: 0.85rem;
    }
    .terminal-step-active {
        color: #fbbf24;
        font-weight: bold;
    }
    .terminal-step-complete {
        color: #10b981;
    }
    .terminal-step-pending {
        color: #64748b;
    }
    .terminal-step-error {
        color: #ef4444;
        font-weight: bold;
    }
    .terminal-time {
        color: #64748b;
        font-size: 0.75rem;
    }

    /* 状态卡片 */
    .status-card {
        background: #1e293b;
        border-radius: 8px;
        padding: 1rem;
        border: 1px solid #334155;
        margin-bottom: 0.5rem;
    }
    .status-card.success {
        border-color: #10b981;
        background: #064e3b;
    }
    .status-card.error {
        border-color: #ef4444;
        background: #7f1d1d;
    }
    .status-card.warning {
        border-color: #f59e0b;
        background: #78350f;
    }

    /* 侧边栏配置 */
    .sidebar-config-header {
        color: #60a5fa;
        font-weight: bold;
        border-bottom: 1px solid #334155;
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }

    /* 进度条 */
    .v7-progress-bar {
        background: #334155;
        border-radius: 4px;
        height: 8px;
        overflow: hidden;
    }
    .v7-progress-fill {
        background: linear-gradient(90deg, #3b82f6, #10b981);
        height: 100%;
        transition: width 0.3s ease;
    }

    /* 报告渲染 */
    .report-container {
        background: #1e293b;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #334155;
    }

    /* 否决报告 */
    .rejection-card {
        background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%);
        border-radius: 12px;
        padding: 1.5rem;
        border: 2px solid #ef4444;
        margin-bottom: 1rem;
    }
    .rejection-card h2 {
        color: #fef2f2;
        margin: 0;
    }
    .rejection-card .reason {
        color: #fee2e2;
        font-size: 1rem;
        margin-top: 0.5rem;
    }

    /* 成功报告 */
    .success-card {
        background: linear-gradient(135deg, #064e3b 0%, #065f46 100%);
        border-radius: 12px;
        padding: 1.5rem;
        border: 2px solid #10b981;
        margin-bottom: 1rem;
    }
    .success-card h2 {
        color: #ecfdf5;
        margin: 0;
    }

    /* 配置参数卡片 */
    .config-param-card {
        background: #1e293b;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        border: 1px solid #334155;
        margin: 0.3rem 0;
    }
    .config-param-label {
        color: #94a3b8;
        font-size: 0.75rem;
    }
    .config-param-value {
        color: #60a5fa;
        font-weight: bold;
    }

    /* 提交守卫状态 */
    .submission-guard-active {
        background: #7f1d1d;
        border: 1px solid #ef4444;
        border-radius: 4px;
        padding: 0.5rem;
        color: #fef2f2;
    }

    /* 轮询统计 */
    .poll-stats-card {
        background: #1e293b;
        border: 1px solid #3b82f6;
        border-radius: 8px;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ==================== Session State 初始化 ====================
def init_session_state():
    """初始化 V7.1 Session State（含加固字段）"""
    defaults = {
        # 任务状态
        'task_id': None,
        'task_state': None,
        'task_progress': 0,
        'task_message': '',
        'task_result': None,
        'task_start_time': None,

        # 配置参数
        'execution_mode': 'autonomous',
        'hard_cap': 15,
        'min_score_threshold': 7.0,
        'max_iterations': 5,
        'enable_intent_sanitizer': True,
        'enable_physical_validator': True,
        'enable_hard_link_anchor': True,
        'enable_convergence_detector': True,
        'enable_vector_pool_manager': True,

        # 用户输入
        'user_input': '',
        'user_domain': 'auto-detect',

        # Pipeline 状态追踪
        'pipeline_steps_status': {},
        'pipeline_logs': [],

        # 最终结果
        'final_report': None,
        'rejection_report': None,

        # 错误状态
        'error_occurred': False,
        'error_type': None,
        'error_message': None,

        # V7.1 新增: 提交守卫状态
        'submission_lock': False,
        'last_submit_time': None,
        'submit_cooldown_until': None,
        'pending_input_hash': None,

        # V7.1 新增: 轮询守卫状态
        'poll_start_time': None,
        'poll_attempt_count': 0,
        'last_state_change_time': None,
        'last_known_state': None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ==================== V7.1 修复 #2: 任务持久化数据库 ====================
def init_task_persistence_db():
    """
    V7.1 任务持久化数据库初始化

    解决: 刷新后 task_id 丢失问题
    """
    try:
        conn = sqlite3.connect(PERSISTENCE_DB)
        cursor = conn.cursor()

        # 任务追踪表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_registry (
                task_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_input_hash TEXT NOT NULL,
                user_input_preview TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                last_poll_at TEXT,
                result_available INTEGER DEFAULT 0,
                result_json TEXT
            )
        """)

        # 创建索引加速查询
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_registry_created
            ON task_registry(created_at)
        """)

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"Persistence DB init failed: {e}")
        return False


def register_task_persistence(task_id: str, user_input: str, config: Dict):
    """
    V7.1 任务注册

    将 task_id 写入本地 SQLite，即使刷新也能召回
    """
    try:
        conn = sqlite3.connect(PERSISTENCE_DB)
        cursor = conn.cursor()

        input_hash = hashlib.sha256(user_input.encode()).hexdigest()[:16]
        session_id = config.get('session_id', 'default')
        input_preview = user_input[:100] if len(user_input) > 100 else user_input

        cursor.execute("""
            INSERT OR REPLACE INTO task_registry
            (task_id, session_id, user_input_hash, user_input_preview, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (task_id, session_id, input_hash, input_preview, 'pending', datetime.now().isoformat()))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"Task persistence register failed: {e}")
        return False


def recover_lost_task_on_reload() -> Optional[str]:
    """
    V7.1 刷新后任务召回（P2-A1 修复：竞态条件防护）

    核心流程:
    1. 从 SQLite 查找最近未完成的任务
    2. 检查 Redis 中实际状态
    3. P2-A1: 检查任务是否被其他 Tab 占用
    4. 自动恢复 task_id 到 session_state

    Returns:
        Optional[str]: 恢复的 task_id，如果不应恢复则返回 None
    """
    try:
        # ==================== P2-A1 修复：多 Tab 竞态检测 ====================
        current_tab_id = st.session_state.get('tab_session_id', '')
        if not current_tab_id:
            # 无 Tab ID，可能是首次加载，不召回
            return None
        # ========================================================================

        conn = sqlite3.connect(PERSISTENCE_DB)
        cursor = conn.cursor()

        # 查找最近 24 小时内的未完成任务
        cursor.execute("""
            SELECT task_id, status, created_at, result_json, user_input_preview, session_id
            FROM task_registry
            WHERE status NOT IN ('SUCCESS', 'FAILURE', 'TIMEOUT', 'completed', 'ZOMBIE', 'REVOKED')
            AND created_at > datetime('now', '-24 hours')
            ORDER BY created_at DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        conn.close()

        if row:
            task_id, status, created_at, result_json, input_preview, owner_session_id = row

            # ==================== P2-A1 修复：检查任务占用 ====================
            # 如果任务被其他 session_id 标记为占用，且该 session 最近有活动，则不召回
            if owner_session_id and owner_session_id != current_tab_id:
                # 检查占用 session 是否还在活跃
                try:
                    conn = sqlite3.connect(PERSISTENCE_DB)
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT COUNT(*) FROM task_registry
                        WHERE session_id = ?
                        AND created_at > datetime('now', '-10 minutes')
                    """, (owner_session_id,))
                    owner_activity = cursor.fetchone()[0]
                    conn.close()

                    if owner_activity > 0:
                        logger.debug(f"[P2-A1] 任务 {task_id[:16]}... 被其他 Tab 占用，跳过召回")
                        return None
                except Exception:
                    pass  # 检查失败，继续尝试召回
            # ========================================================================

            # 检查 Redis 中实际状态
            if CELERY_AVAILABLE:
                actual_result = poll_task_status_safe(task_id)
                actual_state = actual_result['state']

                if actual_state in ['SUCCESS', 'FAILURE']:
                    # 更新本地数据库
                    update_task_completion(task_id, actual_state, result_json)
                    logger.debug(f"[P2-A1] 任务 {task_id[:16]}... 已完成，跳过召回")
                    return None

                # P2-A1: 更新任务占用者为当前 Tab
                try:
                    conn = sqlite3.connect(PERSISTENCE_DB)
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE task_registry
                        SET session_id = ?, last_poll_at = ?
                        WHERE task_id = ?
                    """, (current_tab_id, datetime.now().isoformat(), task_id))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.warning(f"[P2-A1] 更新任务占用者失败: {e}")

                # 恢复到 session_state
                st.session_state.task_id = task_id
                st.session_state.task_state = actual_state
                st.session_state.task_start_time = created_at
                st.session_state.user_input = input_preview or ''

                logger.info(f"[P2-A1] 成功召回任务: {task_id[:16]}...")
                return task_id

        return None
    except Exception as e:
        logger.warning(f"[V7.1 P2-A1] Task recovery failed: {e}")
        return None


def update_task_completion(task_id: str, state: str, result_json: str = None):
    """���新任务完成状态"""
    try:
        conn = sqlite3.connect(PERSISTENCE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE task_registry
            SET status = ?, result_available = 1, result_json = ?, last_poll_at = ?
            WHERE task_id = ?
        """, (state, result_json, datetime.now().isoformat(), task_id))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Task completion update failed: {e}")


def get_task_history_list(limit: int = 10) -> List[Dict]:
    """获取任务历史列表"""
    try:
        conn = sqlite3.connect(PERSISTENCE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT task_id, status, created_at, user_input_preview
            FROM task_registry
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'task_id': row[0],
                'status': row[1],
                'created_at': row[2],
                'input_preview': row[3] or ''
            }
            for row in rows
        ]
    except Exception as e:
        logger.warning(f"Task history fetch failed: {e}")
        return []

# ==================== V7.1 修复 #1: 消息投递安全网 ====================
def init_local_queue_db():
    """
    V7.1 本地任务队列数据库初始化

    当 Redis 不可用时降级使用
    """
    try:
        conn = sqlite3.connect(LOCAL_QUEUE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_tasks (
                task_id TEXT PRIMARY KEY,
                user_input TEXT NOT NULL,
                config_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                last_attempt_at TEXT,
                last_error TEXT
            )
        """)

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"Local queue DB init failed: {e}")
        return False


def check_redis_health() -> Tuple[bool, str]:
    """
    V7.1 Redis 连接健康检查

    Returns:
        Tuple[bool, str]: (是否健康, 错误消息)
    """
    if not CELERY_AVAILABLE:
        return False, "Celery 模块未加载"

    try:
        celery_app = get_celery_app()

        # 获取连接并 ping
        with celery_app.connection_or_acquire() as conn:
            if not conn.connected:
                conn.ensure_connection(max_retries=2, interval_start=0.5)

            # 尝试简单操作验证连接
            conn.default_channel.close()  # 简单的连接验证

        return True, ""

    except redis.ConnectionError as e:
        return False, f"Redis 连接失败: {str(e)}"
    except Exception as e:
        return False, f"健康检查异常: {str(e)}"


def submit_to_local_queue(user_input: str, config: Dict) -> Tuple[str, Dict]:
    """
    V7.1 本地任务队列降级

    当 Redis 不可用时，将任务写入本地 SQLite
    """
    import uuid

    task_id = f"local_{uuid.uuid4().hex[:12]}"

    try:
        conn = sqlite3.connect(LOCAL_QUEUE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO pending_tasks
            (task_id, user_input, config_json, created_at, status)
            VALUES (?, ?, ?, ?, ?)
        """, (task_id, user_input, json.dumps(config), datetime.now().isoformat(), 'pending'))

        conn.commit()
        conn.close()

        # 存入 session_state
        st.session_state.task_id = task_id
        st.session_state.task_state = 'LOCAL_PENDING'
        st.session_state.task_start_time = datetime.now().isoformat()

        return task_id, {
            'success': True,
            'fallback_used': True,
            'task_id': task_id,
            'message': '任务已保存到本地队列（Redis 不可用时的降级方案）',
        }
    except Exception as e:
        return None, {
            'success': False,
            'error': str(e),
            'message': '本地队列写入失败',
        }


def submit_celery_task_with_safety(user_input: str, config: Dict) -> Tuple[Optional[str], Dict]:
    """
    V7.1 安全投递机制 - 防止消息投递黑洞

    三层防护:
    1. 投递前连接健康检查
    2. 投递中异常细粒度捕获 + 重试
    3. 投递后降级回退
    """
    dispatch_result = {
        'attempt': 0,
        'success': False,
        'error_type': None,
        'error_message': None,
        'fallback_used': False,
        'health_check_passed': False,
    }

    # ========== Phase 1: 投递前健康检查 ==========
    if CELERY_AVAILABLE:
        health_ok, health_msg = check_redis_health()
        dispatch_result['health_check_passed'] = health_ok

        if not health_ok:
            dispatch_result['error_type'] = 'REDIS_CONNECTION_FAILED'
            dispatch_result['error_message'] = health_msg

            # 降级到本地队列
            st.warning("⚠️ Redis 不可用，任务已保存到本地队列")
            return submit_to_local_queue(user_input, config)
    else:
        # Celery 未加载，直接本地队列
        dispatch_result['error_type'] = 'CELERY_NOT_AVAILABLE'
        dispatch_result['error_message'] = 'Celery 模块未加载'
        return submit_to_local_queue(user_input, config)

    # ========== Phase 2: 投递中异常捕获 + 重试 ==========
    celery_app = get_celery_app()

    task_kwargs = {
        'user_input': user_input,
        'user_domain': config.get('user_domain', 'auto-detect'),
        'hard_cap': config.get('hard_cap', 15),
        'min_score_threshold': config.get('min_score_threshold', 7.0),
        'max_iterations': config.get('max_iterations', 5),
        'execution_mode': config.get('execution_mode', 'autonomous'),
        'v7_defenses': config.get('v7_defenses', {}),
        'webhook_url': None,
        'session_id': f"v7_session_{datetime.now().strftime('%Y%m%d%H%M%S')}",
    }

    # 日志记录
    logger.debug(f"Task kwargs prepared:")
    for k, v in task_kwargs.items():
        logger.debug(f"  {k}: {v}")

    for attempt in range(1, 4):
        dispatch_result['attempt'] = attempt

        try:
            result = celery_app.send_task(
                'hypothesis_generation_task',
                kwargs=task_kwargs,
                queue='research',
                priority=5,
                retry=True,
            )

            task_id = result.id
            dispatch_result['success'] = True
            dispatch_result['task_id'] = task_id

            # 存入 session_state
            st.session_state.task_id = task_id
            st.session_state.task_state = 'PENDING'
            st.session_state.task_progress = 0
            st.session_state.task_message = '任务已派发'
            st.session_state.task_start_time = datetime.now().isoformat()
            st.session_state.pipeline_logs = [{
                'time': datetime.now().strftime('%H:%M:%S'),
                'step': 2,
                'message': f'Task dispatched: {task_id}',
                'status': 'complete'
            }]

            # 注册持久化
            register_task_persistence(task_id, user_input, config)

            return task_id, dispatch_result

        except redis.ConnectionError as e:
            dispatch_result['error_type'] = 'REDIS_FLASH_DISCONNECT'
            dispatch_result['error_message'] = f'第 {attempt} 次投递时网络闪断: {str(e)}'

            if attempt < 3:
                st.warning(f"⚠️ 投递失败 (第 {attempt} 次)，正在重试...")
                time.sleep(2 ** attempt)
            continue

        except Exception as e:
            dispatch_result['error_type'] = 'UNKNOWN_DISPATCH_ERROR'
            dispatch_result['error_message'] = str(e)
            break

    # ========== Phase 3: 投递失败降级 ==========
    if not dispatch_result['success']:
        # 降级到本地队列
        st.error(f"""
        ❌ 任务投递失败 (尝试 {dispatch_result['attempt']} 次)

        **错误类型**: {dispatch_result['error_type']}
        **错误详情**: {dispatch_result['error_message']}
        """)

        return submit_to_local_queue(user_input, config)

    return dispatch_result.get('task_id'), dispatch_result

# ==================== V7.1 修复 #3: 双重提交防护 ====================
def init_submission_guard():
    """
    V7.1 提交守卫初始化（P1-A3 修复：Tab 隔离机制）

    修复内容：
    - 增加 tab_session_id 用于区分不同 Tab
    - 增加 tab_fingerprint 用于检测新 Tab 打开
    - 使用 Redis 分布式锁（如果可用）
    """
    if 'submission_lock' not in st.session_state:
        st.session_state.submission_lock = False
    if 'last_submit_time' not in st.session_state:
        st.session_state.last_submit_time = None
    if 'submit_cooldown_until' not in st.session_state:
        st.session_state.submit_cooldown_until = None
    if 'pending_input_hash' not in st.session_state:
        st.session_state.pending_input_hash = None

    # ==================== P1-A3 修复：Tab 隔离机制 ====================
    # 为每个 Tab 分配唯一会话 ID
    if 'tab_session_id' not in st.session_state:
        st.session_state.tab_session_id = f"tab_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(os.urandom(8)) & 0xFFFFFF:06x}"

    # Tab 指纹：用于检测多 Tab 场景
    if 'tab_fingerprint' not in st.session_state:
        st.session_state.tab_fingerprint = {
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'activity_count': 0,
        }

    # 更新活动计数
    st.session_state.tab_fingerprint['last_activity'] = datetime.now().isoformat()
    st.session_state.tab_fingerprint['activity_count'] = st.session_state.tab_fingerprint.get('activity_count', 0) + 1
    # ========================================================================


def detect_multi_tab_scenario() -> Tuple[bool, str]:
    """
    P1-A3: 检测多 Tab 同时打开场景

    Returns:
        Tuple[bool, str]: (是否检测到多Tab, 警告消息)
    """
    try:
        # 检查持久化数据库中是否有其他活跃 Tab
        conn = sqlite3.connect(PERSISTENCE_DB)
        cursor = conn.cursor()

        # 查找最近 5 分钟内的其他 Tab
        current_tab_id = st.session_state.get('tab_session_id', '')
        five_minutes_ago = (datetime.now() - timedelta(minutes=5)).isoformat()

        cursor.execute("""
            SELECT DISTINCT session_id, created_at
            FROM task_registry
            WHERE created_at > ?
            AND session_id != ?
            ORDER BY created_at DESC
            LIMIT 3
        """, (five_minutes_ago, current_tab_id))

        other_tabs = cursor.fetchall()
        conn.close()

        if len(other_tabs) > 0:
            return True, f"检测到 {len(other_tabs)} 个其他活跃 Tab，为避免冲突建议关闭其他 Tab"

        return False, ""

    except Exception as e:
        logger.warning(f"[P1-A3] 多 Tab 检测失败: {e}")
        return False, ""


def check_submission_guard(user_input: str) -> Tuple[bool, str]:
    """
    V7.1 提交守卫检查（P1-A3 修复：Tab 隔离）

    Returns:
        Tuple[bool, str]: (是否允许提交, 拒绝原因)
    """
    now = datetime.now()

    # ==================== P1-A3 修复：多 Tab 检测 ====================
    has_multi_tab, multi_tab_msg = detect_multi_tab_scenario()
    if has_multi_tab:
        # 仅警告，不阻止（用户可能确实需要多 Tab）
        logger.warning(f"[P1-A3] {multi_tab_msg}")
    # ========================================================================

    # 检查 1: 提交锁（带 Tab 隔离）
    if st.session_state.submission_lock:
        # 检查锁是否由当前 Tab 持有
        lock_holder = st.session_state.get('lock_holder_tab', '')
        current_tab = st.session_state.get('tab_session_id', '')

        if lock_holder and lock_holder != current_tab:
            # 锁由其他 Tab 持有 → 警告但不阻止（可能是过期锁）
            return False, f"其他 Tab 正在提交任务，请等待或刷新页面"

        return False, "已有任务正在提交中，请等待..."

    # 检查 2: 冷却期
    cooldown_until = st.session_state.submit_cooldown_until
    if cooldown_until:
        cooldown_time = datetime.fromisoformat(cooldown_until)
        if now < cooldown_time:
            remaining = int((cooldown_time - now).total_seconds())
            return False, f"冷却期保护，请等待 {remaining} 秒后再次提交"
        else:
            st.session_state.submit_cooldown_until = None

    # 检查 3: 重复内容检测
    if user_input.strip():
        input_hash = hashlib.sha256(user_input.encode()).hexdigest()[:16]

        if input_hash == st.session_state.pending_input_hash:
            if st.session_state.task_id:
                return False, f"相同内容已提交 (Task: {st.session_state.task_id[:16]}...)"

    # 检查 4: 防抖间隔
    last_submit = st.session_state.last_submit_time
    if last_submit:
        last_time = datetime.fromisoformat(last_submit)
        elapsed = (now - last_time).total_seconds()
        if elapsed < SUBMIT_DEBOUNCE_SECONDS:
            return False, f"提交过于频繁，请等待 {int(SUBMIT_DEBOUNCE_SECONDS - elapsed)} 秒"

    return True, ""


def acquire_submission_lock(user_input: str):
    """获取提交锁（P1-A3 修复：记录锁持有者）"""
    st.session_state.submission_lock = True
    st.session_state.last_submit_time = datetime.now().isoformat()

    # P1-A3: 记录锁持有者 Tab
    st.session_state.lock_holder_tab = st.session_state.get('tab_session_id', '')

    if user_input.strip():
        st.session_state.pending_input_hash = hashlib.sha256(user_input.encode()).hexdigest()[:16]
    st.session_state.submit_cooldown_until = (datetime.now() + timedelta(seconds=SUBMIT_COOLDOWN_SECONDS)).isoformat()


def release_submission_lock():
    """释放提交锁"""
    st.session_state.submission_lock = False

# ==================== V7.1 修复 #4: 僵尸轮询防护 ====================
def init_poll_guard():
    """V7.1 轮询守卫初始化"""
    if 'poll_start_time' not in st.session_state:
        st.session_state.poll_start_time = None
    if 'poll_attempt_count' not in st.session_state:
        st.session_state.poll_attempt_count = 0
    if 'last_state_change_time' not in st.session_state:
        st.session_state.last_state_change_time = None
    if 'last_known_state' not in st.session_state:
        st.session_state.last_known_state = None


def check_poll_guard(task_id: str) -> Tuple[bool, str, Dict]:
    """
    V7.1 轮询守卫检查

    Returns:
        Tuple[bool, str, Dict]: (是否继续轮询, 原因代码, 详情)
    """
    now = datetime.now()

    # 检查 1: 全局超时
    poll_start = st.session_state.poll_start_time
    if poll_start:
        start_time = datetime.fromisoformat(poll_start)
        elapsed_minutes = (now - start_time).total_seconds() / 60

        if elapsed_minutes > ZOMBIE_TASK_THRESHOLD_MINUTES:
            return False, "GLOBAL_TIMEOUT", {
                'elapsed_minutes': elapsed_minutes,
                'reason': f'任务轮询超过 {ZOMBIE_TASK_THRESHOLD_MINUTES} 分钟'
            }

    # 检查 2: 最大轮询次数
    poll_count = st.session_state.poll_attempt_count
    if poll_count > MAX_POLL_ATTEMPTS:
        return False, "MAX_POLL_EXCEEDED", {
            'poll_count': poll_count,
            'reason': f'轮询次数超过 {MAX_POLL_ATTEMPTS} 次'
        }

    # 检查 3: Worker 心跳
    worker_alive = check_worker_heartbeat()
    if not worker_alive:
        return False, "WORKER_NOT_RESPONDING", {
            'reason': 'Celery Worker 无响应'
        }

    # 检查 4: 状态停滞检测
    last_state = st.session_state.last_known_state
    last_change = st.session_state.last_state_change_time

    if last_change and last_state in ['PENDING', 'PROGRESS']:
        change_time = datetime.fromisoformat(last_change)
        stagnant_minutes = (now - change_time).total_seconds() / 60

        if stagnant_minutes > 30:
            return False, "STATE_STagnant", {
                'stagnant_minutes': stagnant_minutes,
                'last_state': last_state,
                'reason': '任务状态 30 分钟无变化'
            }

    return True, "CONTINUE", {}


def check_worker_heartbeat() -> bool:
    """V7.1 Worker 心跳检测"""
    if not CELERY_AVAILABLE:
        return False

    try:
        celery_app = get_celery_app()
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()

        return active_workers is not None and len(active_workers) > 0
    except Exception:
        return False


def poll_task_status_safe(task_id: str) -> Dict:
    """
    V7.1 安全轮询（带守卫检查）
    """
    init_poll_guard()

    # 更新轮询计数
    st.session_state.poll_attempt_count += 1

    # 检查守卫
    can_continue, reason, details = check_poll_guard(task_id)

    if not can_continue:
        return handle_poll_timeout(task_id, reason, details)

    # 正常轮询
    poll_result = poll_task_status(task_id)

    # 更新状态变化时间
    current_state = poll_result['state']
    last_state = st.session_state.last_known_state

    if current_state != last_state:
        st.session_state.last_known_state = current_state
        st.session_state.last_state_change_time = datetime.now().isoformat()

    # 检查完成状态
    if current_state in ['SUCCESS', 'FAILURE']:
        # 清理轮询守卫
        st.session_state.poll_start_time = None
        st.session_state.poll_attempt_count = 0

        # 更新持久化
        update_task_completion(task_id, current_state)

    return poll_result


def handle_poll_timeout(task_id: str, reason: str, details: Dict) -> Dict:
    """
    V7.1 超时处理（P1-A2 修复：自动撤销僵尸任务）

    修复内容：
    - 超时后自动撤销 Celery 任务，释放 Worker 资源
    - 标记任务为 ZOMBIE 状态，便于后续清理
    - 记录撤销日志用于审计
    """
    st.session_state.task_state = 'TIMEOUT'
    st.session_state.error_occurred = True
    st.session_state.error_type = reason
    st.session_state.error_message = details.get('reason', '轮询超时')

    # ==================== P1-A2 修复：自动撤销僵尸任务 ====================
    if CELERY_AVAILABLE and task_id and not task_id.startswith('local_'):
        try:
            celery_app = get_celery_app()

            # 检查任务是否仍在运行
            async_result = AsyncResult(task_id, app=celery_app)
            current_state = async_result.state

            if current_state in ['PENDING', 'PROGRESS', 'STARTED']:
                # 任务仍在运行或等待 → 强制撤销
                celery_app.control.revoke(task_id, terminate=True)
                logger.warning(f"[V7.1 P1-A2] 僵尸任务已撤销: {task_id[:16]}... (原因: {reason})")

                # 更新持久化数据库为 ZOMBIE 状态
                update_task_completion(task_id, 'ZOMBIE')

                # 记录撤销日志
                log_zombie_task_revoke(task_id, reason, details)

        except Exception as e:
            logger.warning(f"[V7.1 P1-A2] 撤销僵尸任务失败: {e}")
    # ========================================================================

    return {
        'state': 'TIMEOUT',
        'progress': 0,
        'message': details.get('reason', '轮询超时'),
        'timeout_reason': reason,
        'details': details,
        'task_revoked': True,  # 标记任务已被撤销
    }


def log_zombie_task_revoke(task_id: str, reason: str, details: Dict):
    """
    P1-A2: 僵尸任务撤销日志记录

    记录到本地文件用于审计和后续分析
    """
    try:
        log_entry = {
            'task_id': task_id,
            'revoked_at': datetime.now().isoformat(),
            'reason': reason,
            'details': details,
        }

        zombie_log_path = DATA_DIR / 'zombie_tasks_revoked.jsonl'

        with open(zombie_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    except Exception as e:
        logger.warning(f"[V7.1 P1-A2] 僵尸任务日志记录失败: {e}")


def cleanup_old_zombie_tasks(days: int = 7):
    """
    P1-A2: 定期清理旧僵尸任务日志

    Args:
        days: 保留最近 N 天的日志
    """
    try:
        zombie_log_path = DATA_DIR / 'zombie_tasks_revoked.jsonl'

        if not zombie_log_path.exists():
            return

        cutoff_time = datetime.now() - timedelta(days=days)
        cleaned_log_path = DATA_DIR / f'zombie_tasks_revoked_cleaned_{datetime.now().strftime("%Y%m%d")}.jsonl'

        retained_entries = []

        with open(zombie_log_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    revoked_at = datetime.fromisoformat(entry.get('revoked_at', ''))

                    if revoked_at > cutoff_time:
                        retained_entries.append(line)
                except (json.JSONDecodeError, ValueError):
                    continue

        # 重写日志文件（仅保留最近 N 天）
        with open(zombie_log_path, 'w', encoding='utf-8') as f:
            f.writelines(retained_entries)

        logger.warning(f"[V7.1 P1-A2] 僵尸任务日志清理完成: 保留最近 {days} 天")

    except Exception as e:
        logger.warning(f"[V7.1 P1-A2] 僵尸任务日志清理失败: {e}")


def poll_task_status(task_id: str) -> Dict:
    """轮询任务状态"""
    if not CELERY_AVAILABLE or not task_id:
        return {'state': 'UNKNOWN', 'progress': 0, 'message': 'Celery不可用'}

    # 处理本地任务
    if task_id.startswith('local_'):
        return poll_local_task_status(task_id)

    try:
        celery_app = get_celery_app()
        async_result = AsyncResult(task_id, app=celery_app)

        state = async_result.state
        info = async_result.info if async_result.info else {}

        progress = 0
        message = ''

        if state == 'PROGRESS':
            progress = info.get('progress', 0)
            message = info.get('message', '执行中...')
        elif state == 'SUCCESS':
            progress = 100
            message = '任务完成'
            st.session_state.task_result = async_result.result
        elif state == 'FAILURE':
            progress = 0
            message = info.get('error', '任务失败') if isinstance(info, dict) else str(info)
            st.session_state.error_occurred = True
            st.session_state.error_message = message
            if isinstance(info, dict):
                st.session_state.error_type = info.get('result_type', 'unknown')
        elif state == 'PENDING':
            progress = 0
            message = '等待 Worker 接收...'

        # 更新 session_state
        st.session_state.task_state = state
        st.session_state.task_progress = progress
        st.session_state.task_message = message

        # 添加 pipeline log
        if message and len(st.session_state.pipeline_logs) < 50:
            st.session_state.pipeline_logs.append({
                'time': datetime.now().strftime('%H:%M:%S'),
                'step': max(1, min(15, progress // 7 + 1)),
                'message': message,
                'status': 'active' if state == 'PROGRESS' else state.lower()
            })

        return {
            'state': state,
            'progress': progress,
            'message': message,
            'info': info,
            'result': async_result.result if state == 'SUCCESS' else None
        }

    except Exception as e:
        return {
            'state': 'ERROR',
            'progress': 0,
            'message': f'轮询异常: {str(e)}'
        }


def poll_local_task_status(task_id: str) -> Dict:
    """轮询本地任务状态"""
    try:
        conn = sqlite3.connect(LOCAL_QUEUE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status, retry_count, last_error
            FROM pending_tasks
            WHERE task_id = ?
        """, (task_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            status, retry_count, last_error = row
            return {
                'state': 'LOCAL_' + status.upper(),
                'progress': 0,
                'message': f'本地任务状态: {status}' + (f' (错误: {last_error})' if last_error else ''),
            }

        return {'state': 'UNKNOWN', 'progress': 0, 'message': '任务未找到'}

    except Exception as e:
        return {'state': 'ERROR', 'progress': 0, 'message': f'本地任务查询异常: {str(e)}'}

# ==================== 侧边栏配置 ====================
def render_sidebar_configurator():
    """V7.1 侧边栏配置"""
    st.sidebar.markdown("""
    <div class="sidebar-config-header">
        ⚙️ V7.1 动态调度中心
    </div>
    """, unsafe_allow_html=True)

    # Execution Mode
    st.sidebar.markdown("### 🎯 执行模式")
    execution_mode = st.sidebar.radio(
        "选择执行模式",
        options=['autonomous', 'hitl'],
        format_func=lambda x: "🤖 Autonomous" if x == 'autonomous' else "👤 HITL",
        key='execution_mode_select',
    )
    st.session_state.execution_mode = execution_mode

    st.sidebar.markdown("---")

    # 防熔断参数
    st.sidebar.markdown("### 🛡️ 防熔断参数")

    hard_cap = st.sidebar.slider(
        "API 调用上限",
        min_value=5, max_value=30,
        value=st.session_state.get('hard_cap', 15),
        key='hard_cap_slider'
    )
    st.session_state.hard_cap = hard_cap

    min_score = st.sidebar.slider(
        "分数及格线",
        min_value=5.0, max_value=9.0,
        value=st.session_state.get('min_score_threshold', 7.0),
        step=0.5,
        key='min_score_slider'
    )
    st.session_state.min_score_threshold = min_score

    max_iter = st.sidebar.slider(
        "最大迭代次数",
        min_value=1, max_value=10,
        value=st.session_state.get('max_iterations', 5),
        key='max_iter_slider'
    )
    st.session_state.max_iterations = max_iter

    st.sidebar.markdown("---")

    # V7.1 新增：文献质量过滤参数
    st.sidebar.markdown("### 📚 文献质量过滤")

    min_if = st.sidebar.number_input(
        "最小影响因子 (IF)",
        min_value=0.0,
        max_value=50.0,
        value=st.session_state.get('min_if', 0.0),
        step=0.5,
        format="%.1f",
        help="只检索 IF ≥ 此值的期刊文献（0 表示不限）",
        key='min_if_input'
    )
    st.session_state.min_if = min_if

    date_range_start = st.sidebar.number_input(
        "起始年份",
        min_value=1990,
        max_value=2030,
        value=st.session_state.get('date_range_start', 2020),
        step=1,
        help="只检索此年份之后的文献",
        key='date_start_input'
    )
    st.session_state.date_range_start = date_range_start

    date_range_end = st.sidebar.number_input(
        "结束年份",
        min_value=date_range_start,
        max_value=2030,
        value=st.session_state.get('date_range_end', 2026),
        step=1,
        help="只检索此年份之前的文献",
        key='date_end_input'
    )
    st.session_state.date_range_end = date_range_end

    st.sidebar.markdown("---")

    # V7.0 漏洞修复开关
    st.sidebar.markdown("### 🔒 V7.0 漏洞修复")

    enable_intent = st.sidebar.checkbox(
        "Intent Sanitizer",
        value=st.session_state.get('enable_intent_sanitizer', True),
        key='enable_intent_check'
    )
    st.session_state.enable_intent_sanitizer = enable_intent

    enable_physical = st.sidebar.checkbox(
        "Physical Validator",
        value=st.session_state.get('enable_physical_validator', True),
        key='enable_physical_check'
    )
    st.session_state.enable_physical_validator = enable_physical

    enable_anchor = st.sidebar.checkbox(
        "Hard-Link Anchor",
        value=st.session_state.get('enable_hard_link_anchor', True),
        key='enable_anchor_check'
    )
    st.session_state.enable_hard_link_anchor = enable_anchor

    st.sidebar.markdown("---")

    # 配置摘要
    st.sidebar.markdown("### 📦 配置摘要")

    config_summary = {
        'execution_mode': execution_mode,
        'hard_cap': hard_cap,
        'min_score_threshold': min_score,
        'max_iterations': max_iter,
        'user_domain': st.session_state.get('user_domain', 'auto-detect'),
        # V7.1 新增：文献质量过滤参数（打包进 Celery Task Payload）
        'min_if': min_if,
        'date_range_start': date_range_start,
        'date_range_end': date_range_end,
        'v7_defenses': {
            'intent_sanitizer': enable_intent,
            'physical_validator': enable_physical,
            'hard_link_anchor': enable_anchor,
        }
    }

    with st.sidebar.expander("🔍 配置预览", expanded=False):
        st.json(config_summary)

    return config_summary

# ==================== 任务历史侧边栏 ====================
def render_task_history_sidebar():
    """V7.1 任务历史列表"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📜 历史任务")

    history = get_task_history_list(5)

    if not history:
        st.sidebar.info("暂无历史任务")
        return

    for item in history:
        task_id = item['task_id']
        status = item['status']
        created_at = item['created_at'][:16] if item['created_at'] else 'N/A'
        preview = item['input_preview'][:30] + '...' if item['input_preview'] and len(item['input_preview']) > 30 else item['input_preview']

        status_color = {
            'SUCCESS': '🟢',
            'FAILURE': '🔴',
            'PENDING': '🟡',
            'PROGRESS': '🔵',
            'TIMEOUT': '🟠',
        }.get(status, '⚪')

        st.sidebar.markdown(f"""
        {status_color} **{task_id[:12]}...**
        - 状态: `{status}` | 时间: {created_at}
        - 内容: {preview}
        """)

        # 召回按钮（仅未完成任务）
        if status not in ['SUCCESS', 'FAILURE', 'TIMEOUT']:
            if st.sidebar.button("召回", key=f"recover_{task_id[:8]}"):
                st.session_state.task_id = task_id
                st.session_state.task_state = status
                st.rerun()

# ==================== Pipeline 可视化 ====================
def render_pipeline_visualizer():
    """V7.1 Pipeline 可视化"""
    task_progress = st.session_state.get('task_progress', 0)
    task_state = st.session_state.get('task_state', 'PENDING')
    task_message = st.session_state.get('task_message', '')
    pipeline_logs = st.session_state.get('pipeline_logs', [])

    st.markdown("""
    <div class="terminal-box">
        <div class="terminal-header">🔬 V7.1 Pipeline Status Monitor</div>
    """, unsafe_allow_html=True)

    # 进度条
    st.markdown(f"""
    <div class="v7-progress-bar">
        <div class="v7-progress-fill" style="width: {task_progress}%"></div>
    </div>
    <div style="color: #60a5fa; font-size: 0.8rem; margin-top: 0.3rem;">
        Progress: {task_progress}% | State: {task_state}
    </div>
    """, unsafe_allow_html=True)

    # 当前步骤
    current_step_idx = max(1, min(15, task_progress // 7 + 1))
    current_step = PIPELINE_STEPS[current_step_idx - 1]

    st.markdown(f"""
    <div class="terminal-line terminal-step-active">
        ▶️ Step {current_step['step']}: {current_step['icon']} {current_step['name']}
    </div>
    <div class="terminal-line" style="color: #fbbf24;">
        📝 {task_message}
    </div>
    """, unsafe_allow_html=True)

    # Pipeline 步骤列表
    for step in PIPELINE_STEPS:
        step_idx = step['step']

        if step_idx < current_step_idx:
            status_class = 'terminal-step-complete'
            status_icon = '✓'
        elif step_idx == current_step_idx and task_state == 'PROGRESS':
            status_class = 'terminal-step-active'
            status_icon = '▶'
        elif task_state == 'FAILURE' and step_idx <= current_step_idx:
            status_class = 'terminal-step-error'
            status_icon = '✗'
        else:
            status_class = 'terminal-step-pending'
            status_icon = '○'

        st.markdown(f"""
        <div class="terminal-line {status_class}">
            {status_icon} {step['icon']} Step {step['step']}: {step['name']}
        </div>
        """, unsafe_allow_html=True)

    # 日志输出
    st.markdown("""
    <div class="terminal-header" style="margin-top: 1rem;">📜 Execution Log</div>
    """, unsafe_allow_html=True)

    for log_entry in pipeline_logs[-15:]:
        status_class = {
            'complete': 'terminal-step-complete',
            'active': 'terminal-step-active',
            'error': 'terminal-step-error',
            'failure': 'terminal-step-error',
        }.get(log_entry.get('status', 'pending'), 'terminal-step-pending')

        st.markdown(f"""
        <div class="terminal-line {status_class}">
            <span class="terminal-time">[{log_entry.get('time', 'N/A')}]</span>
            Step {log_entry.get('step', '?')}: {log_entry.get('message', '')}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ==================== 轮询统计显示 ====================
def render_poll_stats():
    """V7.1 轮询统计卡片"""
    poll_start = st.session_state.poll_start_time
    poll_count = st.session_state.poll_attempt_count

    if poll_start:
        start_time = datetime.fromisoformat(poll_start)
        elapsed = (datetime.now() - start_time).total_seconds()
        elapsed_str = f"{int(elapsed // 60)}分 {int(elapsed % 60)}秒"
    else:
        elapsed_str = "N/A"

    st.markdown(f"""
    <div class="poll-stats-card">
        <p><strong>轮询统计</strong></p>
        <p>已轮询: {poll_count} 次 / {MAX_POLL_ATTEMPTS} | 耗��: {elapsed_str}</p>
    </div>
    """, unsafe_allow_html=True)

# ==================== 安全提交按钮 ====================
def render_safe_submit_button(user_input: str, config: Dict) -> Optional[str]:
    """V7.1 安全提交按钮"""
    init_submission_guard()

    task_id = st.session_state.get('task_id')
    task_state = st.session_state.get('task_state')

    # 任务已进入执行状态
    if task_state in ['PROGRESS', 'SUCCESS', 'FAILURE', 'TIMEOUT']:
        return None

    # 任务等待中
    if task_state == 'PENDING' and task_id:
        st.info(f"""
        ⏳ 任务已提交

        **Task ID**: `{task_id[:20]}...`
        **状态**: 等待 Worker 接收

        请勿重复提交，系统会自动轮询状态...
        """)
        return None

    # 检查提交守卫
    can_submit, reason = check_submission_guard(user_input)

    if not can_submit:
        st.button("🚀 启动推演", type="secondary", disabled=True, key='submit_disabled')
        st.warning(f"🔒 {reason}")
        return None

    # 正常提交
    if st.button("🚀 启动推演", type="primary", key='submit_btn'):
        if not user_input.strip():
            st.warning("⚠️ 请输入研究想法")
            return None

        # 获取提交锁
        acquire_submission_lock(user_input)

        try:
            task_id, dispatch_result = submit_celery_task_with_safety(user_input, config)

            if task_id:
                st.success(f"✅ 任务已派发: {task_id[:20]}...")
                st.info("⏳ 正在异步执行，请稍候...")

                # 初始化轮询开始时间
                st.session_state.poll_start_time = datetime.now().isoformat()
                st.session_state.poll_attempt_count = 0

                return task_id
            else:
                release_submission_lock()
                st.error(f"❌ 投递失败: {dispatch_result.get('error_message', 'Unknown')}")
                return None

        except Exception as e:
            release_submission_lock()
            st.error(f"❌ 提交异常: {str(e)}")
            return None

    return None

# ==================== 结果渲染 ====================
def render_success_report(result: Dict):
    """渲染成功报告"""
    st.markdown("""
    <div class="success-card">
        <h2>🎉 研究假设生成成功</h2>
    </div>
    """, unsafe_allow_html=True)

    payload = result.get('payload', {})
    hypothesis = payload.get('hypothesis', {})
    fitness = payload.get('fitness_result', {})

    tabs = st.tabs([
        "📝 假���概述", "📚 文献支撑", "🔬 技术路线",
        "📊 适应度评估", "🛡️ 审计结果", "📈 资源消耗", "📄 完整报告"
    ])

    with tabs[0]:
        st.markdown(f"""
        <div class="report-container">
            <h3>{hypothesis.get('title', '未命名假设')}</h3>
            <p><strong>学科领域</strong>: {payload.get('domain', 'N/A')}</p>
            <p><strong>描述</strong>: {hypothesis.get('description', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)

    with tabs[1]:
        verified_ids = result.get('verified_ids', {})
        st.markdown(f"""
        <div class="report-container">
            <h4>验证过的文献引用</h4>
            <p>PubMed PMIDs: {len(verified_ids.get('pmids', []))} 篇</p>
        </div>
        """, unsafe_allow_html=True)

    with tabs[3]:
        st.markdown(f"""
        <div class="report-container">
            <h4>混合适应度评估</h4>
            <p><strong>总分</strong>: {fitness.get('hybrid_fitness', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)

    with tabs[6]:
        full_report = generate_full_markdown_report(result)
        st.markdown(full_report)
        st.download_button(
            label="📥 下载报告",
            data=full_report.encode('utf-8'),
            file_name=f"V7_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown"
        )


def render_rejection_report(error_info: Dict, user_input: str):
    """渲染否决报告"""
    st.markdown("""
    <div class="rejection-card">
        <h2>🚫 科研否决报告</h2>
        <div class="reason">研究假设生成失败</div>
    </div>
    """, unsafe_allow_html=True)

    error_type = error_info.get('result_type', 'unknown')
    error_message = error_info.get('error', '未知错误')

    st.error(f"""
    **否决类型**: {error_type}
    **否决原因**: {error_message}
    """)


def render_timeout_report(task_id: str, reason: str, details: Dict):
    """渲染超时报告"""
    st.markdown("""
    <div class="rejection-card">
        <h2>⏰ 任务超时</h2>
    </div>
    """, unsafe_allow_html=True)

    if reason == "GLOBAL_TIMEOUT":
        st.error(f"""
        任务轮询超过 {details.get('elapsed_minutes', 0)} 分钟

        **可能原因**:
        - Worker 进程被系统强杀 (OOM)
        - 网络连接中断
        - 任务逻辑死循环
        """)
    elif reason == "WORKER_NOT_RESPONDING":
        st.error("""
        Celery Worker 无响应

        请检查 Worker 是否正常运行
        """)
    elif reason == "STATE_STagnant":
        st.warning(f"""
        任务状态 {details.get('stagnant_minutes', 0)} 分钟无变化

        **最后状态**: {details.get('last_state', 'Unknown')}
        """)

    # 撤销按钮
    if st.button("🚫 撤销僵尸任务", key='revoke_zombie'):
        if CELERY_AVAILABLE:
            celery_app = get_celery_app()
            celery_app.control.revoke(task_id, terminate=True)
            st.success("✅ 任务已撤销")

        # 清理状态
        for key in ['task_id', 'task_state', 'poll_start_time', 'poll_attempt_count']:
            st.session_state[key] = None if key != 'poll_attempt_count' else 0

        update_task_completion(task_id, 'REVOKED')
        st.rerun()


def generate_full_markdown_report(result: Dict) -> str:
    """生成 Markdown 报告"""
    payload = result.get('payload', {})
    hypothesis = payload.get('hypothesis', {})

    lines = [
        "# 🔬 V7.1 研究假设生成报告",
        "",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> Task ID: {result.get('task_id', 'N/A')}",
        "",
        "---",
        "",
        "## 📋 假设概述",
        "",
        f"**标题**: {hypothesis.get('title', 'N/A')}",
        f"**学科领域**: {payload.get('domain', 'N/A')}",
        "",
        "---",
        "",
        "> 本报告由 V7.1 科研引擎生成",
    ]

    return "\n".join(lines)

# ==================== 主界面 ====================
def render_main_interface():
    """V7.1 主界面"""

    # 标题
    st.markdown("""
    <div class="v7-header">
        <h1>🔬 V7.1 科研引擎 - 异步控制台</h1>
        <div class="subtitle">
            通信边界加固版 | 防丢包 · 防死锁 · 防僵尸轮询
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 用户输入区
    st.markdown("### 📝 研究想法输入")

    col1, col2 = st.columns([3, 1])

    with col1:
        user_input = st.text_area(
            "输入您的研究想法",
            placeholder="例如：阿尔茨海默病患者海马体萎缩与认知功能下降的关系研究...",
            height=150,
            key='user_input_area'
        )
        st.session_state.user_input = user_input

    with col2:
        user_domain = st.selectbox(
            "学科领域",
            options=['auto-detect', 'medicine', 'biology', 'neuroscience',
                     'genomics', 'bioinformatics', 'biostatistics'],
            format_func=lambda x: "🔍 自动检测" if x == 'auto-detect' else x.upper(),
            key='domain_select'
        )
        st.session_state.user_domain = user_domain

    # 侧边栏配置
    config = render_sidebar_configurator()

    # 任务历史
    render_task_history_sidebar()

    # 任务状态检查
    task_id = st.session_state.get('task_id')
    task_state = st.session_state.get('task_state')

    # 提交按钮
    render_safe_submit_button(user_input, config)

    # 任务进行中
    if task_state == 'PROGRESS':
        st.markdown(f"""
        <div class="status-card">
            <p><strong>任务ID</strong>: {task_id[:20]}...</p>
            <p><strong>状态</strong>: 执行中...</p>
        </div>
        """, unsafe_allow_html=True)

        # 轮询统计
        render_poll_stats()

        # Pipeline 可视化
        render_pipeline_visualizer()

        # 自动轮询
        if AUTOREFRESH_AVAILABLE:
            st_autorefresh(interval=POLL_INTERVAL_SECONDS * 1000, key=f"poll_{task_id}")
            poll_result = poll_task_status_safe(task_id)

            if poll_result['state'] == 'SUCCESS':
                st.success("🎉 任务执行成功！")
                st.rerun()
            elif poll_result['state'] == 'FAILURE':
                st.error("❌ 任务执行失败")
                st.rerun()
            elif poll_result['state'] == 'TIMEOUT':
                render_timeout_report(task_id, poll_result.get('timeout_reason', 'UNKNOWN'), poll_result.get('details', {}))
            else:
                st.info(f"🔄 自动刷新中... 进度: {poll_result['progress']}%")
        else:
            if st.button("🔄 手动检查", key='manual_poll'):
                poll_result = poll_task_status_safe(task_id)
                st.rerun()

    # 任务成功
    elif task_state == 'SUCCESS':
        result = st.session_state.get('task_result', {})
        render_success_report(result)

        if st.button("🔄 开始新研究", key='new_research'):
            for key in ['task_id', 'task_state', 'task_result', 'pipeline_logs', 'poll_start_time', 'poll_attempt_count']:
                st.session_state[key] = None if key != 'poll_attempt_count' else 0
            st.session_state.task_progress = 0
            st.rerun()

    # 任务失败
    elif task_state == 'FAILURE':
        error_info = st.session_state.get('task_result', {})
        if not error_info:
            error_info = {
                'result_type': st.session_state.get('error_type', 'unknown'),
                'error': st.session_state.get('error_message', '任务执行失败')
            }
        render_rejection_report(error_info, st.session_state.get('user_input', ''))

        if st.button("🔄 重新提交", key='retry_submit'):
            for key in ['task_id', 'task_state', 'error_occurred', 'error_type', 'error_message', 'pipeline_logs']:
                st.session_state[key] = None if key != 'error_occurred' else False
            st.session_state.task_progress = 0
            st.rerun()

    # 任务超时
    elif task_state == 'TIMEOUT':
        render_timeout_report(
            task_id,
            st.session_state.get('error_type', 'UNKNOWN'),
            {'reason': st.session_state.get('error_message', '超时')}
        )

    # 本地任务
    elif task_state == 'LOCAL_PENDING':
        st.info(f"""
        💾 本地任务模式

        **Task ID**: `{task_id}`
        **状态**: 任务已保存到本地队列

        Redis 服务恢复后将自动投递
        """)

        if st.button("🔄 检查 Redis 状态", key='check_redis'):
            health_ok, _ = check_redis_health()
            if health_ok:
                st.success("✅ Redis 已恢复")
                # 尝试重新投递
                st.rerun()
            else:
                st.warning("⚠️ Redis 仍不可用")

    # Celery 不可用提示
    if not CELERY_AVAILABLE:
        st.markdown("""
        <div class="status-card warning">
            <h4>⚠️ Celery 后端不可用</h4>
            <p>异步任务系统未启动，将使用本地队列模式</p>
        </div>
        """, unsafe_allow_html=True)

# ==================== 主程序入口 ====================
def main():
    """V7.1 主程序入口 - 集中式日志挂载版"""
    logger.info("app.py 开始执行...")

    # 初始化 Session State
    init_session_state()
    logger.debug("Session State 初始化完成")

    # 初始化持久化数据库
    init_task_persistence_db()
    init_local_queue_db()
    logger.debug("持久化数据库初始化完成")

    # 初始化提交守卫
    init_submission_guard()
    init_poll_guard()
    logger.debug("守卫机制初始化完成")

    # 刷新后任务召回
    if st.session_state.task_id is None:
        recovered = recover_lost_task_on_reload()
        if recovered:
            st.toast(f"🔄 已自动恢复任务: {recovered[:12]}...")
            logger.info(f"任务召回成功: {recovered}")

    # 渲染主界面
    render_main_interface()

    logger.info("app.py 执行完成")


if __name__ == '__main__':
    main()