# -*- coding: utf-8 -*-
"""
V7.5 凤凰协议 UI 演化可视化组件

核心功能：
1. 版本演进图渲染
2. Promise Score 仪表盘渲染
3. 分数趋势图渲染

作者: V7.5 架构工程师
日期: 2026-04-19
"""

import streamlit as st
from typing import Dict, List, Optional


def render_phoenix_evolution_graph(version_chain: List[Dict]):
    """
    凤凰协议版本演进图

    Args:
        version_chain: 版本演进链列表
            [
                {
                    'version': 'v1.0',
                    'type': 'initial',
                    'science_score': 6.5,
                    'defense_passed': False,
                    'iteration': 1,
                },
                {
                    'version': 'v1.1',
                    'type': 'physical_fix',
                    'science_score': 7.2,
                    ...
                },
                ...
            ]
    """
    if not version_chain:
        st.info("暂无版本演进记录")
        return

    st.markdown("### 🔥 凤凰协议 - 假设演化路径")

    # 构建演进图
    evolution_html = """
    <style>
        .evolution-container {
            background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
            border-radius: 12px;
            padding: 1.5rem;
            margin-top: 1rem;
        }
        .version-node {
            display: inline-block;
            width: 120px;
            text-align: center;
            margin: 0 8px;
            padding: 12px 8px;
            border-radius: 8px;
            vertical-align: top;
        }
        .version-node.initial { background: #334155; border: 1px solid #64748b; }
        .version-node.physical_fix { background: #7c3aed; border: 1px solid #a78bfa; }
        .version-node.methodology_patch { background: #0891b2; border: 1px solid #22d3ee; }
        .version-node.external_compensation { background: #f59e0b; border: 1px solid #fbbf24; }
        .version-node.success { background: #059669; border: 2px solid #10b981; }
        .version-arrow { color: #60a5fa; font-size: 1.5rem; margin: 0 3px; }
        .score-bar { height: 4px; background: #334155; border-radius: 2px; margin-top: 8px; }
        .score-fill { height: 100%; border-radius: 2px; }
        .version-title { color: #e2e8f0; font-weight: bold; font-size: 14px; }
        .version-score { color: #94a3b8; font-size: 12px; }
        .version-type { color: #64748b; font-size: 11px; margin-top: 4px; }
    </style>
    <div class="evolution-container">
        <div style="display: flex; align-items: center; justify-content: center; flex-wrap: wrap;">
    """

    type_icons = {
        'initial': '📝',
        'physical_fix': '⚡',
        'methodology_patch': '🧬',
        'external_compensation': '📡',
        'major_rewrite': '🔄',
        'final': '✅',
    }

    type_names = {
        'initial': '初始版本',
        'physical_fix': '物理修正',
        'methodology_patch': '方法论补丁',
        'external_compensation': '外部补偿',
        'major_rewrite': '重大重构',
        'final': '最终版本',
    }

    max_score = max(v.get('science_score', 0) for v in version_chain)

    for i, version in enumerate(version_chain):
        v_type = version.get('type', 'initial')
        v_score = version.get('science_score', 0)
        v_passed = version.get('defense_passed', False)

        # 确定样式
        if v_passed:
            node_class = "success"
        else:
            node_class = v_type

        icon = type_icons.get(v_type, '🔄')
        type_name = type_names.get(v_type, v_type)

        # 分数条颜色
        if v_passed:
            fill_color = "#10b981"
        elif v_score >= 7.0:
            fill_color = "#3b82f6"
        elif v_score >= 5.0:
            fill_color = "#f59e0b"
        else:
            fill_color = "#ef4444"

        fill_width = int((v_score / max(max_score, 10)) * 100)

        evolution_html += f"""
        <div class="version-node {node_class}">
            <span style="font-size: 1.2rem;">{icon}</span>
            <div class="version-title">{version.get('version', 'v?.?')}</div>
            <div class="version-score">Score: {v_score:.1f}</div>
            <div class="version-type">{type_name}</div>
            <div class="score-bar">
                <div class="score-fill" style="width: {fill_width}%; background: {fill_color};"></div>
            </div>
        </div>
        """

        if i < len(version_chain) - 1:
            evolution_html += '<span class="version-arrow">→</span>'

    evolution_html += """
        </div>
    </div>
    """

    st.markdown(evolution_html, unsafe_allow_html=True)


