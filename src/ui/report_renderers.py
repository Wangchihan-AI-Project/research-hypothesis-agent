# -*- coding: utf-8 -*-
"""
报告渲染组件 - 成功/失败/拒绝/超时 四种结果渲染

从 app.py 提取，供主应用导入使用。
"""

import streamlit as st
from datetime import datetime
from typing import Dict
import json


def _build_markdown_report(result: Dict) -> str:
    """从 result payload 构建完整 Markdown 报告"""
    payload = result.get('payload', {})
    hypothesis = payload.get('hypothesis', {})
    fitness = payload.get('fitness', {})
    phoenix_protocol = payload.get('phoenix_protocol', {})
    version_evolution = payload.get('version_evolution', {})
    version_chain = version_evolution.get('chain', [])
    score_history = phoenix_protocol.get('score_evolution', [])
    methodology = hypothesis.get('methodology', {})

    lines = []
    lines.append(f"# {hypothesis.get('title', '未命名假设')}")
    lines.append("")
    lines.append(f"**学科领域**: {payload.get('domain', 'N/A')}")
    lines.append(f"**版本**: {hypothesis.get('version', 'N/A')}")
    lines.append(f"**生成时间**: {payload.get('timestamp', 'N/A')}")
    lines.append("")

    # 摘要
    lines.append("## 研究摘要")
    lines.append("")
    final_science = score_history[-1] if score_history else 0
    novelty = fitness.get('vector_novelty_score', 0) if fitness else 0
    rigor = fitness.get('red_team_rigor_score', 0) if fitness else 0
    lines.append(f"| 指标 | 得分 |")
    lines.append(f"|------|------|")
    lines.append(f"| 科学分数 | {final_science:.1f} |")
    lines.append(f"| 创新度 | {novelty:.1f} |")
    lines.append(f"| 严谨度 | {rigor:.1f} |")
    lines.append(f"| 演化版本数 | {len(version_chain)} |")
    lines.append("")

    # 核心假设
    lines.append("## 核心假设")
    lines.append("")
    description = hypothesis.get('details', hypothesis.get('description', ''))
    if description:
        lines.append(str(description)[:2000])
        lines.append("")

    # 方法论
    if methodology:
        lines.append("## 方法论")
        lines.append("")
        if isinstance(methodology, dict):
            for key, value in methodology.items():
                key_display = {
                    'technical_safeguards': '技术保障', 'validation_protocol': '验证协议',
                    'bias_control': '偏倚控制', 'approach': '技术路径',
                    'statistical_framework': '统计框架', 'cohort_definition': '队列定义',
                    'expected_outcomes': '预期结果', 'innovation_analysis': '创新分析',
                }.get(key, key)
                lines.append(f"### {key_display}")
                lines.append("")
                if isinstance(value, list):
                    for item in value:
                        lines.append(f"- {item}")
                elif isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        lines.append(f"- **{sub_key}**: {sub_value}")
                else:
                    lines.append(str(value))
                lines.append("")
        else:
            lines.append(str(methodology))
            lines.append("")

    # 演化历史
    if score_history:
        lines.append("## 分数演化")
        lines.append("")
        for i, score in enumerate(score_history):
            lines.append(f"- v1.{i}: Science Score = {score:.2f}")
        lines.append("")

    # 版本链
    if version_chain:
        lines.append("## 版本演化链")
        lines.append("")
        for v in version_chain:
            ver = v.get('version', 'N/A')
            vtype = v.get('type_display', v.get('type', 'N/A'))
            score = v.get('science_score', 0)
            lines.append(f"- **{ver}** ({vtype}) | Score: {score:.2f}")
            hc = v.get('hypothesis_content', {})
            if hc and isinstance(hc, dict) and hc.get('title'):
                lines.append(f"  - 标题: {hc['title'][:120]}")
        lines.append("")

    # 红方攻击审计
    audit_context = payload.get('audit_context', {})
    if audit_context:
        lines.append("## 防御日志")
        lines.append("")
        lines.append(f"- 总迭代次数: {audit_context.get('iterations', 0)}")
        lines.append(f"- 方法论补丁: {audit_context.get('patches', 0)}")
        lines.append(f"- 物理重写: {audit_context.get('rewrites', 0)}")
        red_attacks = audit_context.get('red_attack_types', [])
        if red_attacks:
            lines.append(f"- 红方攻击类型: {', '.join(red_attacks)}")
        lines.append("")

    # 演化记录
    patch_log = hypothesis.get('patch_log', [])
    if patch_log:
        lines.append("## 演化记录")
        lines.append("")
        for i, patch in enumerate(patch_log, 1):
            if isinstance(patch, dict):
                lines.append(f"### 迭代 {i}: {patch.get('attack_type', '未知')}")
                if patch.get('patch_applied'):
                    lines.append(f"> {patch['patch_applied']}")
            else:
                lines.append(f"- 迭代 {i}: {patch}")
        lines.append("")

    # 落地指南
    roadmap = payload.get('implementation_roadmap', {})
    if roadmap:
        lines.append("## 落地指南")
        lines.append("")
        phases = roadmap.get('phases', [])
        for phase in phases:
            lines.append(f"### {phase.get('phase', phase.get('name', '阶段'))}")
            if phase.get('duration'):
                lines.append(f"*{phase['duration']}*")
            for ms in phase.get('milestones', []):
                lines.append(f"- {ms}")
            lines.append("")

    # 创新分析
    innovation = payload.get('innovation_analysis', {})
    if innovation:
        lines.append("## 创新分析")
        lines.append("")
        for item in innovation.get('core_innovations', []):
            lines.append(f"- {item}")
        nov = innovation.get('novelty_level', '')
        if nov:
            lines.append(f"\n新颖度: {nov}")
        lines.append("")

    # 前沿溯源
    frontier = payload.get('frontier_analysis', {})
    if frontier:
        lines.append("## 前沿溯源")
        lines.append("")
        if frontier.get('frontier_position'):
            lines.append(f"前沿定位: {frontier['frontier_position']}")
        for pub in frontier.get('key_publications', [])[:10]:
            lines.append(f"- **{pub.get('title', 'N/A')}** (引用: {pub.get('citation_count', 0)})")
        lines.append("")

    # 文献支撑
    literature = payload.get('literature_support', payload.get('literature', {}))
    if literature:
        lines.append("## 文献支撑")
        lines.append("")
        papers = literature.get('supporting_papers', literature.get('papers', []))
        for i, paper in enumerate(papers[:20], 1):
            title = paper.get('title', 'N/A')
            year = paper.get('year', '')
            journal = paper.get('journal', '')
            citations = paper.get('citation_count', paper.get('citations', 0))
            lines.append(f"{i}. **{title}** ({year}) - {journal} (引用: {citations})")
            abstract = paper.get('abstract', '')
            if abstract:
                lines.append(f"   > {str(abstract)[:300]}")
        lines.append("")

    lines.append("---")
    lines.append(f"*报告由 V7.5 Phoenix Evolution 科研假设生成器自动生成*")
    return "\n".join(lines)


