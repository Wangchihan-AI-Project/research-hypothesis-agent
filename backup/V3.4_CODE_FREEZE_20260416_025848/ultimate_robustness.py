# -*- coding: utf-8 -*-
"""
终极鲁棒性防御模块 (Ultimate Robustness Shield) - V3.3

这是系统的最后一道防线，负责防御以下 4 个终极死角：
1. 外部数据投毒与 RAG 注入防御
2. 实验可重复性与确定性快照增强
3. 隐式模态越权监控（硬性物理否决）
4. 运行流的可观测性遥测

作者: 架构师 V3.3
日期: 2026-04-16
"""

import re
import json
import hashlib
import html
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum


# ==============================================================================
# 1. 外部数据投毒与 RAG 注入防御 (Data Poisoning Defense)
# ==============================================================================

class DataSanitizer:
    """
    数据清洗器 - 防止外部脏数据冲垮 Agent

    在将 PubMed 摘要喂给 Agent 之前，必须经过清洗
    """

    # 危险字符模式（可能破坏 JSON 解析或注入攻击）
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS
        r'javascript:',  # JS 注入
        r'on\w+\s*=',  # 事件处理器注入
        r'\x00-\x1F',  # 控制字符
        r'\u2028|\u2029',  # Unicode 行/段分隔符
    ]

    # 撤稿论文警告词
    RETRACTION_KEYWORDS = [
        'retraction', 'retracted', 'withdrawn', 'expression of concern',
        '撤回', '撤销', '撤稿', '关注声明'
    ]

    # 最大安全长度（防止超长摘要撑爆上下文）
    MAX_ABSTRACT_LENGTH = 5000
    MAX_TITLE_LENGTH = 500

    @classmethod
    def sanitize_paper(cls, paper: Dict) -> Dict:
        """
        清洗单篇论文数据

        Args:
            paper: 原始论文数据

        Returns:
            清洗后的论文数据
        """
        sanitized = {}

        # 清洗标题
        title = paper.get('title', '')
        sanitized['title'] = cls._sanitize_text(title, max_length=cls.MAX_TITLE_LENGTH)

        # 清洗摘要
        abstract = paper.get('abstract', '')
        sanitized['abstract'] = cls._sanitize_text(abstract, max_length=cls.MAX_ABSTRACT_LENGTH)

        # 撤稿检测
        sanitized['is_retracted'] = cls._check_retraction(sanitized['title'] + ' ' + sanitized['abstract'])

        # 保留原始 PMID
        sanitized['pmid'] = paper.get('pmid', '')

        # 其他字段（直接复制）
        for key in ['journal', 'publication_date', 'authors', 'doi']:
            if key in paper:
                sanitized[key] = paper[key]

        return sanitized

    @classmethod
    def _sanitize_text(cls, text: str, max_length: int = 5000) -> str:
        """清洗文本"""
        if not text:
            return ""

        # 1. HTML 转义
        text = html.escape(text)

        # 2. 移除危险模式
        for pattern in cls.DANGEROUS_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)

        # 3. 移除控制字符（保留换行符和制表符）
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

        # 4. 规范化空白字符
        text = ' '.join(text.split())

        # 5. 长度截断
        if len(text) > max_length:
            text = text[:max_length] + "...[truncated]"

        return text

    @classmethod
    def _check_retraction(cls, text: str) -> bool:
        """检测是否为撤稿论文"""
        text_lower = text.lower()
        for keyword in cls.RETRACTION_KEYWORDS:
            if keyword in text_lower:
                return True
        return False

    @classmethod
    def sanitize_paper_list(cls, papers: List[Dict]) -> Tuple[List[Dict], Dict]:
        """
        清洗论文列表

        Returns:
            (清洗后的论文列表, 清洗报告)
        """
        sanitized_papers = []
        report = {
            'total_input': len(papers),
            'retracted_count': 0,
            'truncated_count': 0,
            'sanitized_count': 0
        }

        for paper in papers:
            sanitized = cls.sanitize_paper(paper)

            if sanitized.get('is_retracted'):
                report['retracted_count'] += 1
                continue  # 跳过撤稿论文

            sanitized_papers.append(sanitized)

            if '[truncated]' in sanitized.get('abstract', ''):
                report['truncated_count'] += 1

            report['sanitized_count'] += 1

        return sanitized_papers, report


