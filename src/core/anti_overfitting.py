# -*- coding: utf-8 -*-
"""
反过拟合审计机制 (Anti-Overfitting Audit)

V4.1 新增核心机制：
- 假大空惩罚器
- 万金油词汇检测
- 无真实机制推断检测
- 早期熔断触发
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum


class OverfittingSeverity(Enum):
    """过拟合严重程度"""
    MINOR = "minor"        # 轻微，扣1分
    MODERATE = "moderate"  # 中等，扣2分
    CRITICAL = "critical"  # 严重，扣3分，触发熔断


@dataclass
class OverfittingIssue:
    """单个过拟合问题"""
    category: str          # 问题类别
    issue: str             # 具体问题描述
    severity: str          # 严重程度
    penalty: float         # 扣分值
    suggestion: str = ""   # 改进建议
    category_detail: str = ""  # 类别详情


@dataclass
class OverfittingAuditResult:
    """反过拟合审计结果"""
    detected_issues: List[Dict]    # 检测到的问题列表
    total_penalty: float           # 总扣分
    should_fuse: bool              # 是否触发熔断
    fusing_reason: str             # 熔断原因
    audit_summary: str             # 审计摘要
    bogus_keyword_count: int       # 万金油词汇计数
    has_real_mechanism: bool       # 是否有真实机制
    has_causal_chain: bool         # 是否有因果链


class AntiOverfittingAuditor:
    """
    反过拟合审计器

    核心功能：
    1. 假大空惩罚器：检测万金油词汇
    2. 真实机制推断检测：确保有具体因果链或参数
    3. 空洞因果链检测：避免因果词汇而无具体链条
    4. 熔断机制：扣分超过阈值触发早期熔断

    设计理念：
    - "多模态联合"、"大模型赋能"等词汇若无具体机制支撑则扣分
    - 必须有明确的 X → M → Y 因果链
    - 必须有具体的 R 包、Python 库、参数值
    """

    # 万金油词汇库（假大空词汇）
    BOGUS_KEYWORDS = {
        # 通用模板词汇（最常见）
        'template': [
            '多模态联合',
            '大模型赋能',
            '人工智能驱动',
            '深度学习辅助',
            '智能化分析',
            '大数据挖掘',
            '精准医疗',
            '个性化诊疗',
            '综合评估',
            '系统性分析',
            '多维度融合',
            '跨领域整合'
        ],
        # 空洞方法论词汇
        'methodology': [
            '采用先进技术',
            '运用创新方法',
            '基于最新研究',
            '综合多种方法',
            '结合前沿理论',
            '创新性方法',
            '突破性技术'
        ],
        # 虚假创新词汇
        'fake_innovation': [
            '颠覆性突破',
            '革命性创新',
            '划时代发现',
            '历史性进展',
            '里程碑意义',
            '开创性研究'
        ],
        # 空洞临床词汇
        'clinical_empty': [
            '显著改善',
            '大幅提升',
            '明显提高',
            '有效治疗',
            '良好效果'
        ]
    }

    # 真实机制推断关键词（正面词汇，表明有具体内容）
    REAL_MECHANISM_KEYWORDS = [
        # 明确因果链格式
        '→', '→', '->',  # 箭头符号
        'mediation',
        'counterfactual',
        'DAG',

        # 具体统计方法
        'instrumental variable',
        'propensity score',
        'E-value',
        'bootstrap',
        'FDR',
        'Bonferroni',

        # 具体软件/包
        'R package',
        'Python library',
        'mediation::',
        'lme4::',
        'glmnet',
        'survival::',
        'scikit-learn',

        # 具体参数
        'p <',
        'p =',
        'CI:',
        'n =',
        'N =',
        'AUROC',
        'AUC',
        'C-index',
        'hazard ratio',
        'odds ratio',
        'beta =',
        'β =',

        # 具体数据集
        'ADNI',
        'UK Biobank',
        'GWAS',
        'pQTL'
    ]

    # 熔断阈值
    FUSE_THRESHOLD = -3.0   # 扣分超过3分触发熔断
    BOGUS_KEYWORD_THRESHOLD = 3  # 万金油词汇超过3个触发熔断

    def audit(self, hypothesis: Dict) -> OverfittingAuditResult:
        """
        执行反过拟合审计

        Args:
            hypothesis: 假设字典，包含 title, details, scores 等

        Returns:
            OverfittingAuditResult: 审计结果
        """
        detected_issues = []
        total_penalty = 0.0
        bogus_keyword_count = 0
        has_real_mechanism = False
        has_causal_chain = False

        # 1. 万金油词汇检测
        bogus_issues = self._detect_bogus_keywords(hypothesis)
        bogus_keyword_count = len(bogus_issues)
        detected_issues.extend(bogus_issues)
        total_penalty += sum(issue['penalty'] for issue in bogus_issues)

        # 2. 真实机制推断检测
        mechanism_issues, has_real_mechanism = self._detect_missing_mechanism(hypothesis)
        detected_issues.extend(mechanism_issues)
        total_penalty += sum(issue['penalty'] for issue in mechanism_issues)

        # 3. 空洞因果链检测
        causal_issues, has_causal_chain = self._detect_empty_causal_chain(hypothesis)
        detected_issues.extend(causal_issues)
        total_penalty += sum(issue['penalty'] for issue in causal_issues)

        # 4. 判断熔断
        should_fuse = (
            total_penalty <= self.FUSE_THRESHOLD or
            bogus_keyword_count >= self.BOGUS_KEYWORD_THRESHOLD
        )

        fusing_reason = ""
        if should_fuse:
            critical_issues = [i for i in detected_issues if i['severity'] == 'critical']
            if critical_issues:
                fusing_reason = f"检测到 {len(critical_issues)} 个严重问题: " + \
                               ", ".join([i['issue'] for i in critical_issues[:3]])
            elif bogus_keyword_count >= self.BOGUS_KEYWORD_THRESHOLD:
                fusing_reason = f"检测到 {bogus_keyword_count} 个万金油词汇，超过阈值 {self.BOGUS_KEYWORD_THRESHOLD}"

        # 5. 生成审计摘要
        audit_summary = self._generate_audit_summary(
            detected_issues,
            total_penalty,
            bogus_keyword_count,
            has_real_mechanism,
            has_causal_chain
        )

        return OverfittingAuditResult(
            detected_issues=detected_issues,
            total_penalty=total_penalty,
            should_fuse=should_fuse,
            fusing_reason=fusing_reason,
            audit_summary=audit_summary,
            bogus_keyword_count=bogus_keyword_count,
            has_real_mechanism=has_real_mechanism,
            has_causal_chain=has_causal_chain
        )

    def _detect_bogus_keywords(self, hypothesis: Dict) -> List[Dict]:
        """
        检测万金油词汇

        Args:
            hypothesis: 假设字典

        Returns:
            List[Dict]: 检测到的问题列表
        """
        issues = []

        # 合并所有文本
        full_text = ""
        full_text += hypothesis.get('title', '') + " "
        full_text += hypothesis.get('details', '') + " "
        full_text += hypothesis.get('core_hypothesis', '') + " "
        full_text += hypothesis.get('mechanism_outline', '') + " "

        # 检测各类万金油词汇
        for category, keywords in self.BOGUS_KEYWORDS.items():
            for kw in keywords:
                if kw in full_text:
                    # 根据类别确定严重程度
                    if category in ['template', 'fake_innovation']:
                        severity = OverfittingSeverity.MODERATE.value
                        penalty = -2.0
                    else:
                        severity = OverfittingSeverity.MINOR.value
                        penalty = -1.0

                    issues.append({
                        'category': 'bogus_keyword',
                        'issue': f"检测到万金油词汇: '{kw}'",
                        'severity': severity,
                        'penalty': penalty,
                        'category_detail': category,
                        'suggestion': f"请替换为具体的方法描述，如: '使用R mediation包进行因果中介分析'"
                    })

        return issues

    def _detect_missing_mechanism(self, hypothesis: Dict) -> Tuple[List[Dict], bool]:
        """
        检测缺失真实机制推断

        Args:
            hypothesis: 假设字典

        Returns:
            Tuple[List[Dict], bool]: (问题列表, 是否有真实机制)
        """
        issues = []

        full_text = ""
        full_text += hypothesis.get('details', '') + " "
        full_text += hypothesis.get('mechanism_outline', '') + " "
        full_text += hypothesis.get('technical_route', '') + " "

        # 检查是否包含至少一个真实机制关键词
        has_real_mechanism = any(
            kw.lower() in full_text.lower()
            for kw in self.REAL_MECHANISM_KEYWORDS
        )

        if not has_real_mechanism:
            issues.append({
                'category': 'missing_mechanism',
                'issue': "缺失真实机制推断：未发现具体的因果链、统计方法或参数",
                'severity': OverfittingSeverity.CRITICAL.value,
                'penalty': -3.0,
                'suggestion': "必须添加: 明确的因果链(X→M→Y)、具体统计方法(R mediation::mediate())、或具体参数值(p < 0.05)"
            })

        return issues, has_real_mechanism

    def _detect_empty_causal_chain(self, hypothesis: Dict) -> Tuple[List[Dict], bool]:
        """
        检测空洞因果链

        Args:
            hypothesis: 假设字典

        Returns:
            Tuple[List[Dict], bool]: (问题列表, 是否有有效因果链)
        """
        issues = []

        details = hypothesis.get('details', '')
        core_hypothesis = hypothesis.get('core_hypothesis', '')
        full_text = details + " " + core_hypothesis

        # 检查因果链格式（多种箭头符号）
        # 有效格式: "X → M → Y" 或 "exposure → mediator → outcome"
        causal_patterns = [
            r'[A-Za-z]+\s*[→]->]+\s*[A-Za-z]+\s*[→]->]+\s*[A-Za-z]+',  # X → M → Y
            r'\b[A-Za-z]+\b.*mediat.*\b[A-Za-z]+\b',  # X mediates Y
            r'exposure.*outcome',  # exposure to outcome
        ]

        has_valid_chain = any(
            re.search(pattern, full_text, re.IGNORECASE)
            for pattern in causal_patterns
        )

        # 检查是否有因果相关词汇但无具体链条
        causal_keywords = ['causal', 'mediation', 'mediator', 'mechanism',
                           'pathway', 'indirect', 'direct effect', '因果']
        has_causal_keywords = any(kw in full_text.lower() for kw in causal_keywords)

        if has_causal_keywords and not has_valid_chain:
            issues.append({
                'category': 'empty_causal_chain',
                'issue': "因果词汇存在但无具体因果链：提到因果/中介但未给出 X → M → Y",
                'severity': OverfittingSeverity.CRITICAL.value,
                'penalty': -3.0,
                'suggestion': "必须明确写出: Exposure → Mediator → Outcome 的具体变量名\n示例: 血浆pQTL → 海马萎缩率 → 认知衰退速度"
            })

        return issues, has_valid_chain

    def _generate_audit_summary(
        self,
        issues: List[Dict],
        total_penalty: float,
        bogus_count: int,
        has_mechanism: bool,
        has_chain: bool
    ) -> str:
        """
        生成审计摘要

        Args:
            issues: 问题列表
            total_penalty: 总扣分
            bogus_count: 万金油词汇计数
            has_mechanism: 是否有真实机制
            has_chain: 是否有因果链

        Returns:
            str: 审计摘要文本
        """
        if not issues:
            return "[反过拟合审计] ✅ 通过：未检测到假大空问题，内容充实具体"

        severity_icons = {
            'minor': '🟡',
            'moderate': '🟠',
            'critical': '🔴'
        }

        summary_lines = [
            "╔══════════════════════════════════════════════════════════════════╗",
            "║              【反过拟合审计结果 - Anti-Overfitting Audit】          ║",
            "╚══════════════════════════════════════════════════════════════════╝",
            "",
            f"**总扣分**: {total_penalty}",
            f"**万金油词汇**: {bogus_count} 个",
            f"**真实机制**: {'✅ 有' if has_mechanism else '❌ 无'}",
            f"**因果链**: {'✅ 有' if has_chain else '❌ 无'}",
            ""
        ]

        if issues:
            summary_lines.append("### 检测到的问题:")
            for issue in issues:
                icon = severity_icons.get(issue['severity'], '⚪')
                summary_lines.append(f"{icon} [{issue['category']}] {issue['issue']}")

                if issue.get('suggestion'):
                    summary_lines.append(f"   💡 建议: {issue['suggestion']}")

        if total_penalty <= self.FUSE_THRESHOLD:
            summary_lines.extend([
                "",
                "🔴 **熔断触发**: 扣分超过阈值，建议重新生成假说"
            ])
        elif bogus_count >= self.BOGUS_KEYWORD_THRESHOLD:
            summary_lines.extend([
                "",
                "🔴 **熔断触发**: 万金油词汇过多，内容空洞"
            ])

        return "\n".join(summary_lines)

    def adjust_scores(
        self,
        hypothesis: Dict,
        audit_result: OverfittingAuditResult
    ) -> Dict:
        """
        根据审计结果调整假设评分

        Args:
            hypothesis: 原假设字典
            audit_result: 审计结果

        Returns:
            Dict: 调整后的假设（含 adjusted_scores）
        """
        original_scores = hypothesis.get('scores', {})

        # 计算调整后的分数
        adjusted_scores = {
            'novelty': original_scores.get('novelty', 7.0) + audit_result.total_penalty,
            'rigor': original_scores.get('rigor', 7.0) + audit_result.total_penalty,
            'impact': original_scores.get('impact', 7.0) + audit_result.total_penalty,
            'overall': original_scores.get('overall', 7.0) + audit_result.total_penalty,
            'overfitting_penalty': audit_result.total_penalty,
            'overfitting_fused': audit_result.should_fuse,
            'bogus_keyword_count': audit_result.bogus_keyword_count,
            'has_real_mechanism': audit_result.has_real_mechanism
        }

        # 确保评分不为负
        for key in ['novelty', 'rigor', 'impact', 'overall']:
            adjusted_scores[key] = max(0, min(10, adjusted_scores[key]))

        # 添加审计信息
        hypothesis['adjusted_scores'] = adjusted_scores
        hypothesis['overfitting_audit'] = audit_result.audit_summary
        hypothesis['overfitting_issues'] = audit_result.detected_issues

        return hypothesis


# ==============================================================================
# 集成到 Fail-Fast 机制的便捷函数
# ==============================================================================

def check_overfitting_before_phase3(phase1_result: Dict) -> Tuple[bool, str]:
    """
    在 Phase 3 展开前检查过拟合

    用于集成到现有的 Fail-Fast Generator

    Args:
        phase1_result: Phase 1 的初步结果

    Returns:
        Tuple[bool, str]: (是否继续, 原因/摘要)
    """
    auditor = AntiOverfittingAuditor()
    audit_result = auditor.audit(phase1_result)

    if audit_result.should_fuse:
        return False, audit_result.fusing_reason

    return True, audit_result.audit_summary


def quick_bogus_check(text: str) -> Tuple[int, List[str]]:
    """
    快速万金油词汇检测

    Args:
        text: 待检测文本

    Returns:
        Tuple[int, List[str]]: (数量, 检测到的词汇列表)
    """
    auditor = AntiOverfittingAuditor()
    detected = []

    for category, keywords in auditor.BOGUS_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                detected.append(kw)

    return len(detected), detected


# ==============================================================================
# 全局便捷函数
# ==============================================================================

_global_overfitting_auditor = None


def get_overfitting_auditor() -> AntiOverfittingAuditor:
    """
    获取全局 AntiOverfittingAuditor 实例（单例模式）

    Returns:
        AntiOverfittingAuditor 实例
    """
    global _global_overfitting_auditor
    if _global_overfitting_auditor is None:
        _global_overfitting_auditor = AntiOverfittingAuditor()
    return _global_overfitting_auditor


def audit_hypothesis_overfitting(hypothesis: Dict) -> OverfittingAuditResult:
    """
    全局便捷函数：审计假设过拟合

    Args:
        hypothesis: 假设字典

    Returns:
        OverfittingAuditResult: 审计结果
    """
    return get_overfitting_auditor().audit(hypothesis)