# -*- coding: utf-8 -*-
"""
V7.0 动态知识图谱模块

从 ChromaDB 提取文献数据，构建实体-关系网络图
支持基于 pyvis 和 streamlit-agraph 的可视化

V7.0 新增：
- 基因白名单验证（防止幽灵节点污染）
- 实体置信度标记
"""
import os
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from collections import defaultdict, Counter
import json

logger = logging.getLogger(__name__)

# 尝试导入依赖
try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

try:
    from pyvis.network import Network
    HAS_PYVIS = True
except ImportError:
    HAS_PYVIS = False

try:
    from streamlit_agraph import agraph, Node, Edge, Config
    from streamlit_agraph.elements import Layout
    HAS_AGRAPH = True
except ImportError:
    HAS_AGRAPH = False

# V7.0: 尝试导入基因白名单验证器
try:
    from utils.gene_whitelist_validator import GeneWhitelistValidator, get_gene_validator
    HAS_GENE_VALIDATOR = True
except ImportError:
    HAS_GENE_VALIDATOR = False
    logger.warning("[knowledge_graph V7.0] 基因白名单验证器未找到，使用基础验证")


class EntityExtractor:
    """
    V7.0 实体提取器 - 从文献中提取关键实体

    新增：基因白名单验证，防止幽灵节点污染
    """

    # 生物医学领域常见关键词模式
    BIOMEDICAL_PATTERNS = {
        'genes': r'\b[A-Z]{2,5}\b',  # 基因名（如 TP53, BRCA1）
        'diseases': r'\b(?:cancer|tumor|carcinoma|syndrome|disease|disorder|leukemia|lymphoma|melanoma)\b',
        'methods': r'\b(?:sequencing|microarray|PCR|RNA-seq|scRNA-seq|ChIP-seq|ATAC-seq|CRISPR|knockout|overexpression)\b',
        'cells': r'\b(?:T-cell|B-cell|macrophage|neuron|stem cell|immune cell|epithelial|fibroblast)\b',
        'pathways': r'\b(?:pathway|signaling|cascade|activation|inhibition|regulation|apoptosis|proliferation)\b',
    }

    # 常见生物学术语列表（扩展）
    BIO_KEYWORDS = {
        'omics': ['genomics', 'transcriptomics', 'proteomics', 'metabolomics', 'epigenomics'],
        'analysis': ['differential', 'enrichment', 'clustering', 'classification', 'regression', 'network'],
        'technologies': ['NGS', 'microarray', 'mass spectrometry', 'flow cytometry', 'imaging'],
        'concepts': ['biomarker', 'prognosis', 'diagnosis', 'therapeutic', 'target', 'mechanism']
    }

    def __init__(self, use_gene_validation: bool = True):
        """
        初始化实体提取器

        Args:
            use_gene_validation: 是否使用基因白名单验证（V7.0新增）
        """
        self.stopwords = self._load_stopwords()
        self.use_gene_validation = use_gene_validation

        # V7.0: 初始化基因验证器
        if use_gene_validation and HAS_GENE_VALIDATOR:
            self.gene_validator = get_gene_validator(use_online_validation=False)
            logger.info("[EntityExtractor V7.0] 基因白名单验证器已启用")
        else:
            self.gene_validator = None
            logger.warning("[EntityExtractor V7.0] 基因验证未启用，可能产生幽灵节点")

    def _load_stopwords(self) -> set:
        """加载停用词"""
        return {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'this', 'that', 'these', 'those', 'have', 'has', 'had', 'not', 'no',
            '我们', '的', '了', '是', '在', '和', '有', '就', '不', '人', '都', '一',
            '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着',
            '没有', '看', '好', '自己', '这'
        }

    def extract_entities_from_text(self, text: str, top_n: int = 20) -> List[Tuple[str, str, int]]:
        """
        V7.0 从文本中提取实体（带白名单验证）

        Args:
            text: 输入文本
            top_n: 返回前N个高频实体

        Returns:
            [(entity, type, frequency), ...]
        """
        if not text:
            return []

        text_lower = text.lower()
        entities = []

        # 提取基因名（大写缩写）- V7.0 增强版
        genes = re.findall(r'\b[A-Z]{2,5}\b', text)
        gene_counter = Counter(g for g in genes if len(g) >= 2 and g not in self.stopwords)

        # V7.0: 基因白名单验证
        validated_genes = []
        rejected_genes = []  # 记录被拒绝的幽灵节点

        for gene, freq in gene_counter.most_common(top_n // 4):
            if self.gene_validator is not None:
                # 使用白名单验证
                result = self.gene_validator.validate_gene_symbol(gene)
                if result.is_valid:
                    validated_genes.append((gene, 'gene', freq))
                    logger.debug(f"[EntityExtractor V7.0] 基因验证通过: {gene}")
                else:
                    rejected_genes.append((gene, 'unknown', freq))
                    logger.debug(f"[EntityExtractor V7.0] 基因验证拒绝: {gene} ({result.message})")
            else:
                # 无验证器时，使用基础过滤（简单黑名单）
                basic_blacklist = {'RTX', 'GPU', 'CPU', 'AI', 'DNA', 'RNA', 'ATP', 'GTP', 'AMP', 'NAD'}
                if gene not in basic_blacklist:
                    validated_genes.append((gene, 'gene', freq))
                else:
                    rejected_genes.append((gene, 'unknown', freq))

        # 只添加验证通过的基因
        entities.extend(validated_genes)

        # 提取疾病相关术语
        diseases = re.findall(self.BIOMEDICAL_PATTERNS['diseases'], text_lower, re.IGNORECASE)
        disease_counter = Counter(diseases)
        for disease, freq in disease_counter.most_common(top_n // 4):
            entities.append((disease.capitalize(), 'disease', freq))

        # 提取方法学术语
        methods = re.findall(self.BIOMEDICAL_PATTERNS['methods'], text_lower, re.IGNORECASE)
        method_counter = Counter(methods)
        for method, freq in method_counter.most_common(top_n // 4):
            entities.append((method.capitalize(), 'method', freq))

        # 提取细胞类型
        cells = re.findall(self.BIOMEDICAL_PATTERNS['cells'], text_lower, re.IGNORECASE)
        cell_counter = Counter(cells)
        for cell, freq in cell_counter.most_common(top_n // 4):
            entities.append((cell.capitalize(), 'cell', freq))

        # 按频率排序
        entities.sort(key=lambda x: x[2], reverse=True)
        return entities[:top_n]

    def extract_entities_from_metadata(self, metadata: Dict) -> List[str]:
        """
        从元数据中提取实体

        Args:
            metadata: ChromaDB 元数据

        Returns:
            实体列表
        """
        entities = []

        # 从标题提取
        title = metadata.get('title', '')
        if title:
            # 简单的名词短语提取
            words = re.findall(r'\b[A-Z][a-z]+\b', title)
            entities.extend(words[:5])

        return list(set(entities))


class KnowledgeGraphBuilder:
    """知识图谱构建器"""

    def __init__(self, chroma_db_path: str = "local_db", collection_name: str = "literature_memory"):
        """
        初始化知识图谱构建器

        Args:
            chroma_db_path: ChromaDB 数据库路径
            collection_name: 集合名称
        """
        self.chroma_db_path = chroma_db_path
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self.entity_extractor = EntityExtractor()

        # 初始化 ChromaDB
        if HAS_CHROMADB:
            try:
                self.client = chromadb.PersistentClient(path=str(chroma_db_path))
                self.collection = self.client.get_or_create_collection(name=collection_name)
            except Exception as e:
                print(f"ChromaDB 初始化失败: {e}")

    def get_collection_data(self) -> Dict:
        """
        获取集合中的所有数据

        Returns:
            {'documents': [], 'metadatas': [], 'ids': []}
        """
        if not self.collection:
            return {'documents': [], 'metadatas': [], 'ids': []}

        try:
            data = self.collection.get(include=['documents', 'metadatas', 'distances'])
            return data
        except Exception as e:
            print(f"获取数据失败: {e}")
            return {'documents': [], 'metadatas': [], 'ids': []}

    def extract_entities_and_relations(self, data: Dict, max_nodes: int = 50) -> Dict:
        """
        从文献数据中提取实体和关系

        Args:
            data: ChromaDB 数据
            max_nodes: 最大节点数

        Returns:
            {'nodes': [], 'edges': [], 'node_types': {}}
        """
        documents = data.get('documents', [])
        metadatas = data.get('metadatas', [])

        if not documents:
            return {'nodes': [], 'edges': [], 'node_types': {}, 'node_labels': {}}

        # 收集所有实体
        all_entities = Counter()
        entity_sources = defaultdict(list)  # 实体 -> 来源文献
        entity_docs = defaultdict(list)  # 实体 -> 文档内容

        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            # 提取实体
            entities = self.entity_extractor.extract_entities_from_text(doc, top_n=10)

            for entity, e_type, freq in entities:
                entity_key = f"{entity}_{e_type}"
                all_entities[entity_key] += freq
                entity_sources[entity_key].append(meta.get('doi', 'unknown'))
                entity_docs[entity_key].append(doc[:200])

        # 选择高频实体作为节点
        top_entities = all_entities.most_common(max_nodes)

        # 构建节点
        nodes = []
        node_types = {}
        node_labels = {}

        # 颜色映射
        type_colors = {
            'gene': '#FF6B6B',
            'disease': '#4ECDC4',
            'method': '#45B7D1',
            'cell': '#96CEB4',
            'pathway': '#FFEAA7',
            'paper': '#DDA0DD'
        }

        for i, (entity_key, freq) in enumerate(top_entities):
            entity_name, e_type = entity_key.rsplit('_', 1)

            nodes.append({
                'id': i,
                'label': entity_name,
                'title': f"{e_type.capitalize()}: {entity_name}\n频率: {freq}",
                'value': freq,
                'group': e_type
            })

            node_types[entity_name] = e_type
            node_labels[entity_name] = entity_name

        # 构建边（基于共现关系）
        edges = []
        edge_weights = defaultdict(int)

        # 分析文档中的实体共现
        for doc, meta in zip(documents, metadatas):
            doc_entities = set()
            entities = self.entity_extractor.extract_entities_from_text(doc, top_n=15)

            for entity, e_type, _ in entities:
                if entity in node_labels:
                    doc_entities.add(entity)

            # 创建共现边
            doc_entities_list = list(doc_entities)
            for i in range(len(doc_entities_list)):
                for j in range(i + 1, len(doc_entities_list)):
                    edge = tuple(sorted([doc_entities_list[i], doc_entities_list[j]]))
                    edge_weights[edge] += 1

        # 转换为边列表
        entity_to_id = {label: nid for nid, node in enumerate(nodes) for label in [node['label']]}

        for (source, target), weight in edge_weights.items():
            if source in entity_to_id and target in entity_to_id:
                if weight >= 2:  # 至少共现2次
                    edges.append({
                        'from': entity_to_id[source],
                        'to': entity_to_id[target],
                        'value': weight,
                        'title': f"共现 {weight} 次"
                    })

        return {
            'nodes': nodes,
            'edges': edges,
            'node_types': node_types,
            'node_labels': node_labels
        }

    def build_paper_entity_graph(self, data: Dict, max_papers: int = 30) -> Dict:
        """
        构建论文-实体混合图

        Args:
            data: ChromaDB 数据
            max_papers: 最大论文数

        Returns:
            {'nodes': [], 'edges': [], 'node_types': {}}
        """
        documents = data.get('documents', [])
        metadatas = data.get('metadatas', [])

        if not documents:
            return {'nodes': [], 'edges': [], 'node_types': {}, 'node_labels': {}}

        # 按DOI分组（每个论文一个节点）
        paper_entities = defaultdict(list)
        paper_titles = {}
        paper_dois = set()

        for doc, meta in zip(documents, metadatas):
            doi = meta.get('doi', 'unknown')
            title = meta.get('title', 'Unknown')

            if doi != 'unknown':
                paper_dois.add(doi)
                paper_titles[doi] = title

                # 提取实体
                entities = self.entity_extractor.extract_entities_from_text(doc, top_n=5)
                for entity, e_type, _ in entities:
                    paper_entities[doi].append((entity, e_type))

        # 限制论文数量
        paper_dois = list(paper_dois)[:max_papers]

        # 构建节点
        nodes = []
        edges = []
        node_types = {}
        node_labels = {}
        entity_to_id = {}

        node_id = 0

        # 添加论文节点
        for doi in paper_dois:
            title = paper_titles.get(doi, doi)
            nodes.append({
                'id': node_id,
                'label': title[:30] + '...' if len(title) > 30 else title,
                'title': f"论文: {title}\nDOI: {doi}",
                'value': len(paper_entities[doi]),
                'group': 'paper'
            })
            node_types[doi] = 'paper'
            node_labels[doi] = node_id
            entity_to_id[doi] = node_id
            node_id += 1

        # 添加实体节点和边
        entity_colors = {
            'gene': '#FF6B6B',
            'disease': '#4ECDC4',
            'method': '#45B7D1',
            'cell': '#96CEB4'
        }

        entity_count = defaultdict(int)

        for doi in paper_dois:
            paper_id = entity_to_id[doi]
            for entity, e_type in paper_entities[doi]:
                entity_count[entity] += 1

        # 添加高频实体节点
        for entity, count in entity_count.most_common(50):
            if count >= 2:  # 至少出现在2篇论文中
                nodes.append({
                    'id': node_id,
                    'label': entity,
                    'title': f"实体: {entity}\n出现: {count} 篇",
                    'value': count,
                    'group': 'entity'
                })
                node_types[entity] = 'entity'
                entity_to_id[entity] = node_id
                node_id += 1

        # 创建边
        for doi in paper_dois:
            paper_id = entity_to_id.get(doi)
            if paper_id is None:
                continue

            for entity, e_type in paper_entities[doi]:
                entity_id = entity_to_id.get(entity)
                if entity_id is not None:
                    edges.append({
                        'from': paper_id,
                        'to': entity_id,
                        'value': 1,
                        'title': f"{doi} mentions {entity}"
                    })

        return {
            'nodes': nodes,
            'edges': edges,
            'node_types': node_types,
            'node_labels': node_labels
        }

    def get_statistics(self) -> Dict:
        """获取知识图谱统计信息"""
        if not self.collection:
            return {
                'total_documents': 0,
                'unique_papers': 0,
                'collection_name': self.collection_name
            }

        try:
            total_docs = self.collection.count()

            # 获取唯一DOI数
            data = self.collection.get(include=['metadatas'])
            unique_dois = set()
            if data.get('metadatas'):
                for meta in data['metadatas']:
                    doi = meta.get('doi', 'unknown')
                    if doi != 'unknown':
                        unique_dois.add(doi)

            return {
                'total_documents': total_docs,
                'unique_papers': len(unique_dois),
                'collection_name': self.collection_name
            }
        except Exception as e:
            return {'error': str(e)}


# ==================== 可视化函数 ====================

def create_pyvis_graph(graph_data: Dict, output_path: str = "knowledge_graph.html") -> Optional[str]:
    """
    使用 Pyvis 创建交互式网络图

    Args:
        graph_data: 图数据 {'nodes': [], 'edges': []}
        output_path: 输出HTML文件路径

    Returns:
        HTML文件路径或None
    """
    if not HAS_PYVIS:
        return None

    nodes = graph_data.get('nodes', [])
    edges = graph_data.get('edges', [])

    if not nodes:
        return None

    # 创建网络图
    net = Network(
        height="750px",
        width="100%",
        bgcolor="#222222",
        font_color="white",
        directed=False
    )

    # 设置物理引擎
    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -8000,
          "centralGravity": 0.3,
          "springLength": 150,
          "springConstant": 0.04
        }
      },
      "nodes": {
        "borderWidth": 2,
        "borderWidthSelected": 3
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 200,
        "hideEdgesOnDrag": true
      }
    }
    """)

    # 颜色映射
    type_colors = {
        'gene': '#FF6B6B',
        'disease': '#4ECDC4',
        'method': '#45B7D1',
        'cell': '#96CEB4',
        'pathway': '#FFEAA7',
        'paper': '#DDA0DD',
        'entity': '#FFA07A'
    }

    # 添加节点
    for node in nodes:
        color = type_colors.get(node.get('group', 'entity'), '#CCCCCC')
        net.add_node(
            node['id'],
            label=node['label'],
            title=node.get('title', ''),
            value=node.get('value', 1),
            color=color,
            size=min(max(node.get('value', 1) * 2, 10), 50)
        )

    # 添加边
    for edge in edges:
        net.add_edge(
            edge['from'],
            edge['to'],
            value=edge.get('value', 1),
            title=edge.get('title', ''),
            color='#888888',
            width=min(max(edge.get('value', 1) / 2, 0.5), 5)
        )

    # 保存HTML
    net.save_graph(output_path)
    return output_path


def create_agraph_data(graph_data: Dict) -> Tuple[List, List]:
    """
    创建 streamlit-agraph 所需的数据格式

    Args:
        graph_data: 图数据

    Returns:
        (nodes, edges) 元组
    """
    if not HAS_AGRAPH:
        return [], []

    nodes = graph_data.get('nodes', [])
    edges = graph_data.get('edges', [])

    # 颜色映射
    type_colors = {
        'gene': '#FF6B6B',
        'disease': '#4ECDC4',
        'method': '#45B7D1',
        'cell': '#96CEB4',
        'pathway': '#FFEAA7',
        'paper': '#DDA0DD',
        'entity': '#FFA07A'
    }

    # 转换节点
    agraph_nodes = []
    for node in nodes:
        color = type_colors.get(node.get('group', 'entity'), '#CCCCCC')
        size = min(max(node.get('value', 1) * 3, 15), 50)

        agraph_nodes.append(Node(
            id=str(node['id']),
            label=node['label'],
            title=node.get('title', ''),
            size=size,
            color=color,
            shape='dot'
        ))

    # 转换边
    agraph_edges = []
    for edge in edges:
        agraph_edges.append(Edge(
            source=str(edge['from']),
            target=str(edge['to']),
            label=str(edge.get('value', 1)),
            width=min(max(edge.get('value', 1) / 2, 1), 5)
        ))

    return agraph_nodes, agraph_edges


# ==================== 便捷函数 ====================

def get_knowledge_graph_data(db_path: str = "local_db", graph_type: str = "entity") -> Dict:
    """
    获取知识图谱数据

    Args:
        db_path: ChromaDB 路径
        graph_type: 图类型 ('entity' 或 'paper_entity')

    Returns:
        图数据
    """
    builder = KnowledgeGraphBuilder(chroma_db_path=db_path)
    data = builder.get_collection_data()

    if graph_type == 'entity':
        return builder.extract_entities_and_relations(data)
    else:
        return builder.build_paper_entity_graph(data)


def get_graph_statistics(db_path: str = "local_db") -> Dict:
    """获取知识图谱统计信息"""
    builder = KnowledgeGraphBuilder(chroma_db_path=db_path)
    return builder.get_statistics()


if __name__ == '__main__':
    # 测试代码
    print("知识图谱模块测试")

    builder = KnowledgeGraphBuilder()
    stats = builder.get_statistics()
    print(f"统计信息: {stats}")

    if stats.get('total_documents', 0) > 0:
        graph_data = builder.extract_entities_and_relations(builder.get_collection_data())
        print(f"节点数: {len(graph_data['nodes'])}")
        print(f"边数: {len(graph_data['edges'])}")
