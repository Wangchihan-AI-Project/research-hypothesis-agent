"""
报告导出工具
导出研究报告为Markdown格式
"""
import os
from datetime import datetime
from typing import Dict


class ReportExporter:
    """报告导出器"""

    def __init__(self, output_dir='./reports'):
        """
        初始化导出器

        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export_to_markdown(self, report: Dict) -> str:
        """
        导出为Markdown格式

        Args:
            report: 报告数据

        Returns:
            输出文件路径
        """
        hypothesis = report['hypothesis']
        validation = report['validation']
        analysis = report.get('technical_analysis', {})
        papers = report.get('source_papers', [])

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = hypothesis['title'][:50].replace(' ', '_').replace('/', '_')
        filename = f"report_{safe_title}_{timestamp}.md"
        filepath = os.path.join(self.output_dir, filename)

        # 构建Markdown内容
        content = self._build_markdown(hypothesis, validation, analysis, papers)

        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return filepath

    def _build_markdown(self, hypothesis, validation, analysis, papers) -> str:
        """构建Markdown内容"""
        md_content = f"""# 研究假设分析报告

**生成日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. 假设信息

**标题**: {hypothesis['title']}

**描述**:
{hypothesis['description']}

**理论依据**:
{hypothesis['rationale']}

**新颖性说明**:
{hypothesis['novelty']}

**预期价值**:
{hypothesis.get('expected_value', 'N/A')}

---

## 2. 验证评估

### 评分结果

| 评估维度 | 评分 | 说明 |
|---------|------|------|
| **可行性** | {validation.get('feasibility_score', 'N/A')}/10 | {validation.get('feasibility_notes', '技术可行性与资源需求评估')} |
| **新颖性** | {validation.get('novelty_score', 'N/A')}/10 | {validation.get('novelty_notes', '理论与方法创新性评估')} |
| **技术性** | {validation.get('technical_score', 'N/A')}/10 | {validation.get('technical_notes', '技术难度与先进性评估')} |

**验证状态**: {validation.get('status', 'N/A')}

### 评估说明

{validation.get('notes', '综合评估说明')}

### 主要优势

{self._format_list(validation.get('strengths', []))}

### 主要挑战

{self._format_list(validation.get('challenges', []))}

### 改进建议

{self._format_list(validation.get('suggestions', []))}

---

## 3. 技术分析

### 所需核心技术

{self._format_list(analysis.get('required_techniques', []))}

### 技术栈详情

#### 数据处理技术
{self._format_list(analysis.get('tech_stack', {}).get('data_processing', []))}

#### 分析方法
{self._format_list(analysis.get('tech_stack', {}).get('analysis_methods', []))}

#### 工具框架
{self._format_list(analysis.get('tech_stack', {}).get('tools', []))}

#### 验证方法
{self._format_list(analysis.get('tech_stack', {}).get('validation', []))}

### 实施路径

{self._format_implementation_path(analysis.get('implementation_path', []))}

### 资源需求

- **计算资源**: {analysis.get('resource_requirements', {}).get('computational', '待评估')}
- **数据资源**: {analysis.get('resource_requirements', {}).get('data', '待评估')}
- **人力资源**: {analysis.get('resource_requirements', {}).get('human', '待评估')}
- **预算预估**: {analysis.get('resource_requirements', {}).get('budget_estimate', '待评估')}

### 时间预估

**总体时间**: {analysis.get('timeline', '待评估')}

---

## 4. 来源论文

{self._format_papers(papers)}

---

## 5. 风险评估

{self._format_risks(analysis.get('risk_assessment', []))}

---

## 6. 备选方案

{self._format_list(analysis.get('alternative_approaches', []))}

---

## 7. 专家建议

{self._format_list(analysis.get('recommendations', []))}

---

**报告生成完毕**

