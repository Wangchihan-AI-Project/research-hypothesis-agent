# -*- coding: utf-8 -*-
"""
Token 熔断与压缩协议 (Token Fuse & Compression Protocol)

总工程师指令：为首席科学家 (HypothesisAgent) 的输入端植入 Token 预检机制

核心功能：
1. 强制 Token 预检：使用 tiktoken 计数预估 Token 总量
2. 安全红线：超过上下文窗口 85% 时触发熔断
3. 分级压缩策略：初级（移除Methods）、高级（剔除低分文献）
4. 结构化压缩：保证 [Paper X] 引用标记不混乱
"""
import re
import logging
from typing import Dict, List, Optional, Tuple, Literal
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 尝试导入 tiktoken，如果不可用则使用回退方案
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken 不可用，将使用回退的字符计数方案")

# 模型上���文窗口配置 (以 Claude/GPT 模型为准)
MODEL_CONTEXTS = {
    'claude-3-5-sonnet': 200000,
    'claude-3-5-haiku': 200000,
    'claude-3-opus': 200000,
    'claude-3-sonnet': 200000,
    'gpt-4-turbo': 128000,
    'gpt-4': 8192,
    'gpt-3.5-turbo': 16385,
    'default': 200000  # 默认使用较大的上下文
}

# 安全阈值：85%
SAFETY_BUFFER_RATIO = 0.85


@dataclass
class CompressionReport:
    """压缩报告"""
    original_token_count: int = 0
    compressed_token_count: int = 0
    compression_ratio: float = 0.0
    strategy_used: Literal['none', 'light', 'aggressive'] = 'none'
    papers_removed: int = 0
    methods_removed: bool = False
    warnings: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [
            f"[Token压缩报告]",
            f"  原始Token: {self.original_token_count:,}",
            f"  压缩后Token: {self.compressed_token_count:,}",
            f"  压缩率: {self.compression_ratio:.1%}",
            f"  策略: {self.strategy_used}",
        ]
        if self.papers_removed > 0:
            lines.append(f"  移除文献: {self.papers_removed} 篇 (低分)")
        if self.methods_removed:
            lines.append(f"  移除内容: Methods 细节")
        if self.warnings:
            lines.append(f"  警告: {', '.join(self.warnings)}")
        return '\n'.join(lines)


class TokenCounter:
    """Token 计数器 - 支持多种计数策略"""

    def __init__(self, model: str = 'claude-3-5-sonnet'):
        """
        初始化计数器

        Args:
            model: 目标模型名称，用于选择正确的编码器
        """
        self.model = model
        self.context_window = MODEL_CONTEXTS.get(model, MODEL_CONTEXTS['default'])
        self.safety_threshold = int(self.context_window * SAFETY_BUFFER_RATIO)

        if TIKTOKEN_AVAILABLE:
            # 使用 tiktoken 进行精确计数
            try:
                # 尝试使用 cl100k_base 编码（适用于 GPT-4 和 Claude）
                self.encoding = tiktoken.get_encoding('cl100k_base')
                self.use_tiktoken = True
            except Exception as e:
                logger.warning(f"tiktoken 初始化失败: {e}，使用回退方案")
                self.use_tiktoken = False
        else:
            self.use_tiktoken = False

    def count_tokens(self, text: str) -> int:
        """
        计算文本的 Token 数量

        Args:
            text: 待计数的文本

        Returns:
            Token 数量
        """
        if not text:
            return 0

        if self.use_tiktoken:
            try:
                return len(self.encoding.encode(text))
            except Exception as e:
                logger.warning(f"tiktoken 计数失败: {e}，使用回退方案")

        # 回退方案：中文字符 ≈ 1 token，英文单词 ≈ 0.75 token
        # 使用更精确的启发式方法
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        other_chars = len(text) - chinese_chars - english_words * 5  # 假设平均英文单词5字符

        # 中文: 1 char ≈ 1.5 tokens (实际测试)
        # 英文: 1 word ≈ 0.75 tokens
        estimated = chinese_chars * 1.5 + english_words * 0.75 + other_chars * 0.5
        return int(estimated * 1.2)  # 添加 20% 安全余量

    def is_safe(self, token_count: int) -> bool:
        """检查 Token 数量是否在安全范围内"""
        return token_count < self.safety_threshold

    def get_overflow_ratio(self, token_count: int) -> float:
        """
        获取溢出比例

        Returns:
            0 表示安全，>1 表示溢出的百分比 (如 1.2 表示超出 20%)
        """
        if token_count <= self.safety_threshold:
            return 0.0
        return (token_count - self.safety_threshold) / self.safety_threshold


