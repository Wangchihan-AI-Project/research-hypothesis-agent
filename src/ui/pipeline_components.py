# -*- coding: utf-8 -*-
"""
流水线可视化与轮询组件

从 app.py 提取，供主应用导入使用。
"""

import streamlit as st
from datetime import datetime
from typing import Dict, List, Optional


# 模块级默认值（由 app.py 在导入后设置）
PIPELINE_STEPS: List[Dict] = []
MAX_POLL_ATTEMPTS: int = 100


# 阶段描述映射 — 每个 step 对应的用户友好说明
STAGE_DESCRIPTIONS = {
    1: {'during': '正在分析输入内容，检测科学信号...', 'done': '输入验证通过'},
    2: {'during': '正在将任务派发到计算队列...', 'done': '任务已派发'},
    3: {'during': '正在初始化协议参数...', 'done': '协议初始化完成'},
    4: {'during': '正在调用 LLM 生成初始假设...', 'done': '初始假设已生成'},
    5: {'during': '正在验证物理可行性和实验可操作性...', 'done': '物理锚定校验通过'},
    6: {'during': '红方模拟攻击，检测逻辑漏洞...', 'done': '红方攻击完成'},
    7: {'during': '蓝方构建防御论证...', 'done': '蓝方答辩完成'},
    8: {'during': '正在分析分数演化趋势...', 'done': '趋势分析完成'},
    9: {'during': '正在根据物理约束重写假设...', 'done': '物理重写完成'},
    10: {'during': '正在注入方法论补丁...', 'done': '方法论补丁已注入'},
    11: {'during': '正在检索外部文献进行交叉验证...', 'done': '外部补偿完成'},
    12: {'during': '正在以补丁参数重新执行...', 'done': '补丁重试完成'},
    13: {'during': '演化完成，正在生成报告...', 'done': '报告生成完毕'},
}


def render_pipeline_visualizer():
    """V7.5 Pipeline 可视化 — 增强反馈版"""
    task_progress = st.session_state.get('task_progress', 0)
    task_state = st.session_state.get('task_state', 'PENDING')
    task_message = st.session_state.get('task_message', '')
    pipeline_logs = st.session_state.get('pipeline_logs', [])

    current_step_idx = max(1, min(13, task_progress // 8 + 1))
    stage = STAGE_DESCRIPTIONS.get(current_step_idx, {})
    stage_text = stage.get('during', '处理中...')

    # 顶部状态条
    st.markdown(f"""
    <div class="terminal-box">
        <div class="terminal-header">🔥 V7.5 Phoenix Pipeline Monitor</div>
        <div class="v7-progress-bar">
            <div class="v7-progress-fill" style="width: {task_progress}%"></div>
        </div>
        <div style="display:flex; justify-content:space-between; color:#94a3b8; font-size:0.75rem; margin-top:0.3rem;">
            <span>{task_progress}%</span>
            <span>Step {current_step_idx}/13</span>
        </div>
        <div class="pipeline-status-msg">
            <span class="pulse-dot"></span> {stage_text}
        </div>
        <div style="color:#fbbf24; font-size:0.8rem; margin-top:0.3rem;">
            📝 {task_message}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 紧凑步骤列表（只显示当前前后各2步）
    with st.expander("📋 查看全部步骤", expanded=False):
        start_idx = max(0, current_step_idx - 3)
        end_idx = min(len(PIPELINE_STEPS), current_step_idx + 2)
        for step in PIPELINE_STEPS[start_idx:end_idx]:
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
                {status_icon} {step['icon']} {step['name']}
            </div>
            """, unsafe_allow_html=True)


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


def render_safe_submit_button(
    user_input: str,
    config: Dict,
    init_submission_guard,
    check_submission_guard,
    acquire_submission_lock,
    submit_celery_task_with_safety,
    release_submission_lock,
    run_hypothesis_task_locally=None,
) -> Optional[str]:
    """安全提交按钮 — V7.5: Worker 离线时提供本地执行选项"""
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

    can_submit, reason = check_submission_guard(st.session_state, user_input)

    if not can_submit:
        st.button("🚀 开始研究", type="secondary", disabled=True, key='submit_disabled')
        st.warning(f"🔒 {reason}")
        return None

    col_btn, col_local = st.columns([2, 1])

    with col_btn:
        if st.button("🚀 提交到Worker", type="primary", key='submit_btn', use_container_width=True):
            if not user_input.strip():
                st.warning("⚠️ 请输入研究想法")
                return None

            acquire_submission_lock(st.session_state, user_input)

            try:
                task_id, dispatch_result = submit_celery_task_with_safety(user_input, config, session_state=st.session_state)

                for warning_msg in dispatch_result.get('warnings', []):
                    st.warning(f"⚠️ {warning_msg}")

                if task_id:
                    st.success(f"✅ 任务已派发: {task_id[:20]}...")
                    st.info("⏳ 正在异步执行，请稍候...")
                    st.session_state.poll_start_time = datetime.now().isoformat()
                    st.session_state.poll_attempt_count = 0
                    st.session_state.axiom_badge_state = 'waiting'
                    st.session_state.last_submit_input = user_input
                    return task_id
                elif dispatch_result.get('error_type') == 'WORKER_OFFLINE':
                    release_submission_lock(st.session_state)
                    st.warning("⚠️ Worker 离线，请使用右侧「本地执行」按钮")
                    return None
                else:
                    release_submission_lock(st.session_state)
                    for error_msg in dispatch_result.get('errors', []):
                        st.error(f"❌ {error_msg}")
                    if not dispatch_result.get('errors'):
                        st.error(f"❌ 投递失败: {dispatch_result.get('error_message', 'Unknown')}")
                    return None

            except Exception as e:
                release_submission_lock(st.session_state)
                st.error(f"❌ 提交异常: {str(e)}")
                return None

    with col_local:
        if st.button("⚡ 本地执行", type="secondary", key='local_btn', use_container_width=True,
                     help="不依赖 Worker，直接在浏览器中同步执行"):
            if not user_input.strip():
                st.warning("⚠️ 请输入研究想法")
                return None

            acquire_submission_lock(st.session_state, user_input)

            with st.spinner("正在本地执行（5-15分钟）..."):
                try:
                    # 获取 run_hypothesis_task_locally（由调用方传入）
                    if run_hypothesis_task_locally is None:
                        from src.core.celery_tasks_v75 import run_hypothesis_task_locally as _local_fn
                        run_hypothesis_task_locally = _local_fn

                    local_result = run_hypothesis_task_locally(user_input, config)

                    if local_result and local_result.get('state') == 'success':
                        st.session_state.task_result = local_result
                        st.session_state.task_state = 'SUCCESS'
                        st.session_state.task_id = f"local_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        st.session_state.last_submit_input = user_input
                        st.success("✅ 本地执行成功！")
                        st.rerun()
                    else:
                        st.session_state.task_result = local_result
                        st.session_state.task_state = 'FAILURE'
                        st.error(f"❌ 失败: {local_result.get('error', '未知')}")
                        st.rerun()
                except Exception as e:
                    release_submission_lock(st.session_state)
                    st.session_state.task_state = 'FAILURE'
                    st.error(f"❌ 异常: {str(e)}")
                    st.rerun()

    return None


__all__ = [
    'PIPELINE_STEPS',
    'MAX_POLL_ATTEMPTS',
    'STAGE_DESCRIPTIONS',
    'render_pipeline_visualizer',
    'render_poll_stats',
    'render_safe_submit_button',
]
