# -*- coding: utf-8 -*-
"""
提交守卫与轮询守卫模块

从 app.py 提取，接受 session_state 作为参数，无 Streamlit 直接依赖。
"""

import hashlib
from datetime import datetime, timedelta
from typing import Dict, Tuple, Callable

# 模块级常量（由 app.py 在导入后设置）
SUBMIT_COOLDOWN_SECONDS: int = 30
SUBMIT_DEBOUNCE_SECONDS: int = 5
MAX_POLL_ATTEMPTS: int = 100
POLL_INTERVAL_SECONDS: int = 3
ZOMBIE_TASK_THRESHOLD_MINUTES: int = 60


def check_submission_guard(session_state, user_input: str) -> Tuple[bool, str]:
    """提交守卫检查

    Args:
        session_state: Streamlit session_state (dict-like)
        user_input: 用户输入文本
    """
    now = datetime.now()

    # 检查 1: 提交锁
    if session_state.get('submission_lock', False):
        lock_holder = session_state.get('lock_holder_tab', '')
        current_tab = session_state.get('tab_session_id', '')

        if lock_holder and lock_holder != current_tab:
            return False, "其他 Tab 正在提交任务，请等待或刷新页面"

        return False, "已有任务正在提交中，请等待..."

    # 检查 2: 冷却期
    cooldown_until = session_state.get('submit_cooldown_until')
    if cooldown_until:
        cooldown_time = datetime.fromisoformat(cooldown_until)
        if now < cooldown_time:
            remaining = int((cooldown_time - now).total_seconds())
            return False, f"冷却期保护，请等待 {remaining} 秒后再次提交"
        else:
            session_state['submit_cooldown_until'] = None

    # 检查 3: 重复内容检测
    if user_input.strip():
        input_hash = hashlib.sha256(user_input.encode()).hexdigest()[:16]

        if input_hash == session_state.get('pending_input_hash'):
            if session_state.get('task_id'):
                return False, f"相同内容已提交 (Task: {session_state['task_id'][:16]}...)"

    # 检查 4: 防抖间隔
    last_submit = session_state.get('last_submit_time')
    if last_submit:
        last_time = datetime.fromisoformat(last_submit)
        elapsed = (now - last_time).total_seconds()
        if elapsed < SUBMIT_DEBOUNCE_SECONDS:
            return False, f"提交过于频繁，请等待 {int(SUBMIT_DEBOUNCE_SECONDS - elapsed)} 秒"

    return True, ""


def acquire_submission_lock(session_state, user_input: str):
    """获取提交锁

    Args:
        session_state: Streamlit session_state (dict-like)
        user_input: 用户输入文本
    """
    session_state['submission_lock'] = True
    session_state['last_submit_time'] = datetime.now().isoformat()
    session_state['lock_holder_tab'] = session_state.get('tab_session_id', '')

    if user_input.strip():
        session_state['pending_input_hash'] = hashlib.sha256(user_input.encode()).hexdigest()[:16]
    session_state['submit_cooldown_until'] = (datetime.now() + timedelta(seconds=SUBMIT_COOLDOWN_SECONDS)).isoformat()


def release_submission_lock(session_state):
    """释放提交锁

    Args:
        session_state: Streamlit session_state (dict-like)
    """
    session_state['submission_lock'] = False
    session_state['lock_holder_tab'] = None


def check_poll_guard(
    session_state,
    task_id: str,
    check_worker_heartbeat_fn: Callable[[], bool],
) -> Tuple[bool, str, Dict]:
    """轮询守卫检查

    Args:
        session_state: Streamlit session_state (dict-like)
        task_id: 任务 ID
        check_worker_heartbeat_fn: Worker 心跳检测函数，返回 bool
    """
    now = datetime.now()

    # 检查 1: 全局超时
    poll_start = session_state.get('poll_start_time')
    if poll_start:
        start_time = datetime.fromisoformat(poll_start)
        elapsed_minutes = (now - start_time).total_seconds() / 60

        if elapsed_minutes > ZOMBIE_TASK_THRESHOLD_MINUTES:
            return False, "GLOBAL_TIMEOUT", {
                'elapsed_minutes': elapsed_minutes,
                'reason': f'任务轮询超过 {ZOMBIE_TASK_THRESHOLD_MINUTES} 分钟'
            }

    # 检查 2: Worker 卡住检测（PENDING 状态过久，在达到 MAX_POLL 之前触发）
    poll_count = session_state.get('poll_attempt_count', 0)
    last_state = session_state.get('last_known_state')

    if poll_count >= 60 and last_state == 'PENDING':
        return False, "WORKER_STUCK", {
            'poll_count': poll_count,
            'last_state': last_state,
            'reason': f'Celery Worker 在 {poll_count * POLL_INTERVAL_SECONDS} 秒内未拾取任务，建议降级到本地执行'
        }

    # 检查 3: 最大轮询次数
    if poll_count > MAX_POLL_ATTEMPTS:
        return False, "MAX_POLL_EXCEEDED", {
            'poll_count': poll_count,
            'reason': f'轮询次数超过 {MAX_POLL_ATTEMPTS} 次'
        }

    # 检查 4: Worker 心跳
    worker_alive = check_worker_heartbeat_fn()
    if not worker_alive:
        return False, "WORKER_NOT_RESPONDING", {
            'reason': 'Celery Worker 无响应'
        }

    # 检查 5: 状态停滞检测
    last_state = session_state.get('last_known_state')
    last_change = session_state.get('last_state_change_time')

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


def should_fallback_to_local(session_state, task_id: str) -> bool:
    """检查是否应该降级到本地同步执行

    当任务长时间处于 PENDING 状态且轮询次数达到阈值时，
    表明 Celery Worker 可能没有正常拾取任务。

    Args:
        session_state: Streamlit session_state (dict-like)
        task_id: 任务 ID

    Returns:
        True 表示应该降级到本地执行
    """
    poll_count = session_state.get('poll_attempt_count', 0)
    last_state = session_state.get('last_known_state')

    if poll_count >= 60 and last_state == 'PENDING':
        return True

    return False


__all__ = [
    'SUBMIT_COOLDOWN_SECONDS',
    'SUBMIT_DEBOUNCE_SECONDS',
    'MAX_POLL_ATTEMPTS',
    'POLL_INTERVAL_SECONDS',
    'ZOMBIE_TASK_THRESHOLD_MINUTES',
    'check_submission_guard',
    'acquire_submission_lock',
    'release_submission_lock',
    'check_poll_guard',
    'should_fallback_to_local',
]
