# -*- coding: utf-8 -*-
"""
早期熔断与两步生成法 (Fail-Fast Mechanism) - V3.0 架构升级核心模块

借鉴 karpathy/autoresearch 范式，重构 HypothesisAgent 的生成流程。

核心设计理念：
- 废弃"一次性输出完整报告"的模式
- 采用两阶段生成：先验证核心假说，再展开详细内容
- 早期熔断：发现同质化文献立即终止，避免浪费 Token

作者: 架构师 V3.0
日期: 2026-04-16
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
import re
from datetime import datetime

# V3.2 新增：导入全局 Token 硬上限管理器
from src.utils.llm_utils import token_hard_cap, TokenHardCapManager

logger = logging.getLogger(__name__)


class GenerationPhase(Enum):
    """生成阶段枚举"""
    PHASE_1_PROPOSAL = "phase_1_proposal"  # 核心机制假说（50字）
    PHASE_2_COLLISION = "phase_2_collision"  # PubMed 碰撞检测
    PHASE_3_EXPANSION = "phase_3_expansion"  # 完整七段式展开
    TERMINATED = "terminated"  # 提前终止


@dataclass
class Phase1Result:
    """Phase 1 结果：核心机制假说"""
    success: bool
    core_hypothesis: str = ""  # 50字以内的核心假说
    exposure: str = ""  # 暴露变量 (X)
    mediator: str = ""  # 中介变量 (M)
    outcome: str = ""  # 结果变量 (Y)
    causal_chain: str = ""  # 因果链描述
    raw_response: str = ""

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'core_hypothesis': self.core_hypothesis,
            'exposure': self.exposure,
            'mediator': self.mediator,
            'outcome': self.outcome,
            'causal_chain': self.causal_chain
        }


@dataclass
class Phase2Result:
    """Phase 2 结果：碰撞检测"""
    passed: bool  # 是否通过碰撞检测
    collision_count: int = 0  # 碰撞文献数量
    collision_papers: List[Dict] = field(default_factory=list)  # 碰撞文献列表
    novelty_score: float = 0.0  # 新颖性评分 (0-100)
    collision_reason: str = ""  # 碰撞原因描述
    should_terminate: bool = False  # 是否应该触发熔断

    def to_dict(self) -> Dict:
        return {
            'passed': self.passed,
            'collision_count': self.collision_count,
            'collision_papers': self.collision_papers,
            'novelty_score': self.novelty_score,
            'collision_reason': self.collision_reason,
            'should_terminate': self.should_terminate
        }


@dataclass
class Phase3Result:
    """Phase 3 结果：完整展开"""
    success: bool
    full_hypothesis: Dict = field(default_factory=dict)  # 完整的七段式假设
    raw_response: str = ""
    generation_time: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'full_hypothesis': self.full_hypothesis,
            'generation_time': self.generation_time
        }


@dataclass
class FailFastSession:
    """Fail-Fast 会话记录"""
    session_id: str
    research_topic: str
    phase1: Optional[Phase1Result] = None
    phase2: Optional[Phase2Result] = None
    phase3: Optional[Phase3Result] = None
    final_phase: GenerationPhase = GenerationPhase.PHASE_1_PROPOSAL
    terminated_reason: str = ""
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: str = ""
    token_saved: int = 0  # 节省的 Token 数量

    def to_dict(self) -> Dict:
        return {
            'session_id': self.session_id,
            'research_topic': self.research_topic,
            'phase1': self.phase1.to_dict() if self.phase1 else None,
            'phase2': self.phase2.to_dict() if self.phase2 else None,
            'phase3': self.phase3.to_dict() if self.phase3 else None,
            'final_phase': self.final_phase.value,
            'terminated_reason': self.terminated_reason,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'token_saved': self.token_saved
        }


class FailFastGenerator:
    """
    早期熔断生成器

    实现两阶段生成法：
    1. Phase 1: 仅生成 50 字的核心机制假说
    2. Phase 2: 立即进行 PubMed 碰撞检测
    3. Phase 3: 只有存活的假说才展开完整内容
    """

    # 熔断阈值
    COLLISION_THRESHOLD = 2  # 发现 2 篇以上同质化文献即熔断
    NOVELTY_THRESHOLD = 30.0  # 新颖性评分低于 30 分即熔断

    # Token 预估（用于计算节省的 Token）
    ESTIMATED_FULL_TOKENS = 6000  # 完整七段式约 6000 tokens
    ESTIMATED_PHASE1_TOKENS = 800  # Phase 1 约 800 tokens

    def __init__(self, llm_client, pubmed_searcher=None):
        """
        初始化 Fail-Fast 生成器

        Args:
            llm_client: LLM 客户端 (Anthropic/Claude)
            pubmed_searcher: PubMed 搜索器（用于碰撞检测）
        """
        self.llm_client = llm_client
        self.pubmed_searcher = pubmed_searcher
        self.logger = logger
        self.sessions: List[FailFastSession] = []

    def _log_state(self, phase: str, message: str):
        """记录状态日志"""
        log_msg = f"[{phase}] {message}"
        self.logger.info(log_msg)
        print(log_msg)

    def generate(
        self,
        research_topic: str,
        literature_context: str = "",
        papers: List[Dict] = None
    ) -> FailFastSession:
        """
        执行 Fail-Fast 生成流程

        Args:
            research_topic: 研究主题
            literature_context: 文献背景
            papers: 相关论文列表

        Returns:
            FailFastSession: 包含完整生成过程的会话记录
        """
        # ========== V3.2 新增：全局 Token 硬上限检查 ==========
        should_terminate, reason = token_hard_cap.should_terminate_generation()
        if should_terminate:
            self._log_state("Fail-Fast", f"⛔ [HARD CAP TRIGGERED] {reason}")
            return FailFastSession(
                session_id="hard_cap_terminated",
                research_topic=research_topic,
                final_phase=GenerationPhase.TERMINATED,
                terminated_reason=f"Token 硬上限触发: {reason}",
                token_saved=0
            )

        import uuid
        session = FailFastSession(
            session_id=str(uuid.uuid4())[:8],
            research_topic=research_topic
        )

        self._log_state("Fail-Fast", "="*60)
        self._log_state("Fail-Fast", f"🚀 启动 Fail-Fast 生成流程 | Session: {session.session_id}")
        self._log_state("Fail-Fast", "="*60)

        # ========== Phase 1: 核心机制假说 ==========
        self._log_state("Phase 1", "\n📍 Phase 1: 生成核心机制假说（约50字）...")

        session.phase1 = self._generate_phase1(
            research_topic=research_topic,
            literature_context=literature_context,
            papers=papers or []
        )

        if not session.phase1.success:
            session.final_phase = GenerationPhase.TERMINATED
            session.terminated_reason = "Phase 1 生成失败"
            self._log_state("Phase 1", "❌ 生成失败，终止流程")
            session.end_time = datetime.now().isoformat()
            return session

        self._log_state("Phase 1", f"✓ 核心假说: {session.phase1.core_hypothesis}")
        self._log_state("Phase 1", f"  因果链: {session.phase1.causal_chain}")

        # ========== Phase 2: 早期碰撞检测 ==========
        self._log_state("Phase 2", "\n📍 Phase 2: PubMed 碰撞检测（Early Collision Check）...")

        session.phase2 = self._check_collision(
            phase1_result=session.phase1,
            research_topic=research_topic
        )

        self._log_state("Phase 2", f"  碰撞文献数: {session.phase2.collision_count}")
        self._log_state("Phase 2", f"  新颖性评分: {session.phase2.novelty_score:.1f}/100")

        # ========== 熔断判断 ==========
        if session.phase2.should_terminate:
            session.final_phase = GenerationPhase.PHASE_2_COLLISION
            session.terminated_reason = session.phase2.collision_reason

            # 计算节省的 Token
            session.token_saved = self.ESTIMATED_FULL_TOKENS - self.ESTIMATED_PHASE1_TOKENS

            self._log_state("Fail-Fast", "\n" + "="*60)
            self._log_state("Fail-Fast", "🔴 [EARLY STOPPING] 熔断触发！")
            self._log_state("Fail-Fast", f"   原因: {session.phase2.collision_reason}")
            self._log_state("Fail-Fast", f"   节省 Token: ~{session.token_saved:,}")
            self._log_state("Fail-Fast", "="*60)

            # 打印碰撞文献
            if session.phase2.collision_papers:
                self._log_state("Fail-Fast", "\n📋 碰撞文献详情:")
                for i, paper in enumerate(session.phase2.collision_papers[:3], 1):
                    self._log_state("Fail-Fast",
                        f"   [{i}] PMID:{paper.get('pmid', 'N/A')} | {paper.get('title', '')[:50]}...")

            session.end_time = datetime.now().isoformat()
            return session

        self._log_state("Phase 2", "✓ 碰撞检测通过，继续展开...")

        # ========== Phase 3: 完整展开 ==========
        self._log_state("Phase 3", "\n📍 Phase 3: 完整七段式展开...")

        session.phase3 = self._generate_phase3(
            phase1_result=session.phase1,
            literature_context=literature_context,
            papers=papers or []
        )

        if session.phase3.success:
            session.final_phase = GenerationPhase.PHASE_3_EXPANSION
            self._log_state("Phase 3", "✓ 完整假设生成成功")
        else:
            session.final_phase = GenerationPhase.TERMINATED
            session.terminated_reason = "Phase 3 生成失败"
            self._log_state("Phase 3", "❌ Phase 3 生成失败")

        session.end_time = datetime.now().isoformat()

        self._log_state("Fail-Fast", "\n" + "="*60)
        self._log_state("Fail-Fast", f"🎉 生成流程完成 | 最终阶段: {session.final_phase.value}")
        self._log_state("Fail-Fast", "="*60)

        self.sessions.append(session)
        return session

    def _generate_phase1(
        self,
        research_topic: str,
        literature_context: str,
        papers: List[Dict]
    ) -> Phase1Result:
        """
        Phase 1: 生成核心机制假说（约50字）

        要求：
        - 明确因果链: X → M → Y
        - 字数限制在 50 字左右
        - 必须具体，不能空泛
        """
        prompt = f"""你是顶级科研假说生成专家。请基于以下研究主题，生成一个**核心机制假说**。

