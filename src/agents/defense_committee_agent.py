# -*- coding: utf-8 -*-
"""
V7.4-F 防御委员会智能体 (Defense Committee Agent)
人设：由资深专家组成的答辩委员会，根据红方攻击报告进行最终裁决

核心任务：
- 评估蓝方防御材料对红方攻击的抵御能力
- 根据攻击报告进行最终裁决
- 判断方案是否可以继续进入下游流程
- 提供需要修复的关键问题清单

V7.4-F 增强：
- 创新性权重维持 40%
- 引入物理公理锚定审查（35%权重）
- 拒绝科幻的正确逻辑：无法推导物理层面传感器逻辑
"""
from typing import Dict, List, Optional
import json
import sys
import os
import time
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import BaseAgent
from utils.llm_utils import SafeExtractor, LLMParseError
import anthropic


# 委员会成员角色
COMMITTEE_MEMBERS = {
    'chair': 'Nature资深编委（主席）',
    'methodology_expert': '方法论专家（统计学/计算机科学）',
    'domain_expert': '领域专家（生物学/医学）',
    'clinical_expert': '临床转化专家'
}

# 裁决标准
VERDICT_STANDARDS = {
    'defense_passed': {
        'description': '防守成功，方案可以继续',
        'criteria': [
            '无致命缺陷',
            '严重问题 ≤ 2个',
            '核心技术方案清晰可行',
            '数据支持基本充分'
        ]
    },
    'defense_failed': {
        'description': '防守失败，方案需要重大修改',
        'criteria': [
            '存在1个以上致命缺陷', 'OR',
            '严重问题 ≥ 3个', 'OR',
            '核心技术方案存在根本性缺陷', 'OR',
            '数据支持严重不足'
        ]
    },
    'conditional_pass': {
        'description': '有条件通过，需要修复指定问题后继续',
        'criteria': [
            '无致命缺陷',
            '严重问题 = 2个',
            '问题可以明确修复'
        ]
    }
}

# ==================== V7.4-F 新增：权重配置 ====================
# 创新性维持 40% 权重，物理可行性新增 35% 权重
INNOVATION_WEIGHTS = {
    'INNOVATION': 0.40,               # 创新性权重（核心权重，维持不变）
    'PHYSICAL_FEASIBILITY': 0.35,     # V7.4-F 新增：物理可行性权重
    'METHODOLOGY': 0.15,              # 方法论权重
    'LITERATURE_SUPPORT': 0.10,       # 文献支撑权重
}

# ==================== V7.4-G 新增：科学底线评分配置 ====================
# 针对经典/前沿课题，赋予底线评分，避免过度严苛拒绝
SCIENTIFIC_BASELINE_SCORES = {
    'UK_BIOBANK_ML': 0.85,        # UK Biobank + ML 类课题默认高分
    'STANDARD_PIPELINE': 0.75,   # 标准机器学习流程
    'NOVEL_BUT_FEASIBLE': 0.70,  # 新颖但可行
    'PROTEIN_STRUCTURE': 0.80,   # AlphaFold/蛋白结构预测
    'GENOMIC_ANALYSIS': 0.75,    # 基因组分析
}

# V7.4-G 新增：命题类型关键词识别
PROPOSAL_TYPE_PATTERNS = {
    'UK_BIOBANK_ML': ['uk biobank', 'xgboost', 'gradient boosting', 'risk prediction', 'diabetes', 'biobank'],
    'PROTEIN_STRUCTURE': ['alphafold', 'protein', 'mutation', 'binding', 'structure prediction', 'gnn'],
    'GENOMIC_ANALYSIS': ['gwas', 'genomic', 'sequencing', 'rna-seq', 'single cell', 'omics'],
}

