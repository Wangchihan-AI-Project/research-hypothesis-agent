# -*- coding: utf-8 -*-
"""
ReAct 工具调用模块 (ReAct Tool-Use Module)

为首席科学家智能体提供实时联网查证能力。

核心功能：
1. 封装 PubMed 检索为标准工具（search_pubmed）
2. 支持工具调用协议（Claude Tool Use / Function Calling）
3. 实现 ReAct (思考-行动-观察) 循环
"""

from typing import Dict, List, Optional, Any, Callable
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


# ==============================================================================
# 工具定义 (Tool Definitions)
# ==============================================================================

SEARCH_PUBMED_TOOL = {
    "name": "search_pubmed",
    "description": """检索 PubMed 生物医学文献数据库。

使用场景：
- 开题前��检索：在构思核心科学假说前，检索相关领域的最新研究
- 参数级查证：查找具体算法、参数、阈值在真实文献中的使用情况
- 铁血查重：检索近3年数据，检测核心假说是否存在高度同质化研究

参数说明：
- query: 检索查询字符串，支持布尔运算符（AND, OR, NOT）
- max_results: 最大返回结果数（默认5，最多20）
- year_start: 起始年份（默认2020，获取最新文献）
- year_end: 结束年份（默认当前年份）

返回结果：
- 每篇论文包含：pmid, title, abstract, journal, publication_date
""",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "PubMed检索查询字符串，例如：'ADNI AND hippocampus AND causal inference'"
            },
            "max_results": {
                "type": "integer",
                "description": "最大返回结果数（1-20）",
                "default": 5,
                "minimum": 1,
                "maximum": 20
            },
            "year_start": {
                "type": "integer",
                "description": "起始年份",
                "default": 2020
            },
            "year_end": {
                "type": "integer",
                "description": "结束年份（留空使用当前年份）"
            }
        },
        "required": ["query"]
    }
}


# ==============================================================================
# ReAct 执行器
# ==============================================================================

