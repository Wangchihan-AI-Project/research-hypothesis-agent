"""
文献侦察员智能体 (Search Agent)

负责根据研究方向搜索文献，使用全自动文献获取器获取全文，
分析内容，生��《文献深度调研报告》。
"""
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# 导入工具箱
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from tools import AutoPaperFetcher

# 导入 Claude API
import anthropic


class SearchAgent:
    """文献侦察员智能体"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化智能体

        Args:
            api_key: Anthropic API 密钥
        """
        # 配置 API
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.use_mock_mode = not self.api_key  # 无 API key 时使用模拟��式

        if self.api_key:
            base_url = os.getenv("ANTHROPIC_BASE_URL")
            if base_url:
                self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
            else:
                self.client = anthropic.Anthropic(api_key=self.api_key)

            self.model = "claude-3-5-sonnet-20241022"
        else:
            self.model = "mock"  # 模拟模式
            print("⚠️ 未检测到 API 密钥，将使用模拟模式运行")

        # 初始化工具
        self.fetcher = AutoPaperFetcher()

        # 输出目录
        self.output_dir = Path("reports")
        self.output_dir.mkdir(exist_ok=True)

    def execute(self, input_data: Dict) -> Dict:
        """
        执行文献侦察任务

        Args:
            input_data: 包含以下键的字典
                - research_topic: 研究方向（必需）
                - max_papers: 最大文献数（可选，默认10）
                - search_terms: 额外搜索词（可选）
                - output_filename: 输出文件名（可选）

        Returns:
            {
                'success': bool,
                'report_path': str,
                'papers_analyzed': int,
                'pdf_count': int,
                'abstract_count': int,
                'summary': str
            }
        """
        research_topic = input_data.get('research_topic', '')
        if not research_topic:
            return {
                'success': False,
                'error': '请提供研究方向'
            }

        max_papers = input_data.get('max_papers', 10)
        search_terms = input_data.get('search_terms', [])
        output_filename = input_data.get('output_filename', None)

        print(f"\n{'='*60}")
        print(f"📚 文献侦察员智能体 - 任务开始")
        print(f"{'='*60}")
        print(f"研究方向: {research_topic}")
        print(f"目标文献数: {max_papers}")

        # 第一步：生成搜索策略
        print(f"\n[步骤1] 制定搜索策略...")
        search_strategy = self._generate_search_strategy(research_topic, search_terms)
        print(f"搜索策略:\n{search_strategy}")

        # 第二步：识别文献
        print(f"\n[步骤2] 识别目标文献...")
        identifiers = self._identify_papers(search_strategy, max_papers)
        print(f"找到 {len(identifiers)} 篇候选文献")

        # 第三步：获取文献内容
        print(f"\n[步骤3] 获取文献全文（使用全自动文献获取器）...")
        papers_content = self._fetch_papers_content(identifiers)

        # 统计结果
        pdf_count = sum(1 for p in papers_content if p.get('source') == 'pdf')
        abstract_count = sum(1 for p in papers_content if 'fallback' in p.get('source', ''))

        print(f"\n内容获取完成:")
        print(f"  - PDF 全文: {pdf_count} 篇")
        print(f"  - 摘要备用: {abstract_count} 篇")

        # 第四步：生成调研报告
        print(f"\n[步骤4] 生成《文献深度调研报告》...")
        report_path = self._generate_report(
            research_topic,
            papers_content,
            search_strategy,
            output_filename
        )

        print(f"\n✅ 报告已保存: {report_path}")

        # 返回结果
        return {
            'success': True,
            'report_path': str(report_path),
            'papers_analyzed': len(papers_content),
            'pdf_count': pdf_count,
            'abstract_count': abstract_count,
            'summary': f"分析了 {len(papers_content)} 篇文献，其中 {pdf_count} 篇获取了全文，{abstract_count} 篇使用摘要模式。"
        }

    def _generate_search_strategy(self, research_topic: str, search_terms: List[str]) -> str:
        """生成搜索策略"""
        prompt = f"""你是一位专业的生物医学文献检索专家。

研究方向：{research_topic}

请制定一个高效的文献搜索策略，包括：
1. 核心关键词（中英文）
2. 数据库推荐（PubMed, Google Scholar等）
3. 搜索式示例

请以简洁的列表格式输出，不要有废话。

输出格式：
核心关键词：
- keyword1
- keyword2

数据库推荐：
- 数据库名称：理由

搜索式示例：
- PubMed: "search string"
"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            # 失败时使用简单策略
            return f"""核心关键词：
- {research_topic}

数据库推荐：
- PubMed: 生物医学文献首选数据库

