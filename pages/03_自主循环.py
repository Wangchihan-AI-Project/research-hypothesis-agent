# -*- coding: utf-8 -*-
"""
自主循环模式 - 自动迭代研究 + 实时监控

作者: V8.1
日期: 2026-05-03
"""
import time

import streamlit as st
from src.ui.page_base import setup_page, get_orchestrator

project_root = setup_page("自主循环", "🤖")

# ==================== Session State ====================
def init_state():
    defaults = {
        'auto_running': False,
        'auto_results': None,
        'auto_query': '',
        'auto_logs': [],
        'auto_config': None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown('<div class="sidebar-config-header">🤖 自主循环</div>', unsafe_allow_html=True)

    st.caption("基于程序化策略自动迭代研究")

    query = st.text_area("研究关键词", value=st.session_state.auto_query, height=80,
                          placeholder="例如: 基于深度学习的药物-靶点相互作用预测",
                          key="auto_query_input")

    with st.expander("⚙️ 参数配置"):
        target_score = st.slider("目标分数", 5.0, 9.5, 7.0, 0.5, key="auto_target")
        max_iterations = st.slider("最大迭代", 3, 30, 10, 1, key="auto_max_iter")
        time_budget = st.slider("时间预算(分钟)", 5, 120, 30, 5, key="auto_time")
        min_if = st.slider("最小 IF", 0.0, 20.0, 3.0, 0.5, key="auto_min_if")

    st.divider()

    if not st.session_state.auto_running:
        can_start = bool(query.strip())
        if st.button("🚀 启动自主循环", type="primary", use_container_width=True, disabled=not can_start):
            st.session_state.auto_query = query
            st.session_state.auto_running = True
            st.session_state.auto_logs = []
            st.rerun()
    else:
        st.warning("⏳ 正在运行中...")
        if st.button("⏹️ 停止", use_container_width=True):
            st.session_state.auto_running = False
            st.rerun()

    if st.button("🔄 重置", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith('auto_'):
                del st.session_state[k]
        init_state()
        st.rerun()

# ==================== 主区域 ====================
st.markdown("""
<div class="v75-header">
    <h1>🤖 自主循环模式</h1>
    <div class="subtitle">基于程序策略的自动化科研迭代 · 灵感来自 Karpathy 的 AutoResearch</div>
</div>
""", unsafe_allow_html=True)

# 运行状态
if st.session_state.auto_running and not st.session_state.auto_results:
    st.markdown("### ⚡ 自主循环运行中")

    config = {
        "target_score": st.session_state.get("auto_target", 7.0),
        "max_iterations": st.session_state.get("auto_max_iter", 10),
        "time_budget_minutes": st.session_state.get("auto_time", 30),
        "min_if": st.session_state.get("auto_min_if", 3.0),
    }

    progress_container = st.container()
    log_container = st.container()

    with st.spinner("🚀 自主循环运行中...这可能需要几分钟"):
        try:
            orch = get_orchestrator()

            with progress_container:
                st.info(f"查询: {st.session_state.auto_query}")
                st.json(config)

            logs = []
            for iteration in range(1, config["max_iterations"] + 1):
                logs.append(f"🔄 迭代 {iteration}/{config['max_iterations']}")
                with log_container:
                    for log in logs[-5:]:
                        st.caption(log)

                # 使用 orchestrator 的自主模式
                result = orch.run_autonomous_mode(
                    query=st.session_state.auto_query,
                    config=config
                )

                if result:
                    st.session_state.auto_results = result
                    st.session_state.auto_logs = logs
                    st.session_state.auto_running = False
                    break

                time.sleep(0.5)  # 防止过快的迭代

            # 如果循环结束仍未达标
            if not st.session_state.auto_results:
                st.warning("达到最大迭代次数，未满足目标分数")
                st.session_state.auto_running = False

        except Exception as e:
            st.error(f"运行失败: {e}")
            st.session_state.auto_running = False

# 结果展示
results = st.session_state.auto_results
if results:
    st.session_state.auto_running = False

    st.markdown("## 📊 自主循环结果")

    # 统计信息
    cols = st.columns(4)
    cols[0].metric("总迭代次数", results.get('total_iterations', results.get('iterations', 'N/A')))
    elapsed = results.get('elapsed_time', results.get('time_elapsed', 0))
    cols[1].metric("耗时(分钟)", f"{float(elapsed) if elapsed else 0:.1f}")
    cols[2].metric("最佳分数", f"{results.get('best_score', results.get('final_score', 0)):.1f}")
    cols[3].metric("论文数", results.get('paper_count', results.get('papers_found', 0)))

    # 最终假设
    hypotheses = results.get('hypotheses', results.get('final_hypotheses', []))
    if isinstance(hypotheses, list) and hypotheses:
        st.markdown("### 🧪 最终假设")
        for i, hyp in enumerate(hypotheses):
            title = hyp.get('title', f'假设 {i+1}')
            score = hyp.get('pre_validation_score', hyp.get('science_score', 'N/A'))
            desc = str(hyp.get('description', ''))[:200]
            with st.expander(f"{i+1}. {title} (评分: {score})"):
                st.write(desc)

    # 完整结果 JSON
    with st.expander("🔍 完整结果数据"):
        st.json({k: v for k, v in results.items()
                 if not isinstance(v, (list, dict)) or (isinstance(v, (list, dict)) and len(str(v)) < 5000)})

    if st.button("🔄 重新运行"):
        st.session_state.auto_results = None
        st.session_state.auto_logs = []
        st.rerun()

# 空状态
if not st.session_state.auto_running and not st.session_state.auto_results:
    st.markdown("""
    <div style="text-align:center; color:#64748b; padding:3rem 0;">
        <p style="font-size:1.2rem;">🤖 自主循环模式</p>
        <p>配置研究关键词和参数后，系统将自动迭代：</p>
        <p style="font-size:0.9rem;">
            搜索论文 → 生成假设 → 预验证 → 评分检查 → 自动调整 → 重试
        </p>
        <p style="font-size:0.85rem;">在左侧边���配置参数后启动</p>
    </div>
    """, unsafe_allow_html=True)