class ReActExecutor:
    """
    ReAct (Reasoning + Acting) 执行器

    实现"思考-行动-观察"循环，让大模型能够：
    1. 思考需要什么信息
    2. 调用工具获取信息
    3. 庺于观察结果继续思考

    V4.0 新增：动态深度评估机制
    - 阶梯式指令压力：3次后可申请补时，4次后强制输出
    - 联动红方审计：记录补时申请，供 RedTeamAgent 批评
    - 反馈循环保护：单次精简为整体效率
    """

    # 阶梯式压力阈值
    TIER1_THRESHOLD = 3  # 第1级压力：可以申请补时
    TIER2_THRESHOLD = 4  # 第2级压力：绝对强制输出

    def __init__(self, client, model: str, tools: List[Dict], tool_implementations: Dict[str, Callable]):
        """
        初始化 ReAct 执行器

        Args:
            client: Anthropic 客户端
            model: 模型名称
            tools: 工具定义列表
            tool_implementations: 工具实现函数字典 {tool_name: function}
        """
        self.client = client
        self.model = model
        self.tools = tools
        self.tool_implementations = tool_implementations
        self.max_iterations = 8  # 允许更多轮次（阶梯式压力控制）
        self.consecutive_failures = 0  # 连续失败计数
        self.max_consecutive_failures = 5  # 最大连续失败次数
        self.successful_searches = 0  # 成功检索计数
        self.logger = logger

        # ==================== V4.0 动态深度评估状态 ====================
        self.requested_extra_search = False  # 是否申请了第4轮补时
        self.extra_search_reason = None  # 补时申请理由（从Thought中提取）
        self.search_tier = 0  # 当前压力层级（0=自由, 1=可申请补时, 2=强制输出）
        self.search_audit_log = []  # 检索审计日志（供红方审计）

    def execute(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> Dict:
        """
        执行 ReAct 循环（V4.0 动态深度评估版）

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数

        Returns:
            {
                'success': bool,
                'final_response': str,  # 最终文本响应
                'tool_calls': List[Dict],  # 所有工具调用记录
                'iterations': int,  # 迭代次数
                'audit_info': Dict,  # V4.0 审计信息（供红方审计）
            }
        """
        messages = [
            {"role": "user", "content": user_prompt}
        ]

        tool_calls = []
        iteration = 0
        self.consecutive_failures = 0  # 重置连续失败计数
        self.successful_searches = 0  # 重置成功检索计数
        self.requested_extra_search = False  # 重置补时申请标记
        self.extra_search_reason = None  # 重置补时理由
        self.search_tier = 0  # 重置压力层级
        self.search_audit_log = []  # 重置审计日志

        self.logger.info(f"[ReAct] 开始执行循环（V4.0 动态深度评估模式）...")
        self.logger.info(f"[ReAct] 注册工具: {[t['name'] for t in self.tools]}")
        self.logger.info(f"[ReAct] 最大迭代次数: {self.max_iterations}")
        self.logger.info(f"[ReAct] 阶梯式压力阈值: TIER1={self.TIER1_THRESHOLD}, TIER2={self.TIER2_THRESHOLD}")

        # ==================== 透明化追踪：实时打印到控制台 ====================
        print("\n" + "="*60)
        print("🔬 [ReAct 思考链追踪] 首席科学家正在思考...")
        print("📊 [动态深度评估] 阶梯式压力机制已激活")
        print("="*60)
        # ====================================================================

        while iteration < self.max_iterations:
            iteration += 1
            self.logger.info(f"[ReAct] === 第 {iteration} 轮 ===")

            # ==================== 透明化追踪：轮次分隔 ====================
            print(f"\n┌──────────────────────────────────────────────────────────┐")
            print(f"│  🧠 第 {iteration} 轮思考 - 首席科学家                                          │")
            print(f"│  📚 成功检索次数: {self.successful_searches} (压力层级: T{self.search_tier})           │")
            print(f"└──────────────────────────────────────────────────────────┘")
            # ====================================================================

            # ==================== V4.0 阶梯式指令压力注入 ====================
            tier_message = self._inject_tiered_pressure()
            if tier_message:
                messages.append({
                    "role": "user",
                    "content": tier_message
                })

            # 检查连续失败次数，如果过多则注入提示让模型生成最终输出
            if self.consecutive_failures >= self.max_consecutive_failures:
                self.logger.warning(f"[ReAct] 连续失败 {self.consecutive_failures} 次，提示模型生成最终输出")
                print(f"\n   ⚠️  检索连续失败 {self.consecutive_failures} 次，转为直接输出模式")
                messages.append({
                    "role": "user",
                    "content": """
【重要提示】检索工具多次未能找到相关文献。这可能是因为：
1. 查询关键词过于具体或前沿
2. 该领域确实是研究空白

请根据您已有的领域知识和文献背景，直接生成研究假设。不要继续调用检索工具。
"""
                })
                self.consecutive_failures = 0  # 重置计数

            try:
                # 调用 LLM
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=8000,
                    temperature=temperature,
                    system=system_prompt,
                    messages=messages,
                    tools=self.tools
                )

                # 处理响应
                stop_reason = response.stop_reason
                content_blocks = []
                has_tool_use = False

                for block in response.content:
                    if block.type == "text":
                        content_blocks.append(block.text)
                        self.logger.info(f"[ReAct] 文本响应: {block.text[:100]}...")

                        # ==================== 透明化追踪：Thought ====================
                        # 提取思考内容（如果包含 Thought 或 思考）
                        thought_content = block.text[:300] if len(block.text) > 300 else block.text
                        print(f"\n   💭 Thought (思考):")
                        print(f"   {thought_content}")
                        if len(block.text) > 300:
                            print(f"   ...[内容过长，截取前300字]")
                        # ==============================================================

                    elif block.type == "tool_use":
                        has_tool_use = True
                        tool_id = block.id
                        tool_name = block.name
                        tool_input = block.input

                        self.logger.info(f"[ReAct] 工具调用: {tool_name}({tool_input})")

                        # ==================== 透明化追踪：Action ====================
                        print(f"\n   🎬 Action (行动):")
                        print(f"   调用工具: {tool_name}")
                        print(f"   参数: {json.dumps(tool_input, ensure_ascii=False, indent=6)}")
                        # ==============================================================

                        # 执行工具
                        tool_result = self._execute_tool(tool_name, tool_input)

                        # ==================== 透明化追踪：Observation ====================
                        print(f"\n   👁️  Observation (观察):")
                        if len(tool_result) > 400:
                            print(f"   {tool_result[:400]}...")
                            print(f"   [结果过长，截取前400字，共{len(tool_result)}字]")
                        else:
                            print(f"   {tool_result}")
                        # ==============================================================

                        # 检查是否成功（结果中包含"未找到"说明失败）
                        if "未找到相关文献" in tool_result or "检索结果说明" in tool_result:
                            self.consecutive_failures += 1
                            self.logger.warning(f"[ReAct] 工具调用未返回结果，连续失败: {self.consecutive_failures}")
                            print(f"\n   ⚠️  检索无结果 → 触发降维策略（下次减少关键词）")

                            # 记录失败审计日志
                            self.search_audit_log.append({
                                'iteration': iteration,
                                'query': tool_input.get('query', 'N/A'),
                                'success': False,
                                'reason': '未找到相关文献'
                            })
                        else:
                            self.consecutive_failures = 0  # 成功则重置
                            self.successful_searches += 1  # 成功检索计数

                            # 更新压力层级
                            if self.successful_searches >= self.TIER2_THRESHOLD:
                                self.search_tier = 2
                            elif self.successful_searches >= self.TIER1_THRESHOLD:
                                self.search_tier = 1

                            print(f"\n   ✅ 成功检索 #{self.successful_searches}")
                            print(f"   📊 压力层级: T{self.search_tier}")

                            # 记录成功审计日志
                            self.search_audit_log.append({
                                'iteration': iteration,
                                'query': tool_input.get('query', 'N/A'),
                                'success': True,
                                'tier_after': self.search_tier
                            })

                        # 记录工具调用
                        tool_calls.append({
                            'iteration': iteration,
                            'tool_name': tool_name,
                            'input': tool_input,
                            'result': tool_result[:500] if tool_result else ""  # 只保存前500字符
                        })

                        # 添加工具结果到消息历史
                        messages.append({
                            "role": "assistant",
                            "content": [{"type": "tool_use", "id": tool_id, "name": tool_name, "input": tool_input}]
                        })
                        messages.append({
                            "role": "user",
                            "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": tool_result}]
                        })

                # 如果停止，返回最终响应
                if stop_reason == "end_turn" or stop_reason == "stop_sequence":
                    final_text = "\n".join(content_blocks)
                    self.logger.info(f"[ReAct] 循环正常结束，共 {iteration} 轮，{len(tool_calls)} 次工具调用")

                    # ==================== V4.0 检测补时申请并解析理由 ====================
                    self._detect_extra_search_request(final_text)

                    # ==================== 透明化追踪：完成总结 ====================
                    print(f"\n" + "="*60)
                    print(f"✅ [ReAct 思考链完成]")
                    print(f"   总轮次: {iteration} 轮")
                    print(f"   工具调用: {len(tool_calls)} 次")
                    print(f"   成功检索: {self.successful_searches} 次")
                    print(f"   申请补时: {'是' if self.requested_extra_search else '否'}")
                    if self.requested_extra_search:
                        print(f"   补时理由: {self.extra_search_reason}")
                    print(f"="*60)
                    # ==============================================================

                    return {
                        'success': True,
                        'final_response': final_text,
                        'tool_calls': tool_calls,
                        'iterations': iteration,
                        'audit_info': self._build_audit_info()
                    }

                # 如果本轮没有工具调用且有文本内容，可能是模型决定直接输出
                if not has_tool_use and content_blocks:
                    final_text = "\n".join(content_blocks)
                    self.logger.info(f"[ReAct] 模型选择直接输出，共 {iteration} 轮")

                    # ==================== V4.0 检测补时申请并解析理由 ====================
                    self._detect_extra_search_request(final_text)

                    # ==================== 透明化追踪：直接输出 ====================
                    print(f"\n" + "="*60)
                    print(f"✅ [ReAct 直接输出模式]")
                    print(f"   首席科学家跳过工具调用，直接输出假设")
                    print(f"   成功检索: {self.successful_searches} 次")
                    print(f"   申请补时: {'是' if self.requested_extra_search else '否'}")
                    print(f"="*60)
                    # ==============================================================

                    return {
                        'success': True,
                        'final_response': final_text,
                        'tool_calls': tool_calls,
                        'iterations': iteration,
                        'audit_info': self._build_audit_info()
                    }

            except Exception as e:
                self.logger.error(f"[ReAct] 执行异常: {e}")

                # ==================== 透明化追踪：异常 ====================
                print(f"\n" + "="*60)
                print(f"❌ [ReAct 异常中断]")
                print(f"   错误: {e}")
                print(f"="*60)
                # ==============================================================

                return {
                    'success': False,
                    'error': str(e),
                    'tool_calls': tool_calls,
                    'iterations': iteration,
                    'audit_info': self._build_audit_info()
                }

        # 达到最大迭代次数
        self.logger.warning(f"[ReAct] 达到最大迭代次数 ({self.max_iterations})")

        # ==================== 透明化追踪：超时 ====================
        print(f"\n" + "="*60)
        print(f"⚠️  [ReAct 达到最大迭代次数]")
        print(f"   已执行 {self.max_iterations} 轮，强制终止")
        print(f"   成功检索: {self.successful_searches} 次")
        print(f"="*60)
        # ==============================================================

        return {
            'success': False,
            'error': '达到最大迭代次数',
            'tool_calls': tool_calls,
            'iterations': iteration,
            'audit_info': self._build_audit_info()
        }

    # ==============================================================================
    # V4.0 动态深度评估辅助方法
    # ==============================================================================

    def _inject_tiered_pressure(self) -> Optional[str]:
        """
        阶梯式指令压力注入

        根据成功检索次数注入不同的压力提示：
        - TIER1 (3次): 可申请补时，但需说明理由
        - TIER2 (4次): 绝对强制输出

        Returns:
            压力提示消息（如果需要注入），或 None（如果不需要）
        """
        # TIER2: 绝对强制输出
        if self.successful_searches >= self.TIER2_THRESHOLD:
            self.search_tier = 2
            self.logger.info(f"[ReAct] TIER2 压力注入: 强制输出")

            print(f"\n   🔴 [TIER2 压力] 检索权限已耗尽，强制输出")
            print(f"   → 必须立即基于现有证据生成假设")

            return """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    【检索权限耗尽 - 绝对强制输出】                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

你已经成功完成了 4 次文献检索。检索权限已完全耗尽。

【绝对禁令】：
- 禁止继续调用 search_pubmed 工具
- 禁止进行任何新的检索行动
- 必须立即基于你已收集的 4 份证据进行最终假设合成

【强制任务】：
1. 综合你收集的所有文献证据
2. 进行反事实推演，构建因果链路
3. 立即输出完整的假设 JSON（包含七段式详细内容）

如果你此时继续调用检索工具，系统将直接报错终止。
"""

        # TIER1: 可申请补时
        if self.successful_searches == self.TIER1_THRESHOLD and self.search_tier < 1:
            self.search_tier = 1
            self.logger.info(f"[ReAct] TIER1 压力注入: 可申请补时")

            print(f"\n   🟡 [TIER1 压力] 已获取 3 份核心证据")
            print(f"   → 可申请第 4 轮补时，但需在 Thought 中明确说明理由")

            return """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    【证据收集评估 - 补时申请窗口】                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

你已成功完成了 3 次文献检索，掌握了 3 份核心证据。

【默认规则】：原则上，你应该立即进入假设合成模式。

【补时申请窗口】：
如果你认为目前的证据链仍存在 **致命缺环**，你可以申请最后一轮（第 4 轮）定向检索。

【申请条件】（必须全部满足）：
- 你的 Thought 中必须明确说明："申请第 4 轮检索"
- 你必须明确指出：第 4 轮检索将解决哪个 **具体的因果逻辑断裂**
- 你必须说明：为什么当前 3 份证据无法填补这个断裂

【格式示例】：
```
Thought: 基于目前3份证据，我发现核心因果链路中缺失了一个关键环节：
[具体的逻辑断裂描述]
因此申请第4轮检索来解决这一问题。
检索目标: [具体的检索关键词]
预期填补: [预期获得的证据类型]
```

【警告】：
- 如果你申请了第 4 轮检索，但最终报告中并未体现出质变提升，
  RedTeamAgent 将在审计时对你的"冗余调研"进行严厉批评
- 外层反馈循环会在假设被判定为"证据不足"时自动开启下一轮迭代，
  单次精简是为了整体效率

你可以选择：
A) 立即进入假设合成模式（推荐）
B) 申请第 4 轮补时（需满足上述条件）
"""

        return None

    def _detect_extra_search_request(self, text: str) -> None:
        """
        检测补时申请并解析理由

        Args:
            text: 模型输出的文本（Thought 或最终输出）
        """
        # 检测补时申请关键词
        extra_search_keywords = [
            "申请第4轮检索",
            "申请第 4 轮检索",
            "申请第四轮检索",
            "申请最后一轮检索",
            "申请补时检索",
            "需要额外检索",
            "证据链存在缺环"
        ]

        # 检查是否在 TIER1 状态下申请了补时
        if self.search_tier == 1 and self.successful_searches == self.TIER1_THRESHOLD:
            for keyword in extra_search_keywords:
                if keyword in text:
                    self.requested_extra_search = True
                    self.logger.info(f"[ReAct] 检测到补时申请: '{keyword}'")

                    # 尝试解析补时理由
                    self.extra_search_reason = self._parse_extra_search_reason(text)
                    print(f"\n   📝 补时申请已记录")
                    print(f"   理由: {self.extra_search_reason}")

                    return

        # 如果已经进入了 TIER2 但还标记着补时申请，更新状态
        if self.search_tier == 2 and self.requested_extra_search:
            self.logger.info(f"[ReAct] 补时申请已执行，进入 TIER2 强制输出")

    def _parse_extra_search_reason(self, text: str) -> str:
        """
        解析补时申请理由

        Args:
            text: 包含补时申请的文本

        Returns:
            提取的补时理由
        """
        # 尝试提取理由描述
        patterns = [
            # 模式1: "证据链中缺失了..." 或 "因果逻辑断裂..."
            r"(?:证据链|因果链路|逻辑断裂|关键环节|致命缺环)[中存在]?缺失[了]?[:：]?\s*([^\n。]{10,100})",
            # 模式2: "检索目标: ..." 或 "预期填补: ..."
            r"检索目标[:：]\s*([^\n]{5,50})",
            r"预期填补[:：]\s*([^\n]{5,50})",
            # 模式3: "解决..." 或 "填补..."
            r"解决\s*([^\n。]{5,50})",
            r"填补\s*([^\n。]{5,50})"
        ]

        import re
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        # 如果无法解析，返回默认描述
        return "申请人认为当前证据链存在关键缺环（具体理由未明确表述）"

    def _build_audit_info(self) -> Dict:
        """
        构建审计信息（供 RedTeamAgent 使用）

        Returns:
            {
                'successful_searches': int,
                'search_tier': int,
                'requested_extra_search': bool,
                'extra_search_reason': str or None,
                'search_audit_log': List[Dict],
                'tier_transitions': List[str],  # 压力层级转换记录
                'efficiency_score': float,  # 效率评分（供红方审计）
            }
        """
        # 计算效率评分
        # 基础效率 = 成功检索数 / 总迭代次数
        base_efficiency = self.successful_searches / max(1, len(self.search_audit_log))

        # 补时惩罚：如果申请了补时但没有带来明显价值，降低效率评分
        efficiency_penalty = 0.0
        if self.requested_extra_search:
            # 如果申请了补时（意味着检索了4次而非3次），效率略有下降
            efficiency_penalty = 0.1
            # 如果申请了补时但理由不明确，进一步惩罚
            if self.extra_search_reason and "未明确表述" in self.extra_search_reason:
                efficiency_penalty = 0.2

        efficiency_score = max(0, min(1, base_efficiency - efficiency_penalty))

        # 构建层级转换记录
        tier_transitions = []
        for log in self.search_audit_log:
            if log.get('success') and log.get('tier_after'):
                tier = log.get('tier_after')
                if tier > 0 and (len(tier_transitions) == 0 or tier_transitions[-1] != f"T{tier}"):
                    tier_transitions.append(f"T{tier}")

        return {
            'successful_searches': self.successful_searches,
            'search_tier': self.search_tier,
            'requested_extra_search': self.requested_extra_search,
            'extra_search_reason': self.extra_search_reason,
            'search_audit_log': self.search_audit_log,
            'tier_transitions': tier_transitions,
            'efficiency_score': efficiency_score,
            'audit_summary': self._generate_audit_summary(efficiency_score)
        }

    def _generate_audit_summary(self, efficiency_score: float) -> str:
        """
        生成审计摘要（供红方审计直接引用）

        Args:
            efficiency_score: 效率评分（由 _build_audit_info 计算并传入）

        Returns:
            审计摘要文本
        """
        if self.requested_extra_search:
            return f"""
[补时审计标记]
- 成功检索次数: {self.successful_searches} 次（超出默认阈值 {self.TIER1_THRESHOLD} 次）
- 申请了第 4 轮补时检索
- 补时理由: {self.extra_search_reason}
- 效率评分: {efficiency_score:.2f}

【红方审计要点】：
如果最终假设质量并未因第 4 轮检索产生质变提升，应对"冗余调研"进行批评。
建议检查：补时检索是否真的解决了申请人声称的因果逻辑断裂？
"""
        else:
            return f"""
[标准检索流程]
- 成功检索次数: {self.successful_searches} 次
- 压力层级: T{self.search_tier}
- 效率评分: {efficiency_score:.2f}
- 未申请补时，符合标准效率要求
"""

    def _execute_tool(self, tool_name: str, tool_input: Dict) -> str:
        """执行工具调用"""
        if tool_name not in self.tool_implementations:
            return f"错误：未知工具 '{tool_name}'"

        try:
            tool_func = self.tool_implementations[tool_name]

            # 如果是异步函数，需要在事件循环中运行
            if asyncio.iscoroutinefunction(tool_func):
                result = asyncio.run(tool_func(**tool_input))
            else:
                result = tool_func(**tool_input)

            # 格式化结果
            if isinstance(result, str):
                return result
            elif isinstance(result, list):
                # 格式化论文列表
                formatted = []
                for i, paper in enumerate(result[:10], 1):
                    formatted.append(f"【论文 {i}】")
                    formatted.append(f"PMID: {paper.get('pmid', 'N/A')}")
                    formatted.append(f"标题: {paper.get('title', 'N/A')}")
                    formatted.append(f"期刊: {paper.get('journal', 'N/A')}")
                    formatted.append(f"日期: {paper.get('publication_date', 'N/A')}")
                    formatted.append(f"摘要: {paper.get('abstract', 'N/A')[:500]}...")
                    formatted.append("")
                return "\n".join(formatted)
            else:
                return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            error_msg = f"工具执行失败: {str(e)}"
            self.logger.error(f"[ReAct] {error_msg}")
            return error_msg


