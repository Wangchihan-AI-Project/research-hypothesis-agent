# -*- coding: utf-8 -*-
"""
补救检索模块 (Remedial Search Module)

当审计失败时，自动从审计意见中提取缺失关键词，
执行定向补救检索，为反馈循环提供方法学文献支持。

核心逻辑：
1. 从审计意见中提取缺失的方法学关键词
2. 使用关键词 + 原主题执行轻量级补救检索（3-5篇）
3. 返回检索结果供反馈循环使用
"""

from typing import Dict, List, Optional, Tuple
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# 方法学关键词库 (用于识别审计意见中的缺失方法)
METHODOLOGY_KEYWORDS = {
    'causal_inference': [
        '因果推断', 'causal inference', 'mediation analysis', '中介分析',
        'confounding', '混杂', 'instrumental variable', '工具变量',
        'propensity score', '倾向性评分', 'counterfactual', '反事实',
        'do-calculus', 'pearl', 'judea pearl'
    ],
    'statistical_power': [
        '统计功效', 'power analysis', '样本量', 'sample size',
        'power calculation', '功效计算', 'underpowered', '功效不足',
        'post hoc power', 'a priori power'
    ],
    'multiple_testing': [
        '多重检验', 'multiple testing', 'fdr', 'false discovery rate',
        'bonferroni', 'benjamini', 'holm', '校正', 'correction',
        'family wise error'
    ],
    'longitudinal_analysis': [
        '纵向分析', 'longitudinal', 'mixed effect', '混合效应',
        'lmm', 'linear mixed model', 'gee', 'generalized estimating equation',
        'time series', '时间序列', 'repeated measure', '重复测量'
    ],
    'mediation_analysis': [
        '中介分析', 'mediation', 'bootstrap', '间接效应',
        'indirect effect', 'direct effect', '直接效应',
        'path analysis', '路径分析'
    ],
    'machine_learning': [
        'machine learning', '机器学习', 'cross validation', '交叉验证',
        'overfitting', '过拟合', 'regularization', '正则化',
        'feature selection', '特征选择', 'dimensionality reduction'
    ],
    'survival_analysis': [
        '生存分析', 'survival analysis', 'cox regression', 'cox回归',
        'kaplan meier', 'hazard ratio', 'time to event',
        'censoring', '删失'
    ],
    'bayesian': [
        'bayesian', '贝叶斯', 'prior', '先验', 'posterior', '后验',
        'mcmc', 'markov chain', 'hierarchical', '层次模型'
    ],
    'imputation': [
        '插补', 'imputation', 'missing data', '缺失数据',
        'mice', 'multiple imputation', 'knn impute'
    ]
}


