"""
假设评审智能体（顶尖生物医学数据科学家级别）
《Nature》杂志高级编辑 × 数据科学专家

严格的审稿标准：
- 广度与深度的颠覆性 (10分)
- 方法论的原创性 (10分)
- 验证的可行性 (10分)
- **数据科学红线** (新增：数据泄露、泛化能力、样本量匹配)
"""
from typing import Dict, List, Optional
import json
import sys
import os
import re
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import BaseAgent
from core.database import Hypothesis, Paper
from utils.pubmed import PubMedSearcher
from utils.llm_utils import SafeExtractor, LLMParseError
import anthropic


# ==================== 反幻觉断路器 (Anti-Hallucination Breaker) ====================

ANTI_HALLUCINATION_PROTOCOL = """
---

## 🚨 【检索终���协议：工具死循环防范】

当文献检索达到最大次数（3次）仍未找到直接支持时：

### ✅ 你必须做的：
1. **诚实声明**：明确说明"经过3次检索尝试，未找到直接相关的文献支持"
2. **标注推测**：如需进行逻辑推理，必须标注【基于有限文献的未证实推测】
3. **建议放弃**：如果证据严重不足，建议"该假设分支缺乏文献支持，建议放弃"

### 🚫 绝对禁止：
1. **捏造检索结果**：禁止编造"检索到X篇相关文献"（实际没有）
2. **虚构引用**：禁止编造PMID、DOI、作者名、期刊名
3. **伪造数据**：禁止编造样本量、效应量、p值等实验结果
4. **把推测当事实**：禁止将未证实的推测当作已证实事实陈述

**违反此协议属于学术不端，系统将终止你��输出并记录违规。**

---

"""

# ================================================================================


# Nature级别评估标准（数据科学增强版）
NATURE_STANDARDS = {
    'transformative_impact': {
        'name': '广度与深度的颠覆性',
        'description': '必须具备跨学科影响力，能够改写教科书或临床指南',
        'scoring': {
            'excellent (9-10)': '跨多个领域的范式转移，影响整个学科方向',
            'good (7-8)': '对某一子领域有显著影响',
            'fair (5-6)': '影响局限于狭窄应用',
            'poor (3-4)': '增量式改进',
            'reject (1-2)': '无实质贡献'
        },
        'reject_patterns': [
            '单一疾病/组织的算法优化',
            '特定数据集的性能提升',
            '方法的简单应用或比较',
            '缺乏跨学科或跨领域潜力'
        ]
    },
    'methodological_originality': {
        'name': '方法论的原创性',
        'description': '必须是底层算法结构的创新，而非微调或堆砌',
        'scoring': {
            'excellent (9-10)': '全新的算法范式或理论框架',
            'good (7-8)': '显著的方法论创新',
            'fair (5-6)': '方法的合理组合或改进',
            'poor (3-4)': '微调或简单堆砌',
            'reject (1-2)': '无原创性'
        },
        'reject_patterns': [
            'Fine-tune预训练模型',
            '多个现有模型的简单堆砌',
            '超参数调优',
            '仅在特定数据上复现现有方法'
        ]
    },
    'poc_feasibility': {
        'name': '验证的可行性',
        'description': '利用全球公开算力和超级数据库能否完成初步概念验证',
        'scoring': {
            'excellent (9-10)': '使用百万级数据，PoC完全可行',
            'good (7-8)': '使用十万级数据，PoC基本可行',
            'fair (5-6)': '数据规模偏小但可能可行',
            'poor (3-4)': '数据获取困难',
            'reject (1-2)': '无法获取所需数据'
        },
        'mega_scale_databases': [
            'UK Biobank (500,000+)',
            'All of Us (1,000,000+)',
            'Human Cell Atlas (10^7+ cells)',
            'GTEx (50,000+, 多组织)',
            'gnomAD (150,000+ genomes)',
            'TCGA (33种癌症，11,000+ 患者)',
            'MIMIC-IV (200,000+ ICU住院)'
        ]
    },
    'data_science_red_lines': {
        'name': '数据科学红线（新增）',
        'description': '评估假设是否存在数据科学方法学缺陷',
        'scoring': {
            'excellent (9-10)': '完全符合数据科学最佳实践',
            'good (7-8)': '基本符合，有小瑕疵',
            'fair (5-6)': '存在数据科学风险需说明',
            'poor (3-4)': '严重违反数据科学原则',
            'reject (1-2)': '存在致命的数据科学缺陷'
        },
        'red_lines': [
            '数据泄露风险：特征选择在CV外进行？时序数据未按时间分割？',
            '泛化能力缺失：未考虑跨中心/数据集泛化？无独立测试集？',
            '样本量不足：参数量 > 样本数/10？未使用预训练/迁移学习？',
            '评估指标不当：类别不平衡仅用AUROC？未进行统计检验？',
            '过拟合风险：未使用正则化？模型复杂度远超数据规模？'
        ]
    },
    'statistical_hardening': {
        'name': '强制性统计验证协议（地狱级）',
        'description': '严禁仅使用P-value，必须包含完整的统计验证链',
        'scoring': {
            'excellent (9-10)': '完整的Power+FDR+Mediation+E-value四件套',
            'good (7-8)': '包含Power+FDR+Mediation三件套',
            'fair (5-6)': '至少包含Power+FDR',
            'poor (3-4)': '仅有FDR或Power之一',
            'reject (1-2)': '仅依赖P-value，无任何高级统计方法'
        },
        'mandatory_components': [
            '1. 统计功效分析 (Power Analysis)：a priori样本量计算，post-hoc功效验证',
            '2. 多重假设检验校正 (FDR/Bonferroni)：明确校正方法和应用场景',
            '3. 中介效应检验 (Mediation Analysis)：机制路径验证，间接效应估计',
            '4. E-value敏感性分析：评估未测量混杂的耐受度'
        ],
        'reject_patterns': [
            '仅报告P值而忽略功效分析',
            '多重比较未进行FDR/Bonferroni校正',
            '声称因果关联但无中介分析或DAG因果图',
            '观察性研究无E-value或敏感性分析'
        ]
    }
}