def _generate_experiment_design(hypothesis: Dict, methodology: Dict, fitness: Dict) -> Dict:
    """根据假设内容生成实验设计方案"""
    title = hypothesis.get('title', '')
    description = hypothesis.get('details', hypothesis.get('description', ''))
    if not description:
        description = title

    stats_framework = ''
    if isinstance(methodology, dict):
        stats_framework = methodology.get('statistical_framework', '')
        if not stats_framework:
            for v in methodology.values():
                if isinstance(v, str) and any(kw in v.lower() for kw in ['regression', 'test', 'model', 'bayesian']):
                    stats_framework = v
                    break

    # 样本量估算
    has_causal = any(kw in str(methodology).lower() + str(description).lower()
                     for kw in ['causal', '因果', 'mendelian', 'randomization'])
    has_prediction = any(kw in str(methodology).lower() + str(description).lower()
                         for kw in ['predict', '预测', 'classifier', '分类', 'machine learning'])

    design = {
        'study_type': 'RCT' if has_causal else '观察性研究（队列设计）' if has_prediction else '横断面研究',
        'sample_size_estimation': {},
        'statistical_methods': [],
        'effect_size_metrics': [],
        'randomization_protocol': '',
        'blinding_strategy': '',
        'data_collection_plan': [],
    }

    # 样本量估算
    if has_causal:
        design['sample_size_estimation'] = {
            'method': '基于效应量的样本量估算（Cohen\'s d）',
            'alpha': 0.05,
            'power': 0.80,
            'effect_size_small': {'d': 0.2, 'n_per_group': 394},
            'effect_size_medium': {'d': 0.5, 'n_per_group': 64},
            'effect_size_large': {'d': 0.8, 'n_per_group': 26},
            'formula': 'n = 2(Z_{1-α/2} + Z_{1-β})² / d²',
            'note': '若使用多重检验校正（Bonferroni），需将 α 除以检验次数后重新计算',
        }
    elif has_prediction:
        design['sample_size_estimation'] = {
            'method': '基于事件数/特征数比的经验法则',
            'rule_of_thumb': 'Events Per Variable (EPV) ≥ 10',
            'n_features_10': 'n ≥ 10 × p（p为预测因子数）',
            'n_features_20': 'n ≥ 20 × p（保守推荐）',
            'for_ml': '机器学习模型建议 n > 500，深度模型 n > 5000',
            'note': '应进行功效曲线分析以确定最小样本量',
        }
    else:
        design['sample_size_estimation'] = {
            'method': '基于置信区间宽度的估算',
            'formula': 'n = (Z_{1-α/2} × σ / W)²',
            'explanation': '其中 W 为期望置信区间半宽，σ 为总体标准差估计',
            'default_medium': '中等效应量 (Cohen\'s d=0.5): 每组 n ≈ 64',
        }

    # 统计方法
    design['statistical_methods'] = [
        {'method': '描述性统计', 'detail': '均值±标准差 / 中位数(IQR)，Shapiro-Wilk 正态性检验'},
        {'method': '组间比较', 'detail': 't检验/Mann-Whitney U 检验; 分类变量: χ² 或 Fisher 精确检验'},
    ]
    if has_causal:
        design['statistical_methods'].extend([
            {'method': '因果推断', 'detail': '工具变量分析 (2SLS)、DID 双重差分、倾向性评分匹配 (PSM)'},
            {'method': '混杂控制', 'detail': 'DAG 建模 + 后门准则调整、逆概率加权 (IPTW)'},
            {'method': '敏感性分析', 'detail': 'E-value、Rosenbaum 界限、Leave-one-out 分析'},
        ])
    if has_prediction:
        design['statistical_methods'].extend([
            {'method': '预测建模', 'detail': 'Logistic/Cox 回归、随机森林、XGBoost，配合交叉验证'},
            {'method': '模型评估', 'detail': 'AUC-ROC、校准曲线、Brier Score、决策曲线分析 (DCA)'},
            {'method': '特征重要性', 'detail': 'SHAP 值、Permutation Importance、LIME'},
        ])

    design['statistical_methods'].append(
        {'method': '多重检验校正', 'detail': 'Bonferroni 校正 / FDR (Benjamini-Hochberg)，预设主/次要终点'}
    )

    # 效应量指标
    design['effect_size_metrics'] = [
        {'metric': "Cohen's d / Hedges' g", 'use': '连续变量组间差异'},
        {'metric': 'Odds Ratio / Risk Ratio', 'use': '二分类结局'},
        {'metric': 'Hazard Ratio', 'use': '生存分析/时间事件数据'},
        {'metric': "η² / ω²", 'use': '方差分析效应量'},
        {'metric': "Cramer's V", 'use': '分类变量关联强度'},
    ]

    # 随机化方案
    if has_causal:
        design['randomization_protocol'] = """**分层区组随机化 (Stratified Block Randomization)**
1. 分层因素: 年龄组、性别、疾病严重程度、研究中心
2. 区组大小: 4-6（随机排列）
3. 分配比例: 1:1（可根据伦理调整为 2:1）
4. 随机序列生成: 计算机生成的伪随机数（种子可复现）
5. 分配隐藏: 中心随机化系统 / 密封不透明信封 (SNOSE)"""
    else:
        design['randomization_protocol'] = """**系统抽样 / 按入组顺序分配**
1. 严格按纳入/排除标准连续入组
2. 暴露/非暴露组按自然分组（观察性研究无随机分配）
3. 使用倾向性评分匹配 (PSM) 减少选择偏倚"""

    # 盲法
    if has_causal:
        design['blinding_strategy'] = """**双盲 + 第三方盲态评估**
1. 受试者盲: 安慰剂/假处理对照
2. 研究者盲: 由独立药房/课题组制备干预材料
3. 评估者盲: 结局评估由独立第三方完成
4. 统计分析盲: 揭盲前完成主分析计划 (SAP)"""
    else:
        design['blinding_strategy'] = """**观察者盲 (Observer-blind)**
1. 数据采集人员不知晓研究假设
2. 结局评估由独立评审员完成
3. 分析代码预先注册，防止 p-hacking"""

    # 数据采集计划
    design['data_collection_plan'] = [
        '🕐 **基线 (T0)**: 人口学、病史、合并用药、基线生物标志物',
        '🕑 **干预/暴露期**: 暴露/干预依从性、不良事件、中期生物标志物',
        '🕒 **随访评估**: 主要/次要结局、安全性、生活质量量表',
        '📋 **数据管理**: REDCap / EDC 系统、双录入校验、审计追踪',
        '📊 **统计分析计划 (SAP)**: 预设亚组分析、缺失数据处理方案（MI/FCS）、敏感性分析',
    ]

    return design


