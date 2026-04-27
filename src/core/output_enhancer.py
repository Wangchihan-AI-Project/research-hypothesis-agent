# -*- coding: utf-8 -*-
"""
V7.5 输出增强器 (Output Enhancer)

核心功能：
1. 生成落地指南 (Implementation Roadmap)
2. 生成创新点文本描述 (Innovation Analysis)
3. 生成前沿溯源分析 (Frontier Analysis)

补齐用户期望的输出内容：
- 落地指南：时间线、资源需求、里程碑
- 创新点：详细的文本分析而非仅有分数
- 前沿溯源：解读文献趋势，非仅ID列表

作者: V7.5 架构工程师
日期: 2026-04-20
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)


# ==================== 数据类定义 ====================

@dataclass
class ImplementationRoadmap:
    """
    落地指南 (Implementation Roadmap)

    Attributes:
        phases: 阶段列表
        resources: 资源需求
        timeline: 时间线
        risks: 风险评估
        budget: 预算估算
    """
    phases: List[Dict] = field(default_factory=list)
    resources: Dict = field(default_factory=dict)
    timeline: Dict = field(default_factory=dict)
    risks: List[Dict] = field(default_factory=list)
    budget: Optional[Dict] = None
    feasibility_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'phases': self.phases,
            'resources': self.resources,
            'timeline': self.timeline,
            'risks': self.risks,
            'budget': self.budget,
            'feasibility_notes': self.feasibility_notes
        }


@dataclass
class InnovationAnalysis:
    """
    创新点分析 (Innovation Analysis)

    Attributes:
        core_innovations: 核心创新点列表
        novelty_level: 新颖度等级
        differentiation: 与现有研究的差异化
        breakthrough_potential: 突破潜力评估
        vector_analysis: 向量创新分析
        methodology_analysis: 方法论创新分析
    """
    core_innovations: List[Dict] = field(default_factory=list)
    novelty_level: str = "unknown"  # breakthrough, incremental, incremental
    differentiation: List[str] = field(default_factory=list)
    breakthrough_potential: Dict = field(default_factory=dict)
    vector_analysis: Dict = field(default_factory=dict)
    methodology_analysis: Dict = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> Dict:
        return {
            'core_innovations': self.core_innovations,
            'novelty_level': self.novelty_level,
            'differentiation': self.differentiation,
            'breakthrough_potential': self.breakthrough_potential,
            'vector_analysis': self.vector_analysis,
            'methodology_analysis': self.methodology_analysis,
            'summary': self.summary
        }


@dataclass
class FrontierAnalysis:
    """
    前沿溯源分析 (Frontier Analysis)

    Attributes:
        frontier_position: 前沿定位
        key_publications: 关键出版物解读
        research_trends: 研究趋势
        gap_analysis: 研究空白分析
        leading_groups: 领先团队/机构
        timeline: 前沿时间线
    """
    frontier_position: str = ""
    key_publications: List[Dict] = field(default_factory=list)
    research_trends: List[str] = field(default_factory=list)
    gap_analysis: List[str] = field(default_factory=list)
    leading_groups: List[Dict] = field(default_factory=list)
    timeline: List[Dict] = field(default_factory=list)
    citation_velocity: str = "unknown"
    year_trend: str = "unknown"

    def to_dict(self) -> Dict:
        return {
            'frontier_position': self.frontier_position,
            'key_publications': self.key_publications,
            'research_trends': self.research_trends,
            'gap_analysis': self.gap_analysis,
            'leading_groups': self.leading_groups,
            'timeline': self.timeline,
            'citation_velocity': self.citation_velocity,
            'year_trend': self.year_trend
        }


# ==================== 输出增强器类 ====================

class OutputEnhancer:
    """
    输出增强器

    核心方法：
    1. generate_implementation_roadmap - 生成落地指南
    2. generate_innovation_analysis - 生成创新点分析
    3. generate_frontier_analysis - 生成前沿溯源分析
    """

    def __init__(self, llm_client=None):
        """
        初始化输出增强器

        Args:
            llm_client: LLM 客户端（可选）
        """
        self.llm_client = llm_client

        # 领域关键词映射（用于分析）
        self.domain_keywords = {
            '心血管疾病': ['cardiovascular', 'heart', 'cardiac', 'myocardial', 'ischemia'],
            '癌症': ['cancer', 'tumor', 'oncology', 'carcinoma', 'malignant'],
            '神经科学': ['neuro', 'brain', 'cognitive', 'dementia', 'alzheimer'],
            '代谢疾病': ['metabolic', 'diabetes', 'obesity', 'fatty liver', 'lipid'],
            '衰老生物学': ['aging', 'senescence', 'telomere', 'longevity', 'lifespan'],
        }

        # 研究方法复杂度评级
        self.methodology_complexity = {
            'high': [
                'multi-omics', 'spatial transcriptomics', 'single-cell',
                'machine learning', 'deep learning', 'causal inference',
                '空间转录组', '多组学', '单细胞', '深度学习'
            ],
            'medium': [
                'rna-seq', 'genomics', 'proteomics', 'bioinformatics',
                '测序', '组学', '生物信息'
            ],
            'low': [
                'pcr', 'western blot', 'elisa', 'cell culture',
                '细胞培养', '蛋白印迹'
            ]
        }

    def generate_implementation_roadmap(
        self,
        hypothesis_data: Dict,
        domain: str,
        fitness_result: Dict
    ) -> ImplementationRoadmap:
        """
        生成落地指南

        Args:
            hypothesis_data: 假设数据
            domain: 研究领域
            fitness_result: 适应度结果

        Returns:
            ImplementationRoadmap: 落地指南
        """
        logger.info("[OutputEnhancer] 生成落地指南")

        # 分析假设内容
        title = hypothesis_data.get('title', '')
        details = hypothesis_data.get('details', '')
        methodology = hypothesis_data.get('methodology', {})

        # 确定研究复杂度
        complexity = self._assess_complexity(title + details + str(methodology))

        # 生成阶段
        phases = self._generate_phases(complexity, domain)

        # 生成资源需求
        resources = self._generate_resources(complexity, domain, methodology)

        # 生成时间线
        timeline = self._generate_timeline(complexity)

        # 生成风险评估
        risks = self._generate_risks(hypothesis_data, domain)

        # 生成可行性备注
        feasibility_notes = self._generate_feasibility_notes(
            hypothesis_data, fitness_result
        )

        return ImplementationRoadmap(
            phases=phases,
            resources=resources,
            timeline=timeline,
            risks=risks,
            budget=self._estimate_budget(resources, timeline),
            feasibility_notes=feasibility_notes
        )

    def generate_innovation_analysis(
        self,
        hypothesis_data: Dict,
        fitness_result: Dict,
        patch_log: List[Dict]
    ) -> InnovationAnalysis:
        """
        生成创新点分析

        Args:
            hypothesis_data: 假设数据
            fitness_result: 适应度结果
            patch_log: 补丁日志

        Returns:
            InnovationAnalysis: 创新点分析
        """
        logger.info("[OutputEnhancer] 生成创新点分析")

        title = hypothesis_data.get('title', '')
        details = hypothesis_data.get('details', '')
        methodology = hypothesis_data.get('methodology', {})
        inferred_domain = str(hypothesis_data.get('domain', '') or hypothesis_data.get('field', '') or '')
        domain_context = self._build_domain_context(hypothesis_data, inferred_domain)
        research_focus = self._infer_research_focus(hypothesis_data)

        # 提取核心创新点
        core_innovations = self._extract_core_innovations(
            title, details, methodology, patch_log
        )

        # 评估新颖度等级
        novelty_level = self._assess_novelty_level(
            fitness_result, core_innovations
        )

        # 分析差异化
        differentiation = self._analyze_differentiation(
            hypothesis_data, patch_log
        )

        # 评估突破潜力
        breakthrough_potential = self._assess_breakthrough_potential(
            hypothesis_data, fitness_result
        )
        breakthrough_potential['context'] = domain_context
        breakthrough_potential['research_focus'] = research_focus

        # 向量创新分析
        vector_analysis = {
            'score': fitness_result.get('vector_novelty_score', 0),
            'interpretation': self._interpret_vector_score(
                fitness_result.get('vector_novelty_score', 0)
            ),
            'similarity': fitness_result.get('similarity', 0),
            'similarity_interpretation': fitness_result.get(
                'similarity_interpretation', ''
            )
        }

        # 方法论创新分析
        methodology_analysis = self._analyze_methodology_innovation(
            methodology, patch_log
        )
        methodology_analysis['context'] = domain_context

        # 生成总结
        summary = self._generate_innovation_summary(
            core_innovations, novelty_level, vector_analysis, differentiation,
            breakthrough_potential, domain_context, research_focus
        )

        return InnovationAnalysis(
            core_innovations=core_innovations,
            novelty_level=novelty_level,
            differentiation=differentiation,
            breakthrough_potential=breakthrough_potential,
            vector_analysis=vector_analysis,
            methodology_analysis=methodology_analysis,
            summary=summary
        )

    def generate_frontier_analysis(
        self,
        hypothesis_data: Dict,
        verified_ids: Dict,
        domain: str,
        promise_score_components: Dict
    ) -> FrontierAnalysis:
        """
        生成前沿溯源分析

        Args:
            hypothesis_data: 假设数据
            verified_ids: 验证的文献ID
            domain: 研究领域
            promise_score_components: Promise Score 组件

        Returns:
            FrontierAnalysis: 前沿溯源分析
        """
        logger.info("[OutputEnhancer] 生成前沿溯源分析")

        pmids = verified_ids.get('pmids', [])
        arxiv_ids = verified_ids.get('arxiv_ids', [])

        # 前沿定位
        frontier_position = self._determine_frontier_position(
            hypothesis_data, promise_score_components
        )
        research_focus = self._infer_research_focus(hypothesis_data)

        # 关键出版物解读（基于 PMID 数量）
        key_publications = self._interpret_publications(
            pmids, arxiv_ids, domain, hypothesis_data
        )

        # 研究趋势
        research_trends = self._analyze_research_trends(
            hypothesis_data, domain
        )

        # 研究空白分析
        gap_analysis = self._identify_research_gaps(
            hypothesis_data, verified_ids
        )

        if research_focus and all(research_focus not in gap for gap in gap_analysis):
            gap_analysis.append(f'围绕“{research_focus}”的规范化验证路径仍不充分')

        # 领先团队（基于文献推断）
        leading_groups = self._infer_leading_groups(
            pmids, domain, hypothesis_data
        )

        # 前沿时间线
        timeline = self._construct_frontier_timeline(
            hypothesis_data, verified_ids, domain
        )

        # 引用速度和年份趋势
        citation_velocity = promise_score_components.get(
            'frontier_alignment', {}
        ).get('details', '').split('引用速度: ')[-1] if promise_score_components else 'normal'

        year_trend = self._assess_year_trend(hypothesis_data)

        return FrontierAnalysis(
            frontier_position=frontier_position,
            key_publications=key_publications,
            research_trends=research_trends,
            gap_analysis=gap_analysis,
            leading_groups=leading_groups,
            timeline=timeline,
            citation_velocity=citation_velocity,
            year_trend=year_trend
        )

    def _build_domain_context(self, hypothesis_data: Dict, domain: str) -> str:
        """构建领域上下文描述"""
        title = str(hypothesis_data.get('title', '')).strip()
        details = str(hypothesis_data.get('details', '')).strip()
        methodology = str(hypothesis_data.get('methodology', '')).strip()
        combined = ' '.join(part for part in [domain, title, details, methodology] if part)

        domain_tags = []
        if any(keyword in combined.lower() for keyword in ['machine learning', 'deep learning', 'ai', '模型', '预测']):
            domain_tags.append('以机器学习/预测建模为核心')
        if any(keyword in combined.lower() for keyword in ['clinical', 'patient', 'cohort', '临床', '患者', '队列']):
            domain_tags.append('强调临床或队列场景落地')
        if any(keyword in combined.lower() for keyword in ['causal', 'dag', '因果', '混杂']):
            domain_tags.append('突出因果识别与偏倚控制')
        if any(keyword in combined.lower() for keyword in ['omics', 'single-cell', '多组学', '单细胞']):
            domain_tags.append('包含高维组学或复杂生物数据')

        if not domain_tags:
            domain_tags.append('聚焦该领域的机制探索与方法学验证')

        return '；'.join(domain_tags[:3])

    def _infer_research_focus(self, hypothesis_data: Dict) -> str:
        """提取研究焦点"""
        title = str(hypothesis_data.get('title', '') or '').strip()
        if title:
            return title[:60] + ('...' if len(title) > 60 else '')

        core_hypothesis = str(hypothesis_data.get('core_hypothesis', '') or '').strip()
        if core_hypothesis:
            sentences = re.split(r'[。；\n]', core_hypothesis)
            first = next((sentence.strip() for sentence in sentences if sentence.strip()), core_hypothesis)
            return first[:60] + ('...' if len(first) > 60 else '')

        details = str(hypothesis_data.get('details', '') or '').strip()
        if details:
            sentences = re.split(r'[。；\n]', details)
            first = next((sentence.strip() for sentence in sentences if sentence.strip()), details)
            return first[:60] + ('...' if len(first) > 60 else '')

        background = str(hypothesis_data.get('background', '') or '').strip()
        if background:
            sentences = re.split(r'[。；\n]', background)
            first = next((sentence.strip() for sentence in sentences if sentence.strip()), background)
            return first[:60] + ('...' if len(first) > 60 else '')

        return '提升研究可信度与解释力的方法学优化'

    def _format_publication_note(self, identifier: str, domain: str, index: int, total_count: int) -> str:
        """生成出版物说明文本"""
        position_text = '奠基性参考' if index == 0 else ('方法学支撑' if index == 1 else '旁证文献')
        if total_count >= 8:
            activity_text = '说明该方向已有较活跃的持续研究积累'
        elif total_count >= 4:
            activity_text = '说明该方向已经形成较稳定的方法学讨论'
        else:
            activity_text = '说明该方向仍存在明显的拓展空间'
        return f"{position_text}，围绕 {domain or '当前主题'} 提供直接参考；{activity_text}。"

    def _estimate_focus_stage(self, hypothesis_data: Dict) -> str:
        """估计当前研究所处阶段"""
        combined = f"{hypothesis_data.get('title', '')} {hypothesis_data.get('details', '')} {hypothesis_data.get('methodology', '')}".lower()
        if any(keyword in combined for keyword in ['validation', 'external', 'prospective', '多中心', '外部验证']):
            return '从方法建立转向外部验证与临床转化'
        if any(keyword in combined for keyword in ['mechanism', 'pathway', '因果', 'dag']):
            return '从相关性发现迈向机制解释与因果识别'
        if any(keyword in combined for keyword in ['single-cell', 'spatial', 'diffusion', 'alphafold']):
            return '处于技术快速扩散后的深化应用阶段'
        return '处于由概念验证向规范化研究设计过渡的阶段'

    # ==================== 私有方法：落地指南 ====================

    def _assess_complexity(self, text: str) -> str:
        """评估研究复杂度"""
        text_lower = text.lower()

        for keyword in self.methodology_complexity['high']:
            if keyword.lower() in text_lower:
                return 'high'

        for keyword in self.methodology_complexity['medium']:
            if keyword.lower() in text_lower:
                return 'medium'

        return 'low'

    def _generate_phases(self, complexity: str, domain: str) -> List[Dict]:
        """生成研究阶段"""
        if complexity == 'high':
            return [
                {
                    'phase': 'Phase 1: 方案设计与数据准备',
                    'duration': '3-6个月',
                    'milestones': [
                        '完成详细实验方案设计',
                        '获取伦理委员会批准',
                        '建立数据采集管道',
                        '完成预实验验证'
                    ],
                    'deliverables': [
                        '实验方案 SOP',
                        '伦理批件',
                        '数据采集手册'
                    ]
                },
                {
                    'phase': 'Phase 2: 核心实验实施',
                    'duration': '12-24个月',
                    'milestones': [
                        '完成主要数据采集',
                        '完成中间分析',
                        '完成质量控制验证'
                    ],
                    'deliverables': [
                        '原始数据集',
                        '中期分析报告',
                        '质量控制报告'
                    ]
                },
                {
                    'phase': 'Phase 3: 数据分析与验证',
                    'duration': '6-12个月',
                    'milestones': [
                        '完成主要统计分析',
                        '完成交叉验证',
                        '完成敏感性分析'
                    ],
                    'deliverables': [
                        '统计分析报告',
                        '验证数据集',
                        '可复现代码'
                    ]
                },
                {
                    'phase': 'Phase 4: 论文撰写与发表',
                    'duration': '6-12个月',
                    'milestones': [
                        '完成初稿撰写',
                        '完成内部评审',
                        '完成同行评议回应',
                        '完成发表'
                    ],
                    'deliverables': [
                        '研究论文',
                        '补充材料',
                        '数据与代码共享'
                    ]
                }
            ]
        elif complexity == 'medium':
            return [
                {
                    'phase': 'Phase 1: 实验准备',
                    'duration': '2-4个月',
                    'milestones': ['方案设计', '伦理批准', '样本准备'],
                    'deliverables': ['实验方案', '伦理批件']
                },
                {
                    'phase': 'Phase 2: 数据采集',
                    'duration': '6-12个月',
                    'milestones': ['完成实验', '数据质控'],
                    'deliverables': ['实验数据', '质控报告']
                },
                {
                    'phase': 'Phase 3: 分析与发表',
                    'duration': '4-8个月',
                    'milestones': ['数据分析', '论文撰写', '投稿发表'],
                    'deliverables': ['论文', '补充材料']
                }
            ]
        else:  # low
            return [
                {
                    'phase': 'Phase 1: 实验实施',
                    'duration': '1-3个月',
                    'milestones': ['完成实验', '数据收集'],
                    'deliverables': ['实验数据']
                },
                {
                    'phase': 'Phase 2: 结果分析',
                    'duration': '1-2个月',
                    'milestones': ['数据分析', '论文撰写'],
                    'deliverables': ['分析报告', '论文']
                }
            ]

    def _generate_resources(
        self,
        complexity: str,
        domain: str,
        methodology: Dict
    ) -> Dict:
        """生成资源需求"""
        # 人力需求
        if complexity == 'high':
            personnel = {
                'PI (项目负责人)': '1人，20%时间投入，负责研究方向与关键里程碑决策',
                'Co-PI (联合负责人)': '1人，30%时间投入，负责跨团队协调与方法学把关',
                '博士后研究员': '2-3人，全职，承担实验推进、模型实现与结果复核',
                '博士研究生': '2-4人，负责数据整理、子课题实验与分析迭代',
                '技术员': '1-2人，负责样本处理、平台操作与质控执行',
                '数据分析师': '1人，负责统计建模、复现包整理与可视化',
                '统计顾问': '1人（兼职），负责功效分析与敏感性分析审阅'
            }
        elif complexity == 'medium':
            personnel = {
                'PI': '1人，30%时间投入，负责总体设计与关键结果把关',
                '博士后/博士生': '1-2人，负责核心实验与数据分析',
                '技术员': '1人，负责样本处理和流程执行'
            }
        else:
            personnel = {
                'PI': '1人，10%时间投入，负责研究设计与结果审阅',
                '研究生': '1人，负责数据处理、实验推进与初稿撰写'
            }

        # 设备需求
        equipment = self._generate_equipment_needs(methodology)
        equipment['narrative'] = f"结合 {domain or '当前领域'} 的研究任务，建议优先保障核心计算环境、数据存储和质量控制工具的持续可用性，避免项目在中期因资源瓶颈导致重复返工。"

        # 数据需求
        data_needs = self._generate_data_needs(methodology, domain)
        data_needs['narrative'] = '数据资源应同时覆盖训练/发现阶段与独立验证阶段，若涉及临床或队列研究，应预先锁定纳排标准、时间窗口与缺失值处理策略。'

        return {
            'personnel': personnel,
            'equipment': equipment,
            'data': data_needs,
            'coordination': {
                'description': '建议建立固定周会 + 关键节点审阅机制',
                'note': '用于同步实验进度、模型迭代与审稿级材料准备'
            }
        }

    def _generate_equipment_needs(self, methodology: Dict) -> Dict:
        """生成设备需求"""
        equipment = {
            'core_facility': [],
            'shared_instruments': [],
            'software': []
        }

        # 根据方法论关键词推断
        method_text = str(methodology).lower()

        if any(kw in method_text for kw in ['sequencing', 'seq', '测序']):
            equipment['core_facility'].extend([
                '高通量测序平台 (Illumina NovaSeq/NextSeq)',
                '生物信息分析工作站'
            ])

        if any(kw in method_text for kw in ['imaging', 'microscopy', '成像']):
            equipment['core_facility'].extend([
                '共聚焦显微镜',
                '高内涵筛选系统'
            ])

        if any(kw in method_text for kw in ['flow cytometry', 'facs', '流式']):
            equipment['shared_instruments'].append(
                '流式细胞仪/分选仪'
            )

        if any(kw in method_text for kw in ['machine learning', 'deep learning', 'ai']):
            equipment['software'].extend([
                'Python/R 计算环境',
                'GPU 计算节点 (可选)',
                '云存储资源'
            ])

        # 通用软件
        equipment['software'].extend([
            '统计分析软件 (R/Python)',
            '数据可视化工具',
            '版本控制系统 (Git)'
        ])

        return equipment

    def _generate_data_needs(self, methodology: Dict, domain: str) -> Dict:
        """生成数据需求"""
        return {
            'sample_size': {
                'description': '建议样本量',
                'note': '需根据功效分析 (Power Analysis) 确定'
            },
            'data_sources': self._infer_data_sources(methodology, domain),
            'storage': {
                'description': '数据存储需求',
                'estimated': '根据实际数据量确定，建议预留 1TB 起始空间'
            }
        }

    def _infer_data_sources(self, methodology: Dict, domain: str) -> List[str]:
        """推断数据来源"""
        sources = []

        # 公共数据库
        if any(kw in str(methodology).lower() for kw in ['tcga', 'geo', 'array', 'public']):
            sources.extend([
                'TCGA (癌症基因组图谱)',
                'GEO (基因表达数据库)',
                'SRA (序列读取档案)'
            ])

        # 队列研究
        if 'cohort' in str(methodology).lower() or '队列' in str(methodology):
            sources.append('前瞻性队列研究')

        # 临床样本
        if any(kw in str(methodology).lower() for kw in ['patient', 'clinical', 'sample']):
            sources.append('临床样本采集')

        return sources if sources else ['根据研究设计确定']

    def _generate_timeline(self, complexity: str) -> Dict:
        """生成时间线"""
        if complexity == 'high':
            return {
                'total_duration': '24-54个月',
                'phase_breakdown': '3-6月 + 12-24月 + 6-12月 + 6-12月',
                'critical_path': '数据采集 -> 分析 -> 验证 -> 发表',
                'buffer_time': '建议预留 20% 缓冲时间'
            }
        elif complexity == 'medium':
            return {
                'total_duration': '12-24个月',
                'phase_breakdown': '2-4月 + 6-12月 + 4-8月',
                'critical_path': '实验 -> 分析 -> 发表',
                'buffer_time': '建议预留 15% 缓冲时间'
            }
        else:
            return {
                'total_duration': '3-6个月',
                'phase_breakdown': '1-3月 + 1-2月',
                'critical_path': '实验 -> 分析',
                'buffer_time': '建议预留 10% 缓冲时间'
            }

    def _generate_risks(self, hypothesis_data: Dict, domain: str) -> List[Dict]:
        """生成风险评估"""
        risks = []
        research_focus = self._infer_research_focus(hypothesis_data)

        risks.append({
            'category': '技术风险',
            'description': '实验技术或模型设计可能无法稳定达到预期效果',
            'mitigation': '在正式研究前先完成小规模预实验，并保留替代技术路线以便快速切换',
            'severity': 'medium'
        })

        risks.append({
            'category': '数据风险',
            'description': '数据质量、样本量或标签定义可能不足以支撑主要结论',
            'mitigation': '制定严格质控标准，进行中期功效分析，并在必要时补充独立验证数据集',
            'severity': 'high'
        })

        risks.append({
            'category': '时间风险',
            'description': '跨阶段依赖较多，关键实验或验证可能拖慢整体进度',
            'mitigation': '设置里程碑检查点，将数据准备、主分析和复现整理并行推进',
            'severity': 'medium'
        })

        if '临床' in str(hypothesis_data) or domain in ['心血管疾病', '癌症']:
            risks.append({
                'category': '伦理风险',
                'description': '涉及人体样本或患者数据时，伦理审批和数据访问可能成为瓶颈',
                'mitigation': '提前准备伦理申请、数据使用协议和脱敏流程，避免主实验启动后等待审批',
                'severity': 'high'
            })

        if any(keyword in research_focus.lower() for keyword in ['causal', '因果', '预测', 'model', '模型']):
            risks.append({
                'category': '方法学风险',
                'description': f'围绕“{research_focus}”的结论容易受到泄漏、混杂或评估偏差影响',
                'mitigation': '强制采用患者级/时间级切分、训练折内预处理、敏感性分析和独立 hold-out 验证',
                'severity': 'high'
            })

        return risks

    def _generate_feasibility_notes(
        self,
        hypothesis_data: Dict,
        fitness_result: Dict
    ) -> List[str]:
        """生成可行性备注"""
        notes = []
        research_focus = self._infer_research_focus(hypothesis_data)

        physical_validation = fitness_result.get('physical_validation', {})
        if not physical_validation.get('passed', True):
            notes.append(
                '[警告] 物理可行性验证未通过，请优先重新评估假说的科学基础与可测量路径。'
            )

        hybrid_fitness = fitness_result.get('hybrid_fitness', 0)
        if hybrid_fitness >= 8.0:
            notes.append(
                f'[优秀] 综合适应度评分较高，说明“{research_focus}”具备较强的科学可行性，但仍建议在正式结论前补足独立验证与复现包。'
            )
        elif hybrid_fitness >= 6.0:
            notes.append(
                f'[良好] 综合适应度处于可推进区间，建议先围绕“{research_focus}”收紧纳排标准、验证协议和关键对照设计。'
            )
        else:
            notes.append(
                f'[注意] 综合适应度偏低，建议先缩小问题范围，明确“{research_focus}”的最小可验证版本后再扩展研究。'
            )

        methodology = hypothesis_data.get('methodology', {})
        if methodology:
            notes.append(
                '[方法论] 当前假设已包含方法论设计草图，但建议把技术保障、偏倚控制、超参数选择与最终评估边界写成可审计流程。'
            )

        if any(keyword in str(methodology).lower() for keyword in ['machine learning', '模型', 'validation', 'causal', 'dag']):
            notes.append(
                '[执行提醒] 若研究涉及预测模型或因果推断，应提前冻结切分策略、特征工程边界和主要终点定义，避免后期出现数据穿越或结论边界漂移。'
            )

        return notes

    def _estimate_budget(self, resources: Dict, timeline: Dict) -> Dict:
        """预算估算"""
        # 简化估算，实际应根据具体项目调整
        personnel_count = len(resources.get('personnel', {}))
        duration_months = 24  # 默认

        # 解析时间
        total_duration = timeline.get('total_duration', '')
        if '24' in total_duration or '54' in total_duration:
            duration_months = 36
        elif '12' in total_duration:
            duration_months = 18
        elif '3' in total_duration or '6' in total_duration:
            duration_months = 6

        # 粗略估算 (单位: 万元)
        estimated = personnel_count * duration_months * 0.5

        return {
            'estimated_total': f"{estimated:.0f} 万元",
            'note': '此为粗略估算，实际预算需根据具体情况调整',
            'breakdown': {
                '人力成本': f"{estimated * 0.6:.0f} 万元",
                '设备使用': f"{estimated * 0.2:.0f} 万元",
                '材料消耗': f"{estimated * 0.15:.0f} 万元",
                '其他费用': f"{estimated * 0.05:.0f} 万元"
            }
        }

    # ==================== 私有方法：创新点分析 ====================

    def _extract_core_innovations(
        self,
        title: str,
        details: str,
        methodology: Dict,
        patch_log: List[Dict]
    ) -> List[Dict]:
        """提取核心创新点"""
        innovations = []

        # 从补丁日志提取（说明修复了什么问题）
        for patch in patch_log:
            attack_type = patch.get('attack_type', '')
            patch_applied = patch.get('patch_applied', '')

            if attack_type and patch_applied:
                innovations.append({
                    'type': self._translate_attack_type(attack_type),
                    'description': patch_applied,
                    'source': '红蓝对抗补丁'
                })

        # 从方法论提取
        tech_safeguards = methodology.get('technical_safeguards', [])
        for safeguard in tech_safeguards:
            if '首次' in safeguard or '创新' in safeguard or '独特' in safeguard:
                innovations.append({
                    'type': '方法论创新',
                    'description': safeguard,
                    'source': '方法论设计'
                })

        # 从标题和详情提取
        combined = f"{title} {details}"
        innovation_keywords = [
            ('新颖', '新颖性设计'),
            ('首创', '首创性方法'),
            ('突破', '突破性进展'),
            ('独特', '独特性视角')
        ]

        for keyword, label in innovation_keywords:
            if keyword in combined:
                # 提取相关句子
                sentences = re.split(r'[。；]', combined)
                for sentence in sentences:
                    if keyword in sentence:
                        innovations.append({
                            'type': label,
                            'description': sentence.strip(),
                            'source': '假设描述'
                        })
                        break

        return innovations[:5]  # 最多返回5个

    def _translate_attack_type(self, attack_type: str) -> str:
        """翻译攻击类型为中文"""
        translations = {
            '数据穿越': '数据泄露防御',
            '内生性偏倚': '因果推断框架',
            'OVERFITTING': '过拟合防御',
            'LEAKAGE': '信息泄露防控',
            'BIAS': '偏倚控制',
            'VALIDATION': '验证协议'
        }
        return translations.get(attack_type, attack_type)

    def _assess_novelty_level(
        self,
        fitness_result: Dict,
        innovations: List[Dict]
    ) -> str:
        """评估新颖度等级"""
        vector_score = fitness_result.get('vector_novelty_score', 0)

        if vector_score >= 9.0:
            return 'breakthrough'  # 突破性
        elif vector_score >= 7.0:
            return 'incremental_high'  # 高度渐进性
        elif vector_score >= 5.0:
            return 'incremental_medium'  # 中度渐进性
        else:
            return 'incremental_low'  # 低度渐进性

    def _analyze_differentiation(
        self,
        hypothesis_data: Dict,
        patch_log: List[Dict]
    ) -> List[str]:
        """分析差异化"""
        differentiation = []

        # 从补丁日志提取差异化点
        for patch in patch_log:
            patch_desc = str(patch.get('patch_applied', '') or '').strip()
            if patch_desc:
                differentiation.append(f"vs. 现有研究: {patch_desc}")

        # 从方法论提取
        methodology = hypothesis_data.get('methodology', {})
        validation_protocol = str(methodology.get('validation_protocol', '') or '').strip()
        if validation_protocol:
            differentiation.append(f"验证协议差异: {validation_protocol}")

        bias_control = str(methodology.get('bias_control', '') or '').strip()
        if bias_control:
            differentiation.append(f"偏倚控制差异: {bias_control}")

        deduped = []
        seen = set()
        for item in differentiation:
            if not item or item in seen:
                continue
            seen.add(item)
            deduped.append(item)

        return deduped[:4]

    def _assess_breakthrough_potential(
        self,
        hypothesis_data: Dict,
        fitness_result: Dict
    ) -> Dict:
        """评估突破潜力"""
        vector_score = fitness_result.get('vector_novelty_score', 0)
        similarity = fitness_result.get('similarity', 0)

        # 突破潜力评估
        if vector_score >= 9.0 and 0.4 <= similarity <= 0.7:
            level = 'high'
            description = '具有成为领域突破性研究的潜力'
        elif vector_score >= 7.0:
            level = 'medium'
            description = '有望产生重要影响的研究'
        else:
            level = 'normal'
            description = '常规性研究进展'

        return {
            'level': level,
            'description': description,
            'factors': [
                f'向量新颖度: {vector_score:.2f}',
                f'相似度位置: {similarity:.2f}',
                f'方法论严谨性: {fitness_result.get("red_team_rigor_score", 0):.2f}'
            ]
        }

    def _interpret_vector_score(self, score: float) -> str:
        """解读向量评分"""
        if score >= 9.5:
            return '极高新颖性 - 向量空间中与现有研究距离远'
        elif score >= 8.0:
            return '高新颖性 - 创新性较强'
        elif score >= 6.0:
            return '中等新颖性 - 有一定创新'
        else:
            return '低新颖性 - 与现有研究较为接近'

    def _analyze_methodology_innovation(
        self,
        methodology: Dict,
        patch_log: List[Dict]
    ) -> Dict:
        """分析方法论创新"""
        return {
            'rigor_score': len(patch_log) * 1.5,  # 补丁越多说明越严谨
            'has_technical_safeguards': bool(methodology.get('technical_safeguards')),
            'has_validation_protocol': bool(methodology.get('validation_protocol')),
            'has_bias_control': bool(methodology.get('bias_control')),
            'patch_count': len(patch_log),
            'summary': f"应用了 {len(patch_log)} 个方法论补丁，"
                       f"涵盖数据泄露防控、因果推断等多个方面"
        }

    def _generate_innovation_summary(
        self,
        innovations: List[Dict],
        novelty_level: str,
        vector_analysis: Dict,
        differentiation: List[str],
        breakthrough_potential: Dict,
        domain_context: str,
        research_focus: str
    ) -> str:
        """生成创新点总结"""
        level_map = {
            'breakthrough': '突破性',
            'incremental_high': '高度渐进性',
            'incremental_medium': '中度渐进性',
            'incremental_low': '低度渐进性'
        }

        lines = [
            f"本研究的创新性属于【{level_map.get(novelty_level, novelty_level)}】创新，整体定位为：{domain_context}。",
            f"从研究问题来看，当前工作的核心聚焦于“{research_focus}”，因此其价值不只在于提出一个新想法，更在于把问题转化为可验证、可复现、可被同行审阅的方法学路径。"
        ]

        if innovations:
            lines.append('核心创新点主要体现在以下方面：')
            for index, innovation in enumerate(innovations[:5], 1):
                innovation_type = innovation.get('type', '创新点')
                description = str(innovation.get('description', '') or '').strip()
                source = str(innovation.get('source', '') or '').strip()
                source_text = f"（来源：{source}）" if source else ''
                if description:
                    lines.append(f"{index}. {innovation_type}：{description}{source_text}")
        else:
            lines.append('当前尚未抽取到明确的显式创新点，建议进一步补强标题、方法论和补丁日志中的创新表达。')

        if differentiation:
            lines.append('与现有研究相比，本方案的差异化重点包括：')
            for item in differentiation[:3]:
                lines.append(f"- {item}")

        lines.append(
            f"向量新颖度评分为 {vector_analysis.get('score', 0):.2f}/10，{vector_analysis.get('interpretation', '')}；"
            f"相似度为 {vector_analysis.get('similarity', 0):.3f}，{vector_analysis.get('similarity_interpretation', '')}。"
        )

        if breakthrough_potential:
            factor_text = '；'.join(str(item) for item in breakthrough_potential.get('factors', []) if str(item).strip())
            lines.append(
                f"综合突破潜力评估为 {breakthrough_potential.get('level', 'normal')}，"
                f"原因是：{breakthrough_potential.get('description', '')}。"
                + (f" 主要依据包括：{factor_text}。" if factor_text else '')
            )

        lines.append('因此，这一创新并非停留在概念层面的“新”，而是体现为研究问题选择、方法学约束和验证路径设计三者的联合提升。')

        return '\n\n'.join(lines).strip()

    # ==================== 私有方法：前沿溯源分析 ====================

    def _determine_frontier_position(
        self,
        hypothesis_data: Dict,
        promise_score_components: Dict
    ) -> str:
        """确定前沿定位"""
        frontier_info = promise_score_components.get('frontier_alignment', {})
        score = frontier_info.get('score', 0)

        if score >= 9.0:
            return '前沿领跑 - 处于研究最前沿'
        elif score >= 7.5:
            return '前沿并跑 - 与国际先进水平同步'
        elif score >= 6.0:
            return '前沿跟随 - 接近国际先进水平'
        else:
            return '前沿追赶 - 有提升空间'

    def _interpret_publications(
        self,
        pmids: List[str],
        arxiv_ids: List[str],
        domain: str,
        hypothesis_data: Dict
    ) -> List[Dict]:
        """解读关键出版物"""
        publications = []
        total_count = len(pmids) + len(arxiv_ids)
        research_focus = self._infer_research_focus(hypothesis_data)

        if total_count == 0:
            publications.append({
                'type': 'note',
                'content': (
                    f'当前未检索到与“{research_focus}”直接对应的已验证文献，这可能意味着问题具有原创性，'
                    '也意味着后续需要更谨慎地补充旁证文献与方法学依据。'
                ),
                'pmids': []
            })
        else:
            publications.append({
                'type': 'field_signal',
                'content': (
                    f'共检索到 {total_count} 篇相关文献，说明 {domain or "当前方向"} 已形成一定研究积累；'
                    f'围绕“{research_focus}”的工作更适合定位为在既有前沿上的细化推进，而非完全脱离文献背景的孤立设想。'
                ),
                'pmids': pmids[:5]
            })

        for index, pmid in enumerate(pmids[:5]):
            publications.append({
                'type': 'key_reference',
                'content': self._format_publication_note(str(pmid), domain, index, total_count),
                'pmids': [pmid],
                'pmid': pmid
            })

        for arxiv_id in arxiv_ids[:2]:
            publications.append({
                'type': 'preprint_signal',
                'content': f'arXiv:{arxiv_id} 提示该方向在预印本层面已有快速迭代迹象，适合重点关注方法学更新与最新 benchmark。',
                'pmids': [],
                'identifier': arxiv_id
            })

        return publications

    def _analyze_research_trends(
        self,
        hypothesis_data: Dict,
        domain: str
    ) -> List[str]:
        """分析研究趋势"""
        trends = []

        # 通用趋势
        trends.extend([
            '多组学数据整合成为主流研究范式',
            '人工智能辅助研究设计快速增长',
            '因果推断方法在临床研究中广泛应用'
        ])

        # 领域特定趋势
        domain_trends = {
            '心血管疾病': [
                '心血管疾病精准医学快速发展',
                '心脏再生医学取得突破进展'
            ],
            '癌症': [
                '免疫治疗持续火热',
                'CAR-T 等细胞治疗技术成熟'
            ],
            '神经科学': [
                '脑连接组学成为新热点',
                '神经退行性疾病机制研究深入'
            ],
            '代谢疾病': [
                '肠道微生物组与代谢疾病关联研究活跃',
                'NAFLD/NASH 新药研发加速'
            ],
            '衰老生物学': [
                '衰老细胞清除 (Senolytics) 进入临床',
                '端粒与寿命关联研究持续'
            ]
        }

        trends.extend(domain_trends.get(domain, []))

        return trends[:5]

    def _identify_research_gaps(
        self,
        hypothesis_data: Dict,
        verified_ids: Dict
    ) -> List[str]:
        """识别研究空白"""
        gaps = []

        # 基于假设内容推断空白
        details = hypothesis_data.get('details', '')

        if '因果' in details or 'causal' in details.lower():
            gaps.append('现有研究缺乏严格的因果推断框架')

        if '验证' in details or 'validation' in details.lower():
            gaps.append('现有研究缺乏独立验证数据集')

        if '多中心' in details or 'multi-center' in details.lower():
            gaps.append('缺乏大规模多中心验证研究')

        gaps.append('本假设针对的研究问题尚未被充分探索')

        return gaps[:4]

    def _infer_leading_groups(
        self,
        pmids: List[str],
        domain: str,
        hypothesis_data: Dict
    ) -> List[Dict]:
        """推断领先团队（增强版）"""
        focus = self._infer_research_focus(hypothesis_data)
        groups = [
            {
                'type': 'research_alliance',
                'content': f'{domain or "该领域"}多中心协作网络通常是推动“{focus}”进入高影响力期刊的主要力量',
                'action': '优先关注多中心队列、公开 benchmark 与共享分析框架'
            },
            {
                'type': 'methodology_team',
                'content': '方法学领先团队通常掌握数据切分、偏倚控制、外部验证和复现包交付等标准化流程',
                'action': '对标其 supplementary materials 与公开代码结构'
            }
        ]

        if pmids:
            groups.append({
                'type': 'literature_signal',
                'content': f'当前已检索到 {len(pmids)} 个 PMID，可进一步据此追踪高频作者、机构和联盟名称，识别真正的头部团队。',
                'action': '基于 PMID 元数据做作者/机构共现分析'
            })

        return groups

    def _construct_frontier_timeline(
        self,
        hypothesis_data: Dict,
        verified_ids: Dict,
        domain: str
    ) -> List[Dict]:
        """构建前沿时间线"""
        focus = self._infer_research_focus(hypothesis_data)
        stage_hint = self._estimate_focus_stage(hypothesis_data)

        return [
            {
                'period': '2018-2020',
                'stage': '基础研究积累',
                'description': f'{domain or "相关领域"}开始形成与“{focus}”相关的基础理论、数据资源和早期分析框架。'
            },
            {
                'period': '2021-2023',
                'stage': '技术方法突破',
                'description': '更成熟的计算工具、验证协议与高维数据分析流程推动该问题从概念验证走向可重复研究。'
            },
            {
                'period': '2024-2026',
                'stage': '当前研究前沿',
                'description': f'当前重点已转向 {stage_hint}，研究竞争点主要集中在方法学严谨性、泛化能力与机制解释。'
            },
            {
                'period': '2026+',
                'stage': '未来发展方向',
                'description': '后续高价值工作通常会围绕多中心验证、标准化复现包和更强的转化落地证据展开。'
            }
        ]

    def _assess_year_trend(self, hypothesis_data: Dict) -> str:
        """评估年份趋势"""
        focus = self._infer_research_focus(hypothesis_data)
        return f'2024-2026 持续升温，围绕“{focus}”的研究正从概念验证转向规范化验证与转化评估'


# ==================== 便捷函数 ====================

def create_output_enhancer(llm_client=None) -> OutputEnhancer:
    """
    创建输出增强器实例

    Args:
        llm_client: LLM 客户端（可选）

    Returns:
        OutputEnhancer: 输出增强器实例
    """
    return OutputEnhancer(llm_client=llm_client)


# ==================== 导出 ====================

__all__ = [
    'OutputEnhancer',
    'ImplementationRoadmap',
    'InnovationAnalysis',
    'FrontierAnalysis',
    'create_output_enhancer',
]
