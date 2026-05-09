# -*- coding: utf-8 -*-
"""
共享 CSS 样式表 - 从 app.py 提取，供所有页面使用

使用方式：
    from src.ui.styles import inject_shared_css
    inject_shared_css()
"""

import streamlit as st

SHARED_CSS = """
<style>
    /* 主标题（完整版） */
    .v75-header {
        background: linear-gradient(135deg, #1a0a0a 0%, #4a0404 50%, #1a0a0a 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        border: 1px solid #f59e0b;
        margin-bottom: 1.5rem;
        box-shadow: 0 0 20px rgba(245, 158, 11, 0.3);
    }
    .v75-header h1 {
        color: #fbbf24;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: 0.05em;
        text-shadow: 0 0 10px rgba(245, 158, 11, 0.5);
    }
    .v75-header .subtitle {
        color: #fcd34d;
        font-size: 0.9rem;
        margin-top: 0.5rem;
    }

    /* 紧凑标题 */
    .v75-header-compact {
        background: linear-gradient(135deg, #1a0a0a 0%, #3a0303 50%, #1a0a0a 100%);
        padding: 0.8rem 1.5rem;
        border-radius: 8px;
        border: 1px solid #f59e0b;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .v75-header-compact h1 {
        color: #fbbf24;
        font-size: 1.3rem;
        font-weight: 700;
        margin: 0;
    }
    .v75-header-compact .header-version {
        color: #f59e0b;
        font-size: 0.7rem;
        background: #1a0a0a;
        padding: 2px 8px;
        border-radius: 4px;
        border: 1px solid #f59e0b55;
        vertical-align: middle;
        margin-left: 0.5rem;
    }
    .v75-header-compact .subtitle {
        color: #fcd34d;
        font-size: 0.75rem;
        margin-top: 0.2rem;
    }

    /* 摘要卡片 */
    .summary-card {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #f59e0b;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
    }
    .summary-card h2 {
        color: #fbbf24;
        font-size: 1.1rem;
        margin: 0 0 0.8rem 0;
    }
    .summary-metrics {
        display: flex;
        gap: 1.5rem;
        flex-wrap: wrap;
    }
    .summary-metric {
        text-align: center;
        min-width: 80px;
    }
    .summary-metric .value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #fbbf24;
    }
    .summary-metric .label {
        font-size: 0.7rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .summary-metric .value.green { color: #10b981; }
    .summary-metric .value.amber { color: #f59e0b; }
    .summary-metric .value.red { color: #ef4444; }

    /* 页面导航卡片 */
    .page-guide {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 0.8rem;
        margin-bottom: 0.5rem;
    }
    .page-guide .title {
        color: #fbbf24;
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .page-guide .page-item {
        color: #94a3b8;
        font-size: 0.75rem;
        padding: 0.15rem 0;
    }
    .page-guide .page-item .icon { margin-right: 0.3rem; }
    .page-guide .page-item .desc { color: #64748b; }

    /* 终端风格进度框 */
    .terminal-box {
        background: #0f172a;
        border: 1px solid #f59e0b;
        border-radius: 8px;
        padding: 1rem;
        font-family: 'Courier New', monospace;
        color: #fbbf24;
        overflow-x: auto;
        max-height: 400px;
    }
    .terminal-header {
        color: #f59e0b;
        font-weight: bold;
        margin-bottom: 0.5rem;
        border-bottom: 1px solid #334155;
        padding-bottom: 0.5rem;
    }
    .terminal-line {
        margin: 0.2rem 0;
        font-size: 0.85rem;
    }
    .terminal-step-active {
        color: #fbbf24;
        font-weight: bold;
    }
    .terminal-step-complete {
        color: #10b981;
    }
    .terminal-step-pending {
        color: #64748b;
    }
    .terminal-step-error {
        color: #ef4444;
        font-weight: bold;
    }

    /* 状态卡片 */
    .status-card {
        background: #1e293b;
        border-radius: 8px;
        padding: 1rem;
        border: 1px solid #334155;
        margin-bottom: 0.5rem;
    }
    .status-card.success {
        border-color: #10b981;
        background: #064e3b;
    }
    .status-card.error {
        border-color: #ef4444;
        background: #7f1d1d;
    }
    .status-card.warning {
        border-color: #f59e0b;
        background: #78350f;
    }

    /* 健康状态指示灯 */
    .health-indicator {
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .health-indicator.healthy {
        background: #064e3b;
        color: #10b981;
        border: 1px solid #10b981;
    }
    .health-indicator.unhealthy {
        background: #7f1d1d;
        color: #ef4444;
        border: 1px solid #ef4444;
    }
    .health-indicator.unknown {
        background: #334155;
        color: #94a3b8;
        border: 1px solid #64748b;
    }

    /* V7.5 金色勋章 */
    .top-candidate-badge {
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 50%, #d97706 100%);
        color: #1a0a0a;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        border: 2px solid #fcd34d;
        box-shadow: 0 0 20px rgba(245, 158, 11, 0.5);
        margin-bottom: 1rem;
    }
    .top-candidate-badge h3 {
        margin: 0;
        font-size: 1.2rem;
        font-weight: 700;
    }
    .top-candidate-badge .score {
        font-size: 2rem;
        font-weight: 800;
    }

    /* V7.5 版本卡片 */
    .version-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #334155;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    .version-card:hover {
        border-color: #f59e0b;
        box-shadow: 0 0 15px rgba(245, 158, 11, 0.3);
    }
    .version-card.initial {
        border-left: 4px solid #3b82f6;
    }
    .version-card.physical-fix {
        border-left: 4px solid #f59e0b;
    }
    .version-card.methodology-patch {
        border-left: 4px solid #10b981;
    }
    .version-card.external-compensation {
        border-left: 4px solid #8b5cf6;
    }

    /* V7.5 Promise Dashboard */
    .promise-dashboard {
        background: #1e293b;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #334155;
    }
    .promise-bar {
        height: 24px;
        border-radius: 4px;
        background: #334155;
        overflow: hidden;
        margin: 0.5rem 0;
    }
    .promise-bar-fill {
        height: 100%;
        transition: width 0.5s ease;
    }
    .promise-bar-fill.innovation {
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
    }
    .promise-bar-fill.resistance {
        background: linear-gradient(90deg, #10b981, #34d399);
    }
    .promise-bar-fill.evidence {
        background: linear-gradient(90deg, #f59e0b, #fbbf24);
    }

    /* V7.5 对抗溯源看板 */
    .conflict-trace {
        background: #1e293b;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #ef4444;
    }
    .conflict-trace.red-attack {
        border-left-color: #ef4444;
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.1), transparent);
    }
    .conflict-trace.blue-defense {
        border-left-color: #3b82f6;
        background: linear-gradient(90deg, rgba(59, 130, 246, 0.1), transparent);
    }

    /* 侧边栏配置 */
    .sidebar-config-header {
        color: #fbbf24;
        font-weight: bold;
        border-bottom: 1px solid #334155;
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }

    /* 进度条 */
    .v7-progress-bar {
        background: #334155;
        border-radius: 4px;
        height: 8px;
        overflow: hidden;
    }
    .v7-progress-fill {
        background: linear-gradient(90deg, #f59e0b, #ef4444);
        height: 100%;
        transition: width 0.3s ease;
    }

    /* ==================== 补全缺失的 CSS 类 ==================== */

    /* 报告容器 */
    .report-container {
        background: #1e293b;
        border-radius: 12px;
        padding: 2rem;
        border: 1px solid #334155;
        margin-bottom: 1rem;
    }
    .report-container h2 {
        color: #fbbf24;
        border-bottom: 1px solid #334155;
        padding-bottom: 0.5rem;
    }
    .report-container h3 {
        color: #fcd34d;
        margin-top: 1rem;
    }

    /* 拒绝/错误报告卡片 */
    .rejection-card {
        background: linear-gradient(135deg, #7f1d1d 0%, #1e293b 100%);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #ef4444;
        margin-bottom: 1rem;
    }
    .rejection-card h3 {
        color: #fca5a5;
    }

    /* 成功卡片 */
    .success-card {
        background: linear-gradient(135deg, #064e3b 0%, #1e293b 100%);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #10b981;
        margin-bottom: 1rem;
    }

    /* 警告卡片 */
    .warning-card {
        background: linear-gradient(135deg, #78350f 0%, #1e293b 100%);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #f59e0b;
        margin-bottom: 1rem;
    }

    /* 轮询统计卡片 */
    .poll-stats-card {
        background: #1e293b;
        border-radius: 8px;
        padding: 0.75rem;
        border: 1px solid #334155;
        text-align: center;
    }

    /* 公理徽章 */
    .axiom-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .axiom-badge.passed {
        background: #064e3b;
        color: #10b981;
        border: 1px solid #10b981;
    }
    .axiom-badge.failed {
        background: #7f1d1d;
        color: #ef4444;
        border: 1px solid #ef4444;
    }
    .axiom-badge.waiting {
        background: #334155;
        color: #94a3b8;
        border: 1px solid #64748b;
    }

    /* ==================== 响应式与动画增强 ==================== */

    /* 脉冲动画 - 当前激活的流水线步骤 */
    @keyframes pulse-active {
        0%, 100% { opacity: 1; text-shadow: 0 0 4px rgba(245, 158, 11, 0.4); }
        50% { opacity: 0.7; text-shadow: 0 0 12px rgba(245, 158, 11, 0.8); }
    }
    .terminal-step-active {
        animation: pulse-active 1.5s ease-in-out infinite;
    }

    /* 流水线状态指示 */
    .pipeline-status-msg {
        color: #fcd34d;
        font-size: 0.85rem;
        margin-top: 0.5rem;
        padding: 0.4rem 0.6rem;
        background: #1e293b;
        border-radius: 4px;
        border-left: 3px solid #f59e0b;
    }
    .pulse-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #f59e0b;
        margin-right: 0.4rem;
        animation: pulse-dot 1.2s ease-in-out infinite;
    }
    @keyframes pulse-dot {
        0%, 100% { opacity: 1; box-shadow: 0 0 4px #f59e0b; }
        50% { opacity: 0.4; box-shadow: 0 0 12px #f59e0b; }
    }

    /* 提交按钮过渡效果 */
    .stButton > button {
        transition: all 0.3s ease;
    }
    .stButton > button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    /* 响应式断点 - 移动端适配 */
    @media (max-width: 768px) {
        .v75-header { padding: 1rem; border-radius: 8px; }
        .v75-header h1 { font-size: 1.3rem; }
        .report-container { padding: 1rem; }
        .version-card { padding: 1rem; }
        .terminal-box { max-height: 250px; font-size: 0.75rem; }
        .promise-dashboard { padding: 0.75rem; }
        .top-candidate-badge { padding: 0.75rem 1rem; }
        .evolution-container [style*="display: flex"] {
            flex-direction: column; align-items: center; gap: 8px;
        }
        .version-node { width: 100%; max-width: 160px; }
        .version-arrow { display: inline-block; transform: rotate(90deg); }
    }

    @media (max-width: 480px) {
        .v75-header h1 { font-size: 1.1rem; }
        .v75-header .subtitle { font-size: 0.75rem; }
    }
</style>
"""


def inject_shared_css():
    """注入共享 CSS 样式（幂等，可多次调用）"""
    st.markdown(SHARED_CSS, unsafe_allow_html=True)
