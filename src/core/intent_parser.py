# -*- coding: utf-8 -*-
"""
V8.0 意图解析器 (Intent Parser)

核心功能：
1. 使用 LLM 进行语义理解��解析用户自然语言输入
2. 识别意图类型（搜索论文、生成假设、查看历史等）
3. 检测多个研究领域（支持交叉学科）
4. 提取参数（query、max_results、date_range、min_if、sources）
5. 推断技术方法和应用场景

作者: V8.0 发版工程师
日期: 2026-04-24
"""

import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


# ==================== 枚举定义 ====================

class UserIntent(Enum):
    """用户意图类型"""
    SEARCH_PAPERS = "search_papers"       # 搜索论文
    GENERATE_HYPOTHESIS = "generate"      # 生成假设
    VIEW_HISTORY = "view_history"        # 查看历史会话
    VIEW_SAVED = "view_saved"            # 查看已保存的假设
    MODIFY_CONFIG = "modify_config"      # 修改配置
    EXPORT_REPORT = "export"             # 导出报告
    REFINE_SEARCH = "refine_search"      # 扩大/缩小搜索（需要上下文）
    SELECT_HYPOTHESIS = "select"         # 选择假设（需要上下文）
    AUTONOMOUS_MODE = "autonomous"       # 自主循环模式
    EXIT = "exit"                        # 退出
    UNKNOWN = "unknown"                  # 未识别


class ResearchDomain(Enum):
    """研究领域枚举（与 rag_router.py 的 DOMAIN_SOURCE_MAPPING 兼容）"""
    # 医学/生命科学
    MEDICINE = "medicine"
    BIOLOGY = "biology"
    BIOMEDICINE = "biomedicine"
    NEUROSCIENCE = "neuroscience"
    CARDIOLOGY = "cardiology"
    ONCOLOGY = "oncology"
    CANCER = "cancer"
    GENOMICS = "genomics"
    PROTEOMICS = "proteomics"
    IMMUNOLOGY = "immunology"
    PHARMACOLOGY = "pharmacology"
    BIOCHEMISTRY = "biochemistry"
    MOLECULAR_BIOLOGY = "molecular_biology"
    CELL_BIOLOGY = "cell_biology"
    PATHOLOGY = "pathology"
    PHYSIOLOGY = "physiology"
    MICROBIOLOGY = "microbiology"
    VIROLOGY = "virology"
    EPIDEMIOLOGY = "epidemiology"
    PUBLIC_HEALTH = "public_health"
    CLINICAL_MEDICINE = "clinical_medicine"
    RADIOLOGY = "radiology"
    MEDICAL_IMAGING = "medical_imaging"
    DIAGNOSTICS = "diagnostics"
    THERAPEUTICS = "therapeutics"
    DRUG_DISCOVERY = "drug_discovery"
    PRECISION_MEDICINE = "precision_medicine"
    TRANSLATIONAL_MEDICINE = "translational_medicine"
    GENE_THERAPY = "gene_therapy"
    STEM_CELL = "stem_cell"
    ALZHEIMER = "alzheimer"
    CARDIOVASCULAR = "cardiovascular"
    DIABETES = "diabetes"
    SINGLE_CELL = "single_cell"
    SEQUENCING = "sequencing"
    CRISPR = "crispr"

    # 计算机/AI
    COMPUTER_SCIENCE = "computer_science"
    ARTIFICIAL_INTELLIGENCE = "artificial_intelligence"
    AI = "ai"
    MACHINE_LEARNING = "machine_learning"
    DEEP_LEARNING = "deep_learning"
    NEURAL_NETWORK = "neural_network"
    NLP = "nlp"
    NATURAL_LANGUAGE_PROCESSING = "natural_language_processing"
    COMPUTER_VISION = "computer_vision"
    CV = "cv"
    ROBOTICS = "robotics"
    REINFORCEMENT_LEARNING = "reinforcement_learning"
    DATA_SCIENCE = "data_science"
    DATA_MINING = "data_mining"
    BIG_DATA = "big_data"
    ALGORITHM = "algorithm"
    OPTIMIZATION = "optimization"

    # 交叉领域
    BIOINFORMATICS = "bioinformatics"
    COMPUTATIONAL_BIOLOGY = "computational_biology"
    AI_MEDICINE = "ai_medicine"  # AI + 医学交叉
    COMPUTATIONAL_BIOMEDICINE = "computational_biomedicine"
    PHARMACOGENOMICS = "pharmacogenomics"  # 药物基因组学

    # 物理/数学
    PHYSICS = "physics"
    MATHEMATICS = "mathematics"
    STATISTICS = "statistics"
    PROBABILITY = "probability"

    # 其他
    GENERAL = "general"
    UNKNOWN = "unknown"


