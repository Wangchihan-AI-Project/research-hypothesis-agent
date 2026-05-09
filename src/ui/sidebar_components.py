# -*- coding: utf-8 -*-
"""
侧边栏组件 - 健康状态、配置面板、历史任务

从 app.py 提取，供主应用导入使用。
"""

import os
import streamlit as st
from datetime import datetime
from typing import Dict


def render_health_indicator(celery_available: bool, check_redis_health, check_worker_heartbeat):
    """健康状态指示灯"""
    if celery_available:
        health_ok, _ = check_redis_health()
        worker_alive = check_worker_heartbeat()

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

        with st.expander("🔍 诊断信息", expanded=True):
            st.code(f"""
Redis 连接: {'✅ 正常' if health_ok else '❌ 失败'}
Worker 状态: {'✅ 活跃' if worker_alive else '❌ 离线'}
Redis URL: {os.getenv('REDIS_URL', 'redis://localhost:6379/0')}
            """)

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
1. Worker 窗口未启动或已关闭
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


def render_sidebar_configurator(celery_available: bool, check_redis_health, check_worker_heartbeat) -> Dict:
    """V7.5 侧边栏配置"""
    st.sidebar.markdown("""
    <div class="sidebar-config-header">
        ⚙️ V7.5 Phoenix Evolution
    </div>
    """, unsafe_allow_html=True)

    # 页面导航引导
    with st.sidebar.expander("🧭 页面导航", expanded=False):
        st.markdown("""
        <div class="page-guide">
            <div class="page-item"><span class="icon">🏠</span> <b>主页</b> — 提交研究想法</div>
            <div class="page-item"><span class="icon">💬</span> <b>智能对话</b> <span class="desc">— AI 科研对话</span></div>
            <div class="page-item"><span class="icon">🔄</span> <b>传统工作流</b> <span class="desc">— 经典流程</span></div>
            <div class="page-item"><span class="icon">🔁</span> <b>自主循环</b> <span class="desc">— 自动迭代</span></div>
            <div class="page-item"><span class="icon">📚</span> <b>文献检索</b> <span class="desc">— 论文搜索</span></div>
            <div class="page-item"><span class="icon">📋</span> <b>假设管理</b> <span class="desc">— 版本管理</span></div>
            <div class="page-item"><span class="icon">⚙️</span> <b>配置策略</b> <span class="desc">— 参数调整</span></div>
            <div class="page-item"><span class="icon">🔬</span> <b>高级管道</b> <span class="desc">— 深度控制</span></div>
            <div class="page-item"><span class="icon">📊</span> <b>Meta评估</b> <span class="desc">— 质量评测</span></div>
        </div>
        """, unsafe_allow_html=True)

    st.sidebar.markdown("### 🩺 系统健康状态")
    render_health_indicator(celery_available, check_redis_health, check_worker_heartbeat)
    st.sidebar.markdown("---")

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
    st.sidebar.markdown("### 🧪 演化协议配置")

    max_phoenix = st.sidebar.slider(
        "最大演化迭代", min_value=4, max_value=12,
        value=st.session_state.get('max_phoenix_iterations', 4),
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
    st.sidebar.markdown("### 🎯 执行模式")
    execution_mode = st.sidebar.radio(
        "选择执行模式",
        options=['autonomous', 'hitl'],
        format_func=lambda x: "🤖 Autonomous" if x == 'autonomous' else "👤 HITL",
        key='execution_mode_select',
    )
    st.session_state.execution_mode = execution_mode

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🛡️ 防熔断参数")

    hard_cap = st.sidebar.slider(
        "API 调用上限", min_value=5, max_value=30,
        value=st.session_state.get('hard_cap', 15),
        key='hard_cap_slider'
    )
    st.session_state.hard_cap = hard_cap

    min_score = st.sidebar.slider(
        "分数及格线", min_value=5.0, max_value=9.0,
        value=st.session_state.get('min_score_threshold', 7.0),
        step=0.5, key='min_score_slider'
    )
    st.session_state.min_score_threshold = min_score

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📚 文献检索筛选")

    min_if = st.sidebar.slider(
        "最低影响因子 (IF)", min_value=0.0, max_value=30.0,
        value=st.session_state.get('min_if', 3.0),
        step=0.5, help="适用于PubMed等数据库。ArXiv无IF，将使用引用数替代",
        key='min_if_slider'
    )
    st.session_state.min_if = min_if

    current_year = datetime.now().year
    col_year1, col_year2 = st.sidebar.columns(2)
    with col_year1:
        start_year = st.number_input(
            "起始年份", min_value=1990, max_value=current_year,
            value=st.session_state.get('start_year', 2020),
            step=1, key='start_year_input'
        )
    with col_year2:
        end_year = st.number_input(
            "结束年份", min_value=1990, max_value=current_year + 2,
            value=st.session_state.get('end_year', current_year),
            step=1, key='end_year_input'
        )
    st.session_state.start_year = start_year
    st.session_state.end_year = end_year

    min_citations = st.sidebar.slider(
        "ArXiv最低引用数", min_value=0, max_value=500,
        value=st.session_state.get('min_citations', 10),
        step=5, help="ArXiv论文无影响因子，使用引用数作为质量指标",
        key='min_citations_slider'
    )
    st.session_state.min_citations = min_citations

    st.sidebar.info("💡 提示: ArXiv无IF，将自动使用引用数筛选")
    st.sidebar.markdown("---")

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


def render_task_history_sidebar(get_task_history_list, clear_all_task_history, delete_task_from_history):
    """任务历史列表"""
    import json

    st.sidebar.markdown("---")

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
            'SUCCESS': '🟢', 'FAILURE': '🔴',
            'PENDING': '🟡', 'PROGRESS': '🔵',
            'TIMEOUT': '🟠', 'ZOMBIE': '🟤',
        }.get(status, '⚪')

        with st.sidebar.expander(f"{status_color} {task_id[:12]}... | {status}", expanded=False):
            st.text(f"时间: {created_at}")
            st.text(f"内容: {preview}")
            st.text(f"ID: {task_id}")

            col1, col2 = st.columns(2)

            if status == 'SUCCESS' and result_json:
                with col1:
                    if st.button("📄 查看", key=f"view_{task_id[:8]}", use_container_width=True):
                        st.session_state.task_id = task_id
                        st.session_state.task_state = 'SUCCESS'
                        try:
                            result_data = json.loads(result_json)
                            st.session_state.task_result = result_data
                        except Exception:
                            st.session_state.task_result = {'payload': result_json}
                        st.rerun()

            if status not in ['SUCCESS', 'FAILURE', 'TIMEOUT', 'ZOMBIE']:
                with col1:
                    if st.button("🔄 召回", key=f"recover_{task_id[:8]}", use_container_width=True):
                        st.session_state.task_id = task_id
                        st.session_state.task_state = status
                        st.rerun()

            with col2:
                if st.button("🗑️", key=f"delete_{task_id[:8]}", use_container_width=True, help="删除此任务记录"):
                    if delete_task_from_history(task_id):
                        st.toast(f"✅ 已删除任务: {task_id[:12]}...")
                        st.rerun()
                    else:
                        st.error("删除失败")


