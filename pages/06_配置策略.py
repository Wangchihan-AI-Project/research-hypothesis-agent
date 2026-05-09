# -*- coding: utf-8 -*-
"""
配置策略编辑器 - program.md 可视化编辑 + 演化协议/Fuse 参数管理

作者: V8.1
日期: 2026-05-03
"""
import streamlit as st
import yaml
from datetime import datetime

from src.ui.page_base import setup_page

project_root = setup_page("配置策略", "⚙️")
_cur_year = datetime.now().year

# ==================== Session State ====================
def init_state():
    defaults = {
        'config_yaml_content': '',
        'config_loaded': False,
        'config_message': '',
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

PROGRAM_MD_PATH = project_root / 'program.md'

# ==================== 加载与保存 ====================
def load_program_md():
    if PROGRAM_MD_PATH.exists():
        content = PROGRAM_MD_PATH.read_text(encoding='utf-8')
        st.session_state.config_yaml_content = content
        st.session_state.config_loaded = True
        return content
    return ""

def save_program_md(content):
    try:
        PROGRAM_MD_PATH.write_text(content, encoding='utf-8')
        return True, "保存成功！"
    except Exception as e:
        return False, f"保存失败: {e}"

def extract_yaml_config(content):
    """从 Markdown 中提取 YAML 配置块"""
    lines = content.split('\n')
    in_yaml = False
    yaml_lines = []
    for line in lines:
        if line.strip().startswith('```yaml') or line.strip().startswith('```yml'):
            in_yaml = True
            continue
        elif line.strip() == '```' and in_yaml:
            in_yaml = False
            continue
        if in_yaml:
            yaml_lines.append(line)
    if yaml_lines:
        try:
            return yaml.safe_load('\n'.join(yaml_lines))
        except yaml.YAMLError:
            return None
    return None

# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown('<div class="sidebar-config-header">⚙️ 配置操作</div>', unsafe_allow_html=True)

    if st.button("📂 加载 program.md", use_container_width=True):
        content = load_program_md()
        if content:
            st.session_state.config_message = "配置已加载"
        else:
            st.session_state.config_message = "program.md 不存在"
        st.rerun()

    if st.button("💾 保存更改", type="primary", use_container_width=True):
        content = st.session_state.get('config_editor_content', '')
        ok, msg = save_program_md(content)
        st.session_state.config_message = msg
        st.rerun()

    if st.session_state.config_message:
        st.info(st.session_state.config_message)

    st.divider()
    st.caption(f"配置文件: {PROGRAM_MD_PATH}")
    st.caption("修改后需重启应用生效")

    st.divider()
    st.markdown("### 📋 快速参考")
    st.caption("**演化协议参数**")
    st.caption("- max_phoenix_iterations: 4-12")
    st.caption("- enable_phoenix_rewrite: true/false")
    st.caption("- enable_methodology_patch: true/false")
    st.caption("**Fuse 保护参数**")
    st.caption("- hard_cap: 5-30")
    st.caption("- min_score_threshold: 5.0-9.0")
    st.caption("**文献检索参数**")
    st.caption("- min_if: 0.0-30.0")
    st.caption("- start_year / end_year")
    st.caption("- min_citations: 0-500")

# ==================== 主区域 ====================
st.markdown("""
<div class="v75-header">
    <h1>⚙️ 配置与策略</h1>
    <div class="subtitle">program.md 编辑器 · 演化参数 · Fuse 保护</div>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📝 YAML 编辑器", "🎛️ 表单编辑", "📊 当前配置预览"])

with tab1:
    content = st.session_state.config_yaml_content
    if not content:
        load_program_md()
        content = st.session_state.config_yaml_content

    if content:
        edited = st.text_area(
            "program.md (可直接编辑 YAML 块)",
            value=content,
            height=600,
            key="config_editor_content",
            label_visibility="collapsed"
        )
        if edited != content:
            st.session_state.config_yaml_content = edited
    else:
        st.warning("program.md 未找到，请在项目根目录创建")

with tab2:
    config = extract_yaml_config(st.session_state.config_yaml_content)

    if config:
        st.markdown("### 自主循环参数")
        col1, col2, col3 = st.columns(3)
        auto_config = config.get('autonomous_mode', {})
        new_target = col1.number_input("目标分数", 5.0, 9.5, float(auto_config.get('target_score', 7.0)), 0.5)
        new_max_iter = col2.number_input("最大迭代", 1, 50, int(auto_config.get('max_iterations', 10)))
        new_time_budget = col3.number_input("时间预算(分钟)", 5, 120, int(auto_config.get('time_budget_minutes', 30)))

        st.markdown("### 演化协议参数")
        col4, col5, col6 = st.columns(3)
        phoenix = config.get('phoenix_protocol', {})
        new_phoenix_iter = col4.slider("最大演化迭代", 4, 12, int(phoenix.get('max_iterations', 8)))
        new_rewrite = col5.checkbox("物理锚点重写", phoenix.get('enable_rewrite', True))
        new_patch = col6.checkbox("方法论补丁注入", phoenix.get('enable_methodology_patch', True))

        st.markdown("### Fuse 保护参数")
        col7, col8 = st.columns(2)
        fuse = config.get('fuse_protection', {})
        new_hard_cap = col7.slider("API 调用上限", 5, 30, int(fuse.get('hard_cap', 15)))
        new_min_score = col8.slider("最低分数阈值", 5.0, 9.0, float(fuse.get('min_score_threshold', 7.0)), 0.5)

        st.markdown("### 文献检索默认参数")
        col9, col10, col11, col12 = st.columns(4)
        search = config.get('paper_search', {})
        new_min_if = col9.number_input("最小 IF", 0.0, 30.0, float(search.get('min_if', 3.0)), 0.5)
        new_start_year = col10.number_input("起始年", 1990, _cur_year, int(search.get('start_year', 2020)))
        new_end_year = col11.number_input("截止年", 1990, _cur_year + 2, int(search.get('end_year', _cur_year)))
        new_min_cite = col12.number_input("最小引用", 0, 500, int(search.get('min_citations', 10)), 5)

        if st.button("💾 应用表单更改（更新 YAML）", type="primary"):
            content = st.session_state.config_yaml_content
            # 简单的字符串替换更新
            import re

            replacements = {
                r'target_score:\s*\d+\.?\d*': f'target_score: {new_target}',
                r'max_iterations:\s*\d+': f'max_iterations: {new_max_iter}',
                r'time_budget_minutes:\s*\d+': f'time_budget_minutes: {new_time_budget}',
                r'max_phoenix_iterations:\s*\d+': f'max_phoenix_iterations: {new_phoenix_iter}',
                r'enable_rewrite:\s*(?:true|false)': f'enable_rewrite: {str(new_rewrite).lower()}',
                r'enable_methodology_patch:\s*(?:true|false)': f'enable_methodology_patch: {str(new_patch).lower()}',
                r'hard_cap:\s*\d+': f'hard_cap: {new_hard_cap}',
                r'min_score_threshold:\s*\d+\.?\d*': f'min_score_threshold: {new_min_score}',
                r'^\s*min_if:\s*\d+\.?\d*': f'  min_if: {new_min_if}',
                r'start_year:\s*\d+': f'start_year: {new_start_year}',
                r'end_year:\s*\d+': f'end_year: {new_end_year}',
                r'min_citations:\s*\d+': f'min_citations: {new_min_cite}',
            }

            for pattern, replacement in replacements.items():
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

            st.session_state.config_yaml_content = content
            st.success("YAML 已更新，请切换到「YAML 编辑器」Tab 检查后保存")
    else:
        st.warning("无法解析 YAML 配置，请先在「YAML 编辑器」中加载 program.md")

with tab3:
    config = extract_yaml_config(st.session_state.config_yaml_content)
    if config:
        st.json(config)
    else:
        st.info("请在「YAML 编辑器」中加载 program.md 查看配置预览")
