# -*- coding: utf-8 -*-
"""
Meta Harness 评估 - 多候选方案 A/B 对比测试框架

作者: V8.1
日期: 2026-05-03
"""
import streamlit as st
from src.ui.page_base import setup_page

project_root = setup_page("Meta 评估", "🧪")

# ==================== Session State ====================
def init_state():
    defaults = {
        'metaeval_tasks': [],
        'metaeval_running': False,
        'metaeval_results': None,
        'metaeval_selected_task': None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ==================== 加载任务集 ====================
def load_task_sets():
    try:
        from src.meta_harness.task_sets import load_task_set, list_task_sets
        tasks = list_task_sets()
        return tasks
    except ImportError:
        return []
    except Exception as e:
        st.error(f"加载任务集失败: {e}")
        return []

# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown('<div class="sidebar-config-header">🧪 Meta 评估</div>', unsafe_allow_html=True)
    st.caption("多候选方案 A/B 对比测试")

    st.divider()
    st.markdown("### 候选方案配置")

    st.markdown("**方案 A (Baseline)**")
    candidate_a_model = st.selectbox("模型 A", ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"], key="meta_model_a")
    candidate_a_temp = st.slider("温度 A", 0.0, 1.0, 0.3, 0.1, key="meta_temp_a")

    st.markdown("**方案 B (Experiment)**")
    candidate_b_model = st.selectbox("模型 B", ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"], key="meta_model_b")
    candidate_b_temp = st.slider("温度 B", 0.0, 1.0, 0.7, 0.1, key="meta_temp_b")

    st.divider()
    st.caption("评估维度:")
    st.caption("• 科学严谨性")
    st.caption("• 创新性")
    st.caption("• 可行性")
    st.caption("• 可读性")

# ==================== 主区域 ====================
st.markdown("""
<div class="v75-header">
    <h1>🧪 Meta Harness 评估</h1>
    <div class="subtitle">多候选方案 A/B 对比 · 多维度评分框架</div>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🚀 运行评估", "📊 历史结果", "📋 任务集管理"])

with tab1:
    st.markdown("### 🚀 运行 A/B 评估")

    # 加载任务集
    task_sets = load_task_sets()
    if task_sets:
        task_options = [t.get('name', t) if isinstance(t, dict) else t for t in task_sets]
        selected_task = st.selectbox("选择任务集", task_options, key="meta_task_select")
    else:
        selected_task = None
        st.warning("未找到预设任务集，可以手动输入测试查询")

    manual_query = st.text_area("或手动输入测试查询:", height=80,
                                 placeholder="描述一个科研问题用于评估...",
                                 key="meta_manual_query")

    test_query = manual_query.strip() or selected_task or ""
    can_run = bool(test_query) and not st.session_state.metaeval_running

    if st.button("🧪 启动 A/B 评估", type="primary", disabled=not can_run, use_container_width=True):
        st.session_state.metaeval_running = True
        st.rerun()

    if st.session_state.metaeval_running:
        st.markdown("---")
        st.markdown("### ⚡ 评估进行中...")

        with st.spinner("正在运行方案 A 和方案 B..."):

            # 模拟 A/B 对比流程
            results = {
                "task": test_query,
                "candidate_a": {
                    "model": st.session_state.get("meta_model_a", "claude-sonnet-4-6"),
                    "temperature": st.session_state.get("meta_temp_a", 0.3),
                },
                "candidate_b": {
                    "model": st.session_state.get("meta_model_b", "claude-opus-4-6"),
                    "temperature": st.session_state.get("meta_temp_b", 0.7),
                },
                "status": "info",
                "message": "Meta Harness 评估模块当前为预览模式。\n\n完整评估需要启动 Celery Worker 并调用 run_eval.py。",
            }

            # 尝试实际运行
            try:
                from src.meta_harness.run_eval import run_evaluation
                from src.meta_harness.task_sets import load_task_set

                task_data = None
                if selected_task:
                    task_data = load_task_set(selected_task)

                result = run_evaluation(
                    task_set=task_data or {"query": test_query},
                    candidates=[
                        results["candidate_a"],
                        results["candidate_b"],
                    ]
                )
                if result:
                    results.update(result)
                    results["status"] = "success"
            except ImportError as e:
                results["status"] = "warning"
                results["message"] += f"\n\n导入错误: {e}"
            except Exception as e:
                results["status"] = "error"
                results["message"] += f"\n\n运行错误: {e}"

            st.session_state.metaeval_results = results
            st.session_state.metaeval_running = False
            st.rerun()

    # 显示结果
    results = st.session_state.metaeval_results
    if results and not st.session_state.metaeval_running:
        st.markdown("---")
        st.markdown("### 📊 评估结果")

        status = results.get("status", "info")
        if status == "success":
            st.success("评估完成！")
        elif status == "error":
            st.error("评估出错")
        elif status == "warning":
            st.warning("评估部分成功")

        if results.get("message"):
            st.info(results["message"])

        # A/B 对比卡片
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 🔵 方案 A (Baseline)")
            st.caption(f"模型: {results.get('candidate_a', {}).get('model', 'N/A')}")
            st.caption(f"温度: {results.get('candidate_a', {}).get('temperature', 'N/A')}")
            a_scores = results.get('scores_a', results.get('candidate_a', {}).get('scores', {}))
            if a_scores:
                for dim, score in a_scores.items():
                    st.metric(dim, f"{score:.1f}" if isinstance(score, (int, float)) else score)

        with col_b:
            st.markdown("#### 🟣 方案 B (Experiment)")
            st.caption(f"模型: {results.get('candidate_b', {}).get('model', 'N/A')}")
            st.caption(f"温度: {results.get('candidate_b', {}).get('temperature', 'N/A')}")
            b_scores = results.get('scores_b', results.get('candidate_b', {}).get('scores', {}))
            if b_scores:
                for dim, score in b_scores.items():
                    st.metric(dim, f"{score:.1f}" if isinstance(score, (int, float)) else score)

        if st.button("🔄 清除结果"):
            st.session_state.metaeval_results = None
            st.rerun()

with tab2:
    st.markdown("### 📊 历史评估结果")

    # 尝试读取 meta_harness_runs 目录
    runs_dir = project_root / 'meta_harness_runs'
    if runs_dir.exists():
        run_files = list(runs_dir.glob("*.json"))
        if run_files:
            for rf in sorted(run_files, reverse=True)[:10]:
                st.caption(f"📄 {rf.name}")
        else:
            st.info("暂无历史评估记录")
    else:
        st.info("meta_harness_runs/ 目录不存在，运行评估后会自动创建")

with tab3:
    st.markdown("### 📋 任务集管理")

    st.caption("任务集定义了评估使用的测试用例。查看 `src/meta_harness/task_sets.py` 了解详情。")

    try:
        from src.meta_harness.task_sets import list_task_sets, load_task_set
        tasks = list_task_sets()

        if tasks:
            for task_name in tasks:
                with st.expander(f"📋 {task_name}"):
                    try:
                        task_data = load_task_set(task_name)
                        st.json(task_data)
                    except Exception:
                        st.write(task_name)
        else:
            st.info("未找到任务集定义")
    except ImportError:
        st.warning("Meta Harness 模块不可用")
    except Exception as e:
        st.error(f"加载失败: {e}")
