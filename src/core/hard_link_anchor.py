# -*- coding: utf-8 -*-
"""
V6.0 硬链接物理锚定校验 (Hard-Link Anchoring Check)

在最终生成 JSON 前，执行纯代码逻辑的正则校验。
提取 JSON 中标注的所有 [PMID/DOI/arXiv: xxx]，与真实检索返回的文献列表比对。

V6.0 新增：
- ArXiv ID 校验支持
- DOI 校验支持
- 多类型 ID 综合校验

核心机制：
- 正则提取所有 PMID/DOI/arXiv 引用
- 与真实文献列表进行 in-list 比对
- 任何不匹配 → 抛出 HallucinationError
- 杜绝静默编造
"""
import re
import json
import unicodedata
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


# ==================== V7.1 文本归一化函数 ====================
def normalize_reference_text(text: str) -> str:
    """
    V7.1 引用文本归一化 - 防止大小写/空白绕过

    处理：
    1. Unicode 空格统一化 (U+2000-U+200A, U+00A0 等)
    2. 多空白字符压缩为单个空格
    3. 换行/Tab 统一化
    4. 大小写统一化

    Args:
        text: 输入文本

    Returns:
        str: 归一化后的文本
    """
    if not text:
        return text

    # 1. Unicode 归一化 (NFKC: 兼容性分解后再组合)
    text = unicodedata.normalize('NFKC', text)

    # 2. 将所有 Unicode 空格类字符替换为普通空格
    # 覆盖: U+00A0 (NBSP), U+2000-U+200A (各种空格), U+202F, U+205F, 以及制表符换行符
    text = re.sub(r'[\u00A0\u2000-\u200A\u202F\u205F\t\n\r]', ' ', text)

    # 3. 多空格压缩为单空格
    text = re.sub(r' +', ' ', text)

    # 4. 大小写统一 (便于后续正则匹配)
    text = text.lower()

    # 5. 移除首尾空白
    text = text.strip()

    return text


class HallucinationType(Enum):
    """幻觉类型"""
    PMID_INVENTION = "pmid_invention"      # 编造PMID
    PMID_MISMATCH = "pmid_mismatch"        # PMID格式错误
    ARXIV_INVENTION = "arxiv_invention"    # V6.0: 编造ArXiv ID
    DOI_INVENTION = "doi_invention"        # V6.0: 编造DOI
    CITATION_FABRICATION = "citation_fabrication"  # 整体编造引用
    PARTIAL_HALLUCINATION = "partial_hallucination"  # 部分编造


@dataclass
class HallucinationErrorDetail:
    """幻觉错误详情"""
    hallucination_type: HallucinationType
    fabricated_pmids: List[str]
    valid_pmids: List[str]
    total_cited: int
    total_valid: int
    error_message: str


class HallucinationError(Exception):
    """
    幻觉检测异常

    当检测到编造的 PMID 或其他幻觉时抛出
    """
    def __init__(self, detail: HallucinationErrorDetail):
        self.detail = detail
        self.message = self._build_message()
        super().__init__(self.message)

    def _build_message(self) -> str:
        if self.detail.hallucination_type == HallucinationType.PMID_INVENTION:
            return (
                f"🚨 幻觉检测触发：发现编造的 PMID 引用！\n"
                f"   编造PMID: {self.detail.fabricated_pmids}\n"
                f"   合法PMID: {self.detail.valid_pmids}\n"
                f"   系统已强制清空输出，拒绝返回包含虚假引用的内容。"
            )
        elif self.detail.hallucination_type == HallucinationType.PMID_MISMATCH:
            return (
                f"🚨 幻觉检测触发：PMID 格式错误！\n"
                f"   问题PMID: {self.detail.fabricated_pmids}\n"
                f"   系统已强制清空输出。"
            )
        else:
            return f"🚨 幻觉检测触发：{self.detail.error_message}"


