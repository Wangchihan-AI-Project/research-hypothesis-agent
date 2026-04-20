# -*- coding: utf-8 -*-
"""
异步限流的草稿-验证检索 (Async Draft-Verification Retrieval)

V4.1 新增核心机制：
- 三阶段生成流程
- Phase 1: 快速草稿（关键词提取）
- Phase 2: 并发PubMed验证（支持/挑战/碰撞）
- Phase 3: 综合输出最终JSON
- 指数退避限流机制
"""

import asyncio
import time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.trace_memory import get_trace_memory, BoundedTraceMemory
from utils.llm_utils import SafeExtractor


class DraftPhase(Enum):
    """草稿阶段枚举"""
    PHASE_1_DRAFT = "phase_1_draft"      # 初步开题草稿
    PHASE_2_VERIFY = "phase_2_verify"    # 并发PubMed验证
    PHASE_3_FINAL = "phase_3_final"      # 综合最终输出


@dataclass
class DraftResult:
    """Phase 1 草稿结果"""
    success: bool
    draft_json: Dict
    core_keywords: List[str]           # 核心关键词（用于检索）
    challenge_keywords: List[str]      # 挑战关键词（反向检索）
    draft_time: float
    error_message: str = ""


@dataclass
class VerificationResult:
    """Phase 2 验证结果"""
    supporting_papers: List[Dict]      # 支持证据
    challenge_papers: List[Dict]       # 挑战文献
    collision_papers: List[Dict]       # 碰撞文献
    collision_detected: bool           # 是否检测到碰撞
    novelty_adjustment: float          # 新颖性调整值
    search_time: float
    queries_executed: List[str]        # 执行的查询列表


@dataclass
class FinalResult:
    """Phase 3 最终结果"""
    success: bool
    hypothesis: Dict                   # 最终假说JSON
    audit_info: Dict                   # 审计信息
    total_time: float
    phase: str                         # 结束阶段