def render_phoenix_failure_report(result: Dict):
    """Phoenix 协议失败报告"""
    payload = result.get('payload', {})
    failure_state = payload.get('failure_state', 'UNKNOWN')
    iterations = payload.get('iterations', 0)
    score_history = payload.get('score_history', [])
    version_chain = payload.get('version_chain', [])
    reason = payload.get('reason', '未知原因')

    failure_messages = {
        'MAX_PHOENIX_EXCEEDED': '⏰ 演化达到最大迭代次数限制',
        'HARD_FAILURE': '❌ 遇到无法修复的物理冲突',
        'UNKNOWN': '⚠️ 未知错误'
    }
    title = failure_messages.get(failure_state, f'⚠️ {failure_state}')

    st.markdown(f"""
    <div class="warning-card">
        <h2>{title}</h2>
        <p><strong>迭代次数</strong>: {iterations} 次</p>
        <p><strong>失败原因</strong>: {reason}</p>
    </div>
    """, unsafe_allow_html=True)

    if score_history:
        st.markdown("---")
        st.markdown("### 📊 分数演化历史")
        for i, score in enumerate(score_history):
            st.markdown(f"- **v1.{i}**: Science Score = {score:.2f}")

    if version_chain:
        st.markdown("---")
        st.markdown("### 🔥 版本演化链")
        for v in version_chain:
            version = v.get('version', 'N/A')
            v_type = v.get('type_display', v.get('type', 'N/A'))
            score = v.get('science_score', 0)
            created_at = v.get('created_at', 'N/A')[:19]

            st.markdown(f"""
            <div class="version-card">
                <strong>{version}</strong> ({v_type}) | Score: {score:.2f} | {created_at}
            </div>
            """, unsafe_allow_html=True)

            hc = v.get('hypothesis_content')
            if hc and isinstance(hc, dict):
                title = hc.get('title', '')
                description = hc.get('description', '')
                if title or description:
                    st.markdown(f"- **标题**: {title[:100] if title else 'N/A'}")
                    if description:
                        with st.expander("查看描述"):
                            st.write(description[:500])


