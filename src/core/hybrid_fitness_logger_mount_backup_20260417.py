# -*- coding: utf-8 -*-
"""
V6.1 混合适应度函数 (Hybrid Fitness Function)

防奖励欺骗核心模块 - 创新度降维 + 甜点区算法

核心机制：
1. 向量距离计算（降维打击）
2. 甜点区算法 (Adjacent Possible)
3. 物理铁闸熔断
4. 权重组合：创新分 × 0.6 + 红方严谨分 × 0.4

作者: 架构师 V6.1
日期: 2026-04-16
"""

import json
import threading
import re
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

# ==================== V7.1: 集中式日志挂载 ====================
from src.utils.logger import get_central_logger, AUDIT_LEVEL, log_exceptions

logger = get_central_logger()


# ==================== 常量配置 ====================

# 甜点区参数 (Adjacent Possible)
SIMILARITY_UPPER_BOUND = 0.85  # > 0.85 = 洗稿 → 0分
SIMILARITY_LOWER_BOUND = 0.20  # < 0.20 = 瞎编 → 0分
OPTIMAL_RANGE_LOW = 0.40       # 甜点区下界
OPTIMAL_RANGE_HIGH = 0.65      # 甜点区上界
PEAK_SIMILARITY = 0.52         # 最佳创新甜点中心

# 权重配置
VECTOR_NOVELTY_WEIGHT = 0.6    # 向量创新分权重
RED_TEAM_RIGOR_WEIGHT = 0.4    # 红方严谨分权重

# V7.0 语义深度校验权重
FILTERED_SIMILARITY_WEIGHT = 0.3  # 过滤后相似度权重
METHODOLOGY_ALIGNMENT_WEIGHT = 0.3  # 方法论一致性权重
RAW_SIMILARITY_WEIGHT = 0.4  # 原始相似度权重

# 嵌入模型配置
DEFAULT_EMBEDDER_MODEL = 'all-MiniLM-L6-v2'  # 默认使用轻量模型


# ==================== V7.0 语义深度校验器 ====================

