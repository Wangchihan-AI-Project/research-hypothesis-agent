# -*- coding: utf-8 -*-
"""
V8.1 意图明确化引导对话 (Intent Clarifier)

核心功能：
1. LLM 语义层理解用户输入，评估科研维度完整度
2. 检测缺失的关键科研要素
3. 生成上下文感知的引导追问（最多 2 轮）
4. 累积用户回答，构建完整的研究画像

完全由 LLM 驱动，不做关键词匹配或模板填充。

作者: V8.1
日期: 2026-05-03
"""
import json
import os
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
env_file = project_root / '.env'
if env_file.exists():
    load_dotenv(env_file, encoding='utf-8')

logger = logging.getLogger(__name__)

MAX_CLARIFICATION_ROUNDS = 2


# ==================== 数据结构 ====================

@dataclass
class ResearchDimension:
    """科研维度评估"""
    dimension: str           # 维度名称
    label_zh: str           # 中文标签
    is_specified: bool       # 用户是否已明确
    what_is_known: str       # 已提取到的信息（自然语言）
    what_is_missing: str     # 缺失的关键信息（自然语言）


@dataclass
class ClarificationResult:
    """明确化评估结果"""
    clarity_score: float                          # 0.0-1.0 整体清晰度
    is_clear_enough: bool                         # 是否足够清晰可直接搜索
    research_scope_summary: str                   # 对用户研究意图的语义理解总结
    dimensions: List[Dict[str, Any]] = field(default_factory=list)  # 各维度评估
    missing_dimensions: List[str] = field(default_factory=list)     # 未明确的维度名
    follow_up_questions: List[str] = field(default_factory=list)    # 追问列表
    refined_query: str = ""                       # 明确化后的搜索 query
    round_count: int = 0                          # 当前追问轮次
    conversation_history: List[Dict] = field(default_factory=list)  # 对话历史


# ==================== 核心 Agent ====================

