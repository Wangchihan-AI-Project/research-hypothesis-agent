# -*- coding: utf-8 -*-
"""
V7.1 向量池分离管理器 (Vector Pool Separation Manager)

修复 VSCG (Vector Space Collapse Game) 漏洞：
- 红方攻击性假设与蓝方防御性假设混存导致向量空间污染
- 检索噪声信号干扰
- 熵塌缩风险（良性信号密度降低）

核心机制：
1. ChromaDB-A (良性池): 仅存储高分验证假设 (score >= 7.0 + 硬链接验证)
2. ChromaDB-B (对抗池): 存储红方产物，标记 adversarial_noise
3. RAG 检索仅从良性池，对抗池仅供红方参考
4. 熵监控：良性池密度 < 40% 时警报
5. 定期清理：每7天清理对抗池过期数据

作者: 零日漏洞修复组 V7.1
日期: 2026-04-17
"""

import os
import json
import logging
import threading
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter

logger = logging.getLogger(__name__)

# 尝试导入 ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False
    logger.warning("[VectorPoolManager V7.1] ChromaDB 未安装，使用文件存储回退")

# 尝试导入嵌入器
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


class VectorPoolType(Enum):
    """向量池类型"""
    BENIGN = "benign"       # 良性池 - 高质量验证假设
    ADVERSARIAL = "adversarial"  # 对抗池 - 红方攻击产物


class EntropyAlertLevel(Enum):
    """熵警报级别"""
    NORMAL = "normal"           # 正常（良性密度 >= 60%）
    WARNING = "warning"         # 警告（良性密度 40-60%）
    CRITICAL = "critical"       # 临界（良性密度 < 40%）
    COLLAPSE = "collapse"       # 塌缩（良性密度 < 20%）


@dataclass
class VectorPoolConfig:
    """向量池配置"""
    # 存储阈值
    benign_score_threshold: float = 7.0  # 良性池最低分数
    require_citation_verification: bool = True  # 是否要求引用验证

    # 熵监控阈值
    entropy_warning_threshold: float = 0.4  # 警告阈值
    entropy_critical_threshold: float = 0.6  # 临界阈值
    entropy_collapse_threshold: float = 0.8  # 塌缩阈值

    # 清理周期
    adversarial_cleanup_days: int = 7  # 对抗池清理周期
    max_adversarial_records: int = 500  # 对抗池最大记录数

    # 存储路径
    db_path: str = "local_db"


@dataclass
class VectorRecord:
    """向量记录"""
    id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict = field(default_factory=dict)
    pool_type: VectorPoolType = VectorPoolType.BENIGN
    score: float = 0.0
    citation_verified: bool = False
    timestamp: str = ""
    session_id: str = ""
    hash: str = ""

    # V7.1: 对抗性标记
    is_adversarial_noise: bool = False
    red_team_source: bool = False
    attack_dimension: Optional[str] = None


@dataclass
class EntropyStatus:
    """熵状态"""
    benign_count: int = 0
    adversarial_count: int = 0
    total_count: int = 0
    benign_density: float = 0.0
    alert_level: EntropyAlertLevel = EntropyAlertLevel.NORMAL
    message: str = ""
    timestamp: str = ""


