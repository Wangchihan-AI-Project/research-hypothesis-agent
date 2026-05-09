# -*- coding: utf-8 -*-
"""
V7.5 凤凰协议 UI 演化可视化组件

合并自 app.py 和原 phoenix_evolution_view.py，消除重复实现。
"""

import streamlit as st
from typing import Dict, List


# ==================== Promise Score 计算 ====================

def calculate_promise_score(version: Dict, phoenix_protocol: Dict) -> Dict:
    """计算 Promise Score"""
    science_score = version.get('science_score', 0)
    defense_passed = version.get('defense_passed', False)
    iteration = version.get('iteration', 1)

    innovation = min(10, science_score * 1.2 + (10 - iteration) * 0.1)
    red_attack_types = version.get('red_attack_types', [])
    resistance = max(3, 10 - len(red_attack_types) * 1.5 + (5 if defense_passed else 0))
    score_history = phoenix_protocol.get('score_evolution', [])
    if len(score_history) >= 2:
        score_trend = score_history[-1] - score_history[0]
        evidence = min(10, 5 + score_trend * 2 + (3 if defense_passed else 0))
    else:
        evidence = min(10, science_score * 0.8)
    total = innovation * 0.35 + resistance * 0.35 + evidence * 0.30

    return {
        'total': total,
        'innovation': innovation,
        'resistance': resistance,
        'evidence': evidence,
        'components': {
            '创新性': {'score': innovation, 'weight': 0.35, 'description': '基于 Science Score 和迭代位置'},
            '抗性': {'score': resistance, 'weight': 0.35, 'description': '基于红方攻击防御能力'},
            '实证度': {'score': evidence, 'weight': 0.30, 'description': '基于分数趋势和验证状态'},
        }
    }


# ==================== 版本演化图 ====================

def render_phoenix_evolution_graph(version_chain: List[Dict]):
    """凤凰协议版本演进图（丰富版）"""
    if not version_chain:
        st.info("暂无版本演进记录")
        return

    st.markdown("### 🧬 版本演进链")

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
        'initial': '📝', 'physical_fix': '⚡',
        'methodology_patch': '🧬', 'external_compensation': '📡',
        'major_rewrite': '🔄', 'final': '✅',
    }
    type_names = {
        'initial': '初始版本', 'physical_fix': '物理修正',
        'methodology_patch': '方法论补丁', 'external_compensation': '外部补偿',
        'major_rewrite': '重大重构', 'final': '最终版本',
    }

    max_score = max(v.get('science_score', 0) for v in version_chain)

    for i, version in enumerate(version_chain):
        v_type = version.get('type', 'initial')
        v_score = version.get('science_score', 0)
        v_passed = version.get('defense_passed', False)

        node_class = "success" if v_passed else v_type
        icon = type_icons.get(v_type, '🔄')
        type_name = type_names.get(v_type, v_type)

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

    evolution_html += "</div></div>"
    st.markdown(evolution_html, unsafe_allow_html=True)


# ==================== 版本详情卡片 ====================