# ==============================================================================
# 工具实现模板
# ==============================================================================

def create_pubmed_tool_implementation(pubmed_searcher) -> Callable:
    """
    创建 PubMed 工具实现（带智能回退机制）

    Args:
        pubmed_searcher: PubMedSearcher 实例

    Returns:
        工具实现函数
    """
    def search_pubmed(
        query: str,
        max_results: int = 5,
        year_start: int = 2020,
        year_end: Optional[int] = None
    ) -> str:
        """
        检索 PubMed 文献（带智能回退）

        回退策略：
        1. 如果指定日期范围无结果，自动扩大到近10年
        2. 如果复杂查询无结果，自动简化关键词
        3. 如果仍无结果，返回友好的提示信息
        """
        if year_end is None:
            year_end = datetime.now().year

        original_date_range = (year_start, year_end)
        original_query = query

        logger.info(f"[PubMed工具] 查询: {query}")
        logger.info(f"[PubMed工具] 原始参数: max_results={max_results}, date_range={original_date_range}")

        # ========== 策略1: 原始查询 ==========
        try:
            papers = pubmed_searcher.search_papers(
                query=query,
                max_results=max_results,
                date_range=original_date_range,
                enable_filter=False
            )

            if papers:
                logger.info(f"[PubMed工具] 检索成功: {len(papers)} 篇文献")
                return _format_papers_for_llm(papers)
            else:
                logger.warning(f"[PubMed工具] 原始查询无结果，尝试回退策略...")

        except Exception as e:
            logger.warning(f"[PubMed工具] 原始查询失败: {e}，尝试回退策略...")

        # ========== 策略2: 扩大日期范围（近10年）==========
        try:
            expanded_range = (2015, datetime.now().year)
            logger.info(f"[PubMed工具] 回退策略1: 扩大日期范围至 {expanded_range}")

            papers = pubmed_searcher.search_papers(
                query=query,
                max_results=max_results,
                date_range=expanded_range,
                enable_filter=False
            )

            if papers:
                logger.info(f"[PubMed工具] 回退成功: {len(papers)} 篇文献（扩大日期范围）")
                return _format_papers_for_llm(papers) + "\n\n[注: 由于指定日期范围无结果，已扩大检索范围至2015年至今]"

        except Exception as e:
            logger.warning(f"[PubMed工具] 回退策略1失败: {e}")

        # ========== 策略3: 简化查询（提取核心关键词）==========
        try:
            # 简化查询：只保留第一个关键词
            simplified_query = query.split()[0] if query else query
            logger.info(f"[PubMed工具] 回退策略2: 简化查询至 '{simplified_query}'")

            papers = pubmed_searcher.search_papers(
                query=simplified_query,
                max_results=max_results,
                date_range=(2015, datetime.now().year),
                enable_filter=False
            )

            if papers:
                logger.info(f"[PubMed工具] 回退成功: {len(papers)} 篇文献（简化查询）")
                return _format_papers_for_llm(papers) + "\n\n[注: 由于原始查询无结果，已使用简化关键词检索]"

        except Exception as e:
            logger.warning(f"[PubMed工具] 回退策略2失败: {e}")

        # ========== 所有策略都失败，返回友好提示 ==========
        logger.error(f"[PubMed工具] 所有检索策略均失败")
        return f"""检索结果说明：针对查询 "{original_query}" 在指定日期范围 {original_date_range} 内未找到直接相关的文献。

建议：
1. 尝试更通用的关键词（如用 "Alzheimer" 代替 "pQTL cerebrospinal fluid Alzheimer causal mediation"）
2. 扩大日期范围（如检索近10年的文献）
3. 检查拼写或使用同义词

您可以继续基于领域知识生成假设，系统会在后续评分环节进行查重验证。
"""

    return search_pubmed