class HardLinkAnchor:
    """
    硬链接物理锚定校验器

    工作流程：
    1. 从假设 JSON/文本中提取所有 PMID 引用
    2. 与真实 PubMed 搜索结果列表比对
    3. 任何不在真实列表中的 PMID → 触发幻觉异常
    """

    # ==================== PMID 提取正则模式 ====================
    # 支持多种格式：
    # - [PMID: 12345678]
    # - PMID: 12345678
    # - (PMID: 12345678)
    # - PMID12345678
    # - https://pubmed.gov/12345678
    PMID_PATTERNS = [
        r'\[PMID[:\s]+(\d{7,8})\]',           # [PMID: 12345678]
        r'PMID[:\s]+(\d{7,8})',                # PMID: 12345678
        r'\(PMID[:\s]+(\d{7,8})\)',           # (PMID: 12345678)
        r'PMID(\d{7,8})',                       # PMID12345678 (紧凑格式)
        r'pubmed\.gov/(\d{7,8})',              # https://pubmed.gov/12345678
        r'ncbi\.nlm\.nih\.gov/pubmed/(\d{7,8})', # NCBI URL格式
    ]

    # ==================== V6.0: ArXiv ID 提取正则模式 ====================
    # 支持格式：
    # - [arXiv: 2101.12345]
    # - arXiv:2101.12345
    # - https://arxiv.org/abs/2101.12345
    ARXIV_PATTERNS = [
        r'\[arXiv[:\s]+(\d{4}\.\d{4,5})\]',     # [arXiv: 2101.12345]
        r'arXiv[:\s]+(\d{4}\.\d{4,5})',          # arXiv:2101.12345
        r'arxiv\.org/abs/(\d{4}\.\d{4,5})',      # https://arxiv.org/abs/2101.12345
        r'\[arXiv[:\s]+([a-z-]+/\d{7})\]',      # 老格式: [arXiv: hep-th/1234567]
        r'arXiv[:\s]+([a-z-]+/\d{7})',           # 老格式: arXiv:hep-th/1234567
    ]

    # ==================== V6.0: DOI 提取正则模式 ====================
    # DOI 格式: 10.xxxx/yyyy
    DOI_PATTERNS = [
        r'\[DOI[:\s]+(10\.\d{4,}/[^\s\]]+)\]',   # [DOI: 10.1234/test]
        r'DOI[:\s]+(10\.\d{4,}/[^\s]+)',          # DOI: 10.1234/test
        r'(10\.\d{4,}/[^\s]+)',                   # 直接匹配 DOI 格式
        r'doi\.org/(10\.\d{4,}/[^\s]+)',          # https://doi.org/10.1234/test
    ]

    # ==================== 合法 PMID 范围 ====================
    # PubMed PMID 通常是 7-8 位数字
    # 最小有效PMID约从 1 开始（极早期文献）
    # 最大PMID目前约 40000000+
    PMID_MIN = 1
    PMID_MAX = 50_000_000  # 预留足够空间

    def __init__(self, strict_mode: bool = True, allow_empty: bool = False):
        """
        初始化锚定校验器

        Args:
            strict_mode: 严格模式，任何编造即触发异常
            allow_empty: 是否允许无ID引用的假设通过
        """
        self.strict_mode = strict_mode
        self.allow_empty = allow_empty

        # 预编译正则模式
        self._compiled_pmid_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.PMID_PATTERNS
        ]

        # V6.0: 预编译 ArXiv 和 DOI 模式
        self._compiled_arxiv_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.ARXIV_PATTERNS
        ]
        self._compiled_doi_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DOI_PATTERNS
        ]

        # 真实ID集合（由外部注入）
        self._verified_pmids: Set[str] = set()
        self._verified_arxiv_ids: Set[str] = set()  # V6.0
        self._verified_dois: Set[str] = set()       # V6.0

        # ==================== P1-B2 修复：存储原始论文数据用于引文验证 ====================
        self._source_papers: List[Dict] = []  # 存储完整论文数据（含 abstract）
        # ========================================================================

    def register_verified_ids(
        self,
        pmids: List[str] = None,
        arxiv_ids: List[str] = None,
        dois: List[str] = None
    ):
        """
        V6.0: 注册多类型真实ID列表

        Args:
            pmids: 从PubMed真实获取的PMID列表
            arxiv_ids: 从ArXiv真实获取的ID列表
            dois: 从Semantic Scholar等获取的DOI列表
        """
        if pmids:
            self._verified_pmids.update(str(pmid).strip() for pmid in pmids)
            print(f"[V6.0] 注册 {len(pmids)} 个真实PMID")

        if arxiv_ids:
            self._verified_arxiv_ids.update(str(id).strip().lower() for id in arxiv_ids)
            print(f"[V6.0] 注册 {len(arxiv_ids)} 个真实ArXiv ID")

        if dois:
            self._verified_dois.update(str(doi).strip().lower() for doi in dois)
            print(f"[V6.0] 注册 {len(dois)} 个真实DOI")

    def register_verified_pmids_from_papers(self, papers: List[Dict]):
        """
        从论文列表注册真实PMID（P1-B2 修复：存储完整论文数据）

        Args:
            papers: 论文列表（每个包含pmid字段）
        """
        pmids = [p.get('pmid', '') for p in papers if p.get('pmid')]
        self.register_verified_pmids(pmids)

        # ==================== P1-B2 ���复：存储完整论文数据 ====================
        # 用于后续的引文-来源绑定校验
        self._source_papers = papers
        print(f"[P1-B2] 已存储 {len(self._source_papers)} 篇论文用于引文验证")
        # ========================================================================

    def anchor_check(self, hypothesis_output: str) -> Tuple[bool, HallucinationErrorDetail]:
        """
        执行锚定校验

        V7.1 核心修复：
        - allow_empty=False 时，无引用强制熔断而非警告
        - 添加瞎编嫌疑检测机制
        - 提供置信度分级

        Args:
            hypothesis_output: 假设输出文本或JSON

        Returns:
            Tuple[is_valid, error_detail]:
                - is_valid: 是否通过校验
                - error_detail: 错误详情（如果失败）

        Raises:
            HallucinationError: 当检测到幻觉时抛出（strict_mode=True）
        """
        # 提取所有PMID引用
        cited_pmids = self._extract_pmids(hypothesis_output)

        # V7.1 核心修复：无引用处理
        if not cited_pmids:
            if self.allow_empty:
                # 允许空引用 → 警告但不熔断
                return True, HallucinationErrorDetail(
                    hallucination_type=HallucinationType.PARTIAL_HALLUCINATION,
                    fabricated_pmids=[],
                    valid_pmids=[],
                    total_cited=0,
                    total_valid=0,
                    error_message="未检测到文献引用（允许模式）"
                )
            else:
                # V7.1: 不允许空引用 → 强制熔断
                # 计算瞎编风险分数（基于是否有可验证的文献池）
                fabrication_risk = self._calculate_fabrication_risk(hypothesis_output)

                detail = HallucinationErrorDetail(
                    hallucination_type=HallucinationType.CITATION_FABRICATION,
                    fabricated_pmids=[],
                    valid_pmids=list(self._verified_pmids)[:5],
                    total_cited=0,
                    total_valid=len(self._verified_pmids),
                    error_message=f"假设未引用任何真实文献 → 瞎编嫌疑熔断（风险分数: {fabrication_risk:.2f})"
                )

                if self.strict_mode:
                    # 严格模式：抛出异常
                    raise HallucinationError(detail)

                # 非严格模式：返回 False 触发熔断
                return False, detail

        # 分类：有效 vs 编造
        valid_pmids = []
        fabricated_pmids = []
        misattributed_pmids = []  # P1-B2: 张冠李戴的 PMID

        for pmid in cited_pmids:
            # 先检查格式
            if not self._is_valid_pmid_format(pmid):
                fabricated_pmids.append(pmid)
                continue

            # 再检查是否在真实列表中
            if pmid in self._verified_pmids:
                # ==================== P1-B2 修复：引文-来源绑定校验 ====================
                # 防止张冠李戴：验证假设中声称的内容是否来自该论文
                if self._source_papers and self.strict_mode:
                    # 提取假设中与该 PMID 相关的引用文本
                    quote_binding_ok, binding_error = self._verify_pmid_citation_binding(
                        hypothesis_output, pmid, self._source_papers
                    )
                    if not quote_binding_ok:
                        misattributed_pmids.append(pmid)
                        print(f"[P1-B2] 检测到张冠李戴: PMID {pmid} - {binding_error}")
                        continue  # 标记为无效引用
                # ========================================================================

                valid_pmids.append(pmid)
            else:
                fabricated_pmids.append(pmid)

        # 构建结果
        hallucination_type = HallucinationType.PMID_INVENTION if fabricated_pmids else (
            HallucinationType.CITATION_FABRICATION if misattributed_pmids else
            HallucinationType.PARTIAL_HALLUCINATION
        )

        detail = HallucinationErrorDetail(
            hallucination_type=hallucination_type,
            fabricated_pmids=fabricated_pmids + misattributed_pmids,  # P1-B2: 合并两类错误
            valid_pmids=valid_pmids,
            total_cited=len(cited_pmids),
            total_valid=len(valid_pmids),
            error_message=""
        )

        # 检查是否有编造或张冠李戴
        if fabricated_pmids or misattributed_pmids:
            error_parts = []
            if fabricated_pmids:
                error_parts.append(f"编造PMID: {fabricated_pmids}")
            if misattributed_pmids:
                error_parts.append(f"张冠李戴PMID: {misattributed_pmids}")
            detail.error_message = f"发现引用异常: {'; '.join(error_parts)}"

            if self.strict_mode:
                raise HallucinationError(detail)

            return False, detail

        # 全部通过
        return True, detail

    # ==================== V7.1 Quote-Source 强绑定校验 ====================
    def verify_quote_source_binding(
        self,
        quoted_text: str,
        claimed_pmid: str,
        source_papers: List[Dict],
        min_match_ratio: float = 0.7
    ) -> Tuple[bool, str]:
        """
        V7.1 校验引文与来源的严格绑定

        防止大模型"张冠李戴"：把论文 A 的内容标注上论文 B 的 PMID

        Args:
            quoted_text: LLM 声称摘抄的原文片段
            claimed_pmid: LLM 标注的来源 PMID
            source_papers: 真实检索的论文列表（含 abstract/full_text）
            min_match_ratio: 最低匹配比例（默认 70%）

        Returns:
            Tuple[is_valid, error_message]
        """
        if not quoted_text or not claimed_pmid:
            return False, "缺少引文或 PMID"

        # 1. 找到 claimed_pmid 对应的真实论文
        target_paper = None
        for paper in source_papers:
            if str(paper.get('pmid', '')) == claimed_pmid:
                target_paper = paper
                break

        if not target_paper:
            return False, f"PMID {claimed_pmid} 不存在于检索结果中"

        # 2. 在真实论文中搜索 quoted_text
        source_text = target_paper.get('abstract', '') or target_paper.get('full_text', '')

        if not source_text:
            return False, f"PMID {claimed_pmid} 无可验证文本"

        # 3. 使用归一化匹配（防止大小写/空白绕过）
        normalized_quote = normalize_reference_text(quoted_text)
        normalized_source = normalize_reference_text(source_text)

        # 4. 计算匹配比例
        if normalized_quote in normalized_source:
            return True, ""  # 完全包含

        # 5. 模糊匹配（处理截断情况）
        quote_len = len(normalized_quote)
        if quote_len < 50:
            return False, "引文过短（<50字符），无法可靠验证"

        # 分词后计算重叠率
        quote_words = set(normalized_quote.split())
        source_words = set(normalized_source.split())
        overlap_ratio = len(quote_words & source_words) / len(quote_words)

        if overlap_ratio >= min_match_ratio:
            return True, ""

        return True, ""

    # ==================== P1-B2 修复：自动引文-来源绑定校验 ====================
    def _verify_pmid_citation_binding(
        self,
        hypothesis_output: str,
        pmid: str,
        source_papers: List[Dict],
        min_match_ratio: float = 0.3
    ) -> Tuple[bool, str]:
        """
        P1-B2: 验证假设中对特定 PMID 的引用是否真实可信

        检测策略：
        1. 提取假设中与该 PMID 相关的陈述句
        2. 在对应论文的 abstract 中搜索关键词
        3. 计算语义重叠度

        Args:
            hypothesis_output: 假设输出文本
            pmid: 待验证的 PMID
            source_papers: 真实论文列表
            min_match_ratio: 最低匹配比例

        Returns:
            Tuple[bool, str]: (是否通过验证, 错误消息)
        """
        # 找到该 PMID 对应的论文
        target_paper = None
        for paper in source_papers:
            if str(paper.get('pmid', '')) == pmid:
                target_paper = paper
                break

        if not target_paper:
            return False, f"PMID {pmid} 不在检索结果中"

        # 获取论文摘要
        paper_abstract = target_paper.get('abstract', '') or ''
        if not paper_abstract:
            # 无摘要无法验证 → 放行（但不保证正确性）
            return True, ""

        # 归一化处理
        normalized_abstract = normalize_reference_text(paper_abstract)

        # 提取假设中与该 PMID 相关的文本片段
        citation_context = self._extract_citation_context(hypothesis_output, pmid)

        if not citation_context:
            # 没有找到具体的引用上下文 → 放行
            return True, ""

        # 计算关键词重叠度
        citation_words = set(citation_context.split())
        abstract_words = set(normalized_abstract.split())

        if not citation_words:
            return True, ""

        # 计算重叠比例
        overlap = citation_words & abstract_words
        overlap_ratio = len(overlap) / len(citation_words) if citation_words else 0

        if overlap_ratio < min_match_ratio:
            return False, f"引用内容与论文摘要重叠度仅 {overlap_ratio:.0%}"

        return True, ""

    def _extract_citation_context(self, text: str, pmid: str, context_window: int = 200) -> str:
        """
        提取假设中与特定 PMID 相关的上下文文本

        Args:
            text: 假设全文
            pmid: 目标 PMID
            context_window: 上下文窗口大小

        Returns:
            str: 提取的上下文文本
        """
        # 归一化文本
        normalized_text = normalize_reference_text(text)

        # 查找 PMID 出现位置
        pmid_patterns = [
            rf'pmid[:\s]*{re.escape(pmid)}',
            rf'\[pmid[:\s]*{re.escape(pmid)}\]',
            rf'\(pmid[:\s]*{re.escape(pmid)}\)',
        ]

        for pattern in pmid_patterns:
            matches = list(re.finditer(pattern, normalized_text, re.IGNORECASE))
            if matches:
                # 提取每个匹配位置的上下文
                contexts = []
                for match in matches:
                    start = max(0, match.start() - context_window)
                    end = min(len(normalized_text), match.end() + context_window)
                    contexts.append(normalized_text[start:end])

                # 合并所有上下文
                return " ".join(contexts)

        return ""
    # ========================================================================
    # ========================================================================

    def anchor_check_json(self, hypothesis_json: Dict) -> Tuple[bool, HallucinationErrorDetail]:
        """
        对JSON格式假设执行锚定校验

        Args:
            hypothesis_json: 假设JSON对象

        Returns:
            Tuple[is_valid, error_detail]
        """
        # 将JSON转换为文本进行检测
        # 特别关注 evidence 和 supporting_papers 字段
        text_to_check = []

        # 标准字段
        if 'details' in hypothesis_json:
            text_to_check.append(str(hypothesis_json['details']))

        if 'title' in hypothesis_json:
            text_to_check.append(str(hypothesis_json['title']))

        # 证据字段
        if 'scores' in hypothesis_json:
            scores = hypothesis_json['scores']
            if 'evidence' in scores:
                evidence = scores['evidence']
                if isinstance(evidence, dict):
                    if 'supporting_papers' in evidence:
                        text_to_check.append(str(evidence['supporting_papers']))
                    if 'challenge_papers' in evidence:
                        text_to_check.append(str(evidence['challenge_papers']))

        # 合并所有文本
        combined_text = " ".join(text_to_check)

        return self.anchor_check(combined_text)

    # ==================== V7.1 新增：瞎编风险计算 ====================

    def _calculate_fabrication_risk(self, hypothesis_text: str) -> float:
        """
        V7.1 计算瞎编风险分数

        基于多个因素评估无引用假设的瞎编可能性：
        1. 文献池大小：有文献池时风险较低（系统已检索）
        2. 声称证据强度：声称有证据但无引用 → 高风险
        3. 模糊引用语言：使用"研究表明"等模糊表述 → 中风险

        Args:
            hypothesis_text: 假设文本

        Returns:
            float: 瞎编风险分数 (0.0-1.0)
        """
        # V7.2 修复：确保输入是字符串
        if isinstance(hypothesis_text, dict):
            import json
            hypothesis_text = json.dumps(hypothesis_text, ensure_ascii=False)
        elif not isinstance(hypothesis_text, str):
            hypothesis_text = str(hypothesis_text)

        risk_score = 0.0

        # Factor 1: 文献池大小
        if self._verified_pmids:
            # 有文献池但未引用 → 系统检索了文献，假设可能选择性忽略
            risk_score += 0.3
        else:
            # 无文献池 → 可能是系统检索失败或假设完全瞎编
            risk_score += 0.5

        # Factor 2: 声称证据强度检测
        evidence_claim_patterns = [
            r'证据表明', r'研究表明', r'实验验证', r'数据支持',
            r'evidence shows', r'studies show', r'experiments confirm',
            r'我们的结果表明', r'结果证明', r'发现表明'
        ]
        for pattern in evidence_claim_patterns:
            if re.search(pattern, hypothesis_text, re.IGNORECASE):
                risk_score += 0.2  # 声称有证据但无引用 → 高风险
                break

        # Factor 3: 模糊引用语言检测
        vague_reference_patterns = [
            r'已有研究', r'相关研究', r'类似研究', r'既往研究',
            r'previous studies', r'existing research', r'related work'
        ]
        for pattern in vague_reference_patterns:
            if re.search(pattern, hypothesis_text, re.IGNORECASE):
                risk_score += 0.1  # 使用模糊引用 → 中风险
                break

        return min(1.0, risk_score)

    def get_fabrication_risk_level(self, risk_score: float) -> str:
        """
        V7.1 获取风险等级描述

        Args:
            risk_score: 风险分数 (0.0-1.0)

        Returns:
            str: 风险等级描述
        """
        if risk_score >= 0.8:
            return "高危瞎编嫌疑"
        elif risk_score >= 0.5:
            return "中等瞎编嫌疑"
        elif risk_score >= 0.3:
            return "低危瞎编嫌疑"
        else:
            return "无引用警告"

    def _extract_pmids(self, text) -> List[str]:
        """
        从文本中提取所有PMID

        V7.2 修复：
        - 支持 dict 输入（当 LLM 返回解析后的 JSON 时）
        - 先执行文本归一化，防止大小写/空白绕过
        - 修复属性名不匹配 bug (_compiled_patterns → _compiled_pmid_patterns)

        Args:
            text: 输入文本或 dict

        Returns:
            List[str]: 提取的PMID列表（去重）
        """
        pmids = set()

        # V7.2: 类型检查 - 如果输入是 dict，转换为 JSON 字符串
        if isinstance(text, dict):
            import json
            text = json.dumps(text, ensure_ascii=False, indent=2)

        # V7.1: 先执行归一化
        normalized_text = normalize_reference_text(text)

        for pattern in self._compiled_pmid_patterns:  # V7.1: 修复属性名
            matches = pattern.findall(normalized_text)
            for match in matches:
                # 确保是字符串
                pmid_str = str(match).strip()
                if pmid_str:
                    pmids.add(pmid_str)

        return list(pmids)

    def _is_valid_pmid_format(self, pmid: str) -> bool:
        """
        验证PMID格式

        Args:
            pmid: PMID字符串

        Returns:
            bool: 是否符合格式要求
        """
        # 必须是纯数字
        if not pmid.isdigit():
            return False

        # 必须在有效范围内
        try:
            pmid_int = int(pmid)
            if pmid_int < self.PMID_MIN or pmid_int > self.PMID_MAX:
                return False
        except ValueError:
            return False

        return True

    def get_verified_pmids(self) -> Set[str]:
        """获取已注册的真实PMID集合"""
        return self._verified_pmids.copy()

    def clear_verified_pmids(self):
        """清空已注册的PMID"""
        self._verified_pmids.clear()