class DataSource(Enum):
    """数据源类型"""
    PUBMED = "pubmed"
    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CROSSREF = "crossref"
    GOOGLE_SCHOLAR = "google_scholar"


# ==================== 数据结构定义 ====================

@dataclass
class DomainDetection:
    """领域检测结果"""
    domain: ResearchDomain
    confidence: float
    reasoning: str


@dataclass
class SearchParameters:
    """搜索参数"""
    query: str  # 搜索查询词
    max_results: Optional[int] = None  # 最大结果数
    date_range: Optional[Tuple[int, int]] = None  # (start_year, end_year)
    min_if: Optional[float] = None  # 最低影响因子
    sources: Optional[List[str]] = None  # 数据源列表
    enable_filter: bool = False  # 是否启用过滤
    fetch_full_text: bool = True  # 是否获取全文


@dataclass
class ParsedIntent:
    """解析后的意图"""
    intent: UserIntent
    original_input: str
    detected_domains: List[DomainDetection]
    inferred_techniques: List[str]  # 推断的技术方法
    inferred_applications: List[str]  # 推断的应用场景
    parameters: Optional[SearchParameters] = None
    config_changes: Optional[Dict[str, Any]] = None  # 配置修改（modify_config 意图）
    needs_context: bool = False  # 是否需要上下文
    confidence: float = 0.0
    reasoning: str = ""
    raw_response: Optional[Dict] = None  # LLM 原始响应

    def to_dict(self) -> Dict:
        """转换为字典"""
        d = asdict(self)
        d['intent'] = self.intent.value
        d['detected_domains'] = [
            {'domain': dd.domain.value, 'confidence': dd.confidence, 'reasoning': dd.reasoning}
            for dd in self.detected_domains
        ]
        return d


# ==================== IntentParser 核心类 ====================