# ==============================================================================
# 2. 实验可重复性与确定性快照增强
# ==============================================================================

@dataclass
class ExperimentSnapshot:
    """实验快照 - 记录所有可复现性关键信息"""
    snapshot_id: str
    timestamp: str
    research_topic: str

    # LLM 参数（锁死随机性）
    model: str = ""
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 42

    # 环境参数
    python_version: str = ""
    working_directory: str = ""

    # 引用数据（PMID 列表）
    pmid_list: List[str] = field(default_factory=list)

    # 输出摘要
    hypothesis_count: int = 0
    hypothesis_titles: List[str] = field(default_factory=list)

    # 性能指标
    total_tokens_used: int = 0
    execution_time_seconds: float = 0.0

    # 完整输出哈希（用于验证）
    output_hash: str = ""

    def to_dict(self) -> Dict:
        return {
            'snapshot_id': self.snapshot_id,
            'timestamp': self.timestamp,
            'research_topic': self.research_topic,
            'llm_params': {
                'model': self.model,
                'temperature': self.temperature,
                'top_p': self.top_p,
                'seed': self.seed
            },
            'environment': {
                'python_version': self.python_version,
                'working_directory': self.working_directory
            },
            'data_provenance': {
                'pmid_list': self.pmid_list,
                'paper_count': len(self.pmid_list)
            },
            'output_summary': {
                'hypothesis_count': self.hypothesis_count,
                'hypothesis_titles': self.hypothesis_titles
            },
            'performance': {
                'total_tokens_used': self.total_tokens_used,
                'execution_time_seconds': self.execution_time_seconds
            },
            'verification': {
                'output_hash': self.output_hash
            }
        }