*本报告由研究假设生成系统自动生成，仅供参考，实际研究需人工进一步验证和调整。*
"""
        return md_content

    def _format_list(self, items: list) -> str:
        """格式化列表"""
        if not items:
            return "无"
        return '\n'.join([f"- {item}" for item in items])

    def _format_implementation_path(self, phases: list) -> str:
        """格式化实施路径"""
        if not phases:
            return "待详细规划"

        formatted = []
        for i, phase in enumerate(phases, 1):
            formatted.append(f"\n### 阶段{i}: {phase.get('phase', '未知')}")

            if phase.get('tasks'):
                formatted.append("\n**主要任务**:")
                formatted.append(self._format_list(phase['tasks']))

            if phase.get('duration'):
                formatted.append(f"\n**预计时间**: {phase['duration']}")

            if phase.get('key_outputs'):
                formatted.append("\n**关键输出**:")
                formatted.append(self._format_list(phase['key_outputs']))

        return '\n'.join(formatted)

    def _format_papers(self, papers: list) -> str:
        """格式化论文列表"""
        if not papers:
            return "无来源论文"

        formatted = []
        for i, paper in enumerate(papers, 1):
            formatted.append(f"\n### 论文{i}")
            formatted.append(f"- **标题**: {paper.get('title', 'N/A')}")
            formatted.append(f"- **PMID**: {paper.get('pmid', 'N/A')}")
            formatted.append(f"- **期刊**: {paper.get('journal', 'N/A')}")
            formatted.append(f"- **发表日期**: {paper.get('publication_date', 'N/A')}")
            if paper.get('doi'):
                formatted.append(f"- **DOI**: {paper['doi']}")

        return '\n'.join(formatted)

    def _format_risks(self, risks: list) -> str:
        """格式化风险评估"""
        if not risks:
            return "风险评估待完善"

        formatted = []
        for i, risk in enumerate(risks, 1):
            formatted.append(f"\n### 风险{i}")
            formatted.append(f"- **风险描述**: {risk.get('risk', 'N/A')}")
            formatted.append(f"- **影响程度**: {risk.get('impact', 'N/A')}")
            formatted.append(f"- **应对策略**: {risk.get('mitigation', 'N/A')}")

        return '\n'.join(formatted)


if __name__ == '__main__':
    # 测试导出器
    test_report = {
        'hypothesis': {
            'title': '基于深度学习的基因组变异检测新方法',
            'description': '提出一种新的深度学习架构用于基因组变异检测',
            'rationale': '基于Transformer架构的优势',
            'novelty': '首次将Transformer应用于此领域',
            'expected_value': '提高准确率10-15%'
        },
        'validation': {
            'feasibility_score': 8,
            'novelty_score': 9,
            'technical_score': 7,
            'status': 'approved',
            'notes': '具有较高的可行性和新颖性',
            'strengths': ['理论基础扎实', '技术路径清晰'],
            'challenges': ['数据需求量大', '计算资源要求高'],
            'suggestions': ['先在小规模数据验证', '考虑分布式训练']
        },
        'technical_analysis': {
            'required_techniques': ['Python', 'TensorFlow', 'BioPython'],
            'timeline': '6-12个月',
            'tech_stack': {
                'data_processing': ['数据清洗', '格式转换'],
                'analysis_methods': ['深度学习', '基因组分析'],
                'tools': ['TensorFlow', 'PyTorch'],
                'validation': ['交叉验证', 'A/B测试']
            },
            'resource_requirements': {
                'computational': 'GPU集群',
                'data': '10000+样本',
                'human': '2-3人团队',
                'budget_estimate': '50-100万'
            },
            'risk_assessment': [
                {
                    'risk': '数据获取困难',
                    'impact': '高',
                    'mitigation': '与医院合作获取数据'
                }
            ],
            'alternative_approaches': ['传统机器学习方法'],
            'recommendations': ['建议分阶段实施']
        },
        'source_papers': [
            {
                'pmid': '12345678',
                'title': 'Deep Learning in Genomics',
                'journal': 'Nature Biotechnology',
                'publication_date': '2024-01-15'
            }
        ]
    }

    exporter = ReportExporter()
    filename = exporter.export_to_markdown(test_report)
    print(f"报告已导出到: {filename}")