class IntentParser:
    """
    V8.0 意图解析器

    使用 LLM 进行语义理解，解析用户自然语言输入
    """

    # LLM Prompt 模板
    INTENT_PARSER_PROMPT = """你是用户意图解析器。请分析用户输入并提取结构化信息。

## 用户输入
{user_input}

## 上下文（如有）
{context}

## 任务
1. 识别意图类型
2. 识别涉及的研究领域（可能多个，按置信度排序）
3. 推断技术方法
4. 提取参数

## 意图类型说明
- **search_papers**: 搜索论文（如"找论文"、"搜索"、"搜索关于X的文献"）
- **generate**: 生成假设（如"生成假设"、"基于文献生成想法"）
- **view_history**: 查看历史会话（如"看看历史"、"查看之前的会话"）
- **view_saved**: 查看已保存的假设（如"看看保存的假设"、"查看假设"）
- **modify_config**: 修改配置（如"修改配置"、"改参数"）
- **export**: 导出报告（如"导出报告"、"保存报告"）
- **refine_search**: 扩大/缩小搜索（如"扩大到100篇"、"缩小范围"、"再多找点"）
- **select**: 选择假设（如"选第一个"、"选假设2"）
- **autonomous**: 自主循环模式（如"自主模式"、"自动迭代"）
- **exit**: 退出（如"退出"、"结束"、"再见"）
- **unknown**: 无法识别

## 领域映射提示

### 医学/生命科学
- "看片子"、"影像"、"CT"、"MRI"、"X光"、"放射" → medical_imaging, radiology
- "基因"、"基因组"、"测序"、"GWAS"、"变异"、"DNA"、"RNA" → genomics, sequencing
- "癌症"、"肿瘤"、"oncology"、"carcinoma" → oncology, cancer
- "单细胞"、"转录组"、"细胞类型" → single_cell, cell_biology
- "CRISPR"、"基因编辑"、"敲除" → crispr, gene_therapy
- "药物发现"、"新药"、"化合物" → drug_discovery, pharmacology
- "预测反应"、"个体化治疗"、"精准" → precision_medicine, pharmacogenomics
- "免疫"、"T细胞"、"B细胞"、"抗体"、"疫苗" → immunology
- "神经"、"大脑"、"认知"、"阿尔茨海默"、"痴呆" → neuroscience, alzheimer
- "心脏"、"心血管"、"血管" → cardiology, cardiovascular
- "糖尿病"、"代谢" → diabetes, metabolism

### 计算机/AI
- "AI"、"人工智能"、"机器学习"、"ML"、"深度学习"、"DL" → machine_learning, deep_learning, ai
- "神经网络"、"网络"、"模型" → neural_network, machine_learning
- "图像"、"视觉"、"CV"、"识别"、"检测" → computer_vision, cv
- "NLP"、"自然语言"、"文本"、"语言模型" → nlp, natural_language_processing
- "预测"、"分类"、"聚类"、"回归"、"算法" → machine_learning, algorithm
- "数据科学"、"大数据"、"挖掘" → data_science, data_mining, big_data
- "强化学习"、"RL"、"智能体" → reinforcement_learning, ai

### 交叉领域
- "生物信息学"、"计算生物学"、"序列分析" → bioinformatics, computational_biology
- "AI医学"、"智能医疗"、"AI辅助诊断" → ai_medicine, medical_imaging, machine_learning
- "计算生物医学"、"医学AI" → computational_biomedicine, ai_medicine
- "药物基因组学"、"基因组药物" → pharmacogenomics, genomics

### 物理/数学
- "物理"、"力学"、"量子" → physics
- "数学"、"统计"、"概率" → mathematics, statistics, probability

## 参数提取提示
- 数量："50篇"、"100 papers" → max_results
- 时间："近3年"、"最近两年"、"2020-2023"、"2022年以后" → date_range
- 影响因子："高影响因子"、"IF>10"、"影响因子5以上" → min_if
- 数据源："PubMed"、"ArXiv"、"只在ArXiv上"、"医学文献" → sources
- 关键词：提取核心研究主题 → query

## 输出格式（JSON）
{{
  "intent": "search_papers",
  "detected_domains": [
    {{"domain": "medical_imaging", "confidence": 0.9, "reasoning": "用户提到'看片子'"}},
    {{"domain": "computer_vision", "confidence": 0.85, "reasoning": "用户提到'AI'暗示图像分析"}}
  ],
  "inferred_techniques": ["深度学习", "图像分割", "卷积神经网络"],
  "inferred_applications": ["放射科辅助诊断", "病灶检测"],
  "parameters": {{
    "query": "AI 医学影像 辅助诊断",
    "max_results": 50,
    "date_range": [2021, 2024],
    "min_if": null,
    "sources": ["pubmed", "arxiv"]
  }},
  "needs_context": false,
  "confidence": 0.85,
  "reasoning": "用户想用AI辅助医生解读医学影像，涉及医学影像和计算机视觉交叉领域"
}}

## 重要说明
1. 领域检测可以返回多个，交叉学科场景下会包含多个领域
2. confidence 范围 0-1，表示整体置信度
3. needs_context 为 true 时表示需要结合上下文（如"把刚才的搜索扩大"）
4. date_range 格式为 [start_year, end_year]，只写年份如"近3年"需要计算
5. 如果用户没有明确指定参数，对应字段设为 null
6. query 应该提取最核心的搜索关键词，去掉冗余词汇
"""

    def __init__(self, llm_client_func=None):
        """
        初始化意图解析器

        Args:
            llm_client_func: LLM 调用函数（兼容 call_llm 接口）
        """
        self.llm_client_func = llm_client_func or self._default_llm_call
        self._domain_mapping = self._build_domain_mapping()

    def parse(
        self,
        user_input: str,
        context: Optional[Dict] = None
    ) -> ParsedIntent:
        """
        解析用户输入

        Args:
            user_input: 用户原始输入
            context: 上下文信息（包含 last_intent, last_query, last_domains 等）

        Returns:
            ParsedIntent: 解析后的意图
        """
        if not user_input or len(user_input.strip()) < 2:
            return self._build_unknown_intent(user_input, "输入过短")

        # 构建提示词
        context_str = self._format_context(context) if context else "无"
        prompt = self.INTENT_PARSER_PROMPT.format(
            user_input=user_input,
            context=context_str
        )

        # 调用 LLM
        try:
            response = self.llm_client_func(
                prompt=prompt,
                response_format="json"
            )

            if not response.get('success'):
                logger.warning(f"[IntentParser] LLM 调用失败: {response.get('error')}")
                return self._fallback_parse(user_input, context)

            content = response.get('content')
            if isinstance(content, str):
                content = json.loads(content)

            return self._parse_llm_response(user_input, content)

        except Exception as e:
            logger.error(f"[IntentParser] 解析异常: {e}")
            return self._fallback_parse(user_input, context)

    def _format_context(self, context: Dict) -> str:
        """格式化上下文"""
        parts = []
        if context.get('last_query'):
            parts.append(f"上一次查询: {context['last_query']}")
        if context.get('last_domains'):
            domains = [d.value if isinstance(d, ResearchDomain) else d for d in context['last_domains']]
            parts.append(f"上一次检测的领域: {', '.join(domains)}")
        if context.get('last_intent'):
            intent = context['last_intent'].value if isinstance(context['last_intent'], UserIntent) else context['last_intent']
            parts.append(f"上一次意图: {intent}")
        if context.get('last_results_count'):
            parts.append(f"上一次结果数量: {context['last_results_count']}")
        return '\n'.join(parts) if parts else "无"

    def _parse_llm_response(self, original_input: str, response: Dict) -> ParsedIntent:
        """解析 LLM 响应"""
        try:
            # 解析意图
            intent_str = response.get('intent', 'unknown')
            intent = UserIntent(intent_str) if intent_str in [e.value for e in UserIntent] else UserIntent.UNKNOWN

            # 解析领域
            detected_domains = []
            for domain_data in response.get('detected_domains', []):
                domain_str = domain_data.get('domain', 'unknown')
                domain = ResearchDomain(domain_str) if domain_str in [e.value for e in ResearchDomain] else ResearchDomain.UNKNOWN
                detected_domains.append(DomainDetection(
                    domain=domain,
                    confidence=float(domain_data.get('confidence', 0.5)),
                    reasoning=domain_data.get('reasoning', '')
                ))

            # 解析参数
            parameters = None
            if response.get('parameters'):
                params = response['parameters']
                parameters = SearchParameters(
                    query=params.get('query', original_input),
                    max_results=params.get('max_results'),
                    date_range=tuple(params['date_range']) if params.get('date_range') else None,
                    min_if=params.get('min_if'),
                    sources=params.get('sources'),
                    enable_filter=params.get('enable_filter', False),
                    fetch_full_text=params.get('fetch_full_text', True)
                )

            return ParsedIntent(
                intent=intent,
                original_input=original_input,
                detected_domains=detected_domains,
                inferred_techniques=response.get('inferred_techniques', []),
                inferred_applications=response.get('inferred_applications', []),
                parameters=parameters,
                needs_context=response.get('needs_context', False),
                confidence=float(response.get('confidence', 0.5)),
                reasoning=response.get('reasoning', ''),
                raw_response=response
            )

        except Exception as e:
            logger.error(f"[IntentParser] 解析 LLM 响应失败: {e}")
            return self._build_unknown_intent(original_input, str(e))

    def _fallback_parse(self, user_input: str, context: Optional[Dict]) -> ParsedIntent:
        """
        降级解析（基于规则）

        当 LLM 不可用时使用
        """
        input_lower = user_input.lower()

        # 检测意图
        intent = UserIntent.UNKNOWN

        # 退出意图
        if any(w in input_lower for w in ['退出', '结束', '再见', 'exit', 'quit', 'bye']):
            intent = UserIntent.EXIT

        # 搜索论文
        elif any(w in input_lower for w in ['搜索', '找', 'search', 'find', '论文', 'paper', '文献', 'literature']):
            intent = UserIntent.SEARCH_PAPERS

        # 生成假设
        elif any(w in input_lower for w in ['生成', '假设', 'generate', 'hypothesis', '想法', 'idea']):
            intent = UserIntent.GENERATE_HYPOTHESIS

        # 查看历史
        elif any(w in input_lower for w in ['历史', '会话', 'history', 'session', '之前的']):
            intent = UserIntent.VIEW_HISTORY

        # 查看保存
        elif any(w in input_lower for w in ['保存', '假设', 'saved', 'hypothesis']):
            intent = UserIntent.VIEW_SAVED

        # 修改配置
        elif any(w in input_lower for w in ['配置', '参数', '设置', 'config', 'setting']):
            intent = UserIntent.MODIFY_CONFIG

        # 导出
        elif any(w in input_lower for w in ['导出', 'export', '报告', 'report']):
            intent = UserIntent.EXPORT_REPORT

        # 扩大/缩小搜索（需要上下文）
        elif any(w in input_lower for w in ['扩大', '缩小', '更多', '少点', 'refine', 'expand', '刚才']):
            intent = UserIntent.REFINE_SEARCH

        # 选择假设
        elif any(w in input_lower for w in ['选', 'select', '第一个', '第二个', '1号', '2号']):
            intent = UserIntent.SELECT_HYPOTHESIS

        # 自主模式
        elif any(w in input_lower for w in ['自主', '自动', '迭代', 'autonomous', 'auto']):
            intent = UserIntent.AUTONOMOUS_MODE

        # 基于规则的领域检测
        detected_domains = self._rule_based_domain_detection(user_input)

        # 基于规则的参数提取
        parameters = self._rule_based_parameter_extraction(user_input)

        needs_context = intent in [UserIntent.REFINE_SEARCH, UserIntent.SELECT_HYPOTHESIS]

        return ParsedIntent(
            intent=intent,
            original_input=user_input,
            detected_domains=detected_domains,
            inferred_techniques=[],
            inferred_applications=[],
            parameters=parameters,
            needs_context=needs_context,
            confidence=0.6,  # 降级方案置信度较低
            reasoning="基于规则的降级解析"
        )

    def _rule_based_domain_detection(self, user_input: str) -> List[DomainDetection]:
        """基于规则的领域检测"""
        input_lower = user_input.lower()
        detected = []

        # 领域关键词映射
        domain_keywords = {
            ResearchDomain.MEDICAL_IMAGING: ['影像', '片子', 'ct', 'mri', 'x光', '放射', '超声', 'imaging'],
            ResearchDomain.GENOMICS: ['基因', '基因组', 'genomics', 'dna', 'rna', '测序', 'sequencing', 'gwas'],
            ResearchDomain.ONCOLOGY: ['癌症', '肿瘤', 'oncology', 'cancer', 'carcinoma', 'tumor'],
            ResearchDomain.MACHINE_LEARNING: ['机器学习', 'machine learning', 'ml', '深度学习', 'deep learning'],
            ResearchDomain.DEEP_LEARNING: ['深度学习', 'deep learning', '神经网络', 'neural network'],
            ResearchDomain.COMPUTER_VISION: ['计算机视觉', 'computer vision', 'cv', '图像识别', '视觉'],
            ResearchDomain.NLP: ['nlp', '自然语言', '文本', '语言模型'],
            ResearchDomain.BIOINFORMATICS: ['生物信息', 'bioinformatics', '计算生物', 'computational biology'],
            ResearchDomain.SINGLE_CELL: ['单细胞', 'single cell'],
            ResearchDomain.CRISPR: ['crispr', '基因编辑'],
            ResearchDomain.PHARMACOGENOMICS: ['药物基因组', '基因组药物', '个体化', '精准医疗'],
            ResearchDomain.DRUG_DISCOVERY: ['药物发现', '新药', '化合物'],
            ResearchDomain.IMMUNOLOGY: ['免疫', '抗体', 't细胞', 'b细胞', '疫苗'],
            ResearchDomain.NEUROSCIENCE: ['神经', '大脑', '认知', '神经科学'],
            ResearchDomain.CARDIOLOGY: ['心脏', '心血管', 'cardio'],
        }

        for domain, keywords in domain_keywords.items():
            score = sum(1 for kw in keywords if kw in input_lower)
            if score > 0:
                confidence = min(0.9, 0.5 + score * 0.1)
                detected.append(DomainDetection(
                    domain=domain,
                    confidence=confidence,
                    reasoning=f"匹配关键词: {', '.join([kw for kw in keywords if kw in input_lower])}"
                ))

        # 如果没有检测到任何领域，返回通用领域
        if not detected:
            detected.append(DomainDetection(
                domain=ResearchDomain.GENERAL,
                confidence=0.5,
                reasoning="未检测到特定领域"
            ))

        return detected

    def _rule_based_parameter_extraction(self, user_input: str) -> SearchParameters:
        """基于规则的参数提取"""
        import re

        query = user_input
        max_results = None
        date_range = None
        min_if = None
        sources = None

        input_lower = user_input.lower()

        # 提取数量
        number_match = re.search(r'(\d+)\s*(篇|个|papers?|articles?)', user_input)
        if number_match:
            max_results = int(number_match.group(1))

        # 提取时间范围
        current_year = datetime.now().year
        if '近3年' in user_input or '最近3年' in user_input or 'recent 3 years' in input_lower:
            date_range = (current_year - 3, current_year)
        elif '近5年' in user_input or '最近5年' in user_input:
            date_range = (current_year - 5, current_year)
        elif '近2年' in user_input or '最近2年' in user_input:
            date_range = (current_year - 2, current_year)
        elif '近1年' in user_input or '最近1年' in user_input:
            date_range = (current_year - 1, current_year)
        else:
            # 匹配具体年份范围
            year_match = re.search(r'(\d{4})\s*[-到至]\s*(\d{4})', user_input)
            if year_match:
                date_range = (int(year_match.group(1)), int(year_match.group(2)))
            else:
                # 匹配"XXXX年以后"
                year_match = re.search(r'(\d{4})\s*年(以后|之后|after)', user_input)
                if year_match:
                    date_range = (int(year_match.group(1)), current_year)

        # 提取影响因子
        if_match = re.search(r'if\s*[>大于]\s*(\d+\.?\d*)', input_lower)
        if if_match:
            min_if = float(if_match.group(1))
        elif '高影响因子' in user_input:
            min_if = 5.0

        # 提取数据源
        if 'arxiv' in input_lower and 'pubmed' not in input_lower:
            sources = ['arxiv']
        elif 'pubmed' in input_lower and 'arxiv' not in input_lower:
            sources = ['pubmed']
        elif '医学' in user_input or '生物' in user_input:
            sources = ['pubmed']
        elif any(w in user_input for w in ['计算机', 'AI', '人工智能', '算法', '机器学习']):
            sources = ['arxiv', 'pubmed']

        # 清理 query（移除已解析的参数词汇）
        query = re.sub(r'\d+\s*(篇|个|papers?|articles?)', '', query)
        query = re.sub(r'(近|最近)\d+年', '', query)
        query = re.sub(r'\d{4}\s*[-到至]\s*\d{4}', '', query)
        query = query.strip()

        return SearchParameters(
            query=query,
            max_results=max_results,
            date_range=date_range,
            min_if=min_if,
            sources=sources
        )

    def _build_unknown_intent(self, user_input: str, reason: str) -> ParsedIntent:
        """构建未知意图"""
        return ParsedIntent(
            intent=UserIntent.UNKNOWN,
            original_input=user_input,
            detected_domains=[DomainDetection(
                domain=ResearchDomain.UNKNOWN,
                confidence=0.0,
                reasoning="未知领域"
            )],
            inferred_techniques=[],
            inferred_applications=[],
            parameters=None,
            needs_context=False,
            confidence=0.0,
            reasoning=reason
        )

    def _default_llm_call(self, prompt: str, response_format: str = "json") -> Dict:
        """默认 LLM 调用（使用 llm_utils.call_llm）"""
        try:
            from src.utils.llm_utils import call_llm
            return call_llm(
                prompt=prompt,
                response_format=response_format
            )
        except ImportError:
            logger.error("[IntentParser] 无法导入 llm_utils")
            return {'success': False, 'error': 'LLM 不可用'}

    def _build_domain_mapping(self) -> Dict[str, ResearchDomain]:
        """构建领域名称映射"""
        mapping = {}
        for domain in ResearchDomain:
            mapping[domain.value] = domain
            # 添加别名
            if domain == ResearchDomain.MACHINE_LEARNING:
                mapping['ml'] = domain
            elif domain == ResearchDomain.DEEP_LEARNING:
                mapping['dl'] = domain
            elif domain == ResearchDomain.COMPUTER_VISION:
                mapping['cv'] = domain
        return mapping