class IntentClarifier:
    """V8.1 意图明确化引导 Agent"""

    CLARIFICATION_SYSTEM_PROMPT = """你是一位资深科研顾问，擅长通过对话帮助研究者明确和细化他们的研究方向。

你的任务分为两步：
1. **语义深度理解**：从用户输入中提取所有已明确的信息
2. **精准追问**：针对真正缺失的关键信息，生成 1-3 个引导性问题

## 评估维度

请从以下 5 个维度评估用户输入的完整度：

1. **research_subject（研究对象）**：疾病/生物过程/靶点/系统 —— 用户想研究什么？
2. **methodological_approach（方法路径）**：技术路线/实验方法/分析手段 —— 用户打算用什么方法？
3. **population_context（人群/样本上下文）**：目标人群/细胞类型/动物模型/样本来源 —— 研究对象是什么？
4. **outcome_direction（结果/产出方向）**：诊断/预后/机制/干预/治疗/发现 —— 最终目标是什么？
5. **innovation_angle（创新角度）**：新组合/新方法/新人群/新机制/新靶点 —— 与众不同之处在哪？

## 判断标准

- **clarity_score ≥ 0.75**：有明确的子领域 + 至少一种方法/技术指向 + 有临床/生物学上下文 → 可以直接研究
- **clarity_score 0.40-0.74**：领域明确但方法或上下文缺失 → 需要 1-2 轮追问
- **clarity_score < 0.40**：只有一个宽泛词（如"癌症"、"AI"）→ 需要深度引导

## 追问原则

- 只追问**缺失的关键维度**，已明确的维度不要问
- 问题要**具体且可回答**，不要开放式哲学问题
- 每个问题给 2-3 个**示例选项**引导用户
- 问题语言与用户输入语言保持一致
- 如果用户回答中已包含对之前追问的回答，则自动提取，不再重复问
- 如果用户说"直接开始"/"就这样"/"先试试"，则尊重用户，不再追问

## 输出格式

严格输出 JSON（不要包含 markdown 代码块标记）：

{
  "clarity_score": 0.45,
  "is_clear_enough": false,
  "research_scope_summary": "用户想研究阿尔茨海默病的相关方向，但研究对象（具体哪个方面）、方法路径、目标人群均未明确",
  "dimensions": [
    {
      "dimension": "research_subject",
      "label_zh": "研究对象",
      "is_specified": true,
      "what_is_known": "阿尔茨海默病",
      "what_is_missing": "未明确具体关注点：病理机制/早期诊断/药物干预/生物标记物等"
    }
  ],
  "missing_dimensions": ["methodological_approach", "population_context", "outcome_direction"],
  "follow_up_questions": [
    "您关注阿尔茨海默病的哪个方面？例如：早期血液生物标记物检测、tau蛋白病理机制、Aβ靶向药物开发、认知功能保护策略",
    "您倾向使用哪种研究手段？例如：单细胞转录组、影像学AI分析、生物样本队列分析、老药新用筛选"
  ],
  "refined_query": "阿尔茨海默病"
}"""

    CLARIFICATION_FOLLOWUP_PROMPT = """这是第 {round_number} 轮追问。用户对上一轮问题的回答如下：

上一轮问题：{previous_questions}
用户回答：{user_answer}

请基于用户的回答，更新各个维度的评估。如果用户已经补充了关键信息，clarity_score 应该相应提高。
如果用户明确表示不想继续回答/直接开始，不管分数如何，设置 is_clear_enough = true。

如果所有关键维度已覆盖 (clarity_score ≥ 0.75)，设置 is_clear_enough = true，follow_up_questions 为空数组。
如果仍有严重缺口且轮次未达上限，给出最后一组追问（不超过 2 个问题）。

输出 JSON（不要包含 markdown 代码块标记）：
{
  "clarity_score": 0.72,
  "is_clear_enough": false,
  "research_scope_summary": "对现有理解的更新",
  "dimensions": [...],
  "missing_dimensions": [...],
  "follow_up_questions": [...],
  "refined_query": "明确化后的搜索关键词组合"
}"""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.base_url = os.getenv("ANTHROPIC_BASE_URL")
        self.model = os.getenv("CLARIFIER_MODEL") or os.getenv("MODEL", "claude-sonnet-4-6")
        self._client = None

    def _get_client(self):
        if self._client is None and self.api_key:
            import anthropic
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def _call_llm(self, system_prompt: str, user_message: str) -> Dict[str, Any]:
        """调用 LLM 并解析 JSON 结果"""
        client = self._get_client()
        if client is None:
            return self._fallback_assessment(user_message)

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            text = response.content[0].text
            return self._parse_json_response(text)
        except Exception as e:
            logger.warning(f"IntentClarifier LLM 调用失败: {e}")
            return self._fallback_assessment(user_message)

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """从 LLM 输出中提取 JSON"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            data = json.loads(text)
            # 确保必要字段存在
            data.setdefault("clarity_score", 0.5)
            data.setdefault("is_clear_enough", False)
            data.setdefault("research_scope_summary", "")
            data.setdefault("dimensions", [])
            data.setdefault("missing_dimensions", [])
            data.setdefault("follow_up_questions", [])
            data.setdefault("refined_query", "")
            return data
        except json.JSONDecodeError:
            logger.warning(f"IntentClarifier JSON 解析失败: {text[:200]}")
            return self._fallback_assessment(text)

    def _fallback_assessment(self, user_input: str) -> Dict[str, Any]:
        """LLM 不可用时的回退"""
        word_count = len(user_input.strip().split())
        if word_count < 5:
            score, is_clear = 0.3, False
            questions = [
                "能否更具体地描述您想研究的领域？例如具体疾病、技术方法或研究角度",
                "您希望从哪个方面切入？例如机制研究、诊断方法、治疗方案、新技术应用"
            ]
        elif word_count < 12:
            score, is_clear = 0.55, False
            questions = ["能否补充您打算使用的研究方法或技术路线？"]
        else:
            score, is_clear = 0.72, True
            questions = []

        return {
            "clarity_score": score,
            "is_clear_enough": is_clear,
            "research_scope_summary": f"用户输入: {user_input[:100]}",
            "dimensions": [],
            "missing_dimensions": [],
            "follow_up_questions": questions,
            "refined_query": user_input.strip()
        }

    def assess(
        self,
        user_input: str,
        previous_result: Optional[ClarificationResult] = None
    ) -> ClarificationResult:
        """
        评估用户输入的科研意图明确度，必要时生成追问。

        Args:
            user_input: 用户原始输入
            previous_result: 上一轮评估结果（多轮追问时传入）

        Returns:
            ClarificationResult: 评估结果
        """
        # 用户主动跳过
        skip_keywords = ["直接开始", "就这样", "先试试", "开始吧", "just start", "go ahead", "skip"]
        if any(kw in user_input.lower() for kw in skip_keywords):
            return ClarificationResult(
                clarity_score=1.0,
                is_clear_enough=True,
                research_scope_summary=previous_result.research_scope_summary if previous_result else user_input,
                refined_query=previous_result.refined_query if previous_result else user_input,
                round_count=(previous_result.round_count if previous_result else 0) + 1
            )

        round_count = 0
        if previous_result is not None:
            round_count = previous_result.round_count + 1
            if round_count > MAX_CLARIFICATION_ROUNDS:
                # 超过最大轮次，汇总已有信息直接开始
                merged = self._merge_rounds(previous_result, user_input)
                merged.is_clear_enough = True
                return merged

        # 构建提示
        if previous_result is not None and previous_result.follow_up_questions:
            system_prompt = self.CLARIFICATION_FOLLOWUP_PROMPT.format(
                round_number=round_count,
                previous_questions="\n".join(f"- {q}" for q in previous_result.follow_up_questions),
                user_answer=user_input
            )
            user_message = user_input
        else:
            system_prompt = self.CLARIFICATION_SYSTEM_PROMPT
            user_message = f"用户输入：{user_input}"

        result = self._call_llm(system_prompt, user_message)

        # 构建对话历史
        conversation_history = []
        if previous_result:
            conversation_history = list(previous_result.conversation_history)
        conversation_history.append({"role": "user", "content": user_input})
        if result.get("follow_up_questions"):
            conversation_history.append({
                "role": "assistant",
                "content": result["follow_up_questions"]
            })

        return ClarificationResult(
            clarity_score=result["clarity_score"],
            is_clear_enough=result["is_clear_enough"],
            research_scope_summary=result["research_scope_summary"],
            dimensions=result["dimensions"],
            missing_dimensions=result["missing_dimensions"],
            follow_up_questions=result["follow_up_questions"],
            refined_query=result.get("refined_query", user_input.strip()),
            round_count=round_count,
            conversation_history=conversation_history
        )

    def _merge_rounds(
        self,
        previous: 'ClarificationResult',
        current_answer: str
    ) -> ClarificationResult:
        """合并多轮追问的信息"""
        merged_query = f"{previous.refined_query} {current_answer}".strip()
        return ClarificationResult(
            clarity_score=max(previous.clarity_score + 0.1, 0.7),
            is_clear_enough=True,
            research_scope_summary=previous.research_scope_summary,
            refined_query=merged_query,
            round_count=previous.round_count + 1,
            conversation_history=list(previous.conversation_history) + [
                {"role": "user", "content": current_answer}
            ]
        )

    def build_research_profile(self, result: ClarificationResult) -> str:
        """将评估结果构建为可读的研究画像文本，可注入到搜索 prompt 中"""
        parts = [f"## 研究画像\n\n{result.research_scope_summary}\n"]

        specified = [d for d in result.dimensions if d.get("is_specified")]
        if specified:
            parts.append("### 已明确的维度\n")
            for d in specified:
                parts.append(f"- **{d.get('label_zh', d.get('dimension', ''))}**: {d.get('what_is_known', '')}\n")

        parts.append(f"\n### 检索关键词\n{result.refined_query}")
        return "".join(parts)


# ==================== 便捷函数 ====================

def clarify_intent(
    user_input: str,
    previous_result: Optional[ClarificationResult] = None
) -> ClarificationResult:
    """意图明确化入口"""
    agent = IntentClarifier()
    return agent.assess(user_input, previous_result)


def is_broad_input(text: str) -> bool:
    """快速检查是否为笼统输入（无需 LLM 的轻量判断）"""
    import re
    stripped = text.strip()
    # 中文字符计数（排除英文/数字/空格/标点）
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', stripped))
    # 英文单词计数
    english_words = len(re.findall(r'[a-zA-Z]+', stripped))
    total_tokens = chinese_chars + english_words

    # 信息量太少 → 笼统
    if total_tokens <= 3:
        return True
    # 纯领域名无修饰（中英文）
    broad_patterns = [
        "研究癌症", "研究ai", "研究糖尿病", "cancer research", "cancer",
        "机器学习", "深度学习", "生物信息", "基因编辑", "阿尔茨海默", "阿尔茨海默病",
        "drug discovery", "machine learning", "ai", "糖尿病", "癌症",
    ]
    if stripped.lower() in [p.lower() for p in broad_patterns]:
        return True
    return False
