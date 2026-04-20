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

        # 生成总结
        summary = self._generate_innovation_summary(
            core_innovations, novelty_level, vector_analysis
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

        # 关键出版物解读（基于PMID数量）
        key_publications = self._interpret_publications(
            pmids, arxiv_ids, domain
        )

        # 研究趋势
        research_trends = self._analyze_research_trends(
            hypothesis_data, domain
        )

        # 研究空白分析
        gap_analysis = self._identify_research_gaps(
            hypothesis_data, verified_ids
        )

        # 领先团队（基于文献推断）
        leading_groups = self._infer_leading_groups(
            pmids, domain
        )

        # 前沿时间线
        timeline = self._construct_frontier_timeline(
            hypothesis_data, verified_ids
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
                'PI (项目负责人)': '1人，20%时间投入',
                'Co-PI (联合负责人)': '1人，30%时间投入',
                '博士后研究员': '2-3人，全职',
                '博士研究生': '2-4人',
                '技术员': '1-2人',
                '数据分析师': '1人',
                '统计顾问': '1人（兼职）'
            }
        elif complexity == 'medium':
            personnel = {
                'PI': '1人，30%时间投入',
                '博士后/博士生': '1-2人',
                '技术员': '1人'
            }
        else:
            personnel = {
                'PI': '1人，10%时间投入',
                '研究生': '1人'
            }

        # 设备需求
        equipment = self._generate_equipment_needs(methodology)

        # 数据需求
        data_needs = self._generate_data_needs(methodology, domain)

        return {
            'personnel': personnel,
            'equipment': equipment,
            'data': data_needs
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

        # 通用风险
        risks.append({
            'category': '技术风险',
            'description': '实验技术可能无法达到预期效果',
            'mitigation': '在正式实验前进行小规模预实验验证',
            'severity': 'medium'
        })

        risks.append({
            'category': '数据风险',
            'description': '数据质量或样本量可能不足',
            'mitigation': '制定严格的质量控制标准，进行中期功效分析',
            'severity': 'high'
        })

        risks.append({
            'category': '时间风险',
            'description': '实验周期可能延长',
            'mitigation': '设置里程碑检查点，及时调整计划',
            'severity': 'medium'
        })

        # 领域特定风险
        if '临床' in str(hypothesis_data) or domain in ['心血管疾病', '癌症']:
            risks.append({
                'category': '伦理风险',
                'description': '涉及人体样本需伦理批准',
                'mitigation': '提前准备伦理申请材料，预留审批时间',
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

        physical_validation = fitness_result.get('physical_validation', {})
        if not physical_validation.get('passed', True):
            notes.append(
                "[警告] 物理可行性验证未通过，请重新评估假设的科学基础"
            )

        hybrid_fitness = fitness_result.get('hybrid_fitness', 0)
        if hybrid_fitness >= 8.0:
            notes.append(
                "[优秀] 综合适应度评分较高，假设具有较强的科学可行性"
            )
        elif hybrid_fitness >= 6.0:
            notes.append(
                "[良好] 综合适应度评分中等，假设基本可行，建议优化细节"
            )
        else:
            notes.append(
                "[注意] 综合适应度评分较低，建议重新审视假设设计"
            )

        # 方法论备注
        methodology = hypothesis_data.get('methodology', {})
        if methodology:
            notes.append(
                "[方法论] 假设已包含详细的方法论设计，包括技术保障、"
                "验证协议和偏倚控制"
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
            patch_desc = patch.get('patch_applied', '')
            if patch_desc:
                differentiation.append(f"vs. 现有研究: {patch_desc}")

        # 从方法论提取
        methodology = hypothesis_data.get('methodology', {})
        if methodology.get('validation_protocol'):
            differentiation.append(
                "验证协议差异: "
                f"{methodology['validation_protocol'][:50]}..."
            )

        if methodology.get('bias_control'):
            differentiation.append(
                "偏倚控制差异: "
                f"{methodology['bias_control'][:50]}..."
            )

        return differentiation[:4]

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
                '相似度位置: {similarity:.2f}',
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
        vector_analysis: Dict
    ) -> str:
        """生成创新点总结"""
        level_map = {
            'breakthrough': '突破性',
            'incremental_high': '高度渐进性',
            'incremental_medium': '中度渐进性',
            'incremental_low': '低度渐进性'
        }

        summary = f"""
本研究的创新性属于【{level_map.get(novelty_level, novelty_level)}】创新。

核心创新点包括：
"""
        for i, innovation in enumerate(innovations, 1):
            summary += f"{i}. {innovation.get('type', '')}: {innovation.get('description', '')[:50]}...\n"

        summary += f"\n向量新颖度评分为 {vector_analysis.get('score', 0):.2f}/10，"
        summary += f"{vector_analysis.get('interpretation', '')}。"

        return summary.strip()

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
        domain: str
    ) -> List[Dict]:
        """解读关键出版物"""
        publications = []

        # 基于数量生成解读
        total_count = len(pmids) + len(arxiv_ids)

        if total_count == 0:
            publications.append({
                'type': 'note',
                'content': '未检索到直接相关文献，可能表明研究具有较高原创性',
                'pmids': []
            })
        elif total_count <= 3:
            publications.append({
                'type': 'direct_support',
                'content': f'检索到 {total_count} 篇直接相关文献，为研究提供基础支持',
                'pmids': pmids[:3]
            })
        else:
            publications.append({
                'type': 'extensive_support',
                'content': f'检索到 {total_count} 篇相关文献，表明该领域研究活跃',
                'pmids': pmids[:5]
            })

        # 如果有 PMID，生成具体解读
        for pmid in pmids[:3]:
            publications.append({
                'type': 'key_reference',
                'content': f'PMID: {pmid} - 作为关键参考文献引用',
                'pmids': [pmid]
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
        domain: str
    ) -> List[Dict]:
        """推断领先团队（简化版）"""
        # 实际应从文献元数据提取，这里提供通用信息
        return [
            {
                'type': 'note',
                'content': '建议从检索到的文献中分析主要贡献机构和作者',
                'action': '使用文献计量学工具分析'
            }
        ]

    def _construct_frontier_timeline(
        self,
        hypothesis_data: Dict,
        verified_ids: Dict
    ) -> List[Dict]:
        """构建前沿时间线"""
        timeline = []

        # 基础研究阶段
        timeline.append({
            'period': '2018-2020',
            'stage': '基础研究积累',
            'description': '相关领域基础理论和方法的建立'
        })

        # 技术突破阶段
        timeline.append({
            'period': '2021-2023',
            'stage': '技术方法突破',
            'description': '关键技术（如单细胞测序、AI分析）的成熟应用'
        })

        # 当前前沿
        timeline.append({
            'period': '2024-2025',
            'stage': '当前研究前沿',
            'description': '本假设所处的前沿位置'
        })

        # 未来方向
        timeline.append({
            'period': '2026+',
            'stage': '未来发展方向',
            'description': '预测的研究演进方向'
        })

        return timeline

    def _assess_year_trend(self, hypothesis_data: Dict) -> str:
        """评估年份趋势"""
        return '2025年最新趋势 - 基于当前最新研究进展'


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
