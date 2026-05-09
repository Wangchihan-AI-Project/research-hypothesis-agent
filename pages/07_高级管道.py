# -*- coding: utf-8 -*-
"""
高级分析管道 - 干实验瀑布 / 暗箱预审计 / 全局先验探测 / 反馈循环

暴露 Orchestrator 中已实现但在 UI 中从未被调用的高级管道

作者: V8.1
日期: 2026-05-03
"""
import streamlit as st
from src.ui.page_base import setup_page, get_orchestrator

project_root = setup_page("高级管道", "⚡")

# ==================== Session State ====================
def init_state():
    defaults = {
        'advpipe_input_data': None,
        'advpipe_results': {},
        'advpipe_running': False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

PIPELINES = {
    "dry_lab_waterfall": {
        "name": "干实验瀑布 (GAIA)",
        "icon": "🌊",
        "desc": "6步流程: GenAI → CompBio → DigitalPathology → Biostats → ResourceEstimator → ClinicalMD",
        "method": "run_dry_lab_waterfall",
        "agents": ["GenAI 架构师", "计算生物学专家", "数字病理学专家", "生物统计师", "资源评估师", "临床医学顾问"],
    },
    "dark_box_pre_audit": {
        "name": "暗箱预审计",
        "icon": "📦",
        "desc": "3方预评审: 全局先验探测 + 生物统计审计 + 红队攻击",
        "method": "run_dark_box_pre_audit",
        "agents": ["全局先验探测员", "生物统计审计师", "红队攻击手"],
    },
    "global_prior_art": {
        "name": "全局先验探测",
        "icon": "🌐",
        "desc": "跨数据库（PubMed + arXiv + Semantic Scholar）检索已有研究，评估新颖性",
        "method": "run_global_prior_art_probe",
        "agents": ["全球先验艺术探员"],
    },
    "feedback_loop": {
        "name": "递归反馈循环",
        "icon": "🔄",
        "desc": "带补救检索的递归反馈: 假设 → 审计 → 修复 → 再验证 → 收敛检测",
        "method": "run_feedback_loop",
        "agents": ["反馈控制器", "补救检索员", "收敛检测器"],
    },
    "data_governance": {
        "name": "数据治理审计",
        "icon": "🏛️",
        "desc": "数据质量管控检查: 数据来源、样本量、偏倚分析、隐私合规",
        "method": "run_data_governance_audit",
        "agents": ["数据治理审计师", "数据猎人"],
    },
}

# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown('<div class="sidebar-config-header">⚡ 高级管道</div>', unsafe_allow_html=True)
    st.caption("这些管道已在 Orchestrator 中实现，但之前未在 UI 中暴露")

    selected_pipeline = st.selectbox(
        "选择管道",
        list(PIPELINES.keys()),
        format_func=lambda x: f"{PIPELINES[x]['icon']} {PIPELINES[x]['name']}"
    )

    pipeline = PIPELINES[selected_pipeline]
    st.info(pipeline['desc'])
    st.caption("**参与 Agent:**")
    for agent in pipeline['agents']:
        st.caption(f"  • {agent}")

    st.divider()
    st.caption("⚠️ 高级管道可能耗时较长，部分操作会消耗 API 配额")

# ==================== 主区域 ====================
st.markdown(f"""
<div class="v75-header">
    <h1>{pipeline['icon']} {pipeline['name']}</h1>
    <div class="subtitle">{pipeline['desc']}</div>
</div>
""", unsafe_allow_html=True)

# 输入区域
st.markdown("### 📥 输入数据")

input_mode = st.radio("输入方式:", ["输入假设描述", "粘贴假设 JSON"], horizontal=True)

if input_mode == "输入假设描述":
    hypothesis_text = st.text_area(
        "假设描述",
        height=120,
        placeholder="描述你的假设，包括：标题、核心机制、预期效果、验证方法...",
        key="advpipe_text"
    )
    additional_context = st.text_area(
        "附加上下文（可选）",
        height=80,
        placeholder="相关文献、已知数据、约束条件...",
        key="advpipe_context"
    )
    if hypothesis_text.strip():
        st.session_state.advpipe_input_data = {
            "title": hypothesis_text.strip().split('\n')[0][:100],
            "description": hypothesis_text.strip(),
            "context": additional_context.strip() if additional_context.strip() else None,
        }
else:
    json_input = st.text_area(
        "假设 JSON",
        height=200,
        placeholder='{"title": "...", "description": "...", "rationale": "...", ...}',
        key="advpipe_json"
    )
    if json_input.strip():
        import json
        try:
            st.session_state.advpipe_input_data = json.loads(json_input)
            st.success("JSON 解析成功")
        except json.JSONDecodeError as e:
            st.error(f"JSON 解析错误: {e}")

# 执行按钮
can_run = st.session_state.advpipe_input_data is not None
if st.button(f"🚀 启动 {pipeline['name']}", type="primary", disabled=not can_run, use_container_width=True):
    st.session_state.advpipe_running = True
    st.rerun()

# 执行
if st.session_state.advpipe_running:
    with st.spinner(f"⏳ {pipeline['name']} 运行中...这可能需要几分钟"):
        try:
            orch = get_orchestrator()
            input_data = st.session_state.advpipe_input_data
            method_name = pipeline['method']

            if method_name == "run_dry_lab_waterfall":
                result = orch.run_dry_lab_waterfall(input_data)
            elif method_name == "run_dark_box_pre_audit":
                result = orch.run_dark_box_pre_audit(input_data)
            elif method_name == "run_global_prior_art_probe":
                result = orch.run_global_prior_art_probe(input_data)
            elif method_name == "run_feedback_loop":
                result = orch.run_feedback_loop(input_data)
            elif method_name == "run_data_governance_audit":
                result = orch.run_data_governance_audit(input_data)
            else:
                result = {"error": f"未知管道: {method_name}"}

            st.session_state.advpipe_results[selected_pipeline] = result
            st.session_state.advpipe_running = False

        except Exception as e:
            st.error(f"管道执行失败: {e}")
            import traceback
            st.code(traceback.format_exc())
            st.session_state.advpipe_running = False

# 结果展示
result = st.session_state.advpipe_results.get(selected_pipeline)
if result and not st.session_state.advpipe_running:
    st.markdown("---")
    st.markdown("## 📊 执行结果")

    if isinstance(result, dict) and result.get("error"):
        st.error(result["error"])
    else:
        # 根据管道类型展示不同内容
        if selected_pipeline == "dry_lab_waterfall":
            tabs = st.tabs(["GenAI", "CompBio", "DigitalPathology", "Biostats", "Resources", "Clinical"])
            agent_keys = ["genai", "compbio", "digital_pathology", "biostats", "resources", "clinical"]
            for tab, key in zip(tabs, agent_keys):
                with tab:
                    data = result.get(key, {}) if isinstance(result, dict) else {}
                    if data:
                        st.json(data)
                    else:
                        st.caption("暂无此阶段输出")

        elif selected_pipeline == "dark_box_pre_audit":
            cols = st.columns(3)
            with cols[0]:
                st.metric("全局先验探测", result.get('prior_art_status', 'N/A') if isinstance(result, dict) else 'N/A')
                st.write(result.get('prior_art', '') if isinstance(result, dict) else '')
            with cols[1]:
                st.metric("生物统计审计", result.get('biostats_status', 'N/A') if isinstance(result, dict) else 'N/A')
                st.write(result.get('biostats_audit', '') if isinstance(result, dict) else '')
            with cols[2]:
                st.metric("红队攻击", result.get('red_team_status', 'N/A') if isinstance(result, dict) else 'N/A')
                st.write(result.get('red_team', '') if isinstance(result, dict) else '')

        elif selected_pipeline == "global_prior_art":
            st.metric("新颖性评估", result.get('novelty_score', 'N/A') if isinstance(result, dict) else 'N/A')
            st.write(result.get('analysis', '') if isinstance(result, dict) else '')

        elif selected_pipeline == "feedback_loop":
            convergence = result.get('convergence', {}) if isinstance(result, dict) else {}
            st.metric("迭代次数", result.get('iterations', 'N/A') if isinstance(result, dict) else 'N/A')
            st.metric("收敛状态", convergence.get('status', 'N/A'))

        elif selected_pipeline == "data_governance":
            st.write(result.get('audit_report', '') if isinstance(result, dict) else '')

        # 通用：完整 JSON
        with st.expander("🔍 原始输出"):
            st.json(result)

    if st.button("🔄 清除结果"):
        st.session_state.advpipe_results = {}
        st.session_state.advpipe_input_data = None
        st.rerun()

# 空状态
if not result and not st.session_state.advpipe_running and not st.session_state.advpipe_input_data:
    st.markdown("""
    <div style="text-align:center; color:#64748b; padding:3rem 0;">
        <p style="font-size:1.2rem;">⚡ 高级分析管道</p>
        <p>这些管道实现了完整的学术审稿流程，每个管道调用多个专业 Agent</p>
        <p style="font-size:0.85rem;">
            🌊 干实验瀑布 &nbsp;|&nbsp;
            📦 暗箱预审计 &nbsp;|&nbsp;
            🌐 全局先验探测 &nbsp;|&nbsp;
            🔄 反馈循环 &nbsp;|&nbsp;
            🏛️ 数据治理
        </p>
        <p style="margin-top:1.5rem;">输入假设描述或 JSON 开始</p>
    </div>
    """, unsafe_allow_html=True)
