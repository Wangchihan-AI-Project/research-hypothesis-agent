# -*- coding: utf-8 -*-
"""
任务持久化数据库模块

从 app.py 提取，纯 DB 操作函数，无 Streamlit 依赖。
"""

import sqlite3
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from src.utils.logger import get_central_logger

logger = get_central_logger()

# 模块级变量（由 app.py 在导入后设置）
PERSISTENCE_DB: Optional[Path] = None
LOCAL_QUEUE_DB: Optional[Path] = None
DATA_DIR: Optional[Path] = None


def init_task_persistence_db() -> bool:
    """任务持久化数据库初始化"""
    try:
        conn = sqlite3.connect(str(PERSISTENCE_DB))
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


def init_local_queue_db() -> bool:
    """本地队列数据库初始化"""
    try:
        conn = sqlite3.connect(str(LOCAL_QUEUE_DB))
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


def register_task_persistence(task_id: str, user_input: str, config: Dict, session_id: str = None) -> bool:
    """任务注册"""
    try:
        conn = sqlite3.connect(str(PERSISTENCE_DB))
        cursor = conn.cursor()

        input_hash = hashlib.sha256(user_input.encode()).hexdigest()[:16]
        # 确保 session_id 不为空
        if session_id is None:
            session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
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


def recover_lost_task_on_reload(
    session_state,
    poll_task_status_safe_fn,
    celery_available: bool = False,
) -> Optional[str]:
    """刷新后任务召回

    Args:
        session_state: Streamlit session_state (dict-like)
        poll_task_status_safe_fn: 安全轮询函数，签名为 (task_id: str) -> Dict
        celery_available: Celery 是否可用
    """
    try:
        current_tab_id = session_state.get('tab_session_id', '')
        if not current_tab_id:
            return None

        conn = sqlite3.connect(str(PERSISTENCE_DB))
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
                    conn = sqlite3.connect(str(PERSISTENCE_DB))
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

            if celery_available:
                actual_result = poll_task_status_safe_fn(task_id)
                actual_state = actual_result['state']

                if actual_state in ['SUCCESS', 'FAILURE']:
                    update_task_completion(task_id, actual_state, result_json)
                    return None

                try:
                    conn = sqlite3.connect(str(PERSISTENCE_DB))
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

                session_state['task_id'] = task_id
                session_state['task_state'] = actual_state
                session_state['task_start_time'] = created_at
                session_state['user_input'] = input_preview or ''

                if config_json:
                    try:
                        config = json.loads(config_json)
                        session_state['min_score_threshold'] = config.get('min_score_threshold', 7.0)
                        session_state['max_phoenix_iterations'] = config.get('max_phoenix_iterations', 8)
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
        conn = sqlite3.connect(str(PERSISTENCE_DB))
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
            conn = sqlite3.connect(str(research_db))
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
        conn = sqlite3.connect(str(PERSISTENCE_DB))
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
        conn = sqlite3.connect(str(PERSISTENCE_DB))
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
                conn = sqlite3.connect(str(research_db))
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
        conn = sqlite3.connect(str(PERSISTENCE_DB))
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
            conn = sqlite3.connect(str(research_db))
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


__all__ = [
    'PERSISTENCE_DB',
    'LOCAL_QUEUE_DB',
    'DATA_DIR',
    'init_task_persistence_db',
    'init_local_queue_db',
    'register_task_persistence',
    'update_task_completion',
    'get_task_history_list',
    'delete_task_from_history',
    'clear_all_task_history',
    'recover_lost_task_on_reload',
]
