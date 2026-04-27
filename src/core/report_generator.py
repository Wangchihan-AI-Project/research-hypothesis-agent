# -*- coding: utf-8 -*-
"""
V7.5 Phoenix Protocol - 详细输出报告生成器

生成类似 DETAILED_OUTPUT_REPORT.md 的 Markdown 格式报告
包含完整的红蓝方对抗详情、方法论、前沿溯源、创新分析等
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class PhoenixReportGenerator:
    """Phoenix 协议详细报告生成器"""

    ATTACK_SEVERITY = {
        'Data Leakage': '💀 致命',
        'Endogeneity': '💀 致命',
        'Multiple Testing': '⚠️ 严重',
        'Statistical Power': '⚠️ 严重',
        'Causal Inference': '💀 致命',
        'Reproducibility': '⚠️ 严重',
        'data_leakage': '💀 致命',
        'endogeneity_confounding': '💀 致命',
        'multiple_testing': '⚠️ 严重',
        'statistical_power': '⚠️ 严重',
        'causal_inference': '💀 致命',
        'reproducibility': '⚠️ 严重',
        '数据穿越': '💀 致命',
        '内生性偏倚': '💀 致命',
        '多重假设检验': '⚠️ 严重',
        '统计功效': '⚠️ 严重',
        '因果推断': '💀 致命',
        '可复现性': '⚠️ 严重',
    }

    def __init__(self, reports_dir: str = "reports"):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(exist_ok=True, parents=True)

    def generate_report(self, task_result: Dict, user_input: str = "") -> str:
        """生成完整的 Markdown 报告"""
        payload = task_result.get('payload', {})
        hypothesis = payload.get('hypothesis', {})
        fitness = payload.get('fitness', {})
        audit_context = payload.get('audit_context', {})
        domain = payload.get('domain', 'auto-detect')
        red_team_report = payload.get('red_team_report', {})
        defense_report = payload.get('defense_report', {})

        task_id = task_result.get('task_id', datetime.now().strftime('%Y%m%d_%H%M%S'))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"phoenix_report_{timestamp}_{task_id[:8]}.md"
        filepath = self.reports_dir / filename

        report_lines = [
            self._generate_header(domain, user_input),
            self._generate_hypothesis_section(hypothesis),
            self._generate_methods_section(hypothesis),
            self._generate_lineage_section(payload),
            self._generate_defense_log_section(audit_context, red_team_report, defense_report, hypothesis),
            self._generate_roadmap_section(payload),
            self._generate_innovation_section(payload),
            self._generate_scoring_section(fitness),
            self._generate_footer(task_result),
        ]

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        return str(filepath)

    def _generate_header(self, domain: str, user_input: str) -> str:
        return f"""# V7.5 Phoenix Protocol - 详细输出报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**学科领域**: {domain}

---

## 用户输入

> {user_input}

---