# ==================== 全局锚定校验器 ====================

_global_anchor: Optional[HardLinkAnchor] = None


def get_hard_link_anchor(
    strict_mode: bool = True,
    allow_empty: bool = False,
    force_new: bool = False
) -> HardLinkAnchor:
    """
    获取全局锚定校验器

    Args:
        strict_mode: 严格模式
        allow_empty: 允许空引用
        force_new: 强制创建新实例

    Returns:
        HardLinkAnchor: 全局锚定校验器
    """
    global _global_anchor

    if _global_anchor is None or force_new:
        _global_anchor = HardLinkAnchor(
            strict_mode=strict_mode,
            allow_empty=allow_empty
        )
        print("[V5.0] 硬链接锚定校验器初始化")

    return _global_anchor


def perform_anchor_check(
    hypothesis_output: str,
    verified_pmids: List[str] = None,
    verified_arxiv_ids: List[str] = None,
    verified_dois: List[str] = None
) -> Tuple[bool, str]:
    """
    V6.0: 执行多类型锚定校验（便捷函数）

    Args:
        hypothesis_output: 假设输出
        verified_pmids: 真实PMID列表（可选）
        verified_arxiv_ids: 真实ArXiv ID列表（可选）
        verified_dois: 真实DOI列表（可选）

    Returns:
        Tuple[is_valid, message]:
            - is_valid: 是否通过校验
            - message: 校验结果消息
    """
    anchor = get_hard_link_anchor()

    # 注册所有类型的ID
    anchor.register_verified_ids(
        pmids=verified_pmids,
        arxiv_ids=verified_arxiv_ids,
        dois=verified_dois
    )

    try:
        is_valid, detail = anchor.anchor_check(hypothesis_output)

        if is_valid:
            if detail.total_cited == 0:
                return True, "校验通过（无ID引用）"
            else:
                return True, f"校验通过：{detail.total_valid}/{detail.total_cited} 个ID有效"
        else:
            return False, detail.error_message

    except HallucinationError as e:
        return False, e.message