# Nature级拒稿理由（一票否决）
REJECT_REASONS = {
    'incremental': {
        'name': '增量式改进',
        'patterns': [
            r'提高.*\d+.*%.*精度',
            r'优化.*超参数',
            r'调整.*参数.*性能',
            r'相比.*baseline.*提升',
            r'仅仅.*提高',
            r'单纯.*优化'
        ],
        'verdict': 'REJECT - 增量式改进不符合Nature标准'
    },
    'narrow_scope': {
        'name': '研究范围过窄',
        'patterns': [
            r'仅针对.*一种.*疾病',
            r'单一.*医院.*数据',
            r'小样本.*少于.*100',
            r'局限.*于.*特定.*人群'
        ],
        'verdict': 'REJECT - 研究范围过窄，缺乏跨学科影响力'
    },
    'derivative': {
        'name': '衍生性工作',
        'patterns': [
            r'仅仅.*基于.*现有.*模型',
            r'简单.*使用.*预训练',
            r'直接.*应用.*无改进',
            r'照搬.*现有.*方法'
        ],
        'verdict': 'REJECT - 对现有方法的衍生应用，原创性不足'
    },
    'comparison': {
        'name': '比较研究',
        'patterns': [
            r'仅比较.*多种.*方法',
            r'纯粹.*评估.*性能',
            r'只是.*benchmark.*测试',
            r'主要.*对比.*算法'
        ],
        'verdict': 'REJECT - 比较研究不足以构成Nature级别的原创贡献'
    },
    'statistical_deficiency': {
        'name': '统计验证缺陷（地狱级一票否决）',
        'patterns': [
            r'仅.*P.?值.*显著',
            r'未.*功效.*分析',
            r'未.*FDR.*校正',
            r'未.*多重.*校正',
            r'无.*中介.*分析'
        ],
        'verdict': 'REJECT - 统计验证不严谨：缺少Power Analysis、FDR校正、或Mediation分析'
    },
    'p_value_only': {
        'name': '仅依赖P值',
        'patterns': [
            r'P.*<.*0\.05.*显著',
            r'统计学意义.*P',
            r'仅.*统计.*显著'
        ],
        'verdict': 'REJECT - 仅报告P值不足以证明因果，必须包含功效分析、FDR校正、E-value'
    }
}


