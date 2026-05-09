# -*- coding: utf-8 -*-
"""
论文搜索智能体 - LLM摘要精读漏斗架构
三阶段流程：
1. 海量泛读 - ���取100-200篇文献
2. 摘要精读 - LLM打分筛选
3. 深度阅读 - 生成调研报告
"""
import sys
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
import time
import json
import anthropic

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import BaseAgent
from utils.pubmed import PubMedSearcher
from utils.llm_utils import SafeExtractor, LLMParseError
from core.database import Paper
from core.db_manager import get_db_manager
from core.reproducibility_engine import (
    DataSnapshotManager,
    get_audit_logger,
    DeterminismLock
)

logger = logging.getLogger(__name__)


class PaperSearchAgent(BaseAgent):
    """论文搜索智能体 - LLM摘要精读漏斗"""

    # LLM 判定 Prompt
    SCREENING_PROMPT = """你是一位极其苛刻的学术期刊编辑，在顶级期刊（Nature, Science, Cell）有20年审稿经验。

请仔细阅读以下论文摘要，从以下几个维度评估其与目标研究方向的关联度：

**评估维度**：
1. **方法论创新性**（0-10分）：是���提供了新的算法、模型或技术框架？是否有实质性创新？
2. **数据规模与质量**（0-10分）：样本量是否足够？数据是否经过严格质控？是否使用了公开数据集？
3. **结果可信度**（0-10分）：结论是否有充分验证？是否提供了消融实验或外部验证？
4. **研究类型**（0-10分）：
   - 原创研究：8-10分
   - 方法学论文：6-8分
   - 综述/Meta分析：2-4分（除非是系统综述）
   - 病例报告：3-5分

**评分标准**：
- 9-10分：顶级工作，必读
- 7-8分：优秀研究，值得参考
- 5-6分：尚可，但非核心
- 0-4分：低质量或不相关

**输出格式**（严格按此格式输出，只输出JSON）：
```json
{{
  "score": <0-10的分数>,
  "reason": "<一句话简述评分理由>",
  "innovation": "<方法论创新性评价>",
  "data_quality": "<数据质量评价>",
  "research_type": "<原创研究/方法论文/综述/病例报告>"
}}
```

---
**论文摘要**：

{title}

{abstract}
"""

    def __init__(self):
        super().__init__("论文搜索智能体", agent_type="paper_search")

        # 初始化 Anthropic client（添加超时设置）
        import httpx
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        # 创建带超时的httpx客户端
        http_client = httpx.Client(timeout=httpx.Timeout(45.0, connect=15.0))

        if base_url:
            self.client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=base_url,
                http_client=http_client,
                max_retries=0,
            )
        else:
            self.client = anthropic.Anthropic(
                api_key=self.api_key,
                http_client=http_client,
                max_retries=0,
            )

        self.searcher = PubMedSearcher(
            email=os.getenv("PUBMED_EMAIL"),
            api_key=os.getenv("PUBMED_API_KEY")
        )
        self.screening_model = self.config.get(
            'agents.paper_search.screening_model',
            os.getenv("PAPER_SCREENING_MODEL", "claude-sonnet-4-6")
        )

        # ========== 按需拉取参数 ==========
        # 严禁过载抓取：严格限制初次检索上限
        self.relevance_threshold = 7.0  # 默认相关性阈值：7.0/10
        self.max_stage1_papers = 100  # 阶段1最大获取数（严格限制，防止过载）
        self.default_stage2_top_k = 25  # 阶段2默认保留数
        self.default_stage2_candidate_limit = 15  # 阶段2默认精读候选上限
        self.max_stage2_candidate_limit = 30  # 阶段2候选硬上限，避免等待过长

        # 防弹解析器
        self.extractor = SafeExtractor()
        self.max_retries = 3

    def execute(self, input_data: Dict) -> Dict:
        """
        执行三阶段摘要精读漏斗（动态质量准入制）

        Args:
            input_data: {
                'query': str - 搜索关键词
                'max_results': int - 最终保留数量（用户指定，None表示基于阈值筛选）
                'date_range': tuple/str/int - 日期范围
                'min_if': float - 最低IF要求
                'relevance_threshold': float - 相关性阈值 (0-10)，超过此分数的文献保留
                'fetch_full_text': bool - 是否获取全文
            }

        Returns:
            {
                'success': bool,
                'papers': list - 筛选后的论文列表
                'stage1_stats': dict - 第一阶段统计
                'stage2_stats': dict - 第二阶段统计
                'stage3_stats': dict - 第三阶段统计
            }
        """
        stage1_result = self.run_stage1(input_data)
        if not stage1_result['success']:
            return stage1_result

        return self.run_stage2_and_save(stage1_result, input_data)

    def run_stage1(self, input_data: Dict) -> Dict:
        query = input_data.get('query', '')
        if not query:
            return {'success': False, 'error': '缺少搜索关键词', 'papers': []}

        max_results = input_data.get('max_results', None)
        date_range = input_data.get('date_range')
        min_if = input_data.get('min_if', 0)
        relevance_threshold = input_data.get('relevance_threshold', self.relevance_threshold)
        snapshot_path = input_data.get('snapshot_path')

        audit_logger = get_audit_logger()
        snapshot_manager = DataSnapshotManager()
        snapshot_file = None

        audit_logger.log_input(query, {
            'max_results': max_results,
            'date_range': date_range,
            'min_if': min_if,
            'relevance_threshold': relevance_threshold,
            'cutoff_date': snapshot_manager.get_cutoff_date().isoformat()
        })

        logger.info(f"LLM摘要精读漏斗启动: query={query}, mode={'threshold' if max_results is None else f'top_{max_results}'}")

        stage1_papers = []
        snapshot_used = False

        if snapshot_path and os.path.exists(snapshot_path):
            logger.info(f"加载快照复现: {snapshot_path}")
            try:
                snapshot_data = snapshot_manager.load_snapshot(snapshot_path)
                stage1_papers = snapshot_data.get('papers', [])
                snapshot_used = True

                logger.info(f"快照加载完成: papers={len(stage1_papers)}, cutoff={snapshot_data.get('cutoff_date')}")

                audit_logger.log_stage('snapshot_loaded', {
                    'snapshot_path': snapshot_path,
                    'papers_loaded': len(stage1_papers)
                })
            except Exception as e:
                logger.warning(f"快照加载失败，回退在线搜索: {e}")

        stage1_error = None
        if not stage1_papers:
            logger.info(f"阶段1开始: 截止日期 {snapshot_manager.get_cutoff_date()}")

            stage1_papers, stage1_error = self._stage1_fetch_abstracts(
                query=query,
                date_range=date_range,
                min_if=min_if
            )

            if stage1_papers:
                snapshot_file = snapshot_manager.create_snapshot(
                    stage1_papers,
                    metadata={'query': query, 'date_range': str(date_range)}
                )
                logger.info(f"阶段1快照已创建: {snapshot_file}")
                audit_logger.log_snapshot(snapshot_file, len(stage1_papers))

        if not stage1_papers:
            error_message = stage1_error if stage1_error else '未找到相关论文'
            if 'RemoteDisconnected' in error_message or 'connection' in error_message.lower():
                error_message = f'PubMed 连接失败: {error_message}\n\n建议：\n1. 检查网络连接\n2. 稍后重试\n3. 尝试使用更简单的关键词'
            return {
                'success': False,
                'error': error_message,
                'papers': []
            }

        stage1_stats = {
            'total_fetched': len(stage1_papers),
            'query': query
        }

        logger.info(f"阶段1完成: 获取到 {len(stage1_papers)} 篇论文摘要")

        return {
            'success': True,
            'papers': stage1_papers,
            'stage1_stats': stage1_stats,
            'snapshot_used': snapshot_used,
            'snapshot_path': snapshot_file if not snapshot_used and stage1_papers else None
        }

    def run_stage2(self, stage1_result: Dict, input_data: Dict) -> Dict:
        stage1_papers = stage1_result.get('papers', [])
        if not stage1_papers:
            return {
                'success': False,
                'error': '缺少阶段1候选论文',
                'papers': []
            }

        max_results = input_data.get('max_results', None)
        relevance_threshold = input_data.get('relevance_threshold', self.relevance_threshold)
        stage1_stats = stage1_result.get('stage1_stats', {
            'total_fetched': len(stage1_papers),
            'query': input_data.get('query', '')
        })

        candidate_limit = input_data.get('stage2_candidate_limit')
        if candidate_limit is None:
            candidate_limit = self.default_stage2_candidate_limit
            if max_results is not None:
                candidate_limit = min(candidate_limit, max_results)
        candidate_limit = max(1, min(int(candidate_limit), self.max_stage2_candidate_limit, len(stage1_papers)))
        stage2_candidates = stage1_papers[:candidate_limit]

        logger.info(f"阶段2开始: stage1_candidates={len(stage1_papers)}, screening_candidates={len(stage2_candidates)}")

        stage2_started_at = time.perf_counter()
        screened_papers = self._stage2_llm_screening(
            papers=stage2_candidates,
            top_k=max_results if max_results is not None else self.default_stage2_top_k,
            relevance_threshold=relevance_threshold
        )
        stage2_elapsed = time.perf_counter() - stage2_started_at
        logger.info(f"阶段2完成: elapsed={stage2_elapsed:.1f}s")

        stage2_stats = screened_papers['stats']
        stage2_stats['candidate_count'] = len(stage2_candidates)
        stage2_stats['total_stage1_candidates'] = len(stage1_papers)
        stage2_stats['elapsed_seconds'] = round(stage2_elapsed, 2)
        return {
            'success': True,
            'papers': screened_papers['papers'],
            'stage1_stats': stage1_stats,
            'stage2_stats': stage2_stats,
            'snapshot_used': stage1_result.get('snapshot_used', False),
            'snapshot_path': stage1_result.get('snapshot_path')
        }

    def run_stage2_and_save(self, stage1_result: Dict, input_data: Dict) -> Dict:
        stage2_result = self.run_stage2(stage1_result, input_data)
        if not stage2_result.get('success'):
            return stage2_result

        print(f"\n[阶段 3/3] 深度阅读 - 生成调研报告...")
        saved_count = self._save_papers_to_db(stage2_result['papers'])

        final_stats = {
            'total_fetched': stage2_result['stage1_stats']['total_fetched'],
            'screened_count': stage2_result['stage2_stats']['candidate_count'],
            'selected_count': len(stage2_result['papers']),
            'saved_count': saved_count,
            'avg_score': stage2_result['stage2_stats']['avg_score']
        }

        logger.info(
            f"漏斗筛选完成: stage1={stage2_result['stage1_stats']['total_fetched']}, "
            f"stage2_candidates={stage2_result['stage2_stats']['candidate_count']}, "
            f"selected={len(stage2_result['papers'])}, saved={saved_count}, "
            f"avg_score={stage2_result['stage2_stats']['avg_score']:.1f}"
        )

        stage2_result['stage3_stats'] = final_stats
        return stage2_result

    def _stage1_fetch_abstracts(
        self,
        query: str,
        date_range=None,
        min_if: float = 0
    ) -> tuple[List[Dict], str]:
        """
        阶段1: 获取文献摘要

        Returns:
            tuple: (papers列表, 错误信息(如果有))
        """
        error_msg = None
        try:
            # 清理查询
            clean_query = self._clean_query(query)

            # 构建搜索条件
            search_term = clean_query

            # 添加日期过滤
            if date_range:
                search_term = self._add_date_filter(search_term, date_range)

            logger.debug(f"阶段1搜索条件: {search_term[:100]}")

            # 执行搜索（动态质量准入制）
            import hashlib
            cache_key = f"search_{hashlib.md5(search_term.encode()).hexdigest()}"

            # 使用动态质量准入：不限制max_results，让PubMed返回所有符合条件的文献
            papers = self.searcher.search_papers(
                query=search_term,
                max_results=self.max_stage1_papers,  # 使用最��限制而非固定值
                enable_filter=(min_if > 0),
                date_range=date_range,
                min_if=min_if
            )

            return papers, None

        except Exception as e:
            error_msg = str(e)
            logger.warning(f"阶段1失败: {error_msg}")
            return [], error_msg

    def _stage2_llm_screening(
        self,
        papers: List[Dict],
        top_k: Optional[int] = None,  # None 表示使用阈值筛选
        relevance_threshold: float = 7.0
    ) -> Dict:
        """
        阶段2: LLM摘要精读评分（动态质量准入制）

        使用大模型对每篇摘要进行深度评分，根据相关性阈值筛选

        Args:
            papers: 论文��表
            top_k: 固定数量模式，保留前k篇（None表示使用阈值筛选）
            relevance_threshold: 相关性阈值，超过此分数的文献保留

        Returns:
            筛选后的论文和统计信息
        """
        screened_papers = []

        total = len(papers)
        batch_size = 5  # 每批处理5篇，避免API限流

        logger.info(f"阶段2精读配置: total={total}, batch_size={batch_size}, mode={'threshold' if top_k is None else f'top_{top_k}'}")

        for i in range(0, total, batch_size):
            batch = papers[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            batch_started_at = time.perf_counter()

            # 对这批论文进行LLM评分
            scored_batch = self._screen_batch_with_llm(batch)

            screened_papers.extend(scored_batch)
            batch_elapsed = time.perf_counter() - batch_started_at
            logger.debug(f"阶段2批次完成: batch={batch_num}/{total_batches}, elapsed={batch_elapsed:.1f}s")

            # 避免API限流，批次间暂停
            if i + batch_size < total:
                time.sleep(1)

        # 按分数排序
        screened_papers.sort(key=lambda x: x.get('llm_score', 0), reverse=True)

        # ========== 动态质量准入：基于阈值筛选 ==========
        if top_k is None:
            # 阈值筛选模式：保留所有超过阈值的"黄金情报"
            final_papers = [p for p in screened_papers if p.get('llm_score', 0) >= relevance_threshold]
            logger.info(f"阶段2阈值筛选完成: screened={len(screened_papers)}, selected={len(final_papers)}, threshold={relevance_threshold}")
        else:
            # 固定数量模式：取前 top_k 篇
            final_papers = screened_papers[:top_k]
            logger.info(f"阶段2固定数量筛选完成: screened={len(screened_papers)}, selected={len(final_papers)}")

        # 计算统计
        scores = [p.get('llm_score', 0) for p in final_papers]
        avg_score = sum(scores) / len(scores) if scores else 0

        stats = {
            'total_screened': len(screened_papers),
            'selected_count': len(final_papers),
            'avg_score': avg_score,
            'min_score': min(scores) if scores else 0,
            'max_score': max(scores) if scores else 0,
            'relevance_threshold': relevance_threshold
        }

        return {'papers': final_papers, 'stats': stats}

    def _screen_batch_with_llm(self, papers: List[Dict]) -> List[Dict]:
        """
        对一批论文进行LLM评分
        """
        scored_papers = []

        for paper in papers:
            title = paper.get('title', '')
            abstract = paper.get('abstract', '')

            if not abstract or len(abstract) < 50:
                # 摘要太短，给低分
                scored_papers.append({
                    **paper,
                    'llm_score': 2.0,
                    'llm_reason': '摘要过短或缺失',
                    'llm_innovation': 'N/A',
                    'llm_data_quality': 'N/A',
                    'llm_research_type': 'N/A'
                })
                continue

            # 调用LLM进行评分
            llm_result = self._call_llm_for_screening(title, abstract)

            scored_papers.append({
                **paper,
                'llm_score': llm_result.get('score', 5.0),
                'llm_reason': llm_result.get('reason', ''),
                'llm_innovation': llm_result.get('innovation', ''),
                'llm_data_quality': llm_result.get('data_quality', ''),
                'llm_research_type': llm_result.get('research_type', ''),
                'llm_fallback': llm_result.get('fallback', False),
                'llm_error_type': llm_result.get('error_type', ''),
            })

        return scored_papers

    def _call_llm_for_screening(self, title: str, abstract: str) -> Dict:
        """
        调用LLM进行摘要评分
        """
        try:
            # 构建完整提示
            prompt = self.SCREENING_PROMPT.format(
                title=f"**{title}**",
                abstract=abstract[:1800]
            )

            # 调用API
            message = self.client.messages.create(
                model=self.screening_model,
                max_tokens=220,
                messages=[{"role": "user", "content": prompt}]
            )

            # 解析响应
            response_text = self._extract_text_from_response(message.content)
            result = self._parse_llm_json_response(response_text)

            return result

        except Exception as e:
            import traceback
            logger.warning(f"LLM评分失败: {type(e).__name__}: {e}")
            logger.debug(f"LLM评分失败详情: {traceback.format_exc()[:500]}")
            return self._build_fallback_screening_result(title, abstract, type(e).__name__)

    def _build_fallback_screening_result(self, title: str, abstract: str, error_type: str) -> Dict:
        """LLM失败时使用启发式评分，避免所有候选都退化为固定分。"""
        import re

        text = f"{title} {abstract}".lower()
        score = 4.8
        innovation_notes = []
        data_notes = []

        research_type = '原创研究'
        if any(keyword in text for keyword in ('systematic review', 'meta-analysis', 'review')):
            research_type = '综述/Meta分析'
            score -= 1.0
        elif any(keyword in text for keyword in ('case report', 'case study')):
            research_type = '病例报告'
            score -= 1.5
        elif any(keyword in text for keyword in ('protocol', 'study design')):
            research_type = '方法论文'
            score -= 0.5

        innovation_keywords = {
            'single-cell': 0.5,
            'spatial': 0.5,
            'multi-omics': 0.5,
            'crispr': 0.4,
            'foundation model': 0.6,
            'deep learning': 0.4,
            'machine learning': 0.3,
            'transformer': 0.4,
            'novel': 0.3,
            'first': 0.2,
        }
        for keyword, bonus in innovation_keywords.items():
            if keyword in text:
                score += bonus
                innovation_notes.append(keyword)

        quality_keywords = {
            'prospective': 0.5,
            'randomized': 0.6,
            'multicenter': 0.5,
            'external validation': 0.7,
            'independent cohort': 0.5,
            'validation cohort': 0.4,
            'benchmark': 0.3,
        }
        for keyword, bonus in quality_keywords.items():
            if keyword in text:
                score += bonus
                data_notes.append(keyword)

        if len(abstract) >= 1200:
            score += 0.4
            data_notes.append('摘要信息完整')
        elif len(abstract) >= 700:
            score += 0.2

        sample_match = re.search(r'\b(n\s*=\s*|included\s+|enrolled\s+|patients?\s*=\s*)(\d{2,5})\b', text)
        if sample_match:
            sample_size = int(sample_match.group(2))
            if sample_size >= 500:
                score += 0.8
                data_notes.append(f'大样本({sample_size})')
            elif sample_size >= 100:
                score += 0.5
                data_notes.append(f'中等样本({sample_size})')
            elif sample_size >= 30:
                score += 0.2
                data_notes.append(f'小样本({sample_size})')

        if any(keyword in text for keyword in ('preclinical', 'mouse model', 'in vitro', 'cell line')):
            score -= 0.3
        if any(keyword in text for keyword in ('editorial', 'commentary', 'letter to the editor')):
            score -= 1.2
            research_type = '综述/Meta分析'

        score = max(2.5, min(round(score, 1), 8.8))
        reason_parts = []
        if innovation_notes:
            reason_parts.append(f"方法亮点: {', '.join(innovation_notes[:3])}")
        if data_notes:
            reason_parts.append(f"质量信号: {', '.join(data_notes[:3])}")
        if not reason_parts:
            reason_parts.append('按摘要长度与研究类型进行保守估分')
        reason_parts.append(f'LLM调用失败({error_type})，使用启发式回退')

        return {
            'score': score,
            'reason': '；'.join(reason_parts)[:100],
            'innovation': '、'.join(innovation_notes[:3]) if innovation_notes else '未见强创新信号',
            'data_quality': '、'.join(data_notes[:3]) if data_notes else '数据质量信号有限',
            'research_type': research_type,
            'fallback': True,
            'error_type': error_type,
        }

    def _parse_llm_json_response(self, response_text: str) -> Dict:
        """
        解析LLM返回的JSON响应
        """
        import re
        import json

        # 尝试提取JSON
        json_match = re.search(r'\{[\s\S]*?\}', response_text)
        if json_match:
            try:
                result = json.loads(json_match.group())
                # 确保所有必需字段存在
                if 'score' not in result:
                    result['score'] = 5.0
                if 'reason' not in result:
                    result['reason'] = '无理由'
                if 'innovation' not in result:
                    result['innovation'] = 'N/A'
                if 'data_quality' not in result:
                    result['data_quality'] = 'N/A'
                if 'research_type' not in result:
                    result['research_type'] = 'N/A'
                if 'fallback' not in result:
                    result['fallback'] = False
                if 'error_type' not in result:
                    result['error_type'] = ''
                return result
            except:
                pass

        # 解析失败，尝试从文本中提取分数
        score_match = re.search(r'(?:评分|score)[:\s]*([0-9]+(?:\.[0-9]+)?)', response_text)
        score = float(score_match.group(1)) if score_match else 5.0

        # 提取理由
        reason_match = re.search(r'(?:理由|reason|评价)[:\s]*[:：]([^。\n]+)', response_text)
        reason = reason_match.group(1).strip() if reason_match else "无法解析"

        return {
            'score': score,
            'reason': reason[:100],
            'innovation': 'N/A',
            'data_quality': 'N/A',
            'research_type': 'N/A',
            'fallback': False,
            'error_type': ''
        }

    def _save_papers_to_db(self, papers: List[Dict]) -> int:
        """保存论文到数据库"""
        saved_count = 0
        try:
            with self.db_manager.get_session() as session:
                for paper_data in papers:
                    if not paper_data.get('pmid'):
                        continue

                    # 检查是否已存在
                    existing = session.query(Paper).filter_by(pmid=paper_data['pmid']).first()
                    if existing:
                        continue

                    # 创建新记录
                    paper = Paper(
                        pmid=paper_data['pmid'],
                        title=paper_data.get('title', '')[:500],
                        abstract=paper_data.get('abstract', ''),
                        authors=paper_data.get('authors', '[]')[:500],
                        journal=paper_data.get('journal', '')[:200],
                        publication_date=paper_data.get('publication_date', None),
                        doi=paper_data.get('doi', ''),
                        # LLM 评分字段
                        llm_score=paper_data.get('llm_score', 0),
                        llm_reason=paper_data.get('llm_reason', ''),
                        llm_innovation=paper_data.get('llm_innovation', ''),
                        llm_data_quality=paper_data.get('llm_data_quality', ''),
                        llm_research_type=paper_data.get('llm_research_type', ''),
                        screening_date=datetime.now()
                    )
                    session.add(paper)
                    saved_count += 1

                session.commit()

        except Exception as e:
            print(f"  ⚠️ 保存到数据库失败: {e}")

        return saved_count

    def _clean_query(self, query: str) -> str:
        """清理查询字符串"""
        # 移除特殊字符
        import re
        query = re.sub(r'[^\w\s\-\(\)\[\]\{\}\.\,\+\*\/\:\"]', ' ', query)
        return ' '.join(query.split())

    def _add_date_filter(self, search_term: str, date_range) -> str:
        """添加日期过滤条件（使用正确的PubMed日期语法）"""
        if not date_range:
            return search_term

        current_year = datetime.now().year
        current_month = datetime.now().month
        current_day = datetime.now().day

        if isinstance(date_range, int):
            # 最近N年
            start_year = current_year - date_range + 1
            # 正确格式: ("2023/01/01"[PDAT] : "2026/04/13"[PDAT])
            return f'{search_term} AND ("{start_year}/01/01"[PDAT] : "{current_year}/{current_month:02d}/{current_day:02d}"[PDAT])'
        elif isinstance(date_range, tuple):
            # 自定义范围 (start_year, end_year)
            start_year, end_year = date_range
            # 正确格式: ("2023/01/01"[PDAT] : "2026/12/31"[PDAT])
            return f'{search_term} AND ("{start_year}/01/01"[PDAT] : "{end_year}/12/31"[PDAT])'
        return search_term

    def _extract_text_from_response(self, content) -> str:
        """从API响应中提取文本（正确处理 ThinkingBlock）"""
        text_parts = []
        for block in content:
            # 只处理 TextBlock，跳过 ThinkingBlock
            if hasattr(block, 'type') and block.type == 'text':
                text_parts.append(block.text)
            elif hasattr(block, 'text') and not hasattr(block, 'thinking'):
                # 兼容旧版本
                text_parts.append(block.text)
            elif isinstance(block, str):
                text_parts.append(block)
        return "\n".join(text_parts)

    # ==================== 预印本搜索与反向查重 ====================

    def search_preprints(self, query: str, max_results: int = 50, months: int = 18) -> List[Dict]:
        """搜索预印本 (bioRxiv/medRxiv) - 边缘知识检索"""
        import requests
        from datetime import timedelta

        # 计算截止日期
        cutoff_date = datetime.now() - timedelta(days=months*30)
        date_filter = cutoff_date.strftime('%Y-%m-%d')

        preprints = []

        try:
            # 使用 biorxiv API
            api_url = 'https://api.biorxiv.org/details/biorxiv/'
            params = {
                'format': 'json',
                'limit': max_results,
                'sort': 'submitted-date-desc',
                'from': date_filter
            }

            print(f'  [预印本搜索] 正在搜索 bioRxiv/medRxiv (最近{months}个月)...')

            response = requests.get(api_url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                collection = data.get('collection', [])

                for item in collection[:max_results]:
                    preprints.append({
                        'pmid': f"preprint_{item.get('doi', 'unknown')}",
                        'title': item.get('title', ''),
                        'abstract': item.get('abstract', ''),
                        'journal': 'bioRxiv/medRxiv',
                        'publication_date': item.get('date', ''),
                        'doi': item.get('doi', ''),
                        'authors': str(item.get('authors', []))[:500],
                        'is_preprint': True,
                        'llm_score': 8.0,
                        'preprint_date': item.get('date', '')
                    })

                print(f'  [预印本搜索] 找到 {len(preprints)} 篇预印本')
            else:
                print(f'  [预印本搜索] API请求失败，使用PubMed替代')

        except Exception as e:
            print(f'  [预印本搜索] 搜索失败: {e}')

        return preprints

    def reverse_search_check(self, hypothesis: Dict, papers: List[Dict] = None) -> Dict:
        """反向查重：检查假设是否已被发表"""
        import requests
        from datetime import timedelta

        # 提取核心关键词
        keywords = self._extract_keywords_from_hypothesis(hypothesis)

        print(f'  [反向查重] 核心关键词: {keywords}')

        # 构建反向搜索查询
        reverse_queries = []
        for i in range(len(keywords)):
            for j in range(i+1, len(keywords)):
                reverse_queries.append(f'{keywords[i]} AND {keywords[j]}')

        conflicting_papers = []

        # 对每个查询进行反向搜索
        for query in reverse_queries[:5]:
            try:
                base_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
                params = {
                    'db': 'pubmed',
                    'term': query,
                    'retmax': 5,
                    'sort': 'relevance',
                    'tool': 'research_agent',
                    'email': os.getenv('PUBMED_EMAIL', 'anon@example.com')
                }

                response = requests.get(base_url, params=params, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    pmids = data.get('esearchresult', {}).get('idlist', [])

                    if pmids:
                        # 获取论文详情
                        summary_params = {
                            'db': 'pubmed',
                            'id': ','.join(pmids),
                            'rettype': 'abstract'
                        }
                        summary_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi'
                        summary_response = requests.get(summary_url, params=summary_params, timeout=15)

                        if summary_response.status_code == 200:
                            summary_data = summary_response.json()
                            results = summary_data.get('result', {})

                            for pmid, paper_data in results.items():
                                if pmid == 'uids':
                                    continue
                                conflicting_papers.append({
                                    'pmid': pmid,
                                    'title': paper_data.get('title', ''),
                                    'abstract': paper_data.get('abstract', ''),
                                    'query_matched': query
                                })

            except Exception as e:
                print(f'  [反向查重] 查询失败: {query} - {e}')

        # 判定逻辑
        if conflicting_papers:
            return {
                'is_novel': False,
                'conflicting_papers': conflicting_papers,
                'warning_message': f'警告：该想法已被{len(conflicting_papers)}篇现有论文高度相关！已毙掉，要求重新生成！',
                'novelty_score': 0,
                'keywords_used': keywords
            }
        else:
            return {
                'is_novel': True,
                'conflicting_papers': [],
                'warning_message': '通过反向查重：未找到直接匹配的现有论文，该假设具备真正的新颖性！',
                'novelty_score': 10,
                'keywords_used': keywords
            }

    def _extract_keywords_from_hypothesis(self, hypothesis: Dict) -> List[str]:
        """从假设中提取核心关键词用于反向查重"""
        keywords = []
        import re

        # 从标题中提取
        title = hypothesis.get('title', '')
        if title:
            stopwords = {'的', '和', '与', '在', '是', '对', '为', '及', '其', '中', '等', '或', '一种', '研究', '方法', '分析', '基于', 'using', 'for', 'novel', 'new', 'approach'}
            words = title.replace('-', ' ').replace('(', ' ').replace(')', ' ').split()
            for word in words:
                word = word.strip().lower()
                if len(word) >= 3 and word not in stopwords:
                    keywords.append(word)

        # 从描述中提取
        description = hypothesis.get('description', '') + ' ' + hypothesis.get('rationale', '')

        # 疾病名模式
        disease_pattern = r'(?:阿尔茨海默|帕金森|糖尿病|癌症|肿瘤|COVID|心血管|神经退行性|自闭症|抑郁症|白血病|淋巴瘤)'
        diseases = re.findall(disease_pattern, description)
        keywords.extend(diseases)

        # 算法/方法名模式
        method_pattern = r'(?:Transformer|GNN|图神经网络|随机森林|SVM|深度学习|卷积神经网络|LSTM|VAE|GAN|BERT|注意力机制|CRISPR|单细胞|空间转录组|多组学)'
        methods = re.findall(method_pattern, description)
        keywords.extend(methods)

        # 靶点/基因名（全大写）
        target_pattern = r'\b[A-Z]{2,}\b'
        targets = re.findall(target_pattern, description)
        keywords.extend(targets)

        # 去重
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen and kw not in {'AND', 'OR', 'NOT'}:
                seen.add(kw)
                unique_keywords.append(kw)
                if len(unique_keywords) >= 5:
                    break

        return unique_keywords[:3]

    # ==================== 向后兼容的单阶段执行函数 ====================

def execute(input_data: Dict) -> Dict:
    """向后兼容的执行函数"""
    agent = PaperSearchAgent()
    return agent.execute(input_data)


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    # 测试LLM摘要精读漏斗
    agent = PaperSearchAgent()

    result = agent.execute({
        'query': 'machine learning genomics',
        'max_results': 25,
        'date_range': 3,  # 最近3年
        'min_if': 5,  # IF ≥ 5
        'fetch_full_text': False
    })

    if result['success']:
        print(f"\n最终获取 {len(result['papers'])} 篇高质量论文")
        for i, paper in enumerate(result['papers'][:5], 1):
            print(f"  {i}. [{paper.get('llm_score', 0):.1f}/10] {paper.get('title', 'Unknown')[:60]}...")
            print(f"     理由: {paper.get('llm_reason', 'N/A')[:80]}...")