# ==================== V7.4-F 新增：物理公理锚定审查协议 ====================
PHYSICAL_FEASIBILITY_PROTOCOL = """
### 🧪 【物理公理锚定审查协议】（V7.4-F 强制执行）

作为 DefenseCommittee 成员，你必须对每个假说执行以下物理可行性审查：

**1. 信号捕获审查 (Sensor/Signal)**
- 是否指定了物理传感器/探测器？（测序仪/光谱仪/电极/显微镜等）
- 传感器类型是否与测量目标匹配？
- 信号检测灵敏度是否在物理可实现范围内？

**拒绝逻辑**：
- 若假说声称"量子共振探测生物状态"，但无具体传感器 → 拒绝
- 若假说声称"意念影响物质"，无物理测量手段 → 拒绝

**2. 能量转换审查 (Thermodynamics)**
- 能量转换路径是否符合热力学定律？
- 是否给出能量转换效率的定量估计？
- 是否避免"无限能量"或"负熵"等伪科学主张？

**拒绝逻辑**：
- 若假说声称"永动机制治疗疾病" → 拒绝（违反能量守恒）
- 若假说声称"量子能量治愈"无能量来源 → 拒绝

**3. 效应度量审查 (Metrology)**
- 是否指定了可量化的生物/临床效应指标？（生存率/响应率/基因表达等��
- 效应指标是否可通过实验测量？
- 统计分析方法是否科学？

**拒绝逻辑**：
- 若假说声称"气场调理改善健康"，无量化指标 → 拒绝
- 若假说缺乏对照组设计 → 部分拒绝，要求补充

**4. 实验验证路径审查 (Experimental Path)**
- 是否给出可执行的实验设计方案？
- 样本量估计是否合理？
- 验证时间线是否现实？

**拒绝逻辑**：
- 若假说声称"无需实验验证，理论即真理" → 拒绝
- 若实验设计不可执行 → 要求修正
"""