"""

    def _parse_hypothesis(self, hypothesis: Any) -> Dict:
        if isinstance(hypothesis, dict):
            return hypothesis
        if isinstance(hypothesis, str):
            try:
                return json.loads(hypothesis)
            except (json.JSONDecodeError, TypeError):
                match = re.search(r'```json\s*(.*?)\s*```', hypothesis, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(1))
                    except json.JSONDecodeError:
                        pass
                return {'raw_content': hypothesis}
        return {}

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ''
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, list):
            parts = [self._stringify(item) for item in value]
            return '；'.join([part for part in parts if part])
        if isinstance(value, dict):
            parts = []
            for key, val in value.items():
                text = self._stringify(val)
                if text:
                    parts.append(f"{key}: {text}")
            return '；'.join(parts)
        return str(value).strip()

    def _normalize_list(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return [item for item in value if item not in (None, '', [], {})]
        return [value]

    def _safe_text(self, value: Any) -> str:
        return self._stringify(value).replace('\n', '<br>').replace('|', '\\|')

    def _split_sentences(self, value: Any) -> List[str]:
        text = self._stringify(value)
        if not text:
            return []
        text = text.replace('\r\n', '\n')
        parts = [part.strip(' -•\t') for part in re.split(r'\n+|(?<=。)|(?<=；)', text) if part.strip(' -•\t')]
        return [part for part in parts if part]

    def _extract_table_rows(self, value: Any) -> List[Dict[str, str]]:
        rows = []
        for item in self._normalize_list(value):
            if isinstance(item, dict):
                normalized = {str(k): self._stringify(v) for k, v in item.items() if self._stringify(v)}
                if normalized:
                    rows.append(normalized)
            else:
                text = self._stringify(item)
                if text:
                    rows.append({'内容': text})
        return rows

    def _append_bullets(self, lines: List[str], value: Any, numbered: bool = False) -> None:
        items = self._normalize_list(value)
        counter = 1
        for item in items:
            text = self._stringify(item)
            if not text:
                continue
            prefix = f"{counter}." if numbered else "-"
            lines.append(f"{prefix} {text}")
            counter += 1
        lines.append("")

    def _append_table(self, lines: List[str], rows: List[Dict[str, str]], headers: List[str] = None) -> None:
        if not rows:
            return
        if not headers:
            headers = []
            for row in rows:
                for key in row.keys():
                    if key not in headers:
                        headers.append(key)
        if not headers:
            return
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(['------'] * len(headers)) + "|")
        for row in rows:
            lines.append("| " + " | ".join(self._safe_text(row.get(h, '')) for h in headers) + " |")
        lines.append("")

    def _append_field_block(self, lines: List[str], title: str, value: Any, prefer_table: bool = False, numbered: bool = False) -> None:
        if value in (None, '', [], {}):
            return
        lines.append(f"#### {title}\n")
        if prefer_table:
            rows = self._extract_table_rows(value)
            if rows and not (len(rows) == 1 and list(rows[0].keys()) == ['内容']):
                self._append_table(lines, rows)
                return
        if isinstance(value, dict):
            rows = self._extract_table_rows([value])
            if rows:
                if len(rows[0].keys()) <= 2:
                    normalized_rows = [{'类型': k, '内容': v} for k, v in rows[0].items()]
                    self._append_table(lines, normalized_rows, ['类型', '内容'])
                else:
                    self._append_table(lines, rows)
            return
        if isinstance(value, list):
            dict_items = [item for item in value if isinstance(item, dict)]
            if prefer_table and dict_items:
                self._append_table(lines, self._extract_table_rows(dict_items))
            else:
                self._append_bullets(lines, value, numbered=numbered)
            return
        text = self._stringify(value)
        if text:
            lines.append(text)
            lines.append("")

    def _severity_for_category(self, category: str, fallback: str) -> str:
        return self.ATTACK_SEVERITY.get(category, fallback)

    def _build_defense_paragraph(self, category: str, safeguard: str, committee_response: str) -> str:
        response_parts = self._split_sentences(committee_response)
        response_excerpt = ' '.join(response_parts[:2]) if response_parts else ''
        if response_excerpt and safeguard:
            return f"{safeguard} 结合委员会说明：{response_excerpt}"
        return safeguard or response_excerpt

    def _render_nested_resource(self, key: str, value: Any) -> List[Dict[str, str]]:
        rows = []
        if isinstance(value, dict):
            for sub_key, sub_val in value.items():
                if isinstance(sub_val, dict):
                    rows.append({
                        '资源类型': key,
                        '子类': sub_key,
                        '规格': self._stringify(sub_val)
                    })
                elif isinstance(sub_val, list):
                    rows.append({
                        '资源类型': key,
                        '子类': sub_key,
                        '规格': '；'.join(self._stringify(v) for v in sub_val if self._stringify(v))
                    })
                else:
                    rows.append({
                        '资源类型': key,
                        '子类': sub_key,
                        '规格': self._stringify(sub_val)
                    })
        elif isinstance(value, list):
            rows.append({'资源类型': key, '子类': '-', '规格': '；'.join(self._stringify(v) for v in value if self._stringify(v))})
        else:
            rows.append({'资源类型': key, '子类': '-', '规格': self._stringify(value)})
        return rows

    def _generate_hypothesis_section(self, hypothesis: Any) -> str:
        h_dict = self._parse_hypothesis(hypothesis)
        title = h_dict.get('title', h_dict.get('hypothesis_title', '未命名假设'))
        details = h_dict.get('details', h_dict.get('description', h_dict.get('rationale', '')))
        version = h_dict.get('version', 'v1.0')
        core_hypothesis = h_dict.get('core_hypothesis', '')
        background = h_dict.get('background', h_dict.get('research_background', ''))
        methodology = h_dict.get('methodology', {})

        causal_chain = ""
        if isinstance(methodology, dict):
            bias_control = self._stringify(methodology.get('bias_control', ''))
            causal_chain_input = self._stringify(methodology.get('causal_chain', ''))
            if causal_chain_input:
                causal_chain = f"""