class RemedialSearchEngine:
    """补救检索引擎 - 为反馈循环提供定向文献支持"""

    def __init__(self, pubmed_searcher=None):
        """
        初始化补救检索引擎

        Args:
            pubmed_searcher: PubMedSearcher 实例（可选）
        """
        self.pubmed_searcher = pubmed_searcher

    def extract_deficiency_keywords(self, feedback_context: Dict) -> List[str]:
        """
        从审计意见中提取缺失的方法学关键词

        Args:
            feedback_context: 反馈上下文，包含 attack_report 和 defense_result

        Returns:
            提取的关键词列表
        """
        keywords = set()

        # 从攻击报告中提取
        attack_report = feedback_context.get('attack_report', {})
        critical_flaws = attack_report.get('critical_flaws', [])
        methodological_issues = attack_report.get('methodological_issues', [])
        statistical_concerns = attack_report.get('statistical_concerns', [])

        # 从防御结果中提取
        defense_result = feedback_context.get('defense_result', {})
        critical_issues = defense_result.get('critical_issues', [])
        final_verdict = defense_result.get('final_verdict', '')

        # 合并所有反馈文本
        all_feedback = []
        all_feedback.extend(critical_flaws)
        all_feedback.extend(methodological_issues)
        all_feedback.extend(statistical_concerns)
        all_feedback.extend(critical_issues)
        all_feedback.append(final_verdict)

        feedback_text = ' '.join(all_feedback).lower()

        # 检查方法学关键词
        for category, kw_list in METHODOLOGY_KEYWORDS.items():
            for kw in kw_list:
                if kw.lower() in feedback_text:
                    keywords.add(kw)
                    # 如果是英文关键词，同时添加对应的英文搜索术语
                    if ' ' in kw:
                        keywords.add(kw.replace(' ', ' AND '))

        # 额外提取：查找具体的技术术语
        # 例如："缺少 X 分析" -> 提取 "X"
        pattern = r'缺少|缺失|缺乏|未包含|未提供|need|lack|missing'
        for feedback in all_feedback:
            if re.search(pattern, feedback, re.IGNORECASE):
                # 尝试提取术语
                terms = self._extract_technical_terms(feedback)
                keywords.update(terms)

        logger.info(f"[补救检索] 提取到的关键词: {keywords}")
        return list(keywords)

    def _extract_technical_terms(self, text: str) -> List[str]:
        """从文本中提取技术术语"""
        terms = []

        # 常见模式：X分析, X模型, X检验, X回归
        patterns = [
            r'(\w+(?:分析|模型|检验|回归|方法|test|analysis|model|regression|method))',
            r'(?:缺少|缺失|缺乏|未|lack|missing|need)\s*(\w+(?:分析|模型|检验)?)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            terms.extend(matches)

        return terms

    def build_remedial_query(self, keywords: List[str], research_topic: str) -> str:
        """
        构建补救检索查询

        Args:
            keywords: 提取的关键词
            research_topic: 原研究主题

        Returns:
            PubMed 查询字符串
        """
        if not keywords:
            # 如果没有提取到关键词，使用通用的方法学查询
            return f"({research_topic}) AND (systematic review OR meta-analysis OR methodology)"

        # 选择最重要的 2-3 个关键词
        top_keywords = keywords[:3]

        # 构建 PubMed 查询
        # 格式： (原主题) AND (关键词1 OR 关键词2 ...) AND (方法学 OR 指南)
        keyword_query = ' OR '.join([f'"{kw}"' for kw in top_keywords])

        query = f'({research_topic}) AND ({keyword_query}) AND (methodology OR guidelines OR "systematic review")'

        logger.info(f"[补救检索] 构建的查询: {query}")
        return query

    async def execute_remedial_search(
        self,
        feedback_context: Dict,
        research_topic: str,
        max_results: int = 5,
        year_start: int = 2020
    ) -> Dict:
        """
        执行补救检索

        Args:
            feedback_context: 反馈上下文
            research_topic: 研究主题
            max_results: 最大结果数（默认5篇）
            year_start: 起始年份（默认2020，获取最新方法学文献）

        Returns:
            {
                'success': bool,
                'keywords': List[str],
                'query': str,
                'papers': List[Dict],
                'remedial_context': str  # 用于直接注入反馈的格式化文本
            }
        """
        result = {
            'success': False,
            'keywords': [],
            'query': '',
            'papers': [],
            'remedial_context': ''
        }

        # 步骤1: 提取缺失关键词
        logger.info("[补救检索] 步骤1: 提取审计意见中的缺失关键词...")
        keywords = self.extract_deficiency_keywords(feedback_context)

        if not keywords:
            logger.warning("[补救检索] 未提取到明确关键词，使用通用方法学查询")
            keywords = ['methodology', 'guidelines', 'best practices']

        result['keywords'] = keywords

        # 步骤2: 构建检索查询
        logger.info("[补救检索] 步骤2: 构建补救检索查询...")
        query = self.build_remedial_query(keywords, research_topic)
        result['query'] = query

        # 步骤3: 执行检索
        logger.info(f"[补救检索] 步骤3: 执行补救检索 (最多{max_results}篇)...")
        if self.pubmed_searcher:
            try:
                # 使用 search_papers 方法，参数格式为 date_range=(year_start, year_end)
                year_end = datetime.now().year
                papers = self.pubmed_searcher.search_papers(
                    query=query,
                    max_results=max_results,
                    date_range=(year_start, year_end),
                    enable_filter=False
                )

                result['papers'] = papers if papers else []
                result['success'] = len(papers) > 0

                logger.info(f"[补救检索] 成功检索到 {len(papers) if papers else 0} 篇方法学文献")

            except Exception as e:
                logger.error(f"[补救检索] 检索失败: {e}")
                result['error'] = str(e)
        else:
            logger.warning("[补救检索] 未配置 PubMedSearcher，返回模拟数据")
            # 返回模拟数据供测试
            result['papers'] = self._get_mock_papers(keywords, max_results)
            result['success'] = True

        # 步骤4: 生成补救上下文（用于直接注入反馈）
        result['remedial_context'] = self._format_remedial_context(
            result['papers'],
            keywords
        )

        return result

    def _format_remedial_context(self, papers: List[Dict], keywords: List[str]) -> str:
        """
        格式化补救检索结果为可读文本

        Args:
            papers: 检索到的论文
            keywords: 提取的关键词

        Returns:
            格式化的文本
        """
        if not papers:
            return "（补救检索未返回相关文献）"

        context = f"""
## 📚 补救检索结果

针对审计意见中指出的缺失方法学，系统自动执行了定向补救检索：

**提取的关键词**: {', '.join(keywords[:5])}

**检索到的最新方法学文献**:

"""
        for i, paper in enumerate(papers, 1):
            title = paper.get('title', 'N/A')
            journal = paper.get('journal', 'N/A')
            pub_date = paper.get('publication_date', 'N/A')
            abstract = paper.get('abstract', 'N/A')[:300]

            context += f"""
### 文献 {i}
**标题**: {title}
**期刊**: {journal}
**发表日期**: {pub_date}
**摘要**: {abstract}...

"""

        context += """
---
请参考上述最新方法学文献，为假设补充相应的统计框架和分析方法。
"""

        return context

    def _get_mock_papers(self, keywords: List[str], max_results: int) -> List[Dict]:
        """生成模拟论文数据（用于测试）"""
        mock_papers = []

        keyword_str = ' '.join(keywords[:2])

        for i in range(min(max_results, 3)):
            mock_papers.append({
                'pmid': f' MOCK{i+1:06d}',
                'title': f'Methodological Advances in {keyword_str}: A Systematic Review',
                'journal': 'Nature Methods',
                'publication_date': '2024-01-15',
                'abstract': f'''
This systematic review examines recent methodological advances in {keyword_str}.
We identified key approaches including robust statistical frameworks, validation protocols,
and best practices for data analysis. The review provides practical recommendations
for researchers implementing these methods in their studies.
Key findings:
1. Importance of proper power analysis and sample size calculation
2. Recommended correction methods for multiple testing
3. Validation protocols for causal inference frameworks
4. Best practices for longitudinal data analysis
                '''.strip(),
                'authors': 'Smith J, et al.',
                'doi': f'10.1038/s41592-024 MOCK{i+1:03d}'
            })

        return mock_papers


def create_remedial_search_prompt(
    original_hypothesis: Dict,
    feedback_context: Dict,
    remedial_search_result: Dict
) -> str:
    """
    创建包含补救检索结果的反馈提示

    Args:
        original_hypothesis: 原始假设数据
        feedback_context: 反馈上下文
        remedial_search_result: 补救检索结果

    Returns:
        完整的反馈提示
    """
    attack_report = feedback_context.get('attack_report', {})
    defense_result = feedback_context.get('defense_result', {})

    critical_issues = defense_result.get('critical_issues', [])[:5]
    final_verdict = defense_result.get('final_verdict', '')
    critical_flaws = attack_report.get('critical_flaws', [])[:3]

    prompt = f"""# 🔄 递归反馈修正（含补救检索支持）

## 📋 原始假设
**标题**: {original_hypothesis.get('title', 'N/A')}

---

## ⚖️ 委员会裁决
{final_verdict}

---

## 🚨 需要修复的关键问题
{chr(10).join(f"- {issue}" for issue in critical_issues)}

---

## 🔴 红方发现的致命缺陷
{chr(10).join(f"- {flaw}" for flaw in critical_flaws)}

---

{remedial_search_result.get('remedial_context', '')}

---

## ✅ 修正指令

请参考上述**补救检索到的最新方法学文献**，针对审计意见指出的问题：
1. 补充缺失的统计框架和分析方法
2. 引用文献中的最佳实践
3. 确保技术路线与最新方法学标准对齐

⚠️ **重要约束**:
- 🚫 绝对禁止在回答中道歉
- 🚫 绝对禁止为了迎合审稿人而降低创新性
- ✅ 必须保持学术攻击性
- ✅ 必须引用补救检索文献中的具体方法

请开始修正：
"""

    return prompt