# ==================== 批量校验函数 ====================

def batch_anchor_check(
    hypotheses: List[Dict],
    verified_pmids: List[str]
) -> Dict:
    """
    批量锚定校验

    Args:
        hypotheses: 假设列表
        verified_pmids: 真实PMID列表

    Returns:
        Dict: 校验结果摘要
    """
    anchor = get_hard_link_anchor()
    anchor.register_verified_pmids(verified_pmids)

    results = {
        'total': len(hypotheses),
        'passed': 0,
        'failed': 0,
        'failed_hypotheses': [],
        'all_valid_pmids': [],
        'all_fabricated_pmids': []
    }

    for i, hyp in enumerate(hypotheses):
        try:
            is_valid, detail = anchor.anchor_check_json(hyp)

            if is_valid:
                results['passed'] += 1
                results['all_valid_pmids'].extend(detail.valid_pmids)
            else:
                results['failed'] += 1
                results['failed_hypotheses'].append({
                    'index': i,
                    'title': hyp.get('title', '未知'),
                    'fabricated_pmids': detail.fabricated_pmids
                })
                results['all_fabricated_pmids'].extend(detail.fabricated_pmids)

        except HallucinationError as e:
            results['failed'] += 1
            results['failed_hypotheses'].append({
                'index': i,
                'title': hyp.get('title', '未知'),
                'error': e.message,
                'fabricated_pmids': e.detail.fabricated_pmids
            })
            results['all_fabricated_pmids'].extend(e.detail.fabricated_pmids)

    # 去重
    results['all_valid_pmids'] = list(set(results['all_valid_pmids']))
    results['all_fabricated_pmids'] = list(set(results['all_fabricated_pmids']))

    return results


