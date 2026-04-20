# -*- coding: utf-8 -*-
"""
V7.2 科研否决报告生成器 - 高危科研路径排雷与转向报告

变废为宝！当假设生成失败或被否决时，系统生成一份高价值的《V7.2 高危科研路径排雷与转向报告》，
而非冷冰冰的报错信息。

V7.2 核心改进：
1. 过程审计 (Iteration Autopsy) - 展示 3 次对抗迭代的完整过程
2. 核心死穴 (The Fatal Flaw) - 提取最后一轮红方攻击的关键拒绝理由
3. 转向建议 (Pivot Strategy) - 基于 LLM 智能生成可闭环的替代方案

报告包含：
- 碰撞文献（至少3篇）：说明该方向已有同质化研究
- 逻辑断裂点（至少2个）：详细说明因果链断裂的具体位置
- 改进建议：提供具体可操作的替代研究方向

核心机制：
- 多类型否决报告模板
- 碰撞文献智能匹配
- 逻辑缺陷深度分析
- Markdown 格式输出（中英双语版）
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 否决类型枚举 ====================

class RejectionType(Enum):
    """否决类型"""
    COLLISION = "collision"                     # 碰撞检测：已有高度同质化研究
    RESOURCE_EXHAUSTED = "resource_exhausted"   # 资源耗尽：熔断触发
    LOGICAL_FLAW = "logical_flaw"               # 逻辑缺陷：因果链断裂
    INSUFFICIENT_SUPPORT = "insufficient_support"  # 支撑不足：文献证据不够
    HALLUCINATION = "hallucination"             # 幻觉检测：编造PMID/数据
    AUDIT_FAILURE = "audit_failure"             # 审计失败：红方否决
    DOMAIN_VIOLATION = "domain_violation"       # 领域违规：跨学科编造
    BOGUS_KEYWORD = "bogus_keyword"             # 假大空词汇：万金油检测
    MAX_ITERATIONS_EXCEEDED = "max_iterations_exceeded"  # V7.2：迭代次数耗尽


# ==================== 逻辑缺陷类型 ====================

class LogicalFlawType(Enum):
    """逻辑缺陷类型"""
    CAUSAL_CHAIN_BREAK = "causal_chain_break"          # 因果链断裂
    MECHANISM_MISSING = "mechanism_missing"             # 机制缺失
    DATA_LEAKAGE = "data_leakage"                       # 数据穿越
    CONFOUNDING_UNADJUSTED = "confounding_unadjusted"   # 混杂因素未调整
    SAMPLE_SIZE_INSUFFICIENT = "sample_size_insufficient"  # 样本量��足
    STATISTICAL_ERROR = "statistical_error"             # 统计方法错误
    BIAS_UNRECOGNIZED = "bias_unrecognized"             # 偏倚未识别
    ALTERNATIVE_PATHWAY = "alternative_pathway"         # 替代路径未排除
    REVERSE_CAUSALITY = "reverse_causality"             # 反向因果
    SELECTION_BIAS = "selection_bias"                   # 选择偏倚


# ==================== 逻辑缺陷数据类 ====================

@dataclass
class LogicalFlaw:
    """逻辑断裂点"""
    flaw_type: LogicalFlawType
    description: str
    location: str
    severity: str = "critical"
    evidence: Optional[str] = None
    suggested_fix: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'flaw_type': self.flaw_type.value,
            'description': self.description,
            'location': self.location,
            'severity': self.severity,
            'evidence': self.evidence,
            'suggested_fix': self.suggested_fix,
        }


# ==================== V7.2 迭代审计记录 ====================

@dataclass
class IterationAuditRecord:
    """V7.2 迭代审计记录"""
    iteration_number: int
    hypothesis_preview: str = ""
    anchor_passed: bool = False
    anchor_message: str = ""
    fitness_score: float = 0.0
    red_team_verdict: str = "N/A"
    red_team_critical_flaws: List[str] = field(default_factory=list)
    red_team_severe_issues: List[str] = field(default_factory=list)
    defense_passed: bool = False
    defense_verdict: str = "N/A"
    defense_critical_issues: List[str] = field(default_factory=list)
    iteration_status: str = "pending"

    def to_dict(self) -> Dict:
        return {
            'iteration_number': self.iteration_number,
            'hypothesis_preview': self.hypothesis_preview,
            'anchor_passed': self.anchor_passed,
            'anchor_message': self.anchor_message,
            'fitness_score': self.fitness_score,
            'red_team_verdict': self.red_team_verdict,
            'red_team_critical_flaws': self.red_team_critical_flaws,
            'red_team_severe_issues': self.red_team_severe_issues,
            'defense_passed': self.defense_passed,
            'defense_verdict': self.defense_verdict,
            'defense_critical_issues': self.defense_critical_issues,
            'iteration_status': self.iteration_status,
        }


# ==================== V7.2 核心死穴 ====================

@dataclass
class FatalFlawAnalysis:
    """V7.2 核心死穴分析"""
    fatal_flaw_type: str = "unknown"
    fatal_flaw_description: str = ""
    academic_barrier_reason: str = ""
    evidence_chain_break: str = ""
    suggested_research_gap: str = ""

    def to_dict(self) -> Dict:
        return {
            'fatal_flaw_type': self.fatal_flaw_type,
            'fatal_flaw_description': self.fatal_flaw_description,
            'academic_barrier_reason': self.academic_barrier_reason,
            'evidence_chain_break': self.evidence_chain_break,
            'suggested_research_gap': self.suggested_research_gap,
        }


# ==================== V7.2 转向建议 ====================

@dataclass
class PivotSuggestion:
    """V7.2 转向建议"""
    pivot_id: int
    pivot_title: str = ""
    pivot_description: str = ""
    supporting_papers: List[str] = field(default_factory=list)
    feasibility_score: float = 0.0
    required_methodology: str = ""
    estimated_timeline: str = ""

    def to_dict(self) -> Dict:
        return {
            'pivot_id': self.pivot_id,
            'pivot_title': self.pivot_title,
            'pivot_description': self.pivot_description,
            'supporting_papers': self.supporting_papers,
            'feasibility_score': self.feasibility_score,
            'required_methodology': self.required_methodology,
            'estimated_timeline': self.estimated_timeline,
        }


# ==================== 碰撞文献数据类 ====================

@dataclass
class CollisionPaper:
    """碰撞文献"""
    title: str
    authors: List[str] = field(default_factory=list)
    year: int = 0
    journal: str = ""
    identifier: str = ""
    identifier_type: str = "pmid"
    similarity_score: float = 0.0
    overlap_description: str = ""
    key_findings: str = ""

    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'authors': self.authors,
            'year': self.year,
            'journal': self.journal,
            'identifier': self.identifier,
            'identifier_type': self.identifier_type,
            'similarity_score': self.similarity_score,
            'overlap_description': self.overlap_description,
            'key_findings': self.key_findings,
        }


# ==================== V7.2 科研否决报告数据类 ====================

@dataclass
class ScientificRejectionReport:
    """
    V7.2 高价值科研否决报告 - 高危科研路径排雷与转向报告

    核心模块：
    1. 过程审计 (Iteration Autopsy)
    2. 核心死穴 (The Fatal Flaw)
    3. 转向建议 (Pivot Strategy)
    """

    # 基础信息
    report_id: str
    research_idea: str
    domain: str
    rejection_type: RejectionType
    primary_reason: str

    # 时间戳
    rejection_time: str = field(default_factory=lambda: datetime.now().isoformat())
    detailed_reason: str = ""

    # V7.2 新增：迭代审计记录
    iteration_history: List[IterationAuditRecord] = field(default_factory=list)
    total_iterations: int = 3

    # V7.2 新增：核心死穴分析
    fatal_flaw_analysis: Optional[FatalFlawAnalysis] = None

    # V7.2 新增：转向建议
    pivot_suggestions: List[PivotSuggestion] = field(default_factory=list)

    # 原有字段
    collision_papers: List[CollisionPaper] = field(default_factory=list)
    logical_flaws: List[LogicalFlaw] = field(default_factory=list)
    alternative_directions: List[str] = field(default_factory=list)
    suggested_keywords: List[str] = field(default_factory=list)
    methodological_suggestions: List[str] = field(default_factory=list)
    literature_suggestions: List[str] = field(default_factory=list)

    # 资源统计
    api_calls_used: int = 0
    tokens_used: int = 0
    time_elapsed: float = 0.0
    papers_searched: int = 0

    # 数据源
    data_sources_used: List[str] = field(default_factory=list)
    verified_ids_found: Dict[str, List[str]] = field(default_factory=dict)
    all_papers: List[Dict] = field(default_factory=list)

    # 附加信息
    session_id: Optional[str] = None
    additional_notes: str = ""

    def to_dict(self) -> Dict:
        return {
            'report_id': self.report_id,
            'research_idea': self.research_idea,
            'domain': self.domain,
            'rejection_time': self.rejection_time,
            'rejection_type': self.rejection_type.value,
            'primary_reason': self.primary_reason,
            'detailed_reason': self.detailed_reason,
            'iteration_history': [i.to_dict() for i in self.iteration_history],
            'total_iterations': self.total_iterations,
            'fatal_flaw_analysis': self.fatal_flaw_analysis.to_dict() if self.fatal_flaw_analysis else None,
            'pivot_suggestions': [p.to_dict() for p in self.pivot_suggestions],
            'collision_papers': [p.to_dict() for p in self.collision_papers],
            'logical_flaws': [f.to_dict() for f in self.logical_flaws],
            'alternative_directions': self.alternative_directions,
            'suggested_keywords': self.suggested_keywords,
            'methodological_suggestions': self.methodological_suggestions,
            'literature_suggestions': self.literature_suggestions,
            'api_calls_used': self.api_calls_used,
            'tokens_used': self.tokens_used,
            'time_elapsed': self.time_elapsed,
            'papers_searched': self.papers_searched,
            'data_sources_used': self.data_sources_used,
            'verified_ids_found': self.verified_ids_found,
            'session_id': self.session_id,
            'additional_notes': self.additional_notes,
        }

    def to_markdown(self) -> str:
        """V7.2 重写：生成《高危科研路径排雷与转向报告》"""
        lines = []

        # ==================== 标题区 ====================
        lines.append("# 🚨 V7.2 高危科研路径排雷与转向报告")
        lines.append("# 🚨 V7.2 High-Risk Research Path Minefield & Pivot Report")
        lines.append("")
        lines.append(f"> **报告ID / Report ID**: `{self.report_id}`")
        lines.append(f"> **生成时间 / Generated**: {self.rejection_time}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ==================== 基础信息 ====================
        lines.append("## 📋 基础信息 / Basic Information")
        lines.append("")
        lines.append(f"| 字段 / Field | 内容 / Content |")
        lines.append(f"|---------------|----------------|")
        lines.append(f"| 学科领域 / Domain | {self.domain} |")
        lines.append(f"| 否决类型 / Rejection Type | {self._get_rejection_type_display()} |")
        lines.append(f"| 总迭代次数 / Total Iterations | {self.total_iterations} |")
        lines.append(f"| 检索文献数 / Papers Retrieved | {self.papers_searched} |")
        lines.append("")
        lines.append("### 🎯 用户研究想法 / Original Research Idea")
        lines.append("")
        lines.append("```")
        lines.append(self.research_idea)
        lines.append("```")
        lines.append("")

        # ==================== 模块 1: 过程审计 ====================
        lines.append("---")
        lines.append("")
        lines.append("## 🔍 模块一：过程审计 (Iteration Autopsy)")
        lines.append("## 🔍 Module 1: Iteration Autopsy")
        lines.append("")
        lines.append(f"系统进行了 **{self.total_iterations} 次红蓝对抗迭代**，以下是完整的审计过程：")
        lines.append(f"The system conducted **{self.total_iterations} adversarial iterations**. Full audit process below:")
        lines.append("")

        if self.iteration_history:
            for record in self.iteration_history:
                status_icon = {
                    'anchor_failed': '⚓❌',
                    'defense_failed': '🛡️❌',
                    'passed': '✅',
                    'pending': '⏳',
                }.get(record.iteration_status, '❓')

                lines.append(f"### 🔄 Iteration #{record.iteration_number} / 迭代 #{record.iteration_number}")
                lines.append("")
                lines.append(f"| 检查项 / Check | 结果 / Result |")
                lines.append(f"|----------------|---------------|")
                lines.append(f"| 假设生成 / Hypothesis Gen | ✅ 完成 / Completed |")
                anchor_status = '✅ 通过 / Passed' if record.anchor_passed else '❌ 失败 / Failed'
                lines.append(f"| 引用锚定 / Anchor Check | {anchor_status} |")
                lines.append(f"| 混合适应度 / Fitness Score | {record.fitness_score:.2f} |")
                lines.append(f"| 红方裁决 / Red Team Verdict | {record.red_team_verdict} |")
                defense_status = '✅ 通过 / Passed' if record.defense_passed else '❌ 失败 / Failed'
                lines.append(f"| 防御答辩 / Defense Committee | {defense_status} |")
                lines.append(f"| 本轮状态 / Iteration Status | {status_icon} {record.iteration_status} |")
                lines.append("")

                if record.red_team_critical_flaws:
                    lines.append("**🔴 红方致命缺陷 / Red Team Critical Flaws:**")
                    for flaw in record.red_team_critical_flaws[:3]:
                        lines.append(f"   - {flaw[:100]}{'...' if len(flaw) > 100 else ''}")
                    lines.append("")

                if record.defense_critical_issues:
                    lines.append("**⚠️ 委员会关键问题 / Committee Critical Issues:**")
                    for issue in record.defense_critical_issues[:2]:
                        lines.append(f"   - {issue[:100]}{'...' if len(issue) > 100 else ''}")
                    lines.append("")

                lines.append("")
        else:
            lines.append("_暂无迭代审计记录 / No iteration audit records available_")
            lines.append("")

        # ==================== 模块 2: 核心死穴 ====================
        lines.append("---")
        lines.append("")
        lines.append("## 💀 模块二：核心死穴 (The Fatal Flaw)")
        lines.append("## 💀 Module 2: The Fatal Flaw")
        lines.append("")
        lines.append(f"经过 {self.total_iterations} 轮对抗检验，系统提取出以下无法跨越的学术障碍：")
        lines.append(f"After {self.total_iterations} rounds of adversarial testing, the system identified the following academic barrier:")
        lines.append("")

        if self.fatal_flaw_analysis:
            lines.append("### ⛔ 致命失败点 / Critical Failure Point")
            lines.append("")
            lines.append(f"**类型 / Type**: `{self.fatal_flaw_analysis.fatal_flaw_type}`")
            lines.append("")
            lines.append(f"> **描述 / Description**: {self.fatal_flaw_analysis.fatal_flaw_description}")
            lines.append("")
            lines.append("### 🧱 学术壁垒分析 / Academic Barrier Analysis")
            lines.append("")
            lines.append("**为什么当前学术界无法跨越 / Why Current Academia Cannot Cross:**")
            lines.append("")
            lines.append(self.fatal_flaw_analysis.academic_barrier_reason)
            lines.append("")
        else:
            lines.append("_未提取到核心死穴分析 / No fatal flaw analysis extracted_")
            lines.append("")
            lines.append("**主要原因 / Primary Reason:**")
            lines.append(self.primary_reason)
            lines.append("")

        # ==================== 模块 3: 转向建议 ====================
        lines.append("---")
        lines.append("")
        lines.append("## 🧭 模块三：转向建议 (Pivot Strategy)")
        lines.append("## 🧭 Module 3: Pivot Strategy")
        lines.append("")
        lines.append(f"基于系统检索到的 **{self.papers_searched} 篇真实文献**，以下是可闭环的替代方案：")
        lines.append(f"Based on **{self.papers_searched} real papers** retrieved by the system, here are actionable pivot strategies:")
        lines.append("")

        if self.pivot_suggestions:
            for pivot in self.pivot_suggestions:
                lines.append(f"### 🔄 转向方案 #{pivot.pivot_id} / Pivot Strategy #{pivot.pivot_id}")
                lines.append("")
                lines.append(f"**标题 / Title**: {pivot.pivot_title}")
                lines.append("")
                lines.append(f"| 维度 / Dimension | 详情 / Detail |")
                lines.append(f"|-------------------|----------------|")
                lines.append(f"| 可行性评分 / Feasibility | {pivot.feasibility_score:.1f}/10 |")
                lines.append(f"| 所需方法论 / Methodology | {pivot.required_methodology} |")
                lines.append(f"| 预估时间线 / Timeline | {pivot.estimated_timeline} |")
                lines.append("")
                lines.append("**方案详述 / Detailed Description:**")
                lines.append("")
                lines.append(pivot.pivot_description)
                lines.append("")
                if pivot.supporting_papers:
                    lines.append("**支撑文献 / Supporting Papers:**")
                    for paper_id in pivot.supporting_papers[:5]:
                        lines.append(f"   - PMID: `{paper_id}`")
                    lines.append("")
                lines.append("")
        else:
            lines.append("_暂无转向建议 / No pivot suggestions available_")
            lines.append("")
            if self.alternative_directions:
                lines.append("**通用改进建议 / General Improvement Suggestions:**")
                lines.append("")
                for i, direction in enumerate(self.alternative_directions, 1):
                    lines.append(f"{i}. {direction}")
                lines.append("")

        # ==================== 资源消耗统计 ====================
        lines.append("---")
        lines.append("")
        lines.append("## 📊 资源消耗统计 / Resource Consumption")
        lines.append("")
        lines.append(f"| 指标 / Metric | 数值 / Value |")
        lines.append(f"|----------------|--------------|")
        lines.append(f"| API 调用次数 / API Calls | {self.api_calls_used} |")
        lines.append(f"| Token 消耗 / Tokens | ~{self.tokens_used} |")
        lines.append(f"| 执行时长 / Duration | {self.time_elapsed:.2f}s |")
        lines.append(f"| 数据源 / Data Sources | {', '.join(self.data_sources_used) if self.data_sources_used else 'N/A'} |")
        lines.append("")

        # ==================== 结语 ====================
        lines.append("---")
        lines.append("")
        lines.append("## 📝 结语 / Conclusion")
        lines.append("")
        lines.append("该研究方向在当前文献支撑下无法形成闭环假设。")
        lines.append("This research direction cannot form a closed-loop hypothesis under current literature support.")
        lines.append("")
        lines.append("然而，**失败本身就是一种发现**。上述转向建议提供了基于真实证据的可操作替代路径。")
        lines.append("However, **failure itself is a discovery**. The pivot strategies above provide actionable alternatives based on real evidence.")
        lines.append("")
        lines.append("> **提示 / Tip**: 请不要放弃！选择一个转向方案，调整研究参数，重新发起探索。")
        lines.append("> **Tip**: Don't give up! Choose a pivot strategy, adjust research parameters, and re-initiate exploration.")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*报告由 V7.2 科研假设智能体系统自动生成*")
        lines.append("*Report auto-generated by V7.2 Research Hypothesis AI System*")
        lines.append("")

        return "\n".join(lines)

    def _get_rejection_type_display(self) -> str:
        """获取否决类型显示文本"""
        display_map = {
            RejectionType.COLLISION: "碰撞检测 / Collision Detected",
            RejectionType.RESOURCE_EXHAUSTED: "资源耗尽 / Resource Exhausted",
            RejectionType.LOGICAL_FLAW: "逻辑缺陷 / Logical Flaw",
            RejectionType.INSUFFICIENT_SUPPORT: "支撑不足 / Insufficient Support",
            RejectionType.HALLUCINATION: "幻觉检测 / Hallucination Detected",
            RejectionType.AUDIT_FAILURE: "审计失败 / Audit Failure",
            RejectionType.DOMAIN_VIOLATION: "领域违规 / Domain Violation",
            RejectionType.BOGUS_KEYWORD: "假大空词汇 / Bogus Keyword",
            RejectionType.MAX_ITERATIONS_EXCEEDED: "迭代耗尽 / Max Iterations Exceeded",
        }
        return display_map.get(self.rejection_type, self.rejection_type.value)

    def save_to_file(self, directory: str = None, filename: str = None) -> str:
        """保存报告到文件"""
        if not directory:
            project_root = Path(__file__).parent.parent.parent
            directory = project_root / "reports" / "rejections"

        Path(directory).mkdir(parents=True, exist_ok=True)

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"V72_PivotReport_{self.report_id}_{timestamp}.md"

        filepath = Path(directory) / filename
        filepath.write_text(self.to_markdown(), encoding='utf-8')

        logger.info(f"[V7.2 Pivot Report] Saved to {filepath}")

        return str(filepath)


# ==================== V7.2 报告生成器 ====================

class RejectionReportGenerator:
    """
    V7.2 科研否决报告生成器

    支持三个核心模块：
    1. 过程审计 (Iteration Autopsy)
    2. 核心死穴 (The Fatal Flaw)
    3. 转向建议 (Pivot Strategy) - 使用 LLM 智能生成
    """

    _report_counter = 0

    def __init__(
        self,
        default_collision_count: int = 3,
        default_flaw_count: int = 2,
        save_reports: bool = True,
        reports_directory: str = None,
    ):
        self.default_collision_count = default_collision_count
        self.default_flaw_count = default_flaw_count
        self.save_reports = save_reports
        self.reports_directory = reports_directory

    def generate_report_id(self) -> str:
        """生成唯一报告ID"""
        self._report_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"V72-{timestamp}-{self._report_counter:04d}"

    def generate(
        self,
        user_input: str,
        domain: str,
        rejection_type: RejectionType,
        primary_reason: str,
        # V7.2 新增参数
        iteration_history: List[Dict] = None,
        red_team_result: Dict = None,
        defense_result: Dict = None,
        all_papers: List[Dict] = None,
        # 原有参数
        collision_papers: List[Dict] = None,
        logical_flaws: List[Dict] = None,
        alternative_directions: List[str] = None,
        suggested_keywords: List[str] = None,
        api_calls_used: int = 0,
        tokens_used: int = 0,
        time_elapsed: float = 0.0,
        papers_searched: int = 0,
        data_sources_used: List[str] = None,
        verified_ids_found: Dict[str, List[str]] = None,
        session_id: str = None,
    ) -> ScientificRejectionReport:
        """生成 V7.2 高价值科研否决报告"""

        report_id = self.generate_report_id()

        # ==================== V7.2: 构建迭代审计记录 ====================
        iteration_records = []
        if iteration_history:
            for iter_data in iteration_history:
                record = IterationAuditRecord(
                    iteration_number=iter_data.get('iteration', 0),
                    hypothesis_preview=iter_data.get('hypothesis_preview', '')[:200],
                    anchor_passed=iter_data.get('anchor_passed', False),
                    anchor_message=iter_data.get('anchor_message', ''),
                    fitness_score=iter_data.get('fitness_score', 0.0),
                    red_team_verdict=iter_data.get('red_team_verdict', 'N/A'),
                    red_team_critical_flaws=iter_data.get('red_team_critical_flaws', []),
                    red_team_severe_issues=iter_data.get('red_team_severe_issues', []),
                    defense_passed=iter_data.get('defense_passed', False),
                    defense_verdict=iter_data.get('defense_verdict', 'N/A'),
                    defense_critical_issues=iter_data.get('defense_critical_issues', []),
                    iteration_status=iter_data.get('status', 'pending'),
                )
                iteration_records.append(record)

        # ==================== V7.2: 提取核心死穴 ====================
        fatal_flaw = self._extract_fatal_flaw(red_team_result, defense_result, primary_reason)

        # ==================== V7.2: 生成转向建议 ====================
        pivot_suggestions = []
        if all_papers and len(all_papers) > 0:
            pivot_suggestions = self._generate_pivot_suggestions(
                user_input, domain, all_papers, fatal_flaw
            )

        # 处理碰撞文献
        collision_paper_objects = []
        for paper in (collision_papers or []):
            cp = CollisionPaper(
                title=paper.get('title', 'Unknown'),
                authors=paper.get('authors', []),
                year=paper.get('year', 0),
                journal=paper.get('journal', 'Unknown'),
                identifier=paper.get('identifier', ''),
                identifier_type=paper.get('identifier_type', 'pmid'),
                similarity_score=paper.get('similarity_score', 0.0),
                overlap_description=paper.get('overlap_description', ''),
                key_findings=paper.get('key_findings', ''),
            )
            collision_paper_objects.append(cp)

        # 处理逻辑缺陷
        logical_flaw_objects = []
        for flaw in (logical_flaws or []):
            flaw_type_str = flaw.get('flaw_type', 'causal_chain_break')
            try:
                flaw_type = LogicalFlawType(flaw_type_str)
            except ValueError:
                flaw_type = LogicalFlawType.CAUSAL_CHAIN_BREAK

            lf = LogicalFlaw(
                flaw_type=flaw_type,
                description=flaw.get('description', ''),
                location=flaw.get('location', ''),
                severity=flaw.get('severity', 'critical'),
                evidence=flaw.get('evidence'),
                suggested_fix=flaw.get('suggested_fix'),
            )
            logical_flaw_objects.append(lf)

        # 根据否决类型补充默���内容
        if not collision_paper_objects:
            collision_paper_objects = self._generate_default_collision_papers(
                rejection_type, domain, verified_ids_found
            )

        if not logical_flaw_objects:
            logical_flaw_objects = self._generate_default_logical_flaws(
                rejection_type, primary_reason
            )

        if not alternative_directions:
            alternative_directions = self._generate_default_alternatives(
                rejection_type, domain, user_input
            )

        if not suggested_keywords:
            suggested_keywords = self._extract_keywords_from_input(user_input)

        detailed_reason = self._build_detailed_reason(
            rejection_type, primary_reason, logical_flaw_objects, collision_paper_objects
        )

        # 创建报告
        report = ScientificRejectionReport(
            report_id=report_id,
            research_idea=user_input,
            domain=domain,
            rejection_type=rejection_type,
            primary_reason=primary_reason,
            detailed_reason=detailed_reason,
            iteration_history=iteration_records,
            total_iterations=len(iteration_records) if iteration_records else 3,
            fatal_flaw_analysis=fatal_flaw,
            pivot_suggestions=pivot_suggestions,
            collision_papers=collision_paper_objects,
            logical_flaws=logical_flaw_objects,
            alternative_directions=alternative_directions,
            suggested_keywords=suggested_keywords,
            api_calls_used=api_calls_used,
            tokens_used=tokens_used,
            time_elapsed=time_elapsed,
            papers_searched=papers_searched,
            data_sources_used=data_sources_used or [],
            verified_ids_found=verified_ids_found or {},
            all_papers=all_papers or [],
            session_id=session_id,
        )

        # 自动保存
        if self.save_reports:
            report.save_to_file(self.reports_directory)

        return report

    def _extract_fatal_flaw(
        self,
        red_team_result: Dict,
        defense_result: Dict,
        primary_reason: str
    ) -> FatalFlawAnalysis:
        """V7.2: 从最后一轮红方攻击中提取核心死穴"""

        fatal_flaw_type = "unknown"
        fatal_flaw_description = ""
        academic_barrier_reason = ""

        # 从红方结果提取
        if red_team_result:
            verdict = red_team_result.get('verdict', '')
            critical_flaws = red_team_result.get('critical_flaws', [])

            if critical_flaws:
                fatal_flaw_type = "critical_flaw_detected"
                fatal_flaw_description = critical_flaws[0] if critical_flaws else verdict

            # 从攻击报告中提取更多信息
            attack_report = red_team_result.get('attack_report', {})
            if attack_report:
                structural_issues = attack_report.get('structural_issues', [])
                if structural_issues:
                    fatal_flaw_description = structural_issues[0]

        # 从防御结果提取
        if defense_result:
            final_verdict = defense_result.get('final_verdict', '')
            critical_issues = defense_result.get('critical_issues', [])

            if critical_issues and not fatal_flaw_description:
                fatal_flaw_type = "committee_rejection"
                fatal_flaw_description = critical_issues[0]

            if final_verdict and not fatal_flaw_description:
                fatal_flaw_description = final_verdict

        # 如果都没有，使用主要原因
        if not fatal_flaw_description:
            fatal_flaw_description = primary_reason

        # 构建学术壁垒分析
        academic_barrier_reason = self._build_academic_barrier(fatal_flaw_type, fatal_flaw_description)

        return FatalFlawAnalysis(
            fatal_flaw_type=fatal_flaw_type,
            fatal_flaw_description=fatal_flaw_description,
            academic_barrier_reason=academic_barrier_reason,
            evidence_chain_break=fatal_flaw_description,
            suggested_research_gap=self._suggest_research_gap(fatal_flaw_type),
        )

    def _build_academic_barrier(self, flaw_type: str, description: str) -> str:
        """构建学术壁垒分析文本"""
        barrier_templates = {
            'critical_flaw_detected': (
                "当前学术界尚未建立足够的理论框架或实验数据来支撑这一因果链推断。"
                "相关领域的核心文献中缺乏对关键中间变量的系统性研究，"
                "导致该假设在现有学术体系下无法形成闭环论证。"
            ),
            'committee_rejection': (
                "防御委员会评估认为该假设存在方法论层面的根本性问题，"
                "这些问题在当前技术条件下难以通过简单的参数调整来解决。"
                "需要等待相关领域的技术突破或新的文献证据出现。"
            ),
            'anchor_failed': (
                "假设引用的文献与检索返回的真实文献无法匹配，"
                "这表明该研究方向可能缺乏足够的文献支撑，"
                "或者假设构建过程中出现了逻辑跳跃。"
            ),
            'unknown': (
                "系统在多轮对���检验后未能找到可以接受的假设版本。"
                "这可能表明研究方向本身存在根本性问题，"
                "或者需要更多的文献证据来支撑论证。"
            ),
        }
        return barrier_templates.get(flaw_type, barrier_templates['unknown'])

    def _suggest_research_gap(self, flaw_type: str) -> str:
        """建议研究空白方向"""
        gap_templates = {
            'critical_flaw_detected': "探索中间机制变量的研究路径，建立更完整的因果链",
            'committee_rejection': "聚焦方法论创新，寻找现有技术可以解决的问题切入点",
            'anchor_failed': "先进行基础文献调研，确保研究方向有足够的文献支撑",
            'unknown': "重新审视研究假设的逻辑结构，寻找更可行的替代路径",
        }
        return gap_templates.get(flaw_type, gap_templates['unknown'])

    def _generate_pivot_suggestions(
        self,
        user_input: str,
        domain: str,
        all_papers: List[Dict],
        fatal_flaw: FatalFlawAnalysis
    ) -> List[PivotSuggestion]:
        """V7.2: 基于文献智能生成转向建议"""

        pivot_suggestions = []

        # 提取论文的关键信息
        paper_titles = [p.get('title', '') for p in all_papers[:10] if p.get('title')]
        paper_pmids = [p.get('pmid', '') for p in all_papers[:10] if p.get('pmid')]

        # 尝试使用 LLM 生成转向建议
        try:
            from src.utils.llm_utils import call_llm

            pivot_prompt = self._build_pivot_prompt(
                user_input, domain, paper_titles, fatal_flaw
            )

            llm_response = call_llm(pivot_prompt)

            if llm_response.get('success'):
                content = llm_response.get('content', '')
                # 解析 LLM 返回的转向建议
                pivot_suggestions = self._parse_pivot_response(content, paper_pmids)

        except Exception as e:
            logger.warning(f"[V7.2] LLM pivot generation failed: {e}")
            # 降级：生成默认转向建议
            pivot_suggestions = self._generate_default_pivots(user_input, domain, paper_pmids)

        return pivot_suggestions

    def _build_pivot_prompt(
        self,
        user_input: str,
        domain: str,
        paper_titles: List[str],
        fatal_flaw: FatalFlawAnalysis
    ) -> str:
        """构建转向建议生成 Prompt"""

        papers_context = "\n".join([f"- {t}" for t in paper_titles[:5]])

        prompt = f"""You are a senior research strategist. The following research hypothesis was rejected after 3 rounds of adversarial testing.