#### 因果链结构
```
{causal_chain_input}
```
"""
            elif 'DAG' in bias_control or '因果' in bias_control:
                causal_chain = """
#### 因果链结构
```
突变/干预 (X) → 方法学改进 (M) → 偏倚降低/因果识别 (Y) → 模型性能提升
```
"""

        research_background = background if background else details
        core_hypothesis_section = ""
        if core_hypothesis:
            core_hypothesis_section = f"""
#### 核心假设陈述
{core_hypothesis}
"""

        return f"""### 【1. Hypothesis - 假设】

#### 标题
**{title}** (_{version}_)

#### 研究背景
{research_background}
{core_hypothesis_section}
{causal_chain}

---

"""

    def _generate_methods_section(self, hypothesis: Any) -> str:
        h_dict = self._parse_hypothesis(hypothesis)
        methodology = h_dict.get('methodology', {})
        if not methodology or not isinstance(methodology, dict):
            for key in ['approach', 'technical_approach', 'design', 'methods']:
                if key in h_dict:
                    methodology = h_dict[key]
                    if isinstance(methodology, dict):
                        break
                    methodology = {'description': methodology}
                    break
            if not methodology or not isinstance(methodology, dict):
                return "### 【2. Methods - 方法论】\n\n暂无详细方法论信息。\n\n---\n\n"

        lines = ["### 【2. Methods - 方法论】\n"]
        self._append_field_block(lines, '数据来源', methodology.get('data_sources', methodology.get('data_source', '')), prefer_table=True)
        self._append_field_block(lines, '分析方法', methodology.get('analysis_methods', methodology.get('analysis_method', methodology.get('approach', ''))), numbered=True)
        self._append_field_block(lines, '验证策略', methodology.get('validation_strategy', methodology.get('validation_protocol', '')), prefer_table=True)
        self._append_field_block(lines, '预期结果', methodology.get('expected_outcomes', methodology.get('expected_results', '')), prefer_table=True)

        other_fields = {
            'technical_safeguards': ('技术保障', True),
            'statistical_framework': ('统计框架', True),
            'cohort_definition': ('队列定义', True),
            'bias_control': ('偏倚控制', True),
        }
        for key, (display_name, prefer_table) in other_fields.items():
            if key in methodology:
                self._append_field_block(lines, display_name, methodology.get(key), prefer_table=prefer_table)

        lines.append("---\n")
        return '\n'.join(lines)

    def _generate_lineage_section(self, payload: Dict) -> str:
        verified_ids = payload.get('verified_ids', {})
        frontier_analysis = payload.get('frontier_analysis', {}) or {}
        sources = payload.get('sources', [])
        lines = ["### 【3. Lineage - 前沿溯源】\n"]

        frontier_position = frontier_analysis.get('frontier_position', frontier_analysis.get('position', ''))
        if frontier_position:
            lines.append("#### 前沿定位\n")
            lines.append(f"**{frontier_position}**\n")

        key_publications = frontier_analysis.get('key_publications', [])
        if key_publications:
            lines.append("#### 关键出版物\n")
            rows = []
            for item in self._normalize_list(key_publications)[:10]:
                if isinstance(item, dict):
                    pmid = item.get('pmid') or item.get('id') or item.get('identifier')
                    pmids = item.get('pmids', [])
                    if not pmid and pmids:
                        pmid = pmids[0]
                    rows.append({
                        'PMID': self._stringify(pmid),
                        '类型': self._stringify(item.get('type', item.get('source', 'PubMed'))) or 'PubMed',
                        '内容': self._stringify(item.get('content', item.get('summary', item.get('title', '作为关键参考文献引用')))) or '作为关键参考文献引用'
                    })
                else:
                    rows.append({'PMID': self._stringify(item), '类型': 'PubMed', '内容': '作为关键参考文献引用'})
            self._append_table(lines, rows, ['PMID', '类型', '内容'])
        else:
            pmids = verified_ids.get('pmids', [])
            if pmids:
                lines.append("#### 关键出版物\n")
                rows = [{'PMID': self._stringify(pmid), '类型': 'PubMed', '内容': '作为关键参考文献引用'} for pmid in pmids[:10]]
                self._append_table(lines, rows, ['PMID', '类型', '内容'])

        research_trends = frontier_analysis.get('research_trends', [])
        if research_trends:
            lines.append("#### 研究趋势\n")
            self._append_bullets(lines, research_trends, numbered=True)

        timeline = frontier_analysis.get('timeline_evolution', frontier_analysis.get('timeline', []))
        if timeline:
            lines.append("#### 时间线演进\n")
            rows = []
            for item in self._normalize_list(timeline)[:8]:
                if isinstance(item, dict):
                    rows.append({
                        '时间段': self._stringify(item.get('period', item.get('time', item.get('year', '')))),
                        '阶段': self._stringify(item.get('stage', item.get('phase', ''))),
                        '描述': self._stringify(item.get('description', item.get('desc', item.get('content', '')))),
                    })
                else:
                    rows.append({'时间段': '', '阶段': '', '描述': self._stringify(item)})
            self._append_table(lines, rows, ['时间段', '阶段', '描述'])

        gap_analysis = frontier_analysis.get('gap_analysis', '')
        if gap_analysis:
            lines.append("#### Gap Analysis\n")
            self._append_bullets(lines, gap_analysis)

        leading_groups = frontier_analysis.get('leading_groups', [])
        if leading_groups:
            lines.append("#### 领先团队\n")
            group_rows = []
            for item in self._normalize_list(leading_groups):
                if isinstance(item, dict):
                    group_rows.append({
                        '类型': self._stringify(item.get('type', 'team')),
                        '内容': self._stringify(item.get('content', item.get('name', ''))),
                        '建议动作': self._stringify(item.get('action', ''))
                    })
                else:
                    group_rows.append({'类型': 'team', '内容': self._stringify(item), '建议动作': ''})
            self._append_table(lines, group_rows, ['类型', '内容', '建议动作'])

        additional_notes = frontier_analysis.get('summary', frontier_analysis.get('context', ''))
        if additional_notes:
            lines.append("#### 前沿解读\n")
            lines.append(self._stringify(additional_notes))
            lines.append("")

        citation_velocity = frontier_analysis.get('citation_velocity', '')
        year_trend = frontier_analysis.get('year_trend', '')
        if citation_velocity or year_trend:
            lines.append("#### 前沿信号\n")
            if citation_velocity:
                lines.append(f"- 引用速度: {self._stringify(citation_velocity)}")
            if year_trend:
                lines.append(f"- 年份趋势: {self._stringify(year_trend)}")
            lines.append("")

        if sources:
            lines.append("#### 数据源\n")
            self._append_bullets(lines, sources)

        lines.append("---\n")
        return '\n'.join(lines)

    def _build_attack_rows(self, items: List[Any], fallback_severity: str) -> List[Dict[str, str]]:
        rows = []
        for item in items:
            if isinstance(item, dict):
                category = self._stringify(item.get('category', item.get('type', '未知')))
                issue = self._stringify(item.get('issue', ''))
                reason = self._stringify(item.get('reason', ''))
                evidence = self._stringify(item.get('evidence', item.get('impact', item.get('details', ''))))
                description_parts = [part for part in [issue, reason, evidence] if part]
                rows.append({
                    '攻击类型': category or '未知',
                    '严重级别': self._severity_for_category(category, fallback_severity),
                    '是否触发': '✅ 触发',
                    '详细描述': ' '.join(description_parts) or '-',
                })
            else:
                category = self._stringify(item) or '未知'
                rows.append({
                    '攻击类型': category,
                    '严重级别': self._severity_for_category(category, fallback_severity),
                    '是否触发': '✅ 触发',
                    '详细描述': '-',
                })
        return rows

    def _build_blue_defense_rows(self, hypothesis: Any, red_team_report: Dict, defense_report: Dict) -> List[Dict[str, str]]:
        h_dict = self._parse_hypothesis(hypothesis)
        methodology = h_dict.get('methodology', {}) if isinstance(h_dict.get('methodology', {}), dict) else {}
        technical_safeguards = self._normalize_list(methodology.get('technical_safeguards', []))
        committee_response = self._stringify(defense_report.get('committee_response', ''))
        committee_discussion = self._stringify(defense_report.get('committee_discussion', ''))
        attack_responses = self._normalize_list(defense_report.get('attack_responses', []))
        recommendations = self._normalize_list(defense_report.get('recommendations', []))
        rows = []

        final_verdict = self._stringify(defense_report.get('final_verdict', defense_report.get('verdict', '')))
        if final_verdict:
            rows.append({'攻击类型': '委员会结论', '答辩要点': final_verdict})

        if committee_response:
            response_lines = self._split_sentences(committee_response)
            if response_lines:
                rows.append({'攻击类型': '总体答辩', '答辩要点': ' '.join(response_lines[:6])})

        if committee_discussion:
            discussion_lines = self._split_sentences(committee_discussion)
            if discussion_lines:
                rows.append({'攻击类型': '委员会讨论', '答辩要点': ' '.join(discussion_lines[:8])})

        for item in attack_responses:
            if not isinstance(item, dict):
                text = self._stringify(item)
                if text:
                    rows.append({'攻击类型': '逐项回应', '答辩要点': text})
                continue
            attack_type = self._stringify(item.get('attack_type', item.get('category', '逐项回应'))) or '逐项回应'
            issue = self._stringify(item.get('issue', ''))
            response = self._stringify(item.get('response', item.get('content', '')))
            paragraph = response
            if issue and response:
                paragraph = f"针对“{issue}”，{response}"
            elif issue:
                paragraph = issue
            if paragraph:
                rows.append({'攻击类型': attack_type, '答辩要点': paragraph})

        red_items = []
        for key in ['critical_flaws', 'severe_issues', 'moderate_concerns']:
            red_items.extend(self._normalize_list(red_team_report.get(key, [])))

        for index, item in enumerate(red_items):
            if not isinstance(item, dict):
                continue
            category = self._stringify(item.get('category', item.get('type', f'问题{index+1}')))
            issue = self._stringify(item.get('issue', ''))
            suggestion = self._stringify(item.get('suggestion', ''))
            safeguard = self._stringify(technical_safeguards[index]) if index < len(technical_safeguards) else ''
            paragraph = self._build_defense_paragraph(category, safeguard, committee_discussion or committee_response)
            if suggestion:
                paragraph = f"{paragraph} 后续修复方向包括：{suggestion}" if paragraph else suggestion
            if issue and paragraph:
                paragraph = f"针对“{issue}”，{paragraph}"
            elif issue:
                paragraph = issue
            if paragraph:
                rows.append({'攻击类型': category, '答辩要点': paragraph})

        for extra_safeguard in technical_safeguards[len(red_items):]:
            rows.append({'攻击类型': '方法论补丁', '答辩要点': self._stringify(extra_safeguard)})

        critical_issues = self._normalize_list(defense_report.get('critical_issues', []))
        for issue in critical_issues:
            rows.append({'攻击类型': '需修复问题', '答辩要点': self._stringify(issue)})

        for recommendation in recommendations[:6]:
            rows.append({'攻击类型': '委员会建议', '答辩要点': self._stringify(recommendation)})

        if not rows:
            rows.extend([
                {'攻击类型': '方法论补丁', '答辩要点': '实施 Pipeline 封装机制，强制特征选择与数据标准化步骤仅在 CV 内部执行。'},
                {'攻击类型': '因果推断', '答辩要点': '引入 DAG 因果框架识别并控制关键混杂因子。'},
            ])

        deduped = []
        seen = set()
        for row in rows:
            marker = (row['攻击类型'], row['答辩要点'])
            if marker in seen or not row['答辩要点']:
                continue
            seen.add(marker)
            deduped.append(row)
        return deduped

    def _build_patch_rows(self, hypothesis: Any, red_team_report: Dict, defense_report: Dict) -> List[Dict[str, str]]:
        h_dict = self._parse_hypothesis(hypothesis)
        patch_log = self._normalize_list(h_dict.get('patch_log', []))
        methodology = h_dict.get('methodology', {}) if isinstance(h_dict.get('methodology', {}), dict) else {}
        technical_safeguards = self._normalize_list(methodology.get('technical_safeguards', []))
        recommendations = self._normalize_list(defense_report.get('recommendations', []))
        rows = []

        for patch in patch_log:
            if not isinstance(patch, dict):
                rows.append({'目标漏洞': '未知', '补丁措施': self._stringify(patch)})
                continue
            attack_type = self._stringify(patch.get('attack_type', patch.get('type', '未知')))
            patch_applied = self._stringify(patch.get('patch_applied', patch.get('measure', patch.get('description', ''))))
            reference = self._stringify(patch.get('supporting_reference', patch.get('reference', '')))
            if reference:
                patch_applied = f"{patch_applied}\n*参考*: {reference}" if patch_applied else f"*参考*: {reference}"
            rows.append({'目标漏洞': attack_type or '未知', '补丁措施': patch_applied})

        if not rows:
            red_categories = []
            for key in ['critical_flaws', 'severe_issues', 'moderate_concerns']:
                for item in self._normalize_list(red_team_report.get(key, [])):
                    if isinstance(item, dict):
                        category = self._stringify(item.get('category', item.get('type', '')))
                        if category and category not in red_categories:
                            red_categories.append(category)
            for index, safeguard in enumerate(technical_safeguards):
                attack_type = red_categories[index] if index < len(red_categories) else '方法论漏洞'
                fix_text = self._stringify(safeguard)
                if index < len(recommendations):
                    fix_text = f"{fix_text}\n*落实建议*: {self._stringify(recommendations[index])}"
                rows.append({'目标漏洞': attack_type, '补丁措施': fix_text})

        return rows

    def _generate_defense_log_section(self, audit_context: Dict, red_team_report: Dict, defense_report: Dict, hypothesis: Any) -> str:
        lines = ["### 【4. Defense Log - 防御日志】\n"]
        iterations = audit_context.get('iterations', 0)
        patches = audit_context.get('patches', 0)
        rewrites = audit_context.get('rewrites', 0)

        lines.append("#### 凤凰协议统计")
        lines.append(f"- 总迭代次数: {iterations}")
        lines.append(f"- 方法论补丁: {patches}")
        lines.append(f"- 物理重写: {rewrites}")
        lines.append("")

        lines.append("#### 红方攻击审计报告（Nature 审稿标准）\n")
        rows = []
        rows.extend(self._build_attack_rows(self._normalize_list(red_team_report.get('critical_flaws', [])), '💀 致命'))
        rows.extend(self._build_attack_rows(self._normalize_list(red_team_report.get('severe_issues', [])), '⚠️ 严重'))
        rows.extend(self._build_attack_rows(self._normalize_list(red_team_report.get('moderate_concerns', [])), '📝 中等'))
        if rows:
            self._append_table(lines, rows, ['攻击类型', '严重级别', '是否触发', '详细描述'])
        else:
            lines.append("暂无红方攻击明细。")
            lines.append("")

        critical_flaws = self._normalize_list(red_team_report.get('critical_flaws', []))
        severe_issues = self._normalize_list(red_team_report.get('severe_issues', []))
        moderate_concerns = self._normalize_list(red_team_report.get('moderate_concerns', []))
        verdict = self._stringify(red_team_report.get('verdict', 'unknown')).upper()
        summary = self._stringify(red_team_report.get('summary', red_team_report.get('overall_assessment', '')))

        lines.append("#### 红方裁决")
        lines.append("```")
        lines.append(f"verdict: {verdict}")
        lines.append(f"overall_severity: {'致命' if critical_flaws else ('严重' if severe_issues else ('中等' if moderate_concerns else '轻微'))}")
        lines.append("```")
        if summary:
            lines.append(summary)
        lines.append("")

        suggestions = []
        for item in critical_flaws + severe_issues + self._normalize_list(red_team_report.get('minor_suggestions', [])):
            if isinstance(item, dict):
                suggestion = self._stringify(item.get('suggestion', ''))
                if suggestion:
                    suggestions.append(suggestion)
            else:
                text = self._stringify(item)
                if text:
                    suggestions.append(text)
        for recommendation in self._normalize_list(defense_report.get('recommendations', [])):
            text = self._stringify(recommendation)
            if text:
                suggestions.append(text)
        suggestions = list(dict.fromkeys(suggestions))

        if suggestions:
            lines.append("#### 红方建议")
            for index, suggestion in enumerate(suggestions[:10], 1):
                lines.append(f"{index}. {suggestion}")
            lines.append("")

        if defense_report:
            lines.append("---\n")
            lines.append("#### 蓝方答辩报告\n")
            blue_rows = self._build_blue_defense_rows(hypothesis, red_team_report, defense_report)
            self._append_table(lines, blue_rows, ['攻击类型', '答辩要点'])

            lines.append("#### 蓝方裁决")
            lines.append("```")
            lines.append(f"defense_passed: {'TRUE' if defense_report.get('defense_passed', False) else 'FALSE'}")
            confidence = defense_report.get('confidence', defense_report.get('physical_feasibility_score', 0))
            lines.append(f"confidence_score: {float(confidence):.1f}/10")
            lines.append("```")
            lines.append("")

        patch_rows = self._build_patch_rows(hypothesis, red_team_report, defense_report)
        if patch_rows:
            lines.append("---\n")
            lines.append("#### 方法论补丁注入\n")
            self._append_table(lines, patch_rows, ['目标漏洞', '补丁措施'])

        lines.append("---\n")
        return '\n'.join(lines)

    def _generate_roadmap_section(self, payload: Dict) -> str:
        roadmap = payload.get('implementation_roadmap', {})
        if not roadmap:
            return "### 【5. Roadmap - 实施路线图】\n\n暂无路线图信息。\n\n---\n\n"

        lines = ["### 【5. Roadmap - 实施路线图】\n"]

        phases = roadmap.get('phases', [])
        if phases:
            lines.append("#### 实施阶段\n")
            rows = []
            for phase in self._normalize_list(phases):
                if not isinstance(phase, dict):
                    rows.append({'阶段': self._stringify(phase), '时间': '', '关键任务': '', '交付物': ''})
                    continue
                rows.append({
                    '阶段': self._stringify(phase.get('phase', phase.get('name', '未命名'))),
                    '时间': self._stringify(phase.get('duration', phase.get('timeline', '-'))),
                    '关键任务': self._stringify(phase.get('milestones', phase.get('tasks', []))),
                    '交付物': self._stringify(phase.get('deliverables', phase.get('outputs', []))),
                })
            self._append_table(lines, rows, ['阶段', '时间', '关键任务', '交付物'])

        timeline = roadmap.get('timeline', {})
        if timeline:
            lines.append("#### 项目时间线\n")
            timeline_rows = [{'项目': key, '说明': self._stringify(value)} for key, value in timeline.items() if self._stringify(value)]
            self._append_table(lines, timeline_rows, ['项目', '说明'])

        resources = roadmap.get('resources', {})
        if resources:
            lines.append("#### 资源需求\n")
            resource_rows = []
            if isinstance(resources, dict):
                for key, value in resources.items():
                    resource_rows.extend(self._render_nested_resource(key, value))
            else:
                resource_rows.extend(self._render_nested_resource('资源', resources))
            self._append_table(lines, resource_rows, ['资源类型', '子类', '规格'])

        budget = roadmap.get('budget', {})
        if budget:
            lines.append("#### 预算估算\n")
            budget_rows = [{'项目': key, '说明': self._stringify(value)} for key, value in budget.items() if self._stringify(value)]
            self._append_table(lines, budget_rows, ['项目', '说明'])

        feasibility_notes = roadmap.get('feasibility_notes', [])
        if feasibility_notes:
            lines.append("#### 可行性备注\n")
            self._append_bullets(lines, feasibility_notes)

        risks = roadmap.get('risks', [])
        if risks:
            lines.append("#### 风险评估\n")
            rows = []
            for risk in self._normalize_list(risks):
                if isinstance(risk, dict):
                    category = self._stringify(risk.get('category', risk.get('type', risk.get('risk', '未知'))))
                    description = self._stringify(risk.get('description', ''))
                    severity = self._stringify(risk.get('severity', risk.get('level', '中')))
                    mitigation = self._stringify(risk.get('mitigation', risk.get('response', risk.get('strategy', ''))))
                    display_name = f"{category} ({description})" if description else category
                    rows.append({'风险': display_name, '级别': severity, '应对策略': mitigation})
                else:
                    rows.append({'风险': self._stringify(risk), '级别': '中', '应对策略': ''})
            self._append_table(lines, rows, ['风险', '级别', '应对策略'])

        lines.append("---\n")
        return '\n'.join(lines)

    def _generate_innovation_section(self, payload: Dict) -> str:
        innovation = payload.get('innovation_analysis', {}) or {}
        if not innovation:
            return "### 【6. Innovation - 创新点分析】\n\n暂无创新点分析信息。\n\n---\n\n"

        lines = ["### 【6. Innovation - 创新点分析】\n"]
        summary = innovation.get('summary', '')
        if summary:
            lines.append("#### 创新总结\n")
            lines.append(self._stringify(summary))
            lines.append("")

        core_innovations = innovation.get('core_innovations', [])
        if core_innovations:
            lines.append("#### 核心创新点\n")
            rows = []
            for item in self._normalize_list(core_innovations):
                if isinstance(item, dict):
                    rows.append({
                        '创新点': self._stringify(item.get('title', item.get('name', item.get('innovation', '')))) or '核心创新',
                        '说明': self._stringify(item.get('description', item.get('content', item.get('details', ''))))
                    })
                else:
                    rows.append({'创新点': '核心创新', '说明': self._stringify(item)})
            self._append_table(lines, rows, ['创新点', '说明'])

        differentiation = innovation.get('differentiation', [])
        if differentiation:
            lines.append("#### 差异化价值\n")
            self._append_bullets(lines, differentiation)

        vector_analysis = innovation.get('vector_analysis', {})
        if vector_analysis:
            lines.append("#### 向量创新分析\n")
            rows = [{'项目': key, '说明': self._stringify(value)} for key, value in vector_analysis.items() if self._stringify(value)]
            self._append_table(lines, rows, ['项目', '说明'])

        methodology_analysis = innovation.get('methodology_analysis', {})
        if methodology_analysis:
            lines.append("#### 方法论创新分析\n")
            rows = [{'项目': key, '说明': self._stringify(value)} for key, value in methodology_analysis.items() if self._stringify(value)]
            self._append_table(lines, rows, ['项目', '说明'])

        breakthrough_potential = innovation.get('breakthrough_potential', {})
        if breakthrough_potential:
            lines.append("#### 突破潜力评估\n")
            rows = [{'项目': key, '说明': self._stringify(value)} for key, value in breakthrough_potential.items() if self._stringify(value)]
            self._append_table(lines, rows, ['项目', '说明'])

        lines.append("---\n")
        return '\n'.join(lines)

    def _generate_scoring_section(self, fitness: Dict) -> str:
        if not fitness:
            return "### 【评分汇总】\n\n暂无评分信息。\n\n---\n\n"

        lines = ["### 【评分汇总】\n"]
        lines.append("| 指标 | 数值 | 解释 |")
        lines.append("|------|------|------|")
        hybrid_fitness = fitness.get('hybrid_fitness', 0)
        lines.append(f"| **Science Score (Hybrid Fitness)** | **{hybrid_fitness:.2f}** | {self._get_score_interpretation(hybrid_fitness)} |")
        novelty = fitness.get('vector_novelty_score', 0)
        lines.append(f"| **向量创新分 (Vector Novelty)** | {novelty:.2f} | {self._get_novelty_interpretation(novelty)} |")
        rigor = fitness.get('red_team_rigor_score', 0)
        lines.append(f"| **红方严谨分 (Red Team Rigor)** | {rigor:.2f} | Nature 审稿标准 |")
        similarity = fitness.get('similarity', 0)
        similarity_interp = fitness.get('similarity_interpretation', '')
        lines.append(f"| **相似度 (Similarity)** | {similarity:.3f} | {similarity_interp} |")
        physical_validation = fitness.get('physical_validation', {})
        if physical_validation:
            passed = physical_validation.get('passed', True)
            physical_status = "Passed" if passed else f"Failed: {physical_validation.get('failure_reason', '未知')}"
            lines.append(f"| **物理验证** | {physical_status} | 无伪科学模式 |")
        lines.append("")
        lines.append("---\n")
        return '\n'.join(lines)

    def _generate_footer(self, task_result: Dict) -> str:
        task_id = task_result.get('task_id', 'N/A')
        duration = task_result.get('duration', 0)
        state = task_result.get('state', 'UNKNOWN')
        return f"""---

## 附录

| 项目 | 值 |
|------|-----|
| 任务 ID | {task_id} |
| 最终状态 | {state} |
| 总耗时 | {duration:.2f} 秒 |
| 报告生成时间 | {datetime.now().isoformat()} |

---

**本报告由 V7.5 Phoenix Protocol 自动生成**
"""

    def _get_score_interpretation(self, score: float) -> str:
        if score >= 9.0:
            return "卓越 - 接近完美的研究假设"
        if score >= 8.5:
            return "优秀 - 达到成功阈值"
        if score >= 7.5:
            return "良好 - 有改进空间"
        if score >= 6.0:
            return "及格 - 需要大幅改进"
        return "不及格 - 建议重新设计"

    def _get_novelty_interpretation(self, score: float) -> str:
        if score >= 9.5:
            return "突破性创新"
        if score >= 8.0:
            return "高创新性"
        if score >= 6.0:
            return "中等创新性"
        return "低创新性"


def generate_phoenix_report(task_result: Dict, user_input: str = "") -> str:
    generator = PhoenixReportGenerator()
    return generator.generate_report(task_result, user_input)


if __name__ == '__main__':
    pass
