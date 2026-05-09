# -*- coding: utf-8 -*-
"""
V7.5 Phoenix Evolution UI - 工业级分布式架构 + 演化可视化版

【架构红线 - 严禁删除】：
- Celery + Redis 分布式任务分发逻辑
- SQLite 状态存储与恢复逻辑
- 冷却期 30s、防抖 5s、多 Tab 提交防护
- Redis/Worker 心跳检测指示灯

【V7.5 新增：演化实验室渲染引擎】：
1. 版本滑块：v1.0 到 v1.9 自由切换
2. 对抗溯源看板：红方攻击点 + 蓝方补丁响应
3. 最佳准方案置顶：MAX_PHOENIX_EXCEEDED 时提取最高 Science Score 版本
4. Promise Dashboard：创新性、抗性、实证度

作者: V7.5 架构工程师
日期: 2026-04-19
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# ==================== V7.1: 集中式日志挂载 ====================
from src.utils.logger import (
    get_central_logger,
    set_task_context,
    clear_task_context,
    AUDIT_LEVEL
)
logger = get_central_logger()

# ==================== 强制 UTF-8 编码环境 ====================
if sys.platform == "win32":
    try:
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
        if sys.stdout is not None and not sys.stdout.closed:
            try:
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, ValueError):
                pass
        if sys.stderr is not None and not sys.stderr.closed:
            try:
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, ValueError):
                pass
    except Exception:
        pass

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
env_path = project_root / '.env'
load_dotenv(env_path, encoding='utf-8', override=True)

import streamlit as st

# ==================== Celery + Redis 组件导入 ====================
try:
    import celery  # noqa: F401
    import redis  # noqa: F401
    CELERY_AVAILABLE = True
except ImportError as e:
    CELERY_AVAILABLE = False
    logger.warning(f"Celery components not available: {e}")

# ==================== st_autorefresh 自动轮询导入 ====================
try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False
    logger.warning("streamlit-autorefresh not available")

# ==================== V7.4-G: 物理公理检测器导入 ====================
try:
    from src.core.pseudoscience_detector import PseudoscienceDetector
    PSEUDOSCIENCE_DETECTOR_AVAILABLE = True
except ImportError:
    PSEUDOSCIENCE_DETECTOR_AVAILABLE = False

# ==================== V7.2: 拒绝报告生成器导入 ====================
try:
    from src.core.rejection_report import (
        RejectionReportGenerator,
        RejectionType,
        ScientificRejectionReport,
    )
    REJECTION_REPORT_AVAILABLE = True
except ImportError:
    REJECTION_REPORT_AVAILABLE = False

# ==================== V7.1 常量定义 ====================
ZOMBIE_TASK_THRESHOLD_MINUTES = 120
MAX_POLL_ATTEMPTS = 300
POLL_INTERVAL_SECONDS = 3
SUBMIT_COOLDOWN_SECONDS = 30
SUBMIT_DEBOUNCE_SECONDS = 5

# 持久化数据库路径
DATA_DIR = project_root / 'data'
DATA_DIR.mkdir(exist_ok=True)
PERSISTENCE_DB = DATA_DIR / 'task_persistence.db'
LOCAL_QUEUE_DB = DATA_DIR / 'local_task_queue.db'

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="科研假设生成器",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "科研假设生成器 - 生物医学AI科研引擎"
    }
)

# ==================== Pipeline 状态定义 ====================
PIPELINE_STEPS = [
    {"step": 1, "name": "Intent Sanitizer", "icon": "🛡️", "description": "意图清洗预检"},
    {"step": 2, "name": "Celery Dispatch", "icon": "📨", "description": "任务派发"},
    {"step": 3, "name": "初始化", "icon": "🧪", "description": "协议初始化"},
    {"step": 4, "name": "Hypothesis Gen", "icon": "🧪", "description": "假设生成"},
    {"step": 5, "name": "Physical Check", "icon": "🔒", "description": "物理锚定校验"},
    {"step": 6, "name": "Red Attack", "icon": "⚔️", "description": "红方攻击"},
    {"step": 7, "name": "Blue Defense", "icon": "🛡️", "description": "蓝方答辩"},
    {"step": 8, "name": "Score Trend", "icon": "📊", "description": "分数趋势检测"},
    {"step": 9, "name": "Phoenix Rewrite", "icon": "🔥", "description": "物理重写"},
    {"step": 10, "name": "Methodology Patch", "icon": "🧬", "description": "方法论补丁"},
    {"step": 11, "name": "External Compensation", "icon": "📡", "description": "外部补偿"},
    {"step": 12, "name": "Phoenix Retry", "icon": "🔄", "description": "补丁重试"},
    {"step": 13, "name": "Evolution Complete", "icon": "✅", "description": "演化完成"},
]

# ==================== V7.5 UI 组件导入（拆分后的模块） ====================
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
import src.ui.pipeline_components as pipeline_mod
from src.ui.pipeline_components import (
    render_pipeline_visualizer,
    render_poll_stats,
    render_safe_submit_button,
)
from src.ui.sidebar_components import (
    render_health_indicator,
    render_sidebar_configurator,
    render_task_history_sidebar,
    render_system_reset_panel,
)

# 注入到流水线模块
pipeline_mod.PIPELINE_STEPS = PIPELINE_STEPS
pipeline_mod.MAX_POLL_ATTEMPTS = MAX_POLL_ATTEMPTS

# ==================== V7.5 核心逻辑模块导入 ====================
import src.core.task_persistence as task_persistence_mod
from src.core.task_persistence import (
    init_task_persistence_db,
    init_local_queue_db,
    register_task_persistence,
    update_task_completion,
    get_task_history_list,
    delete_task_from_history,
    clear_all_task_history,
    recover_lost_task_on_reload,
)
import src.core.health as health_mod
from src.core.health import (
    check_redis_health,
    check_worker_heartbeat,
)
import src.core.guards as guards_mod
from src.core.guards import (
    check_submission_guard,
    acquire_submission_lock,
    release_submission_lock,
    check_poll_guard,
    should_fallback_to_local,
)
from src.core.celery_tasks_v75 import (
    submit_celery_task_with_safety,
    poll_task_status,
    poll_task_status_safe,
    handle_poll_timeout,
    run_hypothesis_task_locally,
)

# 设置模块级变量
task_persistence_mod.PERSISTENCE_DB = PERSISTENCE_DB
task_persistence_mod.LOCAL_QUEUE_DB = LOCAL_QUEUE_DB
task_persistence_mod.DATA_DIR = DATA_DIR
health_mod.CELERY_AVAILABLE = CELERY_AVAILABLE
guards_mod.SUBMIT_COOLDOWN_SECONDS = SUBMIT_COOLDOWN_SECONDS
guards_mod.SUBMIT_DEBOUNCE_SECONDS = SUBMIT_DEBOUNCE_SECONDS
guards_mod.MAX_POLL_ATTEMPTS = MAX_POLL_ATTEMPTS
guards_mod.POLL_INTERVAL_SECONDS = POLL_INTERVAL_SECONDS
guards_mod.ZOMBIE_TASK_THRESHOLD_MINUTES = ZOMBIE_TASK_THRESHOLD_MINUTES

# ==================== V7.5 极客风格 CSS（从共享模块注入） ====================
from src.ui.styles import inject_shared_css
inject_shared_css()

# ==================== Session State 初始化 ====================
def init_session_state():
    """初始化 V7.5 Session State"""
    defaults = {
        # 任务状态
        'task_id': None,
        'task_state': None,
        'task_progress': 0,
        'task_message': '',
        'task_result': None,
        'task_start_time': None,

        # 配置参数
        'execution_mode': 'autonomous',
        'hard_cap': 15,
        'min_score_threshold': 7.0,
        'max_iterations': 5,
        'enable_intent_sanitizer': True,
        'enable_physical_validator': True,

        # V7.5 Phoenix 配置
        'max_phoenix_iterations': 4,
        'enable_phoenix_rewrite': True,
        'enable_methodology_patch': True,

        # 用户输入
        'user_input': '',
        'user_domain': 'auto-detect',

        # Pipeline 状态追踪
        'pipeline_steps_status': {},
        'pipeline_logs': [],

        # V7.5 演化追踪
        'selected_version': None,
        'show_top_candidate': False,

        # 错误状态
        'error_occurred': False,
        'error_type': None,
        'error_message': None,

        # 提交守卫状态
        'submission_lock': False,
        'last_submit_time': None,
        'submit_cooldown_until': None,
        'pending_input_hash': None,

        # 轮询守卫状态
        'poll_start_time': None,
        'poll_attempt_count': 0,
        'last_state_change_time': None,
        'last_known_state': None,

        # 多 Tab 隔离
        'tab_session_id': None,
        'tab_fingerprint': None,
        'lock_holder_tab': None,

        # V7.5 物理公理状态
        'axiom_badge_state': 'waiting',
        'pseudoscience_detected': False,
        'attack_types_detected': [],

        # 本地降级执行备份
        'last_submit_config': {},
        'last_submit_input': '',

        # V7.5 迭代追踪
        'refinement_count': 0,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ==================== 提交守卫系统 ====================
def init_submission_guard():
    """提交守卫初始化"""
    if 'submission_lock' not in st.session_state:
        st.session_state.submission_lock = False
    if 'last_submit_time' not in st.session_state:
        st.session_state.last_submit_time = None
    if 'submit_cooldown_until' not in st.session_state:
        st.session_state.submit_cooldown_until = None
    if 'pending_input_hash' not in st.session_state:
        st.session_state.pending_input_hash = None

    # Tab 隔离机制
    if 'tab_session_id' not in st.session_state:
        st.session_state.tab_session_id = f"tab_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(os.urandom(8)) & 0xFFFFFF:06x}"

    if 'tab_fingerprint' not in st.session_state or st.session_state.tab_fingerprint is None:
        st.session_state.tab_fingerprint = {
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'activity_count': 0,
        }

    st.session_state.tab_fingerprint['last_activity'] = datetime.now().isoformat()
    st.session_state.tab_fingerprint['activity_count'] = st.session_state.tab_fingerprint.get('activity_count', 0) + 1

# ==================== 轮询守卫系统 ====================
def init_poll_guard():
    """轮询守卫初始化"""
    if 'poll_start_time' not in st.session_state:
        st.session_state.poll_start_time = None
    if 'poll_attempt_count' not in st.session_state:
        st.session_state.poll_attempt_count = 0
    if 'last_state_change_time' not in st.session_state:
        st.session_state.last_state_change_time = None
    if 'last_known_state' not in st.session_state:
        st.session_state.last_known_state = None


# ==================== 主界面 ====================
def render_main_interface():
    """V7.5 主界面"""

    # 紧凑标题
    st.markdown("""
    <div class="v75-header-compact">
        <h1>🧪 科研假设生成器 <span class="header-version">V7.5</span></h1>
        <div class="subtitle">生物医学AI科研引擎 · 文献检索 · 假设生成 · 智能验证</div>
    </div>
    """, unsafe_allow_html=True)

    # 用户输入区 + 提交按钮（紧凑布局）
    with st.container():
        st.markdown("### 📝 研究想法")

        # 快捷示例行
        EXAMPLES = [
            ("🧠 阿尔茨海默病", "阿尔茨海默病患者海马体萎缩与认知功能下降的关系研究"),
            ("🧬 三阴性乳腺癌", "利用单细胞转录组学识别三阴性乳腺癌的免疫逃逸机制"),
            ("💊 药物靶点", "基于深度学习的药物-靶点相互作用预测模型的构建与验证"),
        ]
        cols = st.columns(len(EXAMPLES))
        for i, (label, text) in enumerate(EXAMPLES):
            if cols[i].button(label, key=f"ex_{i}", use_container_width=True, help=text[:80] + "…"):
                st.session_state.user_input = text
                st.session_state.user_input_area = text
                st.rerun()

        col_input, col_side = st.columns([5, 1])
        with col_input:
            user_input = st.text_area(
                "输入您的研究想法",
                placeholder="例如：阿尔茨海默病患者海马体萎缩与认知功能下降的关系研究...",
                height=100,
                max_chars=2000,
                key='user_input_area',
                label_visibility="collapsed",
            )
            st.session_state.user_input = user_input
            char_count = len(user_input) if user_input else 0
            count_color = "#94a3b8" if char_count < 1800 else "#f59e0b" if char_count < 2000 else "#ef4444"
            st.markdown(f'<span style="color:{count_color};font-size:0.75rem;">{char_count}/2000</span>', unsafe_allow_html=True)

        with col_side:
            user_domain = st.selectbox(
                "领域",
                options=['auto-detect', 'medicine', 'biology', 'neuroscience',
                         'genomics', 'bioinformatics', 'biostatistics'],
                format_func=lambda x: "🔍 自动" if x == 'auto-detect' else x.upper(),
                key='domain_select',
            )
            st.session_state.user_domain = user_domain

            axiom_state = st.session_state.get('axiom_badge_state', 'waiting')
            if axiom_state == 'waiting':
                st.markdown('<span class="axiom-badge waiting">⏳ 等待检阅</span>', unsafe_allow_html=True)
            elif axiom_state == 'passed':
                st.markdown('<span class="axiom-badge passed">✅ 科学底线达标</span>', unsafe_allow_html=True)
            elif axiom_state == 'failed':
                st.markdown('<span class="axiom-badge failed">❌ 物理公理冲突</span>', unsafe_allow_html=True)

    # 提交按钮 — 紧接输入区
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        config = render_sidebar_configurator(CELERY_AVAILABLE, check_redis_health, check_worker_heartbeat)
        render_safe_submit_button(user_input, config, init_submission_guard, check_submission_guard, acquire_submission_lock, submit_celery_task_with_safety, release_submission_lock, run_hypothesis_task_locally)

    # 任务历史（侧边栏）
    render_task_history_sidebar(get_task_history_list, clear_all_task_history, delete_task_from_history)

    # 系统维护面板（侧边栏底部）
    render_system_reset_panel()

    # 任务状态检查
    task_id = st.session_state.get('task_id')
    task_state = st.session_state.get('task_state')

    # 防止死循环：若任务启动超过 5 分钟仍未完成，自动清除
    task_start = st.session_state.get('task_start_time')
    if task_start and task_state in ('PENDING', 'PROGRESS'):
        try:
            start = datetime.fromisoformat(task_start)
            if (datetime.now() - start).total_seconds() > 300:
                logger.warning(f"任务 {task_id[:16] if task_id else '?'} 超时 5 分钟，自动清除")
                st.session_state.task_id = None
                st.session_state.task_state = None
                st.session_state.task_progress = 0
                st.session_state.poll_attempt_count = 0
                st.session_state.submission_lock = False
                task_id = None
                task_state = None
                st.rerun()
        except Exception:
            pass

    # 任务进行中
    if task_state == 'PROGRESS' or task_state == 'PENDING':
        st.markdown(f"""
        <div class="status-card">
            <p><strong>任务ID</strong>: {task_id[:20]}...</p>
            <p><strong>状态</strong>: 执行中...</p>
        </div>
        """, unsafe_allow_html=True)

        # 轮询统计
        render_poll_stats()

        # Pipeline 可视化
        render_pipeline_visualizer()

        # 自动轮询
        if AUTOREFRESH_AVAILABLE:
            st_autorefresh(interval=POLL_INTERVAL_SECONDS * 1000, key=f"poll_{task_id}")
            poll_result = poll_task_status_safe(task_id, session_state=st.session_state)

            if poll_result['state'] == 'SUCCESS':
                st.session_state.task_result = poll_result.get('result')
                st.session_state.task_state = 'SUCCESS'
                st.success("🎉 任务执行成功！")
                st.rerun()
            elif poll_result['state'] == 'FAILURE':
                st.session_state.task_result = poll_result.get('result', poll_result)
                st.session_state.task_state = 'FAILURE'
                st.error("❌ 任务执行失败")
                st.rerun()
            elif poll_result['state'] == 'FALLBACK_TO_LOCAL':
                st.warning("⚠️ Celery Worker 未响应，切换到本地执行...")
                logger.warning(f"FALLBACK_TO_LOCAL triggered for task {task_id}")

                # 从 session_state 恢复提交时的 config 和 user_input
                fallback_config = st.session_state.get('last_submit_config', {})
                fallback_input = st.session_state.get('last_submit_input', st.session_state.get('user_input', ''))

                if not fallback_input:
                    st.error("无法恢复用户输入，请重新提交")
                else:
                    with st.spinner("正在本地同步执行假设生成（可能需要 5-15 分钟）..."):
                        try:
                            local_result = run_hypothesis_task_locally(fallback_input, fallback_config)

                            if local_result and local_result.get('state') == 'success':
                                st.session_state.task_result = local_result
                                st.session_state.task_state = 'SUCCESS'
                                st.success("本地执行成功！")
                            else:
                                st.session_state.task_result = local_result
                                st.session_state.task_state = 'FAILURE'
                                st.error(f"本地执行失败: {local_result.get('error', '未知错误')}")
                        except Exception as e:
                            logger.exception(f"本地执行异常: {e}")
                            st.session_state.task_state = 'FAILURE'
                            st.session_state.task_result = {
                                'error': str(e),
                                'result_type': 'local_fallback_error',
                            }
                            st.error(f"本地执行异常: {str(e)}")
                    st.rerun()

            elif poll_result['state'] == 'TIMEOUT':
                render_timeout_report(task_id, poll_result.get('timeout_reason', 'UNKNOWN'), poll_result.get('details', {}))
            else:
                st.info(f"🔄 自动刷新中... 进度: {poll_result['progress']}%")
        else:
            if st.button("🔄 手动检查", key='manual_poll'):
                poll_result = poll_task_status_safe(task_id, session_state=st.session_state)
                st.rerun()

    # 任务成功
    elif task_state == 'SUCCESS':
        result = st.session_state.get('task_result', {})
        render_success_report(result)

        # V7.5: 假设迭代追踪 — 在成功结果基础上继续优化
        with st.expander("🔄 在此基础优化", expanded=False):
            st.markdown("在现有结果基础上，补充新的约束或研究方向，系统将基于原假设继续演化。")

            # 显示原始输入
            original_input = st.session_state.get('last_submit_input', st.session_state.get('user_input', ''))
            st.caption(f"**原始输入**: {original_input[:100]}...")

            # 获取上一次的假设标题
            payload = result.get('payload', {})
            hypothesis = payload.get('hypothesis', {})
            prev_title = hypothesis.get('title', '未命名')
            st.caption(f"**上一轮假设**: {prev_title}")

            # 迭代次数追踪
            iteration_count = st.session_state.get('refinement_count', 0)
            st.caption(f"**已迭代**: {iteration_count} 次")

            refinement = st.text_area(
                "优化指令",
                placeholder="例如：增加样本量要求、更换统计方法为贝叶斯框架、限定研究人群为老年人...",
                height=80,
                max_chars=500,
                key='refinement_input',
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 基于此继续演化", key='refine_submit', use_container_width=True,
                             disabled=not refinement.strip()):
                    # 构建迭代输入：仅追加最新优化指令（避免多轮累积导致 prompt 膨胀）
                    new_input = f"""[迭代优化 - 第{iteration_count + 1}轮]