class SemanticDepthValidator:
    """
    V7.0 语义深度校验器 - 防止甜点区逆向欺骗

    问题：高频学术词汇（Transformer, AI, deep learning）嵌入向量方向趋同
    攻击者可构造"高相似度但错误方法论"的假设获得高分

    解决方案：
    1. 过滤高频学术泛词
    2. 方法论一致性校验（LLM辅助）
    3. 综合相似度计算
    """

    # 高频学术泛词过滤列表（这些词汇会拉高余弦相似度但无实际方法论意义）
    HIGH_FREQUENCY_BUZZWORDS = [
        # AI/ML 通用词汇
        'transformer', 'deep learning', 'ai', 'machine learning',
        'neural network', 'artificial intelligence', 'ml', 'dl',
        'precision medicine', 'big data', 'data-driven', 'computational',
        'algorithm', 'model', 'framework', 'approach', 'method', 'novel',
        'innovative', 'advanced', 'state-of-the-art', 'cutting-edge',
        # 研究通用词汇
        'analysis', 'study', 'research', 'investigation', 'examination',
        'exploration', 'assessment', 'evaluation', 'investigate', 'analyze',
        # 结果描述词汇
        'significant', 'important', 'critical', 'essential', 'key',
        'potential', 'promising', 'remarkable', 'notable', 'substantial',
        # 生物医学通用词汇（过于宽泛）
        'biological', 'clinical', 'medical', 'health', 'disease',
        'patient', 'treatment', 'therapy', 'outcome', 'result'
    ]

    # 方法论关键词映射（用于提取核心方法论）
    METHODOLOGY_KEYWORDS = {
        'molecular_docking': ['docking', 'binding', 'affinity', 'pose', 'score',
                               'vina', 'autodock', 'gold', 'glide', 'boltz'],
        'genomics': ['gwas', 'variant', 'snp', 'allele', 'gene', 'mutation',
                     'sequencing', 'genotype', 'phenotype', 'association'],
        'transcriptomics': ['rna-seq', 'expression', 'transcript', 'mrna',
                            'differential', 'profile', 'regulation'],
        'proteomics': ['protein', 'peptide', 'mass spectrometry', 'ms',
                       'proteome', 'phosphorylation', 'acetylation'],
        'machine_learning': ['classification', 'prediction', 'regression',
                             'clustering', 'feature', 'training', 'validation',
                             'cross-validation', 'auc', 'roc'],
        'statistical': ['p-value', 'confidence interval', 'hazard ratio',
                        'odds ratio', 'correlation', 'regression', 'adjustment'],
        'imaging': ['mri', 'ct', 'pet', 'imaging', 'segmentation', 'radiomics',
                   'deep learning imaging', 'computer vision']
    }

    def __init__(self, llm_client=None):
        """
        初始化语义深度校验器

        Args:
            llm_client: LLM 客户端（用于方法论一致性校验）
        """
        self.llm_client = llm_client
        self._methodology_cache: Dict[str, str] = {}

    def filter_buzzwords(self, text: str) -> str:
        """
        过滤高频学术泛词，降低欺骗可能性

        Args:
            text: 原始文本

        Returns:
            str: 过滤后的文本
        """
        filtered = text.lower()
        for word in self.HIGH_FREQUENCY_BUZZWORDS:
            # 使用正则表达式匹配并替换
            filtered = re.sub(r'\b' + re.escape(word) + r'\b', '', filtered, flags=re.IGNORECASE)

        # 清理多余空格
        filtered = ' '.join(filtered.split())
        return filtered.strip()

    def extract_methodology_keywords(self, text: str) -> List[str]:
        """
        提取方法论关键词

        Args:
            text: 输入文本

        Returns:
            List[str]: 匹配到的方法论类别列表
        """
        text_lower = text.lower()
        matched_categories = []

        for category, keywords in self.METHODOLOGY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    matched_categories.append(category)
                    break

        return matched_categories

    def check_methodology_alignment(
        self,
        hypothesis_text: str,
        doc_texts: List[str]
    ) -> Tuple[float, str]:
        """
        方法论一致性校验

        检测假设的核心方法论是否与文献方法论在同一学科范式

        Args:
            hypothesis_text: 假设文本
            doc_texts: 文献文本列表

        Returns:
            Tuple[float, str]: (一致性分数, 解释)
        """
        # 提取假设方法论
        hyp_methodologies = self.extract_methodology_keywords(hypothesis_text)

        if not hyp_methodologies:
            # 假设未明确方法论，返回中等分数
            return 0.5, "假设方法论不明确"

        # 提取文献方法论
        doc_methodologies = []
        for doc_text in doc_texts:
            doc_methodologies.extend(self.extract_methodology_keywords(doc_text))

        if not doc_methodologies:
            # 文献未明确方法论，返回中等分数
            return 0.5, "文献方法论不明确"

        # 计算方法论重叠度
        hyp_set = set(hyp_methodologies)
        doc_set = set(doc_methodologies)

        intersection = hyp_set & doc_set
        union = hyp_set | doc_set

        jaccard = len(intersection) / len(union) if union else 0.0

        # 转换为一致性分数（0-1）
        alignment_score = jaccard

        # 生成解释
        if alignment_score >= 0.7:
            explanation = f"方法论高度一致 ({intersection})"
        elif alignment_score >= 0.3:
            explanation = f"方法论部分一致 ({intersection}), 假设方法: {hyp_set}, 文献方法: {doc_set}"
        else:
            explanation = f"方法论不一致，假设使用 {hyp_set}，文献使用 {doc_set}"

        return alignment_score, explanation

    def check_methodology_alignment_with_llm(
        self,
        hypothesis_text: str,
        doc_texts: List[str]
    ) -> Tuple[float, str]:
        """
        方法论一致性校验（LLM 增强版）

        使用 LLM 进行更深入的方法论语义分析

        Args:
            hypothesis_text: 假设文本
            doc_texts: 文献文本列表

        Returns:
            Tuple[float, str]: (一致性分数, 解释)
        """
        if self.llm_client is None:
            # 回退到无 LLM 版本
            return self.check_methodology_alignment(hypothesis_text, doc_texts)

        try:
            # 提取方法论关键词
            hyp_methodologies = self.extract_methodology_keywords(hypothesis_text)

            # 构建 LLM 提示词
            prompt = f"""
判断以下假设的核心方法论是否与参考文献的方法论在同一学科范式。

假设内容（前500字符）:
{hypothesis_text[:500]}

假设方法论关键词: {hyp_methodologies}

参考文献摘要（前300字符）:
{doc_texts[0][:300] if doc_texts else '无参考文献'}

请以 JSON 格式回答（只输出 JSON，不要其他内容）:
{
  "alignment_score": 0.0-1.0,
  "same_paradigm": true或false,
  "explanation": "简要说明理由（30字以内）"
}
"""

            # LLM 校验（使用低温度确保稳定性）
            import anthropic
            message = self.llm_client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=200,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text

            # 解析 JSON 响应
            try:
                # 尝试提取 JSON 块
                json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = json.loads(response_text)

                alignment_score = float(result.get('alignment_score', 0.5))
                explanation = result.get('explanation', 'LLM 校验完成')

                return alignment_score, explanation

            except json.JSONDecodeError:
                # JSON 解析失败，回退
                return 0.5, "LLM 响应解析失败"

        except Exception as e:
            logger.warning(f"[SemanticDepthValidator] LLM 校验失败: {e}")
            # 回退到无 LLM 版本
            return self.check_methodology_alignment(hypothesis_text, doc_texts)

    def calculate_composite_similarity(
        self,
        raw_similarity: float,
        filtered_similarity: float,
        alignment_score: float
    ) -> float:
        """
        计算综合相似度

        综合相似度 = 原始相似度 × RAW_SIMILARITY_WEIGHT +
                     过滤后相似度 × FILTERED_SIMILARITY_WEIGHT +
                     方法论一致性 × METHODOLOGY_ALIGNMENT_WEIGHT

        Args:
            raw_similarity: 原始余弦相似度
            filtered_similarity: 过滤高频词后的余弦相似度
            alignment_score: 方法论一致性分数

        Returns:
            float: 综合相似度 (0-1)
        """
        composite = (
            raw_similarity * RAW_SIMILARITY_WEIGHT +
            filtered_similarity * FILTERED_SIMILARITY_WEIGHT +
            alignment_score * METHODOLOGY_ALIGNMENT_WEIGHT
        )
        return min(1.0, max(0.0, composite))


