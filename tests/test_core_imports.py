# -*- coding: utf-8 -*-
"""核心入口 smoke test。"""


def test_core_entrypoints_importable():
    from src.core.celery_tasks_v75 import get_celery_app
    from src.core.orchestrator import Orchestrator
    from src.utils.logger import CentralizedLogger

    logger = CentralizedLogger()

    assert Orchestrator is not None
    assert get_celery_app is not None
    assert hasattr(logger, "session_start")