**研究主题**: {research_topic}

**文献背景**:
{literature_context[:500]}

**要求**:
1. 因果链明确：Exposure (X) → Mediator (M) → Outcome (Y)
2. 字数控制在 50 字左右
3. 必须具体，包含具体的生物标志物、分析方法或干预手段

**输出格式**（JSON）:
```json
{{
  "core_hypothesis": "一句话核心假说（50字左右）",
  "exposure": "暴露变量 X",
  "mediator": "中介变量 M",
  "outcome": "结果变量 Y",
  "causal_chain": "X → M → Y"
}}
```

请生成核心假说:"""

        try:
            response = self.llm_client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=1000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            result = self._parse_phase1_response(response_text)
            result.raw_response = response_text
            return result

        except Exception as e:
            self.logger.error(f"Phase 1 生成失败: {e}")
            return Phase1Result(success=False)

    def _parse_phase1_response(self, response_text: str) -> Phase1Result:
        """解析 Phase 1 响应"""
        try:
            # 提取 JSON
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
            else:
                # 尝试直接解析
                data = json.loads(response_text)

            return Phase1Result(
                success=True,
                core_hypothesis=data.get('core_hypothesis', ''),
                exposure=data.get('exposure', ''),
                mediator=data.get('mediator', ''),
                outcome=data.get('outcome', ''),
                causal_chain=data.get('causal_chain', '')
            )
        except Exception as e:
            self.logger.warning(f"JSON 解析失败，尝试从文本提取: {e}")
            # 文本提取 fallback
            return self._extract_phase1_from_text(response_text)

    def _extract_phase1_from_text(self, text: str) -> Phase1Result:
        """从纯文本中提取 Phase 1 结果（降级处理）"""
        sentences = re.split(r'[。！？.!?]', text)
        core_hypothesis = max([s.strip() for s in sentences if s.strip()], key=len, default="")

        # If extracted content is too short or empty, mark as failed
        if len(core_hypothesis) < 20:
            self.logger.warning(f"Text extraction failed: content too short ({len(core_hypothesis)} chars)")
            return Phase1Result(
                success=False,
                core_hypothesis="",
                exposure="",
                mediator="",
                outcome="",
                causal_chain=""
            )

        # Try to infer causal chain from text (simple heuristic)
        causal_keywords = ['causes', 'mediates', 'via', 'through', 'leading to', 'results in']
        has_causal_indicator = any(kw in text.lower() for kw in causal_keywords)

        return Phase1Result(
            success=has_causal_indicator,  # Only mark success if causal indicators found
            core_hypothesis=core_hypothesis[:100],
            exposure="",  # Cannot precisely extract in fallback mode
            mediator="",
            outcome="",
            causal_chain=core_hypothesis if has_causal_indicator else ""
        )

    def _check_collision(
        self,
        phase1_result: Phase1Result,
        research_topic: str
    ) -> Phase2Result:
        """
        Phase 2: PubMed 碰撞检测

        核心逻辑：
        1. 提取核心关键词
        2. 检索 PubMed
        3. 判断是否存在同质化研究
        4. 决定是否触发熔断
        """
        result = Phase2Result(passed=False, collision_count=0)

        if not self.pubmed_searcher:
            # 没有 PubMed 搜索器，默认通过
            result.passed = True
            result.novelty_score = 70.0
            return result

        # CRITICAL FIX: Check if Phase 1 actually succeeded
        if not phase1_result.success or not phase1_result.core_hypothesis:
            self.logger.warning("Phase 1 result invalid, rejecting continuation")
            result.passed = False
            result.should_terminate = True
            result.collision_reason = "Phase 1 generation failed or core hypothesis empty"
            result.novelty_score = 0.0
            return result

        # Build query
        keywords = [
            phase1_result.exposure,
            phase1_result.mediator,
            phase1_result.outcome
        ]
        keywords = [k for k in keywords if k]

        # CRITICAL FIX: If no valid keywords, reject instead of pass
        if not keywords:
            self.logger.warning("Phase 1 missing key variables (exposure/mediator/outcome), rejecting continuation")
            result.passed = False
            result.should_terminate = True
            result.collision_reason = "Core hypothesis incomplete, missing causal chain variables"
            result.novelty_score = 10.0
            return result

        # 执行检索（使用最简洁的查询）
        query = ' AND '.join([f'{k}[TIAB]' for k in keywords[:2]])
        self._log_state("Phase 2", f"  检索查询: {query}")

        try:
            papers = self.pubmed_searcher.search_papers(
                query=query,
                max_results=10,
                year_start=2020
            )

            result.collision_count = len(papers)
            result.collision_papers = papers[:5]

            # 分析碰撞程度
            high_collision = 0
            for paper in papers:
                similarity = self._calculate_similarity(phase1_result, paper)
                if similarity > 0.7:  # 相似度 > 70%
                    high_collision += 1
                    paper['similarity'] = similarity
                    result.collision_papers.append(paper)

            # 判断熔断
            if high_collision >= self.COLLISION_THRESHOLD:
                result.should_terminate = True
                result.passed = False
                result.novelty_score = max(0, 50 - high_collision * 10)
                result.collision_reason = f"发现 {high_collision} 篇高度同质化文献（相似度>70%）"
            else:
                result.should_terminate = False
                result.passed = True
                result.novelty_score = min(100, 50 + (5 - high_collision) * 10)
                result.collision_reason = "未发现致命同质化研究"

        except Exception as e:
            self.logger.warning(f"碰撞检测失败: {e}")
            # 检测失败时保守处理，允许继续
            result.passed = True
            result.novelty_score = 50.0

        return result

    def _calculate_similarity(self, phase1: Phase1Result, paper: Dict) -> float:
        """计算假说与文献的相似度"""
        # 简化版相似度计算
        title = paper.get('title', '').lower()
        abstract = paper.get('abstract', '').lower()

        # 关键词匹配
        keywords = [
            phase1.exposure.lower(),
            phase1.mediator.lower(),
            phase1.outcome.lower()
        ]
        keywords = [k for k in keywords if k]

        if not keywords:
            return 0.0

        match_count = 0
        for kw in keywords:
            if kw in title or kw in abstract:
                match_count += 1

        # 相似度 = 匹配关键词数 / 总关键词数
        return match_count / len(keywords)

    def _generate_phase3(
        self,
        phase1_result: Phase1Result,
        literature_context: str,
        papers: List[Dict]
    ) -> Phase3Result:
        """
        Phase 3: 完整七段式展开

        只有通过碰撞检测的假说才会进入此阶段
        生成完整的七段式 JSON 结构
        """
        # 构建论文上下文
        paper_context = ""
        if papers:
            paper_context = "\n\n## 核心论文\n"
            for i, p in enumerate(papers[:5], 1):
                paper_context += f"\n【论文{i}】\n"
                paper_context += f"标题: {p.get('title', 'N/A')}\n"
                paper_context += f"摘要: {p.get('abstract', 'N/A')[:300]}...\n"

        prompt = f"""你是《Nature Neuroscience》级别的审稿人兼 PI。基于已通过碰撞检测的核心假说，生成完整的七段式研究假设。