# ==================== 结果数据类 ====================


@dataclass
class FitnessResult:
    """
    适应度评估结果

    包含详细的评分信息和验证状态
    """
    hybrid_fitness: float = 0.0
    vector_novelty_score: float = 0.0
    red_team_rigor_score: float = 0.0
    physical_validation: Dict = field(default_factory=dict)
    fused: bool = False
    fuse_reason: str = ""
    similarity: float = 0.5
    similarity_interpretation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'hybrid_fitness': self.hybrid_fitness,
            'vector_novelty_score': self.vector_novelty_score,
            'red_team_rigor_score': self.red_team_rigor_score,
            'physical_validation': self.physical_validation,
            'fused': self.fused,
            'fuse_reason': self.fuse_reason,
            'similarity': self.similarity,
            'similarity_interpretation': self.similarity_interpretation,
            'timestamp': self.timestamp
        }


class HybridFitnessScorer:
    """
    混合适应度打分器

    创新度 = (客观向量创新分 × 0.6) + (红方严谨分 × 0.4)

    核心机制：
    1. 向量距离计算（降维打击）
    2. 甜点区算法 (Adjacent Possible)
    3. 物理铁闸熔断

    设计理念：
    - 剥夺红方对创新性 (Novelty) 的评估权限
    - 创新性由客观向量距离锚定
    - 红方只负责严谨性 (Rigor) 审查
    """

    def __init__(
        self,
        embedder_model: str = DEFAULT_EMBEDDER_MODEL,
        enable_physical_validation: bool = True
    ):
        """
        初始化混合打分器

        Args:
            embedder_model: 向量嵌入模型名称
            enable_physical_validation: 是否启用物理铁闸校验
        """
        self.embedder_model = embedder_model
        self.enable_physical_validation = enable_physical_validation

        # 嵌入器（延迟初始化）
        self._embedder = None
        self._embedder_lock = threading.Lock()

        # 物理验证器
        self._physical_validator = None

        logger.info(f"[HybridFitnessScorer] 初始化完成")
        logger.info(f"  embedder_model: {embedder_model}")
        logger.info(f"  enable_physical_validation: {enable_physical_validation}")
        logger.info(f"  甜点区: [{OPTIMAL_RANGE_LOW}, {OPTIMAL_RANGE_HIGH}]")
        logger.info(f"  权重: vector={VECTOR_NOVELTY_WEIGHT}, rigor={RED_TEAM_RIGOR_WEIGHT}")

    def _init_embedder(self):
        """
        延迟初始化向量嵌入器

        使用 sentence-transformers 模型
        """
        if self._embedder is not None:
            return

        with self._embedder_lock:
            if self._embedder is not None:
                return

            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer(self.embedder_model)
                logger.info(f"[HybridFitnessScorer] 嵌入器加载成功: {self.embedder_model}")

            except ImportError:
                logger.warning("[HybridFitnessScorer] sentence-transformers 未安装，使用回退方法")
                self._embedder = None

            except Exception as e:
                logger.warning(f"[HybridFitnessScorer] 嵌入器加载失败: {e}")
                self._embedder = None

    def _init_physical_validator(self):
        """初始化物理验证器"""
        if self._physical_validator is None and self.enable_physical_validation:
            try:
                from core.physical_validator import PhysicalValidator
                self._physical_validator = PhysicalValidator()
                logger.info("[HybridFitnessScorer] 物理验证器加载成功")
            except ImportError:
                logger.warning("[HybridFitnessScorer] 物理验证器模块未找到")
                self._physical_validator = None
            except Exception as e:
                logger.warning(f"[HybridFitnessScorer] 物理验证器加载失败: {e}")
                self._physical_validator = None

    @property
    def embedder(self):
        """获取嵌入器（延迟初始化）"""
        self._init_embedder()
        return self._embedder

    @property
    def physical_validator(self):
        """获取物理验证器（延迟初始化）"""
        self._init_physical_validator()
        return self._physical_validator

    # ==================== 核心评估函数 ====================

    def calculate_fitness(
        self,
        hypothesis_json: Dict,
        retrieved_docs: List[Dict],
        red_team_rigor_score: float = None,
        enable_semantic_depth_validation: bool = True,
        enable_methodology_validation: bool = True,  # V7.1 新增
        llm_client: Any = None
    ) -> FitnessResult:
        """
        V7.1 核心评估函数 - 集成方法论语义验证

        流程：
        1. V7.1 方法论语义验证（防止甜点区逆向欺骗）
        2. 物理铁闸校验（若失败 → 立即熔断）
        3. V7.0 语义深度校验（防止甜点区逆向欺骗）
        4. 向量创新度计算（甜点区算法）
        5. 红方严谨分整合
        6. 混合得分计算

        Args:
            hypothesis_json: 假设数据（包含 title, details, scores）
            retrieved_docs: 检索到的真实文献列表
            red_team_rigor_score: 红方严谨分（可选）
            enable_semantic_depth_validation: 是否启用语义深度校验（V7.0新增）
            enable_methodology_validation: 是否启用方法论验证（V7.1新增）
            llm_client: LLM客户端（用于方法论一致性校验）

        Returns:
            FitnessResult: 混合适应度评估结果
        """
        result = FitnessResult()

        # V7.1 Step 0: 方法论语义验证（防止甜点区逆向欺骗）
        methodology_multiplier = 1.0
        if enable_methodology_validation:
            try:
                from utils.methodology_validator import validate_methodology, MethodologyValidationResult
                hypothesis_text = hypothesis_json.get('title', '') + '\n' + hypothesis_json.get('details', '')

                methodology_result = validate_methodology(hypothesis_text, strict_mode=True)

                if not methodology_result.is_valid:
                    # 工具-任务不匹配 → 熔断
                    result.fused = True
                    result.fuse_reason = methodology_result.message
                    result.hybrid_fitness = 0.0
                    result.vector_novelty_score = 0.0
                    result.red_team_rigor_score = 0.0
                    result.similarity_interpretation = f"方法论验证熔断: {methodology_result.message}"
                    logger.warning(f"[HybridFitnessScorer V7.1] 方法论验证熔断: {methodology_result.message}")
                    return result

                # 获取分数乘数
                methodology_multiplier = methodology_result.score_multiplier
                logger.info(f"[HybridFitnessScorer V7.1] 方法论验证通过，乘数={methodology_multiplier}")

            except ImportError:
                logger.warning("[HybridFitnessScorer V7.1] methodology_validator 未安装，跳过")
            except Exception as e:
                logger.warning(f"[HybridFitnessScorer V7.1] 方法论验证异常: {e}")

        # Step 1: 物理铁闸校验
        if self.enable_physical_validation and self.physical_validator:
            physical_result = self.physical_validator.validate_hypothesis_physical(hypothesis_json)
            result.physical_validation = {
                'passed': physical_result.passed,
                'details': physical_result.details,
                'failure_reason': physical_result.failure_reason
            }

            if not physical_result.passed:
                # V7.1: AUDIT 级别日志（业务驳回）
                logger.audit(
                    f"[驳回] 物理铁闸熔断\n"
                    f"  失败原因: {physical_result.failure_reason}\n"
                    f"  校验详情: {physical_result.details}"
                )
                result.fused = True
                result.fuse_reason = physical_result.failure_reason
                result.hybrid_fitness = 0.0
                result.vector_novelty_score = 0.0
                result.red_team_rigor_score = 0.0
                result.similarity_interpretation = "物理铁闸熔断"
                logger.warning(f"物理铁闸熔断: {physical_result.failure_reason}")
                return result

        # V7.0 Step 2: 语义深度校验（防止甜点区逆向欺骗）
        semantic_depth_result = {
            'alignment_score': 0.5,
            'filtered_similarity': 0.5,
            'explanation': ''
        }

        if enable_semantic_depth_validation:
            semantic_validator = SemanticDepthValidator(llm_client=llm_client)

            # 合并假设文本
            hyp_text = hypothesis_json.get('title', '') + '\n' + hypothesis_json.get('details', '')

            # 合并文献文本
            doc_texts = []
            for doc in retrieved_docs:
                doc_text = doc.get('title', '') + '\n' + (doc.get('abstract', '') or '')
                doc_texts.append(doc_text)

            # 2.1: 过滤高频词汇后的相似度
            hyp_text_filtered = semantic_validator.filter_buzzwords(hyp_text)
            filtered_similarity = self.get_cosine_similarity(hyp_text_filtered, doc_texts)
            semantic_depth_result['filtered_similarity'] = filtered_similarity

            # 2.2: 方法论一致性校验
            if llm_client:
                alignment_score, explanation = semantic_validator.check_methodology_alignment_with_llm(
                    hyp_text, doc_texts
                )
            else:
                alignment_score, explanation = semantic_validator.check_methodology_alignment(
                    hyp_text, doc_texts
                )
            semantic_depth_result['alignment_score'] = alignment_score
            semantic_depth_result['explanation'] = explanation

            # 2.3: 如果方法论一致性过低，记录警告
            if alignment_score < 0.3:
                logger.warning(f"[V7.0 SemanticDepth] 方法论不一致警告: {explanation}")

        # Step 3: 向量创新度计算（原始）
        vector_score, raw_similarity, interpretation = self._calculate_vector_novelty(
            hypothesis_json,
            retrieved_docs
        )

        # V7.0: 使用综合相似度重新计算得分
        if enable_semantic_depth_validation:
            composite_similarity = semantic_validator.calculate_composite_similarity(
                raw_similarity,
                semantic_depth_result['filtered_similarity'],
                semantic_depth_result['alignment_score']
            )

            # 使用综合相似度重新映射得分
            composite_score, composite_interpretation = self._map_similarity_to_score(composite_similarity)

            # 方法论一致性过低时降分
            if semantic_depth_result['alignment_score'] < 0.3:
                composite_score *= 0.5  # 降分 50%
                composite_interpretation += " (方法论不一致警告)"

            result.vector_novelty_score = composite_score
            result.similarity = composite_similarity
            result.similarity_interpretation = composite_interpretation
        else:
            result.vector_novelty_score = vector_score
            result.similarity = raw_similarity
            result.similarity_interpretation = interpretation

        # Step 4: 红方严谨分
        if red_team_rigor_score is not None:
            result.red_team_rigor_score = red_team_rigor_score
        else:
            scores = hypothesis_json.get('scores', {})
            result.red_team_rigor_score = scores.get('rigor', scores.get('overall', 7.5))

        # Step 5: V7.1 混合得分计算（应用方法论乘数）
        base_fitness = (
            result.vector_novelty_score * VECTOR_NOVELTY_WEIGHT +
            result.red_team_rigor_score * RED_TEAM_RIGOR_WEIGHT
        )

        # V7.1: 应用方法论验证乘数
        result.hybrid_fitness = base_fitness * methodology_multiplier

        logger.info(f"[HybridFitnessScorer V7.1] 评估完成:")
        logger.info(f"  原始相似度: {raw_similarity:.3f}")
        logger.info(f"  过滤后相似度: {semantic_depth_result['filtered_similarity']:.3f}")
        logger.info(f"  方法论一致性: {semantic_depth_result['alignment_score']:.3f}")
        logger.info(f"  综合相似度: {result.similarity:.3f} ({result.similarity_interpretation})")
        logger.info(f"  向量创新分: {result.vector_novelty_score:.2f}")
        logger.info(f"  红方严谨分: {result.red_team_rigor_score:.2f}")
        logger.info(f"  基础得分: {base_fitness:.2f}")
        logger.info(f"  方法论乘数: {methodology_multiplier}")
        logger.info(f"  最终混合得分: {result.hybrid_fitness:.2f}")

        return result

    def get_cosine_similarity(
        self,
        hypothesis_text: str,
        doc_texts: List[str]
    ) -> float:
        """
        计算假说与检索文献的向量余弦相似度

        Args:
            hypothesis_text: 假设文本（title + details 合并）
            doc_texts: 文献文本列表（title + abstract 合并）

        Returns:
            float: 平均余弦相似度 (0-1)
        """
        # 初始化嵌入器
        if self.embedder is None:
            # 回退到简单文本相似度
            return self._fallback_similarity(hypothesis_text, doc_texts)

        try:
            # 计算假设嵌入
            hyp_embedding = self.embedder.encode(hypothesis_text)

            if not doc_texts:
                return 0.5  # 无文献时返回中性值

            # 计算文献嵌入
            doc_embeddings = self.embedder.encode(doc_texts)

            # 计算余弦相似度
            hyp_norm = np.linalg.norm(hyp_embedding)
            similarities = []

            for doc_emb in doc_embeddings:
                doc_norm = np.linalg.norm(doc_emb)
                if hyp_norm > 0 and doc_norm > 0:
                    sim = np.dot(hyp_embedding, doc_emb) / (hyp_norm * doc_norm)
                    # 转换到 [0, 1] 范围
                    sim = (sim + 1) / 2
                    similarities.append(sim)

            return np.mean(similarities) if similarities else 0.5

        except Exception as e:
            # V7.1: 深水区异常捕获 - 记录完整堆栈和关键变量
            logger.exception(
                "向量计算异常（深水区）",
                extra_vars={
                    'hypothesis_text_len': len(hypothesis_text),
                    'doc_texts_count': len(doc_texts),
                    'embedder_model': self.embedder_model,
                    'exception_type': type(e).__name__
                }
            )
            return self._fallback_similarity(hypothesis_text, doc_texts)

    def _fallback_similarity(self, hypothesis_text: str, doc_texts: List[str]) -> float:
        """
        回退相似度计算（当嵌入器不可用时）

        使用简单的关键词重叠率

        Args:
            hypothesis_text: 假设文本
            doc_texts: 文献文本列表

        Returns:
            float: 简化相似度 (0-1)
        """
        if not doc_texts:
            return 0.5

        # 简单的关键词提取
        hyp_keywords = set(hypothesis_text.lower().split())
        hyp_keywords = {w for w in hyp_keywords if len(w) > 3}  # 过滤短词

        similarities = []
        for doc_text in doc_texts:
            doc_keywords = set(doc_text.lower().split())
            doc_keywords = {w for w in doc_keywords if len(w) > 3}

            if hyp_keywords and doc_keywords:
                overlap = len(hyp_keywords & doc_keywords)
                union = len(hyp_keywords | doc_keywords)
                jaccard = overlap / union if union > 0 else 0
                similarities.append(jaccard)

        return np.mean(similarities) if similarities else 0.5

    def _calculate_vector_novelty(
        self,
        hypothesis_json: Dict,
        retrieved_docs: List[Dict]
    ) -> Tuple[float, float, str]:
        """
        甜点区算法 - 创新度降维

        相似度 > 0.85 → 洗稿 → 0分
        相似度 < 0.20 → 瞎编 → 0分
        0.40-0.65 → 甜点区 → 极高分 (9-10)
        其他 → 线性过渡

        Args:
            hypothesis_json: 假设数据
            retrieved_docs: 检索到的文献列表

        Returns:
            Tuple[float, float, str]: (得分, 相似度, 解释)
        """
        # 合并假设文本
        hyp_text = hypothesis_json.get('title', '') + '\n' + hypothesis_json.get('details', '')

        # 合并文献文本
        doc_texts = []
        for doc in retrieved_docs:
            doc_text = doc.get('title', '') + '\n' + (doc.get('abstract', '') or '')
            doc_texts.append(doc_text)

        # 计算相似度
        similarity = self.get_cosine_similarity(hyp_text, doc_texts)

        # 甜点区映射
        score, interpretation = self._map_similarity_to_score(similarity)

        return score, similarity, interpretation

    def _map_similarity_to_score(self, similarity: float) -> Tuple[float, str]:
        """
        将相似度映射到创新分（甜点区算法）

        Args:
            similarity: 余弦相似度 (0-1)

        Returns:
            Tuple[float, str]: (得分, 解释)
        """
        # 洗稿检测（相似度 > 0.85）
        if similarity > SIMILARITY_UPPER_BOUND:
            return 0.0, "洗稿嫌疑（与现有文献高度相似）"

        # 瞎编检测（相似度 < 0.20）
        if similarity < SIMILARITY_LOWER_BOUND:
            return 0.0, "瞎编嫌疑（与现有文献完全不相关）"

        # 甜点区（0.40-0.65）
        if OPTIMAL_RANGE_LOW <= similarity <= OPTIMAL_RANGE_HIGH:
            # 高斯分布峰值
            peak_distance = abs(similarity - PEAK_SIMILARITY)
            # 使用高斯函数映射到 9-10 分
            gaussian_score = 10.0 * np.exp(-(peak_distance ** 2) / 0.02)

            # 确保分数在 9-10 范围内
            score = min(10.0, max(9.0, gaussian_score))

            if similarity < PEAK_SIMILARITY:
                interpretation = "创新甜点区（恰到好处的创新度）"
            elif similarity == PEAK_SIMILARITY:
                interpretation = "完美创新甜点（最佳平衡点）"
            else:
                interpretation = "创新甜点区（适度参考现有研究）"

            return score, interpretation

        # 线性过渡区
        if similarity < OPTIMAL_RANGE_LOW:
            # 0.20-0.40: 线性从 0 → 9
            ratio = (similarity - SIMILARITY_LOWER_BOUND) / (OPTIMAL_RANGE_LOW - SIMILARITY_LOWER_BOUND)
            score = ratio * 9.0
            interpretation = "过渡区（创新度偏低但非瞎编）"
            return score, interpretation

        else:
            # 0.65-0.85: 线性从 9 → 0
            ratio = (SIMILARITY_UPPER_BOUND - similarity) / (SIMILARITY_UPPER_BOUND - OPTIMAL_RANGE_HIGH)
            score = ratio * 9.0
            interpretation = "过渡区（创新度偏高但非洗稿）"
            return score, interpretation

    # ==================== 批量评估接口 ====================

    def batch_calculate_fitness(
        self,
        hypotheses: List[Dict],
        retrieved_docs: List[Dict],
        red_team_scores: List[float] = None
    ) -> List[FitnessResult]:
        """
        批量评估多个假设

        Args:
            hypotheses: 假设列表
            retrieved_docs: 文献列表（应用于所有假设）
            red_team_scores: 红方评分列表（可选）

        Returns:
            List[FitnessResult]: 评估结果列表
        """
        results = []

        for i, hyp in enumerate(hypotheses):
            rigor_score = None
            if red_team_scores and i < len(red_team_scores):
                rigor_score = red_team_scores[i]

            result = self.calculate_fitness(hyp, retrieved_docs, rigor_score)
            results.append(result)

        return results

    def get_evaluation_summary(self, results: List[FitnessResult]) -> Dict:
        """
        生成评估结果摘要

        Args:
            results: 评估结果列表

        Returns:
            Dict: 摘要统计
        """
        if not results:
            return {}

        fitness_scores = [r.hybrid_fitness for r in results]
        vector_scores = [r.vector_novelty_score for r in results]
        rigor_scores = [r.red_team_rigor_score for r in results]
        similarities = [r.similarity for r in results]

        fused_count = sum(1 for r in results if r.fused)

        # 统计甜点区命中情况
        sweet_spot_count = sum(
            1 for s in similarities
            if OPTIMAL_RANGE_LOW <= s <= OPTIMAL_RANGE_HIGH
        )

        wash_count = sum(1 for s in similarities if s > SIMILARITY_UPPER_BOUND)
        fake_count = sum(1 for s in similarities if s < SIMILARITY_LOWER_BOUND)

        return {
            'total': len(results),
            'avg_fitness': np.mean(fitness_scores),
            'max_fitness': max(fitness_scores),
            'min_fitness': min(fitness_scores),
            'avg_vector_novelty': np.mean(vector_scores),
            'avg_rigor': np.mean(rigor_scores),
            'avg_similarity': np.mean(similarities),
            'fused_count': fused_count,
            'sweet_spot_hits': sweet_spot_count,
            'wash_count': wash_count,
            'fake_count': fake_count,
            'sweet_spot_rate': sweet_spot_count / len(results)
        }

    # ==================== 配置接口 ====================

    def update_parameters(
        self,
        upper_bound: float = None,
        lower_bound: float = None,
        optimal_low: float = None,
        optimal_high: float = None,
        peak: float = None,
        vector_weight: float = None,
        rigor_weight: float = None
    ) -> None:
        """
        更新甜点区参数

        Args:
            upper_bound: 洗稿阈值
            lower_bound: 瞎编阈值
            optimal_low: 甜点区下界
            optimal_high: 甜点区上界
            peak: 最佳甜点中心
            vector_weight: 向量创新分权重
            rigor_weight: 红方严谨分权重
        """
        global SIMILARITY_UPPER_BOUND, SIMILARITY_LOWER_BOUND
        global OPTIMAL_RANGE_LOW, OPTIMAL_RANGE_HIGH, PEAK_SIMILARITY
        global VECTOR_NOVELTY_WEIGHT, RED_TEAM_RIGOR_WEIGHT

        if upper_bound is not None:
            SIMILARITY_UPPER_BOUND = upper_bound
        if lower_bound is not None:
            SIMILARITY_LOWER_BOUND = lower_bound
        if optimal_low is not None:
            OPTIMAL_RANGE_LOW = optimal_low
        if optimal_high is not None:
            OPTIMAL_RANGE_HIGH = optimal_high
        if peak is not None:
            PEAK_SIMILARITY = peak
        if vector_weight is not None:
            VECTOR_NOVELTY_WEIGHT = vector_weight
        if rigor_weight is not None:
            RED_TEAM_RIGOR_WEIGHT = rigor_weight

        logger.info(f"[HybridFitnessScorer] 参数已更新:")
        logger.info(f"  洗稿阈值: {SIMILARITY_UPPER_BOUND}")
        logger.info(f"  瞎编阈值: {SIMILARITY_LOWER_BOUND}")
        logger.info(f"  甜点区: [{OPTIMAL_RANGE_LOW}, {OPTIMAL_RANGE_HIGH}]")
        logger.info(f"  最佳甜点: {PEAK_SIMILARITY}")
        logger.info(f"  权重: vector={VECTOR_NOVELTY_WEIGHT}, rigor={RED_TEAM_RIGOR_WEIGHT}")

    def get_current_parameters(self) -> Dict:
        """获取当前参数配置"""
        return {
            'upper_bound': SIMILARITY_UPPER_BOUND,
            'lower_bound': SIMILARITY_LOWER_BOUND,
            'optimal_low': OPTIMAL_RANGE_LOW,
            'optimal_high': OPTIMAL_RANGE_HIGH,
            'peak': PEAK_SIMILARITY,
            'vector_weight': VECTOR_NOVELTY_WEIGHT,
            'rigor_weight': RED_TEAM_RIGOR_WEIGHT
        }