def render_success_report(result: Dict):
    """科研假设生成器成功报告"""
    from src.ui.evolution_view import (
        render_top_candidate_badge, render_promise_dashboard,
        render_phoenix_evolution_graph, render_phoenix_status_panel,
        render_score_trend_chart, render_evolution_slider,
        render_conflict_trace
    )

    payload = result.get('payload', {})

    failure_state = payload.get('failure_state')
    if failure_state:
        render_phoenix_failure_report(result)
        return

    st.markdown("""
    <div class="success-card">
        <h2>🧪 演化完成</h2>
    </div>
    """, unsafe_allow_html=True)

    hypothesis = payload.get('hypothesis', {})
    fitness = payload.get('fitness', {})
    phoenix_protocol = payload.get('phoenix_protocol', {})
    version_evolution = payload.get('version_evolution', {})
    version_chain = version_evolution.get('chain', [])
    score_history = phoenix_protocol.get('score_evolution', [])
    versions_count = len(version_chain)

    # V7.5: 摘要卡片 — 关键指标一览
    promise_score = None
    try:
        from src.ui.evolution_view import calculate_promise_score
        best_idx, best_score = calculate_promise_score(result)
        promise_score = best_score
    except Exception:
        pass

    hybrid_fitness = fitness.get('hybrid_fitness', 0) if fitness else 0
    novelty = fitness.get('vector_novelty_score', 0) if fitness else 0
    rigor = fitness.get('red_team_rigor_score', 0) if fitness else 0
    final_science = score_history[-1] if score_history else 0

    def _score_color(v):
        if v >= 8: return 'green'
        if v >= 6: return 'amber'
        return 'red'

    st.markdown(f"""
    <div class="summary-card">
        <h2>📊 研究摘要</h2>
        <div class="summary-metrics">
            <div class="summary-metric">
                <div class="value {_score_color(final_science)}">{final_science:.1f}</div>
                <div class="label">科学分数</div>
            </div>
            <div class="summary-metric">
                <div class="value {_score_color(novelty)}">{novelty:.1f}</div>
                <div class="label">创新度</div>
            </div>
            <div class="summary-metric">
                <div class="value {_score_color(rigor)}">{rigor:.1f}</div>
                <div class="label">严谨度</div>
            </div>
            <div class="summary-metric">
                <div class="value">{versions_count}</div>
                <div class="label">演化版本</div>
            </div>
            <div class="summary-metric">
                <div class="value" style="font-size:1rem;">{hypothesis.get('title', '未命名')[:30]}</div>
                <div class="label">假设标题</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    final_state = phoenix_protocol.get('final_state', '')
    is_max_exceeded = final_state == 'MAX_PHOENIX_EXCEEDED'

    if is_max_exceeded:
        st.markdown("### ⏰ 演化达到上限，展示最佳候选方案")
        render_top_candidate_badge(result)

    tabs = st.tabs([
        "📄 完整报告", "📋 落地指南", "💡 创新分析", "🔬 前沿溯源", "🔥 演化实验室", "📚 文献支撑", "🧪 实验设计"
    ])

    with tabs[0]:
        st.markdown(f"""
        <div class="report-container">
            <h3>{hypothesis.get('title', '未命名假设')}</h3>
            <p><strong>学科领域</strong>: {payload.get('domain', 'N/A')}</p>
            <p><strong>版本</strong>: {hypothesis.get('version', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)

        methodology = hypothesis.get('methodology', {})
        if methodology:
            st.markdown("### 🎯 核心假设陈述")
            bias_control = methodology.get('bias_control', '')
            validation_protocol = methodology.get('validation_protocol', '')

            if 'DAG' in bias_control or '因果' in bias_control:
                st.markdown("""
**因果链结构**:
```
突变/干预 (X) → 方法学改进 (M) → 偏倚降低/因果识别 (Y) → 模型性能提升
```
""")
                hypothesis_statement = f"""**研究假设**:

本研究假设：通过引入**因果推断框架（DAG与混杂因子调整）**结合**Pipeline-封装式机器学习范式**，能够：

1. **显著降低数据穿越偏倚**：通过严格的信息隔离协议，确保测试集统计信息不泄露到训练过程
2. **提高模型因果推断准确性**：通过DAG识别并控制混杂因子，消除虚假关联
3. **提升模型泛化能力**：通过嵌套交叉验证获得无偏的性能估计

**假设检验方法**: {validation_protocol[:100] if validation_protocol else '见方法论详情'}..."""
            else:
                hypothesis_statement = f"""**研究假设**:

{hypothesis.get('title', '该研究提出的新方法')}将显著提升临床预测模型的性能与可靠性。

**假设检验方法**: {validation_protocol[:100] if validation_protocol else '见方法论详情'}..."""

            st.markdown(hypothesis_statement)
            st.markdown("---")

        details = hypothesis.get('details', hypothesis.get('description', ''))
        if details and len(details) > 50:
            st.markdown("### 研究背景")
            st.info(details)

        methodology = hypothesis.get('methodology', {})
        if methodology:
            st.markdown("---")
            st.markdown("### 🔬 方法论")
            if isinstance(methodology, dict):
                for key, value in methodology.items():
                    key_display = {
                        'technical_safeguards': '技术保障', 'validation_protocol': '验证协议',
                        'bias_control': '偏倚控制', 'approach': '技术路径',
                        'statistical_framework': '统计框架', 'cohort_definition': '队列定义',
                        'expected_outcomes': '预期结果', 'innovation_analysis': '创新分析',
                    }.get(key, key)
                    st.markdown(f"**{key_display}**")
                    if isinstance(value, list):
                        for item in value:
                            st.markdown(f"  • {item}")
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            st.markdown(f"  • **{sub_key}**: {sub_value}")
                    else:
                        st.markdown(f"{value}")
                    st.markdown("")
            else:
                st.markdown(str(methodology))

        patch_log = hypothesis.get('patch_log', [])
        if patch_log:
            st.markdown("---")
            st.markdown("### 🔧 演化记录")
            for i, patch in enumerate(patch_log, 1):
                st.markdown(f"**迭代 {i}**: {patch}")

        if fitness:
            st.markdown("---")
            st.markdown("### 📊 混合适应度评估")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总分", f"{fitness.get('hybrid_fitness', 0):.2f}")
            with col2:
                st.metric("创新度", f"{fitness.get('vector_novelty_score', 0):.2f}")
            with col3:
                st.metric("严谨度", f"{fitness.get('red_team_rigor_score', 0):.2f}")
            similarity = fitness.get('similarity_interpretation', '')
            if similarity:
                st.info(f"**创新度分析**: {similarity}")

        audit_context = payload.get('audit_context', {})
        if audit_context:
            st.markdown("---")
            st.markdown("## 【4. Defense Log - 防御日志】")
            iterations = audit_context.get('iterations', 0)
            patches = audit_context.get('patches', 0)
            rewrites = audit_context.get('rewrites', 0)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总迭代次数", iterations)
            with col2:
                st.metric("方法论补丁", patches)
            with col3:
                st.metric("物理重写", rewrites)

            red_attack_types = audit_context.get('red_attack_types', [])
            if red_attack_types:
                st.markdown("---")
                st.markdown("### 红方攻击审计")
                attack_severity = {
                    'Data Leakage': '💀 致命', 'Endogeneity': '💀 致命',
                    'Multiple Testing': '⚠️ 严重', 'Statistical Power': '⚠️ 严重',
                    'Causal Inference': '💀 致命', 'Reproducibility': '⚠️ 严重',
                }
                for attack in red_attack_types:
                    severity = attack_severity.get(attack, '📝 中等')
                    st.markdown(f"**{attack}** | {severity}")

            patch_log = hypothesis.get('patch_log', [])
            if patch_log:
                st.markdown("---")
                st.markdown("### 方法论补丁注入")
                for i, patch in enumerate(patch_log, 1):
                    if isinstance(patch, dict):
                        attack_type = patch.get('attack_type', '未知')
                        patch_applied = patch.get('patch_applied', '')
                        reference = patch.get('supporting_reference', '')
                        st.markdown(f"**迭代 {i}**: {attack_type}")
                        if patch_applied:
                            st.markdown(f"> 补丁措施: {patch_applied}")
                        if reference:
                            st.markdown(f"> 参考文献: {reference}")
                    else:
                        st.markdown(f"**迭代 {i}**: {patch}")
                    st.markdown("")

    with tabs[1]:
        roadmap = payload.get('implementation_roadmap', {})
        if roadmap:
            st.markdown("## 📋 Implementation Roadmap (落地指南)")
            phases = roadmap.get('phases', [])
            if phases:
                st.markdown("### 🎯 阶段规划")
                for phase in phases:
                    phase_name = phase.get('phase', phase.get('name', '未命名阶段'))
                    duration = phase.get('duration', '')
                    milestones = phase.get('milestones', [])
                    deliverables = phase.get('deliverables', [])
                    st.markdown(f"**{phase_name}**")
                    if duration:
                        st.markdown(f"⏱️ *{duration}*")
                    if milestones:
                        st.markdown("**里程碑**:")
                        for ms in milestones:
                            st.markdown(f"  • {ms}")
                    if deliverables:
                        st.markdown("**交付物**:")
                        for d in deliverables:
                            st.markdown(f"  • {d}")
                    st.markdown("")

            resources = roadmap.get('resources', {})
            if resources:
                st.markdown("---")
                st.markdown("### 🔧 资源需求")
                personnel = resources.get('personnel', {})
                if personnel:
                    st.markdown("**👥 人员配置**")
                    for role, detail in personnel.items():
                        if isinstance(detail, dict):
                            st.markdown(f"  • **{role}**: {detail.get('count', detail.get('name', 'N/A'))}")
                        else:
                            st.markdown(f"  • **{role}**: {detail}")
                equipment = resources.get('equipment', {})
                if equipment:
                    st.markdown("**🖥️ 设备需求**")
                    for key, val in equipment.items():
                        if isinstance(val, dict):
                            st.markdown(f"  • **{key}**: {val.get('type', val.get('name', 'N/A'))}")
                        else:
                            st.markdown(f"  • **{key}**: {val}")
                data = resources.get('data', {})
                if data:
                    st.markdown("**📊 数据需求**")
                    for key, val in data.items():
                        st.markdown(f"  • **{key}**: {val}")

            timeline = roadmap.get('timeline', {})
            if timeline:
                st.markdown("---")
                st.markdown("### ⏱️ 时间线")
                st.markdown(f"**总周期**: {timeline.get('total_duration', 'N/A')}")
                milestones = timeline.get('milestones', [])
                if milestones:
                    for ms in milestones:
                        st.markdown(f"  • {ms}")

            risks = roadmap.get('risks', [])
            if risks:
                st.markdown("---")
                st.markdown("### ⚠️ 风险评估")
                for risk in risks:
                    category = risk.get('category', risk.get('type', '未知'))
                    description = risk.get('description', '')
                    mitigation = risk.get('mitigation', '')
                    severity = risk.get('severity', 'medium')
                    severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(severity, '⚪')
                    st.warning(f"{severity_icon} **{category}**")
                    if description:
                        st.markdown(f">{description}")
                    if mitigation:
                        st.markdown(f"*应对策略*: {mitigation}")
                    st.markdown("")

            budget = roadmap.get('budget', {})
            if budget:
                st.markdown("---")
                st.markdown("### 💰 预算估算")
                estimated_total = budget.get('estimated_total', 'N/A')
                if estimated_total:
                    st.metric("预估总成本", estimated_total)
                breakdown = budget.get('breakdown', {})
                if breakdown:
                    st.markdown("**成本明细**:")
                    for item, cost in breakdown.items():
                        st.markdown(f"  • {item}: {cost}")
                note = budget.get('note', '')
                if note:
                    st.info(f"ℹ️ {note}")
        else:
            st.info("暂无落地指南数据")

    with tabs[2]:
        innovation = payload.get('innovation_analysis', {})
        if innovation:
            st.markdown("## 💡 Innovation Analysis (创新分析)")
            core = innovation.get('core_innovations', [])
            if core:
                st.markdown("### 🌟 核心创新点")
                for i, item in enumerate(core, 1):
                    st.markdown(f"**{i}.** {item}")
            novelty = innovation.get('novelty_level')
            if novelty:
                st.markdown("---")
                st.markdown("### 📊 新颖度等级")
                if isinstance(novelty, dict):
                    level = novelty.get('level', 'N/A')
                    score = novelty.get('score', 0)
                    st.metric("等级", level)
                    st.metric("评分", f"{score:.2f}")
                else:
                    level_display = {'breakthrough': '🌟 突破性', 'incremental': '📈 渐进式', 'novel': '💡 原创性'}.get(novelty, novelty)
                    st.metric("等级", level_display)
            diff = innovation.get('differentiation', [])
            if diff:
                st.markdown("---")
                st.markdown("### 🔄 差异化分析")
                for item in diff:
                    st.markdown(f"  • {item}")
            potential = innovation.get('breakthrough_potential')
            if potential:
                st.markdown("---")
                st.markdown("### 🚀 突破潜力")
                if isinstance(potential, dict):
                    st.metric("Science Score", f"{potential.get('science_score', 0):.2f}")
                    st.metric("Promise Score", f"{potential.get('promise_score', 0):.2f}")
                else:
                    st.markdown(f"**突破潜力**: {potential}")
            summary = innovation.get('summary', '')
            if summary:
                st.markdown("---")
                st.markdown("### 📝 总结")
                st.markdown(summary)
        else:
            st.info("暂无创新分析数据")

    with tabs[3]:
        frontier = payload.get('frontier_analysis', {})
        if frontier:
            st.markdown("## 🔬 Frontier Analysis (前沿溯源)")
            position = frontier.get('frontier_position')
            if position:
                st.markdown("### 📍 前沿定位")
                if isinstance(position, dict):
                    st.markdown(f"**2026 SoTA对比**: {position.get('sota_comparison', 'N/A')}")
                    st.markdown(f"**位置**: {position.get('position', 'N/A')}")
                else:
                    st.markdown(f"**前沿定位**: {position}")
            pubs = frontier.get('key_publications', [])
            if pubs:
                st.markdown("---")
                st.markdown("### 📄 关键出版物")
                for pub in pubs[:5]:
                    title = pub.get('title', 'N/A')
                    cite = pub.get('citation_count', 0)
                    st.markdown(f"  • **{title}** (引用: {cite})")
            trends = frontier.get('research_trends', [])
            if trends:
                st.markdown("---")
                st.markdown("### 📈 研究趋势")
                for trend in trends:
                    st.markdown(f"  • {trend}")
            gaps = frontier.get('gap_analysis', [])
            if gaps:
                st.markdown("---")
                st.markdown("### 🔍 研究空白 (Gap Analysis)")
                for gap in gaps:
                    st.markdown(f"  • {gap}")
            citation = frontier.get('citation_velocity')
            year_trend = frontier.get('year_trend')
            if citation or year_trend:
                st.markdown("---")
                st.markdown("### ⚡ 引用速度与趋势")
                if citation:
                    if isinstance(citation, dict):
                        st.metric("年均引用", f"{citation.get('avg_per_year', 0):.1f}")
                        st.metric("增长趋势", f"{citation.get('growth_rate', 0):.1%}")
                    else:
                        st.markdown(f"**引用速度**: {citation}")
                if year_trend:
                    st.markdown(f"**年度趋势**: {year_trend}")
        else:
            st.info("暂无前沿溯源数据")

    with tabs[4]:
        st.markdown(f"""
        <div class="report-container">
            <h3>{hypothesis.get('title', '未命名假设')}</h3>
            <p><strong>学科领域</strong>: {payload.get('domain', 'N/A')}</p>
            <p><strong>版本</strong>: {hypothesis.get('version', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)

        details = hypothesis.get('details', hypothesis.get('description', ''))
        if details:
            st.markdown("### 📋 假设概述")
            st.markdown(f"<div class='report-container'>{details}</div>", unsafe_allow_html=True)

        methodology = hypothesis.get('methodology', {})
        if methodology:
            st.markdown("---")
            st.markdown("### 🔬 方法论")
            if isinstance(methodology, dict):
                for key, value in methodology.items():
                    key_display = {
                        'technical_safeguards': '技术保障', 'validation_protocol': '验证协议',
                        'bias_control': '偏倚控制', 'approach': '技术路径',
                        'statistical_framework': '统计框架', 'cohort_definition': '队列定义',
                        'expected_outcomes': '预期结果', 'innovation_analysis': '创新分析',
                    }.get(key, key)
                    st.markdown(f"**{key_display}**")
                    if isinstance(value, list):
                        for item in value:
                            st.markdown(f"  • {item}")
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            st.markdown(f"  • **{sub_key}**: {sub_value}")
                    else:
                        st.markdown(f"{value}")
                    st.markdown("")
            else:
                st.markdown(str(methodology))

    with tabs[5]:
        literature = payload.get('literature_support', payload.get('literature', {}))
        if literature:
            st.markdown("## 📚 Literature Support (文献支撑)")
            supporting = literature.get('supporting_papers', literature.get('papers', []))
            if isinstance(supporting, list) and supporting:
                for i, paper in enumerate(supporting[:20]):
                    title = paper.get('title', 'N/A')
                    year = paper.get('year', '')
                    journal = paper.get('journal', '')
                    citation_count = paper.get('citation_count', paper.get('citations', 0))
                    relevance = paper.get('relevance', paper.get('relevance_score', ''))
                    with st.expander(f"{i+1}. {title} ({year})"):
                        st.caption(f"**期刊**: {journal or 'N/A'}")
                        st.caption(f"**引用数**: {citation_count}")
                        if relevance:
                            st.caption(f"**相关度**: {relevance}")
                        abstract = paper.get('abstract', '')
                        if abstract:
                            st.write(str(abstract)[:400])
                        doi = paper.get('doi', '')
                        if doi:
                            st.caption(f"DOI: {doi}")
            else:
                st.info("暂无文献支撑详情")
        else:
            st.info("暂无文献支撑数据")

    with tabs[6]:
        st.markdown("## 🧪 实验设计方案")
        st.caption("基于研究方法论自动生成的实验设计框架，供参考调整")

        design = _generate_experiment_design(hypothesis, methodology, fitness)

        # 研究类型
        st.markdown(f"### 📋 研究类型")
        st.markdown(f"**推荐设计**: {design['study_type']}")

        # 样本量估算
        st.markdown("---")
        st.markdown("### 📊 样本量估算")
        sse = design['sample_size_estimation']
        st.markdown(f"**方法**: {sse.get('method', 'N/A')}")
        if 'formula' in sse:
            st.latex(sse['formula'])
        if 'alpha' in sse:
            cols = st.columns(4)
            cols[0].metric("α (I类错误)", sse['alpha'])
            cols[1].metric("Power", sse.get('power', 'N/A'))
            if sse.get('effect_size_small'):
                cols[2].metric("小效应 (d=0.2)", f"n={sse['effect_size_small']['n_per_group']}")
            if sse.get('effect_size_medium'):
                cols[3].metric("中效应 (d=0.5)", f"n={sse['effect_size_medium']['n_per_group']}")
        if sse.get('rule_of_thumb'):
            st.info(f"**经验法则**: {sse['rule_of_thumb']}")
        if sse.get('note'):
            st.caption(f"⚠️ {sse['note']}")

        # 统计方法
        st.markdown("---")
        st.markdown("### 🔢 推荐统计方法")
        for sm in design['statistical_methods']:
            with st.expander(f"📐 {sm['method']}", expanded=False):
                st.markdown(sm['detail'])

        # 效应量指标
        st.markdown("---")
        st.markdown("### 📏 效应量指标")
        for i in range(0, len(design['effect_size_metrics']), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx < len(design['effect_size_metrics']):
                    em = design['effect_size_metrics'][idx]
                    with cols[j]:
                        st.markdown(f"**{em['metric']}**: {em['use']}")

        # 随机化方案
        st.markdown("---")
        st.markdown("### 🎲 随机化方案")
        st.info(design['randomization_protocol'])

        # 盲法策略
        st.markdown("---")
        st.markdown("### 🎭 盲法策略")
        st.info(design['blinding_strategy'])

        # 数据采集计划
        st.markdown("---")
        st.markdown("### 📋 数据采集计划")
        for item in design['data_collection_plan']:
            st.markdown(item)

    # V7.5: 导出 Markdown 报告
    st.markdown("---")
    try:
        markdown_content = _build_markdown_report(result)
        st.download_button(
            label="📥 导出 Markdown 报告",
            data=markdown_content,
            file_name=f"hypothesis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown",
            key="export_md",
            use_container_width=True,
        )
    except Exception as e:
        st.caption(f"导出失败: {e}")


def render_rejection_report(error_info: Dict, user_input: str):
    """拒绝报告渲染 — V7.5 用户友好版"""
    result_type = error_info.get('result_type', error_info.get('type', 'unknown'))
    error_msg = error_info.get('error', error_info.get('message', '未知错误'))

    # 根据错误类型映射用户友好的提示
    ERROR_GUIDE = {
        'PSEUDOSCIENCE': {
            'icon': '🛡️', 'title': '检测到非科学内容',
            'explain': '输入内容包含伪科学信号或无法验证的主张。',
            'actions': [
                '提供具体可测量的研究假设（如明确实验方法、检测指标）',
                '避免使用无法验证的术语或超自然概念',
                '补充具体的实验仪器或检测手段',
            ],
        },
        'REJECTION': {
            'icon': '🚫', 'title': '意图净化器拒绝了请求',
            'explain': '输入内容未通过系统安全审查。',
            'actions': [
                '使用更学术化的语言描述研究问题',
                '确保输入是明确的研究假设而非一般性问题',
                '尝试从侧边栏调整「学科领域」后重新提交',
            ],
        },
        'WORKER_OFFLINE': {
            'icon': '🔌', 'title': 'Worker 服务离线',
            'explain': 'Celery Worker 未运行或已崩溃。',
            'actions': [
                '在终端执行: python -m celery -A src.core.celery_tasks_v75 worker -Q research --loglevel=info --pool=solo',
                '确认 Redis 服务正常运行（侧边栏应显示绿色）',
                '或者刷新页面，系统将自动使用本地执行模式',
            ],
        },
        'local_fallback_error': {
            'icon': '⚠️', 'title': '本地执行失败',
            'explain': '本地同步执行过程中发生错误。',
            'actions': [
                '检查 API Key 是否有效且配额充足',
                '尝试简化研究问题或降低复杂度参数',
                '查看终端错误日志获取详细信息',
            ],
        },
    }

    guide = ERROR_GUIDE.get(result_type, {
        'icon': '❌', 'title': '任务执行失败',
        'explain': error_msg,
        'actions': [
            '刷新页面后重新提交',
            '在侧边栏降低参数后重试（如减少演化迭代次数）',
            '检查 API 服务和网络连接',
        ],
    })

    st.markdown(f"""
    <div class="rejection-card">
        <h2>{guide['icon']} {guide['title']}</h2>
        <p style="color:#94a3b8;">{guide['explain']}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🔧 可尝试的解决方案")
    for i, action in enumerate(guide['actions'], 1):
        st.markdown(f"{i}. {action}")

    with st.expander("🔍 技术详情", expanded=False):
        st.code(error_msg[:500] if error_msg else '无')
        st.caption(f"错误类型: {result_type}")

    st.caption(f"原始输入: {user_input[:200] if len(user_input) > 200 else user_input}")


def render_timeout_report(task_id: str, reason: str, details: Dict):
    """超时报告渲染 — V7.5 用户友好版"""
    reason_guide = {
        'MAX_POLL_EXCEEDED': ('轮询等待超限', '任务处理时间超过预期，前端等待超时。'),
        'GLOBAL_TIMEOUT': ('全局超时', '任务执行时间超过系统上限。'),
        'WORKER_STUCK': ('Worker 卡住', 'Celery Worker 取到任务后无响应，可能已崩溃。'),
        'WORKER_NOT_RESPONDING': ('Worker 无响应', 'Celery Worker 可能已停止运行。'),
        'STATE_STAGNANT': ('任务停滞', '任务长时间处于同一状态无进展。'),
    }

    title, explain = reason_guide.get(reason, (reason, '任务未能在预期时间内完成。'))

    st.markdown(f"""
    <div class="warning-card">
        <h2>⏰ {title}</h2>
        <p style="color:#94a3b8;">{explain}</p>
        <p><code>{task_id[:20]}...</code></p>
    </div>
    """, unsafe_allow_html=True)

    if details:
        elapsed = details.get('elapsed_seconds', details.get('elapsed_minutes', 0) * 60)
        attempts = details.get('poll_attempts', details.get('poll_count', 0))
        last_state = details.get('last_state', 'UNKNOWN')
        cols = st.columns(3)
        cols[0].metric("已等待", f"{elapsed:.0f}秒" if elapsed < 120 else f"{elapsed/60:.1f}分钟")
        cols[1].metric("轮询次数", attempts)
        cols[2].metric("最后状态", last_state)

    st.markdown("### 🔧 常见解决方案")
    solutions = [
        ("🔄 直接重试", "刷新页面后重新提交，大多数超时通过重试即可解决"),
        ("⚙️ 降低复杂度", "在侧边栏减少「最大演化迭代」或「API 调用上限」"),
        ("🔌 检查 Worker", "若使用 Celery，确认 Worker 仍在运行（侧边栏查看状态）"),
        ("📝 简化输入", "缩短研究问题描述，明确核心研究方向"),
    ]
    for sol_title, sol_desc in solutions:
        st.markdown(f"**{sol_title}**：{sol_desc}")


__all__ = [
    'render_phoenix_failure_report',
    'render_success_report',
    'render_rejection_report',
    'render_timeout_report',
]
