# -*- coding: utf-8 -*-
"""
V7.5 Phoenix Evolution UI - 工业级分布式架构 + 演化可视化版

【架构红线 - 严禁删除】：
- Celery + Redis 分布式任务分发逻辑
- SQLite 状态存储与恢复逻辑
- 冷却期 30s、防抖 5s、多 Tab 提交防护
- Redis/Worker 心跳检测指示灯

【V7.5 新增：演化实验室渲染引擎】：
1. 版本滑块：v1.0 到 v1.9 自由切换
2. 对抗溯源看板：红方攻击点 + 蓝方补丁响应
3. 最佳准方案置顶：MAX_PHOENIX_EXCEEDED 时提取最高 Science Score 版本
4. Promise Dashboard：创新性、抗性、实证度

作者: V7.5 架构工程师
日期: 2026-04-19
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

# ==================== 强制 UTF-8 编码环境 ====================
if sys.platform == "win32":
    try:
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
        if sys.stdout is not None and not sys.stdout.closed:
            try:
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, ValueError):
                pass
        if sys.stderr is not None and not sys.stderr.closed:
            try:
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, ValueError):
                pass
    except Exception:
        pass

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
env_path = project_root / '.env'
load_dotenv(env_path, encoding='utf-8', override=True)

import streamlit as st

# ==================== Celery + Redis 组件导入 ====================
try:
    from celery.result import AsyncResult
    import redis
    from src.core.celery_tasks_v75 import (
        get_celery_app,
        TaskState,
        TaskResult,
        hypothesis_generation_task_v75_impl,
    )
    CELERY_AVAILABLE = True
except ImportError as e:
    CELERY_AVAILABLE = False
    logger.warning(f"Celery components not available: {e}")

# ==================== st_autorefresh 自动轮询导入 ====================
try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False
    logger.warning("streamlit-autorefresh not available")

# ==================== V7.4-G: 物理公理检测器导入 ====================
try:
    from src.core.pseudoscience_detector import PseudoscienceDetector
    PSEUDOSCIENCE_DETECTOR_AVAILABLE = True
except ImportError:
    PSEUDOSCIENCE_DETECTOR_AVAILABLE = False

# ==================== V7.2: 拒绝报告生成器导入 ====================
try:
    from src.core.rejection_report import (
        RejectionReportGenerator,
        RejectionType,
        ScientificRejectionReport,
    )
    REJECTION_REPORT_AVAILABLE = True
except ImportError:
    REJECTION_REPORT_AVAILABLE = False

# ==================== V7.1 常量定义 ====================
ZOMBIE_TASK_THRESHOLD_MINUTES = 60
MAX_POLL_ATTEMPTS = 100
POLL_INTERVAL_SECONDS = 3
SUBMIT_COOLDOWN_SECONDS = 30
SUBMIT_DEBOUNCE_SECONDS = 5

# 持久化数据库路径
DATA_DIR = project_root / 'data'
DATA_DIR.mkdir(exist_ok=True)
PERSISTENCE_DB = DATA_DIR / 'task_persistence.db'
LOCAL_QUEUE_DB = DATA_DIR / 'local_task_queue.db'

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="V7.5 Phoenix Evolution - 工业级分布式",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "V7.5 Phoenix Evolution - 凤凰协议演化型科研引擎"
    }
)

# ==================== Pipeline 状态定义 ====================
PIPELINE_STEPS = [
    {"step": 1, "name": "Intent Sanitizer", "icon": "🛡️", "description": "意图清洗预检"},
    {"step": 2, "name": "Celery Dispatch", "icon": "📨", "description": "任务派发"},
    {"step": 3, "name": "Phoenix Init", "icon": "🔥", "description": "凤凰协议初始化"},
    {"step": 4, "name": "Hypothesis Gen", "icon": "🧪", "description": "假设生成"},
    {"step": 5, "name": "Physical Check", "icon": "🔒", "description": "物理锚定校验"},
    {"step": 6, "name": "Red Attack", "icon": "⚔️", "description": "红方攻击"},
    {"step": 7, "name": "Blue Defense", "icon": "🛡️", "description": "蓝方答辩"},
    {"step": 8, "name": "Score Trend", "icon": "📊", "description": "分数趋势检测"},
    {"step": 9, "name": "Phoenix Rewrite", "icon": "🔥", "description": "物理重写"},
    {"step": 10, "name": "Methodology Patch", "icon": "🧬", "description": "方法论补丁"},
    {"step": 11, "name": "External Compensation", "icon": "📡", "description": "外部补偿"},
    {"step": 12, "name": "Phoenix Retry", "icon": "🔄", "description": "补丁重试"},
    {"step": 13, "name": "Evolution Complete", "icon": "✅", "description": "演化完成"},
]

# ==================== V7.5 极客风格 CSS ====================
st.markdown("""
<style>
    /* V7.5 主标题 - 凤凰主题 */
    .v75-header {
        background: linear-gradient(135deg, #1a0a0a 0%, #4a0404 50%, #1a0a0a 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        border: 1px solid #f59e0b;
        margin-bottom: 1.5rem;
        box-shadow: 0 0 20px rgba(245, 158, 11, 0.3);
    }
    .v75-header h1 {
        color: #fbbf24;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: 0.05em;
        text-shadow: 0 0 10px rgba(245, 158, 11, 0.5);
    }
    .v75-header .subtitle {
        color: #fcd34d;
        font-size: 0.9rem;
        margin-top: 0.5rem;
    }

    /* 终端风格进度框 */
    .terminal-box {
        background: #0f172a;
        border: 1px solid #f59e0b;
        border-radius: 8px;
        padding: 1rem;
        font-family: 'Courier New', monospace;
        color: #fbbf24;
        overflow-x: auto;
        max-height: 400px;
    }
    .terminal-header {
        color: #f59e0b;
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

    /* 健康状态指示灯 */
    .health-indicator {
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .health-indicator.healthy {
        background: #064e3b;
        color: #10b981;
        border: 1px solid #10b981;
    }
    .health-indicator.unhealthy {
        background: #7f1d1d;
        color: #ef4444;
        border: 1px solid #ef4444;
    }
    .health-indicator.unknown {
        background: #334155;
        color: #94a3b8;
        border: 1px solid #64748b;
    }

    /* V7.5 金色勋章 */
    .top-candidate-badge {
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 50%, #d97706 100%);
        color: #1a0a0a;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        border: 2px solid #fcd34d;
        box-shadow: 0 0 20px rgba(245, 158, 11, 0.5);
        margin-bottom: 1rem;
    }
    .top-candidate-badge h3 {
        margin: 0;
        font-size: 1.2rem;
        font-weight: 700;
    }
    .top-candidate-badge .score {
        font-size: 2rem;
        font-weight: 800;
    }

    /* V7.5 版本卡片 */
    .version-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #334155;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    .version-card:hover {
        border-color: #f59e0b;
        box-shadow: 0 0 15px rgba(245, 158, 11, 0.3);
    }
    .version-card.initial {
        border-left: 4px solid #3b82f6;
    }
    .version-card.physical-fix {
        border-left: 4px solid #f59e0b;
    }
    .version-card.methodology-patch {
        border-left: 4px solid #10b981;
    }
    .version-card.external-compensation {
        border-left: 4px solid #8b5cf6;
    }

    /* V7.5 Promise Dashboard */
    .promise-dashboard {
        background: #1e293b;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #334155;
    }
    .promise-bar {
        height: 24px;
        border-radius: 4px;
        background: #334155;
        overflow: hidden;
        margin: 0.5rem 0;
    }
    .promise-bar-fill {
        height: 100%;
        transition: width 0.5s ease;
    }
    .promise-bar-fill.innovation {
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
    }
    .promise-bar-fill.resistance {
        background: linear-gradient(90deg, #10b981, #34d399);
    }
    .promise-bar-fill.evidence {
        background: linear-gradient(90deg, #f59e0b, #fbbf24);
    }

    /* V7.5 对抗溯源看板 */
    .conflict-trace {
        background: #1e293b;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #ef4444;
    }
    .conflict-trace.red-attack {
        border-left-color: #ef4444;
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.1), transparent);
    }
    .conflict-trace.blue-defense {
        border-left-color: #3b82f6;
        background: linear-gradient(90deg, rgba(59, 130, 246, 0.1), transparent);
    }

    /* 侧边栏配置 */
    .sidebar-config-header {
        color: #fbbf24;
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
        background: linear-gradient(90deg, #f59e0b, #ef4444);
        height: 100%;
        transition: width 0.3s ease;
    }
</style>
""", unsafe_allow_html=True)

# ==================== Session State 初始化 ====================
def init_session_state():
    """初始化 V7.5 Session State"""
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

        # V7.5 Phoenix 配置
        'max_phoenix_iterations': 8,
        'enable_phoenix_rewrite': True,
        'enable_methodology_patch': True,

        # 用户输入
        'user_input': '',
        'user_domain': 'auto-detect',

        # Pipeline 状态追踪
        'pipeline_steps_status': {},
        'pipeline_logs': [],

        # V7.5 演化追踪
        'selected_version': None,
        'show_top_candidate': False,

        # 错误状态
        'error_occurred': False,
        'error_type': None,
        'error_message': None,

        # 提交守卫状态
        'submission_lock': False,
        'last_submit_time': None,
        'submit_cooldown_until': None,
        'pending_input_hash': None,

        # 轮询守卫状态
        'poll_start_time': None,
        'poll_attempt_count': 0,
        'last_state_change_time': None,
        'last_known_state': None,

        # 多 Tab 隔离
        'tab_session_id': None,
        'tab_fingerprint': None,
        'lock_holder_tab': None,

        # V7.5 物理公理状态
        'axiom_badge_state': 'waiting',
        'pseudoscience_detected': False,
        'attack_types_detected': [],
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ==================== 任务持久化数据库 ====================
def init_task_persistence_db():
    """任务持久化数据库初始化"""
    try:
        conn = sqlite3.connect(PERSISTENCE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_registry (
                task_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_input_hash TEXT NOT NULL,
                user_input_preview TEXT,
                config TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                last_poll_at TEXT,
                result_available INTEGER DEFAULT 0,
                result_json TEXT
            )
        """)

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


def init_local_queue_db():
    """本地队列数据库初始化"""
    try:
        conn = sqlite3.connect(LOCAL_QUEUE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS local_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_input_hash TEXT NOT NULL,
                user_input TEXT NOT NULL,
                config TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                error_message TEXT
            )
        """)

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"Local queue DB init failed: {e}")
        return False


def register_task_persistence(task_id: str, user_input: str, config: Dict):
    """任务注册"""
    try:
        conn = sqlite3.connect(PERSISTENCE_DB)
        cursor = conn.cursor()

        input_hash = hashlib.sha256(user_input.encode()).hexdigest()[:16]
        # 确保 session_id 不为空
        session_id = st.session_state.get('tab_session_id') or f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        input_preview = user_input[:100] if len(user_input) > 100 else user_input
        config_json = json.dumps(config, ensure_ascii=False)

        cursor.execute("""
            INSERT OR REPLACE INTO task_registry
            (task_id, session_id, user_input_hash, user_input_preview, config, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (task_id, session_id, input_hash, input_preview, config_json, 'pending', datetime.now().isoformat()))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"Task persistence register failed: {e}")
        return False


def recover_lost_task_on_reload() -> Optional[str]:
    """刷新后任务召回"""
    try:
        current_tab_id = st.session_state.get('tab_session_id', '')
        if not current_tab_id:
            return None

        conn = sqlite3.connect(PERSISTENCE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT task_id, status, created_at, result_json, user_input_preview, session_id, config
            FROM task_registry
            WHERE status NOT IN ('SUCCESS', 'FAILURE', 'TIMEOUT', 'completed', 'ZOMBIE', 'REVOKED')
            AND created_at > datetime('now', '-24 hours')
            ORDER BY created_at DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        conn.close()

        if row:
            task_id, status, created_at, result_json, input_preview, owner_session_id, config_json = row

            if owner_session_id and owner_session_id != current_tab_id:
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
                        return None
                except Exception:
                    pass

            if CELERY_AVAILABLE:
                actual_result = poll_task_status_safe(task_id)
                actual_state = actual_result['state']

                if actual_state in ['SUCCESS', 'FAILURE']:
                    update_task_completion(task_id, actual_state, result_json)
                    return None

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
                    logger.warning(f"更新任务占用者失败: {e}")

                st.session_state.task_id = task_id
                st.session_state.task_state = actual_state
                st.session_state.task_start_time = created_at
                st.session_state.user_input = input_preview or ''

                if config_json:
                    try:
                        config = json.loads(config_json)
                        st.session_state.min_score_threshold = config.get('min_score_threshold', 7.0)
                        st.session_state.max_phoenix_iterations = config.get('max_phoenix_iterations', 8)
                    except Exception:
                        pass

                logger.info(f"成功召回任务: {task_id[:16]}...")
                return task_id

        return None
    except Exception as e:
        logger.warning(f"Task recovery failed: {e}")
        return None


def update_task_completion(task_id: str, state: str, result_json: str = None):
    """更新任务完成状态"""
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
    """获取任务历史列表 - 从两个数据库合并"""
    history = []

    # 1. 从 research.db 读取旧版本任务（research_sessions）
    try:
        research_db = DATA_DIR / 'research.db'
        if research_db.exists():
            conn = sqlite3.connect(research_db)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, query, created_at, status, hypotheses_generated
                FROM research_sessions
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                history.append({
                    'task_id': f"old_{row[0]}",
                    'status': row[3],
                    'created_at': row[2],
                    'input_preview': row[1] or '',
                    'result_json': None,
                    'source': 'research.db'
                })
    except Exception as e:
        logger.warning(f"Research history fetch failed: {e}")

    # 2. 从 task_persistence.db 读取新版本任务（task_registry）
    try:
        conn = sqlite3.connect(PERSISTENCE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT task_id, status, created_at, user_input_preview, result_json
            FROM task_registry
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            history.append({
                'task_id': row[0],
                'status': row[1],
                'created_at': row[2],
                'input_preview': row[3] or '',
                'result_json': row[4],
                'source': 'task_persistence.db'
            })
    except Exception as e:
        logger.warning(f"Task history fetch failed: {e}")

    # 3. 合并并排序（按时间）
    history.sort(key=lambda x: x['created_at'] or '', reverse=True)
    return history[:limit]


def delete_task_from_history(task_id: str) -> bool:
    """从历史记录中删除任务（支持两个数据库）"""
    deleted = False

    # 1. 从 task_persistence.db 删除新任务
    try:
        conn = sqlite3.connect(PERSISTENCE_DB)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM task_registry WHERE task_id = ?", (task_id,))
        conn.commit()
        if cursor.rowcount > 0:
            deleted = True
            logger.info(f"任务已删除 (task_registry): {task_id[:12]}...")
        conn.close()
    except Exception as e:
        logger.warning(f"Task deletion from task_registry failed: {e}")

    # 2. 从 research.db 删除旧任务
    if task_id.startswith('old_'):
        try:
            research_db = DATA_DIR / 'research.db'
            if research_db.exists():
                session_id = task_id.replace('old_', '')
                conn = sqlite3.connect(research_db)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM research_sessions WHERE id = ?", (session_id,))
                conn.commit()
                if cursor.rowcount > 0:
                    deleted = True
                    logger.info(f"任务已删除 (research_sessions): {session_id}")
                conn.close()
        except Exception as e:
            logger.warning(f"Task deletion from research_sessions failed: {e}")

    return deleted


def clear_all_task_history() -> int:
    """清空所有任务历史（两个数据库）"""
    total_count = 0

    # 1. 清空 task_persistence.db
    try:
        conn = sqlite3.connect(PERSISTENCE_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM task_registry")
        count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM task_registry")
        conn.commit()
        conn.close()
        total_count += count
    except Exception as e:
        logger.warning(f"Clear task_registry failed: {e}")

    # 2. 清空 research.db 的 research_sessions
    try:
        research_db = DATA_DIR / 'research.db'
        if research_db.exists():
            conn = sqlite3.connect(research_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM research_sessions")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM research_sessions")
            conn.commit()
            conn.close()
            total_count += count
    except Exception as e:
        logger.warning(f"Clear research_sessions failed: {e}")

    logger.info(f"已清空所有任务历史，共 {total_count} 条记录")
    return total_count

# ==================== Redis 健康检查 ====================
def check_redis_health() -> Tuple[bool, str]:
    """Redis 连接健康检查"""
    if not CELERY_AVAILABLE:
        return False, "Celery 模块未加载"

    try:
        celery_app = get_celery_app()

        with celery_app.connection_or_acquire() as conn:
            if not conn.connected:
                conn.ensure_connection(max_retries=2, interval_start=0.5)

            conn.default_channel.close()

        return True, ""

    except redis.ConnectionError as e:
        return False, f"Redis 连接失败: {str(e)}"
    except Exception as e:
        return False, f"健康检查异常: {str(e)}"

# ==================== Celery 任务安全投递 ====================
def submit_celery_task_with_safety(user_input: str, config: Dict) -> Tuple[Optional[str], Dict]:
    """V7.5 安全投递机制"""
    dispatch_result = {
        'attempt': 0,
        'success': False,
        'error_type': None,
        'error_message': None,
        'fallback_used': False,
        'health_check_passed': False,
    }

    # Phase 1: 投递前健康检查
    if CELERY_AVAILABLE:
        health_ok, health_msg = check_redis_health()
        dispatch_result['health_check_passed'] = health_ok

        if not health_ok:
            dispatch_result['error_type'] = 'REDIS_CONNECTION_FAILED'
            dispatch_result['error_message'] = health_msg
            return None, dispatch_result

        # Worker 检测（支持手动确认）
        worker_alive = check_worker_heartbeat()
        manual_confirm = st.session_state.get('worker_confirmed', False)

        if not worker_alive and not manual_confirm:
            dispatch_result['error_type'] = 'WORKER_OFFLINE'
            dispatch_result['error_message'] = 'Worker 未运行。请在侧边栏勾选"我确认 Worker 已运行"或启动 Worker。'
            return None, dispatch_result
    else:
        dispatch_result['error_type'] = 'CELERY_NOT_AVAILABLE'
        dispatch_result['error_message'] = 'Celery 模块未加载'
        return None, dispatch_result

    # Phase 2: 投递中异常捕获 + 重试
    celery_app = get_celery_app()

    # V7.5: 参数穿透
    task_kwargs = {
        'user_input': user_input,
        'user_domain': config.get('user_domain', 'auto-detect'),
        'hard_cap': config.get('hard_cap', 15),
        'min_score_threshold': config.get('min_score_threshold', 7.0),
        'max_iterations': config.get('max_iterations', 5),
        'execution_mode': config.get('execution_mode', 'autonomous'),
        'webhook_url': None,
        'session_id': st.session_state.get('tab_session_id', f"v7_session_{datetime.now().strftime('%Y%m%d%H%M%S')}"),

        # V7.5 Phoenix 参数
        'max_phoenix_iterations': config.get('max_phoenix_iterations', 8),
        'enable_phoenix_rewrite': config.get('enable_phoenix_rewrite', True),
        'enable_methodology_patch': config.get('enable_methodology_patch', True),

        # 文献检索筛选参数
        'min_if': config.get('min_if', 3.0),
        'start_year': config.get('start_year', 2020),
        'end_year': config.get('end_year', datetime.now().year),
        'min_citations': config.get('min_citations', 10),
    }

    logger.debug(f"V7.5 Task kwargs prepared:")
    for k, v in task_kwargs.items():
        logger.debug(f"  {k}: {v}")

    for attempt in range(1, 4):
        dispatch_result['attempt'] = attempt

        try:
            result = celery_app.send_task(
                'hypothesis_generation_task_v75',
                kwargs=task_kwargs,
                queue='research',
                priority=5,
                retry=True,
            )

            task_id = result.id
            dispatch_result['success'] = True
            dispatch_result['task_id'] = task_id

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

    # Phase 3: 投递失败降级
    if not dispatch_result['success']:
        st.error(f"""
        ❌ 任务投递失败 (尝试 {dispatch_result['attempt']} 次)

        **错误类型**: {dispatch_result['error_type']}
        **错误详情**: {dispatch_result['error_message']}
        """)
        return None, dispatch_result

    return dispatch_result.get('task_id'), dispatch_result

# ==================== 提交守卫系统 ====================
def init_submission_guard():
    """提交守卫初始化"""
    if 'submission_lock' not in st.session_state:
        st.session_state.submission_lock = False
    if 'last_submit_time' not in st.session_state:
        st.session_state.last_submit_time = None
    if 'submit_cooldown_until' not in st.session_state:
        st.session_state.submit_cooldown_until = None
    if 'pending_input_hash' not in st.session_state:
        st.session_state.pending_input_hash = None

    # Tab 隔离机制
    if 'tab_session_id' not in st.session_state:
        st.session_state.tab_session_id = f"tab_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(os.urandom(8)) & 0xFFFFFF:06x}"

    if 'tab_fingerprint' not in st.session_state or st.session_state.tab_fingerprint is None:
        st.session_state.tab_fingerprint = {
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'activity_count': 0,
        }

    st.session_state.tab_fingerprint['last_activity'] = datetime.now().isoformat()
    st.session_state.tab_fingerprint['activity_count'] = st.session_state.tab_fingerprint.get('activity_count', 0) + 1


def check_submission_guard(user_input: str) -> Tuple[bool, str]:
    """提交守卫检查"""
    now = datetime.now()

    # 检查 1: 提交锁
    if st.session_state.submission_lock:
        lock_holder = st.session_state.get('lock_holder_tab', '')
        current_tab = st.session_state.get('tab_session_id', '')

        if lock_holder and lock_holder != current_tab:
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
    """获取提交锁"""
    st.session_state.submission_lock = True
    st.session_state.last_submit_time = datetime.now().isoformat()
    st.session_state.lock_holder_tab = st.session_state.get('tab_session_id', '')

    if user_input.strip():
        st.session_state.pending_input_hash = hashlib.sha256(user_input.encode()).hexdigest()[:16]
    st.session_state.submit_cooldown_until = (datetime.now() + timedelta(seconds=SUBMIT_COOLDOWN_SECONDS)).isoformat()


def release_submission_lock():
    """释放提交锁"""
    st.session_state.submission_lock = False
    st.session_state.lock_holder_tab = None

# ==================== 轮询守卫系统 ====================
def init_poll_guard():
    """轮询守卫初始化"""
    if 'poll_start_time' not in st.session_state:
        st.session_state.poll_start_time = None
    if 'poll_attempt_count' not in st.session_state:
        st.session_state.poll_attempt_count = 0
    if 'last_state_change_time' not in st.session_state:
        st.session_state.last_state_change_time = None
    if 'last_known_state' not in st.session_state:
        st.session_state.last_known_state = None


def check_poll_guard(task_id: str) -> Tuple[bool, str, Dict]:
    """轮询守卫检查"""
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
            return False, "STATE_STAGNANT", {
                'stagnant_minutes': stagnant_minutes,
                'last_state': last_state,
                'reason': '任务状态 30 分钟无变化'
            }

    return True, "CONTINUE", {}


def check_worker_heartbeat() -> bool:
    """Worker 心跳检测（支持多种检测方式）"""
    if not CELERY_AVAILABLE:
        print("[DEBUG] CELERY_NOT_AVAILABLE")
        return False

    # 方法0: 直接检查 Redis 中的 Celery key（最可靠，优先使用）
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        print(f"[DEBUG] 检查 Redis: {redis_url}")
        r = redis.from_url(redis_url, decode_responses=True)
        # 检查是否有 Celery heartbeat 或 worker 相关的 key
        celery_keys = r.keys('celery*')
        kombu_keys = r.keys('_kombu.binding.celery*')
        print(f"[DEBUG] celery_keys: {celery_keys}, kombu_keys: {kombu_keys}")
        if celery_keys or kombu_keys:
            logger.info(f"[Health Check] Redis 中发现 Celery 迹象: {len(celery_keys)} celery keys, {len(kombu_keys)} kombu keys")
            print(f"[Health Check] ✅ 通过 Redis key 检测到 Worker!")
            return True
    except Exception as redis_err:
        print(f"[DEBUG] Redis 检测失败: {redis_err}")

    # 如果 Redis 检测没有找到，尝试使用 inspect（可能失败）
    try:
        print("[DEBUG] 尝试使用 inspect 检测...")
        celery_app = get_celery_app()

        # 方法1: 检测活跃任务
        inspect = celery_app.control.inspect(timeout=1.0)
        active_workers = inspect.active()
        print(f"[DEBUG] active_workers: {active_workers}")

        if active_workers and len(active_workers) > 0:
            logger.info(f"[Health Check] 检测到 {len(active_workers)} 个活跃 Worker (active)")
            return True

        # 方法2: 检测已注册的 Worker（备用）
        registered_workers = inspect.registered()
        print(f"[DEBUG] registered_workers: {registered_workers}")
        if registered_workers and len(registered_workers) > 0:
            logger.info(f"[Health Check] 检测到 {len(registered_workers)} 个 Worker (registered)")
            return True

        # 方法3: 检测 Worker 统计信息（备用）
        stats = inspect.stats()
        print(f"[DEBUG] stats: {stats}")
        if stats and len(stats) > 0:
            logger.info(f"[Health Check] 检测到 {len(stats)} 个 Worker (stats)")
            return True
    except Exception as inspect_err:
        print(f"[DEBUG] Inspect 检测失败（已跳过）: {inspect_err}")

    logger.warning("[Health Check] 所有检测方法均未发现 Worker")
    print("[DEBUG] 所有检测方法均未发现 Worker")
    return False


def poll_task_status_safe(task_id: str) -> Dict:
    """安全轮询"""
    init_poll_guard()

    st.session_state.poll_attempt_count += 1

    can_continue, reason, details = check_poll_guard(task_id)

    if not can_continue:
        return handle_poll_timeout(task_id, reason, details)

    poll_result = poll_task_status(task_id)

    current_state = poll_result['state']
    last_state = st.session_state.last_known_state

    if current_state != last_state:
        st.session_state.last_known_state = current_state
        st.session_state.last_state_change_time = datetime.now().isoformat()

    if current_state in ['SUCCESS', 'success', 'FAILURE', 'failure']:
        st.session_state.poll_start_time = None
        st.session_state.poll_attempt_count = 0
        # 序列化结果并保存
        result_json = json.dumps(poll_result.get('result'), ensure_ascii=False) if poll_result.get('result') else None
        # 标准化状态为大写
        normalized_state = current_state.upper()
        update_task_completion(task_id, normalized_state, result_json)

    return poll_result


def handle_poll_timeout(task_id: str, reason: str, details: Dict) -> Dict:
    """超时处理"""
    st.session_state.task_state = 'TIMEOUT'
    st.session_state.error_occurred = True
    st.session_state.error_type = reason
    st.session_state.error_message = details.get('reason', '轮询超时')

    if CELERY_AVAILABLE and task_id:
        try:
            celery_app = get_celery_app()
            async_result = AsyncResult(task_id, app=celery_app)
            current_state = async_result.state

            if current_state in ['PENDING', 'PROGRESS', 'STARTED']:
                celery_app.control.revoke(task_id, terminate=True)
                logger.warning(f"僵尸任务已撤销: {task_id[:16]}... (原因: {reason})")
                update_task_completion(task_id, 'ZOMBIE')

        except Exception as e:
            logger.warning(f"撤销僵尸任务失败: {e}")

    return {
        'state': 'TIMEOUT',
        'progress': 0,
        'message': details.get('reason', '轮询超时'),
        'timeout_reason': reason,
        'details': details,
        'task_revoked': True,
    }


def poll_task_status(task_id: str) -> Dict:
    """轮询任务状态"""
    if not CELERY_AVAILABLE or not task_id:
        return {'state': 'UNKNOWN', 'progress': 0, 'message': 'Celery不可用'}

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

        st.session_state.task_state = state
        st.session_state.task_progress = progress
        st.session_state.task_message = message

        if message and len(st.session_state.pipeline_logs) < 50:
            st.session_state.pipeline_logs.append({
                'time': datetime.now().strftime('%H:%M:%S'),
                'step': max(1, min(13, progress // 8 + 1)),
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

# ==================== V7.5 演化实验室渲染引擎 ====================

def render_top_candidate_badge(result: Dict):
    """渲染最佳准方案金色勋章"""
    payload = result.get('payload', {})
    phoenix_protocol = payload.get('phoenix_protocol', {})
    version_chain = phoenix_protocol.get('version_chain', [])

    if not version_chain:
        return

    # 找出 Science Score 最高的版本
    top_version = max(version_chain, key=lambda v: v.get('science_score', 0), default=None)

    if not top_version:
        return

    top_score = top_version.get('science_score', 0)

    # 计算 Promise Score
    promise_score = calculate_promise_score(top_version, phoenix_protocol)

    st.markdown(f"""
    <div class="top-candidate-badge">
        <h3>🏆 最佳候选方案 (Top Candidate)</h3>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1rem;">
            <div>
                <div style="font-size: 0.9rem; opacity: 0.8;">版本</div>
                <div style="font-size: 1.2rem; font-weight: 700;">{top_version.get('version', 'v?.?')}</div>
            </div>
            <div>
                <div style="font-size: 0.9rem; opacity: 0.8;">Science Score</div>
                <div class="score">{top_score:.2f}</div>
            </div>
            <div>
                <div style="font-size: 0.9rem; opacity: 0.8;">Promise Score</div>
                <div class="score">{promise_score['total']:.2f}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Promise Dashboard
    render_promise_dashboard(promise_score)


def calculate_promise_score(version: Dict, phoenix_protocol: Dict) -> Dict:
    """计算 Promise Score"""
    science_score = version.get('science_score', 0)
    defense_passed = version.get('defense_passed', False)
    iteration = version.get('iteration', 1)

    # 创新性：基于分数和迭代次数
    innovation = min(10, science_score * 1.2 + (10 - iteration) * 0.1)

    # 抗性：基于红方攻击通过情况和补丁次数
    red_attack_types = version.get('red_attack_types', [])
    resistance = max(3, 10 - len(red_attack_types) * 1.5 + (5 if defense_passed else 0))

    # 实证度：基于版本演化和分数稳定性
    score_history = phoenix_protocol.get('score_evolution', [])
    if len(score_history) >= 2:
        score_trend = score_history[-1] - score_history[0]
        evidence = min(10, 5 + score_trend * 2 + (3 if defense_passed else 0))
    else:
        evidence = min(10, science_score * 0.8)

    # Promise Score = 创新性(35%) + 抗性(35%) + 实证度(30%)
    total = innovation * 0.35 + resistance * 0.35 + evidence * 0.30

    return {
        'total': total,
        'innovation': innovation,
        'resistance': resistance,
        'evidence': evidence,
        'components': {
            '创新性': {'score': innovation, 'weight': 0.35, 'description': '基于 Science Score 和迭代位置'},
            '抗性': {'score': resistance, 'weight': 0.35, 'description': '基于红方攻击防御能力'},
            '实证度': {'score': evidence, 'weight': 0.30, 'description': '基于分数趋势和验证状态'},
        }
    }


def render_promise_dashboard(promise_score: Dict):
    """渲染 Promise Score 仪表盘"""
    st.markdown("### 📊 Promise Dashboard")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div class="promise-dashboard">
            <div style="color: #8b5cf6; font-weight: bold;">创新性</div>
            <div style="font-size: 2rem; font-weight: 700;">{promise_score['innovation']:.1f}</div>
            <div class="promise-bar">
                <div class="promise-bar-fill innovation" style="width: {promise_score['innovation'] * 10}%"></div>
            </div>
            <div style="font-size: 0.8rem; color: #94a3b8;">权重 35%</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="promise-dashboard">
            <div style="color: #10b981; font-weight: bold;">抗性</div>
            <div style="font-size: 2rem; font-weight: 700;">{promise_score['resistance']:.1f}</div>
            <div class="promise-bar">
                <div class="promise-bar-fill resistance" style="width: {promise_score['resistance'] * 10}%"></div>
            </div>
            <div style="font-size: 0.8rem; color: #94a3b8;">权重 35%</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="promise-dashboard">
            <div style="color: #f59e0b; font-weight: bold;">实证度</div>
            <div style="font-size: 2rem; font-weight: 700;">{promise_score['evidence']:.1f}</div>
            <div class="promise-bar">
                <div class="promise-bar-fill evidence" style="width: {promise_score['evidence'] * 10}%"></div>
            </div>
            <div style="font-size: 0.8rem; color: #94a3b8;">权重 30%</div>
        </div>
        """, unsafe_allow_html=True)


def render_evolution_slider(version_chain: List[Dict]):
    """渲染版本滑块"""
    if not version_chain or len(version_chain) <= 1:
        return

    st.markdown("### 🔍 版本演化浏览器")

    # 提取版本号列表
    versions = [v.get('version', f'v{i+1}.0') for i, v in enumerate(version_chain)]

    # 创建版本选择滑块
    selected_idx = st.select_slider(
        "选择版本查看详情",
        options=range(len(versions)),
        format_func=lambda i: versions[i],
        value=len(versions) - 1,
        key='version_slider'
    )

    st.session_state.selected_version = version_chain[selected_idx]

    # 渲染选中版本的详情
    render_version_detail(version_chain[selected_idx])


def render_version_detail(version: Dict):
    """渲染版本详情卡片"""
    v_type = version.get('type', 'unknown')
    v_type_display = {
        'initial': '初始版本',
        'physical_fix': '物理锚定重写',
        'methodology_patch': '方法论补丁',
        'external_compensation': '外部算法补偿',
    }.get(v_type, v_type)

    card_class = {
        'initial': 'initial',
        'physical-fix': 'physical-fix',
        'methodology-patch': 'methodology-patch',
        'external-compensation': 'external-compensation',
    }.get(v_type.replace('_', '-'), 'initial')

    st.markdown(f"""
    <div class="version-card {card_class}">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h3 style="margin: 0;">{version.get('version', 'v?.?')}</h3>
                <div style="color: #94a3b8; font-size: 0.9rem;">{v_type_display}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 1.5rem; font-weight: 700; color: #fbbf24;">
                    {version.get('science_score', 0):.2f}
                </div>
                <div style="font-size: 0.8rem; color: #94a3b8;">Science Score</div>
            </div>
        </div>
        <div style="margin-top: 1rem; font-size: 0.9rem; color: #94a3b8;">
            迭代轮次: {version.get('iteration', 0)} | 创建时间: {version.get('created_at', 'N/A')[:19]}
        </div>
        <div style="margin-top: 0.5rem;">
            状态: {'✅ 通过' if version.get('defense_passed') else '🔄 未通过'}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_conflict_trace(result: Dict):
    """渲染对抗溯源看板"""
    payload = result.get('payload', {})
    phoenix_protocol = payload.get('phoenix_protocol', {})
    version_chain = phoenix_protocol.get('version_chain', [])

    if not version_chain:
        return

    st.markdown("### ⚔️ 对抗溯源看板")

    for version in version_chain:
        v_type = version.get('type', 'unknown')
        v_num = version.get('version', 'v?.?')

        # 红方攻击点
        red_attack_types = version.get('red_attack_types', [])
        if red_attack_types and red_attack_types != ['UNKNOWN']:
            st.markdown(f"""
            <div class="conflict-trace red-attack">
                <div style="font-weight: bold; color: #ef4444;">⚔️ 红方攻击 - {v_num}</div>
                <div style="margin-top: 0.5rem;">
            """, unsafe_allow_html=True)

            for attack_type in red_attack_types:
                attack_desc = {
                    'OVERFITTING': '过拟合 - 模型在训练集上表现过好，泛化能力差',
                    'LEAKAGE': '数据泄露 - 测试集信息意外进入训练过程',
                    'BIAS': '选择偏差 - 样本选择不当导致系统性偏差',
                    'VALIDATION': '验证不足 - 缺乏独立验证集或验证方法不当',
                    'PSEUDOSCIENCE': '伪科学 - 缺乏物理锚定或可测量手段',
                }.get(attack_type, attack_type)

                st.info(f"**{attack_type}**: {attack_desc}")

            st.markdown("</div></div>", unsafe_allow_html=True)

        # 蓝方补丁响应
        patch_applied = version.get('patch_applied', False)
        if patch_applied:
            st.markdown(f"""
            <div class="conflict-trace blue-defense">
                <div style="font-weight: bold; color: #3b82f6;">🛡️ 蓝方补丁响应 - {v_num}</div>
                <div style="margin-top: 0.5rem; color: #10b981;">
                    ✓ 方法论补丁已注入
                </div>
            </div>
            """, unsafe_allow_html=True)


def render_phoenix_status_panel(phoenix_protocol: Dict):
    """渲染凤凰协议状态面板"""
    st.markdown("### 🔥 凤凰协议执行统计")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("总迭代", phoenix_protocol.get('total_iterations', 0))
    with col2:
        st.metric("物理重写", phoenix_protocol.get('rewrite_attempts', 0))
    with col3:
        st.metric("方法论补丁", phoenix_protocol.get('patch_attempts', 0))
    with col4:
        final_state = phoenix_protocol.get('final_state', 'UNKNOWN')
        state_icon = '✅' if final_state == 'SUCCESS' else '⏰'
        st.metric("最终状态", f"{state_icon} {final_state}")


def render_score_trend_chart(score_history: List[float]):
    """渲染分数趋势图"""
    if not score_history or len(score_history) < 2:
        return

    st.markdown("### 📈 Science Score 趋势")

    # 创建趋势数据
    trend_data = {
        '版本': [f'v{i//3+1}.{i%3+1}' for i in range(len(score_history))],
        '分数': score_history
    }

    st.line_chart(trend_data.set_index('版本')['分数'] if hasattr(st, 'dataframe') else score_history)

    # 趋势分析
    if len(score_history) >= 2:
        first_score = score_history[0]
        last_score = score_history[-1]
        delta = last_score - first_score

        if delta > 0.5:
            st.success(f"📈 趋势上升 (+{delta:.2f})")
        elif delta < -0.5:
            st.error(f"📉 趋势下降 ({delta:.2f})")
        else:
            st.warning(f"➡️ 趋势平稳 ({delta:+.2f})")


def render_phoenix_evolution_graph(version_chain: List[Dict]):
    """渲染版本演进图"""
    if not version_chain:
        return

    st.markdown("### 🧬 版本演进链")

    # 计算布局
    n_versions = len(version_chain)
    cols = st.columns(min(n_versions, 5))

    for i, version in enumerate(version_chain):
        col_idx = i % min(n_versions, 5)
        with cols[col_idx]:
            v_type = version.get('type', 'unknown')
            v_score = version.get('science_score', 0)
            v_passed = version.get('defense_passed', False)

            type_colors = {
                'initial': '#3b82f6',
                'physical_fix': '#f59e0b',
                'methodology_patch': '#10b981',
                'external_compensation': '#8b5cf6',
            }

            color = type_colors.get(v_type, '#64748b')
            status_icon = '✅' if v_passed else '🔄'

            st.markdown(f"""
            <div style="text-align: center; padding: 0.5rem; border: 2px solid {color}; border-radius: 8px; background: rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1);">
                <div style="font-weight: bold;">{version.get('version', 'v?.?')}</div>
                <div style="font-size: 1.2rem;">{v_score:.1f}</div>
                <div>{status_icon}</div>
            </div>
            """, unsafe_allow_html=True)

            if i < n_versions - 1:
                st.markdown(f"<div style='text-align: center; color: {color};'>↓</div>", unsafe_allow_html=True)


# ==================== 健康状态指示灯渲染 ====================
def render_health_indicator():
    """健康状态指示灯"""
    if CELERY_AVAILABLE:
        health_ok, _ = check_redis_health()
        worker_alive = check_worker_heartbeat()

        # 添加刷新按钮
        col1, col2 = st.columns([3, 1])
        with col1:
            if health_ok and worker_alive:
                st.markdown(
                    '<span class="health-indicator healthy">✅ Redis + Worker 就绪</span>',
                    unsafe_allow_html=True
                )
            elif health_ok:
                st.markdown(
                    '<span class="health-indicator warning">⚠️ Redis 就绪，Worker 离线</span>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    '<span class="health-indicator unhealthy">❌ Redis 不可用</span>',
                    unsafe_allow_html=True
                )
        with col2:
            if st.button("🔄", key="refresh_health", help="刷新健康状态"):
                st.rerun()

        # 显示诊断信息（展开式）
        with st.expander("🔍 诊断信息", expanded=True):
            st.code(f"""
Redis 连接: {'✅ 正常' if health_ok else '❌ 失败'}
Worker 状态: {'✅ 活跃' if worker_alive else '❌ 离线'}
Redis URL: {os.getenv('REDIS_URL', 'redis://localhost:6379/0')}
            """)

            # 添加详细的Redis检测信息
            try:
                import redis
                r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
                all_keys = r.keys('*')
                celery_keys = [k for k in all_keys if 'celery' in k.lower()]
                st.text(f"Redis 总keys: {len(all_keys)}")
                st.text(f"Celery相关keys: {len(celery_keys)}")
                if celery_keys:
                    st.text("Celery keys:")
                    for k in celery_keys:
                        st.text(f"  - {k}")
            except Exception as e:
                st.text(f"Redis检测错误: {e}")

            if not worker_alive:
                st.info("""
💡 **Worker 离线可能原因：**
1. Worker 窗口��启动或已关闭
2. Worker 启动命令错误
3. Redis 连接问题

🔧 **解决方案：**
```bash
celery -A src.core.celery_tasks_v75 worker --loglevel=info --pool=solo
```
                """)
    else:
        st.markdown(
            '<span class="health-indicator unknown">⏳ Celery 未加载</span>',
            unsafe_allow_html=True
        )

# ==================== 侧边栏配置 ====================
def render_sidebar_configurator():
    """V7.5 侧边栏配置"""
    st.sidebar.markdown("""
    <div class="sidebar-config-header">
        ⚙️ V7.5 Phoenix Evolution
    </div>
    """, unsafe_allow_html=True)

    # 健康状态指示灯
    st.sidebar.markdown("### 🩺 系统健康状态")
    render_health_indicator()

    st.sidebar.markdown("---")

    # Worker 手动确认（始终显示，因为 Windows 检测不可靠）
    st.sidebar.markdown("### ⚙️ Worker 确认")
    worker_confirmed = st.sidebar.checkbox(
        "✅ 我确认 Worker 正在运行",
        value=st.session_state.get('worker_confirmed', False),
        key="worker_confirmed_checkbox",
        help="如果自动检测失败，请手动勾选此项"
    )
    st.session_state.worker_confirmed = worker_confirmed

    if worker_confirmed:
        st.sidebar.success("可以提交任务")
    else:
        st.sidebar.warning("请先启动 Worker 或勾选确认")

    st.sidebar.markdown("---")

    # V7.5 Phoenix 配置
    st.sidebar.markdown("### 🔥 凤凰协议配置")

    max_phoenix = st.sidebar.slider(
        "最大演化迭代",
        min_value=4, max_value=12,
        value=st.session_state.get('max_phoenix_iterations', 8),
        key='max_phoenix_slider'
    )
    st.session_state.max_phoenix_iterations = max_phoenix

    enable_rewrite = st.sidebar.checkbox(
        "物理锚定重写",
        value=st.session_state.get('enable_phoenix_rewrite', True),
        key='enable_rewrite_check'
    )
    st.session_state.enable_phoenix_rewrite = enable_rewrite

    enable_patch = st.sidebar.checkbox(
        "方法论补丁注入",
        value=st.session_state.get('enable_methodology_patch', True),
        key='enable_patch_check'
    )
    st.session_state.enable_methodology_patch = enable_patch

    st.sidebar.markdown("---")

    # 执行模式
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

    st.sidebar.markdown("---")

    # 文献检索筛选
    st.sidebar.markdown("### 📚 文献检索筛选")

    # 影响因子筛选
    min_if = st.sidebar.slider(
        "最低影响因子 (IF)",
        min_value=0.0, max_value=30.0,
        value=st.session_state.get('min_if', 3.0),
        step=0.5,
        help="适用于PubMed等数据库。ArXiv无IF，将使用引用数替代",
        key='min_if_slider'
    )
    st.session_state.min_if = min_if

    # 时间范围筛选
    current_year = datetime.now().year
    col_year1, col_year2 = st.sidebar.columns(2)
    with col_year1:
        start_year = st.number_input(
            "起始年份",
            min_value=1990, max_value=current_year,
            value=st.session_state.get('start_year', 2020),
            step=1,
            key='start_year_input'
        )
    with col_year2:
        end_year = st.number_input(
            "结束年份",
            min_value=1990, max_value=current_year + 2,
            value=st.session_state.get('end_year', current_year),
            step=1,
            key='end_year_input'
        )

    st.session_state.start_year = start_year
    st.session_state.end_year = end_year

    # ArXiv 替代筛选（引用数）
    min_citations = st.sidebar.slider(
        "ArXiv最低引用数",
        min_value=0, max_value=500,
        value=st.session_state.get('min_citations', 10),
        step=5,
        help="ArXiv论文无影响因子，使用引用数作为质量指标",
        key='min_citations_slider'
    )
    st.session_state.min_citations = min_citations

    st.sidebar.info("💡 提示: ArXiv无IF，将自动使用引用数筛选")

    st.sidebar.markdown("---")

    # 配置摘要
    config_summary = {
        'execution_mode': execution_mode,
        'hard_cap': hard_cap,
        'min_score_threshold': min_score,
        'max_phoenix_iterations': max_phoenix,
        'enable_phoenix_rewrite': enable_rewrite,
        'enable_methodology_patch': enable_patch,
        'min_if': min_if,
        'start_year': start_year,
        'end_year': end_year,
        'min_citations': min_citations,
    }

    with st.sidebar.expander("🔍 配置预览", expanded=False):
        st.json(config_summary)

    return config_summary


def render_task_history_sidebar():
    """任���历史列表"""
    st.sidebar.markdown("---")

    # 标题和清空按钮
    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        st.markdown("### 📜 历史任务")
    with col2:
        if st.button("🗑️", key="clear_all_history", help="清空所有历史"):
            if st.session_state.get('confirm_clear_history', False):
                count = clear_all_task_history()
                st.toast(f"✅ 已清空 {count} 条历史记录")
                st.session_state.confirm_clear_history = False
                st.rerun()
            else:
                st.session_state.confirm_clear_history = True
                st.warning("再次点击确认清空")
                st.rerun()

    history = get_task_history_list(5)

    if not history:
        st.sidebar.info("暂无历史任务")
        return

    for item in history:
        task_id = item['task_id']
        status = item['status']
        created_at = item['created_at'][:16] if item['created_at'] else 'N/A'
        preview = item['input_preview'][:30] + '...' if item['input_preview'] and len(item['input_preview']) > 30 else item['input_preview']
        result_json = item.get('result_json')

        status_color = {
            'SUCCESS': '🟢',
            'FAILURE': '🔴',
            'PENDING': '🟡',
            'PROGRESS': '🔵',
            'TIMEOUT': '🟠',
            'ZOMBIE': '🟤',
        }.get(status, '⚪')

        # 使用 expander 显示任务详情
        with st.sidebar.expander(f"{status_color} {task_id[:12]}... | {status}", expanded=False):
            st.text(f"时间: {created_at}")
            st.text(f"内容: {preview}")
            st.text(f"ID: {task_id}")

            col1, col2 = st.columns(2)

            # 查看按钮（用于成功的任务）
            if status == 'SUCCESS' and result_json:
                with col1:
                    if st.button("📄 查看", key=f"view_{task_id[:8]}", use_container_width=True):
                        st.session_state.task_id = task_id
                        st.session_state.task_state = 'SUCCESS'
                        try:
                            result_data = json.loads(result_json)
                            st.session_state.task_result = result_data
                        except:
                            st.session_state.task_result = {'payload': result_json}
                        st.rerun()

            # 召回按钮（用于进行中的任务）
            if status not in ['SUCCESS', 'FAILURE', 'TIMEOUT', 'ZOMBIE']:
                with col1:
                    if st.button("🔄 召回", key=f"recover_{task_id[:8]}", use_container_width=True):
                        st.session_state.task_id = task_id
                        st.session_state.task_state = status
                        st.rerun()

            # 删除按钮
            with col2:
                if st.button("🗑️", key=f"delete_{task_id[:8]}", use_container_width=True, help="删除此任务记录"):
                    if delete_task_from_history(task_id):
                        st.toast(f"✅ 已删除任务: {task_id[:12]}...")
                        st.rerun()
                    else:
                        st.error("删除失败")

# ==================== Pipeline 可视化 ====================
def render_pipeline_visualizer():
    """V7.5 Pipeline 可视化"""
    task_progress = st.session_state.get('task_progress', 0)
    task_state = st.session_state.get('task_state', 'PENDING')
    task_message = st.session_state.get('task_message', '')
    pipeline_logs = st.session_state.get('pipeline_logs', [])

    st.markdown("""
    <div class="terminal-box">
        <div class="terminal-header">🔥 V7.5 Phoenix Pipeline Monitor</div>
    """, unsafe_allow_html=True)

    # 进度条
    st.markdown(f"""
    <div class="v7-progress-bar">
        <div class="v7-progress-fill" style="width: {task_progress}%"></div>
    </div>
    <div style="color: #fbbf24; font-size: 0.8rem; margin-top: 0.3rem;">
        Progress: {task_progress}% | State: {task_state}
    </div>
    """, unsafe_allow_html=True)

    # 当前步骤
    current_step_idx = max(1, min(13, task_progress // 8 + 1))
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
            <span style="color: #64748b; font-size: 0.75rem;">[{log_entry.get('time', 'N/A')}]</span>
            Step {log_entry.get('step', '?')}: {log_entry.get('message', '')}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_poll_stats():
    """轮询统计卡片"""
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
        <p>已轮询: {poll_count} 次 / {MAX_POLL_ATTEMPTS} | 耗时: {elapsed_str}</p>
    </div>
    """, unsafe_allow_html=True)


# ==================== 安全提交按钮 ====================
def render_safe_submit_button(user_input: str, config: Dict) -> Optional[str]:
    """安全提交按钮"""
    init_submission_guard()

    task_id = st.session_state.get('task_id')
    task_state = st.session_state.get('task_state')

    if task_state in ['PROGRESS', 'SUCCESS', 'FAILURE', 'TIMEOUT']:
        return None

    if task_state == 'PENDING' and task_id:
        st.info(f"""
        ⏳ 任务已提交

        **Task ID**: `{task_id[:20]}...`
        **状态**: 等待 Worker 接收

        请勿重复提交，系统会自动轮询状态...
        """)
        return None

    can_submit, reason = check_submission_guard(user_input)

    if not can_submit:
        st.button("🚀 启动凤凰演化", type="secondary", disabled=True, key='submit_disabled')
        st.warning(f"🔒 {reason}")
        return None

    if st.button("🚀 启动凤凰演化", type="primary", key='submit_btn'):
        if not user_input.strip():
            st.warning("⚠️ 请输入研究想法")
            return None

        acquire_submission_lock(user_input)

        try:
            task_id, dispatch_result = submit_celery_task_with_safety(user_input, config)

            if task_id:
                st.success(f"✅ 任务已派发: {task_id[:20]}...")
                st.info("⏳ 正在异步执行，请稍候...")

                st.session_state.poll_start_time = datetime.now().isoformat()
                st.session_state.poll_attempt_count = 0
                st.session_state.axiom_badge_state = 'waiting'

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


def render_phoenix_failure_report(result: Dict):
    """Phoenix 协议失败报告"""
    payload = result.get('payload', {})
    failure_state = payload.get('failure_state', 'UNKNOWN')
    iterations = payload.get('iterations', 0)
    score_history = payload.get('score_history', [])
    version_chain = payload.get('version_chain', [])
    reason = payload.get('reason', '未知原因')

    # 根据失败类型显示不同的消息
    failure_messages = {
        'MAX_PHOENIX_EXCEEDED': '⏰ 演化达到最大迭代次数限制',
        'HARD_FAILURE': '❌ 遇到无法修复的物理冲突',
        'UNKNOWN': '⚠️ 未知错误'
    }
    title = failure_messages.get(failure_state, f'⚠️ {failure_state}')

    st.markdown(f"""
    <div class="warning-card">
        <h2>{title}</h2>
        <p><strong>迭代次数</strong>: {iterations} 次</p>
        <p><strong>失败原因</strong>: {reason}</p>
    </div>
    """, unsafe_allow_html=True)

    # 分数历史
    if score_history:
        st.markdown("---")
        st.markdown("### 📊 分数演化历史")
        for i, score in enumerate(score_history):
            st.markdown(f"- **v1.{i}**: Science Score = {score:.2f}")

    # 版本链
    if version_chain:
        st.markdown("---")
        st.markdown("### 🔥 版本演化链")
        for v in version_chain:
            version = v.get('version', 'N/A')
            v_type = v.get('type_display', v.get('type', 'N/A'))
            score = v.get('science_score', 0)
            created_at = v.get('created_at', 'N/A')[:19]

            st.markdown(f"""
            <div class="version-card">
                <strong>{version}</strong> ({v_type}) | Score: {score:.2f} | {created_at}
            </div>
            """, unsafe_allow_html=True)

            # 显示假设内容（如果有）
            hc = v.get('hypothesis_content')
            if hc and isinstance(hc, dict):
                title = hc.get('title', '')
                description = hc.get('description', '')
                if title or description:
                    st.markdown(f"- **标题**: {title[:100] if title else 'N/A'}")
                    if description:
                        with st.expander("查看描述"):
                            st.write(description[:500])


# ==================== V7.5 成功报告渲染 ====================
def render_success_report(result: Dict):
    """V7.5 凤凰协议成功报告"""
    payload = result.get('payload', {})

    # 检查是否为 Phoenix 失败结果
    failure_state = payload.get('failure_state')
    if failure_state:
        render_phoenix_failure_report(result)
        return

    st.markdown("""
    <div class="success-card">
        <h2>🎉 凤凰演化完成</h2>
    </div>
    """, unsafe_allow_html=True)

    hypothesis = payload.get('hypothesis', {})
    fitness = payload.get('fitness', {})

    # 提取凤凰协议数据
    phoenix_protocol = payload.get('phoenix_protocol', {})
    version_evolution = payload.get('version_evolution', {})
    version_chain = version_evolution.get('chain', [])
    score_history = phoenix_protocol.get('score_evolution', [])

    # 判断是否为 MAX_PHOENIX_EXCEEDED
    final_state = phoenix_protocol.get('final_state', '')
    is_max_exceeded = final_state == 'MAX_PHOENIX_EXCEEDED'

    # 如果超过最大迭代次数，显示最佳候选方案
    if is_max_exceeded:
        st.markdown("### ⏰ 演化达到上限，展示最佳候选方案")
        render_top_candidate_badge(result)

    # 创建多个主要 Tabs
    tabs = st.tabs([
        "📄 完整报告", "📋 落地指南", "💡 创新分析", "🔬 前沿溯源", "🔥 演化实验室", "📚 文献支撑"
    ])

    with tabs[0]:
        st.markdown(f"""
        <div class="report-container">
            <h3>{hypothesis.get('title', '未命名假设')}</h3>
            <p><strong>学科领域</strong>: {payload.get('domain', 'N/A')}</p>
            <p><strong>版本</strong>: {hypothesis.get('version', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)

        # 重构真正的���设陈述（从 methodology 提取核心假设）
        methodology = hypothesis.get('methodology', {})
        if methodology:
            st.markdown("### 🎯 核心假设陈述")

            # 从方法论中提取核心假设
            bias_control = methodology.get('bias_control', '')
            validation_protocol = methodology.get('validation_protocol', '')

            # 构建假设陈述
            if 'DAG' in bias_control or '因果' in bias_control:
                # 因果链结构
                st.markdown("""
**因果链结构**:
```
突变/干预 (X) → 方法学改进 (M) → 偏倚降低/因果识别 (Y) → 模型性能提升
```
""")

                hypothesis_statement = f"""**研究假设**:

本研究假设：通过引入**因果推断框架（DAG与混杂因子调整）**结合**Pipeline-封装式机器学习范式**，能够：

1. **显著降低数据穿越偏倚**：通过严格的信息隔离协议，确保测试集统计信息不泄露到训练过程
2. **提高模型因果推断准确性**：通过DAG识别并控制混杂因子，消除虚假关联
3. **提升模型泛化能力**：通过嵌套交叉验证获得无偏的性能估计

**假设检验方法**: {validation_protocol[:100] if validation_protocol else '见方法论详情'}..."""
            else:
                hypothesis_statement = f"""**研究假设**:

{hypothesis.get('title', '该研究提出的新方法')}将显著提升临床预测模型的性能与可靠性。

**假设检验方法**: {validation_protocol[:100] if validation_protocol else '见方法论详情'}..."""

            st.markdown(hypothesis_statement)
            st.markdown("---")

        # 版本迭代说明（如果有）
        details = hypothesis.get('details', hypothesis.get('description', ''))
        # 简化条件：只要 details 存在且长度大于50，就显示为版本迭代说明
        if details and len(details) > 50:
            st.markdown("### 研究背景")
            st.info(details)

        # 方法论详情
        methodology = hypothesis.get('methodology', {})
        if methodology:
            st.markdown("---")
            st.markdown("### 🔬 方法论")

            if isinstance(methodology, dict):
                for key, value in methodology.items():
                    key_display = {
                        'technical_safeguards': '技术保障',
                        'validation_protocol': '验证协议',
                        'bias_control': '偏倚控制',
                        'approach': '技术路径',
                        'statistical_framework': '统计框架',
                        'cohort_definition': '队列定义',
                        'expected_outcomes': '预期结果',
                        'innovation_analysis': '创新分析',
                    }.get(key, key)

                    st.markdown(f"**{key_display}**")

                    if isinstance(value, list):
                        for item in value:
                            st.markdown(f"  • {item}")
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            st.markdown(f"  • **{sub_key}**: {sub_value}")
                    else:
                        st.markdown(f"{value}")
                    st.markdown("")
            else:
                st.markdown(str(methodology))

        # 补丁日志
        patch_log = hypothesis.get('patch_log', [])
        if patch_log:
            st.markdown("---")
            st.markdown("### 🔧 演化记录")
            for i, patch in enumerate(patch_log, 1):
                st.markdown(f"**迭代 {i}**: {patch}")

        # 混合适应度
        if fitness:
            st.markdown("---")
            st.markdown("### 📊 混合适应度评估")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总分", f"{fitness.get('hybrid_fitness', 0):.2f}")
            with col2:
                st.metric("创新度", f"{fitness.get('vector_novelty_score', 0):.2f}")
            with col3:
                st.metric("严谨度", f"{fitness.get('red_team_rigor_score', 0):.2f}")

            # 相似度解释
            similarity = fitness.get('similarity_interpretation', '')
            if similarity:
                st.info(f"**创新度分析**: {similarity}")

        # 防御日志（从 audit_context 提取）
        audit_context = payload.get('audit_context', {})
        if audit_context:
            st.markdown("---")
            st.markdown("## 【4. Defense Log - 防御日志】")

            # 迭代统计
            iterations = audit_context.get('iterations', 0)
            patches = audit_context.get('patches', 0)
            rewrites = audit_context.get('rewrites', 0)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总迭代次数", iterations)
            with col2:
                st.metric("方法论补丁", patches)
            with col3:
                st.metric("物理重写", rewrites)

            # 红方攻击类型
            red_attack_types = audit_context.get('red_attack_types', [])
            if red_attack_types:
                st.markdown("---")
                st.markdown("### 红方攻击审计")

                attack_severity = {
                    'Data Leakage': '💀 致命',
                    'Endogeneity': '💀 致命',
                    'Multiple Testing': '⚠️ 严重',
                    'Statistical Power': '⚠️ 严重',
                    'Causal Inference': '💀 致命',
                    'Reproducibility': '⚠️ 严重',
                }

                for attack in red_attack_types:
                    severity = attack_severity.get(attack, '📝 中等')
                    st.markdown(f"**{attack}** | {severity}")

            # 补丁日志
            patch_log = hypothesis.get('patch_log', [])
            if patch_log:
                st.markdown("---")
                st.markdown("### 方法论补丁注入")
                for i, patch in enumerate(patch_log, 1):
                    if isinstance(patch, dict):
                        attack_type = patch.get('attack_type', '未知')
                        patch_applied = patch.get('patch_applied', '')
                        reference = patch.get('supporting_reference', '')

                        st.markdown(f"**迭代 {i}**: {attack_type}")
                        if patch_applied:
                            st.markdown(f"> 补丁措施: {patch_applied}")
                        if reference:
                            st.markdown(f"> 参考文献: {reference}")
                    else:
                        st.markdown(f"**迭代 {i}**: {patch}")
                    st.markdown("")

    with tabs[1]:
        # 落地指南
        roadmap = payload.get('implementation_roadmap', {})
        if roadmap:
            st.markdown("## 📋 Implementation Roadmap (落地指南)")

            # 阶段规划
            phases = roadmap.get('phases', [])
            if phases:
                st.markdown("### 🎯 阶段规划")
                for phase in phases:
                    phase_name = phase.get('phase', phase.get('name', '未命名阶段'))
                    duration = phase.get('duration', '')
                    milestones = phase.get('milestones', [])
                    deliverables = phase.get('deliverables', [])

                    st.markdown(f"**{phase_name}**")
                    if duration:
                        st.markdown(f"⏱️ *{duration}*")

                    if milestones:
                        st.markdown("**里程碑**:")
                        for ms in milestones:
                            st.markdown(f"  • {ms}")

                    if deliverables:
                        st.markdown("**交付物**:")
                        for d in deliverables:
                            st.markdown(f"  • {d}")
                    st.markdown("")

            # 资源需求
            resources = roadmap.get('resources', {})
            if resources:
                st.markdown("---")
                st.markdown("### 🔧 资源需求")

                # 人员
                personnel = resources.get('personnel', {})
                if personnel:
                    st.markdown("**👥 人员配置**")
                    for role, detail in personnel.items():
                        if isinstance(detail, dict):
                            st.markdown(f"  • **{role}**: {detail.get('count', detail.get('name', 'N/A'))}")
                        else:
                            st.markdown(f"  • **{role}**: {detail}")

                # 设备
                equipment = resources.get('equipment', {})
                if equipment:
                    st.markdown("**🖥️ 设备需求**")
                    for key, val in equipment.items():
                        if isinstance(val, dict):
                            st.markdown(f"  • **{key}**: {val.get('type', val.get('name', 'N/A'))}")
                        else:
                            st.markdown(f"  • **{key}**: {val}")

                # 数据
                data = resources.get('data', {})
                if data:
                    st.markdown("**📊 数据需求**")
                    for key, val in data.items():
                        st.markdown(f"  • **{key}**: {val}")

            # 时间线
            timeline = roadmap.get('timeline', {})
            if timeline:
                st.markdown("---")
                st.markdown("### ⏱️ 时间线")
                st.markdown(f"**总周期**: {timeline.get('total_duration', 'N/A')}")
                milestones = timeline.get('milestones', [])
                if milestones:
                    for ms in milestones:
                        st.markdown(f"  • {ms}")

            # 风险评估
            risks = roadmap.get('risks', [])
            if risks:
                st.markdown("---")
                st.markdown("### ⚠️ 风险评估")
                for risk in risks:
                    category = risk.get('category', risk.get('type', '未知'))
                    description = risk.get('description', '')
                    mitigation = risk.get('mitigation', '')
                    severity = risk.get('severity', 'medium')

                    severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(severity, '⚪')
                    st.warning(f"{severity_icon} **{category}**")
                    if description:
                        st.markdown(f">{description}")
                    if mitigation:
                        st.markdown(f"*应对策略*: {mitigation}")
                    st.markdown("")

            # 预算估算
            budget = roadmap.get('budget', {})
            if budget:
                st.markdown("---")
                st.markdown("### 💰 预算估算")

                estimated_total = budget.get('estimated_total', 'N/A')
                if estimated_total:
                    st.metric("预估总成本", estimated_total)

                breakdown = budget.get('breakdown', {})
                if breakdown:
                    st.markdown("**成本明细**:")
                    for item, cost in breakdown.items():
                        st.markdown(f"  • {item}: {cost}")

                note = budget.get('note', '')
                if note:
                    st.info(f"ℹ️ {note}")
        else:
            st.info("暂无落地指南数据")

    with tabs[2]:
        # 创新分析
        innovation = payload.get('innovation_analysis', {})
        if innovation:
            st.markdown("## 💡 Innovation Analysis (创新分析)")

            # 核心创新点
            core = innovation.get('core_innovations', [])
            if core:
                st.markdown("### 🌟 核心创新点")
                for i, item in enumerate(core, 1):
                    st.markdown(f"**{i}.** {item}")

            # 新颖度等级
            novelty = innovation.get('novelty_level')
            if novelty:
                st.markdown("---")
                st.markdown("### 📊 新颖度等级")
                if isinstance(novelty, dict):
                    level = novelty.get('level', 'N/A')
                    score = novelty.get('score', 0)
                    st.metric("等级", level)
                    st.metric("评分", f"{score:.2f}")
                else:
                    # novelty_level 是字符串
                    level_display = {
                        'breakthrough': '🌟 突破性',
                        'incremental': '📈 渐进式',
                        'novel': '💡 原创性',
                    }.get(novelty, novelty)
                    st.metric("等级", level_display)

            # 差异化分析
            diff = innovation.get('differentiation', [])
            if diff:
                st.markdown("---")
                st.markdown("### 🔄 差异化分析")
                for item in diff:
                    st.markdown(f"  • {item}")

            # 突破潜力
            potential = innovation.get('breakthrough_potential')
            if potential:
                st.markdown("---")
                st.markdown("### 🚀 突破潜力")
                if isinstance(potential, dict):
                    st.metric("Science Score", f"{potential.get('science_score', 0):.2f}")
                    st.metric("Promise Score", f"{potential.get('promise_score', 0):.2f}")
                else:
                    st.markdown(f"**突破潜力**: {potential}")

            # 总结
            summary = innovation.get('summary', '')
            if summary:
                st.markdown("---")
                st.markdown("### 📝 总结")
                st.markdown(summary)
        else:
            st.info("暂无创新分析数据")

    with tabs[3]:
        # 前沿溯源分析
        frontier = payload.get('frontier_analysis', {})
        if frontier:
            st.markdown("## 🔬 Frontier Analysis (前沿溯源)")

            # 前沿定位
            position = frontier.get('frontier_position')
            if position:
                st.markdown("### 📍 前沿定位")
                if isinstance(position, dict):
                    st.markdown(f"**2026 SoTA对比**: {position.get('sota_comparison', 'N/A')}")
                    st.markdown(f"**位置**: {position.get('position', 'N/A')}")
                else:
                    st.markdown(f"**前沿定位**: {position}")

            # 关键出版物
            pubs = frontier.get('key_publications', [])
            if pubs:
                st.markdown("---")
                st.markdown("### 📄 关键出版物")
                for pub in pubs[:5]:
                    title = pub.get('title', 'N/A')
                    cite = pub.get('citation_count', 0)
                    st.markdown(f"  • **{title}** (引用: {cite})")

            # 研究趋势
            trends = frontier.get('research_trends', [])
            if trends:
                st.markdown("---")
                st.markdown("### 📈 研究趋势")
                for trend in trends:
                    st.markdown(f"  • {trend}")

            # Gap分析
            gaps = frontier.get('gap_analysis', [])
            if gaps:
                st.markdown("---")
                st.markdown("### 🔍 研究空白 (Gap Analysis)")
                for gap in gaps:
                    st.markdown(f"  • {gap}")

            # 引用速度
            citation = frontier.get('citation_velocity')
            year_trend = frontier.get('year_trend')
            if citation or year_trend:
                st.markdown("---")
                st.markdown("### ⚡ 引用速度与趋势")
                if citation:
                    if isinstance(citation, dict):
                        st.metric("年均引用", f"{citation.get('avg_per_year', 0):.1f}")
                        st.metric("增长趋势", f"{citation.get('growth_rate', 0):.1%}")
                    else:
                        st.markdown(f"**引用速度**: {citation}")
                if year_trend:
                    st.markdown(f"**年度趋势**: {year_trend}")
        else:
            st.info("暂无前沿溯源数据")

    with tabs[4]:
        st.markdown(f"""
        <div class="report-container">
            <h3>{hypothesis.get('title', '未命名假设')}</h3>
            <p><strong>学科领域</strong>: {payload.get('domain', 'N/A')}</p>
            <p><strong>版本</strong>: {hypothesis.get('version', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)

        # 详细描述
        details = hypothesis.get('details', hypothesis.get('description', ''))
        if details:
            st.markdown("### 📋 假设概述")
            st.markdown(f"<div class='report-container'>{details}</div>", unsafe_allow_html=True)

        # 方法论详情
        methodology = hypothesis.get('methodology', {})
        if methodology:
            st.markdown("---")
            st.markdown("### 🔬 方法论")

            if isinstance(methodology, dict):
                for key, value in methodology.items():
                    key_display = {
                        'technical_safeguards': '技术保障',
                        'validation_protocol': '验证协议',
                        'bias_control': '偏倚控制',
                        'approach': '技术路径',
                        'statistical_framework': '统计框架',
                        'cohort_definition': '队列定义',
                        'expected_outcomes': '预期结果',
                        'innovation_analysis': '创新分析',
                    }.get(key, key)

                    st.markdown(f"**{key_display}**")

                    if isinstance(value, list):
                        for item in value:
                            st.markdown(f"  • {item}")
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            st.markdown(f"  • **{sub_key}**: {sub_value}")
                    else:
                        st.markdown(f"{value}")
                    st.markdown("")
            else:
                st.markdown(str(methodology))

        # 补丁日志
        patch_log = hypothesis.get('patch_log', [])
        if patch_log:
            st.markdown("---")
            st.markdown("### 🔧 演化记录")
            for i, patch in enumerate(patch_log, 1):
                st.markdown(f"**迭代 {i}**: {patch}")

        # 混合适应度
        if fitness:
            st.markdown("---")
            st.markdown("### 📊 混合适应度评估")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总分", f"{fitness.get('hybrid_fitness', 0):.2f}")
            with col2:
                st.metric("创新度", f"{fitness.get('vector_novelty_score', 0):.2f}")
            with col3:
                st.metric("严谨度", f"{fitness.get('red_team_rigor_score', 0):.2f}")

            # 相似度解释
            similarity = fitness.get('similarity_interpretation', '')
            if similarity:
                st.info(f"**创新度分析**: {similarity}")

        # 防御日志（从 audit_context 提取）
        audit_context = payload.get('audit_context', {})
        if audit_context:
            st.markdown("---")
            st.markdown("## 【4. Defense Log - 防御日志】")

            # 迭代统计
            iterations = audit_context.get('iterations', 0)
            patches = audit_context.get('patches', 0)
            rewrites = audit_context.get('rewrites', 0)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总迭代次数", iterations)
            with col2:
                st.metric("方法论补丁", patches)
            with col3:
                st.metric("物理重写", rewrites)

            # 红方攻击类型
            red_attack_types = audit_context.get('red_attack_types', [])
            if red_attack_types:
                st.markdown("---")
                st.markdown("### 红方攻击审计")

                attack_severity = {
                    'Data Leakage': '💀 致命',
                    'Endogeneity': '💀 致命',
                    'Multiple Testing': '⚠️ 严重',
                    'Statistical Power': '⚠️ 严重',
                    'Causal Inference': '💀 致命',
                    'Reproducibility': '⚠️ 严重',
                }

                for attack in red_attack_types:
                    severity = attack_severity.get(attack, '📝 中等')
                    st.markdown(f"**{attack}** | {severity}")

            # 补丁日志
            patch_log = hypothesis.get('patch_log', [])
            if patch_log:
                st.markdown("---")
                st.markdown("### 方法论补丁注入")
                for i, patch in enumerate(patch_log, 1):
                    if isinstance(patch, dict):
                        attack_type = patch.get('attack_type', '未知')
                        patch_applied = patch.get('patch_applied', '')
                        reference = patch.get('supporting_reference', '')

                        st.markdown(f"**迭代 {i}**: {attack_type}")
                        if patch_applied:
                            st.markdown(f"> 补丁措施: {patch_applied}")
                        if reference:
                            st.markdown(f"> 参考文献: {reference}")
                    else:
                        st.markdown(f"**迭代 {i}**: {patch}")
                    st.markdown("")

    with tabs[4]:
        st.markdown("### 🔥 V7.5 演化实验室")

        # 凤凰协议统计
        if phoenix_protocol:
            render_phoenix_status_panel(phoenix_protocol)

        # 版本演进图
        if version_chain:
            st.markdown("---")
            render_phoenix_evolution_graph(version_chain)

        # 分数趋势图
        if score_history:
            st.markdown("---")
            render_score_trend_chart(score_history)

        # 版本滑块
        if version_chain and len(version_chain) > 1:
            st.markdown("---")
            render_evolution_slider(version_chain)

        # 对抗溯源看板
        st.markdown("---")
        render_conflict_trace(result)

    with tabs[5]:
        st.markdown(f"""
        <div class="report-container">
            <h4>验证过的文献引用</h4>
            <p>PubMed PMIDs: {len(payload.get('verified_ids', {}).get('pmids', []))} 篇</p>
            <p>数据源: {', '.join(payload.get('sources', []))}</p>
        </div>
        """, unsafe_allow_html=True)


def render_rejection_report(error_info: Dict, user_input: str):
    """拒绝报告"""
    st.markdown("""
    <div class="rejection-card">
        <h2>🚫 科研否决报告</h2>
        <div class="reason">研究假设生成失败</div>
    </div>
    """, unsafe_allow_html=True)

    error_type = error_info.get('result_type', error_info.get('state', 'unknown'))
    error_message = error_info.get('error', '未知错误')

    st.error(f"""
    **否决类型**: {error_type}
    **否决原因**: {error_message}
    """)

    # V7.5: 显示 Phoenix 失败信息
    if error_type == 'phoenix_failure':
        payload = error_info.get('payload', {})
        failure_state = payload.get('failure_state', 'UNKNOWN')
        iterations = payload.get('iterations', 0)
        score_history = payload.get('score_history', [])

        st.warning(f"""
        **凤凰协议状态**: {failure_state}
        **迭代次数**: {iterations}
        **分数历史**: {score_history}
        """)


def render_timeout_report(task_id: str, reason: str, details: Dict):
    """超时报告"""
    st.markdown("""
    <div class="rejection-card">
        <h2>⏰ 任务超时</h2>
    </div>
    """, unsafe_allow_html=True)

    if reason == "GLOBAL_TIMEOUT":
        st.error(f"""
        任务轮询超过 {details.get('elapsed_minutes', 0)} 分钟
        """)
    elif reason == "WORKER_NOT_RESPONDING":
        st.error("Celery Worker 无响应")
    elif reason == "STATE_STAGNANT":
        st.warning(f"""
        任务状态 {details.get('stagnant_minutes', 0)} 分钟无变化
        """)

    if st.button("🚫 撤销僵尸任务", key='revoke_zombie'):
        if CELERY_AVAILABLE:
            celery_app = get_celery_app()
            celery_app.control.revoke(task_id, terminate=True)
            st.success("✅ 任务已撤销")

        for key in ['task_id', 'task_state', 'poll_start_time', 'poll_attempt_count']:
            st.session_state[key] = None if key != 'poll_attempt_count' else 0

        update_task_completion(task_id, 'REVOKED')
        st.rerun()

# ==================== 主界面 ====================
def render_main_interface():
    """V7.5 主界面"""

    # 标题
    st.markdown("""
    <div class="v75-header">
        <h1>🔥 V7.5 Phoenix Evolution - 凤凰协议演化引擎</h1>
        <div class="subtitle">
            Celery + Redis + SQLite | 演化型逻辑 | 版本可视化 | Promise Score
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 用户输入区
    st.markdown("### 📝 研究想法输入")

    col1, col2 = st.columns([4, 1])

    with col1:
        user_input = st.text_area(
            "输入您的研究想法",
            placeholder="例如：阿尔茨海默病患者海马体萎缩与认知功能下降的关系研究...",
            height=120,
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

        # 物理公理指示灯
        axiom_state = st.session_state.get('axiom_badge_state', 'waiting')
        if axiom_state == 'waiting':
            st.markdown('<span class="axiom-badge waiting">⏳ 等待检阅</span>', unsafe_allow_html=True)
        elif axiom_state == 'passed':
            st.markdown('<span class="axiom-badge passed">✅ 科学底线达标</span>', unsafe_allow_html=True)
        elif axiom_state == 'failed':
            st.markdown('<span class="axiom-badge failed">❌ 物理公理冲突</span>', unsafe_allow_html=True)

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
    if task_state == 'PROGRESS' or task_state == 'PENDING':
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
                st.session_state.task_result = poll_result.get('result')
                st.session_state.task_state = 'SUCCESS'
                st.success("🎉 任务执行成功！")
                st.rerun()
            elif poll_result['state'] == 'FAILURE':
                st.session_state.task_result = poll_result.get('result', poll_result)
                st.session_state.task_state = 'FAILURE'
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
            st.session_state.axiom_badge_state = 'waiting'
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
            st.session_state.axiom_badge_state = 'waiting'
            st.rerun()

    # 任务超时
    elif task_state == 'TIMEOUT':
        render_timeout_report(
            task_id,
            st.session_state.get('error_type', 'UNKNOWN'),
            {'reason': st.session_state.get('error_message', '超时')}
        )

    # Celery 不可用提示
    if not CELERY_AVAILABLE:
        st.markdown("""
        <div class="status-card warning">
            <h4>⚠️ Celery 后端不可用</h4>
            <p>异步任务系统未启动</p>
            <p>请确保 Redis 和 Celery Worker 正常运行</p>
        </div>
        """, unsafe_allow_html=True)

# ==================== 主程序入口 ====================
def main():
    """V7.5 主程序入口"""
    logger.info("V7.5 app.py 开始执行...")

    # 初始化 Session State
    init_session_state()

    # 初始化持久化数据库
    init_task_persistence_db()
    init_local_queue_db()

    # 初始化守卫
    init_submission_guard()
    init_poll_guard()

    # 刷新后任务召回
    if st.session_state.task_id is None:
        recovered = recover_lost_task_on_reload()
        if recovered:
            st.toast(f"🔄 已自动恢复任务: {recovered[:12]}...")
            logger.info(f"任务召回成功: {recovered}")

    # 渲染主界面
    render_main_interface()

    logger.info("V7.5 app.py 执行完成")


if __name__ == '__main__':
    main()