class DraftVerificationRetrieval:
    """
    异步限流的草稿-验证检索

    三阶段流程：
    1. Phase 1: 快速输出开题草稿（不含文献引用）
    2. Phase 2: 并发检索（支持证据 + 挑战文献 + 碰撞检测）
    3. Phase 3: 综合输出最终JSON

    限流机制：
    - 指数退避，最高重试3次
    - 单次检索并发上限: 4
    - 基础延迟: 1秒
    """

    # 限流参数
    MAX_RETRIES = 3
    MAX_CONCURRENT_SEARCHES = 4
    BASE_DELAY = 1.0
    MAX_DELAY = 30.0

    # 碰撞阈值
    COLLISION_THRESHOLD = 2  # 2篇以上同质化文献即碰撞

    def __init__(self, llm_client, pubmed_searcher, session_id: str = None):
        """
        初始化草稿-验证检索器

        Args:
            llm_client: LLM客户端（anthropic.Anthropic）
            pubmed_searcher: PubMed搜索器实例
            session_id: 会话ID（用于失败记录）
        """
        self.llm_client = llm_client
        self.pubmed_searcher = pubmed_searcher
        self.session_id = session_id or datetime.now().strftime('%Y%m%d_%H%M%S')
        self.trace_memory = get_trace_memory()
        self.extractor = SafeExtractor()

        # 使用的模型
        self.model = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")

        print(f"[DraftVerification] 初始化完成，会话ID: {self.session_id}")

    async def execute(
        self,
        user_input: str,
        bootstrap_env: Dict,
        pi_system_prompt: str = None
    ) -> Tuple[Dict, Dict]:
        """
        执行完整三阶段流程

        Args:
            user_input: 用户原始输入
            bootstrap_env: Bootstrap环境快照
            pi_system_prompt: PI系统提示词（可选）

        Returns:
            Tuple[Dict, Dict]: (最终假说, 审计信息)
        """
        total_start_time = time.time()

        # Phase 1: 草稿生成
        print("[DraftVerification] Phase 1: 生成初步草稿...")
        draft_result = await self._generate_draft(user_input, bootstrap_env, pi_system_prompt)

        if not draft_result.success:
            # 草稿失败，记录并返回
            self.trace_memory.serialize_failure(
                hypothesis_summary="草稿生成失败",
                failure_reason=draft_result.error_message,
                collision_papers=[],
                session_id=self.session_id
            )
            return (
                self._fallback_output(user_input),
                {'phase': 'draft_failed', 'error': draft_result.error_message}
            )

        print(f"[DraftVerification] Phase 1 完成，关键词: {draft_result.core_keywords}")

        # Phase 2: 并发验证检索
        print("[DraftVerification] Phase 2: 并发PubMed验证...")
        verification_result = await self._verify_draft_concurrent(
            draft_result.core_keywords,
            draft_result.challenge_keywords
        )

        print(f"[DraftVerification] Phase 2 完成，碰撞检测: {verification_result.collision_detected}")

        # 碰撞检测熔断
        if verification_result.collision_detected:
            # 记录失败
            self.trace_memory.serialize_failure(
                hypothesis_summary=draft_result.draft_json.get('title', ''),
                failure_reason="高度同质化研究已存在",
                collision_papers=[p.get('pmid', 'N/A') for p in verification_result.collision_papers],
                session_id=self.session_id,
                domain=bootstrap_env.get('domain', 'unknown'),
                keywords=draft_result.core_keywords
            )

            return (
                self._collision_fallback(draft_result, verification_result),
                {
                    'phase': 'collision_detected',
                    'papers': verification_result.collision_papers,
                    'collision_count': len(verification_result.collision_papers),
                    'queries': verification_result.queries_executed
                }
            )

        # Phase 3: 综合输出
        print("[DraftVerification] Phase 3: 综合输出最终JSON...")
        final_result = await self._synthesize_final(
            draft_result,
            verification_result,
            user_input,
            bootstrap_env,
            pi_system_prompt
        )

        total_time = time.time() - total_start_time

        audit_info = {
            'phase': 'complete',
            'draft_keywords': draft_result.core_keywords,
            'challenge_keywords': draft_result.challenge_keywords,
            'supporting_count': len(verification_result.supporting_papers),
            'challenge_count': len(verification_result.challenge_papers),
            'novelty_adjustment': verification_result.novelty_adjustment,
            'queries_executed': verification_result.queries_executed,
            'total_time': total_time,
            'draft_time': draft_result.draft_time,
            'search_time': verification_result.search_time
        }

        print(f"[DraftVerification] 三阶段流程完成，总耗时: {total_time:.2f}s")

        return final_result, audit_info

    async def _generate_draft(
        self,
        user_input: str,
        bootstrap_env: Dict,
        pi_system_prompt: str = None
    ) -> DraftResult:
        """
        Phase 1: 生成初步草稿

        约束：
        - 限时60秒
        - 输出不含具体PMID引用
        - 必须提取核心关键词

        Args:
            user_input: 用户输入
            bootstrap_env: Bootstrap环境
            pi_system_prompt: PI系统提示词

        Returns:
            DraftResult: 草稿结果
        """
        start_time = time.time()

        # 构建草稿提示词
        prompt = self._build_draft_prompt(user_input, bootstrap_env, pi_system_prompt)

        # 指数退避重试
        for attempt in range(self.MAX_RETRIES):
            try:
                # 同步调用LLM（使用线程池）
                response = await asyncio.to_thread(
                    self._call_llm,
                    prompt
                )

                # 解析JSON
                draft_json = self.extractor.safe_extract_json(response)

                if not draft_json:
                    continue

                # 提取关键词
                core_keywords = self._extract_core_keywords(draft_json, user_input)
                challenge_keywords = self._derive_challenge_keywords(core_keywords)

                return DraftResult(
                    success=True,
                    draft_json=draft_json,
                    core_keywords=core_keywords,
                    challenge_keywords=challenge_keywords,
                    draft_time=time.time() - start_time
                )

            except Exception as e:
                print(f"[DraftVerification] 草稿生成尝试 {attempt + 1} 失败: {e}")

                if attempt < self.MAX_RETRIES - 1:
                    delay = self.BASE_DELAY * (2 ** attempt)
                    delay = min(delay, self.MAX_DELAY)
                    print(f"[DraftVerification] 指数退避: 等待 {delay}s")
                    await asyncio.sleep(delay)

        # 所有重试失败
        return DraftResult(
            success=False,
            draft_json={},
            core_keywords=[],
            challenge_keywords=[],
            draft_time=time.time() - start_time,
            error_message="草稿生成失败，请检查LLM连接"
        )

    async def _verify_draft_concurrent(
        self,
        core_keywords: List[str],
        challenge_keywords: List[str]
    ) -> VerificationResult:
        """
        Phase 2: 并发PubMed验证

        限流策略：
        - 最多4个并发检索
        - 每个检索独立重试（指数退避）

        Args:
            core_keywords: 核心关键词
            challenge_keywords: 挑战关键词

        Returns:
            VerificationResult: 验证结果
        """
        start_time = time.time()

        # 构建检索任务
        search_tasks = []
        queries_executed = []

        # 支持证据检索（核心关键词组合）
        if len(core_keywords) >= 2:
            support_query_1 = f"{core_keywords[0]} AND {core_keywords[1]}"
            support_query_2 = f"{core_keywords[0]} AND mechanism"
            search_tasks.extend([
                self._search_with_retry(support_query_1, 'support'),
                self._search_with_retry(support_query_2, 'support')
            ])
            queries_executed.extend([support_query_1, support_query_2])

        if len(core_keywords) >= 3:
            support_query_3 = f"{core_keywords[1]} AND {core_keywords[2]}"
            search_tasks.append(
                self._search_with_retry(support_query_3, 'support')
            )
            queries_executed.append(support_query_3)

        # 挑战文献检索（反向关键词）
        if challenge_keywords:
            challenge_query = " OR ".join(challenge_keywords[:3])
            search_tasks.append(
                self._search_with_retry(challenge_query, 'challenge')
            )
            queries_executed.append(challenge_query)

        # 碰撞检测检索（全部核心关键词）
        if len(core_keywords) >= 2:
            collision_query = " AND ".join(core_keywords[:3])
            search_tasks.append(
                self._search_with_retry(collision_query, 'collision')
            )
            queries_executed.append(collision_query)

        # 限制并发数
        search_tasks = search_tasks[:self.MAX_CONCURRENT_SEARCHES]

        # 并发执行
        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # 分类整理结果
        supporting_papers = []
        challenge_papers = []
        collision_papers = []

        for result in results:
            if isinstance(result, Exception):
                print(f"[DraftVerification] 检索异常: {result}")
                continue

            search_type, papers = result
            if search_type == 'support':
                supporting_papers.extend(papers)
            elif search_type == 'challenge':
                challenge_papers.extend(papers)
            elif search_type == 'collision':
                collision_papers.extend(papers)

        # 碰撞判断
        collision_detected = len(collision_papers) >= self.COLLISION_THRESHOLD

        # 新颖性调整（基于碰撞数量）
        novelty_adjustment = max(0, 10 - len(collision_papers) * 2)

        search_time = time.time() - start_time

        return VerificationResult(
            supporting_papers=supporting_papers[:10],
            challenge_papers=challenge_papers[:5],
            collision_papers=collision_papers[:5],
            collision_detected=collision_detected,
            novelty_adjustment=novelty_adjustment,
            search_time=search_time,
            queries_executed=queries_executed
        )

    async def _search_with_retry(
        self,
        query: str,
        search_type: str
    ) -> Tuple[str, List[Dict]]:
        """
        带重试的单次检索

        Args:
            query: 检索查询
            search_type: 检索类型 (support/challenge/collision)

        Returns:
            Tuple[str, List[Dict]]: (检索类型, 文献列表)
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                # 同步调用PubMed（使用线程池）
                papers = await asyncio.to_thread(
                    self.pubmed_searcher.search_papers,
                    query=query,
                    max_results=10,
                    year_start=2020
                )

                return (search_type, papers)

            except Exception as e:
                print(f"[DraftVerification] 检索 '{query}' 尝试 {attempt + 1} 失败: {e}")

                if attempt < self.MAX_RETRIES - 1:
                    delay = self.BASE_DELAY * (2 ** attempt)
                    delay = min(delay, self.MAX_DELAY)
                    await asyncio.sleep(delay)

        # 所有重试失败，返回空列表
        return (search_type, [])

    async def _synthesize_final(
        self,
        draft_result: DraftResult,
        verification_result: VerificationResult,
        user_input: str,
        bootstrap_env: Dict,
        pi_system_prompt: str = None
    ) -> Dict:
        """
        Phase 3: 综合输出最终JSON

        Args:
            draft_result: Phase 1 草稿结果
            verification_result: Phase 2 验证结果
            user_input: 用户原始输入
            bootstrap_env: Bootstrap环境
            pi_system_prompt: PI系统提示词

        Returns:
            Dict: 最终假说JSON
        """
        # 构建综合提示词
        prompt = self._build_synthesis_prompt(
            draft_result,
            verification_result,
            user_input,
            bootstrap_env,
            pi_system_prompt
        )

        # 指数退避重试
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await asyncio.to_thread(
                    self._call_llm,
                    prompt
                )

                final_json = self.extractor.safe_extract_json(response)

                if final_json:
                    # 添加审计信息
                    final_json['verification_info'] = {
                        'supporting_papers': [
                            p.get('pmid') for p in verification_result.supporting_papers[:5]
                        ],
                        'challenge_papers': [
                            p.get('pmid') for p in verification_result.challenge_papers[:3]
                        ],
                        'novelty_adjustment': verification_result.novelty_adjustment,
                        'queries': verification_result.queries_executed
                    }

                    return final_json

            except Exception as e:
                print(f"[DraftVerification] 综合输出尝试 {attempt + 1} 失败: {e}")

                if attempt < self.MAX_RETRIES - 1:
                    delay = self.BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)

        # 综合失败，返回草稿（加上验证信息）
        fallback = draft_result.draft_json.copy()
        fallback['verification_info'] = {
            'supporting_papers': [],
            'challenge_papers': [],
            'novelty_adjustment': verification_result.novelty_adjustment,
            'queries': verification_result.queries_executed,
            'synthesis_failed': True
        }
        return fallback

    def _call_llm(self, prompt: str) -> str:
        """
        同步调用LLM

        Args:
            prompt: 提示词

        Returns:
            str: LLM响应文本
        """
        try:
            message = self.llm_client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}],
                timeout=120
            )

            # 提取文本
            text_parts = []
            for block in message.content:
                if hasattr(block, 'type') and block.type == 'text':
                    text_parts.append(block.text)
                elif hasattr(block, 'text') and not hasattr(block, 'thinking'):
                    text_parts.append(block.text)

            return "\n".join(text_parts)

        except Exception as e:
            print(f"[DraftVerification] LLM调用失败: {e}")
            raise

    def _build_draft_prompt(
        self,
        user_input: str,
        bootstrap_env: Dict,
        pi_system_prompt: str = None
    ) -> str:
        """
        构建草稿提示词

        Args:
            user_input: 用户输入
            bootstrap_env: Bootstrap环境
            pi_system_prompt: PI系统提示词

        Returns:
            str: 草稿提示词
        """
        bootstrap_text = bootstrap_env.get('bootstrap_text', '')

        base_prompt = pi_system_prompt or """
