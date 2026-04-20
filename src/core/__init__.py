"""
核心模块初始化
"""
from .database import init_database, Paper, Hypothesis, ResearchSession
from .db_manager import get_db_manager
from .config_loader import get_config

__all__ = [
    'init_database',
    'Paper',
    'Hypothesis',
    'ResearchSession',
    'get_db_manager',
    'get_config'
]