class ValidationAgent(BaseAgent):
    """
    《Nature》杂志高级编辑 × 数据科学专家

    评估维度：
    1. 广度与深度的颠覆性 (10分)
    2. 方法论的原创性 (10分)
    3. 验证的可行性 (10分)
    4. **数据科学红线** (新增：数据泄露、泛化能力、样本量匹配)
    5. **强制性统计验证协议** (地狱级：Power + FDR + Mediation + E-value)

    一票否决权：发现增量改进、范围过窄、衍生工作、比较研究、
                 **数据泄露风险、严重过拟合、统计验证缺陷** 直接拒稿
    """

    def __init__(self):
        super().__init__("Nature高级编辑", agent_type="validation")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.pubmed_searcher = None
        self.extractor = SafeExtractor()
        self.max_retries = 3
        # 审稿模式：低温度确保严格一致性
        self.temperature = 0.2  # ≤0.3 确保评审稳定一致

        # ==================== 反幻觉断路器：搜索失败计数器 ====================
        self._search_attempt_count = 0  # 搜索尝试次数
        self._max_search_attempts = 3   # 最大搜索次数
        # =======================================================================

    def _get_pubmed_searcher(self):
        if self.pubmed_searcher is None:
            email = os.getenv("PUBMED_EMAIL")
            api_key = os.getenv("PUBMED_API_KEY")
            self.pubmed_searcher = PubMedSearcher(email=email, api_key=api_key)
        return self.pubmed_searcher

    def reset_search_attempts(self):
        """重置搜索尝试计数器 - 用于新会话开始时"""
        self._search_attempt_count = 0
        print("🔄 [反幻觉断路器] 搜索尝试计数器已重置")

    def execute(self, input_data: Dict) -> Dict:
        """执行Nature级别评审"""
        hypothesis_id = input_data.get('hypothesis_id')
        hypothesis_data = input_data.get('hypothesis_data')
        source_papers = input_data.get('source_papers', [])
        enable_literature_check = input_data.get('enable_literature_check', True)
        output_dir = input_data.get('output_dir', 'reports')
        min_if = input_data.get('min_if', 10.0)  # 期刊白名单谓词下推：最低IF要求

        if not hypothesis_data:
            return {
                'success': False,
                'error': '没有提供假设数据',
                'validation': None
            }

        # 步骤1：一票否决检查
        reject_check = self._check_immediate_reject(hypothesis_data)
        if reject_check['should_reject']:
            validation_result = {
                'final_decision': 'rejected',
                'reject_reason': reject_check['reason'],
                'scores': {
                    'transformative_impact': reject_check['score'],
                    'methodological_originality': reject_check['score'],
                    'poc_feasibility': 0
                },
                'nature_verdict': 'REJECT'
            }
            # 生成拒稿决议书
            decision_path = self._generate_rejection_decision(
                hypothesis_data=hypothesis_data,
                reject_check=reject_check,
                output_dir=output_dir
            )
            validation_result['report_path'] = decision_path

            return {
                'success': True,
                'validation': validation_result,
                'hypothesis_id': hypothesis_id
            }

        # 步骤2：完整评估
        validation_result = self._validate_nature_level(
            hypothesis_data,
            source_papers,
            enable_literature_check
        )

        # 确保 validation_result 包含必要字段
        if 'final_decision' not in validation_result:
            validation_result['final_decision'] = self._determine_nature_decision(validation_result)
        if 'scores' not in validation_result:
            validation_result['scores'] = {
                'transformative_impact': 5,
                'methodological_originality': 5,
                'poc_feasibility': 5
            }

        # 更新数据库
        if hypothesis_id:
            with self.db_manager.get_session() as session:
                hypothesis = session.query(Hypothesis).filter_by(id=hypothesis_id).first()
                if hypothesis:
                    hypothesis.validation_status = validation_result.get('final_decision', 'pending')
                    scores = validation_result.get('scores', {})
                    hypothesis.feasibility_score = scores.get('poc_feasibility', 0)
                    hypothesis.novelty_score = scores.get('methodological_originality', 0)
                    hypothesis.technical_score = scores.get('transformative_impact', 0)
                    hypothesis.validation_notes = json.dumps(validation_result, ensure_ascii=False)

        # 生成决议书
        decision_path = self._generate_nature_decision(
            hypothesis_data=hypothesis_data,
            validation_result=validation_result,
            output_dir=output_dir
        )
        validation_result['report_path'] = decision_path

        return {
            'success': True,
            'validation': validation_result,
            'hypothesis_id': hypothesis_id
        }

    def _check_immediate_reject(self, hypothesis: Dict) -> Dict:
        """一票否决检查"""
        title = hypothesis.get('title', '').lower()
        description = hypothesis.get('description', '').lower()
        rationale = hypothesis.get('rationale', '').lower()
        full_text = title + ' ' + description + ' ' + rationale

        for reject_key, reject_info in REJECT_REASONS.items():
            for pattern in reject_info['patterns']:
                if re.search(pattern, full_text):
                    return {
                        'should_reject': True,
                        'reason': reject_info['verdict'],
                        'category': reject_key,
                        'score': 1
                    }

        return {'should_reject': False}

    def _validate_nature_level(self, hypothesis: Dict, source_papers: List[Dict],
                               enable_literature_check: bool) -> Dict:
        """Nature级别完整评估

        Raises:
            RuntimeError: 解析失败时抛出异常
        """
        # 文献查重
        literature_check_result = {}
        if enable_literature_check:
            literature_check_result = self._perform_literature_check(hypothesis, min_if=min_if)

        # 构建提示词
        prompt = self._build_nature_review_prompt(
            hypothesis=hypothesis,
            source_papers=source_papers,
            literature_check=literature_check_result
        )

        # 使用重试机制
        for attempt in range(self.max_retries):
            try:
                print("[Nature评审] 第 {}/{} 次尝试生成评审...".format(attempt + 1, self.max_retries))

                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=5000,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}]
                )

                response_text = self._extract_text_from_response(message.content)
                print("[Nature评审] 响应长度: {} 字符".format(len(response_text)))
                print("[Nature评审] 响应预览: {}...".format(response_text[:300]))

                validation_result = self._parse_nature_response(response_text)
                validation_result['literature_check'] = literature_check_result
                validation_result['final_decision'] = self._determine_nature_decision(validation_result)
                return validation_result

            except Exception as e:
                print("[Nature评审] 尝试 {} 失败: {}".format(attempt + 1, e))
                if attempt == self.max_retries - 1:
                    raise RuntimeError("Nature评审失败：经过 {} 次尝试后仍无法解析响应。最后错误: {}".format(self.max_retries, e))
                time.sleep(2 ** attempt)

        raise RuntimeError("Nature评审失败：重试次数耗尽")

    def _build_nature_review_prompt(self, hypothesis: Dict, source_papers: List[Dict],
                                  literature_check: Dict) -> str:
        """构建Nature评审提示词"""

        similar_works_section = ""
        if literature_check.get('similar_works'):
            similar_works_section += "\n## 文献查重结果\n\n"
            for work in literature_check['similar_works'][:3]:
                similar_works_section += "- **{}** ({}, {})\n".format(
                    work['title'], work['journal'], work['date']
                )

        # Nature级数据库清单
        db_list = "\n".join(["- " + db for db in NATURE_STANDARDS['poc_feasibility']['mega_scale_databases']])

        prompt = """你是《Nature》杂志的高级编辑**兼顶尖数据科学专家**，负责评审最具颠覆性的科研假设。

## 🚨 【极度重要警告】：Gap-Finding 盲区寻找机制

**严禁给总结、缝合现有文献的假设打高分！**

如果该假设只是将输入的顶刊文献内容杂��，必须判定为 REJECT。

**你的核心任务是审查该假设是否击中了现有文献的【集体盲区 (Collective Blindspots)】。**

只有利用跨界思维（如非欧几何引入生物网络、拓扑数据分析、热力学时序建模）填补了盲区，才能给予高分。

**三个关键问题**：
1. 他们在做什么？
2. 他们都没做什么？（寻找盲区！）
3. 为什么没人做？（技术障碍？认知盲区？）

---

## 评审假设

**假设名称**: {}

**前沿框架**: {}

**大挑战**: {}

**方法论创新**: {}

**双重价值**:
- 计算革命性: {}
- 生物学/临床突破: {}

{}

## Nature级数据库清单

{}

## 📏 【强制执行】绝对打分标准

**1-3分：常识性废话、增量研究、学术洗稿**
- 常识性推理
- 简单的增量改进（换个数据集跑老模型）
- 90%以上与现有文献重复

**4-6分：常规交叉，缺乏深度**
- A领域方法 + B领域数据，但没有深度融合
- 缺乏对盲区的识别

**7-8分：高质量的【跨界组合创新】**
- 成功将A领域的复杂算法降维应用解决B领域的顽疾
- 逻辑自洽，技术路线清晰
- **注意：一旦达到7-8分，必须判定为 ACCEPT / 放行，允许进入下游阶段！**

**9-10分：范式转移级（改写教科书）**
- 发现全新的生物学机制
- 发明全新的算法范式

## 🔒 【保底规则】Base Score Rubric

鉴于输入文献本身已是IF≥5的顶刊精华，该假设自带基础价值。

**只要满足以下条件，严禁打出低于7分的总评：**
- 逻辑自洽
- 提出一种新颖的跨学科验证方式
- 技术路线可行

## 评分维度 (每项1-10分)

1. **广度与深度的颠覆性**: 是否具备跨学科影响力，能否改写教科书或临床指南
2. **方法论的原创性**: 是否是底层算法结构的创新，而非微调或堆砌
3. **验证的可行性**: 利用全球公开算力和超级数据库能否完成初步概念验证
4. **数据科学红线**: 评估是否存在数据泄露、泛化能力缺���、样本量不足等问题
5. **统计验证严谨性**: 是否包含Power Analysis、FDR校正、Mediation分析等

## 请以JSON格式返回评审结果:

{{
    "scores": {{
        "transformative_impact": <1-10>,
        "methodological_originality": <1-10>,
        "poc_feasibility": <1-10>,
        "data_science_red_lines": <1-10>,
        "statistical_hardening": <1-10>
    }},
    "impact_analysis": {{
        "breadth": "跨学科影响力分析",
        "depth": "颠覆性分析",
        "textbook_impact": "教科书影响评估",
        "collective_bindspot": "现有文献的集体盲区是什么？该假设是否击中了盲区？"
    }},
    "originality_analysis": {{
        "core_innovation": "核心创新点",
        "comparison": "与现有方法的区别",
        "derivative_check": "是否为衍生工作",
        "is_cross_domain_pivot": "是否为跨界降维打击（如将物理学相变理论引入肿瘤转移）"
    }},
    "feasibility_analysis": {{
        "data_scale": "数据规模评估",
        "computational_needs": "算力需求评估",
        "recommended_databases": ["推荐的数据库名称"]
    }},
    "ds_red_line_analysis": {{
        "data_leakage_risk": "数据泄露风险评估",
        "generalization_strategy": "泛化策略",
        "sample_size_adequacy": "样本量充足性",
        "evaluation_metrics": "评估指标科学性"
    }},
    "verdict": {{
        "decision": "accepted/revise/rejected",
        "rationale": "详细理由"
    }},
    "constructive_pivot": "如果判定为REJECT或REVISE，必须提供一个【主编的降维打击建议】。格式：'建议放弃X方向，引入Y跨学科方向（如拓扑数据分析/热力学时序建模/因果推断框架）以解决Z核心问题'"
}}

请开始评审：
""".format(
    hypothesis.get('title', 'N/A'),
    hypothesis.get('paradigm_framework', 'N/A'),
    hypothesis.get('grand_challenge', 'N/A'),
    hypothesis.get('description', 'N/A'),
    hypothesis.get('expected_value', 'N/A'),
    hypothesis.get('novelty', 'N/A'),
    similar_works_section,
    db_list
) + ANTI_HALLUCINATION_PROTOCOL

        return prompt

    def _perform_literature_check(self, hypothesis: Dict, min_if: float = 10.0) -> Dict:
        """执行文献查重 - 动态查新探针（含反幻觉断路器）"""
        result = {'searched': False, 'similar_works': [], 'keywords_used': []}

        # ==================== 反幻觉断路器：检查搜索次数 ====================
        self._search_attempt_count += 1
        if self._search_attempt_count > self._max_search_attempts:
            print(f"\n🚨 [反幻觉断路器] 搜索次数已达上限 ({self._max_search_attempts} 次)")
            print("🚨 【检索终止】：已达到最大搜索次数。必须诚实声明未能检索到文献。")
            result['search_terminated'] = True
            result['termination_reason'] = 'MAX_SEARCH_ATTEMPTS_EXCEEDED'
            result['anti_hallucination_warning'] = """
🚨 【检索终止】：已达到最大搜索次数 (3次)。

你必须诚实地声明"未能检索到直接支持的文献"。
你可以基于现有的、已证实的上下文进行极其谨慎的逻辑推理，但必须明确标注这是【未证实的推测】，
或者直接建议放弃当前假设分支。

严禁捏造任何事实、文献或数据！
            """.strip()
            return result
        print(f"📊 [文献查重] 第 {self._search_attempt_count}/{self._max_search_attempts} 次搜索尝试...")
        # =======================================================================

        try:
            # 优先使用假设本体提供的 search_queries（LLM动态提取的精准检索词）
            search_queries = hypothesis.get('search_queries', [])

            if search_queries and isinstance(search_queries, list):
                # 使用假设本体提供的精准检索词
                result['keywords_used'] = search_queries[:3]
                query = ' OR '.join(search_queries[:3])  # 使用OR组合扩大检索范围
            else:
                # 兜底方案：从title提取核心名词
                keywords = self._extract_keywords_from_title(hypothesis)
                result['keywords_used'] = keywords
                if not keywords:
                    return result
                query = ' AND '.join(keywords[:3])

            searcher = self._get_pubmed_searcher()

            # ========== 动态质量准入：不限制结果数量 ==========
            # 使用相关性阈值而非固定数量，确保不会错过第11篇的神级论文
            try:
                papers = searcher.search_papers(
                    query,
                    max_results=None,  # 无限制，基于质量准入
                    min_if=min_if,
                    relevance_threshold=7.0  # 7.0/10 以上的论文保留
                )
            except Exception as search_error:
                # 处理 ZeroResultsError 或其他错误
                papers = []
                result['search_error'] = str(search_error)

            if papers:
                result['searched'] = True
                # 最多保留前10篇用于展示（但实际检索了更多）
                result['similar_works'] = [
                    {
                        'pmid': p.get('pmid'),
                        'title': p.get('title'),
                        'journal': p.get('journal'),
                        'date': p.get('publication_date'),
                        'abstract': p.get('abstract', '')[:300]
                    }
                    for p in papers[:5]
                ]
                result['total_found'] = len(papers)  # 记录实际找到的数量
            else:
                # 搜索成功但无结果
                result['searched'] = True
                result['no_results'] = True
                result['search_attempt'] = f"{self._search_attempt_count}/{self._max_search_attempts}"
        except Exception as e:
            result['error'] = str(e)
        return result

    def _extract_keywords_from_title(self, hypothesis: Dict) -> List[str]:
        """
        从假设中提取核心关键词 - 强化版兜底方案

        提取策略：
        1. 从 title 中提取专业术语
        2. 从 core_hypothesis 中提取生物医学核心词汇
        3. 如果仍失败，使用 title 的完整核心短语（最后的防线）

        【关键修复】严禁回退到"机器学习"等宽泛默认词！
        """
        import re
        title = hypothesis.get('title', '')
        core_hypothesis = hypothesis.get('core_hypothesis', '')
        description = hypothesis.get('description', '')

        # 合并所有文本进行提取
        full_text = f"{title} {core_hypothesis} {description}"

        # 提取看起来像专业术语的单词
        keywords = []

        # ========== 策略1: 从标题中���取大写开头的专业术语 ==========
        english_terms = re.findall(r'\b[A-Z][a-z]{2,}\b', title)
        keywords.extend([t for t in english_terms if t not in ['The', 'This', 'That', 'Based', 'Using', 'Novel', 'New', 'Study', 'Research']])

        # ========== 策略2: 生物医学核心词汇硬约束提取 ==========
        # 【硬约束】必须提取这些核心医学/生物学词汇，不能只保留"机器学习"
        biomedical_patterns = [
            # 疾病类
            r'(?:heart.?failure|cardiac.?failure|心力衰竭)',
            r'(?:Alzheimer|帕金森|Parkinson|dementia|痴呆)',
            r'(?:diabetes|糖尿病|hyperglycemia)',
            r'(?:cancer|tumor|肿瘤|癌症|carcinoma|melanoma|leukemia)',
            r'(?:COVID.?19|coronavirus|SARS.?CoV)',
            r'(?:cardiovascular|心血管|vascular|动脉)',
            r'(?:neurodegenerative|神经退行性|neuro|神经)',
            r'(?:inflammation|炎症|immune|免��|autoimmune)',
            r'(?:fibrosis|纤维化|cirrhosis|硬化)',
            r'(?:hypertension|高血压|atherosclerosis|动脉硬化)',
            # 生物学概念
            r'(?:metabolism|代谢|thermodynamic|热力学|entropy|熵)',
            r'(?:mitochondria|线粒体|organelle|细胞器)',
            r'(?:apoptosis|凋亡|necrosis|坏死|autophagy|自噬)',
            r'(?:stem.?cell|干细胞|progenitor|祖细胞)',
            r'(?:microbiome|微生物组|gut.?flora|肠道菌群)',
            r'(?:epigenetic|表观遗传|methylation|甲基化)',
            r'(?:protein.?interaction|蛋白质互作|pathway|通路)',
            # 技术方法
            r'(?:spatial.?transcriptom|空间转录组|single.?cell|单细胞)',
            r'(?:CRISPR|gene.?editing|基因编辑|sequencing|测序)',
            r'(?:graph.?neural.?network|GNN|图神经网络)',
            r'(?:causal|inference|counterfactual|因果|反事实)',
            r'(?:heterogeneity|异质性|endogeneity|内生性)',
            r'(?:transformer|attention|注意力|BERT)',
            r'(?:synthetic.?control|合成控制|regression|回归)',
        ]

        for pattern in biomedical_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            keywords.extend(matches)

        # ========== 策略3: 从 core_hypothesis 中提取关键词 ==========
        # 提取中文术语（2-6个汉字的连续词组）
        chinese_terms = re.findall(r'[\u4e00-\u9fa5]{2,6}', core_hypothesis)
        # 过滤常见停用词
        stopwords = {'的', '和', '与', '在', '是', '对', '为', '及', '其', '中', '等', '或', '一种', '研究', '方法', '分析', '基于', '通过', '进行', '可以', '能够', '由于', '因此'}
        chinese_terms = [t for t in chinese_terms if t not in stopwords and len(t) >= 2]
        keywords.extend(chinese_terms[:5])

        # ========== 策略4: 最后的防线 - 使用 title 的核心短语 ==========
        # 如果仍然没有提取到任何关键词，使用 title 的核心部分
        if not keywords:
            print(f"  [关键词提取回退] 使用原始标题作为检索词")
            # 清理标题，移除停用词前缀
            title_clean = title
            for prefix in ['基于', 'Using', 'A', 'An', 'The ']:
                if title_clean.startswith(prefix):
                    title_clean = title_clean[len(prefix):].strip()
            if title_clean:
                return [title_clean[:50]]  # 限制长度避免过长

        # 去重并限制数量
        unique_keywords = []
        seen = set()
        for kw in keywords:
            kw_lower = kw.lower().strip()
            if kw_lower and kw_lower not in seen and kw_lower not in {'and', 'or', 'not', 'with', 'for', 'from', 'the', 'a', 'an'}:
                seen.add(kw_lower)
                unique_keywords.append(kw.strip())

        # 确保返回至少一个关键词
        if not unique_keywords and title:
            unique_keywords = [title[:30]]

        return unique_keywords[:8]

    def _extract_text_from_response(self, content) -> str:
        """安全地从 Claude 响应中提取文本（正确处理 ThinkingBlock）"""
        text_parts = []
        for block in content:
            # 只处理 TextBlock，跳过 ThinkingBlock
            if hasattr(block, 'type') and block.type == 'text':
                text_parts.append(block.text)
            elif hasattr(block, 'text') and not hasattr(block, 'thinking'):
                text_parts.append(block.text)
            elif isinstance(block, str):
                text_parts.append(block)
        return "\n".join(text_parts)

    def _parse_nature_response(self, response_text: str) -> Dict:
        """解析Nature评审响应

        使用多层策略确保提取到正确的 dict 格式评审结果

        核心改进：使用智能JSON提取器，正确处理字符串内的大括号

        Args:
            response_text: LLM响应文本

        Returns:
            解析后的评审结果（必须是dict）

        Raises:
            ValueError: 解析失败时抛出异常
        """
        import json
        import re
        from src.utils.smart_json_extractor import SmartJSONExtractor

        if not response_text:
            raise ValueError("响应文本为空")

        print("[Nature评审解析] 响应长度: {} 字符".format(len(response_text)))
        print("[Nature评审解析] 响应预览: {}...".format(response_text[:300]))

        # 策略1: 找到所有 ```json 代码块，优先解析以 { 开头的
        block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        block_matches = re.findall(block_pattern, response_text)

        if block_matches:
            print("[Nature评审解析] 找到 {} 个代码块".format(len(block_matches)))
            for i, match in enumerate(block_matches):
                match = match.strip()
                print("[Nature评审解析] 代码块 {} 开头: {}".format(i, match[:30] if len(match) > 30 else match))

                if match.startswith('{'):
                    # 使用 SmartJSONExtractor 进行智能提取
                    result = SmartJSONExtractor.extract_first_dict(match)
                    if result:
                        print("[Nature评审解析] 成功从代码块 {} 解析dict".format(i))
                        return result
                    else:
                        print("[Nature评审解析] 代码块 {} SmartJSON提取失败，尝试传统方式".format(i))
                        # 降级：传统解析
                        cleaned = re.sub(r'\\(?![nrtbf\"\\/])', '', match)
                        try:
                            result = json.loads(cleaned)
                            if isinstance(result, dict):
                                print("[Nature评审解析] 传统方式从代码块 {} 解析成功".format(i))
                                return result
                        except json.JSONDecodeError as e:
                            print("[Nature评审解析] 代码块 {} 解析失败: {}".format(i, str(e)[:50]))
                            continue

        # ���略2: 使用 SmartJSONExtractor 直接从文本中提取
        print("[Nature评审解析] 策略2: 使用SmartJSONExtractor提取")
        result = SmartJSONExtractor.extract_first_dict(response_text)
        if result:
            print("[Nature评审解析] SmartJSONExtractor成功提取dict")
            return result

        # 策略3: SafeExtractor 作为后备
        try:
            result = self.extractor.safe_extract_json(response_text)
            if isinstance(result, dict):
                return result
            elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
                return result[0]
        except Exception as e:
            print("[Nature评审解析] SafeExtractor失败: {}".format(e))

        raise ValueError("无法提取有效的dict JSON。响应预览: {}".format(response_text[:500]))

    def _determine_nature_decision(self, validation: Dict) -> str:
        """确定Nature级别决议

        保底规则：只要达到7-8分（高质量跨界创新），必须放行
        """
        scores = validation.get('scores', {})
        impact = scores.get('transformative_impact', 0)
        originality = scores.get('methodological_originality', 0)
        feasibility = scores.get('poc_feasibility', 0)

        avg_score = (impact + originality + feasibility) / 3

        # 保底放行规则：7-8分必须接受
        if avg_score >= 7.0:
            return "accepted"
        elif avg_score >= 6:
            return "revise"
        else:
            return "rejected"

    def _get_score_level(self, score: int) -> str:
        """获取得分等级"""
        if score >= 9:
            return 'Nature级别'
        elif score >= 7:
            return '优秀'
        elif score >= 5:
            return '中等'
        elif score >= 3:
            return '较差'
        else:
            return '拒稿'

    def _generate_nature_decision(self, hypothesis_data: Dict, validation_result: Dict,
                                output_dir: str) -> str:
        """生成Nature决议书"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = "Nature_Decision_{}.md".format(timestamp)
        filepath = os.path.join(output_dir, filename)
        cn_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

        verdict = validation_result.get('verdict', {}).get('decision', 'REVISE')
        verdict_map = {'accepted': '🟢 ACCEPT', 'revise': '🟡 REVISE', 'rejected': '🔴 REJECT'}
        verdict_emoji = verdict_map.get(verdict.lower(), '🟡 REVISE')

        scores = validation_result.get('scores', {})
        avg_score = (sum(scores.values()) / len(scores)) if scores else 0
        avg_display = '{:.1f}'.format(avg_score)

        md_content = """# Nature评审决议书