def render_promise_score_dashboard(promise_score: Dict):
    """
    Promise Score 仪表盘

    Args:
        promise_score: Promise Score 结果字典
            {
                'total_score': 8.5,
                'components': {
                    'innovation': {'score': 8.0, 'weight': 0.30, 'description': '创新性'},
                    'feasibility': {'score': 9.0, 'weight': 0.35, 'description': '可行性'},
                    ...
                },
                'trend': 'rising',
                'evolution_delta': 1.5,
                'grade': 'good',
                'recommendation': '...'
            }
    """
    if not promise_score:
        st.info("暂无 Promise Score 数据")
        return

    st.markdown("### 📊 Promise Score 仪表盘")

    total = promise_score.get('total_score', 0)
    grade = promise_score.get('grade', 'ungraded')
    trend = promise_score.get('trend', 'unknown')
    delta = promise_score.get('evolution_delta', 0)
    components = promise_score.get('components', {})
    recommendation = promise_score.get('recommendation', '')

    # 评级图标
    grade_icons = {
        'excellent': '🌟',
        'good': '✨',
        'acceptable': '📊',
        'poor': '⚠️',
        'very_poor': '❌',
    }

    # 趋势图标
    trend_icons = {
        'strong_rising': '📈',
        'rising': '↗️',
        'stable_rising': '➡️',
        'stagnant': '📊',
        'declining': '📉',
    }

    grade_icon = grade_icons.get(grade, '📊')
    trend_icon = trend_icons.get(trend, '➡️')

    # 仪表盘 HTML
    dashboard_html = f"""
    <style>
        .promise-dashboard {{
            background: #1e293b;
            border-radius: 12px;
            padding: 1.5rem;
            margin-top: 1rem;
        }}
        .score-gauge {{
            width: 180px;
            height: 180px;
            border-radius: 50%;
            margin: 0 auto;
            position: relative;
        }}
        .score-center {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 120px;
            height: 120px;
            background: #0f172a;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
        }}
        .component-bar {{
            height: 8px;
            background: #334155;
            border-radius: 4px;
            margin-top: 4px;
        }}
        .component-fill {{
            height: 100%;
            border-radius: 4px;
        }}
    </style>
    """

    # 圆形仪表盘角度计算
    success_angle = int(total * 36)  # 10分 = 360度

    dashboard_html += f"""
    <div class="promise-dashboard">
        <div style="text-align: center;">
            <div class="score-gauge" style="background: conic-gradient(#10b981 0deg {success_angle}deg, #334155 {success_angle}deg 360deg);">
                <div class="score-center">
                    <span style="font-size: 2rem; color: #10b981; font-weight: bold;">{total:.1f}</span>
                    <span style="color: #94a3b8; font-size: 12px;">总分</span>
                </div>
            </div>
        </div>

        <div style="margin-top: 1rem; text-align: center;">
            <span style="color: #e2e8f0;">{grade_icon} 评级: {grade}</span>
            <span style="color: #94a3b8; margin-left: 1rem;">{trend_icon} 趋势: {trend}</span>
            <span style="color: #60a5fa; margin-left: 1rem;">演化增量: +{delta:.1f}</span>
        </div>
    """

    # 四维度条形图
    if components:
        dashboard_html += """
        <div style="margin-top: 1.5rem; display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
        """

        bar_colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6']

        for i, (comp_name, comp_data) in enumerate(components.items()):
            comp_score = comp_data.get('score', 0)
            comp_desc = comp_data.get('description', comp_name)
            bar_width = int(comp_score * 10)
            bar_color = bar_colors[i % len(bar_colors)]

            dashboard_html += f"""
            <div>
                <span style="color: #94a3b8; font-size: 12px;">{comp_desc}</span>
                <div class="component-bar">
                    <div class="component-fill" style="width: {bar_width}%; background: {bar_color};"></div>
                </div>
                <span style="color: #e2e8f0; font-size: 11px;">{comp_score:.1f} (权重: {comp_data.get('weight', 0):.0%})</span>
            </div>
            """

        dashboard_html += """
        </div>
        """

    # 推荐建议
    if recommendation:
        dashboard_html += f"""
        <div style="margin-top: 1rem; padding: 10px; background: #334155; border-radius: 8px;">
            <span style="color: #60a5fa; font-size: 13px;">💡 推荐: {recommendation}</span>
        </div>
        """

    dashboard_html += """
    </div>
    """

    st.markdown(dashboard_html, unsafe_allow_html=True)


def render_score_trend_chart(score_history: List[float]):
    """
    分数趋势图

    Args:
        score_history: 分数历史列表
    """
    if not score_history or len(score_history) < 2:
        st.info("分数历史数据不足，无法绘制趋势图")
        return

    st.markdown("### 📈 Science Score 趋势图")

    # 使用 Streamlit 内置图表
    import pandas as pd

    df = pd.DataFrame({
        '迭代次数': range(1, len(score_history) + 1),
        'Science Score': score_history
    })

    st.line_chart(df.set_index('迭代次数'))


def render_phoenix_status_panel(phoenix_protocol: Dict):
    """
    凤凰协议状态面板

    Args:
        phoenix_protocol: 凤凰协议状态字典
    """
    if not phoenix_protocol:
        return

    st.markdown("### 🔥 凤凰协议状态")

    enabled = phoenix_protocol.get('enabled', False)
    rewrite_triggered = phoenix_protocol.get('rewrite_triggered', False)
    compensation_triggered = phoenix_protocol.get('external_compensation_triggered', False)
    total_iterations = phoenix_protocol.get('total_iterations', 0)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        status = "✅ 启用" if enabled else "❌ 禁用"
        st.metric("凤凰协议", status)

    with col2:
        rewrite_status = "🔥 触发" if rewrite_triggered else "➡️ 未触发"
        st.metric("物理重写", rewrite_status)

    with col3:
        comp_status = "📡 触发" if compensation_triggered else "➡️ 未触发"
        st.metric("外部补偿", comp_status)

    with col4:
        st.metric("总迭代次数", total_iterations)


# ==================== 导出 ====================

__all__ = [
    'render_phoenix_evolution_graph',
    'render_promise_score_dashboard',
    'render_score_trend_chart',
    'render_phoenix_status_panel',
]