搜索式示例：
- PubMed: {research_topic}
"""

    def _identify_papers(self, search_strategy: str, max_papers: int) -> List[str]:
        """
        根据搜索策略识别文献

        Args:
            search_strategy: 搜索策略
            max_papers: 最大文献数

        Returns:
            文献标识符列表（DOI 或 PMID）
        """
        identifiers = []

        # 从搜索策略中提取关键词
        keywords = []
        for line in search_strategy.split('\n'):
            line = line.strip()
            if line.startswith('-') or line.startswith('•'):
                keyword = line.lstrip('-•').strip()
                if keyword and len(keyword) > 2:
                    keywords.append(keyword)

        # 使用关键词搜索（如果关键词不够，使用研究主题）
        search_terms = keywords[:5] if keywords else [search_strategy.split('\n')[0]]

        # 使用 PubMed 搜索
        try:
            from Bio import Entrez
            Entrez.email = "research@example.com"

            for term in search_terms:
                try:
                    handle = Entrez.esearch(db="pubmed", term=term, retmax=max_papers)
                    result = Entrez.read(handle)
                    handle.close()

                    id_list = result.get('IdList', [])
                    if id_list:
                        identifiers.extend([f"PMID:{pmid}" for pmid in id_list])
                        print(f"  - 通过 '{term}' 找到 {len(id_list)} 篇")

                    if len(identifiers) >= max_papers:
                        break

                except Exception as e:
                    print(f"  - 搜索 '{term}' 失败: {e}")
                    continue

        except Exception as e:
            print(f"  - PubMed 搜索失败: {e}")

        # 去重
        seen = set()
        unique_identifiers = []
        for identifier in identifiers:
            if identifier not in seen:
                seen.add(identifier)
                unique_identifiers.append(identifier)

        return unique_identifiers[:max_papers]

    def _fetch_papers_content(self, identifiers: List[str]) -> List[Dict]:
        """
        使用全自动文献获取器获取文献内容

        Args:
            identifiers: 文献标识符列表

        Returns:
            文献内容列表
        """
        papers_content = []

        # 清理标识符（移除 PMID: 前缀等）
        cleaned_identifiers = []
        for identifier in identifiers:
            # 提取纯 PMID 或 DOI
            if identifier.startswith('PMID:'):
                cleaned_identifiers.append(identifier.replace('PMID:', ''))
            else:
                cleaned_identifiers.append(identifier)

        # 使用工具箱批量获取
        results = self.fetcher.batch_fetch(cleaned_identifiers, delay=0.5)

        # 处理结果
        for i, result in enumerate(results, 1):
            if result['success']:
                papers_content.append({
                    'index': i,
                    'identifier': result['identifier'],
                    'content': result['content'],
                    'source': result['source'],
                    'word_count': result['word_count'],
                    'warning': result.get('warning', ''),
                    'pdf_path': result.get('pdf_path', '')
                })

                # 显示状态
                if result['source'] == 'pdf':
                    print(f"  [{i}] {result['identifier'][:40]}... ✓ PDF ({result['word_count']} 字)")
                elif 'fallback' in result['source']:
                    print(f"  [{i}] {result['identifier'][:40]}... ⚠ 摘要 ({result['word_count']} 字)")
            else:
                print(f"  [{i}] {result['identifier'][:40]}... ✗ 失败")

        return papers_content

    def _generate_report(
        self,
        research_topic: str,
        papers_content: List[Dict],
        search_strategy: str,
        output_filename: Optional[str] = None
    ) -> Path:
        """
        生成《文献深度调研报告》

        Args:
            research_topic: 研究方向
            papers_content: 文献内容
            search_strategy: 搜索策略
            output_filename: 输出文件名

        Returns:
            报告文件路径
        """
        # 生成文件名
        if output_filename:
            if not output_filename.endswith('.md'):
                output_filename += '.md'
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_topic = ''.join(c for c in research_topic[:30] if c.isalnum() or c in ('-', '_'))
            output_filename = f"literature_review_{safe_topic}_{timestamp}.md"

        report_path = self.output_dir / output_filename

        # 生成报告
        report_content = self._format_report(
            research_topic,
            papers_content,
            search_strategy
        )

        # 保存报告
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        return report_path

    def _format_report(
        self,
        research_topic: str,
        papers_content: List[Dict],
        search_strategy: str
    ) -> str:
        """
        格式化报告内容

        Args:
            research_topic: 研究方向
            papers_content: 文献内容
            search_strategy: 搜索策略

        Returns:
            Markdown 格式的报告内容
        """
        # 统计信息
        total_papers = len(papers_content)
        pdf_count = sum(1 for p in papers_content if p.get('source') == 'pdf')
        abstract_count = total_papers - pdf_count

        # 生成报告
        report = f"""# 文献深度调研报告

**研究方向**: {research_topic}
**生成时间**: {datetime.now().strftime("%Y年%m月%d日 %H:%M")}

---

## 📊 执行摘要

本次调研共分析了 **{total_papers}** 篇相关文献：
- 获取完整 PDF 全文：**{pdf_count}** 篇
- 使用摘要模式：**{abstract_count}** 篇

---

## 🔍 搜索策略

{search_strategy}

---

## 📖 文献深度分析

"""

        # 为每篇文献生成分析
        for i, paper in enumerate(papers_content, 1):
            content = paper['content']
            source = paper['source']
            word_count = paper['word_count']
            warning = paper.get('warning', '')
            identifier = paper['identifier']

            # 来源标签
            if source == 'pdf':
                source_tag = "📄 PDF 全文"
            elif 'fallback' in source:
                source_tag = "📝 摘要模式"
            else:
                source_tag = f"📋 {source}"

            report += f"""