class PaperCompressor:
    """论文压缩器 - 实施分级压缩策略"""

    def __init__(self, counter: TokenCounter):
        """
        初始化压缩器

        Args:
            counter: Token 计数器实例
        """
        self.counter = counter

    def compress_papers(
        self,
        papers: List[Dict],
        base_prompt_tokens: int,
        max_papers: int = 50
    ) -> Tuple[str, CompressionReport]:
        """
        压缩论文列表以适应 Token 限制

        Args:
            papers: 论文列表
            base_prompt_tokens: 基础 Prompt 的 Token 数量
            max_papers: 最大论文数量（硬限制）

        Returns:
            (压缩后的论文上下文字符串, 压缩报告)
        """
        report = CompressionReport()
        report.original_token_count = base_prompt_tokens

        if not papers:
            return "无具体论文引用", report

        # 限制最大论文数量
        papers = papers[:max_papers]

        # 初始格式化（完整版）
        full_context, initial_tokens = self._format_papers_full(papers)
        total_tokens = base_prompt_tokens + initial_tokens

        report.compressed_token_count = total_tokens

        # 检查是否需要压缩
        if self.counter.is_safe(total_tokens):
            report.strategy_used = 'none'
            return full_context, report

        # 计算溢出比例
        overflow_ratio = self.counter.get_overflow_ratio(total_tokens)

        logger.warning(f"[Token熔断] 检测到Token溢出: {total_tokens:,} / {self.counter.safety_threshold:,} (溢出 {overflow_ratio:.1%})")

        # ========== 初级压缩：移除 Methods 细节 ==========
        if overflow_ratio < 0.3:  # 轻微超标 (<30%)
            logger.info("[初级压缩] 移除 Methods 细节...")
            compressed_context, compressed_tokens = self._format_papers_light(papers)
            total_tokens = base_prompt_tokens + compressed_tokens

            if self.counter.is_safe(total_tokens):
                report.compressed_token_count = total_tokens
                report.strategy_used = 'light'
                report.methods_removed = True
                report.compression_ratio = 1 - (compressed_tokens / initial_tokens) if initial_tokens > 0 else 0
                logger.info(f"[初级压缩成功] Token: {initial_tokens:,} -> {compressed_tokens:,}")
                return compressed_context, report

        # ========== 高级压缩：剔除低分文献 ==========
        logger.info("[高级压缩] 移除低分文献...")
        compressed_context, compressed_tokens, removed_count = self._format_papers_aggressive(
            papers,
            base_prompt_tokens,
            self.counter.safety_threshold
        )
        total_tokens = base_prompt_tokens + compressed_tokens

        report.compressed_token_count = total_tokens
        report.strategy_used = 'aggressive'
        report.papers_removed = removed_count
        report.compression_ratio = 1 - (compressed_tokens / initial_tokens) if initial_tokens > 0 else 0

        if removed_count > 0:
            warning = f"[Token限制] 已自动忽略 {removed_count} 篇低评分文献"
            report.warnings.append(warning)
            logger.warning(warning)

        logger.info(f"[高级压缩完成] Token: {initial_tokens:,} -> {compressed_tokens:,}, 移除 {removed_count} 篇")

        # 最终安全检查
        if not self.counter.is_safe(total_tokens):
            critical_warning = f"[严重警告] 经过压缩后仍超过Token限制 ({total_tokens:,} / {self.counter.safety_threshold:,})"
            report.warnings.append(critical_warning)
            logger.error(critical_warning)

        return compressed_context, report

    def _format_papers_full(self, papers: List[Dict]) -> Tuple[str, int]:
        """格式化论文（完整版，包含所有信息）"""
        summaries = []
        for i, paper in enumerate(papers, 1):
            ctx = self._format_single_paper_full(paper, i)
            summaries.append(ctx)

        defensive_note = self._get_defensive_note()
        context = "\n\n".join(summaries) + defensive_note

        tokens = self.counter.count_tokens(context)
        return context, tokens

    def _format_papers_light(self, papers: List[Dict]) -> Tuple[str, int]:
        """格式化论文（轻量版，移除 Methods 等细节）"""
        summaries = []
        for i, paper in enumerate(papers, 1):
            ctx = self._format_single_paper_light(paper, i)
            summaries.append(ctx)

        defensive_note = self._get_defensive_note()
        context = "\n\n".join(summaries) + defensive_note

        tokens = self.counter.count_tokens(context)
        return context, tokens

    def _format_papers_aggressive(
        self,
        papers: List[Dict],
        base_tokens: int,
        target_limit: int
    ) -> Tuple[str, int, int]:
        """
        格式化论文（激进版，移除低分文献）

        Returns:
            (上下文字符串, Token数, 移除的论文数量)
        """
        # 按评分排序（如果有评分）
        scored_papers = []
        for p in papers:
            score = p.get('llm_score', p.get('relevance_score', 5.0))
            scored_papers.append((score, p))

        scored_papers.sort(key=lambda x: x[0], reverse=True)

        # 逐步增加论文数量，直到接近限制
        available_tokens = target_limit - base_tokens
        selected_papers = []
        current_tokens = 0

        defensive_note = self._get_defensive_note()
        note_tokens = self.counter.count_tokens(defensive_note)

        for score, paper in scored_papers:
            paper_text = self._format_single_paper_light(paper, len(selected_papers) + 1)
            paper_tokens = self.counter.count_tokens(paper_text)

            if current_tokens + paper_tokens + note_tokens <= available_tokens:
                selected_papers.append((score, paper))
                current_tokens += paper_tokens
            else:
                break  # 达到限制，停止添加

        removed_count = len(papers) - len(selected_papers)

        summaries = []
        for i, (score, paper) in enumerate(selected_papers, 1):
            ctx = self._format_single_paper_light(paper, i)
            summaries.append(ctx)

        context = "\n\n".join(summaries) + defensive_note
        total_tokens = self.counter.count_tokens(context)

        return context, total_tokens, removed_count

    def _format_single_paper_full(self, paper: Dict, index: int) -> str:
        """格式化单篇论文（完整版）"""
        ctx = f"<Paper_{index}>\n"
        ctx += f"PMID: {paper.get('pmid', 'N/A')}\n"
        ctx += f"标题: {paper.get('title', 'N/A')}\n"

        # 摘要（完整版，最多1000字符）
        abstract = paper.get('abstract', 'N/A')
        if abstract and abstract != 'N/A':
            ctx += f"摘要: {abstract[:1000]}\n"

        # 全文（如果有）
        full_text = paper.get('full_text', '')
        if full_text and len(full_text) > 100:
            ctx += f"全文: {full_text[:2000]}...\n"

        # LLM 评分和评价
        if 'llm_score' in paper:
            ctx += f"LLM评分: {paper.get('llm_score', 'N/A')}/10\n"
        if 'llm_reason' in paper:
            ctx += f"LLM评价: {paper.get('llm_reason', 'N/A')[:300]}\n"

        # 期刊和日期
        if paper.get('journal'):
            ctx += f"期刊: {paper.get('journal', 'N/A')}\n"
        if paper.get('publication_date'):
            ctx += f"发表日期: {paper.get('publication_date', 'N/A')}\n"

        ctx += f"</Paper_{index}>"
        return ctx

    def _format_single_paper_light(self, paper: Dict, index: int) -> str:
        """格式化单篇论文（轻量版，仅核心信息）"""
        ctx = f"<Paper_{index}>\n"
        ctx += f"PMID: {paper.get('pmid', 'N/A')}\n"
        ctx += f"标题: {paper.get('title', 'N/A')}\n"

        # 摘要（截取核心部分，最多500字符）
        abstract = paper.get('abstract', 'N/A')
        if abstract and abstract != 'N/A':
            # 尝试提取结论部分
            conclusion = self._extract_conclusion(abstract)
            if conclusion:
                ctx += f"核心结论: {conclusion}\n"
            else:
                ctx += f"摘要: {abstract[:500]}...\n"

        # LLM 评分（简化版）
        if 'llm_score' in paper:
            ctx += f"相关性: {paper.get('llm_score', 'N/A')}/10\n"

        ctx += f"</Paper_{index}>"
        return ctx

    def _extract_conclusion(self, abstract: str) -> Optional[str]:
        """从摘要中提取结论部分"""
        # 常见的结论引导词
        conclusion_patterns = [
            r'(?:结论|Conclusion|conclusions|综上|总之|In conclusion)[：:,]\s*(.{0,300})$',
            r'(?:结果表明|Results?[：:,]\s*)(.{0,200})$',
            r'(?:Our findings|We found)[：:,]\s*(.{0,200})$',
        ]

        for pattern in conclusion_patterns:
            match = re.search(pattern, abstract, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _get_defensive_note(self) -> str:
        """获取防御性提示"""
        return "\n\n<IMPORTANT_REMINDER>\n" \
               "你只能引用上述 <Paper_X> 标签中明确提供的文献。\n" \
               "严禁捏造、编造或幻觉生成任何不存在的论文、DOI或作者。\n" \
               "如果需要引用但上述文献未包含相关信息，请明确说明'根据当前文献未找到相关支持'。\n" \
               "</IMPORTANT_REMINDER>\n"


def pre_check_prompt(
    base_prompt: str,
    papers: List[Dict],
    model: str = 'claude-3-5-sonnet',
    max_papers: int = 50
) -> Tuple[str, CompressionReport]:
    """
    Prompt 预检入口函数

    Args:
        base_prompt: 基础 Prompt（不含论文上下文）
        papers: 论文列表
        model: 目标模型名称
        max_papers: 最大论文数量

    Returns:
        (论文上下文字符串, 压缩报告)
    """
    counter = TokenCounter(model)
    compressor = PaperCompressor(counter)

    # 计算基础 Prompt 的 Token 数
    base_tokens = counter.count_tokens(base_prompt)

    logger.info(f"[Token预检] 基础Prompt: {base_tokens:,} tokens, 论文数量: {len(papers)}, 安全阈值: {counter.safety_threshold:,}")

    # 执行压缩
    paper_context, report = compressor.compress_papers(papers, base_tokens, max_papers)

    # 记录报告
    logger.info(f"\n{report}")

    return paper_context, report