**生成时间**: {}
**智能体**: Nature高级编辑
**决议**: {} **{}**

---

## 综合评分

| 评估维度 | 得分 | 等级 |
|---------|-----|------|
| 广度与深度的颠覆性 | {}/10 | {} |
| 方法论的原创性 | {}/10 | {} |
| 验证的可行性 | {}/10 | {} |
| **数据科学红线** | {}/10 | {} |
| **平均分** | {}/10 | - |


---

## 假设信息

**假设名称**: {}

**前沿框架**: {}

**大挑战**: {}

**方法论创新**: {}...

**双重价值**:
- 计算革命性: {}...
- 生物学/临床突破: {}...

---

## 详细评审

### 1. 广度与深度的颠覆性

""".format(cn_time, verdict_emoji, verdict,
           scores.get('transformative_impact', 'N/A'),
           self._get_score_level(scores.get('transformative_impact', 0)),
           scores.get('methodological_originality', 'N/A'),
           self._get_score_level(scores.get('methodological_originality', 0)),
           scores.get('poc_feasibility', 'N/A'),
           self._get_score_level(scores.get('poc_feasibility', 0)),
           scores.get('data_science_red_lines', 'N/A'),
           self._get_score_level(scores.get('data_science_red_lines', 0)),
           avg_display,
           hypothesis_data.get('title', 'N/A'),
           hypothesis_data.get('paradigm_framework', 'N/A'),
           hypothesis_data.get('grand_challenge', 'N/A'),
           hypothesis_data.get('description', 'N/A')[:500],
           hypothesis_data.get('expected_value', 'N/A')[:300],
           hypothesis_data.get('novelty', 'N/A')[:300])

        impact_analysis = validation_result.get('impact_analysis', {})
        md_content += "**跨学科影响力**: {}\n\n".format(impact_analysis.get('breadth', '待评估'))
        md_content += "**颠覆性**: {}\n\n".format(impact_analysis.get('depth', '待评估'))
        md_content += "**教科书影响**: {}\n\n".format(impact_analysis.get('textbook_impact', '待评估'))

        md_content += """### 2. 方法论的原创性