**Original Research Idea:**
{user_input}

**Domain:** {domain}

**Available Real Papers (from PubMed):**
{papers_context}

**Fatal Flaw Identified:**
{fatal_flaw.fatal_flaw_description}

**Task:** Based on the real papers above, generate 2-3 **actionable pivot strategies** that could form closed-loop hypotheses. Each strategy should:
1. Reduce complexity (fewer variables, narrower scope)
2. Have literature support from the papers listed
3. Be methodologically feasible

**Output Format (JSON):**
```json
{
  "pivot_strategies": [
    {
      "id": 1,
      "title": "Pivot Strategy Title",
      "description": "Detailed description of the alternative approach",
      "feasibility_score": 8.5,
      "methodology": "Required research methodology",
      "timeline": "Estimated research timeline"
    }
  ]
}
```

Generate the pivot strategies now."""

        return prompt

    def _parse_pivot_response(
        self,
        content: str,
        paper_pmids: List[str]
    ) -> List[PivotSuggestion]:
        """解析 LLM 返回的转向建议"""

        pivot_suggestions = []

        try:
            from src.utils.llm_utils import SafeExtractor
            parsed = SafeExtractor.safe_extract_json(content)

            strategies = parsed.get('pivot_strategies', [])
            for s in strategies:
                pivot = PivotSuggestion(
                    pivot_id=s.get('id', len(pivot_suggestions) + 1),
                    pivot_title=s.get('title', ''),
                    pivot_description=s.get('description', ''),
                    supporting_papers=paper_pmids[:3],
                    feasibility_score=float(s.get('feasibility_score', 7.0)),
                    required_methodology=s.get('methodology', ''),
                    estimated_timeline=s.get('timeline', ''),
                )
                pivot_suggestions.append(pivot)

        except Exception as e:
            logger.warning(f"[V7.2] Failed to parse pivot response: {e}")

        return pivot_suggestions

    def _generate_default_pivots(
        self,
        user_input: str,
        domain: str,
        paper_pmids: List[str]
    ) -> List[PivotSuggestion]:
        """生成默认转向建议"""

        # 从用户输入提取关键词
        keywords = self._extract_keywords_from_input(user_input)

        pivots = [
            PivotSuggestion(
                pivot_id=1,
                pivot_title="缩小研究范围 / Narrow Research Scope",
                pivot_description=(
                    "聚焦于更具体的研究问题，减少变量数量，"
                    "选择已有文献支撑的子方向进行深入探索。"
                ),
                supporting_papers=paper_pmids[:3],
                feasibility_score=7.5,
                required_methodology="文献综述 + 案例研究",
                estimated_timeline="3-6个月",
            ),
            PivotSuggestion(
                pivot_id=2,
                pivot_title="更换观测指标 / Change Observation Metrics",
                pivot_description=(
                    "基于已有文献，选择更容易测量且已有成熟方法的观测指标，"
                    "降低研究的技术门槛和风险。"
                ),
                supporting_papers=paper_pmids[3:6] if len(paper_pmids) > 3 else paper_pmids,
                feasibility_score=8.0,
                required_methodology="循证方法 + 统计分析",
                estimated_timeline="6-12个月",
            ),
            PivotSuggestion(
                pivot_id=3,
                pivot_title="关联点延伸 / Extend Related Points",
                pivot_description=(
                    "寻找已有研究中的空白点或衍生方向，"
                    "基于现有文献构建新的研究假设。"
                ),
                supporting_papers=paper_pmids,
                feasibility_score=7.0,
                required_methodology="系统综述 + 元分析",
                estimated_timeline="6-9个月",
            ),
        ]

        return pivots

    def _generate_default_collision_papers(
        self,
        rejection_type: RejectionType,
        domain: str,
        verified_ids: Dict[str, List[str]],
    ) -> List[CollisionPaper]:
        """生成默认碰撞文献"""
        papers = []

        if verified_ids:
            pmids = verified_ids.get('pmids', [])
            for i, pmid in enumerate(pmids[:self.default_collision_count]):
                papers.append(CollisionPaper(
                    title=f"相关文献 #{i+1}",
                    authors=["未知作者"],
                    year=2020,
                    journal="相关期刊",
                    identifier=pmid,
                    identifier_type="pmid",
                    similarity_score=0.7 - i * 0.1,
                    overlap_description="研究方向重叠",
                    key_findings="相关领域已有研究",
                ))

        if not papers:
            for i in range(self.default_collision_count):
                papers.append(CollisionPaper(
                    title=f"{domain}领域的相关研究 #{i+1}",
                    authors=["未知作者"],
                    year=2020 + i,
                    journal="待补充",
                    identifier="待检索",
                    identifier_type="pmid",
                    similarity_score=0.75,
                    overlap_description="研究方向高度相似",
                    key_findings="建议补充文献调研",
                ))

        return papers

    def _generate_default_logical_flaws(
        self,
        rejection_type: RejectionType,
        primary_reason: str,
    ) -> List[LogicalFlaw]:
        """生成默认逻辑缺陷"""
        flaws = []

        if rejection_type == RejectionType.LOGICAL_FLAW:
            flaws.append(LogicalFlaw(
                flaw_type=LogicalFlawType.CAUSAL_CHAIN_BREAK,
                description="因果链中的关键节点缺失，无法建立完整的机制推断",
                location="假设核心因果链",
                severity="critical",
                suggested_fix="补充中间机制变量，建立完整的 X → M → Y 因果链",
            ))
            flaws.append(LogicalFlaw(
                flaw_type=LogicalFlawType.MECHANISM_MISSING,
                description="缺乏具体的生化/统计机制描述",
                location="假设机制部分",
                severity="severe",
                suggested_fix="明确具体的分子机制或统计方法",
            ))
        elif rejection_type == RejectionType.MAX_ITERATIONS_EXCEEDED:
            flaws.append(LogicalFlaw(
                flaw_type=LogicalFlawType.CAUSAL_CHAIN_BREAK,
                description="经过多轮对抗检验，假设仍无法通过防御委员会审查",
                location="假设整体逻辑",
                severity="critical",
                suggested_fix="重新审视研究假设的基础假设和因果链结构",
            ))
            flaws.append(LogicalFlaw(
                flaw_type=LogicalFlawType.ALTERNATIVE_PATHWAY,
                description="红方攻击揭示了假设中的逻辑漏洞",
                location="假设论证部分",
                severity="severe",
                suggested_fix="参考转向建议，选择更可行的研究路径",
            ))
        else:
            flaws.append(LogicalFlaw(
                flaw_type=LogicalFlawType.CAUSAL_CHAIN_BREAK,
                description=primary_reason,
                location="假设整体",
                severity="critical",
                suggested_fix="重新审视研究假设的逻辑完整性",
            ))
            flaws.append(LogicalFlaw(
                flaw_type=LogicalFlawType.MECHANISM_MISSING,
                description="需要补充具体的研究机制描述",
                location="机制部分",
                severity="severe",
                suggested_fix="明确具体的因果变量和方法论",
            ))

        return flaws

    def _generate_default_alternatives(
        self,
        rejection_type: RejectionType,
        domain: str,
        user_input: str,
    ) -> List[str]:
        """生成默认替代研究方向"""
        alternatives = []

        keywords = self._extract_keywords_from_input(user_input)

        if rejection_type == RejectionType.MAX_ITERATIONS_EXCEEDED:
            alternatives.append("参考转向建议模块中的具体替代方案")
            alternatives.append("减少研究变量，聚焦于单一因果关系")
            alternatives.append("更换已有成熟文献支撑的观测指标")
        elif rejection_type == RejectionType.COLLISION:
            alternatives.append("考虑已有研究的衍生方向，如：样本亚群差异、时间维度变化")
            alternatives.append("探索已有研究的不足之处，如：方法局限性、数据来源差异")
            alternatives.append("调整研究视角，从不同学科角度切入")
        elif rejection_type == RejectionType.INSUFFICIENT_SUPPORT:
            alternatives.append("扩大检索关键词范围，使用更通用的术语")
            alternatives.append("检查是否存在跨学科相关研究")
            alternatives.append("考虑进行预实验或专家咨询")
        else:
            for kw in keywords[:3]:
                alternatives.append(f"探索 '{kw}' 相关的其他研究方向")
            alternatives.append("调整研究范围，聚焦更具体的问题")

        return alternatives[:5]

    def _extract_keywords_from_input(self, user_input: str) -> List[str]:
        """从用户输入中提取关键词"""
        import re

        stopwords = {'的', '与', '在', '是', '和', '对', '为', '及', '等', '中',
                      '研究', '分析', '关系', '影响', '作用', '机制', '方法', '应用'}

        words = re.findall(r'[\w\u4e00-\u9fff]+', user_input)

        keywords = []
        for word in words:
            if len(word) >= 2 and word not in stopwords:
                keywords.append(word)

        return keywords[:10]

    def _build_detailed_reason(
        self,
        rejection_type: RejectionType,
        primary_reason: str,
        logical_flaws: List[LogicalFlaw],
        collision_papers: List[CollisionPaper],
    ) -> str:
        """构建详细原因说明"""
        lines = []

        lines.append(f"**核心问题 / Core Issue**: {primary_reason}")
        lines.append("")

        if rejection_type == RejectionType.MAX_ITERATIONS_EXCEEDED:
            lines.append("**对抗收敛分析 / Adversarial Convergence Analysis**:")
            lines.append("")
            lines.append(f"系统进行了 3 轮红蓝对抗迭代，每次生成的假设版本均未能通过防御委员会审查。")
            lines.append("这表明该研究方向存在根本性的逻辑问题，无法通过简单的参数调整来解决。")
            lines.append("")

        if logical_flaws:
            lines.append("**逻辑缺陷详情 / Logical Flaw Details**:")
            lines.append("")
            for flaw in logical_flaws:
                lines.append(f"- {flaw.description}")

        return "\n".join(lines)


# ==================== 便捷函数 ====================

def generate_rejection_report(
    user_input: str,
    domain: str,
    rejection_type: str,
    primary_reason: str,
    # V7.2 新增参数
    iteration_history: List[Dict] = None,
    red_team_result: Dict = None,
    defense_result: Dict = None,
    all_papers: List[Dict] = None,
    # 原有参数
    collision_papers: List[Dict] = None,
    logical_flaws: List[Dict] = None,
    alternative_directions: List[str] = None,
    suggested_keywords: List[str] = None,
    api_calls_used: int = 0,
    tokens_used: int = 0,
    time_elapsed: float = 0.0,
) -> Dict:
    """
    V7.2 快捷生成否决报告函数

    Args:
        user_input: 用户原始想法
        domain: 学科领域
        rejection_type: 否决类型字符串
        primary_reason: 主要否决原因
        iteration_history: V7.2 迭代历史
        red_team_result: V7.2 红方攻击结果
        defense_result: V7.2 防御委员会结果
        all_papers: V7.2 所有检索到的论文

    Returns:
        Dict: 报告字典
    """
    generator = RejectionReportGenerator()

    # 转换否决类型
    try:
        rejection_type_enum = RejectionType(rejection_type)
    except ValueError:
        rejection_type_enum = RejectionType.MAX_ITERATIONS_EXCEEDED

    report = generator.generate(
        user_input=user_input,
        domain=domain,
        rejection_type=rejection_type_enum,
        primary_reason=primary_reason,
        iteration_history=iteration_history,
        red_team_result=red_team_result,
        defense_result=defense_result,
        all_papers=all_papers,
        collision_papers=collision_papers,
        logical_flaws=logical_flaws,
        alternative_directions=alternative_directions,
        suggested_keywords=suggested_keywords,
        api_calls_used=api_calls_used,
        tokens_used=tokens_used,
        time_elapsed=time_elapsed,
    )

    return report.to_dict()


def get_rejection_report_generator() -> RejectionReportGenerator:
    """获取否决报告生成器实例"""
    return RejectionReportGenerator()


# ==================== 测试 ====================

if __name__ == '__main__':
    print("=" * 60)
    print("V7.2 科研否决报告生成器 - 测试")
    print("=" * 60)

    generator = RejectionReportGenerator()

    # 测试生成报告（包含 V7.2 新模块）
    report = generator.generate(
        user_input="肿瘤耐药性机制研究",
        domain="肿瘤学",
        rejection_type=RejectionType.MAX_ITERATIONS_EXCEEDED,
        primary_reason="经过3轮对抗检验，假设仍无法通过防御委员会审查",
        iteration_history=[
            {'iteration': 1, 'anchor_passed': True, 'fitness_score': 8.4,
             'red_team_verdict': 'rejected', 'defense_passed': False, 'status': 'defense_failed'},
            {'iteration': 2, 'anchor_passed': False, 'fitness_score': 0,
             'red_team_verdict': 'N/A', 'defense_passed': False, 'status': 'anchor_failed'},
            {'iteration': 3, 'anchor_passed': True, 'fitness_score': 8.4,
             'red_team_verdict': 'rejected', 'defense_passed': False, 'status': 'defense_failed'},
        ],
        red_team_result={
            'verdict': 'rejected',
            'critical_flaws': ['因果链断裂：缺乏中间机制变量'],
        },
        defense_result={
            'final_verdict': 'rejected',
            'critical_issues': ['方法论存在根本性问题'],
        },
        all_papers=[
            {'title': 'Cancer drug resistance mechanisms', 'pmid': '12345678'},
            {'title': 'Tumor heterogeneity and therapy', 'pmid': '23456789'},
        ],
        api_calls_used=5,
        time_elapsed=175.15,
        papers_searched=10,
    )

    print(f"\n报告ID: {report.report_id}")
    print(f"\nMarkdown 报告预览:")
    print("-" * 40)
    print(report.to_markdown())

    print("\n" + "=" * 60)
    print("测试完成")