**核心假说**（已通过碰撞检测）:
- 核心陈述: {phase1_result.core_hypothesis}
- 因果链: {phase1_result.causal_chain}
- Exposure: {phase1_result.exposure}
- Mediator: {phase1_result.mediator}
- Outcome: {phase1_result.outcome}

**文献背景**:
{literature_context[:1000]}
{paper_context}

**七段式输出要求**:
1. 破局点批判 (Gap Analysis) [>=150字]
2. 核心科学假说 (The Core Hypothesis) [>=100字]
3. 颠覆性创新点 (The Innovation) [>=150字]
4. 底层逻辑与反事实推演 (Mechanism & Counterfactuals) [>=300字]
5. 详尽技术路线 (The Technical Roadmap) [>=400字]
6. 转化价值 (Translational Impact) [>=200字]
7. 证伪方案 (Falsification Plan) [>=200字]

**输出格式**（JSON）:
```json
{{
  "title": "假设标题",
  "details": "七段式完整内容（1500字以上）",
  "scores": {{
    "novelty": 8.5,
    "rigor": 9.0,
    "impact": 8.0,
    "overall": 8.5
  }}
}}
```

请生成完整假设:"""

        try:
            import time
            start_time = time.time()

            response = self.llm_client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=8000,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}]
            )

            generation_time = time.time() - start_time
            response_text = response.content[0].text

            # 解析响应
            full_hypothesis = self._parse_phase3_response(response_text)

            return Phase3Result(
                success=True,
                full_hypothesis=full_hypothesis,
                raw_response=response_text,
                generation_time=generation_time
            )

        except Exception as e:
            self.logger.error(f"Phase 3 生成失败: {e}")
            return Phase3Result(success=False)

    def _parse_phase3_response(self, response_text: str) -> Dict:
        """解析 Phase 3 响应"""
        try:
            # 提取 JSON
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            else:
                # 尝试直接解析
                return json.loads(response_text)
        except Exception as e:
            self.logger.warning(f"JSON 解析失败: {e}")
            return {
                'title': '解析失败',
                'details': response_text[:1000],
                'scores': {'novelty': 5.0, 'rigor': 5.0, 'impact': 5.0, 'overall': 5.0}
            }

    def get_session_statistics(self) -> Dict:
        """获取会话统计信息"""
        if not self.sessions:
            return {'total_sessions': 0}

        total = len(self.sessions)
        phase1_terminated = sum(1 for s in self.sessions if s.final_phase == GenerationPhase.PHASE_1_PROPOSAL)
        phase2_terminated = sum(1 for s in self.sessions if s.final_phase == GenerationPhase.PHASE_2_COLLISION)
        phase3_completed = sum(1 for s in self.sessions if s.final_phase == GenerationPhase.PHASE_3_EXPANSION)
        total_token_saved = sum(s.token_saved for s in self.sessions)

        return {
            'total_sessions': total,
            'phase1_terminated': phase1_terminated,
            'phase2_terminated': phase2_terminated,
            'phase3_completed': phase3_completed,
            'termination_rate': (phase1_terminated + phase2_terminated) / total,
            'total_token_saved': total_token_saved,
            'avg_token_saved_per_session': total_token_saved / total if total > 0 else 0
        }


# ========== 便捷函数 ==========

def create_fail_fast_generator(llm_client, pubmed_searcher=None) -> FailFastGenerator:
    """创建 Fail-Fast 生成器的便捷函数"""
    return FailFastGenerator(llm_client=llm_client, pubmed_searcher=pubmed_searcher)


if __name__ == '__main__':
    # 测试 Fail-Fast 生成器
    from dotenv import load_dotenv
    import anthropic
    load_dotenv()

    print("="*60)
    print("Fail-Fast Generator 测试")
    print("="*60)

    # 创建模拟客户端
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # 创建生成器
    generator = create_fail_fast_generator(client)

    # 测试生成
    session = generator.generate(
        research_topic="Alzheimer's disease and plasma pQTL biomarkers",
        literature_context="Recent studies have shown...",
        papers=[]
    )

    print(f"\n会话结果:")
    print(f"  最终阶段: {session.final_phase.value}")
    print(f"  核心假说: {session.phase1.core_hypothesis if session.phase1 else 'N/A'}")
    print(f"  碰撞检测: {session.phase2.passed if session.phase2 else 'N/A'}")
    print(f"  终止原因: {session.terminated_reason}")