"""

        originality = validation_result.get('originality_analysis', {})
        md_content += "**核心创新**: {}\n\n".format(originality.get('core_innovation', '待评估'))
        md_content += "**与现有方法的区别**: {}\n\n".format(originality.get('comparison', '待评估'))
        md_content += "**衍生工作检查**: {}\n\n".format(originality.get('derivative_check', '待评估'))

        md_content += """### 3. 验证的可行性

"""

        feasibility = validation_result.get('feasibility_analysis', {})
        md_content += "**数据规模**: {}\n\n".format(feasibility.get('data_scale', '待评估'))
        md_content += "**算力需求**: {}\n\n".format(feasibility.get('computational_needs', '待评估'))
        md_content += "**推荐数据库**:\n"
        for db in feasibility.get('recommended_databases', []):
            md_content += "- {}\n".format(db)

        md_content += "\n### 4. 数据科学红线评估\n\n"

        ds_analysis = validation_result.get('ds_red_line_analysis', {})
        md_content += "**数据泄露风险**: {}\n\n".format(ds_analysis.get('data_leakage_risk', '待评估'))
        md_content += "**泛化策略**: {}\n\n".format(ds_analysis.get('generalization_strategy', '待评'))
        md_content += "**样本量充足性**: {}\n\n".format(ds_analysis.get('sample_size_adequacy', '待评估'))
        md_content += "**评估指标科学性**: {}\n\n".format(ds_analysis.get('evaluation_metrics', '待评估'))

        md_content += """
