# -*- coding: utf-8 -*-
"""
红方攻击智能体 (Red Team Agent - 纯数据科学火力校准版)
人���：极度挑剔的Nature审稿人，专门攻击纯数据科学领域的致命伤

核心任务（重构后）：
- 攻击数据穿越 (Data Leakage)
- 检测内生性偏倚 (Endogeneity/Confounders)
- 识别多重假设检验校正缺失 (FDR/Bonferroni)
- 评估因果图后门路径未闭合
- 检查样本量与参数量比例不当
- 评估泛化能力缺失（过拟合）
"""
from typing import Dict, List, Optional
import json
import sys
import os
import time
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import BaseAgent
from utils.llm_utils import SafeExtractor, LLMParseError, RetryExecutor
from core.zero_day_defense import SteelStampReinforcer  # V3.4: 钢印强化
import anthropic


# 纯数据科学攻击检查清单
PURE_DS_RED_TEAM_CHECKLIST = {
    'data_leakage': {
        'name': '数据穿越 (Data Leakage)',
        'description': '最致命的数据科学错误',
        'patterns': [
            'CV外特征选择：在交叉验证外进行特征选择/降维',
            '信息泄露：使用未来信息预测过去',
            '样本泄漏：同一患者的多次采样分散在train/test中',
            '标签泄露：特征中包含目标变量的信息',
            '预处理泄漏：使用全集统计量（均值/方差）进行归一化',
            '时间穿越：时间序列模型使用未来数据'
        ]
    },
    'endogeneity_confounding': {
        'name': '内生性偏倚 (Endogeneity & Confounders)',
        'description': '因果推断的核心问题',
        'patterns': [
            '未闭合后门路径：DAG中存在未阻断的后门路径',
            '遗漏变量偏倚：关键混杂因素未被控制',
            '反向因果：结果变量影响原因变量',
            '测量误差：关键变量测量不精确',
            '选择性偏倚：样本非随机选择',
            '工具变量无效：IV与内生变量不相关或与误差项相关'
        ]
    },
    'multiple_testing': {
        'name': '多重假设检验校正缺失',
        'description': '统计学重大错误',
        'patterns': [
            '未校正FDR：进行多次假设检验但未校正假发现率',
            '未使用Bonferroni：多项检验未采用保守校正',
            'P-hacking：数据挖掘后只报告显著结果',
            'HARKing：假设事后已知结果',
            '未预设终点：次要分析当作主要分析报告'
        ]
    },
    'statistical_power': {
        'name': '统计功效与样本量问题',
        'description': '研究设计的统计学缺陷',
        'patterns': [
            '样本量不足：参数量 > 样本数/10（过拟合风险）',
            '功效分析缺失：未进行a priori功效计算',
            '效应量虚高：报告的效应量远超领域典型值',
            '置信区间过宽：效应估计不精确',
            '事件数不足：生存分析中事件数/变量数 < 10'
        ]
    },
    'causal_inference': {
        'name': '因果推断问题',
        'description': '观察性研究的致命伤',
        'patterns': [
            '混淆控制不充分：关键混杂因素未测量或未控制',
            '中介分析未正确识别：未区分总效应与直接效应',
            '敏感性分析缺失：未评估未测量混杂的影响（E-value）',
            '负性对照缺失：未使用阴性对照暴露/结局检验模型',
            'DAG不完整：因果图遗漏关键变量'
        ]
    },
    'reproducibility': {
        'name': '可复现性问题',
        'description': '研究质量的关键',
        'patterns': [
            '随机种子未固定：结果不可复现',
            '数据分割不清晰：train/test分割未明确说明',
            '代码未公开：无法验证结果',
            '超参数搜索泄漏：在测试集上调参',
            '数据增强不恰当：train/test使用了不同的增强策略'
        ]
    }
}




# ==================== V6.1 降权版系统提示词 ====================

