# -*- coding: utf-8 -*-
"""
共享页面基模块 - 消除 pages/ 下 8 个文件的重复样板代码

使用方式:
    from src.ui.page_base import setup_page, get_orchestrator
    project_root = setup_page("页面标题", "🔬")
"""

import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.ui.styles import inject_shared_css


def setup_page(title: str, icon: str = "🧪", layout: str = "wide") -> Path:
    """统一页面初始化: 路径设置, 环境变量, 页面配置, 共享样式注入.

    返回 project_root 供需要读取项目文件的页面使用.
    """
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(project_root / 'src'))

    load_dotenv(project_root / '.env', encoding='utf-8')

    st.set_page_config(page_title=title, page_icon=icon, layout=layout)
    inject_shared_css()

    return project_root


@st.cache_resource
def get_orchestrator(search_only: bool = False):
    """共享 Orchestrator 单例 (懒加载, 跨页面缓存)."""
    from src.core.orchestrator import Orchestrator
    return Orchestrator(search_only=search_only)