你是Nature Neuroscience级别的首席科学家，专注于生成高质量的科研假设。

请按照以下要求生成初步开题草稿：

"""

        return f"""{base_prompt}

---

## 动态沙盒边界（Bootstrap Environment）

{bootstrap_text}

---

## 研究种子

{user_input}

---

## Phase 1 任务：初步开题草稿

请快速生成一个**不含具体PMID引用**的开题草稿。

要求：
1. 输出JSON格式
2. 包含: title, core_hypothesis, mechanism_outline, expected_impact
3. 必须提取3-5个核心关键词（用于后续验证检索）
4. 限时思考，不要过度深入
5. 必须遵守上述沙盒边界约束

输出格式：
```json
{
  "title": "假设标题（20-50字）",
  "core_hypothesis": "一句话核心假说，明确 X → M → Y 因果链",
  "mechanism_outline": "机制概述（200-300字）",
  "expected_impact": "预期影响（100字）",
  "core_keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"],
  "draft_phase": "phase_1"
}
```

请输出JSON：
"""

    def _build_synthesis_prompt(
        self,
        draft_result: DraftResult,
        verification_result: VerificationResult,
        user_input: str,
        bootstrap_env: Dict,
        pi_system_prompt: str = None
    ) -> str:
        """
        构建综合提示词

        Args:
            draft_result: 草稿结果
            verification_result: 验证结果
            user_input: 用户输入
            bootstrap_env: Bootstrap环境
            pi_system_prompt: PI系统提示词

        Returns:
            str: 综合提示词
        """
        bootstrap_text = bootstrap_env.get('bootstrap_text', '')

        # 构建文献证据摘要
        supporting_summary = ""
        for p in verification_result.supporting_papers[:5]:
            supporting_summary += f"- PMID: {p.get('pmid', 'N/A')}: {p.get('title', '')[:100]}\n"

        challenge_summary = ""
        for p in verification_result.challenge_papers[:3]:
            challenge_summary += f"- PMID: {p.get('pmid', 'N/A')}: {p.get('title', '')[:100]}\n"

        base_prompt = pi_system_prompt or """