class SnapshotManager:
    """快照管理器 - 确保实验可复现"""

    def __init__(self, snapshot_dir: str = 'snapshots'):
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(
        self,
        research_topic: str,
        llm_params: Dict,
        papers: List[Dict],
        hypotheses: List[Dict],
        execution_stats: Dict
    ) -> ExperimentSnapshot:
        """创建实验快照"""
        import sys
        import hashlib

        # 生成快照 ID
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        content_hash = hashlib.md5(
            f"{research_topic}{llm_params}{len(papers)}".encode()
        ).hexdigest()[:8]
        snapshot_id = f"snap_{timestamp}_{content_hash}"

        # 提取 PMID 列表
        pmid_list = [p.get('pmid', '') for p in papers if p.get('pmid')]

        # 计算输出哈希
        output_content = json.dumps(hypotheses, sort_keys=True, ensure_ascii=False)
        output_hash = hashlib.sha256(output_content.encode()).hexdigest()[:16]

        # 创建快照
        snapshot = ExperimentSnapshot(
            snapshot_id=snapshot_id,
            timestamp=datetime.now().isoformat(),
            research_topic=research_topic,
            model=llm_params.get('model', ''),
            temperature=llm_params.get('temperature', 0.0),
            top_p=llm_params.get('top_p', 1.0),
            seed=llm_params.get('seed', 42),
            python_version=sys.version,
            working_directory=sys.path.prefix,
            pmid_list=pmid_list,
            hypothesis_count=len(hypotheses),
            hypothesis_titles=[h.get('title', '') for h in hypotheses],
            total_tokens_used=execution_stats.get('total_tokens', 0),
            execution_time_seconds=execution_stats.get('execution_time', 0.0),
            output_hash=output_hash
        )

        # 保存快照
        self._save_snapshot(snapshot)

        return snapshot

    def _save_snapshot(self, snapshot: ExperimentSnapshot):
        """保存快照到文件"""
        snapshot_file = self.snapshot_dir / f"{snapshot.snapshot_id}.json"
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)

    def load_snapshot(self, snapshot_id: str) -> Optional[ExperimentSnapshot]:
        """加载快照"""
        snapshot_file = self.snapshot_dir / f"{snapshot_id}.json"
        if not snapshot_file.exists():
            return None

        with open(snapshot_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return ExperimentSnapshot(**{
            'snapshot_id': data['snapshot_id'],
            'timestamp': data['timestamp'],
            'research_topic': data['research_topic'],
            'model': data['llm_params']['model'],
            'temperature': data['llm_params']['temperature'],
            'top_p': data['llm_params']['top_p'],
            'seed': data['llm_params']['seed'],
            'python_version': data['environment']['python_version'],
            'working_directory': data['environment']['working_directory'],
            'pmid_list': data['data_provenance']['pmid_list'],
            'hypothesis_count': data['output_summary']['hypothesis_count'],
            'hypothesis_titles': data['output_summary']['hypothesis_titles'],
            'total_tokens_used': data['performance']['total_tokens_used'],
            'execution_time_seconds': data['performance']['execution_time_seconds'],
            'output_hash': data['verification']['output_hash']
        })


# ==============================================================================
# 3. 隐式模态越权监控 (Modality Jailbreak Monitor)
# ==============================================================================

class ModalityBlacklist:
    """
    模态违禁词库 - 硬性物理否决

    一旦检测到越权词汇，无需经过 LLM 思考，直接物理否决
    """

    # 单细胞相关违禁词（严格禁止）
    SINGLE_CELL_BLACKLIST = [
        'Seurat', 'Scanpy', 'scVI', 'scRNA-seq', 'scrna-seq',
        'Cell Ranger', '10x Genomics', '10x Genomics',
        'scATAC-seq', 'scatac-seq', 'spatial transcriptomics',
        'single cell', 'single-cell', '单细胞',
        'UMI', 'Unique Molecular Identifier',
        'mitochondrial gene', '线粒体基因',
        'cell type annotation', '细胞类型注释',
        'pseudobulk', 'pseudo-bulk',
        'Harmony', 'Seurat integration', 'Scanpy integration',
        'Liger', 'scANVI', 'totalVI'
    ]

    # 空间转录组违禁词
    SPATIAL_TRANSCRIPTOMICS_BLACKLIST = [
        'Visium', 'Slide-seq', 'Stereo-seq', 'MERFISH',
        'spatial transcriptomics', '空间转录组',
        'in situ sequencing', '原位测序'
    ]

    # 其他微观模态违禁词
    MICROSCOPY_BLACKLIST = [
        'confocal microscopy', '共聚焦显微镜',
        'two-photon', '双光子',
        'electron microscopy', '电子显微镜',
        'immunofluorescence staining', '免疫荧光染色',
        'flow cytometry', '流式细胞术',
        'FACS', 'fluorescence-activated cell sorting'
    ]

    @classmethod
    def check_violation(cls, text: str) -> Tuple[bool, List[str]]:
        """
        检查是否违反模态约束

        Returns:
            (is_violation, matched_violations)
        """
        text_lower = text.lower()
        matched = []

        # 检查单细胞违禁词
        for term in cls.SINGLE_CELL_BLACKLIST:
            if term.lower() in text_lower:
                matched.append(term)

        # 检查空间转录组违禁词
        for term in cls.SPATIAL_TRANSCRIPTOMICS_BLACKLIST:
            if term.lower() in text_lower:
                matched.append(term)

        # 检查显微镜违禁词
        for term in cls.MICROSCOPY_BLACKLIST:
            if term.lower() in text_lower:
                matched.append(term)

        return len(matched) > 0, matched

    @classmethod
    def physical_reject(cls, hypothesis: Dict) -> Tuple[bool, str]:
        """
        物理否决 - 直接拒绝，不经过 LLM

        Returns:
            (is_rejected, rejection_reason)
        """
        # 检查标题和详情
        title = hypothesis.get('title', '')
        details = hypothesis.get('details', '')

        combined_text = f"{title} {details}"

        is_violation, matched = cls.check_violation(combined_text)

        if is_violation:
            reason = f"[物理否决] 检测到违禁模态词汇: {', '.join(matched[:3])}"
            if len(matched) > 3:
                reason += f" 等 {len(matched)} 个"
            return True, reason

        return False, ""


# ==============================================================================
# 4. 运行流的可观测性遥测 (Agentic Observability & Tracing)
# ==============================================================================

@dataclass
class TraceEvent:
    """追踪事件"""
    timestamp: str
    event_type: str  # 'thought', 'action', 'observation', 'error'
    stage: str  # 阶段名称
    content: str
    latency_ms: float = 0.0
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'stage': self.stage,
            'content': self.content,
            'latency_ms': self.latency_ms,
            'metadata': self.metadata
        }