---

## 编辑决议

### 决策: {}

**理由**: {}
""".format(verdict, validation_result.get('verdict', {}).get('rationale', '待评估'))

        # 添加主编的降维打击建议
        constructive_pivot = validation_result.get('constructive_pivot', '')
        if verdict in ['revise', 'rejected'] and constructive_pivot:
            md_content += """

---

## 🎯 [主编的降维打击建议]

{}

---

*此建议由Nature主编智能体基于跨学科前沿方向生成，旨在引导假设向范式转移级创新演进*
""".format(constructive_pivot)
        elif verdict == 'revise':
            md_content += "\n**修改条件**: {}\n".format(validation_result.get('verdict', {}).get('conditions', '待补充'))

        # 添加集体盲区分析
        if impact_analysis.get('collective_bindspot'):
            md_content += """

---

## 🔍 集体盲区分析

**现有文献的盲区**: {}

**该假设是否击中盲区**: {}
""".format(impact_analysis.get('collective_bindspot', '待分析'),
           '是' if originality.get('is_cross_domain_pivot') else '否')

        md_content += """
---

## Nature级别标准

### 接受 (ACCEPT) 标准
- 跨多个领域的范式转移
- 全新的算法范式
- 百万级数据支持
- **无数据科学红线问题**

### 修改 (REVISE) 条件
- 对某一子领域有显著影响
- 显著的方法论创新
- 数据规模基本可行
- **数据科学风险可说明**