# ==================== 便捷函数 ====================

_global_parser: Optional[IntentParser] = None


def get_intent_parser() -> IntentParser:
    """获取全局意图解析器实例"""
    global _global_parser
    if _global_parser is None:
        _global_parser = IntentParser()
    return _global_parser


def parse_intent(user_input: str, context: Optional[Dict] = None) -> ParsedIntent:
    """
    解析用户意图（便捷函数）

    Args:
        user_input: 用户原始输入
        context: 上下文信息

    Returns:
        ParsedIntent: 解析后的意图
    """
    parser = get_intent_parser()
    return parser.parse(user_input, context)


# ==================== 测试用例 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V8.0 意图解析器测试")
    print("=" * 70)

    test_cases = [
        "帮我找50篇关于CRISPR基因治疗的论文",
        "用AI帮医生看片子",
        "预测病人对药物的反应",
        "搜索最近3年关于深度学习在医学影像应用的论文",
        "把刚才的搜索扩大到100篇",
        "查看历史会话",
        "生成假设",
        "退出",
    ]

    parser = IntentParser()

    for test_input in test_cases:
        print(f"\n{'='*70}")
        print(f"输入: {test_input}")
        print(f"{'='*70}")

        result = parser.parse(test_input)

        print(f"意图: {result.intent.value}")
        print(f"置信度: {result.confidence:.2f}")
        print(f"理由: {result.reasoning}")

        if result.detected_domains:
            print("\n检测到的领域:")
            for dd in result.detected_domains:
                print(f"  - {dd.domain.value} (置信度: {dd.confidence:.2f})")
                print(f"    理由: {dd.reasoning}")

        if result.inferred_techniques:
            print(f"\n推断的技术方法: {', '.join(result.inferred_techniques)}")

        if result.inferred_applications:
            print(f"推断的应用场景: {', '.join(result.inferred_applications)}")

        if result.parameters:
            print(f"\n提取的参数:")
            print(f"  query: {result.parameters.query}")
            if result.parameters.max_results:
                print(f"  max_results: {result.parameters.max_results}")
            if result.parameters.date_range:
                print(f"  date_range: {result.parameters.date_range}")
            if result.parameters.sources:
                print(f"  sources: {result.parameters.sources}")