### 文献 {i}: {identifier}

**信息来源**: {source_tag}
**内容长度**: {word_count} 字
{'**⚠️ ' + warning + '**' if warning else ''}

---

**核心内容提取**:

{self._extract_core_content(content, source)}

---

"""

        # 添加总结部分
        report += self._generate_summary(papers_content, research_topic)

        report += f"""
---

## 📝 附录

**分析说明**:
- PDF 全文文献：已获取完整论文内容，包含实验方法、结果和讨论
- 摘要模式文献：受限于获取条件，仅包含论文摘要信息
- 建议优先参考获取了 PDF 全文的文献进行深入分析

**报告生成**: 文献侦察员智能体 (Search Agent)
**文件路径**: {str(self.output_dir.absolute())}

---
*此报告由 AI 自动生成，请人工核查关键信息后再使用。*
"""

        return report

    def _extract_core_content(self, content: str, source: str) -> str:
        """
        提取文献核心内容

        Args:
            content: 文献内容
            source: 内容来源

        Returns:
            提取的核心内容
        """
        # 如果是摘要模式，内容通常已经比较简洁
        if 'fallback' in source or len(content) < 2000:
            # 摘要模式：直接返回，清理格式
            return self._clean_abstract(content)
        else:
            # PDF 全文：使用 AI 提取关键信息
            return self._extract_from_full_text(content)

    def _clean_abstract(self, abstract: str) -> str:
        """清理摘要格式"""
        # 移除警告标记
        lines = abstract.split('\n')
        cleaned_lines = []
        for line in lines:
            if '【未能获取免费全文' in line:
                continue
            cleaned_lines.append(line.strip())
        return '\n'.join(cleaned_lines).strip()

    def _extract_from_full_text(self, full_text: str) -> str:
        """
        从全文中提取关键信息

        Args:
            full_text: 全文内容

        Returns:
            提取的关键信息
        """
        # 限制长度避免超长处理
        if len(full_text) > 15000:
            full_text = full_text[:15000] + "..."

        prompt = f"""你是文献分析专家。请从以下论文全文中提取关键信息。

论文内容（部分）:
{full_text}

请按以下格式提取（不要添加任何额外的解释）：

**研究背景**:
（简要说明研究背景和目的）

**研究方法**:
（实验设计、使用的技术手段、分析方法）

**主要发现**:
（核心实验结果和结论）

**创新点**:
（本研究的创新之处）

请只输出提取的内容，保持简洁。"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            # AI 提取失败，返回原始内容的前 2000 字
            return f"[AI 提取失败，显示原文前 2000 字]\n\n{full_text[:2000]}..."

    def _generate_summary(self, papers_content: List[Dict], research_topic: str) -> str:
        """
        生成调研总结

        Args:
            papers_content: 文献内容列表
            research_topic: 研究方向

        Returns:
            总结内容
        """
        if not papers_content:
            return "未找到可分析的文献。"

        # 收集所有内容的前 2000 字符用于总结
        combined_content = ""
        for paper in papers_content[:5]:  # 最多取 5 篇
            combined_content += f"\n\n文献 {paper['index']}: {paper['identifier']}\n{paper['content'][:1000]}"

        # 限制总长度
        if len(combined_content) > 8000:
            combined_content = combined_content[:8000] + "..."

        prompt = f"""你是科研分析专家。基于以下文献内容，生成一份研究领域的总结。

研究方向：{research_topic}

文献内容（汇总）:
{combined_content}

请生成以下内容（markdown 格式）：

### 研究现状概述
（简要描述当前领域的发展状况）

### 主要研究方向
（列举该领域的主要研究方向和热点）

### 技术方法汇总
（总结常用的技术方法和工具）

### 存在的挑战
（指出当前领域面临的主要挑战和未解决问题）

请以清晰的列表格式输出，不要有废话。"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            return f"### 研究总结\n\n{message.content[0].text}"
        except Exception as e:
            return "### 研究总结\n\n[总结生成失败，请手动分析文献内容]"


if __name__ == '__main__':
    # 测试文献侦察员
    from dotenv import load_dotenv
    load_dotenv()

    print("=" * 60)
    print("文献侦察员智能体 - 独立测试")
    print("=" * 60)

    agent = SearchAgent()

    # 测试任务
    test_task = {
        'research_topic': 'CRISPR 基因编辑治疗遗传病',
        'max_papers': 3
    }

    print(f"\n测试任务: {test_task['research_topic']}")
    print(f"目标文献数: {test_task['max_papers']}")

    result = agent.execute(test_task)

    if result['success']:
        print(f"\n✅ 任务完成!")
        print(f"报告路径: {result['report_path']}")
        print(f"分析文献数: {result['papers_analyzed']}")
        print(f"PDF 全文: {result['pdf_count']}")
        print(f"摘要模式: {result['abstract_count']}")
        print(f"\n{result['summary']}")
    else:
        print(f"\n❌ 任务失败: {result.get('error')}")

    print("\n" + "=" * 60)