class ObservabilityTracer:
    """
    可观测性追踪器

    记录每一步 Thought、Action、Observation
    带时间戳和运行耗时
    """

    def __init__(self, output_dir: str = 'logs/traces'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.events: List[TraceEvent] = []
        self.start_time = time.time()
        self.stage_start_time: Dict[str, float] = {}

    def start_stage(self, stage_name: str):
        """开始一个阶段"""
        self.stage_start_time[stage_name] = time.time()
        self.log_event('stage_start', stage_name, f"开始阶段: {stage_name}")

    def end_stage(self, stage_name: str):
        """结束一个阶段"""
        if stage_name in self.stage_start_time:
            latency = (time.time() - self.stage_start_time[stage_name]) * 1000
            self.log_event('stage_end', stage_name, f"结束阶段: {stage_name}", latency_ms=latency)
            del self.stage_start_time[stage_name]

    def log_thought(self, stage: str, thought: str):
        """记录思考"""
        self.log_event('thought', stage, thought)

    def log_action(self, stage: str, action: str):
        """记录动作"""
        self.log_event('action', stage, action)

    def log_observation(self, stage: str, observation: str):
        """记录观察"""
        self.log_event('observation', stage, observation)

    def log_error(self, stage: str, error: str):
        """记录错误"""
        self.log_event('error', stage, error)

    def log_event(
        self,
        event_type: str,
        stage: str,
        content: str,
        latency_ms: float = 0.0,
        metadata: Dict = None
    ):
        """记录事件"""
        event = TraceEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            stage=stage,
            content=content[:500],  # 限制内容长度
            latency_ms=latency_ms,
            metadata=metadata or {}
        )
        self.events.append(event)

    def export_trace(self, filename: str = None) -> str:
        """导出追踪日志"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'trace_{timestamp}.jsonl'

        trace_file = self.output_dir / filename

        with open(trace_file, 'w', encoding='utf-8') as f:
            for event in self.events:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + '\n')

        return str(trace_file)

    def export_summary(self) -> Dict:
        """导出追踪摘要"""
        summary = {
            'total_events': len(self.events),
            'total_duration_ms': (time.time() - self.start_time) * 1000,
            'events_by_type': {},
            'events_by_stage': {},
            'errors': []
        }

        for event in self.events:
            # 按类型统计
            if event.event_type not in summary['events_by_type']:
                summary['events_by_type'][event.event_type] = 0
            summary['events_by_type'][event.event_type] += 1

            # 按阶段统计
            if event.stage not in summary['events_by_stage']:
                summary['events_by_stage'][event.stage] = 0
            summary['events_by_stage'][event.stage] += 1

            # 错误收集
            if event.event_type == 'error':
                summary['errors'].append({
                    'stage': event.stage,
                    'content': event.content,
                    'timestamp': event.timestamp
                })

        return summary


# ==============================================================================
# 终极鲁棒性盾牌（统一入口）
# ==============================================================================

class UltimateRobustnessShield:
    """
    终极鲁棒性盾牌

    统一管理 4 个终极防御机制
    """

    def __init__(self):
        self.data_sanitizer = DataSanitizer()
        self.snapshot_manager = SnapshotManager()
        self.modality_blacklist = ModalityBlacklist()
        self.tracer = ObservabilityTracer()

    def shield_external_data(self, papers: List[Dict]) -> Tuple[List[Dict], Dict]:
        """防御外部数据投毒"""
        return self.data_sanitizer.sanitize_paper_list(papers)

    def create_reproducibility_snapshot(
        self,
        research_topic: str,
        llm_params: Dict,
        papers: List[Dict],
        hypotheses: List[Dict],
        execution_stats: Dict
    ) -> ExperimentSnapshot:
        """创建可复现性快照"""
        return self.snapshot_manager.create_snapshot(
            research_topic, llm_params, papers, hypotheses, execution_stats
        )

    def check_modality_violation(self, hypothesis: Dict) -> Tuple[bool, str]:
        """检查模态越权"""
        return self.modality_blacklist.physical_reject(hypothesis)

    def trace_event(self, event_type: str, stage: str, content: str):
        """记录追踪事件"""
        self.tracer.log_event(event_type, stage, content)

    def export_all(self) -> Dict[str, str]:
        """导出所有日志"""
        return {
            'trace_file': self.tracer.export_trace(),
            'trace_summary': self.tracer.export_summary()
        }


# 全局单例
_ultimate_shield: Optional[UltimateRobustnessShield] = None


def get_ultimate_shield() -> UltimateRobustnessShield:
    """获取终极鲁棒性盾牌单例"""
    global _ultimate_shield
    if _ultimate_shield is None:
        _ultimate_shield = UltimateRobustnessShield()
    return _ultimate_shield


# ==============================================================================
# 便捷函数
# ==============================================================================

def sanitize_papers(papers: List[Dict]) -> List[Dict]:
    """清洗论文数据"""
    shield = get_ultimate_shield()
    sanitized, _ = shield.shield_external_data(papers)
    return sanitized


def check_hypothesis_modality(hypothesis: Dict) -> Tuple[bool, str]:
    """检查假设模态"""
    shield = get_ultimate_shield()
    return shield.check_modality_violation(hypothesis)


def trace_thought(stage: str, thought: str):
    """追踪思考"""
    shield = get_ultimate_shield()
    shield.tracer.log_thought(stage, thought)


def trace_action(stage: str, action: str):
    """追踪动作"""
    shield = get_ultimate_shield()
    shield.tracer.log_action(stage, action)


def trace_observation(stage: str, observation: str):
    """追踪观察"""
    shield = get_ultimate_shield()
    shield.tracer.log_observation(stage, observation)


if __name__ == '__main__':
    print("=" * 70)
    print("Ultimate Robustness Shield V3.3 - Testing")
    print("=" * 70)

    # 测试 1: 数据清洗
    print("\n[Test 1] Data Sanitizer")
    test_papers = [
        {
            'pmid': '1234567',
            'title': '<script>alert("xss")</script> A Study on Alzheimer',
            'abstract': 'This is a very long abstract. ' * 100,
            'journal': 'Nature'
        },
        {
            'pmid': '7654321',
            'title': 'Retracted: False Claims About AD',
            'abstract': 'This paper was retracted due to errors.',
            'journal': 'Science'
        }
    ]

    shield = get_ultimate_shield()
    sanitized, report = shield.shield_external_data(test_papers)

    print(f"  Input: {report['total_input']} papers")
    print(f"  Sanitized: {report['sanitized_count']}")
    print(f"  Retracted (removed): {report['retracted_count']}")
    print(f"  Truncated: {report['truncated_count']}")

    # 测试 2: 模态黑名单
    print("\n[Test 2] Modality Blacklist")
    test_hypothesis = {
        'title': 'Using Seurat for Single Cell Analysis in AD',
        'details': 'We will use scRNA-seq and Cell Ranger...'
    }

    is_rejected, reason = shield.check_modality_violation(test_hypothesis)
    print(f"  Rejected: {is_rejected}")
    print(f"  Reason: {reason}")

    # 测试 3: 追踪
    print("\n[Test 3] Observability Tracer")
    shield.tracer.start_stage('test_stage')
    trace_thought('test_stage', 'Thinking about hypothesis')
    trace_action('test_stage', 'Searching PubMed')
    trace_observation('test_stage', 'Found 10 papers')
    shield.tracer.end_stage('test_stage')

    summary = shield.tracer.export_summary()
    print(f"  Total events: {summary['total_events']}")
    print(f"  Duration: {summary['total_duration_ms']:.1f}ms")

    print("\n" + "=" * 70)
    print("V3.3 Ultimate Robustness Shield Ready!")
    print("=" * 70)
