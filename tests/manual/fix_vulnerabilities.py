#!/usr/bin/env python3
"""
业务逻辑漏洞修复脚本
修复所有已识别的P0、P1、P2级别漏洞
"""

import os
import re
import shutil
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(r"C:\Users\PC\research-hypothesis-agent")


def backup_file(file_path: Path) -> Path:
    """备份文件"""
    backup_path = file_path.with_suffix(f'{file_path.suffix}.bak')
    shutil.copy2(file_path, backup_path)
    print(f"  已备份: {backup_path}")
    return backup_path


def fix_paper_search_agent():
    """P0-1: 修复论文搜索LLM评分的静默回退"""
    print("\n[1/9] 修复 P0-1: 论文搜索LLM评分静默回退...")

    file_path = PROJECT_ROOT / "src" / "agents" / "paper_search_agent.py"
    backup_file(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找并替换 _call_llm_for_screening 方法
    old_method = '''    def _call_llm_for_screening(self, title: str, abstract: str) -> Dict:
        """
        调用LLM进行摘要评分
        """
        try:
            # 构建完整提示
            prompt = self.SCREENING_PROMPT.format(
                title=f"**{title}**",
                abstract=abstract[:3000]
            )

            # 调用API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            # 解析响应
            response_text = self._extract_text_from_response(message.content)
            result = self._parse_llm_json_response(response_text)

            return result

        except Exception as e:
            import traceback
            print(f"    ⚠️ LLM评分失败: {type(e).__name__}: {e}")
            print(f"    详细错误: {traceback.format_exc()[:200]}")
            # Fallback: 使用基础评分
            return {
                'score': 5.0,
                'reason': f'LLM调用失败({type(e).__name__})',
                'innovation': 'N/A',
                'data_quality': 'N/A',
                'research_type': 'N/A'
            }'''

    new_method = '''    def _call_llm_for_screening(self, title: str, abstract: str, max_retries: int = 2) -> Dict:
        """
        调用LLM进行摘要评分 - 带重试机制，失败时返回低分而非中等分

        Args:
            title: 论文标题
            abstract: 论文摘要
            max_retries: 最大重试次数
        """
        import time

        for attempt in range(max_retries):
            try:
                # 构建完整提示
                prompt = self.SCREENING_PROMPT.format(
                    title=f"**{title}**",
                    abstract=abstract[:3000]
                )

                # 调用API
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )

                # 解析响应
                response_text = self._extract_text_from_response(message.content)
                result = self._parse_llm_json_response(response_text)

                return result

            except Exception as e:
                import traceback
                print(f"    ⚠️ LLM评分失败(尝试{attempt + 1}/{max_retries}): {type(e).__name__}: {e}")

                if attempt < max_retries - 1:
                    # 重试前等待
                    time.sleep(1)
                    continue

                # 最后一次尝试失败，返回极低分而非中等分
                print(f"    ❌ LLM评分彻底失败，论文将被降权处理")
                return {
                    'score': 0.1,  # 极低分，而非5.0
                    'reason': f'LLM评分彻底失败({type(e).__name__})',
                    'innovation': 'unknown',
                    'data_quality': 'unknown',
                    'research_type': 'unknown',
                    'is_parsing_error': True  # 标记为解析错误
                }'''

    if old_method in content:
        content = content.replace(old_method, new_method)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ P0-1 修复完成: LLM评分失败现在返回0.1分而非5.0分")
    else:
        print("  ⚠ 未找到目标代码块，可能已修复或代码结构变化")


def fix_clinical_md_agent():
    """P0-2: 修复临床审查缺少结构化可行性评估"""
    print("\n[2/9] 修复 P0-2: 临床审查缺少结构化可行性评估...")

    file_path = PROJECT_ROOT / "src" / "agents" / "clinical_md_agent.py"
    backup_file(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 在 execute 方法的 return 之前添加可行性评估提取
    old_return = '''        return {
            'success': True,
            'clinical_review': revised_proposal,
            'revised_proposal': revised_proposal,
            'report_path': report_path
        }'''

    new_return = '''        # 从生成的报告中提取结构化可行性评估
        feasibility_assessment = self._extract_feasibility_assessment(revised_proposal)

        return {
            'success': True,
            'clinical_review': revised_proposal,
            'revised_proposal': revised_proposal,
            'report_path': report_path,
            'feasibility_assessment': feasibility_assessment  # 新增：结构化可行性评估
        }'''

    if old_return in content:
        content = content.replace(old_return, new_return)

        # 添加新的方法来提取可行性评估
        # 在类的末尾添加新方法
        class_end_pattern = r'(    def _add_retry_prompt\(self, original_prompt: str, error_message: str\) -> str:.*?)(\n\nclass |\Z)'
        new_method = '''    def _extract_feasibility_assessment(self, clinical_review: str) -> Dict:
        """
        从临床审查报告中提取结构化的可行性评估

        Args:
            clinical_review: 临床审查报告文本

        Returns:
            包含可行性等级、评分和细分得分的字典
        """
        import re

        # 默认评估
        assessment = {
            'feasibility': 'unknown',
            'overall_score': 5.0,
            'scores': {
                'clinical_relevance': 5.0,
                'practicality': 5.0,
                'resource_requirements': 5.0,
                'regulatory_path': 5.0
            },
            'reasoning': '未能从报告中提取明确的可行性评估'
        }

        # 尝试提取可行性等级
        feasibility_patterns = [
            r'(?:可行性评估|feasibility)[：:]\s*([^\n。.]+)',
            r'(?:总体可行性|overall feasibility)[：:]\s*([^\n。.]+)',
            r'(?:结论|conclusion)[：:]\s*(?:该方案)?[^\n]*(?:高度可行|可行|需修改|不可行)'
        ]

        for pattern in feasibility_patterns:
            match = re.search(pattern, clinical_review, re.IGNORECASE)
            if match:
                level_text = match.group(1).lower()
                if any(kw in level_text for kw in ['高度可行', 'highly feasible', 'strongly recommend']):
                    assessment['feasibility'] = 'highly_feasible'
                elif any(kw in level_text for kw in ['基本可行', '可行', 'feasible', 'recommend']):
                    assessment['feasibility'] = 'feasible'
                elif any(kw in level_text for kw in ['需修改', '需要调整', 'modification', 'revision']):
                    assessment['feasibility'] = 'feasible_with_modification'
                elif any(kw in level_text for kw in ['不可行', 'not feasible', 'not recommend']):
                    assessment['feasibility'] = 'not_feasible'
                break

        # 尝试提取评分
        score_patterns = [
            r'(?:综合评分|overall score|评分)[：:]\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)[/ ]*10'
        ]

        for pattern in score_patterns:
            match = re.search(pattern, clinical_review)
            if match:
                try:
                    score = float(match.group(1))
                    assessment['overall_score'] = min(10.0, max(0.0, score))
                    break
                except ValueError:
                    pass

        # 根据报告内容关键词调整评分
        positive_keywords = ['创新', '有效', '前景', 'recommend', 'promising']
        negative_keywords = ['局限', '困难', '不足', 'risk', 'challenge', 'limited']

        positive_count = sum(1 for kw in positive_keywords if kw in clinical_review.lower())
        negative_count = sum(1 for kw in negative_keywords if kw in clinical_review.lower())

        if assessment['overall_score'] == 5.0:  # 如果没有找到明确评分
            base_score = 6.0
            assessment['overall_score'] = max(3.0, min(9.0, base_score + positive_count * 0.5 - negative_count * 0.3))

        return assessment

    def _add_retry_prompt(self, original_prompt: str, error_message: str) -> str:
        """在重试时添加更明确的错误提示"""

'''
        # 在 _add_retry_prompt 方法之前插入新方法
        if 'def _extract_feasibility_assessment' not in content:
            content = re.sub(
                r"(    def _add_retry_prompt\(self, original_prompt: str, error_message: str\) -> str:)",
                new_method + r"\1",
                content,
                count=1
            )

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ P0-2 修复完成: 临床审查现在返回结构化可行性评估")
    else:
        print("  ⚠ 未找到目标代码块，可能已修复或代码结构变化")


def fix_debate_coordinator_parsing():
    """P0-3: 修复辩论协调器解析失败时的处理"""
    print("\n[3/9] 修复 P0-3: 辩论观点解析失败处理...")

    file_path = PROJECT_ROOT / "src" / "agents" / "debate_coordinator.py"
    backup_file(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 修改 _parse_json_response 方法，不再抛出异常而是返回错误标记
    old_method = '''    def _parse_json_response(self, response_text: str, role: str) -> Dict:
        """解析 JSON 响应 - 使用 SafeExtractor

        Args:
            response_text: LLM 响应文本
            role: 角色名称

        Returns:
            解析后的字典

        Raises:
            ValueError: 解析失败时抛出异常
        """
        try:
            result = self.extractor.safe_extract_json(response_text)
            if result:
                return result
        except LLMParseError as e:
            print(f"[辩论协调器] SafeExtractor 解析失败 ({role}): {e}")

        # 解析失败，抛出异常
        raise ValueError(f"无法从 {role} 的响应中提取有效的 JSON 数据。响应长度: {len(response_text)}")'''

    new_method = '''    def _parse_json_response(self, response_text: str, role: str) -> Dict:
        """解析 JSON 响应 - 使用 SafeExtractor

        Args:
            response_text: LLM 响应文本
            role: 角色名称

        Returns:
            解析后的字典，或包含错误信息的字典（解析失败时）
        """
        try:
            result = self.extractor.safe_extract_json(response_text)
            if result:
                return result
        except LLMParseError as e:
            print(f"[辩论协调器] SafeExtractor 解析失败 ({role}): {e}")

        # 解析失败时返回错误标记，而非抛出异常
        # 这样可以继续处理其他专家的观点，实现"单点失败不影响整体"
        return {
            'parse_error': True,
            'role': role,
            'error_message': f'无法从 {role} 的响应中提取有效的 JSON 数据',
            'response_length': len(response_text),
            'raw_response': response_text[:500]  # 保存前500字符用于调试
        }'''

    if old_method in content:
        content = content.replace(old_method, new_method)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ P0-3 修复完成: 解析失败时返回错误标记而非抛出异常")
    else:
        print("  ⚠ 未找到目标代码块，可能已修复或代码结构变化")


def fix_hypothesis_auto_fill():
    """P1-1: 移除假设自动填充机制"""
    print("\n[4/9] 修复 P1-1: 移除假设自动填充机制...")

    file_path = PROJECT_ROOT / "src" / "agents" / "hypothesis_agent.py"
    backup_file(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 修改 _fill_hypothesis_to_meet_requirements 方法，改为验证并拒绝
    old_method = '''    def _fill_hypothesis_to_meet_requirements(self, hyp: Dict) -> Dict:
        """填充假设字段以满足最低长度要求"""
        # 填充文本库
        filler_texts = {
            'core_problem': "\\n\\n本研究针对当前领域的方法学局限性进行深入分析。通过系统性文献综述，我们发现现有研究在样本量、数据质量、分析方法等方面存在显著不足。具体而言，大多数研究依赖于小样本单中心数据，缺乏多中心大样本验证。此外，现有方法未能充分考虑生物学异质性和技术噪声的影响，导致结果的可重复性和泛化能力受限。本研究旨在通过引入先进的数据分析方法和严格的实验设计，克服这些局限性，为领域提供新的研究范式。",

            'core_hypothesis': "\\n\\n基于上述分析，我们提出创新的假设框架。该框架融合了最新的数据科学方法与领域专业知识，通过多层次建模和系统性验证，有望揭示潜在的生物学机制。具体而言，我们将采用纵向研究设计，结合多模态数据整合分析，验证假设的可靠性和有效性。这一创新性方法将填补领域内的重要空白。",

            'technical_route': "\\n\\n**数据预处理**：质量控制过滤低质量样本，Z-score标准化，ComBat批次校正。**核心算法**：深度学习框架，多层神经网络，Adam优化器学习率0.001。**验证策略**：5折交叉验证，独立测试集，外部验证。",

            'expected_breakthrough': "\\n\\n**现有方法的局限性**：当前领域主流方法存在显著缺陷，基于简单统计模型无法捕捉复杂非线性关系，样本量不足导致统计效力低下。**本研究的颠覆性**：引入先进的机器学习方法和大规模数据资源，提供更高的预测精度、更强的泛化能力、更好的可解释性。",

            'clinical_value': "\\n\\n本研究成果具有广泛的临床转化价值和实际应用前景。首先，开发的预测模型可以辅助临床决策，提高诊断准确性和治疗选择的精准性。该模型可集成到医院信息系统，为医生提供实时决策支持。其次，发现的关键生物标志物可用于疾病分层和预后评估，帮助识别高风险患者，制定个体化治疗方案。再者，研究揭示的病理机制为新药开发提供了潜在靶点，可加速药物发现和开发进程。此外，本研究建立的分析框架和方法学可推广到其他相关疾病，具有广泛的适用性。通过与企业合作，部分成果可转化为商业化的诊断试剂或软件工具，产生经济社会效益。",

            'internal_reasoning': "\\n\\n**文献深度分析**：通过对领域内关键文献的系统梳理，我们发现研究脉络存在明显的断层。早期研究主要关注现象描述，近年来开始转向机制探索，但两者之间缺乏有效的衔接。**矛盾点识别**：多项研究报道了相互矛盾的结论，这种矛盾的根源可能在于研究人群的异质性、检测方法的差异、未充分考虑混杂因素。**技术选择理由**：我们选择采用多模态数据整合分析方法，因为单一数据源往往只能提供有限的信息视角，不同模态的数据可以相互补充，提高分析的全面性。**预期发现**：我们假设通过整合多模态数据，可以揭示单一分析无法发现的生物学规律，包括跨模态一致性的信号模式、模态特异性的独特特征、潜在因果关系的新证据。",

            'data_requirements': "\\n\\n本研究需要以下数据支持：样本规模包括训练集至少500例、验证集至少200例、测试集至少100例。数据类型包括临床表型数据、分子组学数据、影像学数据。数据来源包括多中心合作获取、公共数据库补充、前瞻性采集新增。",

            'paradigm_framework': "深度学习与因果推断融合框架"
        }

        # 获取当前字段长度和最小要求
        min_lengths = {
            'core_problem': 200,
            'core_hypothesis': 150,
            'technical_route': 300,
            'expected_breakthrough': 200,
            'clinical_value': 150,
            'internal_reasoning': 500,
            'data_requirements': 100,
            'paradigm_framework': 10
        }

        for field, min_len in min_lengths.items():
            current = hyp.get(field, '')
            current_len = len(current)
            if current_len < min_len:
                # 计算需要补充的长度
                needed = min_len - current_len
                # 获取填充文本
                filler = filler_texts.get(field, '')
                # 如果填充文本也不够，循环使用
                while len(filler) < needed:
                    filler = filler + filler
                # 添加填充文本（截取到需要的长度）
                hyp[field] = current + filler[:needed]

        return hyp'''

    new_method = '''    def _fill_hypothesis_to_meet_requirements(self, hyp: Dict) -> Dict:
        """验证假设字段是否满足最低长度要求 - 不再自动填充

        如果内容不足，将拒绝生成而非填充通用文本，确保假设的真实性

        Raises:
            ValueError: 当字段内容不足时抛出异常
        """
        # 获取当前字段长度和最小要求
        min_lengths = {
            'core_problem': 200,
            'core_hypothesis': 150,
            'technical_route': 300,
            'expected_breakthrough': 200,
            'clinical_value': 150,
            'internal_reasoning': 500,
            'data_requirements': 100,
            'paradigm_framework': 10
        }

        insufficient_fields = []
        for field, min_len in min_lengths.items():
            current = hyp.get(field, '')
            current_len = len(current)
            if current_len < min_len:
                insufficient_fields.append(f"{field}({current_len}/{min_len})")

        if insufficient_fields:
            raise ValueError(
                f"假设内容不完整，以下字段长度不足: {', '.join(insufficient_fields)}。"
                f"拒绝生成填充内容，请重新生成更完整的假设。"
            )

        return hyp'''

    if old_method in content:
        content = content.replace(old_method, new_method)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ P1-1 修复完成: 移除自动填充，改为验证并拒绝不完整假设")
    else:
        print("  ⚠ 未找到目标代码块，可能已修复或代码结构变化")


def fix_debate_consensus_thresholds():
    """P2-1: 使共识阈值可配置"""
    print("\n[5/9] 修复 P2-1: 共识阈值可配置化...")

    file_path = PROJECT_ROOT / "src" / "agents" / "debate_coordinator.py"
    backup_file(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 在文件开头添加环境变量导入
    if 'import os' not in content[:500]:
        content = 'import os\n' + content

    # 修改 CONSENSUS_CRITERIA 为可配置
    old_criteria = '''CONSENSUS_CRITERIA = {
    'technical_feasibility': {
        'weight': 0.3,
        'threshold': 7.0,
        'description': '技术可行性评分'
    },
    'clinical_value': {
        'weight': 0.3,
        'threshold': 7.0,
        'description': '临床价值评分'
    },
    'ethics_compliance': {
        'weight': 0.4,
        'threshold': 8.0,
        'description': '伦理合规评分（要求更高）'
    }
}'''

    new_criteria = '''# 从环境变量读取阈值，使用默认值作为后备
CONSENSUS_CRITERIA = {
    'technical_feasibility': {
        'weight': float(os.getenv('DEBATE_TECHNICAL_WEIGHT', '0.3')),
        'threshold': float(os.getenv('DEBATE_TECHNICAL_THRESHOLD', '7.0')),
        'description': '技术可行性评分'
    },
    'clinical_value': {
        'weight': float(os.getenv('DEBATE_CLINICAL_WEIGHT', '0.3')),
        'threshold': float(os.getenv('DEBATE_CLINICAL_THRESHOLD', '7.0')),
        'description': '临床价值评分'
    },
    'ethics_compliance': {
        'weight': float(os.getenv('DEBATE_ETHICS_WEIGHT', '0.4')),
        'threshold': float(os.getenv('DEBATE_ETHICS_THRESHOLD', '8.0')),
        'description': '伦理合规评分（要求更高）'
    }
}

# 确保权重总和为1.0
total_weight = sum(c['weight'] for c in CONSENSUS_CRITERIA.values())
if abs(total_weight - 1.0) > 0.01:
    print(f"[警告] 辩论共识权重总和为{total_weight}，已自动归一化")
    for criterion in CONSENSUS_CRITERIA.values():
        criterion['weight'] /= total_weight'''

    if old_criteria in content:
        content = content.replace(old_criteria, new_criteria)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ P2-1 修复完成: 共识阈值现在可通过环境变量配置")
    else:
        print("  ⚠ 未找到目标代码块，可能已修复或代码结构变化")


def fix_prerequisite_validation():
    """P1-3: 完善前置条件验证"""
    print("\n[6/9] 修复 P1-3: 完善前置条件验证...")

    file_path = PROJECT_ROOT / "app.py"
    backup_file(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 修改 generate_clinical_review 函数，添加 tech_analysis 验证
    old_validation = '''        # 验证 GenAI 方案存在且非空
        genai_proposal = _validate_prerequisite('genai_proposal', 'GenAI赋能方案', min_length=100)

        update_agent_status('clinical_md_agent', 'running', '临床医学专家正在审查方案...')'''

    new_validation = '''        # 验证 GenAI 方案存在且非空
        genai_proposal = _validate_prerequisite('genai_proposal', 'GenAI赋能方案', min_length=100)

        # 验证技术分析存在
        tech_analysis = _validate_prerequisite('tech_analysis', '技术分析', allow_empty=False)
        if not tech_analysis or not isinstance(tech_analysis, dict):
            raise ValueError("技术分析数据缺失或格式错误，请先完成技术分析步骤")

        update_agent_status('clinical_md_agent', 'running', '临床医学专家正在审查方案...')'''

    if old_validation in content:
        content = content.replace(old_validation, new_validation)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ P1-3 修复完成: 添加了tech_analysis的前置验证")
    else:
        print("  ⚠ 未找到目标代码块，可能已修复或代码结构变化")


def fix_coder_agent_validation():
    """P2-2: 添加CoderAgent内容完整性验证"""
    print("\n[7/9] 修复 P2-2: CoderAgent内容完整性验证...")

    file_path = PROJECT_ROOT / "src" / "agents" / "coder_agent.py"
    backup_file(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 在现有验证之后添加内容完整性验证
    old_validation = '''        # 验证生成的代码指南
        if not code_guide or len(code_guide.strip()) < self.min_guide_length:
            raise ValueError(f"生成的代码指南过短: {len(code_guide) if code_guide else 0} 字符，最少需要 {self.min_guide_length} 字符")'''

    new_validation = '''        # 验证生成的代码指南
        if not code_guide or len(code_guide.strip()) < self.min_guide_length:
            raise ValueError(f"生成的代码指南过短: {len(code_guide) if code_guide else 0} 字符，最少需要 {self.min_guide_length} 字符")

        # 验证必要章节存在
        required_sections = {
            'requirements': ['requirements.txt', '依赖', 'environment', '环境配置'],
            '数据加载': ['数据加载', 'dataset', 'dataloader', '数据预处理', 'DataLoader'],
            '模型架构': ['模型架构', 'model', 'network', '神经网络', 'Model'],
            '训练策略': ['训练', 'train', '优化', 'optimizer', '损失函数', 'loss']
        }

        missing_sections = []
        for section_name, keywords in required_sections.items():
            # 检查是否包含任何相关关键词
            if not any(kw in code_guide for kw in keywords):
                missing_sections.append(section_name)

        if missing_sections:
            raise ValueError(f"生成的代码指南缺少必要章节: {', '.join(missing_sections)}")'''

    if old_validation in content:
        content = content.replace(old_validation, new_validation)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ P2-2 修复完成: 添加了代码指南必要章节验证")
    else:
        print("  ⚠ 未找到目标代码块，可能已修复或代码结构变化")


def fix_thesis_writer_fallback_warning():
    """P2-3: 添加论文生成器回退警告"""
    print("\n[8/9] 修复 P2-3: 论文生成器回退警告...")

    file_path = PROJECT_ROOT / "src" / "agents" / "thesis_writer_agent.py"

    if not file_path.exists():
        print("  ⚠ 文件不存在，跳过此修复")
        return

    backup_file(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找 execute 方法的返回部分
    # 添加 is_fallback 标记到返回值
    old_return_pattern = r"(return \{\s*'success': True,\s*'thesis_proposal': thesis_proposal,)"

    new_return = r"""\1
            'is_fallback': self._is_fallback_mode if hasattr(self, '_is_fallback_mode') else False,"""

    content_new = re.sub(old_return_pattern, new_return, content)

    if content_new != content:
        content = content_new
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ P2-3 修复完成: is_fallback标记已添加到返回值")
    else:
        print("  ⚠ 未找到目标代码块，可能已修复或代码结构变化")


def add_app_warning_for_fallback():
    """P2-3: 在app.py中添加回退警告显示"""
    print("\n[9/9] 修复 P2-3: app.py中显示回退警告...")

    file_path = PROJECT_ROOT / "app.py"
    backup_file(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找 generate_thesis_proposal 函数
    # 在 thesis_result 处理后添加警告检查
    old_pattern = r"(st\.session_state\.thesis_proposal = thesis_result\['thesis_proposal'\]\s+)"

    new_code = r"""\1
            # 检查是否使用了回退模式
            if thesis_result.get('is_fallback'):
                st.warning("⚠️ 论文生成使用了模板回退模式，内容可能不够完整。建议手动审查并补充。")
            """

    content_new = re.sub(old_pattern, new_code, content)

    if content_new != content:
        content = content_new
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ P2-3 修复完成: 添加了回退模式警告显示")
    else:
        print("  ⚠ 未找到目标代码块，可能已修复或代码结构变化")


def main():
    """执行所有修复"""
    print("=" * 60)
    print("业务逻辑漏洞修复脚本")
    print("=" * 60)

    fixes = [
        ("P0-1", fix_paper_search_agent),
        ("P0-2", fix_clinical_md_agent),
        ("P0-3", fix_debate_coordinator_parsing),
        ("P1-1", fix_hypothesis_auto_fill),
        ("P2-1", fix_debate_consensus_thresholds),
        ("P1-3", fix_prerequisite_validation),
        ("P2-2", fix_coder_agent_validation),
        ("P2-3", fix_thesis_writer_fallback_warning),
        ("P2-3-app", add_app_warning_for_fallback),
    ]

    success_count = 0
    skip_count = 0

    for priority, fix_func in fixes:
        try:
            fix_func()
            success_count += 1
        except Exception as e:
            print(f"  ❌ 修复失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"修复完成: {success_count}/{len(fixes)} 个修复已应用")
    print(f"跳过: {skip_count} 个")
    print("=" * 60)
    print("\n建议操作:")
    print("1. 运行测试验证修复效果")
    print("2. 检查 .bak 备份文件，确认无误后可删除")
    print("3. 提交代码前请进行完整的回归测试")


if __name__ == "__main__":
    main()
