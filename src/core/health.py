# -*- coding: utf-8 -*-
"""
健康检查模块

从 app.py 提取，提供 Redis / Worker 心跳检测功能。
"""

import os
from typing import Tuple

from src.utils.logger import get_central_logger

logger = get_central_logger()

# 模块级变量（由 app.py 在导入后设置）
CELERY_AVAILABLE: bool = False


def check_redis_health() -> Tuple[bool, str]:
    """Redis 连接健康检查"""
    if not CELERY_AVAILABLE:
        return False, "Celery 模块未加载"

    try:
        from src.core.celery_tasks_v75 import get_celery_app

        celery_app = get_celery_app()

        with celery_app.connection_or_acquire() as conn:
            if not conn.connected:
                conn.ensure_connection(max_retries=2, interval_start=0.5)
            # 不关闭 channel，避免影响后续 inspect 调用

        return True, ""

    except Exception as e:
        if 'ConnectionError' in type(e).__name__:
            return False, f"Redis 连接失败: {str(e)}"
        return False, f"健康检查异常: {str(e)}"


def check_worker_heartbeat() -> bool:
    """Worker 心跳检测"""
    if not CELERY_AVAILABLE:
        logger.warning("[Health Check] CELERY_AVAILABLE=False")
        return False

    try:
        from src.core.celery_tasks_v75 import get_celery_app
        celery_app = get_celery_app()
        inspect = celery_app.control.inspect(timeout=3.0)

        # 优先使用 ping() — Celery 原生检测方式
        pings = inspect.ping()
        if pings and len(pings) > 0:
            logger.info(f"[Health Check] ping 检测到 {len(pings)} 个 Worker: {list(pings.keys())}")
            return True

        # 备用: active()
        active_workers = inspect.active()
        if active_workers and len(active_workers) > 0:
            logger.info(f"[Health Check] active 检测到 {len(active_workers)} 个 Worker")
            return True

    except Exception as e:
        import traceback
        logger.error(f"[Health Check] 异常: {e}\n{traceback.format_exc()}")

    logger.warning("[Health Check] 未检测到 Worker")
    return False


__all__ = [
    'CELERY_AVAILABLE',
    'check_redis_health',
    'check_worker_heartbeat',
]