class DefenseCommitteeAgent(BaseAgent):
    """
    防御委员会智能体

    取代原DebateCoordinator，作为红蓝对抗后的终审裁决机构
    """

    def __init__(self):
        super().__init__("防御委员会", agent_type="defense_committee")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.extractor = SafeExtractor()
        self.max_retries = 3

        # 从环境变量读取裁决标准
        self.critical_threshold = int(os.getenv('DEFENSE_CRITICAL_THRESHOLD', 1))
        self.severe_threshold = int(os.getenv('DEFENSE_SEVERE_THRESHOLD', 3))

    def _evaluate_physical_feasibility(self, hypothesis_data: dict) -> tuple:
        """
        V7.4-F 新增：物理可行性评分

        检查假说是否具备物理公理锚定：
        1. 信号捕获（传感器）
        2. 能量转换（热力学）
        3. 效应度量（量化指标）
        4. 实验验证路径

        Returns:
            Tuple[float, List[str]]: (评分, 缺失要素列表)
        """
        score = 0.0
        missing_elements = []

        # 提取假说文本
        hypothesis_text = ""
        if isinstance(hypothesis_data, dict):
            for key in ['hypothesis', 'title', 'abstract', 'methodology', 'details']:
                if hypothesis_data.get(key):
                    hypothesis_text += str(hypothesis_data[key]) + " "
        else:
            hypothesis_text = str(hypothesis_data)

        # 调用物理锚定检测器
        try:
            from src.core.pseudoscience_detector import PseudoscienceDetector
            detector = PseudoscienceDetector()
            result = detector.perform_physical_anchor_check(hypothesis_text)

            if result.passed:
                score = result.score if result.score > 0 else 0.7  # 有传感器默认 0.7
            else:
                # 根据缺失要素数量扣分
                missing_count = len(result.missing_elements)
                score = max(0.0, 1.0 - 0.25 * missing_count)
                missing_elements = result.missing_elements

                # 伪科学类型触发零分
                if result.pseudoscience_type:
                    score = 0.0
                    print(f"[V7.4-F] 检测到伪科学模式: {result.pseudoscience_type.value}")

        except ImportError:
            # 物理检测器不可用时，给予中性评分
            score = 0.5
            print("[V7.4-F] PseudoscienceDetector 不可用，使用中性评分")
        except Exception as e:
            score = 0.5
            print(f"[V7.4-F] 物理可行性检测异常: {e}")

        return score, missing_elements

    def _evaluate_scientific_baseline(self, hypothesis_text: str) -> float:
        """
        V7.4-G 新增：科学底线评分

        识别命题类型并赋予底线评分，避免合理课题被过度严苛拒绝

        Args:
            hypothesis_text: 假说文本

        Returns:
            float: 底线评分 (0.50 - 0.85)
        """
        baseline_score = 0.50  # 默认底线

        for proposal_type, keywords in PROPOSAL_TYPE_PATTERNS.items():
            if any(kw.lower() in hypothesis_text.lower() for kw in keywords):
                baseline_score = max(baseline_score, SCIENTIFIC_BASELINE_SCORES[proposal_type])
                print(f"[V7.4-G] 识别命题类型: {proposal_type}, 底线评分: {baseline_score}")
                break

        return baseline_score

    def execute(self, input_data: Dict) -> Dict:
        """
        执行防御委员会裁决

        V7.4-F 增强：引入物理可行性评分

        Args:
            input_data: {
                'blue_package': dict - 蓝方防御材料
                'red_attack': dict - 红方攻击报告
            }

        Returns:
            {
                'success': bool,
                'defense_passed': bool,      # 关键：防守是否通过
                'verdict': str,              # 裁决结论: 'passed/failed/conditional'
                'committee_response': str,   # 委员会回应
                'final_verdict': str,        # 最终裁决描述
                'critical_issues': [],       # 需要修复的关键问题
                'recommendations': [],       # 改进建议
                'physical_feasibility_score': float  # V7.4-F 新增
            }
        """
        blue_package = input_data.get('blue_package', {})
        red_attack = input_data.get('red_attack', {})

        if not blue_package:
            return {
                'success': False,
                'error': '缺少蓝方防御材料'
            }

        if not red_attack:
            return {
                'success': False,
                'error': '缺少红方攻击报告'
            }

        # ==================== V7.4-F 新增：物理可行性预检 ====================
        hypothesis_data = blue_package.get('hypothesis_data', {})
        physical_score, physical_issues = self._evaluate_physical_feasibility(hypothesis_data)

        print(f"[V7.4-F] 物理可行性评分: {physical_score:.2f}")

        # 物理可行性为 0 时直接拒绝（伪科学）
        if physical_score == 0.0:
            return {
                'success': True,
                'defense_passed': False,
                'verdict': 'failed',
                'committee_response': f"**委员会裁决：物理公理锚定失败**\n\n{physical_issues[0] if physical_issues else '检测到伪科学模式，缺乏可验证的物理传感器逻辑。'}",
                'final_verdict': 'FAILED - 物理公理锚定失败',
                'critical_issues': physical_issues,
                'recommendations': ['请补充具体的物理传感器（如：测序仪、光谱仪、电极）和可量化的效应指标'],
                'physical_feasibility_score': 0.0,
                'innovation_score': 0.0,
                'total_score': 0.0,
            }

        # ==================== V7.4-G 新增：科学底线评分 ====================
        # 提取假说文本用于识别命题类型
        hypothesis_text = ""
        if isinstance(hypothesis_data, dict):
            for key in ['hypothesis', 'title', 'abstract', 'methodology', 'details']:
                if hypothesis_data.get(key):
                    hypothesis_text += str(hypothesis_data[key]) + " "

        baseline_score = self._evaluate_scientific_baseline(hypothesis_text)

        # V7.4-G：底线评分 >= 0.70 时，调整阈值提高容错率
        if baseline_score >= 0.70 and physical_score > 0:
            original_threshold = self.severe_threshold
            self.severe_threshold = max(self.severe_threshold, 4)  # 允许最多4个严重问题
            print(f"[V7.4-G] 科学底线评分 {baseline_score:.2f} >= 0.70，调整阈值: {original_threshold} -> {self.severe_threshold}")

        # 执行委员会裁决
        verdict_result = self._conduct_committee_deliberation(blue_package, red_attack)

        # V7.4-F：将物理可行性评分添加到裁决结果
        verdict_result['physical_feasibility_score'] = physical_score
        # V7.4-G：将科学底线评分添加到裁决结果
        verdict_result['scientific_baseline_score'] = baseline_score
        if physical_issues:
            verdict_result['physical_issues'] = physical_issues

        return {
            'success': True,
            **verdict_result
        }

    def _conduct_committee_deliberation(self, blue_package: dict, red_attack: dict) -> dict:
        """
        进行委员会审议

        Args:
            blue_package: 蓝方防御材料
            red_attack: 红方攻击报告

        Returns:
            裁决结果
        """
        # 先进行快速裁决（基于攻击报告的定量分析）
        # V7.2: 传递 blue_package 以检查 technical_safeguards
        quick_verdict = self._quick_verdict(red_attack, blue_package)

        # 如果快速裁决结果明确，直接返回
        if quick_verdict['is_definitive']:
            return quick_verdict['result']

        # 否则进行深度审议
        return self._deep_deliberation(blue_package, red_attack)

    def _extract_technical_safeguards(self, blue_package: dict) -> List[str]:
        """提取技术防范措施"""
        if not blue_package:
            return []

        hypothesis_data = blue_package.get('hypothesis_data', {})
        methodology = hypothesis_data.get('methodology', {})
        if not isinstance(methodology, dict):
            return []

        safeguards = methodology.get('technical_safeguards', [])
        if isinstance(safeguards, list):
            return [str(item).strip() for item in safeguards if str(item).strip()]
        if safeguards:
            return [str(safeguards).strip()]
        return []

    def _summarize_issue_labels(self, issues: List[dict], limit: int = 3) -> str:
        """汇总问题标签"""
        labels = []
        for item in issues[:limit]:
            if not isinstance(item, dict):
                text = str(item).strip()
                if text:
                    labels.append(text)
                continue
            category = item.get('category') or item.get('type') or '问题'
            issue = item.get('issue') or item.get('reason') or ''
            labels.append(f"{category}: {issue}" if issue else str(category))
        return '；'.join(labels)

    def _build_attack_responses(
        self,
        red_attack: dict,
        technical_safeguards: List[str] = None,
        committee_response: str = "",
        recommendations: List[str] = None
    ) -> List[dict]:
        """构建按攻击类型组织的答辩要点"""
        technical_safeguards = technical_safeguards or []
        recommendations = recommendations or []
        attack_responses = []

        red_items = []
        for key in ['critical_flaws', 'severe_issues', 'moderate_concerns']:
            red_items.extend(red_attack.get(key, []) or [])

        for index, item in enumerate(red_items):
            if not isinstance(item, dict):
                text = str(item).strip()
                if text:
                    attack_responses.append({
                        'attack_type': text,
                        'issue': text,
                        'response': committee_response or '委员会认为该问题需要在后续版本中通过更具体的方法学补丁予以回应。'
                    })
                continue

            attack_type = item.get('category') or item.get('type') or f'问题{index + 1}'
            issue = item.get('issue') or item.get('reason') or item.get('details') or ''
            suggestion = item.get('suggestion') or ''
            safeguard = technical_safeguards[index] if index < len(technical_safeguards) else ''
            recommendation = recommendations[index] if index < len(recommendations) else ''

            response_parts = []
            if safeguard:
                response_parts.append(f"蓝方已提出对应措施：{safeguard}")
            elif committee_response:
                response_parts.append("委员会认为该问题已有初步回应，但仍需补充可审计证据")
            else:
                response_parts.append("委员会认为该问题尚未被充分化解，需要补充可执行修复路径")

            if suggestion:
                response_parts.append(f"红方建议优先处理：{suggestion}")
            if recommendation and recommendation != suggestion:
                response_parts.append(f"委员会补充建议：{recommendation}")

            attack_responses.append({
                'attack_type': str(attack_type),
                'issue': str(issue),
                'response': '；'.join(part for part in response_parts if part)
            })

        return attack_responses

    def _build_committee_discussion(self, red_attack: dict, technical_safeguards: List[str] = None) -> str:
        """构建委员会讨论摘要"""
        technical_safeguards = technical_safeguards or []
        critical_flaws = red_attack.get('critical_flaws', []) or []
        severe_issues = red_attack.get('severe_issues', []) or []
        moderate_concerns = red_attack.get('moderate_concerns', []) or []

        discussion_parts = [
            f"委员会首先确认红方共提出 {len(critical_flaws)} 个致命缺陷、{len(severe_issues)} 个严重问题和 {len(moderate_concerns)} 个中等疑虑。"
        ]

        critical_summary = self._summarize_issue_labels(critical_flaws)
        if critical_summary:
            discussion_parts.append(f"最核心的否决点集中在：{critical_summary}。")

        severe_summary = self._summarize_issue_labels(severe_issues)
        if severe_summary:
            discussion_parts.append(f"需要重点修复的次级问题包括：{severe_summary}。")

        if technical_safeguards:
            safeguards_preview = '；'.join(technical_safeguards[:3])
            discussion_parts.append(f"蓝方已给出技术防范措施，主要包括：{safeguards_preview}。委员会认为这些措施可以部分降低方法学风险，但仍需以审计日志、独立验证或复现包证明其有效性。")
        else:
            discussion_parts.append("蓝方尚未提交足够具体的技术防范措施，因此委员会无法将相关风险下调。")

        return ' '.join(discussion_parts)

    def _quick_verdict(self, red_attack: dict, blue_package: dict = None) -> dict:
        """
        快速裁决（基于攻击报告的定量分析）

        V7.2 修复：检查 technical_safeguards，如果蓝方提供了有效反击，进入深度审议

        Returns:
            {
                'is_definitive': bool,  # 是否可以确定裁决
                'result': dict          # 裁决结果
            }
        """
        critical_flaws = red_attack.get('critical_flaws', [])
        severe_issues = red_attack.get('severe_issues', [])
        moderate_concerns = red_attack.get('moderate_concerns', [])

        critical_count = len(critical_flaws)
        severe_count = len(severe_issues)

        technical_safeguards = self._extract_technical_safeguards(blue_package)
        has_safeguards = bool(technical_safeguards)
        if has_safeguards:
            print("[防御委员会 V7.2] 检测到蓝方提供了技术防范措施 (technical_safeguards)")

        if critical_count >= self.critical_threshold:
            if has_safeguards:
                print("[防御委员会 V7.2] 虽然有致命缺陷，但蓝方提供了技术防范措施，进入深度审议")
                return {
                    'is_definitive': False,
                    'result': {}
                }

            recommendations = [f['suggestion'] for f in critical_flaws if isinstance(f, dict) and f.get('suggestion')]
            committee_discussion = self._build_committee_discussion(red_attack, technical_safeguards)
            attack_responses = self._build_attack_responses(
                red_attack,
                technical_safeguards=technical_safeguards,
                committee_response=committee_discussion,
                recommendations=recommendations
            )
            return {
                'is_definitive': True,
                'result': {
                    'defense_passed': False,
                    'verdict': 'failed',
                    'committee_response': (
                        f"**委员会裁决：防守失败**\n\n发现 {critical_count} 个致命缺陷，这些缺陷会导致研究无法达到预期目标或产生不可靠的结论。"
                        f" 当前最关键的问题包括：{self._summarize_issue_labels(critical_flaws)}。"
                    ),
                    'final_verdict': 'FAILED - 存在致命缺陷',
                    'critical_issues': [f['issue'] for f in critical_flaws if isinstance(f, dict) and f.get('issue')],
                    'recommendations': recommendations,
                    'committee_discussion': committee_discussion,
                    'attack_responses': attack_responses,
                }
            }

        if severe_count >= self.severe_threshold:
            recommendations = [f['suggestion'] for f in severe_issues if isinstance(f, dict) and f.get('suggestion')]
            committee_discussion = self._build_committee_discussion(red_attack, technical_safeguards)
            attack_responses = self._build_attack_responses(
                red_attack,
                technical_safeguards=technical_safeguards,
                committee_response=committee_discussion,
                recommendations=recommendations
            )
            return {
                'is_definitive': True,
                'result': {
                    'defense_passed': False,
                    'verdict': 'failed',
                    'committee_response': (
                        f"**委员会裁决：防守失败**\n\n存在 {severe_count} 个严重问题，累积影响研究的可信度和可行性。"
                        f" 委员会认为优先修复项为：{self._summarize_issue_labels(severe_issues)}。"
                    ),
                    'final_verdict': 'FAILED - 严重问题过多',
                    'critical_issues': [f['issue'] for f in severe_issues if isinstance(f, dict) and f.get('issue')],
                    'recommendations': recommendations,
                    'committee_discussion': committee_discussion,
                    'attack_responses': attack_responses,
                }
            }

        if severe_count == 0 and critical_count == 0:
            recommendations = [f['suggestion'] for f in moderate_concerns if isinstance(f, dict) and f.get('suggestion')]
            committee_discussion = self._build_committee_discussion(red_attack, technical_safeguards)
            attack_responses = self._build_attack_responses(
                red_attack,
                technical_safeguards=technical_safeguards,
                committee_response=committee_discussion,
                recommendations=recommendations
            )
            return {
                'is_definitive': True,
                'result': {
                    'defense_passed': True,
                    'verdict': 'passed',
                    'committee_response': (
                        f"**委员会裁决：防守成功**\n\n红方攻击未发现致命或严重问题。"
                        f" {len(moderate_concerns)} 个中等疑虑可以在后续研究中改进。"
                    ),
                    'final_verdict': 'PASSED - 无重大问题',
                    'critical_issues': [],
                    'recommendations': recommendations,
                    'committee_discussion': committee_discussion,
                    'attack_responses': attack_responses,
                }
            }

        return {
            'is_definitive': False,
            'result': {}
        }

    def _deep_deliberation(self, blue_package: dict, red_attack: dict) -> dict:
        """
        深度审议（调用LLM进行综合评估）

        Args:
            blue_package: 蓝方防御材料
            red_attack: 红方攻击报告

        Returns:
            裁决结果
        """
        prompt = self._build_deliberation_prompt(blue_package, red_attack)

        for attempt in range(self.max_retries):
            try:
                print(f"[防御委员会] 第 {attempt + 1}/{self.max_retries} 次尝试进行审议...")

                response = self._call_llm_with_retry(prompt, max_tokens=3000)

                # 解析响应
                deliberation_result = self._parse_deliberation_response(response)

                return deliberation_result

            except Exception as e:
                print(f"[防御委员会] 审议失败 (尝试 {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                else:
                    # 最后一次失败，使用保守裁决
                    return self._conservative_verdict(red_attack)

    def _build_deliberation_prompt(self, blue_package: dict, red_attack: dict) -> str:
        """构建审议提示词"""
        hypothesis_data = blue_package.get('hypothesis_data', {})
        title = hypothesis_data.get('title', 'N/A')

        # V7.2: 提取 technical_safeguards（技术防范措施）
        methodology = hypothesis_data.get('methodology', {})
        technical_safeguards = None
        safeguards_text = "无"

        # V7.2 调试输出
        print(f"[DEBUG] hypothesis_data keys: {list(hypothesis_data.keys())}")
        print(f"[DEBUG] methodology type: {type(methodology)}")
        if isinstance(methodology, dict):
            print(f"[DEBUG] methodology keys: {list(methodology.keys())}")

        if isinstance(methodology, dict):
            technical_safeguards = methodology.get('technical_safeguards')
            if technical_safeguards:
                import json
                safeguards_text = json.dumps(technical_safeguards, ensure_ascii=False, indent=2)

        # V7.3 调试输出
        print(f"[DEBUG V7.3] safeguards_text 长度: {len(safeguards_text)}")
        print(f"[DEBUG V7.3] safeguards_text 前300字符:\n{safeguards_text[:300]}")

        critical_flaws = red_attack.get('critical_flaws', [])
        severe_issues = red_attack.get('severe_issues', [])
        moderate_concerns = red_attack.get('moderate_concerns', [])
        red_summary = red_attack.get('summary', '')

        # 格式化问题列表
        critical_text = "\n".join([f"- [{f.get('category', 'N/A')}] {f.get('issue', '')}" for f in critical_flaws])
        severe_text = "\n".join([f"- [{f.get('category', 'N/A')}] {f.get('issue', '')}" for f in severe_issues])
        moderate_text = "\n".join([f"- [{f.get('category', 'N/A')}] {f.get('issue', '')}" for f in moderate_concerns])

        prompt = f"""你是研究假设答辩委员会，由四位资深专家组成：

1. **主席**：Nature杂志资深编委
2. **方法论专家**：统计学和计算机科学专家
3. **领域专家**：生物学和医学专家
4. **临床转化专家**：临床应用和转化专家

---

## 案例信息

**研究题目**: {title}

---

## 红方攻击报告摘要

### 红方整体评估
{red_summary}

### 攻击详情

**致命缺陷** ({len(critical_flaws)}项):
{critical_text if critical_text else '无'}

**严重问题** ({len(severe_issues)}项):
{severe_text if severe_text else '无'}

**中等疑虑** ({len(moderate_concerns)}项):
{moderate_text if moderate_text else '无'}

---

## V7.2 蓝方技术防范措施（Technical Safeguards）

**重要**: 蓝方是否针对红方攻击添加了具体的技术防范措施？

{safeguards_text}

**审议提示**: 如果蓝方提供了有效的技术防范措施（如嵌套交叉验证���预处理隔离、SHAP可解释性等），请在裁决时考虑这些反击是否充分回应了红方的攻击。

---

## 委员会审议任务

请四位专家从各自角度讨论：

1. **主席**：综合评估，判断是否达到Nature/Science级别的发表标准
2. **方法论专家**：评估技术路线的合理性和可行性
3. **领域专家**：评估科学创新性和潜在影响力
4. **临床转化专家**：评估临床应用价值和转化可能性

## 裁决标准

- **防守成功 (passed)**: 无致命缺陷，严重问题 ≤ 2个，核心方案可行
- **有条件通过 (conditional)**: 无致命缺陷，严重问题 = 2个但可明确修复
- **防守失败 (failed)**: 存在致命缺陷，或严重问题 ≥ 3个，或核心方案有根本性问题

**V7.2 重要补充**: 如果蓝方提供了有��的 `technical_safeguards`（技术防范措施），请评估这些措施是否充分回应了红方关于方法论漏洞的攻击。如果反击充分且具体，可以降低对相应问题的严重程度判定。

## 输出要求

请以JSON格式输出委员会决议：

{{
  "defense_passed": true/false,
  "verdict": "passed/conditional/failed",
  "committee_response": "委员会的正式回应，说明裁决理由",
  "final_verdict": "最终裁决的简短描述",
  "critical_issues": ["需要修复的关键问题列表"],
  "recommendations": ["具体改进建议"],
  "committee_discussion": "委员会讨论要点摘要，需比 committee_response 更细，说明各角色争议与共识",
  "attack_responses": [
    {{
      "attack_type": "攻击类型",
      "issue": "该类型下最关键的问题",
      "response": "委员会对该攻击的具体回应或要求"
    }}
  ]
}}

请开始委员会审议：
"""

        return prompt

    def _parse_deliberation_response(self, response: str) -> dict:
        """解析审议响应"""
        try:
            deliberation_data = self.extractor.safe_extract_json(response)

            defense_passed = deliberation_data.get('defense_passed', False)
            verdict = deliberation_data.get('verdict', 'failed')

            # V7.3 调试输出
            print(f"[DEBUG V7.3] 深度审议结果: defense_passed={defense_passed}, verdict={verdict}")

            # conditional 视为 passed，但需要修复问题
            if verdict == 'conditional':
                defense_passed = True

            return {
                'defense_passed': defense_passed,
                'verdict': verdict,
                'committee_response': deliberation_data.get('committee_response', ''),
                'final_verdict': deliberation_data.get('final_verdict', ''),
                'critical_issues': deliberation_data.get('critical_issues', []),
                'recommendations': deliberation_data.get('recommendations', []),
                'committee_discussion': deliberation_data.get('committee_discussion', ''),
                'attack_responses': deliberation_data.get('attack_responses', []),
            }
        except Exception as e:
            print(f"[防御委员会] 解析响应失败: {e}")
            raise LLMParseError(f"无法解析审议响应: {e}")

    def _conservative_verdict(self, red_attack: dict) -> dict:
        """保守裁决（当审议失败时使用）"""
        severe_issues = red_attack.get('severe_issues', [])
        severe_count = len(severe_issues)

        technical_safeguards = []
        committee_discussion = self._build_committee_discussion(red_attack, technical_safeguards)
        attack_responses = self._build_attack_responses(
            red_attack,
            technical_safeguards=technical_safeguards,
            committee_response=committee_discussion,
            recommendations=[]
        )

        if severe_count >= 2:
            # 保守策略：2个严重问题视为失败
            return {
                'defense_passed': False,
                'verdict': 'failed',
                'committee_response': '**委员会裁决：防守失败**\n\n由于委员会审议过程出现问题，采用保守裁决。鉴于红方报告指出多个严重问题，判定方案需要重大修改。',
                'final_verdict': 'FAILED - 保守裁决',
                'critical_issues': [f['issue'] for f in severe_issues if isinstance(f, dict) and f.get('issue')],
                'recommendations': [],
                'committee_discussion': committee_discussion,
                'attack_responses': attack_responses,
            }
        else:
            # 保守策略：允许通过但需要改进
            return {
                'defense_passed': True,
                'verdict': 'conditional',
                'committee_response': '**委员会裁决：有条件通过**\n\n由于委员会审议过程出现问题，采用保守裁决。方案基本可行，但需要针对指出的问题进行改进。',
                'final_verdict': 'CONDITIONAL - 保守裁决',
                'critical_issues': [],
                'recommendations': [],
                'committee_discussion': committee_discussion,
                'attack_responses': attack_responses,
            }

    def _call_llm_with_retry(self, prompt: str, max_tokens: int = 3000) -> str:
        """带重试的LLM调用"""
        for attempt in range(self.max_retries):
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}]
                )
                return message.content[0].text
            except Exception as e:
                print(f"[防御委员会] LLM调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                else:
                    raise


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    # 测试防御委员会
    committee = DefenseCommitteeAgent()

    test_blue_package = {
        'hypothesis_data': {
            'title': '测试假设',
            'core_hypothesis': '这是一个测试用的核心假设描述'
        },
        'genai_proposal': {
            'technical_proposal': '这是GenAI技术方案的测试内容...'
        }
    }

    test_red_attack = {
        'critical_flaws': [],
        'severe_issues': [
            {
                'category': '数据风险',
                'issue': '样本量可能不足',
                'severity': 'severe',
                'reason': '需要更多数据支持',
                'suggestion': '增加数据集规模'
            }
        ],
        'moderate_concerns': [],
        'summary': '整体方案可行，但存在一些数据相关的问题需要解决。',
        'confidence': 0.7
    }

    result = committee.execute({
        'blue_package': test_blue_package,
        'red_attack': test_red_attack
    })

    if result['success']:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