def render_system_reset_panel():
    """系统重置面板 — 清理 Redis 缓存 & 解锁提交状态"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧹 系统维护")

    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("🔄 解锁提交", use_container_width=True, help="清除提交锁，解决「正在提交中」卡死"):
            st.session_state.submission_lock = False
            st.session_state.lock_holder_tab = None
            st.session_state.submit_cooldown_until = None
            st.session_state.task_id = None
            st.session_state.task_state = None
            st.session_state.task_progress = 0
            st.session_state.poll_attempt_count = 0
            st.toast("✅ 提交锁已解除")
            st.rerun()

    with col2:
        if st.button("🗑️ 清理Redis", use_container_width=True, help="清空 Redis 中的残留任务和队列"):
            try:
                import redis, os
                redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
                r = redis.from_url(redis_url, decode_responses=True)
                keys_before = r.keys('*')
                count = len(keys_before)
                if count > 0:
                    r.flushall()
                    st.toast(f"✅ 已清理 {count} 个 Redis key")
                else:
                    st.toast("✅ Redis 已为空，无需清理")
            except Exception as e:
                st.toast(f"❌ 清理失败: {str(e)[:50]}")
                st.error(f"Redis 清理失败: {e}")


__all__ = [
    'render_health_indicator',
    'render_sidebar_configurator',
    'render_task_history_sidebar',
    'render_system_reset_panel',
]