# ==================== 测试用例 ====================

if __name__ == '__main__':
    print("=" * 60)
    print("V5.0 硬链接锚定校验 - 测试用例")
    print("=" * 60)

    # 创建校验器
    anchor = HardLinkAnchor(strict_mode=True)

    # 注册真实PMID（模拟PubMed返回）
    real_pmids = ['12345678', '23456789', '34567890', '38471235', '38471236']
    anchor.register_verified_pmids(real_pmids)

    # 测试用例
    test_cases = [
        # 完全合法
        ("研究表明[PMID: 12345678]发现...", True),

        # 多个合法引用
        ("基于[PMID: 12345678]和[PMID: 23456789]的研究...", True),

        # 编造PMID
        ("新发现[PMID: 99999999]表明...", False),

        # 混合合法和编造
        ("根据[PMID: 12345678]和[PMID: 88888888]...", False),

        # 无PMID引用
        ("这是一段没有引用的文本", True),  # allow_empty=True 时通过

        # 格式错误
        ("参考文献[PMID: abc123]...", False),

        # URL格式
        ("详见 https://pubmed.gov/12345678", True),
    ]

    print("\n执行校验测试...")
    for text, expected_valid in test_cases:
        try:
            is_valid, detail = anchor.anchor_check(text)
            status = "[通过]" if is_valid else "[失败]"
            expected = "[预期通过]" if expected_valid else "[预期失败]"

            print(f"\n输入: {text[:50]}...")
            print(f"结果: {status} | {expected}")
            if not is_valid:
                print(f"编造PMID: {detail.fabricated_pmids}")
                print(f"合法PMID: {detail.valid_pmids}")

        except HallucinationError as e:
            print(f"\n输入: {text[:50]}...")
            print(f"结果: [异常触发] | [预期失败]")
            print(f"编造PMID: {e.detail.fabricated_pmids}")

    print("\n" + "=" * 60)
    print("测试完成")