# ==================== 全局实例 ====================

_hybrid_fitness_scorer: Optional[HybridFitnessScorer] = None
_scorer_lock = threading.Lock()


def get_hybrid_fitness_scorer(**kwargs) -> HybridFitnessScorer:
    """
    获取全局混合打分器实例

    Args:
        **kwargs: 初始化参数

    Returns:
        HybridFitnessScorer: 全局实例
    """
    global _hybrid_fitness_scorer

    with _scorer_lock:
        if _hybrid_fitness_scorer is None:
            _hybrid_fitness_scorer = HybridFitnessScorer(**kwargs)
        return _hybrid_fitness_scorer


def calculate_hybrid_fitness(
    hypothesis_json: Dict,
    retrieved_docs: List[Dict],
    rigor_score: float = None
) -> FitnessResult:
    """
    便捷函数：计算混合适应度

    Args:
        hypothesis_json: 假设数据
        retrieved_docs: 文献列表
        rigor_score: 红方严谨分（可选）

    Returns:
        FitnessResult: 评估结果
    """
    scorer = get_hybrid_fitness_scorer()
    return scorer.calculate_fitness(hypothesis_json, retrieved_docs, rigor_score)


# ==================== 测试代码 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V6.1 混合适应度打分器 - 测试")
    print("=" * 70)

    scorer = HybridFitnessScorer()

    # 测试 1: 甜点区映射
    print("\n[Test 1] 甜点区算法测试")

    test_similarities = [0.10, 0.25, 0.45, 0.52, 0.60, 0.75, 0.90]
    for sim in test_similarities:
        score, interp = scorer._map_similarity_to_score(sim)
        print(f"  相似度 {sim:.2f} → 得分 {score:.2f} ({interp})")

    # 测试 2: 混合得分计算
    print("\n[Test 2] 混合得分计算")

    hypothesis = {
        'title': '血浆 pQTL 影响阿尔茨海默病认知衰退的中介机制研究',
        'details': '��过因果中介分析探索血浆蛋白对阿尔茨海默病患者认知功能的影响机制...',
        'scores': {'rigor': 8.5}
    }

    docs = [
        {'title': '血浆蛋白与阿尔茨海默病关联研究', 'abstract': '本研究分析了血浆蛋白与阿尔茨海默病的关联...'},
        {'title': '因果中介分析方法综述', 'abstract': '本文综述了因果中介分析在医学研究中的应用...'}
    ]

    result = scorer.calculate_fitness(hypothesis, docs, rigor_score=8.5)
    print(f"  相似度: {result.similarity:.3f}")
    print(f"  向量创新分: {result.vector_novelty_score:.2f}")
    print(f"  红方严谨分: {result.red_team_rigor_score:.2f}")
    print(f"  混合得分: {result.hybrid_fitness:.2f}")
    print(f"  熔断状态: {result.fused}")

    # 测试 3: 批量评估
    print("\n[Test 3] 批量评估")

    hypotheses = [
        {'title': '假设A', 'details': '内容A...', 'scores': {'rigor': 7.5}},
        {'title': '假设B', 'details': '内容B...', 'scores': {'rigor': 8.0}},
        {'title': '假设C', 'details': '内容C...', 'scores': {'rigor': 9.0}}
    ]

    results = scorer.batch_calculate_fitness(hypotheses, docs)
    summary = scorer.get_evaluation_summary(results)

    print(f"  平均得分: {summary['avg_fitness']:.2f}")
    print(f"  最高得分: {summary['max_fitness']:.2f}")
    print(f"  甜点区命中率: {summary['sweet_spot_rate']:.2%}")

    # 测试 4: 参数更新
    print("\n[Test 4] 参数配置")

    params = scorer.get_current_parameters()
    print(f"  当前配置: {params}")

    print("\n" + "=" * 70)
    print("V6.1 混合适应度打分器测试完成!")
    print("=" * 70)