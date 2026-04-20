"""
技术分析智能体
分析实现假设所需的技术和方法
"""
from typing import Dict, List
import json
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import BaseAgent
from core.database import Hypothesis
from utils.llm_utils import SafeExtractor, LLMParseError, RetryExecutor
import anthropic


class TechAnalysisAgent(BaseAgent):
    """技术分析智能体"""

    def __init__(self):
        super().__init__("技术分析智能体", agent_type="tech_analysis")
        # 支持自定义 base_url（中转站）
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        # 使用防弹解析器
        self.extractor = SafeExtractor()
        self.retry_executor = RetryExecutor(max_retries=3)
        self.max_retries = 3

    def execute(self, input_data: Dict) -> Dict:
        """
        执行技术分析

        Args:
            input_data: 包含以下键的字典
                - hypothesis_id: 假设ID（必需）
                - hypothesis_data: 假设数据（必需）
                - validation_result: 验证结果（可选）

        Returns:
            技术分析结果
        """
        hypothesis_id = input_data.get('hypothesis_id')
        hypothesis_data = input_data.get('hypothesis_data')
        validation_result = input_data.get('validation_result', {})

        if not hypothesis_data:
            return {
                'success': False,
                'error': '没有提供假设数据',
                'analysis': None
            }

        # 执行技术分析
        analysis_result = self._analyze_technology(
            hypothesis_data,
            validation_result
        )

        # 更新数据库
        if hypothesis_id:
            with self.db_manager.get_session() as session:
                hypothesis = session.query(Hypothesis).filter_by(
                    id=hypothesis_id
                ).first()

                if hypothesis:
                    hypothesis.technical_analysis = json.dumps(
                        analysis_result,
                        ensure_ascii=False
                    )
                    hypothesis.required_techniques = json.dumps(
                        analysis_result.get('required_techniques', []),
                        ensure_ascii=False
                    )
                    hypothesis.estimated_timeline = analysis_result.get('timeline', '')

        return {
            'success': True,
            'analysis': analysis_result,
            'hypothesis_id': hypothesis_id
        }

    def _analyze_technology(
        self,
        hypothesis: Dict,
        validation: Dict
    ) -> Dict:
        """
        使用Claude分析技术需求

        Args:
            hypothesis: 假设数据
            validation: 验证结果

        Returns:
            技术分析结果

        Raises:
            RuntimeError: 解析失败时抛出异常
        """
        # 构建分析提示词
        prompt = f"""你是一位在计算生物学领域有丰富经验的技术专家。
需要分析以下研究假设的技术实现方案。

假设信息：
标题: {hypothesis.get('title', 'N/A')}
描述: {hypothesis.get('description', 'N/A')}
理论依据: {hypothesis.get('rationale', 'N/A')}
新颖性说明: {hypothesis.get('novelty', 'N/A')}

验证结果：
可行性评分: {validation.get('feasibility_score', 'N/A')}
新颖性评分: {validation.get('novelty_score', 'N/A')}
技术性评分: {validation.get('technical_score', 'N/A')}
主要挑战: {', '.join(validation.get('challenges', []))}
主要优势: {', '.join(validation.get('strengths', []))}

请从以下几个方面进行详细分析：

1. **核心技术栈**:
   - 数据处理技术（数据获取、清洗、预处理）
   - 分析方法技术（算法、模型、分析流程）
   - 实现工具技术（编程语言、框架、工具包）
   - 验证技术（实验设计、验证方法、评估指标）

2. **技术实现路径**:
   - 第一阶段：数据准备阶段
   - 第二阶段：模型开发阶段
   - 第三阶段：验证测试阶段
   - 第四阶段：应用部署阶段

3. **技术难点与解决方案**:
   - 主要技术难点
   - 可能的解决方案
   - 需要攻关的技术点

4. **资源需求**:
   - 计算资源需求
   - 数据资源需求
   - 人力资源需求
   - 时间预估

5. **技术风险评估**:
   - 技术风险点
   - 风险应对策略
   - 备选方案

请以JSON格式输出：
{{
  "required_techniques": ["技术1", "技术2", ...],
  "tech_stack": {{
    "data_processing": ["技术列表"],
    "analysis_methods": ["技术列表"],
    "tools": ["工具列表"],
    "validation": ["验证方法"]
  }},
  "implementation_path": [
    {{
      "phase": "阶段名称",
      "tasks": ["任务列表"],
      "duration": "预计时间",
      "key_outputs": ["关键输出"]
    }}
  ],
  "technical_challenges": [
    {{
      "challenge": "难点描述",
      "solution": "解决方案",
      "priority": "高/中/低"
    }}
  ],
  "resource_requirements": {{
    "computational": "计算资源需求",
    "data": "数据需求",
    "human": "人力需求",
    "budget_estimate": "预算预估"
  }},
  "timeline": "总体时间预估",
  "risk_assessment": [
    {{
      "risk": "风险描述",
      "impact": "影响程度",
      "mitigation": "应对策略"
    }}
  ],
  "alternative_approaches": ["备选方案"],
  "recommendations": ["具体建议"]
}}

请开始分析："""

        # 使用重试机制调用 API
        for attempt in range(self.max_retries):
            try:
                print(f"[技术分析] 第 {attempt + 1}/{self.max_retries} 次尝试生成分析...")

                # 调用Claude API
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                # 解析返回结果
                response_text = message.content[0].text

                # 使用 SafeExtractor 提取 JSON
                result = self.extractor.safe_extract_json(response_text)

                if result:
                    print(f"[技术分析] 分析成功，长度: {len(response_text)} 字符")
                    return result
                else:
                    raise ValueError("SafeExtractor 无法从响应中提取有效 JSON")

            except Exception as e:
                print(f"[技术分析] 尝试 {attempt + 1} 失败: {e}")
                if attempt == self.max_retries - 1:
                    # 最后一次尝试失败，抛出异常
                    raise RuntimeError(f"技术分析失败：经过 {self.max_retries} 次尝试后仍无法解析响应。最后错误: {e}")
                # 指数退避重试
                time.sleep(2 ** attempt)

        # 理论上不会到达这里，但为了类型检查
        raise RuntimeError("技术分析失败：重试次数耗尽")

    def get_full_report(self, hypothesis_id: int) -> Dict:
        """
        获取完整的技术分析报告

        Args:
            hypothesis_id: 假设ID

        Returns:
            包含假设、验证和技术分析的完整报告
        """
        with self.db_manager.get_session() as session:
            hypothesis = session.query(Hypothesis).filter_by(
                id=hypothesis_id
            ).first()

            if not hypothesis:
                return None

            report = {
                'hypothesis': {
                    'id': hypothesis.id,
                    'title': hypothesis.title,
                    'description': hypothesis.description,
                    'rationale': hypothesis.rationale,
                    'novelty': hypothesis.novelty,
                    'expected_value': hypothesis.expected_value
                },
                'validation': {
                    'feasibility_score': hypothesis.feasibility_score,
                    'novelty_score': hypothesis.novelty_score,
                    'technical_score': hypothesis.technical_score,
                    'validation_notes': hypothesis.validation_notes,
                    'validation_status': hypothesis.validation_status
                },
                'technical_analysis': json.loads(hypothesis.technical_analysis) if hypothesis.technical_analysis else {},
                'source_papers': [
                    {
                        'pmid': paper.pmid,
                        'title': paper.title,
                        'journal': paper.journal,
                        'publication_date': paper.publication_date
                    }
                    for paper in hypothesis.papers
                ]
            }

            return report

    def __del__(self):
        """析构函数"""
        pass  # 不需要关闭session，由db_manager统一管理


if __name__ == '__main__':
    # 测试智能体
    from dotenv import load_dotenv
    load_dotenv()

    agent = TechAnalysisAgent()
    test_hypothesis = {
        'title': '基于深度学习的基因组变异检测方法',
        'description': '提出一种新的深度学习架构',
        'rationale': '基于现有研究成果',
        'novelty': '首次应用Transformer架构'
    }
    test_validation = {
        'feasibility_score': 8,
        'novelty_score': 9,
        'technical_score': 7,
        'challenges': ['数据量需求大', '模型训练时间长']
    }

    result = agent.execute({
        'hypothesis_id': None,
        'hypothesis_data': test_hypothesis,
        'validation_result': test_validation
    })

    if result['success']:
        analysis = result['analysis']
        print(f"所需技术: {analysis.get('required_techniques', [])}")
        print(f"时间预估: {analysis.get('timeline', '')}")
        print(f"\n实施路径:")
        for phase in analysis.get('implementation_path', []):
            print(f"  - {phase['phase']}: {phase['duration']}")
    else:
        print(f"分析失败: {result.get('error')}")