研究问题: {original_input}

上一轮假设摘要: {prev_title}

优化指令: {refinement}

请在原有假设基础上，根据优化指令进行定向改进。"""

                    st.session_state.user_input = new_input
                    st.session_state.last_submit_input = original_input  # 始终保留原始问题
                    st.session_state.refinement_count = iteration_count + 1

                    # 清除当前结果，触发重新提交
                    st.session_state.task_id = None
                    st.session_state.task_state = None
                    st.session_state.task_result = None
                    st.session_state.task_progress = 0
                    st.session_state.poll_attempt_count = 0
                    st.session_state.submission_lock = False
                    st.session_state.axiom_badge_state = 'waiting'
                    st.toast(f"🔄 开始第 {iteration_count + 1} 轮迭代...")
                    st.rerun()

            with col2:
                if iteration_count > 0:
                    st.caption(f"已进行 {iteration_count} 轮迭代优化")

        st.markdown("---")
        col_new, col_clear = st.columns(2)
        with col_new:
            if st.button("🔄 全新研究", key='new_research', use_container_width=True):
                for key in ['task_id', 'task_state', 'task_result', 'pipeline_logs', 'poll_start_time',
                            'poll_attempt_count', 'refinement_count']:
                    if key == 'poll_attempt_count':
                        st.session_state[key] = 0
                    elif key == 'refinement_count':
                        st.session_state[key] = 0
                    else:
                        st.session_state[key] = None
                st.session_state.task_progress = 0
                st.session_state.axiom_badge_state = 'waiting'
                st.rerun()
        with col_clear:
            if st.button("🗑️ 清除全部", key='clear_all', use_container_width=True):
                for key in ['task_id', 'task_state', 'task_result', 'pipeline_logs', 'poll_start_time',
                            'poll_attempt_count', 'refinement_count', 'user_input', 'user_input_area',
                            'last_submit_input']:
                    if key in ('poll_attempt_count', 'refinement_count'):
                        st.session_state[key] = 0
                    else:
                        st.session_state[key] = None
                st.session_state.task_progress = 0
                st.session_state.axiom_badge_state = 'waiting'
                st.rerun()

    # 任务失败
    elif task_state == 'FAILURE':
        error_info = st.session_state.get('task_result', {})
        if not error_info:
            error_info = {
                'result_type': st.session_state.get('error_type', 'unknown'),
                'error': st.session_state.get('error_message', '任务执行失败')
            }
        render_rejection_report(error_info, st.session_state.get('user_input', ''))

        if st.button("🔄 重新提交", key='retry_submit'):
            for key in ['task_id', 'task_state', 'error_occurred', 'error_type', 'error_message', 'pipeline_logs']:
                st.session_state[key] = None if key != 'error_occurred' else False
            st.session_state.task_progress = 0
            st.session_state.axiom_badge_state = 'waiting'
            st.rerun()

    # 任务超时
    elif task_state == 'TIMEOUT':
        render_timeout_report(
            task_id,
            st.session_state.get('error_type', 'UNKNOWN'),
            {'reason': st.session_state.get('error_message', '超时')}
        )

    # Celery 不可用提示
    if not CELERY_AVAILABLE:
        st.markdown("""
        <div class="status-card warning">
            <h4>⚠️ Celery 后端不可用</h4>
            <p>异步任务系统未启动</p>
            <p>请确保 Redis 和 Celery Worker 正常运行</p>
        </div>
        """, unsafe_allow_html=True)

# ==================== 主程序入口 ====================
def main():
    """V7.5 主程序入口"""
    logger.info("V7.5 app.py 开始执行...")

    # 初始化 Session State
    init_session_state()

    # 初始化持久化数据库
    init_task_persistence_db()
    init_local_queue_db()

    # 初始化守卫
    init_submission_guard()
    init_poll_guard()

    # 刷新后任务召回
    if st.session_state.task_id is None:
        recovered = recover_lost_task_on_reload(
            st.session_state,
            poll_task_status_safe_fn=lambda tid: poll_task_status_safe(tid, session_state=st.session_state),
            celery_available=CELERY_AVAILABLE,
        )
        if recovered:
            st.toast(f"🔄 已自动恢复任务: {recovered[:12]}...")
            logger.info(f"任务召回成功: {recovered}")

    # 渲染主界面
    render_main_interface()

    logger.info("V7.5 app.py 执行完成")


if __name__ == '__main__':
    main()
