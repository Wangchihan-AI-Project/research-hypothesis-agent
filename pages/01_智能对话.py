# -*- coding: utf-8 -*-
"""
智能对话模式 - 自然语言科研助手

移植 CLI 的 run_conversational_mode() + IntentClarifier 语义追问
使用 Streamlit chat_message 构建类聊天 UI

作者: V8.1
日期: 2026-05-03
"""
import os

import streamlit as st
from src.ui.page_base import setup_page, get_orchestrator

project_root = setup_page("智能对话", "💬")

from src.core.intent_parser import IntentParser, UserIntent, ParsedIntent
from src.core.conversation_context import ConversationContext, create_session_context
from src.core.intent_clarifier import IntentClarifier, ClarificationResult, MAX_CLARIFICATION_ROUNDS, is_broad_input

# ==================== Session State 初始化 ====================
def init_conv_state():
    defaults = {
        'conv_messages': [],           # 聊天消息列表 [{"role":"user/assistant","content":"..."}]
        'conv_context': None,          # ConversationContext 实例
        'conv_orchestrator': None,     # Orchestrator 懒加载
        'conv_clarifier': None,        # IntentClarifier 懒加载
        'conv_parser': None,           # IntentParser 懒加载
        'conv_clarify_round': 0,       # 当前追问轮次
        'conv_clarify_result': None,   # ClarificationResult
        'conv_clarify_active': False,  # 是否在追问中
        'conv_pending_intent': None,   # 等待明确的意图
        'conv_current_papers': [],     # 当前检索到的论文
        'conv_generated_hypotheses': [], # 当前生成的假设
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_conv_state()

@st.cache_resource
def get_parser():
    return IntentParser()

@st.cache_resource
def get_clarifier():
    return IntentClarifier()

def ensure_context():
    if st.session_state.conv_context is None:
        import uuid
        sid = str(uuid.uuid4())[:8]
        st.session_state.conv_context = create_session_context(sid)

# ==================== 参数处理 ====================
def params_to_dict(parsed):
    """将 ParsedIntent.parameters (SearchParameters dataclass) 转为可修改的 dict"""
    if parsed.parameters is None:
        return {}
    from dataclasses import asdict
    return asdict(parsed.parameters)

def dict_to_params(parsed, d):
    """将 dict 的修改写回 SearchParameters dataclass"""
    if parsed.parameters is not None:
        for k, v in d.items():
            if hasattr(parsed.parameters, k):
                setattr(parsed.parameters, k, v)

# ==================== 意图执行 ====================
def handle_search_papers(parsed, container):
    """执行论文搜索"""
    params = params_to_dict(parsed)
    query = params.get("query", parsed.original_input)
    max_results = params.get("max_results", 20)

    with container.status(f"🔍 搜索中: {query[:80]}...", expanded=True):
        orch = get_orchestrator()
        orch.start_session(query)
        result = orch.search_papers(query, max_results=max_results, enable_filter=False, fetch_full_text=True, max_full_text=5)
        papers = result.get('papers', [])
        st.session_state.conv_current_papers = papers
        st.session_state.conv_context.current_query = query
        st.session_state.conv_context.paper_count = len(papers)

    if papers:
        st.success(f"找到 {len(papers)} 篇论文")
        for i, p in enumerate(papers[:5]):
            title = p.get('title', 'N/A')
            year = p.get('year', '')
            journal = p.get('journal', '')
            pmid = p.get('pmid', '')
            st.markdown(f"**{i+1}. {title}**  ({year})")
            st.caption(f"{journal} | PMID: {pmid}")
        if len(papers) > 5:
            st.info(f"...还有 {len(papers) - 5} 篇论文")
    else:
        st.warning("未找到匹配论文，请尝试修改搜索词")

def handle_refine_search(parsed, container):
    """扩大/缩小搜索"""
    expand_keywords = ["扩大", "expand", "更多", "more", "broaden", "widen"]
    shrink_keywords = ["缩小", "narrow", "少", "fewer", "less", "specific"]

    current_max = st.session_state.conv_context.paper_count or 20
    user_text = parsed.original_input.lower()

    if any(kw in user_text for kw in expand_keywords):
        new_max = min(current_max * 2, 100)
        action = "扩大"
    elif any(kw in user_text for kw in shrink_keywords):
        new_max = max(current_max // 2, 5)
        action = "缩小"
    else:
        new_max = current_max
        action = "调整"

    query = st.session_state.conv_context.current_query or parsed.original_input
    with container.status(f"🔄 {action}搜索: {query[:80]}...", expanded=True):
        orch = get_orchestrator()
        result = orch.search_papers(query, max_results=new_max, enable_filter=False, fetch_full_text=True, max_full_text=5)
        papers = result.get('papers', [])
        st.session_state.conv_current_papers = papers
        st.session_state.conv_context.paper_count = len(papers)

    st.success(f"{action}搜索完成，找到 {len(papers)} 篇论文")

def handle_generate_hypothesis(parsed, container):
    """生成假设"""
    papers = st.session_state.conv_current_papers
    if not papers:
        st.warning("请先搜索论文再生成假设")
        return

    params = params_to_dict(parsed)
    topic = params.get("query", st.session_state.conv_context.current_query or "")
    with container.status("🧪 首席科学家正在生成假设...", expanded=True):
        orch = get_orchestrator()
        hypotheses = orch.generate_hypotheses(papers, research_field=topic)
        st.session_state.conv_generated_hypotheses = hypotheses
        st.session_state.conv_context.hypothesis_count = len(hypotheses) if isinstance(hypotheses, list) else 0

    if isinstance(hypotheses, list) and hypotheses:
        st.success(f"生成 {len(hypotheses)} 个假设")
        for i, hyp in enumerate(hypotheses):
            title = hyp.get('title', f'假设 {i+1}')
            score = hyp.get('pre_validation_score', hyp.get('science_score', 'N/A'))
            desc = hyp.get('description', '')[:200]
            with st.expander(f"假设 {i+1}: {title} (评分: {score})"):
                st.write(desc)
    else:
        st.error("假设生成失败，请重试")

def handle_view_history(container):
    """查看历史会话"""
    orch = get_orchestrator()
    try:
        sessions = orch.list_recent_sessions(10)
        if not sessions:
            st.info("暂无历史会话")
            return

        rows = []
        for s in sessions:
            rows.append({
                "ID": s.get('id', ''),
                "查询": (s.get('query', '') or '')[:40],
                "时间": str(s.get('created_at', ''))[:19],
                "状态": s.get('status', ''),
                "论文数": s.get('papers_found', 0),
                "假设数": s.get('hypotheses_generated', 0),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"暂无法加载会话历史: {e}")

def handle_export_report(parsed, container):
    """导出报告"""
    # 从用户输入中提取数字 ID
    import re
    match = re.search(r'(\d+)', parsed.original_input)
    if match:
        hyp_id = int(match.group(1))
    else:
        hyp_id_str = st.text_input("请输入假设 ID:", key="conv_export_id")
        if not hyp_id_str:
            return
    try:
        hyp_id = int(hyp_id_str)
        orch = get_orchestrator()
        report = orch.get_full_report(hyp_id)
        if report:
            from src.utils.report_export import ReportExporter
            exporter = ReportExporter()
            path = exporter.export_to_markdown(report)
            st.success(f"报告已导出到: {path}")
        else:
            st.error(f"未找到假设 ID: {hyp_id}")
    except ValueError:
        st.error("请输入有效的数字 ID")

def handle_modify_config(parsed, container):
    """修改配置 - 跳转到配置页面提示"""
    st.info("📝 配置编辑请使用侧边栏导航到「配置策略」页面进行详细修改")
    # 显示当前关键配置
    try:
        from src.core.program_config import get_program_config
        config = get_program_config()
        st.markdown("### 当前配置摘要")
        sections = ['research_goals', 'paper_search', 'hypothesis_generation', 'autonomous_mode']
        for sec in sections:
            data = config.get_section(sec)
            if data:
                st.markdown(f"**{sec}**")
                st.json(data)
    except Exception:
        pass

# ==================== 意图路由 ====================
def dispatch_intent(parsed, container):
    """根据意图执行操作，返回响应文本"""
    intent = parsed.intent
    if intent == UserIntent.SEARCH_PAPERS:
        handle_search_papers(parsed, container)
        return f"论文搜索完成。你可以输入「生成假设」来基于这些论文创建研究假设，或输入「扩大搜索」获取更多论文。"

    elif intent == UserIntent.REFINE_SEARCH:
        handle_refine_search(parsed, container)
        return "搜索已更新。满意后可以输入「生成假设」继续。"

    elif intent == UserIntent.GENERATE_HYPOTHESIS:
        handle_generate_hypothesis(parsed, container)
        return "假设已生成。你可以输入「选择第1个」来验证某个假设，或输入「导出报告」保存结果。"

    elif intent == UserIntent.SELECT_HYPOTHESIS:
        import re
        user_text = parsed.original_input
        match = re.search(r'(\d+)', user_text)
        if match:
            idx = int(match.group(1)) - 1
            hyps = st.session_state.conv_generated_hypotheses
            if hyps and 0 <= idx < len(hyps):
                selected = hyps[idx]
                orch = get_orchestrator()
                with container.status("🔬 验证假设中...", expanded=True):
                    validation = orch.validate_hypothesis(selected)
                    if validation:
                        scores = validation.get('scores', {})
                        st.markdown("### 验证结果")
                        cols = st.columns(3)
                        cols[0].metric("影响力", f"{scores.get('impact', 0):.1f}")
                        cols[1].metric("原创性", f"{scores.get('originality', 0):.1f}")
                        cols[2].metric("可行性", f"{scores.get('feasibility', 0):.1f}")
                        decision = validation.get('decision', '')
                        st.info(f"**结论**: {decision}")
                return f"假设 {idx+1} 验证完成。"
            else:
                return "请先确认假设编号，输入「生成假设」查看可用的假设列表。"
        return "请指明要选择第几个假设，如「选择第1个」。"

    elif intent == UserIntent.VIEW_HISTORY:
        handle_view_history(container)
        return ""

    elif intent == UserIntent.VIEW_SAVED:
        st.info("假设浏览功能请使用侧边栏导航到「假设管理」页面")
        return ""

    elif intent == UserIntent.MODIFY_CONFIG:
        handle_modify_config(parsed, container)
        return ""

    elif intent == UserIntent.EXPORT_REPORT:
        handle_export_report(parsed, container)
        return ""

    elif intent == UserIntent.AUTONOMOUS_MODE:
        st.info("🤖 自主循环模式请使用侧边栏导航到「自主循环」页面")
        return ""

    elif intent == UserIntent.EXIT:
        return "再见！随时回来继续研究。"

    else:
        return "抱歉，我没理解你的意图。你可以尝试：\n- 「搜索阿尔茨海默病的血液生物标记物」\n- 「生成假设」\n- 「查看历史」\n- 「修改配置」"

# ==================== 澄清追问处理 ====================
SKIP_KEYWORDS = ["直接开始", "就这样", "先试试", "开始吧", "just start", "go ahead", "skip", "跳过"]

def process_clarification_answer(user_input):
    """处理用户对追问的回答"""
    if any(kw in user_input.lower() for kw in SKIP_KEYWORDS):
        st.session_state.conv_clarify_active = False
        return True  # 跳过，直接执行

    clarifier = get_clarifier()
    prev = st.session_state.conv_clarify_result

    if prev and prev.round_count + 1 > MAX_CLARIFICATION_ROUNDS:
        st.session_state.conv_clarify_active = False
        return True

    result = clarifier.assess(user_input, previous_result=prev)
    st.session_state.conv_clarify_result = result
    st.session_state.conv_clarify_round = result.round_count

    if result.is_clear_enough:
        st.session_state.conv_clarify_active = False
        return True

    return False

def apply_clarified_query(parsed):
    """将澄清后的 query 应用到 parsed intent"""
    result = st.session_state.conv_clarify_result
    if result and result.refined_query and result.refined_query != parsed.original_input:
        if parsed.parameters is not None:
            parsed.parameters.query = result.refined_query

# ==================== 页面渲染 ====================
def render_sidebar_info():
    with st.sidebar:
        st.markdown('<div class="sidebar-config-header">💬 智能对话</div>', unsafe_allow_html=True)
        st.caption("用自然语言描述研究需求")

        ctx = st.session_state.conv_context
        if ctx:
            summary = ctx.get_summary()
            if summary != "新会话":
                st.info(summary)

        st.divider()
        st.caption("支持的指令示例：")
        examples = [
            "搜索阿尔茨海默病的血液生物标记物",
            "扩大搜索范围",
            "生成假设",
            "选择第1个假设",
            "查看历史",
            "导出报告",
            "修改配置",
        ]
        for ex in examples:
            st.caption(f"• {ex}")

        if st.button("🔄 新对话", use_container_width=True):
            import uuid
            sid = str(uuid.uuid4())[:8]
            st.session_state.conv_context = create_session_context(sid)
            st.session_state.conv_messages = []
            st.session_state.conv_clarify_active = False
            st.session_state.conv_clarify_result = None
            st.session_state.conv_current_papers = []
            st.session_state.conv_generated_hypotheses = []

# ==================== 主入口 ====================
render_sidebar_info()

st.markdown("""
<div class="v75-header">
    <h1>💬 智能科研对话</h1>
    <div class="subtitle">V8.1 意图理解 + 语义追问 · 用自然语言驱动科研引擎</div>
</div>
""", unsafe_allow_html=True)

# 渲染聊天历史
for msg in st.session_state.conv_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 处理澄清追问
if st.session_state.conv_clarify_active:
    result = st.session_state.conv_clarify_result
    if result and result.follow_up_questions:
        st.info(f"**让我帮你明确研究方向** (第{result.round_count + 1}轮)")
        st.caption(f"当前理解: {result.research_scope_summary}")
        for i, q in enumerate(result.follow_up_questions, 1):
            st.markdown(f"{i}. {q}")
        st.caption("*(输入「直接开始」跳过追问)*")

# 用户输入
user_input = st.chat_input("请输入你的研究需求...")

if user_input:
    ensure_context()
    user_input = user_input.strip()

    # 添加用户消息
    st.session_state.conv_messages.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.markdown(user_input)

    # 如果在追问中
    if st.session_state.conv_clarify_active:
        done = process_clarification_answer(user_input)
        if done:
            # 追问结束，用澄清后的 query 执行原意图
            parsed = st.session_state.conv_pending_intent
            if parsed:
                apply_clarified_query(parsed)
                with st.chat_message("assistant"):
                    with st.container():
                        resp = dispatch_intent(parsed, st.container())
                        if resp:
                            st.markdown(resp)
                    st.session_state.conv_messages.append({"role": "assistant", "content": resp or "操作完成"})
        else:
            # 继续追问
            with st.chat_message("assistant"):
                result = st.session_state.conv_clarify_result
                if result and result.follow_up_questions:
                    st.markdown(f"**继续明确一下：**")
                    for i, q in enumerate(result.follow_up_questions, 1):
                        st.markdown(f"{i}. {q}")
                    st.session_state.conv_messages.append({
                        "role": "assistant",
                        "content": f"继续明确：\n" + "\n".join(f"{i}. {q}" for i, q in enumerate(result.follow_up_questions, 1))
                    })

    else:
        # 正常处理流程
        with st.chat_message("assistant"):
            with st.container():
                # 1. 解析意图
                parser = get_parser()
                ctx = st.session_state.conv_context
                parsed = parser.parse(user_input, ctx)

                # 2. 检查是否需要澄清
                if parsed.intent in (UserIntent.SEARCH_PAPERS, UserIntent.GENERATE_HYPOTHESIS):
                    clarifier = get_clarifier()
                    params = params_to_dict(parsed)
                    query = params.get("query", user_input) if params else user_input
                    if is_broad_input(query):
                        result = clarifier.assess(query)
                        if not result.is_clear_enough and result.follow_up_questions:
                            st.session_state.conv_clarify_active = True
                            st.session_state.conv_clarify_result = result
                            st.session_state.conv_clarify_round = 0
                            st.session_state.conv_pending_intent = parsed
                            st.info(f"**让我帮你明确研究方向** (清晰度: {result.clarity_score:.0%})")
                            st.caption(result.research_scope_summary)
                            for i, q in enumerate(result.follow_up_questions, 1):
                                st.markdown(f"{i}. {q}")
                            st.caption("*(输入「直接开始」跳过追问)*")
                            resp = "你的输入比较宽泛，请回答以上问题帮助我更好地理解你的需求。"
                            st.session_state.conv_messages.append({"role": "assistant", "content": resp})
                    elif result.clarity_score < 1.0:
                        # 清晰但显示理解摘要
                        st.caption(f"📌 理解为: {result.research_scope_summary}")
                        if result.refined_query != user_input and parsed.parameters is not None:
                            parsed.parameters.query = result.refined_query

                # 3. 更新上下文
                ctx.add_turn(user_input, parsed, action_taken="")

                # 4. 执行意图
                resp = dispatch_intent(parsed, st.container())
                if resp:
                    st.markdown(resp)

                st.session_state.conv_messages.append({"role": "assistant", "content": resp or "操作完成"})

# 空状态提示
if not st.session_state.conv_messages:
    st.markdown("""
    <div style="text-align:center; color:#64748b; padding:3rem 0;">
        <p style="font-size:1.2rem;">👋 你好！我是你的科研助手</p>
        <p>你可以直接用自然语言描述你的研究需求，我会帮你：</p>
        <p>
            🔍 搜索论文 &nbsp;|&nbsp;
            🧪 生成假设 &nbsp;|&nbsp;
            📊 验证方案 &nbsp;|&nbsp;
            📝 导出报告
        </p>
        <p style="margin-top:2rem; font-size:0.85rem;">试着输入：<code>搜索 CRISPR 在肿瘤免疫治疗中的应用</code></p>
    </div>
    """, unsafe_allow_html=True)