RED_TEAM_V6_AUDITOR_PROMPT = """
╔══════════════════════════════════════════════════════════════════════════════╗
║              红方审计员 (降权版 V6.1) - 严谨性专责审查                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

你是 Nature 杂志的顶级审稿人，但你的权限已被重新界定。

## ════════════════════════════════════════════════════════════════════════════
## 【权限边界声明 - Authority Boundary】
## ════════════════════════════════════════════════════════════════════════════

**你不再负责评估该假说的创新性（Novelty）**。该指标已由外部向量引擎接管。

你的**唯一任务**是评估：
1. **严谨性（Rigor）** - 技术路线是否闭环、参数是否合理
2. **文献支撑度（Grounding）** - 引用是否真实、数据来源是否可靠

## ════════════════════════════════════════════════════════════════════════════
## 【物理铁闸熔断触发条件】
## ════════════════════════════════════════════════════════════════════════════

以下任一情况发生时，你必须将 `rigor_score` 设为 **0** 并触发熔断：

### 熔断条件 A：虚假模型包装
如果发现它是用毫无意义的模型名词（如强加 Transformer 到不该用的场景）来包装一个错误的对接逻辑：
- 例如：在分子对接任务中强行使用 "Transformer-based docking" 而非 Boltz2 或 Glide
- 例如：声称使用 "深度学习增强的 GWAS"，但没有说明具体的 DL 模型和基因特征编码方式

### 熔断条件 B：参数黑洞
技术路线中出现无法落实的参数：
- 例如："使用 RTX 4090 进行大规模推理" 但未说明显存需求
- 例如："训练 1000 个 epoch" 但未说明数据量和训练时间

### 熔断条件 C：UKB 字段伪造
引用的 UK Biobank Data-Field 不存在：
- 真实字段示例：31（性别）、21022（年龄）、30000（BMI）
- 虚假字段示例：99999、88888（不存在）

### 熔断条件 D：SMILES 非法
如果假设涉及药物设计，但 SMILES 字符串不合法：
- 真实 SMILES：CC(=O)Oc1ccccc1C(=O)O（阿司匹林）
- 非法 SMILES：随机字符组合

## ════════════════════════════════════════════════════════════════════════════
## 【纯数据科学攻击检查清单 - 保留】
## ════════════════════════════════════════════════════════════════════════════

请从以下维度进行严格审查：

### 1. 数据穿越 (Data Leakage) - 致命
- CV外特征选择：特征选择/降维在交叉验证外进行
- 信息泄露：使用未来信息预测过去
- 样本泄漏：同一患者的多次采样分散在train/test中

### 2. 内生性偏倚 (Endogeneity & Confounders) - 致命
- 未闭合后门路径：DAG中存在未阻断的后门路径
- 遗漏变量偏倚：关键混杂因素未被控制
- 反向因果：结果变量影响原因变量

### 3. 多重假设检验校正缺失 - 严重
- 未校正FDR：多次检验未校正假发现率
- P-hacking：数据挖掘后只报告显著结果

### 4. 统计功效与样本量问题 - 严重
- 样本量不足：参数量 > 样本数/10
- 功效分析缺失：未进行a priori功效计算

### 5. 因果推断问题 - 严重
- 混杂控制不充分：关键混杂因素未测量或未控制
- 敏感性分析缺失：未评估未测量混杂的影响（E-value）

### 6. 可复现性问题 - 中等
- 随机种子未固定：结果不可复现
- 超参数搜索泄漏：在测试集上调参

## ════════════════════════════════════════════════════════════════════════════
## 【输出格式 - Output Format】
## ════════════════════════════════════════════════════════════════════════════

请以 JSON 格式输出你的审计报告：

{
  "rigor_score": 0-10,      // 严谨性分数（遇熔断条件=0）
  "grounding_score": 0-10,  // 文献支撑度分数
  "critical_flaws": [...],  // 致命缺陷（导致熔断）
  "severe_issues": [...],   // 严重问题
  "moderate_concerns": [...],
  "minor_suggestions": [...],
  "fuse_triggered": false,  // 是否触发熔断
  "fuse_reason": "",        // 熔断原因（如有）
  "verdict": "pass/fail",
  "confidence": 0.8
}

**重要**：你只评估严谨性和支撑度，不要评价"这个想法有多新颖"。
创新性已由外部向量引擎计算，你的任务只是确保技术路线不犯错。
"""
class RedTeamAgent(BaseAgent):
    """
    红方攻击智能体（纯数据科学版）

    人设：极度挑剔的Nature审稿人
    专门攻击纯数据科学领域的致命伤

    V3.2 新增：差异化批评机制（防止模式崩溃）
    """

    # 致命缺陷阈值：发现任一致命缺陷即判定为防守失败
    CRITICAL_FLAW_THRESHOLD = 1

    # 严重问题阈值：严重问题超过此数量即判定为防守失败
    SEVERE_ISSUE_THRESHOLD = 3

    def __init__(self):
        super().__init__("红方攻击专家", agent_type="red_team")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.extractor = SafeExtractor()
        self.max_retries = 3

        # V3.2 新增：历史批评记录（用于差异化）
        self.criticism_history: List[Dict] = []

    def execute(self, input_data: Dict) -> Dict:
        """
        执行红方攻击（纯数据科学版）

        Args:
            input_data: {
                'blue_package': dict - 蓝方防御材料
                    {
                        'genai_proposal': dict/s - GenAI方案
                        'compbio_proposal': dict/s - 计算生物学方案
                        'pathology_proposal': dict/s - 数字病理学方案
                        'biostats_proposal': dict/s - 生物统计学方案
                        'clinical_review': dict/s - 临床审查
                        'hypothesis_data': dict - 原始假设
                    }
            }

        Returns:
            {
                'success': bool,
                'attack_report': {
                    'critical_flaws': [],      # 致命缺陷（一票否决）
                    'severe_issues': [],       # 严重问题
                    'moderate_concerns': [],   # 中等疑虑
                    'minor_suggestions': [],   # 轻微建议
                    'verdict': str,            # 攻击结论: 'pass/fail'
                    'confidence': float,       # 攻击置信度 (0-1)
                    'overall_assessment': str  # 整体评估
                }
            }
        """
        blue_package = input_data.get('blue_package', {})

        if not blue_package:
            return {
                'success': False,
                'error': '缺少蓝方防御材料'
            }

        # 执行攻击分析
        attack_result = self._conduct_attack_analysis(blue_package)

        return {
            'success': True,
            'attack_report': attack_result
        }

    def _conduct_attack_analysis(self, blue_package: dict) -> dict:
        """
        进行攻击分析（纯数据科学版）

        Args:
            blue_package: 蓝方防御材料

        Returns:
            攻击报告
        """
        # 构建攻击提示词
        prompt = self._build_attack_prompt(blue_package)

        # 使用重试机制调用LLM
        for attempt in range(self.max_retries):
            try:
                print(f"[红方攻击专家] 第 {attempt + 1}/{self.max_retries} 次尝试生成攻击报告...")

                response = self._call_llm_with_retry(prompt, max_tokens=4000)

                # 解析响应
                attack_report = self._parse_attack_response(response)

                # 评估攻击结论
                verdict = self._determine_verdict(attack_report)

                attack_report['verdict'] = verdict
                attack_report['overall_assessment'] = self._generate_overall_assessment(attack_report)

                # V3.2 新增：记录审计历史（用于差异化）
                self.criticism_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'critical_flaws': attack_report.get('critical_flaws', []),
                    'severe_issues': attack_report.get('severe_issues', []),
                    'verdict': verdict
                })

                return attack_report

            except Exception as e:
                print(f"[红方攻击专家] 尝试 {attempt + 1} 失败: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                else:
                    # 最后一次失败，返回基础攻击报告
                    return self._generate_fallback_attack_report(blue_package, str(e))

    def _build_attack_prompt(self, blue_package: dict) -> str:
        """构建攻击提示词（纯数据科学版）"""

        genai_proposal = blue_package.get('genai_proposal', {})
        compbio_proposal = blue_package.get('compbio_proposal', {})
        pathology_proposal = blue_package.get('pathology_proposal', {})
        biostats_proposal = blue_package.get('biostats_proposal', {})
        clinical_review = blue_package.get('clinical_review', {})
        hypothesis_data = blue_package.get('hypothesis_data', {})

        # 提取关键信息
        title = hypothesis_data.get('title', 'N/A')
        core_hypothesis = hypothesis_data.get('core_hypothesis', hypothesis_data.get('rationale', 'N/A'))

        # V7.3 修复: 确保 core_hypothesis 是字符串
        if isinstance(core_hypothesis, dict):
            core_hypothesis = str(core_hypothesis)
        elif not isinstance(core_hypothesis, str):
            core_hypothesis = str(core_hypothesis)

        # 处理上游数据（可能是字符串或字典）
        def extract_content(data, max_len=800):
            if isinstance(data, dict):
                # 尝试提取关键字段
                for key in ['proposal', 'analysis', 'design', 'report', 'content']:
                    if key in data:
                        return str(data[key])[:max_len]
                # 处理空字典情况
                if not data:
                    return ''
                return str(data.get(list(data.keys())[0], ''))[:max_len]
            return str(data)[:max_len] if data else ''

        genai_content = extract_content(genai_proposal)
        compbio_content = extract_content(compbio_proposal)
        pathology_content = extract_content(pathology_proposal)
        biostats_content = extract_content(biostats_proposal)
        clinical_content = extract_content(clinical_review)

        prompt = f"""你是一位**Nature杂志的顶级审稿人**，以极度挑剔和严格著称。你的任务是找出以下**纯数据科学研究方案**中的所有统计学和因果推断缺陷。

**重要**：本研究是**纯干实验**（Dry Lab），不涉及任何湿实验。你的攻击焦点必须是**纯数据科学领域的致命���**。

---

**研究题目**: {title}

**核心假设**: {core_hypothesis[:500]}

---

## 蓝方防御材料

### 1. GenAI架构方案
{genai_content[:800]}

### 2. 计算生物学Pipeline
{compbio_content[:800]}

### 3. 数字病理学分析
{pathology_content[:800]}

### 4. 生物统计学验证框架
{biostats_content[:800]}

### 5. 临床效用评估
{clinical_content[:800]}

---

## 纯数据科学攻击检查清单

请从以下**六个维度**进行严格审查：

### 1. 数据穿越 (Data Leakage) - 致命
- CV外特征选择：特征选择/降维在交叉验证外进行
- 信息泄露：使用未来信息预测过去
- 样本泄漏：同一患者的多次采样分散在train/test中
- 标签泄露：特征中包含目标变量的信息
- 预处理泄漏：使用全集统计量进行归一化
- 时间穿越：时间序列模型使用未来数据

### 2. 内生性偏倚 (Endogeneity & Confounders) - 致命
- 未闭合后门路径：DAG中存在未阻断的后门路径
- 遗漏变量偏倚：关键混杂因素未被控制
- 反向因果：结果变量影响原因变量
- 选择性偏倚：样本非随机选择
- 工具变量无效：IV与误差项相关

### 3. 多重假设检验校正缺失 - 严重
- 未校正FDR：多次检验未校正假发现率
- 未使用Bonferroni：多项检验未采用保守校正
- P-hacking：数据挖掘后只报告显著结果
- HARKing：假设事后已知结果

### 4. 统计功效与样本量问题 - 严重
- 样本量不足：参数量 > 样本数/10
- 功效分析缺失：未进行a priori功效计算
- 效应量虚高：报告的效应量远超领域典型值
- 事件数不足：生存分析中事件数/变量数 < 10

### 5. 因果推断问题 - 严重
- 混杂控制不充分：关键混杂因素未测量或未控制
- 敏感性分析缺失：未评估未测量混杂的影响（E-value）
- 负性对照缺失：未使用阴性对照检验模型
- DAG不完整：因果图遗漏关键变量

### 6. 可复现性问题 - 中等
- 随机种子未固定：结果不可复现
- 超参数搜索泄漏：在测试集上调参
- 代码未公开：无法验证结果

---

## 输出要求

请以JSON格式输出你的攻击报告：

{{
  "critical_flaws": [
    {{
      "category": "数据穿越/内生性偏倚/多重假设检验/统计功效/因果推断/可复现性",
      "issue": "具体问题描述",
      "severity": "critical",
      "reason": "为什么这是致命缺陷",
      "suggestion": "如何修复（如果能修复）"
    }}
  ],
  "severe_issues": [
    {{
      "category": "同上",
      "issue": "具体问题描述",
      "severity": "severe",
      "reason": "为什么这是严重问题",
      "suggestion": "改进建议"
    }}
  ],
  "moderate_concerns": [
    {{
      "category": "同上",
      "issue": "具体问题描述",
      "severity": "moderate",
      "reason": "为什么这是问题",
      "suggestion": "改进建议"
    }}
  ],
  "minor_suggestions": [
    {{
      "category": "同上",
      "issue": "具体问题描述",
      "severity": "minor",
      "suggestion": "改进建议"
    }}
  ],
  "summary": "整体攻击总结（聚焦数据科学问题）",
  "confidence": 0.8
}}

**注意**：
1. critical_flaws 是致命缺陷，任何一项都可能导致拒稿
2. 数据穿越和内生性偏倚是最高优先级的攻击目标
3. 如果方案确实优秀且无明显数据科学问题，请诚实承认
4. confidence 表示你对攻击结论的信心程度（0-1）

请开始你的纯数据科学攻击分析："""

        # V3.4: 钢印强化 - 防止"中间迷失"
        prompt = SteelStampReinforcer.reinforce_prompt_constraints(
            prompt,
            categories=['modality_rejection', 'no_hallucination']
        )

        return prompt

    def _parse_attack_response(self, response: str) -> dict:
        """解析攻击响应"""
        try:
            attack_data = self.extractor.safe_extract_json(response)

            return {
                'critical_flaws': attack_data.get('critical_flaws', []),
                'severe_issues': attack_data.get('severe_issues', []),
                'moderate_concerns': attack_data.get('moderate_concerns', []),
                'minor_suggestions': attack_data.get('minor_suggestions', []),
                'summary': attack_data.get('summary', ''),
                'confidence': attack_data.get('confidence', 0.5)
            }
        except Exception as e:
            print(f"[红方攻击专家] 解析响应失败: {e}")
            raise LLMParseError(f"无法解析攻击响应: {e}")

    def _determine_verdict(self, attack_report: dict) -> str:
        """判定攻击结论"""
        critical_count = len(attack_report.get('critical_flaws', []))
        severe_count = len(attack_report.get('severe_issues', []))

        # 致命缺陷一票否决
        if critical_count > 0:
            return 'fail'

        # 严重问题累积否决
        if severe_count >= self.SEVERE_ISSUE_THRESHOLD:
            return 'fail'

        # 通过
        return 'pass'

    def _generate_overall_assessment(self, attack_report: dict) -> str:
        """生成整体评估"""
        critical_count = len(attack_report.get('critical_flaws', []))
        severe_count = len(attack_report.get('severe_issues', []))
        moderate_count = len(attack_report.get('moderate_concerns', []))
        summary = attack_report.get('summary', '')

        verdict = attack_report.get('verdict', 'pass')

        if verdict == 'fail':
            assessment = f"""**红方攻击结论：防守失败（纯数据科学视角）**

**致命缺陷**: {critical_count} 项
**严重问题**: {severe_count} 项

{summary}

该方案存在不可忽视的数据科学问题，建议进行重大修改后再提交。
"""
        else:
            assessment = f"""**红方攻击结论：防守通过（纯数据科学视角）**

**严重问题**: {severe_count} 项
**中等疑虑**: {moderate_count} 项

{summary}

该方案整体数据科学设计良好，建议针对指出的问题进行改进。
"""

        return assessment

    def _generate_fallback_attack_report(self, blue_package: dict, error: str) -> dict:
        """生成fallback攻击报告"""
        return {
            'critical_flaws': [
                {
                    'category': '系统错误',
                    'issue': f'红方攻击分析失败: {error}',
                    'severity': 'critical',
                    'reason': '系统无法完成攻击分析',
                    'suggestion': '请检查LLM服务状态'
                }
            ],
            'severe_issues': [],
            'moderate_concerns': [],
            'minor_suggestions': [],
            'summary': f'由于系统错误，无法完成完整的攻击分析。',
            'confidence': 0.0,
            'verdict': 'fail'
        }


    # ==================== V6.1 降权版评估方法 ====================

    def execute_v61_rigor_audit(self, input_data: Dict) -> Dict:
        """
        V6.1 降权版评估 - 仅评估严谨性，不评估创新性

        Args:
            input_data: {
                'hypothesis_data': dict - 原始假设
                'technical_proposal': dict/s - 技术方案
            }

        Returns:
            {
                'success': bool,
                'rigor_report': {
                    'rigor_score': float,        // 严谨性分数 (0-10)
                    'grounding_score': float,    // 文献支撑度 (0-10)
                    'critical_flaws': [],
                    'severe_issues': [],
                    'moderate_concerns': [],
                    'minor_suggestions': [],
                    'fuse_triggered': bool,
                    'fuse_reason': str,
                    'verdict': str
                }
            }
        """
        hypothesis_data = input_data.get('hypothesis_data', {})
        technical_proposal = input_data.get('technical_proposal', {})

        if not hypothesis_data:
            return {
                'success': False,
                'error': '缺少假设数据'
            }

        # 构建降权版提示词
        prompt = self._build_v61_rigor_prompt(hypothesis_data, technical_proposal)

        # 使用重试机制调用LLM
        for attempt in range(self.max_retries):
            try:
                print(f"[红方审计员V6.1] 第 {attempt + 1}/{self.max_retries} 次严谨性审查...")

                response = self._call_llm_with_retry(prompt, max_tokens=3000)

                # 解析响应
                rigor_report = self._parse_v61_response(response)

                # 记录审计历史
                self.criticism_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'rigor_score': rigor_report.get('rigor_score', 7.5),
                    'fuse_triggered': rigor_report.get('fuse_triggered', False),
                    'verdict': rigor_report.get('verdict', 'pass')
                })

                return {
                    'success': True,
                    'rigor_report': rigor_report
                }

            except Exception as e:
                print(f"[红方审计员V6.1] 尝试 {attempt + 1} 失败: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                else:
                    return {
                        'success': False,
                        'error': str(e),
                        'rigor_report': self._generate_fallback_rigor_report(hypothesis_data, str(e))
                    }

    def _build_v61_rigor_prompt(self, hypothesis_data: dict, technical_proposal: dict) -> str:
        """构建 V6.1 降权版提示词"""

        title = hypothesis_data.get('title', 'N/A')
        details = hypothesis_data.get('details', hypothesis_data.get('rationale', 'N/A'))

        # 提取技术方案内容
        tech_content = ''
        if isinstance(technical_proposal, dict):
            for key in ['proposal', 'analysis', 'design', 'content']:
                if key in technical_proposal:
                    tech_content = str(technical_proposal[key])[:1000]
                    break
        elif technical_proposal:
            tech_content = str(technical_proposal)[:1000]

        prompt = f"""{RED_TEAM_V6_AUDITOR_PROMPT}

---

## 研究方案

**标题**: {title}

**详细内容**:
{details[:1500]}

**技术方案**:
{tech_content}

---

请严格按照上述输出格式，输出你的严谨性审计报告（JSON格式）：
"""
        return prompt

    def _parse_v61_response(self, response: str) -> dict:
        """解析 V6.1 降权版响应"""
        try:
            audit_data = self.extractor.safe_extract_json(response)

            return {
                'rigor_score': float(audit_data.get('rigor_score', 7.5)),
                'grounding_score': float(audit_data.get('grounding_score', 7.5)),
                'critical_flaws': audit_data.get('critical_flaws', []),
                'severe_issues': audit_data.get('severe_issues', []),
                'moderate_concerns': audit_data.get('moderate_concerns', []),
                'minor_suggestions': audit_data.get('minor_suggestions', []),
                'fuse_triggered': audit_data.get('fuse_triggered', False),
                'fuse_reason': audit_data.get('fuse_reason', ''),
                'verdict': audit_data.get('verdict', 'pass'),
                'confidence': float(audit_data.get('confidence', 0.8))
            }
        except Exception as e:
            print(f"[红方审计员V6.1] 解析响应失败: {e}")
            return {
                'rigor_score': 0.0,              # V7.1: Fail-Closed - 降至 0 分
                'grounding_score': 0.0,          # V7.1: Fail-Closed - 降至 0 分
                'critical_flaws': [{
                    'category': '解析失败',
                    'issue': f'无法解析审计响应: {e}',
                    'severity': 'critical',
                    'suggestion': '审计结果不可信，采用 Fail-Closed 策略'
                }],
                'severe_issues': [],
                'moderate_concerns': [],
                'minor_suggestions': [],
                'fuse_triggered': True,          # V7.1: Fail-Closed - 强制熔断
                'fuse_reason': f'响应解析失败: {e}',
                'verdict': 'fail',               # V7.1: Fail-Closed - 强制拦截
                'confidence': 0.0                # V7.1: Fail-Closed - 置信度为 0
            }

    def _generate_fallback_rigor_report(self, hypothesis_data: dict, error: str) -> dict:
        """V7.1 Fail-Closed：审计失败时强制拦截"""
        return {
            'rigor_score': 0.0,              # V7.1: Fail-Closed - 降至 0 分
            'grounding_score': 0.0,          # V7.1: Fail-Closed - 降至 0 分
            'critical_flaws': [
                {
                    'category': '审计失败',
                    'issue': f'严谨性审查系统异常: {error}',
                    'severity': 'critical',
                    'reason': '审计器崩溃，采用 Fail-Closed 策略强制拦截',
                    'suggestion': '请检查 LLM 服务状态后重新提交'
                }
            ],
            'severe_issues': [],
            'moderate_concerns': [],
            'minor_suggestions': [],
            'fuse_triggered': True,          # V7.1: Fail-Closed - 强制熔断
            'fuse_reason': f'审计系统异常: {error}',
            'verdict': 'fail',               # V7.1: Fail-Closed - 强制拦截
            'confidence': 0.0                # V7.1: Fail-Closed - 置信度为 0
        }

    def _call_llm_with_retry(self, prompt: str, max_tokens: int = 4000) -> str:
        """带重试的LLM调用"""
        for attempt in range(self.max_retries):
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=0.3,
                    messages=[{"role": "user", "content": prompt}]
                )
                return message.content[0].text
            except Exception as e:
                print(f"[红方攻击专家] LLM调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                else:
                    raise


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    # 测试红方攻击（纯数据科学版）
    red_team = RedTeamAgent()

    test_blue_package = {
        'hypothesis_data': {
            'title': '测试假设',
            'core_hypothesis': '这是一个测试用的核心假设描述'
        },
        'genai_proposal': {
            'technical_proposal': '这是GenAI技术方案的测试内容...'
        },
        'compbio_proposal': {
            'pipeline': '计算生物学Pipeline测试内容...'
        },
        'pathology_proposal': {
            'analysis': '数字病理学分析测试内容...'
        },
        'biostats_proposal': {
            'framework': '生物统计学验证框架测试内容...'
        },
        'clinical_review': {
            'assessment': '临床效用评估测试内容...'
        }
    }

    result = red_team.execute({'blue_package': test_blue_package})

    if result['success']:
        import json
        print(json.dumps(result['attack_report'], ensure_ascii=False, indent=2))