你是Nature Neuroscience级别的首席科学家。

请基于草稿和文献验证结果，输出最终的完整科研假设。

"""

        return f"""{base_prompt}

---

## 动态沙盒边界

{bootstrap_text}

---

## Phase 1 草稿

{draft_result.draft_json}

---

## Phase 2 文献验证结果

### 支持证据（共 {len(verification_result.supporting_papers)} 篇）
{supporting_summary or "未找到直接支持证据"}

### 挑战文献（共 {len(verification_result.challenge_papers)} 篇）
{challenge_summary or "未找到挑战文献"}

### 新颖性调整值
{verification_result.novelty_adjustment}

---

## Phase 3 任务：综合输出最终JSON

请基于草稿和文献证据，输出**完整的七段式科研假设**。

要求：
1. 必须引用至少2篇真实PMID（来自上述文献证据）
2. 因果链必须具体：明确写出 X → M → Y 的变量名
3. 技术路线必须包含具体R包/函数/参数
4. 回答三个反事实问题：
   - 如果Mediator被阻断，Outcome如何变化？
   - 如果Exposure与Outcome关联消失，替代路径是什么？
   - 如果样本量减少50%，结论是否成立？
5. 必须遵守沙盒边界约束

输出格式（七段式）：
```json
{
  "title": "假设标题",
  "details": "七段式完整内容（1500字以上）",
  "scores": {
    "novelty": 8.0,
    "rigor": 9.0,
    "impact": 8.0,
    "overall": 8.5
  },
  "evidence": {
    "pubmed_queries": ["查询1", "查询2"],
    "collision_detected": false,
    "supporting_papers": ["PMID:1", "PMID:2"],
    "challenge_papers": ["PMID:3"]
  },
  "counterfactual_analysis": {
    "mediator_block_effect": "...",
    "alternative_pathway": "...",
    "sample_reduction_impact": "..."
  }
}
```

