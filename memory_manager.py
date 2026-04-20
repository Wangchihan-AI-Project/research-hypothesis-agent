"""
永久记忆与RAG（检索增强生成）模块

使用 ChromaDB 建立本地持久化数据库，存储和检索文献内容。
支持文本切片、向量化存储和语义搜索。
"""
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# 尝试导入依赖
try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False
    print("警告: chromadb 未安装，记忆功能将不可用")

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    print("警告: sentence-transformers 未安装，将使用 ChromaDB 默认嵌入")


class MemoryManager:
    """
    文献记忆管理器

    功能：
    - 文本切片和向量化存储
    - DOI 和抓取时间的 metadata 记录
    - 语义搜索返回最相关的历史文献
    """

    def __init__(self, db_path: str = "local_db", collection_name: str = "literature_memory"):
        """
        初始化记忆管理器

        Args:
            db_path: 数据库持久化路径
            collection_name: ChromaDB 集合名称
        """
        self.db_path = Path(db_path)
        self.db_path.mkdir(exist_ok=True, parents=True)
        self.collection_name = collection_name

        # 初始化嵌入模型
        self.embed_model = None
        if HAS_SENTENCE_TRANSFORMERS:
            try:
                # 使用轻量级多语言模型，适合中英文混合场景
                self.embed_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            except Exception as e:
                print(f"加载嵌入模型失败: {e}, 将使用默认嵌入")

        # 初始化 ChromaDB
        self.client = None
        self.collection = None
        if HAS_CHROMADB:
            try:
                # ChromaDB 新版 API：PersistentClient 直接接受 path 参数
                self.client = chromadb.PersistentClient(path=str(self.db_path))
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"description": "文献永久记忆库"}
                )
                print(f"记忆库初始化成功: {self.db_path}")
            except Exception as e:
                print(f"ChromaDB 初始化失败: {e}")

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        将文本切片成适合嵌入的小块

        Args:
            text: 原始文本
            chunk_size: 每个切片的目标字符数
            overlap: 切片之间的重叠字符数

        Returns:
            切片列表
        """
        if not text or not text.strip():
            return []

        # 清理文本
        text = self._clean_text(text)

        # 如果文本很短，直接返回
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # 尝试在句子边界切分
            if end < len(text):
                # 找最近的句子结束位置
                sentence_endings = ['。', '.', '！', '!', '？', '?', '\n']
                nearest_end = end
                for ending in sentence_endings:
                    pos = text.rfind(ending, start, end + overlap)
                    if pos > start and pos < end + overlap:
                        nearest_end = min(nearest_end, pos + 1)
                end = nearest_end

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap if end < len(text) else end

        return chunks

    def _clean_text(self, text: str) -> str:
        """
        清理文本，移除无用内容

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        if not text:
            return ""

        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)

        # 移除页码等干扰信息
        text = re.sub(r'\bPage\s*\d+\s*of\s*\d+\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\b\d+\s*[Bb]io[Rr]xi[vv]\b', '', text)

        # 移除引用标记（保留内容）
        text = re.sub(r'\[\d+\]', '', text)

        # 移除常见的PDF解析噪声
        text = re.sub(r'Abstract\s*:\s*', '摘要: ', text, flags=re.IGNORECASE)
        text = re.sub(r'Introduction\s*:\s*', '引言: ', text, flags=re.IGNORECASE)

        return text.strip()

    def _get_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        获取文本嵌入向量

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表，如果嵌入模型不可用则返回 None
        """
        if not texts:
            return None

        if self.embed_model:
            try:
                embeddings = self.embed_model.encode(texts, show_progress_bar=False)
                return embeddings.tolist()
            except Exception as e:
                print(f"嵌入失败: {e}")
                return None

        return None  # 让 ChromaDB 使用默认嵌入

    def save_to_memory(self, text: str, metadata: Dict) -> Dict:
        """
        将文本切片并存入数据库

        Args:
            text: 文献全文或摘要文本
            metadata: 元数据，必须包含 DOI 和抓取时间
                     {'doi': str, 'fetch_time': str, 'source': str, 'title': str, ...}

        Returns:
            {'success': bool, 'chunks_saved': int, 'message': str}
        """
        result = {
            'success': False,
            'chunks_saved': 0,
            'message': ''
        }

        if not HAS_CHROMADB or not self.collection:
            result['message'] = 'ChromaDB 未初始化'
            return result

        if not text or not text.strip():
            result['message'] = '文本内容为空'
            return result

        try:
            # 确保 metadata 有必要字段
            if 'fetch_time' not in metadata:
                metadata['fetch_time'] = datetime.now().isoformat()

            if 'doi' not in metadata:
                metadata['doi'] = 'unknown'

            # 切片文本
            chunks = self._chunk_text(text)

            if not chunks:
                result['message'] = '文本切片失败'
                return result

            # 生成唯一 ID
            base_id = f"{metadata.get('doi', 'unknown')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            chunk_ids = [f"{base_id}_chunk_{i}" for i in range(len(chunks))]

            # 为每个切片准备 metadata
            chunk_metadatas = []
            for i, chunk in enumerate(chunks):
                chunk_meta = metadata.copy()
                chunk_meta['chunk_index'] = i
                chunk_meta['chunk_count'] = len(chunks)
                chunk_meta['chunk_text_preview'] = chunk[:100]  # 存储预览
                chunk_metadatas.append(chunk_meta)

            # 获取嵌入（如果可用）
            embeddings = self._get_embeddings(chunks)

            # 存入 ChromaDB
            if embeddings:
                self.collection.add(
                    ids=chunk_ids,
                    embeddings=embeddings,
                    documents=chunks,
                    metadatas=chunk_metadatas
                )
            else:
                # 使用 ChromaDB 默认嵌入函数
                self.collection.add(
                    ids=chunk_ids,
                    documents=chunks,
                    metadatas=chunk_metadatas
                )

            result['success'] = True
            result['chunks_saved'] = len(chunks)
            result['message'] = f'成功存储 {len(chunks)} 个文本切片'

            print(f"[记忆库] 存储: DOI={metadata.get('doi')}, 切片数={len(chunks)}")

        except Exception as e:
            result['message'] = f'存储失败: {str(e)}'
            print(f"[记忆库] 存储错误: {e}")

        return result

    def search_past_literature(self, query: str, n_results: int = 3) -> Dict:
        """
        搜索本地记忆库中的历史文献

        Args:
            query: 搜索问题，如 '之前关于单细胞图神经网络的文献有哪些'
            n_results: 返回结果数量（默认 3）

        Returns:
            {
                'success': bool,
                'results': [
                    {
                        'text': str,  # 匹配的文本片段
                        'doi': str,
                        'title': str,
                        'fetch_time': str,
                        'distance': float,  # 相似度距离
                        'relevance_score': float  # 相关性评分
                    }
                ],
                'message': str
            }
        """
        result = {
            'success': False,
            'results': [],
            'message': ''
        }

        if not HAS_CHROMADB or not self.collection:
            result['message'] = 'ChromaDB 未初始化'
            return result

        if not query or not query.strip():
            result['message'] = '搜索查询为空'
            return result

        try:
            # 检查集合是否有数据
            count = self.collection.count()
            if count == 0:
                result['message'] = '记忆库为空，暂无历史文献'
                return result

            # 获取查询嵌入
            query_embedding = self._get_embeddings([query])
            query_embedding = query_embedding[0] if query_embedding else None

            # 执行搜索
            if query_embedding:
                search_result = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    include=['documents', 'metadatas', 'distances']
                )
            else:
                search_result = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    include=['documents', 'metadatas', 'distances']
                )

            # 解析结果
            if search_result and search_result.get('documents'):
                documents = search_result['documents'][0]  # 第一组结果
                metadatas = search_result['metadatas'][0] if search_result.get('metadatas') else []
                distances = search_result['distances'][0] if search_result.get('distances') else []

                for i, doc in enumerate(documents):
                    meta = metadatas[i] if i < len(metadatas) else {}
                    distance = distances[i] if i < len(distances) else 0

                    # 计算相关性评分（距离越小越相关）
                    relevance_score = max(0, 1 - distance) if distance else 0.5

                    result['results'].append({
                        'text': doc,
                        'doi': meta.get('doi', 'unknown'),
                        'title': meta.get('title', '未知标题'),
                        'fetch_time': meta.get('fetch_time', ''),
                        'source': meta.get('source', 'unknown'),
                        'distance': distance,
                        'relevance_score': relevance_score
                    })

                result['success'] = True
                result['message'] = f'找到 {len(result["results"])} 条相关文献记录'

                print(f"[记忆库] 搜索: 查询='{query[:50]}...', 结果数={len(result['results'])}")

            else:
                result['message'] = '未找到相关文献'

        except Exception as e:
            result['message'] = f'搜索失败: {str(e)}'
            print(f"[记忆库] 搜索错误: {e}")

        return result

    def get_memory_stats(self) -> Dict:
        """
        获取记忆库统计信息

        Returns:
            {'total_chunks': int, 'unique_dois': int, 'collection_name': str}
        """
        stats = {
            'total_chunks': 0,
            'unique_dois': 0,
            'collection_name': self.collection_name,
            'db_path': str(self.db_path)
        }

        if not self.collection:
            return stats

        try:
            stats['total_chunks'] = self.collection.count()

            # 获取所有 DOI
            all_items = self.collection.get(include=['metadatas'])
            if all_items and all_items.get('metadatas'):
                unique_dois = set()
                for meta in all_items['metadatas']:
                    if meta.get('doi'):
                        unique_dois.add(meta['doi'])
                stats['unique_dois'] = len(unique_dois)

        except Exception as e:
            print(f"[记忆库] 统计失败: {e}")

        return stats

    def clear_memory(self) -> Dict:
        """
        清空记忆库（谨慎使用）

        Returns:
            {'success': bool, 'message': str}
        """
        result = {'success': False, 'message': ''}

        if not self.client or not self.collection:
            result['message'] = 'ChromaDB 未初始化'
            return result

        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "文献永久记忆库"}
            )
            result['success'] = True
            result['message'] = '记忆库已清空'
            print("[记忆库] 已清空")
        except Exception as e:
            result['message'] = f'清空失败: {str(e)}'

        return result


# 全局单例实例（懒加载）
_memory_manager_instance: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """
    获取记忆管理器单例实例

    Returns:
        MemoryManager 实例
    """
    global _memory_manager_instance

    if _memory_manager_instance is None:
        # 默认在项目根目录下创建 local_db
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_db')
        _memory_manager_instance = MemoryManager(db_path=db_path)

    return _memory_manager_instance


def save_to_memory(text: str, metadata: Dict) -> Dict:
    """
    便捷函数：保存文本到记忆库

    Args:
        text: 文献文本
        metadata: 元数据（DOI, fetch_time 等）

    Returns:
        操作结果
    """
    manager = get_memory_manager()
    return manager.save_to_memory(text, metadata)


def search_past_literature(query: str, n_results: int = 3) -> Dict:
    """
    便捷函数：搜索历史文献

    Args:
        query: 搜索查询
        n_results: 返回结果数量

    Returns:
        搜索结果
    """
    manager = get_memory_manager()
    return manager.search_past_literature(query, n_results)


def get_memory_stats() -> Dict:
    """
    便捷函数：获取记忆库统计
    """
    manager = get_memory_manager()
    return manager.get_memory_stats()


if __name__ == '__main__':
    print("=" * 60)
    print("记忆管理器测试")
    print("=" * 60)

    # 初始化
    manager = MemoryManager()

    # 测试存储
    test_text = """
    单细胞图神经网络在生物医学中的应用

    摘要：近年来，单细胞RNA测序技术的发展使得我们能够在单细胞分辨率下研究生物系统。
    图神经网络(GNN)作为一种强大的深度学习工具，已被广泛应用于单细胞数据分析。
    本文综述了GNN在单细胞聚类、细胞类型识别、基因调控网络推断等方面的应用。

    引言：单细胞技术的快速发展产生了海量的高维数据。传统的分析方法难以捕捉
    细胞之间的复杂关系。GNN能够有效地建模细胞之间的拓扑结构，
    为理解细胞状态转换和细胞间通信提供了新的视角。
    """

    test_metadata = {
        'doi': '10.1234/test.2024.001',
        'title': '单细胞图神经网络综述',
        'source': 'test',
        'fetch_time': datetime.now().isoformat()
    }

    save_result = manager.save_to_memory(test_text, test_metadata)
    print(f"存储结果: {save_result}")

    # 测试搜索
    search_result = manager.search_past_literature("单细胞图神经网络的应用")
    print(f"\n搜索结果: {search_result}")

    # 统计信息
    stats = manager.get_memory_stats()
    print(f"\n记忆库统计: {stats}")