### 拒稿 (REJECT) 理由
- 增量式改进(在老数据上提高精度)
- 研究范围过窄(单一疾病/组织)
- 衍生性工作(微调/应用现有模型)
- 比较研究(方法性能对比)
- **存在数据科学红线问题**(数据泄露、严重过拟合、样本量不足)

---

*本决议书由Nature高级编辑智能体生成*
*生成时间: {}*
""".format(cn_time)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)

        return filepath

    def _generate_rejection_decision(self, hypothesis_data: Dict, reject_check: Dict,
                                   output_dir: str) -> str:
        """生成拒稿决议书"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = "Nature_Rejection_{}.md".format(timestamp)
        filepath = os.path.join(output_dir, filename)
        cn_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

        md_content = """# Nature拒稿决议书

**生成时间**: {}
**智能体**: Nature高级编辑
**决议**: 🔴 **REJECTED**

---

## 拒稿原因

{}

---

## 假设信息

**假设名称**: {}

**前沿框架**: {}

**大挑战**: {}

**方法论创新**: {}

---

## Nature标准说明

此假设不符合《Nature》杂志的发表标准。请确保您的假设：
1. 具备跨学科的范式转移潜力
2. 包含原创性的方法论贡献
3. 可使用大规模公开数据进行验证
4. 符合数据科学最佳实践

---

*本决议书由Nature高级编辑智能体生成*
*生成时间: {}*
""".format(
    cn_time,
    reject_check.get('reason', '不符合Nature标准'),
    hypothesis_data.get('title', 'N/A'),
    hypothesis_data.get('paradigm_framework', 'N/A'),
    hypothesis_data.get('grand_challenge', 'N/A'),
    hypothesis_data.get('description', 'N/A')[:500],
    cn_time
)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)

        return filepath

    def batch_validate(self, hypothesis_ids: List[int]) -> Dict:
        """批量验证"""
        results = []
        with self.db_manager.get_session() as session:
            for hyp_id in hypothesis_ids:
                hypothesis = session.query(Hypothesis).filter_by(id=hyp_id).first()
                if hypothesis:
                    source_papers = [
                        {
                            'pmid': paper.pmid,
                            'title': paper.title,
                            'journal': paper.journal,
                            'publication_date': paper.publication_date,
                            'abstract': paper.abstract
                        }
                        for paper in hypothesis.papers
                    ]
                    technical_analysis = {}
                    if hypothesis.technical_analysis:
                        try:
                            technical_analysis = json.loads(hypothesis.technical_analysis)
                        except:
                            pass
                    result = self.execute({
                        'hypothesis_id': hyp_id,
                        'hypothesis_data': {
                            'title': hypothesis.title,
                            'description': hypothesis.description,
                            'rationale': hypothesis.rationale,
                            'novelty': hypothesis.novelty,
                            'expected_value': hypothesis.expected_value or '',
                            'validation_plan': '',
                            'required_techniques': technical_analysis.get('required_techniques', []),
                            'paradigm_framework': technical_analysis.get('paradigm_framework', ''),
                            'grand_challenge': technical_analysis.get('grand_challenge', '')
                        },
                        'source_papers': source_papers,
                        'enable_literature_check': True
                    })
                    results.append(result)
        return {
            'success': True,
            'validated_count': len(results),
            'results': results
        }

    def __del__(self):
        pass


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    # 测试Nature级别评审
    test_hypothesis = {
        'title': 'Universal Gene Expression Transformer: 跨越所有细胞类型和组织的基因表达预测模型',
        'description': '提出自监督跨模态对比学习框架，将基因组、表观基因组、转录组映射到统一空间，实现跨组织的零样本迁移',
        'rationale': '当前模型都是组织特异性的，无法泛化。首个真正通用的生物学表示学习框架',
        'novelty': '首个跨细胞类型和组织的通用基因表达预测模型',
        'expected_value': '发现控制基因表达的通用法则，预测非编码变异的功能影响',
        'validation_plan': '使用GTEx(50,000+样本，54种组织)和Human Cell Atlas数据进行验证',
        'required_techniques': ['Python', 'PyTorch', 'Transformer', 'JAX'],
        'paradigm_framework': '生物学基础大模型',
        'grand_challenge': '通用生物学法则'
    }

    agent = ValidationAgent()
    result = agent.execute({
        'hypothesis_id': None,
        'hypothesis_data': test_hypothesis,
        'source_papers': [],
        'enable_literature_check': False
    })

    if result['success']:
        validation = result['validation']
        print("=" * 60)
        print("Nature级别评审结果")
        print("=" * 60)
        print("决议: {}".format(validation['final_decision']))
        print()
        print("评分:")
        for key, value in validation.get('scores', {}).items():
            print("  {}: {}/10".format(key, value))
        print("\n决议书: {}".format(validation.get('report_path', 'N/A')))