请输出JSON：
"""

    def _extract_core_keywords(self, draft_json: Dict, user_input: str) -> List[str]:
        """
        提取核心关键词

        Args:
            draft_json: 草稿JSON
            user_input: 用户输入

        Returns:
            List[str]: 核心关键词列表
        """
        # 从draft_json中提取
        keywords = draft_json.get('core_keywords', [])

        if keywords:
            return keywords[:5]

        # 从core_hypothesis中提取
        hypothesis = draft_json.get('core_hypothesis', '')
        if hypothesis:
            # 简单提取英文词
            import re
            words = re.findall(r'\b[A-Za-z]{3,10}\b', hypothesis)
            keywords.extend(words[:3])

        # 从title中提取
        title = draft_json.get('title', '')
        if title:
            words = re.findall(r'\b[A-Za-z]{3,10}\b', title)
            keywords.extend(words[:2])

        # 去重
        return list(dict.fromkeys(keywords))[:5]

    def _derive_challenge_keywords(self, core_keywords: List[str]) -> List[str]:
        """
        从核心关键词推导挑战关键词

        Args:
            core_keywords: 核心关键词

        Returns:
            List[str]: 挑战关键词
        """
        challenge_keywords = []

        # 添加否定词
        negations = ['NOT', 'against', 'contradict', 'refute']
        for kw in core_keywords[:2]:
            challenge_keywords.extend([f"NOT {kw}", f"{kw} against"])

        # 添加替代词
        alternatives = ['alternative', 'different', 'other']
        for kw in core_keywords[:2]:
            challenge_keywords.append(f"{kw} alternative")

        return challenge_keywords[:5]

    def _fallback_output(self, user_input: str) -> Dict:
        """
        草稿失败时的备用输出

        Args:
            user_input: 用户输入

        Returns:
            Dict: 备用假说
        """
        return {
            'title': "生成失败",
            'core_hypothesis': f"基于 {user_input} 的假说生成失败，请重试",
            'details': "草稿生成阶段失败，请检查LLM连接或简化输入",
            'scores': {'novelty': 0, 'rigor': 0, 'impact': 0, 'overall': 0},
            'draft_phase': 'failed'
        }

    def _collision_fallback(
        self,
        draft_result: DraftResult,
        verification_result: VerificationResult
    ) -> Dict:
        """
        碰撞检测时的备用输出

        Args:
            draft_result: 草稿结果
            verification_result: 验证结果

        Returns:
            Dict: 碰撞假说
        """
        return {
            'title': draft_result.draft_json.get('title', '碰撞检测'),
            'core_hypothesis': draft_result.draft_json.get('core_hypothesis', ''),
            'details': f"检测到 {len(verification_result.collision_papers)} 篇同质化文献，假说被熔断",
            'scores': {'novelty': 0, 'rigor': 0, 'impact': 0, 'overall': 0},
            'collision_papers': [p.get('pmid') for p in verification_result.collision_papers],
            'draft_phase': 'collision_fused'
        }


# ==============================================================================
# 同步包装器（用于非异步环境）
# ==============================================================================

def run_draft_verification_sync(
    llm_client,
    pubmed_searcher,
    user_input: str,
    bootstrap_env: Dict,
    pi_system_prompt: str = None,
    session_id: str = None
) -> Tuple[Dict, Dict]:
    """
    同步运行草稿-验证检索（包装异步函数）

    Args:
        llm_client: LLM客户端
        pubmed_searcher: PubMed搜索器
        user_input: 用户输入
        bootstrap_env: Bootstrap环境
        pi_system_prompt: PI系统提示词
        session_id: 会话ID

    Returns:
        Tuple[Dict, Dict]: (最终假说, 审计信息)
    """
    verifier = DraftVerificationRetrieval(
        llm_client=llm_client,
        pubmed_searcher=pubmed_searcher,
        session_id=session_id
    )

    # 运行异步函数
    return asyncio.run(
        verifier.execute(
            user_input=user_input,
            bootstrap_env=bootstrap_env,
            pi_system_prompt=pi_system_prompt
        )
    )