def render_version_detail(version: Dict):
    """渲染版本详情卡片"""
    v_type = version.get('type', 'unknown')
    v_type_display = {
        'initial': '初始版本', 'physical_fix': '物理锚定重写',
        'methodology_patch': '方法论补丁', 'external_compensation': '外部算法补偿',
    }.get(v_type, v_type)

    card_class = {
        'initial': 'initial', 'physical-fix': 'physical-fix',
        'methodology-patch': 'methodology-patch',
        'external-compensation': 'external-compensation',
    }.get(v_type.replace('_', '-'), 'initial')

    st.markdown(f"""
    <div class="version-card {card_class}">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h3 style="margin: 0;">{version.get('version', 'v?.?')}</h3>
                <div style="color: #94a3b8; font-size: 0.9rem;">{v_type_display}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 1.5rem; font-weight: 700; color: #fbbf24;">
                    {version.get('science_score', 0):.2f}
                </div>
                <div style="font-size: 0.8rem; color: #94a3b8;">Science Score</div>
            </div>
        </div>
        <div style="margin-top: 1rem; font-size: 0.9rem; color: #94a3b8;">
            迭代轮次: {version.get('iteration', 0)} | 创建时间: {version.get('created_at', 'N/A')[:19]}
        </div>
        <div style="margin-top: 0.5rem;">
            状态: {'✅ 通过' if version.get('defense_passed') else '🔄 未通过'}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ==================== 版本滑块 ====================

def render_evolution_slider(version_chain: List[Dict]):
    """渲染版本滑块"""
    if not version_chain or len(version_chain) <= 1:
        return

    st.markdown("### 🔍 版本演化浏览器")
    versions = [v.get('version', f'v{i+1}.0') for i, v in enumerate(version_chain)]
    selected_idx = st.select_slider(
        "选择版本查看详情",
        options=range(len(versions)),
        format_func=lambda i: versions[i],
        value=len(versions) - 1,
        key='version_slider'
    )
    st.session_state.selected_version = version_chain[selected_idx]
    render_version_detail(version_chain[selected_idx])


# ==================== Promise Dashboard ====================

def render_promise_dashboard(promise_score: Dict):
    """渲染 Promise Score 仪表盘（3列布局版）"""
    st.markdown("### 📊 Promise Dashboard")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div class="promise-dashboard">
            <div style="color: #8b5cf6; font-weight: bold;">创新性</div>
            <div style="font-size: 2rem; font-weight: 700;">{promise_score['innovation']:.1f}</div>
            <div class="promise-bar">
                <div class="promise-bar-fill innovation" style="width: {promise_score['innovation'] * 10}%"></div>
            </div>
            <div style="font-size: 0.8rem; color: #94a3b8;">权重 35%</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="promise-dashboard">
            <div style="color: #10b981; font-weight: bold;">抗性</div>
            <div style="font-size: 2rem; font-weight: 700;">{promise_score['resistance']:.1f}</div>
            <div class="promise-bar">
                <div class="promise-bar-fill resistance" style="width: {promise_score['resistance'] * 10}%"></div>
            </div>
            <div style="font-size: 0.8rem; color: #94a3b8;">权重 35%</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="promise-dashboard">
            <div style="color: #f59e0b; font-weight: bold;">实证度</div>
            <div style="font-size: 2rem; font-weight: 700;">{promise_score['evidence']:.1f}</div>
            <div class="promise-bar">
                <div class="promise-bar-fill evidence" style="width: {promise_score['evidence'] * 10}%"></div>
            </div>
            <div style="font-size: 0.8rem; color: #94a3b8;">权重 30%</div>
        </div>
        """, unsafe_allow_html=True)


# ==================== 最佳候选方案 ====================