def _format_papers_for_llm(papers: List[Dict]) -> str:
    """格式化论文列表供 LLM 阅读"""
    if not papers:
        return "未找到相关文献。"

    result_parts = [f"检索到 {len(papers)} 篇相关文献：\n"]

    for i, paper in enumerate(papers[:10], 1):  # 最多显示10篇
        title = paper.get('title', 'N/A')
        journal = paper.get('journal', 'N/A')
        pub_date = paper.get('publication_date', 'N/A')
        abstract = paper.get('abstract', 'N/A')[:400]

        result_parts.append(f"""【文献 {i}】
标题: {title}
期刊: {journal}
发表日期: {pub_date}
摘要: {abstract}...
""")

    return "\n".join(result_parts)


# ==============================================================================
# 查证钢印（追加到系统提示词）
# ==============================================================================

VERIFICATION_STEEL_IMPRINT = """

---

## 【强制工具调用协议】(Mandatory Tool-Use Protocol)

你现在拥有一个名为 `search_pubmed` 的底层检索工具。你不再是一个"闭卷"思考的 AI，而是一个必须做到"字字有出处"的严谨学者。在执行任务期间，你必须严格遵循以下"ReAct (思考-行动-观察)"序列：

### 1. 开题前置检索 (Evidence Gathering)

在构思【核心科学假说】前，你必须主动调用 `search_pubmed`，输入你初步构思的机制关键词（如 "ADNI AND 慢波睡眠 AND 因果推断"），拉取近 3 年的至少 5 篇顶刊摘要。

**要求**：
- 你的假说必须建立在这些真实文献的盲区之上
- 在【底层逻辑与反事实推演】中明确写出参考依据
- 引用格式：`"根据最新文献 PMID:XXXXXX 的发现..."` 或 `"基于 Smith et al. (2024) 的研究..."`

### 2. 参数级查证 (Parameter Grounding)

在【详尽技术路线】中，严禁脑补参数。如果不确定具体的算法包或阈值，必须立刻调用检索工具。

**示例**：
- 不确定 Bootstrap 抽样次数？→ 检索 "mediation analysis bootstrap sims"
- 不确定混合效应模型的协方差结构？→ 检索 "linear mixed model covariance structure adni"
- 不确定 FDR 校正方法？→ 检索 "false discovery rate correction neuroimaging"

### 3. 铁血查重与评分 (Falsification & Scoring)

在生成最终的 `scores` 之前，你必须执行"动态碰撞检测"：

**检测流程**：
1. 提取你的核心假说关键词（如 "ADNI hippocampus causal mediation"）
2. 调用 `search_pubmed` 搜索近 3 年的数据
3. 分析检索结果

**评分规则**：
- **致命碰撞**：如果搜到了高度同质化的研究（研究目标、方法、数据集完全一致），你的 `methodological_originality` 必须强制打低于 4 分，并在 `novelty` 说明中发出红色预警
- **部分重叠**：如果存在相似研究但你的方法有显著差异，`novelty` 可给 6-7 分
- **真实支撑**：你的每一项打分（尤其是可行性和新颖性）都必须基于 PubMed 的检索结果来计算

**评分输出格式**：
```json
"scores": {
  "novelty": 8.5,
  "rigor": 9.0,
  "impact": 8.0,
  "overall": 8.5,
  "evidence": {
    "pubmed_queries": ["查询1", "查询2"],
    "collision_detected": false,
    "supporting_papers": ["PMID:1", "PMID:2"]
  }
}
```

---

## 【强制 PubMed 检索操作规范】(Search Tool Protocol)

当你调用 `search_pubmed` 检索工具时，你必须像一个真实的人类科研工作者一样使用关键词，**绝对禁止**以下愚蠢的检索行为：

### ❌ 严禁查询词过载

每次搜索的 `query` 最多只能包含 **2-3 个核心关键词**。

**正确示例**：
- `query="Alzheimer pQTL"`
- `query="proteomics causal mediation"`
- `query="hippocampus atrophy MRI"`

**错误示例**（禁止）：
- `query="pQTL cerebrospinal fluid Alzheimer causal mediation 2022-2024"`
- `query="brain proteome Mendelian randomization neurodegeneration longitudinal"`

### ❌ 严禁在 Query 中带入年份

绝对不要在文本查询词中输入 "2022-2024"、"recent"、"last 5 years" 等时间词汇！年份限制由工具的后台参数（`year_start`, `year_end`）处理。

**正确示例**：
```python
search_pubmed(query="Alzheimer hippocampus", year_start=2020, year_end=2024)
```

**错误示例**（禁止）：
```python
search_pubmed(query="Alzheimer hippocampus 2022-2024 recent")
```

### ⚠️ 降级搜索策略

如果第一次调用工具返回了"未找到文献"，你在下一次思考时，**必须减少查询词的数量**，把检索范围放宽，直到找到真实文献为止。

**降级流程**：
```
第1次: "Alzheimer pQTL cerebrospinal fluid causal"  (4个词)
  ↓ 未找到
第2次: "Alzheimer pQTL cerebrospinal"  (3个词)
  ↓ 未找到
第3次: "Alzheimer pQTL"  (2个词)
  ↓ 找到了！
```

---

## 【工具调用示例】

**场景：生成 ADNI 相关假设**

```
思考：我需要了解 ADNI 数据集中海马体积与认知衰退关系的最新研究
行动：调用 search_pubmed(query="ADNI hippocampus volume cognitive decline causal", max_results=5)
观察：检索到 5 篇文献，其中 3 篇使用线性混合模型，2 篇使用中介分析
思考：我发现现有研究主要关注线性关系，缺少对非线性阈值效应的探索...
行动：继续检索 "threshold effect hippocampus cognitive decline"
观察：检索到关于非线性阈值效应的方法学文献
思考：好的，我现在可以提出一个基于阈值效应的因果中介假设...
```

---

**记住**：你不是在"写小说"，而是在"写基金申请书"。每一句话都必须有据可查。
"""
