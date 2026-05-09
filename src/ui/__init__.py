# -*- coding: utf-8 -*-
"""
src/ui - 共享 UI 组件库

便捷导入:
    from src.ui import setup_page, get_orchestrator
    from src.ui import (render_success_report, render_pipeline_visualizer, ...)
"""

from src.ui.styles import inject_shared_css
from src.ui.page_base import setup_page, get_orchestrator
from src.ui.evolution_view import (
    calculate_promise_score,
    render_top_candidate_badge,
    render_promise_dashboard,
    render_evolution_slider,
    render_version_detail,
    render_conflict_trace,
    render_phoenix_status_panel,
    render_score_trend_chart,
    render_phoenix_evolution_graph,
)
from src.ui.report_renderers import (
    render_success_report,
    render_phoenix_failure_report,
    render_rejection_report,
    render_timeout_report,
)
from src.ui.pipeline_components import (
    render_pipeline_visualizer,
    render_poll_stats,
    render_safe_submit_button,
)
from src.ui.sidebar_components import (
    render_health_indicator,
    render_sidebar_configurator,
    render_task_history_sidebar,
)