def render_top_candidate_badge(result: Dict):
    """渲染最佳准方案金色勋章"""
    payload = result.get('payload', {})
    phoenix_protocol = payload.get('phoenix_protocol', {})
    version_chain = phoenix_protocol.get('version_chain', [])

    if not version_chain:
        return

    top_version = max(version_chain, key=lambda v: v.get('science_score', 0), default=None)
    if not top_version:
        return

    top_score = top_version.get('science_score', 0)
    promise_score = calculate_promise_score(top_version, phoenix_protocol)

    st.markdown(f"""
    <div class="top-candidate-badge">
        <h3>🏆 最佳候选方案 (Top Candidate)</h3>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1rem;">
            <div>
                <div style="font-size: 0.9rem; opacity: 0.8;">版本</div>
                <div style="font-size: 1.2rem; font-weight: 700;">{top_version.get('version', 'v?.?')}</div>
            </div>
            <div>
                <div style="font-size: 0.9rem; opacity: 0.8;">Science Score</div>
                <div class="score">{top_score:.2f}</div>
            </div>
            <div>
                <div style="font-size: 0.9rem; opacity: 0.8;">Promise Score</div>
                <div class="score">{promise_score['total']:.2f}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_promise_dashboard(promise_score)


# ==================== 对抗溯源看板 ====================

def render_conflict_trace(result: Dict):
    """渲染对抗溯源看板"""
    payload = result.get('payload', {})
    phoenix_protocol = payload.get('phoenix_protocol', {})
    version_chain = phoenix_protocol.get('version_chain', [])

    if not version_chain:
        return

    st.markdown("### ⚔️ 对抗溯源看板")

    for version in version_chain:
        v_num = version.get('version', 'v?.?')

        red_attack_types = version.get('red_attack_types', [])
        if red_attack_types and red_attack_types != ['UNKNOWN']:
            st.markdown(f"""
            <div class="conflict-trace red-attack">
                <div style="font-weight: bold; color: #ef4444;">⚔️ 红方攻击 - {v_num}</div>
                <div style="margin-top: 0.5rem;">
            """, unsafe_allow_html=True)

            for attack_type in red_attack_types:
                attack_desc = {
                    'OVERFITTING': '过拟合 - 模型在训练集上表现过好，泛化能力差',
                    'LEAKAGE': '数据泄露 - 测试集信息意外进入训练过程',
                    'BIAS': '选择偏差 - 样本选择不当导致系统性偏差',
                    'VALIDATION': '验证不足 - 缺乏独立验证集或验证方法不当',
                    'PSEUDOSCIENCE': '伪科学 - 缺乏物理锚定或可测量手段',
                }.get(attack_type, attack_type)
                st.info(f"**{attack_type}**: {attack_desc}")

            st.markdown("</div></div>", unsafe_allow_html=True)

        patch_applied = version.get('patch_applied', False)
        if patch_applied:
            st.markdown(f"""
            <div class="conflict-trace blue-defense">
                <div style="font-weight: bold; color: #3b82f6;">🛡️ 蓝方补丁响应 - {v_num}</div>
                <div style="margin-top: 0.5rem; color: #10b981;">
                    ✓ 方法论补丁已注入
                </div>
            </div>
            """, unsafe_allow_html=True)


# ==================== 凤凰协议状态面板 ====================

def render_phoenix_status_panel(phoenix_protocol: Dict):
    """渲染演化协议状态面板"""
    st.markdown("### 🧪 演化执行统计")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总迭代", phoenix_protocol.get('total_iterations', 0))
    with col2:
        st.metric("物理重写", phoenix_protocol.get('rewrite_attempts', 0))
    with col3:
        st.metric("方法论补丁", phoenix_protocol.get('patch_attempts', 0))
    with col4:
        final_state = phoenix_protocol.get('final_state', 'UNKNOWN')
        state_icon = '✅' if final_state == 'SUCCESS' else '⏰'
        st.metric("最终状态", f"{state_icon} {final_state}")


# ==================== 分数趋势图 ====================

def render_score_trend_chart(score_history: List[float]):
    """渲染分数趋势图（含趋势分析）"""
    if not score_history or len(score_history) < 2:
        return

    st.markdown("### 📈 Science Score 趋势")
    st.line_chart({"分数": score_history})

    if len(score_history) >= 2:
        delta = score_history[-1] - score_history[0]
        if delta > 0.5:
            st.success(f"📈 趋势上升 (+{delta:.2f})")
        elif delta < -0.5:
            st.error(f"📉 趋势下降 ({delta:.2f})")
        else:
            st.warning(f"➡️ 趋势平稳 ({delta:+.2f})")


__all__ = [
    'calculate_promise_score',
    'render_phoenix_evolution_graph',
    'render_version_detail',
    'render_evolution_slider',
    'render_promise_dashboard',
    'render_top_candidate_badge',
    'render_conflict_trace',
    'render_phoenix_status_panel',
    'render_score_trend_chart',
]
