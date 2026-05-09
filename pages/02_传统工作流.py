# -*- coding: utf-8 -*-
"""
传统 HITL 工作流 - 六步人工在回路假设生成向导

移植 CLI 的 run_workflow_hitl() 完整逻辑

作者: V8.1
日期: 2026-05-03
"""
import streamlit as st
from src.ui.page_base import setup_page, get_orchestrator

project_root = setup_page("传统工作流", "🔬")

# ==================== Session State ====================
def init_state():
    defaults = {
        'hitl_step': 1,
        'hitl_query': '',
        'hitl_session_id': '',
        'hitl_papers': [],
        'hitl_hypotheses': [],
        'hitl_selected_hypothesis': None,
        'hitl_validation': None,
        'hitl_loading': False,
        'hitl_error': '',
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

STEPS = [
    {"num": 1, "name": "研究方向", "icon": "🎯", "desc": "描述你的研究问题"},
    {"num": 2, "name": "文献检索", "icon": "🔍", "desc": "搜索相关论文"},
    {"num": 3, "name": "生成假设", "icon": "🧪", "desc": "首席科学家创建假设"},
    {"num": 4, "name": "人工选择", "icon": "👤", "desc": "审查并选择假设"},
    {"num": 5, "name": "深度验证", "icon": "🔬", "desc": "评审委员会评估"},
    {"num": 6, "name": "最终报告", "icon": "📊", "desc": "查看完整报告"},
]

# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown('<div class="sidebar-config-header">🔬 工作流向导</div>', unsafe_allow_html=True)

    for step in STEPS:
        num = step['num']
        if num < st.session_state.hitl_step:
            status = "✅"
        elif num == st.session_state.hitl_step:
            status = "▶️"
        else:
            status = "⚪"
        st.caption(f"{status} 步骤{num}: {step['name']}")

    st.divider()

    if st.button("🔄 重新开始", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith('hitl_'):
                del st.session_state[k]
        init_state()

    if st.session_state.hitl_step > 1:
        st.info(f"会话: {st.session_state.hitl_session_id[:8] if st.session_state.hitl_session_id else 'N/A'}")

# ==================== 主区域 ====================
st.markdown("""
<div class="v75-header">
    <h1>🔬 传统 HITL 工作流</h1>
    <div class="subtitle">六步人工在回路 · 从研究问题到验证假设</div>
</div>
""", unsafe_allow_html=True)

progress = (st.session_state.hitl_step - 1) / 5
st.progress(progress, text=f"步骤 {st.session_state.hitl_step}/6: {STEPS[st.session_state.hitl_step - 1]['name']}")
st.divider()

# ==================== 步骤 1 ====================
if st.session_state.hitl_step == 1:
    st.markdown("### 🎯 步骤 1: 确定研究方向")
    query = st.text_area("请输入你的研究方向或关键词:", height=100,
                          placeholder="例如: 利用单细胞转录组学识别阿尔茨海默病早期血液生物标记物",
                          key="hitl_query_input")

    if st.button("开始 →", type="primary", disabled=not query.strip()):
        st.session_state.hitl_query = query.strip()
        st.session_state.hitl_loading = True
        st.session_state.hitl_step = 2

# ==================== 步骤 2 ====================
elif st.session_state.hitl_step == 2:
    st.markdown("### 🔍 步骤 2: 文献检索")
    st.info(f"搜索主题: {st.session_state.hitl_query}")

    max_results = st.number_input("最大检索数", 5, 100, 20, 5, key="hitl_max_results")

    if st.button("🔍 开始检索", type="primary") or st.session_state.hitl_loading:
        st.session_state.hitl_loading = False
        with st.spinner("正在检索论文..."):
            try:
                orch = get_orchestrator()
                sid = orch.start_session(st.session_state.hitl_query)
                st.session_state.hitl_session_id = sid
                result = orch.search_papers(
                    st.session_state.hitl_query,
                    max_results=max_results,
                    enable_filter=False,
                    fetch_full_text=True,
                    max_full_text=5
                )
                papers = result.get('papers', [])
                st.session_state.hitl_papers = papers
                st.success(f"找到 {len(papers)} 篇论文")

                for i, p in enumerate(papers[:10]):
                    title = p.get('title', 'N/A')
                    year = p.get('year', '')
                    journal = p.get('journal', '')
                    with st.expander(f"{i+1}. {title} ({year})"):
                        st.caption(f"{journal}")
                        abstract = p.get('abstract', '')
                        if abstract:
                            st.write(str(abstract)[:400])

                st.session_state.hitl_step = 3
            except Exception as e:
                st.error(f"检索失败: {e}")
                st.session_state.hitl_step = 1

# ==================== 步骤 3 ====================
elif st.session_state.hitl_step == 3:
    st.markdown("### 🧪 步骤 3: 生成假设")
    st.caption(f"基于 {len(st.session_state.hitl_papers)} 篇论文生成假设")

    topic = st.text_input("确认/修改研究主题:", value=st.session_state.hitl_query)

    if st.button("🧪 生成假设", type="primary"):
        with st.spinner("首席科学家正在生成假设..."):
            try:
                orch = get_orchestrator()
                hypotheses = orch.generate_hypotheses(
                    st.session_state.hitl_papers,
                    research_field=topic
                )
                st.session_state.hitl_hypotheses = hypotheses if isinstance(hypotheses, list) else []
                st.session_state.hitl_step = 4
            except Exception as e:
                st.error(f"生成失败: {e}")
                st.session_state.hitl_step = 2

# ==================== 步骤 4 ====================
elif st.session_state.hitl_step == 4:
    st.markdown("### 👤 步骤 4: 人工在回路 - 审查假设")

    hyps = st.session_state.hitl_hypotheses
    if not hyps:
        st.warning("暂无假设可用")
    else:
        st.info(f"首席科学家提出了 {len(hyps)} 个假设，请审查后选择一个进入验证阶段。")

        for i, hyp in enumerate(hyps):
            title = hyp.get('title', f'假设 {i+1}')
            desc = hyp.get('description', '') or ''
            paradigm = hyp.get('paradigm_framework', '')
            score = hyp.get('pre_validation_score', hyp.get('science_score', 'N/A'))

            with st.container():
                st.markdown(f"### 假设 {i+1}: {title}")
                col1, col2 = st.columns([3, 1])
                col1.caption(f"范式: {paradigm or 'N/A'}")
                col2.metric("预评分", score)
                st.write(str(desc)[:300])

        st.divider()
        col_a, col_b = st.columns(2)
        choice = col_a.selectbox("选择一个假设:", ["1", "2", "3"][:len(hyps)], key="hitl_select")
        regenerate = col_b.button("🔄 不满意，重新生成", use_container_width=True)

        if regenerate:
            st.session_state.hitl_step = 3
            st.session_state.hitl_loading = True

        if st.button("✅ 确认选择，开始验证", type="primary"):
            idx = int(choice) - 1
            st.session_state.hitl_selected_hypothesis = hyps[idx]
            st.session_state.hitl_step = 5

# ==================== 步骤 5 ====================
elif st.session_state.hitl_step == 5:
    st.markdown("### 🔬 步骤 5: 深度验证")

    selected = st.session_state.hitl_selected_hypothesis
    if selected:
        st.info(f"正在验证: **{selected.get('title', '')}**")

        if not st.session_state.hitl_validation:
            with st.spinner("评审委员会正在深度评估..."):
                try:
                    orch = get_orchestrator()
                    validation = orch.validate_hypothesis(selected)
                    st.session_state.hitl_validation = validation
                except Exception as e:
                    st.error(f"验证失败: {e}")
                    st.session_state.hitl_step = 4

        validation = st.session_state.hitl_validation
        if validation:
            st.success("验证完成！")
            scores = validation.get('scores', {})
            cols = st.columns(3)
            cols[0].metric("🎯 影响力", f"{scores.get('impact', 0):.1f}/10")
            cols[1].metric("💡 原创性", f"{scores.get('originality', 0):.1f}/10")
            cols[2].metric("⚙️ 可行性", f"{scores.get('feasibility', 0):.1f}/10")

            decision = validation.get('decision', '')
            rationale = validation.get('rationale', '')
            if decision:
                st.info(f"**结论**: {decision}")
            if rationale:
                st.write(rationale)

            if st.button("📊 查看完整报告 →", type="primary"):
                st.session_state.hitl_step = 6

# ==================== 步骤 6 ====================
elif st.session_state.hitl_step == 6:
    st.markdown("### 📊 步骤 6: 最终报告")

    selected = st.session_state.hitl_selected_hypothesis
    validation = st.session_state.hitl_validation

    if selected and validation:
        st.markdown(f"## {selected.get('title', '假设报告')}")

        scores = validation.get('scores', {})
        score_data = {
            "维度": ["影响力", "原创性", "可行性"],
            "分数": [
                f"{scores.get('impact', 0):.1f}/10",
                f"{scores.get('originality', 0):.1f}/10",
                f"{scores.get('feasibility', 0):.1f}/10"
            ]
        }
        st.dataframe(score_data, use_container_width=True, hide_index=True)

        avg = sum(scores.values()) / len(scores) if scores else 0
        st.metric("综合平均分", f"{avg:.1f}/10")

        decision = validation.get('decision', '')
        color = "green" if "ACCEPT" in str(decision).upper() else ("orange" if "REVISE" in str(decision).upper() else "red")
        st.markdown(f"### 最终决定: :{color}[{decision}]")

        tabs = st.tabs(["影响力分析", "原创性分析", "可行性分析", "实现建议"])
        with tabs[0]:
            st.write(validation.get('impact_analysis', '暂无'))
        with tabs[1]:
            st.write(validation.get('originality_analysis', '暂无'))
        with tabs[2]:
            st.write(validation.get('feasibility_analysis', '暂无'))
        with tabs[3]:
            st.write(validation.get('implementation_notes', '暂无'))

        if st.button("📥 导出报告"):
            try:
                from src.utils.report_export import ReportExporter
                exporter = ReportExporter()
                report = {
                    "title": selected.get("title", ""),
                    "hypothesis_data": selected,
                    "validation_data": validation,
                }
                path = exporter.export_to_markdown(report)
                st.success(f"已导出到: {path}")
            except Exception as e:
                st.error(f"导出失败: {e}")

        if st.button("🔄 开始新工作流"):
            for k in list(st.session_state.keys()):
                if k.startswith('hitl_'):
                    del st.session_state[k]
            init_state()
