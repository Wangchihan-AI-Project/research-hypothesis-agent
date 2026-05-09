# -*- coding: utf-8 -*-
"""
假设管理中心 - 浏览、查看详情、对比、导出已保存的假设

作者: V8.1
日期: 2026-05-03
"""
import streamlit as st
import pandas as pd

from src.ui.page_base import setup_page, get_orchestrator

project_root = setup_page("假设管理", "🧪")

# ==================== Session State ====================
def init_state():
    defaults = {
        'hypmgr_sessions': [],
        'hypmgr_selected_session': None,
        'hypmgr_selected_hypothesis': None,
        'hypmgr_compare_list': [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ==================== 数据加载 ====================
def load_sessions():
    try:
        orch = get_orchestrator()
        sessions = orch.list_recent_sessions(20)
        st.session_state.hypmgr_sessions = sessions or []
    except Exception as e:
        st.error(f"加载会话失败: {e}")
        st.session_state.hypmgr_sessions = []

def load_hypothesis_detail(hypothesis_id):
    try:
        orch = get_orchestrator()
        report = orch.get_full_report(hypothesis_id)
        return report
    except Exception as e:
        return {"error": str(e)}

# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown('<div class="sidebar-config-header">🧪 假设管理</div>', unsafe_allow_html=True)

    if st.button("🔄 刷新列表", use_container_width=True):
        load_sessions()
        st.rerun()

    st.divider()

    # 对比列表
    compare = st.session_state.hypmgr_compare_list
    if compare:
        st.caption(f"📊 对比列表 ({len(compare)} 个)")
        for cid in compare:
            st.caption(f"• ID: {cid}")
        if st.button("清空对比", use_container_width=True):
            st.session_state.hypmgr_compare_list = []
            st.rerun()

# ==================== 主区域 ====================
st.markdown("""
<div class="v75-header">
    <h1>🧪 假设管理中心</h1>
    <div class="subtitle">浏览 · 详情 · 对比 · 导出</div>
</div>
""", unsafe_allow_html=True)

# 加载数据
if not st.session_state.hypmgr_sessions:
    load_sessions()

sessions = st.session_state.hypmgr_sessions

if not sessions:
    st.info("暂无已保存的假设。去首页提交研究任务，或使用「智能对话」生成假设。")
    st.stop()

# 构建表格数据
rows = []
for s in sessions:
    rows.append({
        "会话 ID": str(s.get('id', ''))[:8],
        "查询主题": (s.get('query', '') or '')[:60],
        "时间": str(s.get('created_at', ''))[:19],
        "状态": s.get('status', ''),
        "论文数": s.get('papers_found', 0),
        "假设数": s.get('hypotheses_generated', 0),
    })

df = pd.DataFrame(rows)

# 选择操作模式
tab1, tab2, tab3 = st.tabs(["📋 会话列表", "🔍 假设详情", "📊 假设对比"])

with tab1:
    st.dataframe(df, use_container_width=True, hide_index=True,
                 column_config={
                     "会话 ID": st.column_config.TextColumn(width="small"),
                     "查询主题": st.column_config.TextColumn(width="large"),
                     "时间": st.column_config.TextColumn(width="medium"),
                 })

    # 查看详情
    st.divider()
    selected_id = st.text_input("输入会话或假设 ID 查看详情:", key="detail_id_input")
    if selected_id and st.button("查看详情"):
        try:
            hyp_id = int(selected_id)
            report = load_hypothesis_detail(hyp_id)
            if report:
                st.session_state.hypmgr_selected_hypothesis = report
                st.rerun()
            else:
                st.warning(f"未找到 ID: {hyp_id}")
        except ValueError:
            st.warning("请输入有效的数字 ID")

with tab2:
    report = st.session_state.hypmgr_selected_hypothesis
    if report:
        if isinstance(report, dict) and report.get("error"):
            st.error(report["error"])
        else:
            title = report.get('title', report.get('hypothesis_title', '未命名'))
            domain = report.get('domain', '')
            score = report.get('science_score', report.get('final_score', 'N/A'))
            version = report.get('version', '')

            st.markdown(f"## {title}")
            st.caption(f"领域: {domain} | 版本: {version} | 评分: {score}")

            # 方法论
            methodology = report.get('methodology', report.get('core_hypothesis', ''))
            if methodology:
                with st.expander("核心假设"):
                    st.write(methodology)

            # 创新分析
            innovation = report.get('innovation_analysis', report.get('innovation', {}))
            if innovation:
                with st.expander("创新分析"):
                    if isinstance(innovation, dict):
                        st.json(innovation)
                    else:
                        st.write(innovation)

            # 前沿分析
            frontier = report.get('frontier_analysis', report.get('frontier', {}))
            if frontier:
                with st.expander("前沿分析"):
                    if isinstance(frontier, dict):
                        st.json(frontier)
                    else:
                        st.write(frontier)

            # 实现路线
            roadmap = report.get('implementation_roadmap', report.get('roadmap', {}))
            if roadmap:
                with st.expander("实现路线图"):
                    if isinstance(roadmap, dict):
                        st.json(roadmap)
                    else:
                        st.write(roadmap)

            # 导出
            st.divider()
            if st.button("📥 导出为 Markdown", key="export_detail"):
                try:
                    from src.utils.report_export import ReportExporter
                    exporter = ReportExporter()
                    path = exporter.export_to_markdown(report)
                    st.success(f"已导出到: {path}")
                except Exception as e:
                    st.error(f"导出失败: {e}")

            # 加入对比
            hyp_id = report.get('id', report.get('hypothesis_id', ''))
            if hyp_id:
                if st.button("📊 加入对比列表"):
                    compare = st.session_state.hypmgr_compare_list
                    if hyp_id not in compare:
                        compare.append(hyp_id)
                        st.session_state.hypmgr_compare_list = compare
                        st.success(f"已将 ID {hyp_id} 加入对比")
                        st.rerun()
    else:
        st.info("在「会话列表」中输入 ID 查看详情，或在下方直接输入")

with tab3:
    compare_list = st.session_state.hypmgr_compare_list
    if len(compare_list) < 2:
        st.info("请至少添加 2 个假设到对比列表（在「假设详情」中点击「加入对比列表」）")
    else:
        st.markdown(f"### 对比 {len(compare_list)} 个假设")
        reports = []
        for hid in compare_list:
            r = load_hypothesis_detail(hid)
            if r:
                reports.append(r)

        if reports:
            # 关键指标对比表
            compare_rows = []
            for r in reports:
                compare_rows.append({
                    "ID": r.get('id', r.get('hypothesis_id', '')),
                    "标题": (r.get('title', r.get('hypothesis_title', '')) or '')[:40],
                    "评分": r.get('science_score', r.get('final_score', 'N/A')),
                    "领域": r.get('domain', ''),
                    "版本": r.get('version', ''),
                })
            st.dataframe(pd.DataFrame(compare_rows), use_container_width=True, hide_index=True)

            # 并列展示
            cols = st.columns(len(reports))
            for i, (col, r) in enumerate(zip(cols, reports)):
                with col:
                    st.markdown(f"**假设 {i+1}**")
                    st.caption(f"评分: {r.get('science_score', 'N/A')}")
                    method = r.get('methodology', r.get('core_hypothesis', ''))
                    if method:
                        st.markdown(str(method)[:300])