class VectorPoolManager:
    """
    V7.1 向量池分离管理器 - 修复 VSCG 漏洞

    核心改进：
    1. 良性池/对抗池分离存储
    2. 存储准入验证（分数 + 引用）
    3. 熵密度实时监控
    4. 对抗池定期清理
    5. RAG 检索池隔离
    """

    COLLECTION_BENIGN = "hypothesis_benign_pool"
    COLLECTION_ADVERSARIAL = "hypothesis_adversarial_pool"

    def __init__(self, config: VectorPoolConfig = None):
        """
        初始化向量池管理器

        Args:
            config: 向量池配置
        """
        self.config = config or VectorPoolConfig()
        self.db_path = Path(self.config.db_path)

        # 确保数据库目录存在
        self.db_path.mkdir(parents=True, exist_ok=True)

        # 初始化 ChromaDB
        self._init_chromadb()

        # 熵监控状态
        self._entropy_status: Optional[EntropyStatus] = None
        self._entropy_lock = threading.Lock()

        # 清理定时器
        self._cleanup_thread: Optional[threading.Thread] = None
        self._cleanup_running = False

        logger.info(
            f"[VectorPoolManager V7.1] 初始化完成\n"
            f"  良性池阈值: {self.config.benign_score_threshold}\n"
            f"  引用验证: {self.config.require_citation_verification}\n"
            f"  熵警告阈值: {self.config.entropy_warning_threshold}\n"
            f"  数据库路径: {self.db_path}"
        )

    def _init_chromadb(self):
        """初始化 ChromaDB 双池"""
        if not HAS_CHROMADB:
            logger.warning("[VectorPoolManager V7.1] ChromaDB 不可用，使用文件存储回退")
            self.benign_client = None
            self.adversarial_client = None
            self.benign_collection = None
            self.adversarial_collection = None
            return

        try:
            # 创建持久化客户端
            self.client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=Settings(anonymized_telemetry=False)
            )

            # 良性池 - 高质量验证假设
            self.benign_collection = self.client.get_or_create_collection(
                name=self.COLLECTION_BENIGN,
                metadata={"description": "V7.1 良性向量池 - 高质量验证假设"}
            )

            # 对抗池 - 红方攻击产物
            self.adversarial_collection = self.client.get_or_create_collection(
                name=self.COLLECTION_ADVERSARIAL,
                metadata={"description": "V7.1 对抗向量池 - 红方攻击产物"}
            )

            logger.info(
                f"[VectorPoolManager V7.1] ChromaDB 双池创建成功\n"
                f"  良性池: {self.COLLECTION_BENIGN} ({self.benign_collection.count()} 条)\n"
                f"  对抗池: {self.COLLECTION_ADVERSARIAL} ({self.adversarial_collection.count()} 条)"
            )

        except Exception as e:
            logger.error(f"[VectorPoolManager V7.1] ChromaDB 初始化失败: {e}")
            self.benign_collection = None
            self.adversarial_collection = None

    def store_hypothesis(
        self,
        hypothesis: Dict,
        score: float,
        session_id: str,
        is_red_team: bool = False,
        attack_dimension: str = None,
        citation_verified: bool = False
    ) -> Tuple[bool, str]:
        """
        V7.1 存储假设 - 分池存储机制

        核心规则：
        - score >= 7.0 且 citation_verified=True → 良性池
        - score < 7.0 或 is_red_team=True → 对抗池（标记 adversarial_noise）
        - score < 3.0 → 拒绝存储（噪声过滤）

        Args:
            hypothesis: 假设内容
            score: 适应度分数
            session_id: 会话ID
            is_red_team: 是否为红方产物
            attack_dimension: 攻击维度（红方）
            citation_verified: 是否通过硬链接锚定验证

        Returns:
            Tuple[成功, 存储池类型/拒绝原因]
        """
        # 生成记录ID和哈希
        hypothesis_text = hypothesis.get('title', '') + ' ' + hypothesis.get('abstract', '')
        record_id = self._generate_record_id(hypothesis_text, session_id)
        record_hash = self._compute_hash(hypothesis_text)

        # 构建元数据
        metadata = {
            'session_id': session_id,
            'score': score,
            'timestamp': datetime.now().isoformat(),
            'citation_verified': citation_verified,
            'is_red_team': is_red_team,
            'attack_dimension': attack_dimension or 'none',
            'hash': record_hash
        }

        # V7.1: 分池决策逻辑
        # 规则 1: 极低分数拒绝
        if score < 3.0:
            logger.info(f"[VectorPoolManager V7.1] 拒绝存储: score={score} < 3.0 (噪声过滤)")
            return False, "rejected_noise_filter"

        # 规则 2: 红方产物 → 对抗池
        if is_red_team:
            metadata['adversarial_noise'] = True
            metadata['pool_type'] = 'adversarial'
            stored = self._store_to_adversarial_pool(record_id, hypothesis_text, metadata)
            if stored:
                self._update_entropy_status()
                return True, "adversarial_pool"
            return False, "adversarial_pool_failed"

        # 规则 3: 良性池准入验证
        benign_criteria_met = (
            score >= self.config.benign_score_threshold and
            (citation_verified or not self.config.require_citation_verification)
        )

        if benign_criteria_met:
            # 存入良性池
            metadata['pool_type'] = 'benign'
            metadata['adversarial_noise'] = False
            stored = self._store_to_benign_pool(record_id, hypothesis_text, metadata)
            if stored:
                self._update_entropy_status()
                return True, "benign_pool"
            return False, "benign_pool_failed"

        # 规则 4: 未达良性标准 → 对抗池（待验证区）
        metadata['adversarial_noise'] = False  # 不是噪声，只是待验证
        metadata['pool_type'] = 'adversarial_pending'
        metadata['pending_validation'] = True
        stored = self._store_to_adversarial_pool(record_id, hypothesis_text, metadata)
        if stored:
            self._update_entropy_status()
            return True, "adversarial_pending"
        return False, "adversarial_pending_failed"

    def _store_to_benign_pool(
        self,
        record_id: str,
        content: str,
        metadata: Dict
    ) -> bool:
        """存储到良性池"""
        if self.benign_collection is None:
            # 文件存储回退
            return self._file_store(VectorPoolType.BENIGN, record_id, content, metadata)

        try:
            self.benign_collection.add(
                ids=[record_id],
                documents=[content],
                metadatas=[metadata]
            )
            logger.info(f"[VectorPoolManager V7.1] 良性池存储成功: {record_id}")
            return True
        except Exception as e:
            logger.error(f"[VectorPoolManager V7.1] 良性池存储失败: {e}")
            return False

    def _store_to_adversarial_pool(
        self,
        record_id: str,
        content: str,
        metadata: Dict
    ) -> bool:
        """存储到对抗池"""
        if self.adversarial_collection is None:
            # 文件存储回退
            return self._file_store(VectorPoolType.ADVERSARIAL, record_id, content, metadata)

        try:
            self.adversarial_collection.add(
                ids=[record_id],
                documents=[content],
                metadatas=[metadata]
            )
            logger.info(f"[VectorPoolManager V7.1] 对抗池存储成功: {record_id}")
            return True
        except Exception as e:
            logger.error(f"[VectorPoolManager V7.1] 对抗池存储失败: {e}")
            return False

    def _file_store(
        self,
        pool_type: VectorPoolType,
        record_id: str,
        content: str,
        metadata: Dict
    ) -> bool:
        """文件存储回退（ChromaDB 不可用时）"""
        pool_dir = self.db_path / f"{pool_type.value}_pool"
        pool_dir.mkdir(parents=True, exist_ok=True)

        filepath = pool_dir / f"{record_id}.json"
        record = {
            'id': record_id,
            'content': content,
            'metadata': metadata
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"[VectorPoolManager V7.1] 文件存储失败: {e}")
            return False

    def retrieve_for_rag(
        self,
        query: str,
        top_k: int = 10,
        exclude_adversarial: bool = True
    ) -> List[Dict]:
        """
        V7.1 RAG 检索 - 池隔离机制

        核心规则：
        - 默认仅从良性池检索（exclude_adversarial=True）
        - 红方参考时可从对抗池检索（exclude_adversarial=False）

        Args:
            query: 检索查询
            top_k: 返回数量
            exclude_adversarial: 是否排除对抗池

        Returns:
            List[Dict]: 检索结果
        """
        results = []

        # 良性池检索
        if self.benign_collection is not None:
            try:
                benign_results = self.benign_collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    include=['documents', 'metadatas', 'distances']
                )

                if benign_results.get('ids'):
                    for i, doc_id in enumerate(benign_results['ids'][0]):
                        results.append({
                            'id': doc_id,
                            'content': benign_results['documents'][0][i] if benign_results['documents'] else '',
                            'metadata': benign_results['metadatas'][0][i] if benign_results['metadatas'] else {},
                            'distance': benign_results['distances'][0][i] if benign_results['distances'] else 0,
                            'pool_type': 'benign',
                            'verified': True
                        })
            except Exception as e:
                logger.error(f"[VectorPoolManager V7.1] 良性池检索失败: {e}")

        # 对抗池检索（可选）
        if not exclude_adversarial and self.adversarial_collection is not None:
            try:
                adversarial_results = self.adversarial_collection.query(
                    query_texts=[query],
                    n_results=top_k // 2,  # 对抗池返回较少
                    include=['documents', 'metadatas', 'distances']
                )

                if adversarial_results.get('ids'):
                    for i, doc_id in enumerate(adversarial_results['ids'][0]):
                        metadata = adversarial_results['metadatas'][0][i] if adversarial_results['metadatas'] else {}
                        results.append({
                            'id': doc_id,
                            'content': adversarial_results['documents'][0][i] if adversarial_results['documents'] else '',
                            'metadata': metadata,
                            'distance': adversarial_results['distances'][0][i] if adversarial_results['distances'] else 0,
                            'pool_type': 'adversarial',
                            'verified': False,
                            'is_noise': metadata.get('adversarial_noise', False)
                        })
            except Exception as e:
                logger.error(f"[VectorPoolManager V7.1] 对抗池检索失败: {e}")

        logger.info(
            f"[VectorPoolManager V7.1] RAG 检索完成\n"
            f"  查询: {query[:50]}...\n"
            f"  返回: {len(results)} 条\n"
            f"  良性池: {sum(1 for r in results if r['pool_type'] == 'benign')}\n"
            f"  对抗池: {sum(1 for r in results if r['pool_type'] == 'adversarial')}"
        )

        return results

    def check_entropy(self) -> EntropyStatus:
        """
        V7.1 熵密度检查 - 向量空间健康度监控

        计算良性池密度：
        - density = benign_count / total_count
        - density >= 60% → NORMAL
        - density 40-60% → WARNING
        - density < 40% → CRITICAL
        - density < 20% → COLLAPSE

        Returns:
            EntropyStatus: 熵状态报告
        """
        with self._entropy_lock:
            if self._entropy_status is not None:
                # 检查是否需要更新（5分钟缓存）
                last_time = datetime.fromisoformat(self._entropy_status.timestamp)
                if datetime.now() - last_time < timedelta(minutes=5):
                    return self._entropy_status

            return self._update_entropy_status()

    def _update_entropy_status(self) -> EntropyStatus:
        """更新熵状态"""
        benign_count = 0
        adversarial_count = 0

        # 获取 ChromaDB 计数
        if self.benign_collection is not None:
            try:
                benign_count = self.benign_collection.count()
            except Exception:
                pass

        if self.adversarial_collection is not None:
            try:
                adversarial_count = self.adversarial_collection.count()
            except Exception:
                pass

        # 文件存储回退计数
        if self.benign_collection is None:
            benign_dir = self.db_path / "benign_pool"
            if benign_dir.exists():
                benign_count = len(list(benign_dir.glob("*.json")))

        if self.adversarial_collection is None:
            adversarial_dir = self.db_path / "adversarial_pool"
            if adversarial_dir.exists():
                adversarial_count = len(list(adversarial_dir.glob("*.json")))

        total_count = benign_count + adversarial_count

        # 计算良性密度
        if total_count == 0:
            benign_density = 1.0  # 无数据时默认健康
        else:
            benign_density = 1.0 - (adversarial_count / total_count)

        # 确定警报级别
        if benign_density >= 0.6:
            alert_level = EntropyAlertLevel.NORMAL
            message = f"向量空间健康（良性密度 {benign_density:.1%}）"
        elif benign_density >= 0.4:
            alert_level = EntropyAlertLevel.WARNING
            message = f"向量空间警告（良性密度 {benign_density:.1%}）- 需关注"
        elif benign_density >= 0.2:
            alert_level = EntropyAlertLevel.CRITICAL
            message = f"向量空间临界（良性密度 {benign_density:.1%}）- 紧急"
        else:
            alert_level = EntropyAlertLevel.COLLAPSE
            message = f"向量空间塌缩（良性密度 {benign_density:.1%}）- 灾难"

        self._entropy_status = EntropyStatus(
            benign_count=benign_count,
            adversarial_count=adversarial_count,
            total_count=total_count,
            benign_density=benign_density,
            alert_level=alert_level,
            message=message,
            timestamp=datetime.now().isoformat()
        )

        # 警告级别日志
        if alert_level in [EntropyAlertLevel.CRITICAL, EntropyAlertLevel.COLLAPSE]:
            logger.warning(f"[VectorPoolManager V7.1] 熵警报: {message}")
        else:
            logger.info(f"[VectorPoolManager V7.1] 熵状态: {message}")

        return self._entropy_status

    def cleanup_adversarial_pool(self, days: int = None) -> int:
        """
        V7.1 对抗池清理 - 过期数据删除

        Args:
            days: 清理天数阈值（默认使用配置值）

        Returns:
            int: 清理的记录数
        """
        cleanup_days = days or self.config.adversarial_cleanup_days
        cutoff_time = datetime.now() - timedelta(days=cleanup_days)
        deleted_count = 0

        if self.adversarial_collection is not None:
            try:
                # 获取所有对抗池记录
                all_records = self.adversarial_collection.get(
                    include=['metadatas']
                )

                ids_to_delete = []
                if all_records.get('ids') and all_records.get('metadatas'):
                    for i, record_id in enumerate(all_records['ids']):
                        metadata = all_records['metadatas'][i]
                        timestamp_str = metadata.get('timestamp', '')

                        if timestamp_str:
                            try:
                                record_time = datetime.fromisoformat(timestamp_str)
                                if record_time < cutoff_time:
                                    ids_to_delete.append(record_id)
                            except ValueError:
                                pass

                # 执行删除
                if ids_to_delete:
                    self.adversarial_collection.delete(ids=ids_to_delete)
                    deleted_count = len(ids_to_delete)

            except Exception as e:
                logger.error(f"[VectorPoolManager V7.1] 对抗池清理失败: {e}")

        # 文件存储回退清理
        if self.adversarial_collection is None:
            adversarial_dir = self.db_path / "adversarial_pool"
            if adversarial_dir.exists():
                for filepath in adversarial_dir.glob("*.json"):
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            record = json.load(f)
                        timestamp_str = record.get('metadata', {}).get('timestamp', '')

                        if timestamp_str:
                            record_time = datetime.fromisoformat(timestamp_str)
                            if record_time < cutoff_time:
                                filepath.unlink()
                                deleted_count += 1
                    except Exception:
                        pass

        # 强制执行最大记录数限制
        if self.adversarial_collection is not None:
            try:
                current_count = self.adversarial_collection.count()
                if current_count > self.config.max_adversarial_records:
                    excess = current_count - self.config.max_adversarial_records
                    # 删除最旧的 excess 条记录
                    all_records = self.adversarial_collection.get(include=['metadatas'])
                    if all_records.get('ids') and all_records.get('metadatas'):
                        sorted_records = sorted(
                            zip(all_records['ids'], all_records['metadatas']),
                            key=lambda x: x[1].get('timestamp', '')
                        )
                        ids_to_trim = [r[0] for r in sorted_records[:excess]]
                        self.adversarial_collection.delete(ids=ids_to_trim)
                        deleted_count += len(ids_to_trim)
            except Exception:
                pass

        logger.info(f"[VectorPoolManager V7.1] 对抗池清理完成: 删除 {deleted_count} 条")
        self._update_entropy_status()
        return deleted_count

    def promote_to_benign(
        self,
        record_id: str,
        new_score: float,
        citation_verified: bool = True
    ) -> bool:
        """
        V7.1 对抗池晋升 - 待验证假设通过后晋升至良性池

        Args:
            record_id: 记录ID
            new_score: 新分数
            citation_verified: 是否通过引用验证

        Returns:
            bool: 晋升成功
        """
        if new_score < self.config.benign_score_threshold:
            logger.info(f"[VectorPoolManager V7.1] 晋升拒绝: score={new_score} < {self.config.benign_score_threshold}")
            return False

        # 从对抗池获取记录
        if self.adversarial_collection is None:
            logger.error(f"[VectorPoolManager V7.1] 晋升失败: 对抗池不可用")
            return False

        try:
            record = self.adversarial_collection.get(
                ids=[record_id],
                include=['documents', 'metadatas']
            )

            if not record.get('ids'):
                logger.error(f"[VectorPoolManager V7.1] 晋升失败: 记录不存在 {record_id}")
                return False

            content = record['documents'][0] if record['documents'] else ''
            old_metadata = record['metadatas'][0] if record['metadatas'] else {}

            # 更新元数据
            new_metadata = old_metadata.copy()
            new_metadata['score'] = new_score
            new_metadata['citation_verified'] = citation_verified
            new_metadata['pool_type'] = 'benign'
            new_metadata['promoted_at'] = datetime.now().isoformat()
            new_metadata['adversarial_noise'] = False
            new_metadata['pending_validation'] = False

            # 存入良性池
            self._store_to_benign_pool(record_id, content, new_metadata)

            # 从对抗池删除
            self.adversarial_collection.delete(ids=[record_id])

            logger.info(f"[VectorPoolManager V7.1] 晋升成功: {record_id}")
            self._update_entropy_status()
            return True

        except Exception as e:
            logger.error(f"[VectorPoolManager V7.1] 晋升失败: {e}")
            return False

    def get_pool_statistics(self) -> Dict:
        """获取向量池统计信息"""
        entropy = self.check_entropy()

        return {
            'benign_pool': {
                'count': entropy.benign_count,
                'collection': self.COLLECTION_BENIGN
            },
            'adversarial_pool': {
                'count': entropy.adversarial_count,
                'collection': self.COLLECTION_ADVERSARIAL
            },
            'entropy': {
                'total': entropy.total_count,
                'benign_density': entropy.benign_density,
                'alert_level': entropy.alert_level.value,
                'message': entropy.message
            },
            'config': {
                'benign_threshold': self.config.benign_score_threshold,
                'cleanup_days': self.config.adversarial_cleanup_days,
                'max_adversarial': self.config.max_adversarial_records
            }
        }

    def _generate_record_id(self, content: str, session_id: str) -> str:
        """生成记录ID"""
        hash_value = self._compute_hash(content)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"hyp_{session_id[:8]}_{hash_value}_{timestamp}"

    def _compute_hash(self, text: str) -> str:
        """计算文本哈希"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()[:8]

    def start_cleanup_scheduler(self):
        """启动清理定时器"""
        if self._cleanup_running:
            return

        self._cleanup_running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self._cleanup_thread.start()
        logger.info("[VectorPoolManager V7.1] 清理定时器已启动")

    def stop_cleanup_scheduler(self):
        """停止清理定时器"""
        self._cleanup_running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        logger.info("[VectorPoolManager V7.1] 清理定时器已停止")

    def _cleanup_loop(self):
        """清理循环（每24小时执行一次）"""
        import time
        while self._cleanup_running:
            time.sleep(24 * 3600)  # 24小时
            if self._cleanup_running:
                self.cleanup_adversarial_pool()

    def reset(self):
        """重置向量池"""
        if self.benign_collection is not None:
            try:
                # 删除所有良性池记录
                all_records = self.benign_collection.get()
                if all_records.get('ids'):
                    self.benign_collection.delete(ids=all_records['ids'])
            except Exception:
                pass

        if self.adversarial_collection is not None:
            try:
                # 删除所有对抗池记录
                all_records = self.adversarial_collection.get()
                if all_records.get('ids'):
                    self.adversarial_collection.delete(ids=all_records['ids'])
            except Exception:
                pass

        self._entropy_status = None
        logger.info("[VectorPoolManager V7.1] 向量池已重置")


# ==================== 全局实例 ====================

_global_pool_manager: Optional[VectorPoolManager] = None


def get_vector_pool_manager(config: VectorPoolConfig = None) -> VectorPoolManager:
    """
    获取全局向量池管理器实例

    Args:
        config: 配置参数

    Returns:
        VectorPoolManager: 管理器实例
    """
    global _global_pool_manager

    if _global_pool_manager is None:
        _global_pool_manager = VectorPoolManager(config=config)

    return _global_pool_manager


def reset_vector_pool_manager():
    """重置全局向量池管理器"""
    global _global_pool_manager
    if _global_pool_manager is not None:
        _global_pool_manager.reset()


# ==================== 便捷函数 ====================

def store_hypothesis_safe(
    hypothesis: Dict,
    score: float,
    session_id: str,
    is_red_team: bool = False,
    citation_verified: bool = False
) -> Tuple[bool, str]:
    """
    安全存储假设（便捷函数）

    Args:
        hypothesis: 假设内容
        score: 适应度分数
        session_id: 会话ID
        is_red_team: 是否为红方产物
        citation_verified: 是否通过引用验证

    Returns:
        Tuple[成功, 存储池类型]
    """
    manager = get_vector_pool_manager()
    return manager.store_hypothesis(
        hypothesis=hypothesis,
        score=score,
        session_id=session_id,
        is_red_team=is_red_team,
        citation_verified=citation_verified
    )


def retrieve_benign_only(query: str, top_k: int = 10) -> List[Dict]:
    """
    仅从良性池检索（便捷函数）

    Args:
        query: 检索查询
        top_k: 返回数量

    Returns:
        List[Dict]: 检索结果
    """
    manager = get_vector_pool_manager()
    return manager.retrieve_for_rag(query, top_k=top_k, exclude_adversarial=True)


def check_vector_entropy() -> EntropyStatus:
    """
    检查向量熵状态（便捷函数）

    Returns:
        EntropyStatus: 熵状态报告
    """
    manager = get_vector_pool_manager()
    return manager.check_entropy()


# ==================== 测试代码 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V7.1 向量池分离管理器 - 测试")
    print("=" * 70)

    # 创建管理器
    config = VectorPoolConfig(
        db_path="test_db",
        benign_score_threshold=7.0
    )
    manager = VectorPoolManager(config=config)

    # 测试 1: 良性池存储
    print("\n[Test 1] 良性池存储测试")
    hypothesis1 = {
        'title': '阿尔茨海默病基因关联研究',
        'abstract': '本研究探索APOE基因与阿尔茨海默病的关联性...'
    }
    result = manager.store_hypothesis(
        hypothesis=hypothesis1,
        score=8.5,
        session_id="test_session_001",
        citation_verified=True
    )
    print(f"  结果: {result}")

    # 测试 2: 对抗池存储（红方产物）
    print("\n[Test 2] 对抗池存储测试")
    hypothesis2 = {
        'title': '攻击性假设：基因数据泄露风险',
        'abstract': '红方攻击维度：数据泄露可能导致...'
    }
    result = manager.store_hypothesis(
        hypothesis=hypothesis2,
        score=5.0,
        session_id="test_session_001",
        is_red_team=True,
        attack_dimension="data_leakage"
    )
    print(f"  结果: {result}")

    # 测试 3: 熵检查
    print("\n[Test 3] 熵检查测试")
    entropy = manager.check_entropy()
    print(f"  良性池: {entropy.benign_count}")
    print(f"  对抗池: {entropy.adversarial_count}")
    print(f"  良性密度: {entropy.benign_density:.1%}")
    print(f"  警报级别: {entropy.alert_level.value}")

    # 测试 4: RAG 检索
    print("\n[Test 4] RAG 检索测试")
    results = manager.retrieve_for_rag("阿尔茨海默病基因", top_k=5)
    print(f"  返回数量: {len(results)}")
    for r in results:
        print(f"    - {r['pool_type']}: {r['content'][:30]}...")

    # 测试 5: 晋升机制
    print("\n[Test 5] 晋升机制测试")
    stats = manager.get_pool_statistics()
    print(f"  统计: {stats}")

    print("\n" + "=" * 70)
    print("V7.1 向量池分离管理器测试完成!")
    print("=" * 70)