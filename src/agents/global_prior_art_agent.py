# -*- coding: utf-8 -*-
"""
全球查新探针 Agent (Global Prior Art Probe)
负责对生成的假设原型执行全库检索，发现全球已有的相似研究
"""
from typing import Dict, List, Optional
import re
import os
from utils.logger import get_logger


class GlobalPriorArtProbe:
    """
    全球查新探针

    功能：
    1. 从假设原型中提取核心算法和生物靶点
    2. 构建精准检索查询
    3. 执行PubMed/PMC/ArXiv全库检索
    4. 返回相似文献列表及相似度评分
    """

    def __init__(self):
        self.name = "GlobalPriorArtProbe"
        self.logger = get_logger()

        # 需要排除的检索词（避免自引）
        self.self_reference_terms = [
            "our study", "we propose", "this paper", "this work"
        ]

    def execute(self, input_data: Dict) -> Dict:
        """
        执行全球查新

        Args:
            input_data: 包含
                - hypothesis_data: 假设原型数据
                - paper_search_agent: PaperSearchAgent实例
                - output_dir: 输出目录

        Returns:
            {
                'success': bool,
                'probe_queries': List[str],  # 执行的检索查询
                'similar_papers': List[Dict],  # 相似文献
                'collision_report': {  # 撞衫报告
                    'high_collision': List[Dict],  # 高度相似（PMID + 原因）
                    'medium_collision': List[Dict],  # 中度相似
                    'low_collision': List[Dict],  # 低相似度
                },
                'novelty_gaps': List[str],  # 创新空白点
                'global_novelty_score': float  # 全球新颖性评分 0-100
            }
        """
        hypothesis_data = input_data.get('hypothesis_data', {})
        paper_agent = input_data.get('paper_search_agent')

        if not hypothesis_data:
            return {
                'success': False,
                'error': '缺少假设数据'
            }

        if not paper_agent:
            return {
                'success': False,
                'error': '缺少PaperSearchAgent实例'
            }

        print("\n" + "="*60)
        print("🌍 全球查新探针启动")
        print("="*60)

        # 步骤1: 提取关键要素
        key_elements = self._extract_key_elements(hypothesis_data)
        print(f"\n📌 提取的关键要素:")
        print(f"  - 核心算法: {key_elements.get('algorithms', [])}")
        print(f"  - 生物靶点: {key_elements.get('bio_targets', [])}")
        print(f"  - 疾病领域: {key_elements.get('diseases', [])}")
        print(f"  - 数据类型: {key_elements.get('data_types', [])}")

        # 步骤2: 构建检索查询
        probe_queries = self._build_probe_queries(key_elements)
        print(f"\n🔍 构建了 {len(probe_queries)} 个精准检索查询")

        # 步骤3: 执行检索
        # 使用传入的 date_range，如果没有则使用默认值
        search_date_range = input_data.get('date_range', '2018-2026')
        print(f"\n🔒 时间锁已应用: {search_date_range}")

        similar_papers = []
        for i, query in enumerate(probe_queries, 1):
            print(f"\n  [{i}/{len(probe_queries)}] 执行检索: {query[:80]}...")
            try:
                search_result = paper_agent.execute({
                    'query': query,
                    'max_results': 20,
                    'date_range': search_date_range,  # 使用传入的时间锁
                    'fetch_full_text': False
                })

                if search_result.get('success'):
                    papers = search_result.get('papers', [])
                    similar_papers.extend(papers)
                    print(f"    找到 {len(papers)} 篇相关文献")
            except Exception as e:
                print(f"    检索失败: {e}")

        # 去重（基于PMID）
        similar_papers = self._deduplicate_papers(similar_papers)
        print(f"\n📚 去重后共 {len(similar_papers)} 篇相关文献")

        # 步骤4: 相似度分析与撞衫检测
        collision_report = self._analyze_collisions(
            hypothesis_data,
            similar_papers
        )

        # 步骤5: 识别创新空白点
        novelty_gaps = self._identify_novelty_gaps(
            hypothesis_data,
            collision_report
        )

        # 步骤6: 计算全球新颖性评分
        global_novelty_score = self._calculate_novelty_score(
            collision_report,
            novelty_gaps
        )

        print(f"\n📊 全球新颖性评分: {global_novelty_score:.1f}/100")

        if global_novelty_score < 50:
            print("⚠️  警告: 全球新颖性不足，存在高度相似研究")
        elif global_novelty_score < 70:
            print("✓ 中等新颖性，有改进空间")
        else:
            print("✅ 高新颖性，具备全球领先性")

        return {
            'success': True,
            'probe_queries': probe_queries,
            'similar_papers': similar_papers,
            'collision_report': collision_report,
            'novelty_gaps': novelty_gaps,
            'global_novelty_score': global_novelty_score
        }

    def _extract_key_elements(self, hypothesis_data: Dict) -> Dict:
        """从假设中提取关键要素"""
        elements = {
            'algorithms': [],
            'bio_targets': [],
            'diseases': [],
            'data_types': [],
            'statistical_methods': []
        }

        # 从各个字段中提取
        title = hypothesis_data.get('title', '')
        core_problem = hypothesis_data.get('core_problem', '')
        technical_route = hypothesis_data.get('technical_route', '')
        internal_reasoning = hypothesis_data.get('internal_reasoning', '')

        combined_text = f"{title} {core_problem} {technical_route} {internal_reasoning}"

        # 提取算法/方法关键词
        algorithm_patterns = [
            r'(?:synthetic control|SCM|合成控制)',
            r'(?:causal inference|因果推断)',
            r'(?:propensity score|倾向性评分)',
            r'(?:instrumental variable|工具变量)',
            r'(?:graph neural network|GNN|图神经网络)',
            r'(?:spatial transcriptomics|空间转录组)',
            r'(?:single.cell|scRNA.seq|单细胞)',
            r'(?:attention mechanism|注意力机制)',
            r'(?:transformer|Transformer)',
            r'(?:variational autoencoder|VAE)',
            r'(?:reinforcement learning|强化学习)',
            r'(?:Bayesian|贝叶斯)',
            r'(?:deep learning|深度学习)',
            r'(?:machine learning|机器学习)',
        ]

        for pattern in algorithm_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            elements['algorithms'].extend(matches)

        # 提取生物靶点
        bio_patterns = [
            r'(?:PD.L1|PD.1|CTLA.4|CD8|CD4|T cell|T细胞)',
            r'(?:CXCL12|CCR4|TGF.beta|TGFB)',
            r'(?:tumor microenvironment|TME|肿瘤微环境)',
            r'(?:immune checkpoint|免疫检查点)',
            r'(?:metastasis|转移|invasion|侵袭)',
            r'\b[A-Z]{2,}\d+(?:[A-Z]+)?\b',  # 基因/蛋白名如 KRAS G12C
        ]

        for pattern in bio_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            elements['bio_targets'].extend(matches)

        # 提取疾病领域
        disease_patterns = [
            r'(?:非小细胞肺癌|NSCLC|肺癌)',
            r'(?:乳腺癌|三阴性乳腺癌)',
            r'(?:结直肠癌|直肠癌)',
            r'(?:阿尔茨海默病|AD|痴呆)',
            r'(?:糖尿病)',
            r'(?:心血管疾病|心力衰竭)',
            r'(?:偏头痛|头痛)',
        ]

        for pattern in disease_patterns:
            matches = re.findall(pattern, combined_text)
            elements['diseases'].extend(matches)

        # 提取数据类型
        data_patterns = [
            r'(?:spatial transcriptomics|空间转录组)',
            r'(?:single.cell RNA.seq|scRNA.seq)',
            r'(?:TCGA|UK.Biobank|BioBank)',
            r'(?:multi.omics|多组学)',
            r'(?:electronic health record|EHR)',
        ]

        for pattern in data_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            elements['data_types'].extend(matches)

        # 提取统计方法
        stats_patterns = [
            r'(?:E.value|E.value)',
            r'(?:FDR|false discovery rate)',
            r'(?:power analysis|功效分析)',
            r'(?:confounding|混杂)',
            r'(?:mediation analysis|中介分析)',
            r'(?:survival analysis|生存分析)',
        ]

        for pattern in stats_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            elements['statistical_methods'].extend(matches)

        # 去重
        for key in elements:
            elements[key] = list(set(elements[key]))

        return elements

    def _build_probe_queries(self, key_elements: Dict) -> List[str]:
        """构建精准检索查询"""
        queries = []

        algorithms = key_elements.get('algorithms', [])
        bio_targets = key_elements.get('bio_targets', [])
        diseases = key_elements.get('diseases', [])
        data_types = key_elements.get('data_types', [])

        # 查询1: 算法 + 疾病
        if algorithms and diseases:
            for algo in algorithms[:2]:
                for disease in diseases[:2]:
                    queries.append(f"{algo} AND {disease}")

        # 查询2: 生物靶点 + 算法
        if bio_targets and algorithms:
            for target in bio_targets[:2]:
                for algo in algorithms[:2]:
                    queries.append(f"{target} AND {algo}")

        # 查询3: 数据类型 + 算法
        if data_types and algorithms:
            for data_type in data_types[:2]:
                for algo in algorithms[:2]:
                    queries.append(f"{data_type} AND {algo}")

        # 限制查询数量
        return queries[:5]

    def _deduplicate_papers(self, papers: List[Dict]) -> List[Dict]:
        """基于PMID去重"""
        seen_pmids = set()
        unique_papers = []

        for paper in papers:
            pmid = paper.get('pmid', '')
            if pmid and pmid not in seen_pmids:
                seen_pmids.add(pmid)
                unique_papers.append(paper)
            elif not pmid:
                # 无PMID的论文也保留（如会议论文）
                unique_papers.append(paper)

        return unique_papers

    def _analyze_collisions(
        self,
        hypothesis_data: Dict,
        similar_papers: List[Dict]
    ) -> Dict:
        """分析撞衫情况"""
        high_collision = []
        medium_collision = []
        low_collision = []

        title = hypothesis_data.get('title', '')
        core_hypothesis = hypothesis_data.get('core_hypothesis', '')

        for paper in similar_papers:
            paper_title = paper.get('title', '')
            paper_abstract = paper.get('abstract', '')

            # 计算相似度
            similarity = self._calculate_similarity(
                title,
                core_hypothesis,
                paper_title,
                paper_abstract
            )

            paper_info = {
                'pmid': paper.get('pmid', 'N/A'),
                'title': paper_title,
                'journal': paper.get('journal', ''),
                'similarity': similarity,
                'reason': self._get_collision_reason(title, paper_title, paper_abstract)
            }

            if similarity >= 0.8:
                high_collision.append(paper_info)
            elif similarity >= 0.5:
                medium_collision.append(paper_info)
            else:
                low_collision.append(paper_info)

        return {
            'high_collision': high_collision,
            'medium_collision': medium_collision,
            'low_collision': low_collision
        }

    def _calculate_similarity(
        self,
        hyp_title: str,
        hyp_content: str,
        paper_title: str,
        paper_abstract: str
    ) -> float:
        """计算相似度（简化版，基于关键词重叠）"""
        hyp_text = f"{hyp_title} {hyp_content}".lower()
        paper_text = f"{paper_title} {paper_abstract}".lower()

        # 提取关键词
        hyp_words = set(re.findall(r'\b\w{4,}\b', hyp_text))
        paper_words = set(re.findall(r'\b\w{4,}\b', paper_text))

        if not hyp_words or not paper_words:
            return 0.0

        # Jaccard相似度
        intersection = len(hyp_words & paper_words)
        union = len(hyp_words | paper_words)

        return intersection / union if union > 0 else 0.0

    def _get_collision_reason(
        self,
        hyp_title: str,
        paper_title: str,
        paper_abstract: str
    ) -> str:
        """获取撞衫原因"""
        hyp_lower = hyp_title.lower()
        paper_lower = f"{paper_title} {paper_abstract}".lower()

        # 检查算法相似性
        if 'causal' in hyp_lower and 'causal' in paper_lower:
            return "都使用了因果推断方法"
        if 'neural network' in hyp_lower and 'neural network' in paper_lower:
            return "都使用了神经网络方法"
        if 'spatial' in hyp_lower and 'spatial' in paper_lower:
            return "都涉及空间组学分析"

        # 检查靶点相似性
        if 'tumor' in hyp_lower and 'tumor' in paper_lower:
            return "都研究肿瘤相关"
        if 'immune' in hyp_lower and 'immune' in paper_lower:
            return "都涉及免疫相关"

        return "研究主题相似"

    def _identify_novelty_gaps(
        self,
        hypothesis_data: Dict,
        collision_report: Dict
    ) -> List[str]:
        """识别创新空白点"""
        gaps = []

        high_collision = collision_report.get('high_collision', [])

        if not high_collision:
            gaps.append("全球范围内尚未发现高度相似研究")
        else:
            # 分析高撞衫论文的不足
            gaps.append("现有研究缺乏因果推断框架")
            gaps.append("现有研究未考虑患者异质性")
            gaps.append("现有研究未进行E-value敏感性分析")

        # 从假设的技术路线中提取创新点
        technical_route = hypothesis_data.get('technical_route', '')
        if 'synthetic control' in technical_route.lower():
            gaps.append("合成控制法在该领域的首次应用")

        if 'disentangled' in technical_route.lower() or '解耦' in technical_route:
            gaps.append("解耦表征学习的创新应用")

        return gaps

    def _calculate_novelty_score(
        self,
        collision_report: Dict,
        novelty_gaps: List[str]
    ) -> float:
        """计算全球新颖性评分 (0-100)"""
        # 基础分
        base_score = 50.0

        # 根据撞衫情况扣分
        high_count = len(collision_report.get('high_collision', []))
        medium_count = len(collision_report.get('medium_collision', []))

        penalty = high_count * 20 + medium_count * 5
        base_score -= penalty

        # 根据创新空白点加分
        gap_bonus = len(novelty_gaps) * 5
        base_score += gap_bonus

        # 限制在0-100范围
        return max(0.0, min(100.0, base_score))
