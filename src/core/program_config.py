# -*- coding: utf-8 -*-
"""
V6.1 配置管理层重构 - Pydantic 强校验 + 动态拉取模式

核心改进：
1. Pydantic BaseModel 强校验防线（Anti-Crash Validation）
2. Lazy Evaluation 消灭 Celery 状态幽灵
3. ValidationError 捕获 → 默认安全配置回退

禁止在模块顶层（Global Scope）实例化配置对象！
"""

import os
import re
import yaml
import logging
import threading
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

# ==================== Pydantic 强校验导入 ====================
try:
    from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    # 回退：定义简化版 BaseModel
    class BaseModel:
        """Pydantic 未安装时的简化回退"""
        def __init__(self, **data):
            for key, value in data.items():
                setattr(self, key, value)

        def model_dump(self) -> Dict:
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

    def Field(default=None, **kwargs):
        return default

    class ValidationError(Exception):
        pass


# ==================== CRITICAL 级别日志配置 ====================
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    logger.addHandler(handler)
logger.setLevel(logging.CRITICAL)


# ==================== Pydantic 配置模型定义 ====================

class DefenseLayerConfig(BaseModel):
    """
    防御层配置模型

    熔断器、意图清洗、硬链接锚定
    """
    # Intent Sanitizer
    intent_sanitizer_enabled: bool = Field(default=True, description="意图清洗网关开关")
    intent_sanitizer_strict_mode: bool = Field(default=True, description="意图清洗严格模式")

    # Global Fuse
    global_fuse_enabled: bool = Field(default=True, description="全局熔断器开关")
    hard_cap: int = Field(
        default=15,
        ge=1,
        le=50,
        description="API调用熔断硬上限 (范围: 1-50)"
    )
    warning_threshold: int = Field(
        default=10,
        ge=1,
        le=40,
        description="熔断预警阈值"
    )

    # Hard-Link Anchor
    hard_link_anchor_enabled: bool = Field(default=True, description="硬链接锚定开关")
    hard_link_anchor_strict_mode: bool = Field(default=True, description="硬链接锚定严格模式")

    # V7.0 分布式熔断器配置
    fuse_backend: str = Field(default="redis", description="熔断器后端: memory/redis")
    fuse_redis_key_prefix: str = Field(default="research_agent_fuse_v7:", description="Redis 键前缀")
    fuse_ttl: int = Field(default=3600, ge=60, le=86400, description="熔断器状态 TTL（秒）")
    fuse_sync_interval: int = Field(default=5, ge=1, le=60, description="同步间隔（秒）")

    if PYDANTIC_AVAILABLE:
        @field_validator('warning_threshold')
        @classmethod
        def validate_warning_threshold(cls, v, info):
            """预警阈值必须小于硬上限"""
            hard_cap = info.data.get('hard_cap', 15)
            if v >= hard_cap:
                raise ValueError(f"warning_threshold ({v}) 必须小于 hard_cap ({hard_cap})")
            return v


class HypothesisGenerationConfig(BaseModel):
    """
    假设生成配置模型

    核心参数：分数阈值、重试次数、突变阈值
    """
    num_hypotheses: int = Field(default=3, ge=1, le=10, description="每轮生成假设数量")
    best_of_n: int = Field(default=3, ge=1, le=10, description="多轨并行原型数")
    min_score_threshold: float = Field(
        default=7.5,
        ge=0.0,
        le=10.0,
        description="假设最低通过分数阈值 (范围: 0.0-10.0)"
    )
    enable_prevalidation: bool = Field(default=True, description="启用预验证")
    radical_pivot_threshold: float = Field(
        default=5.0,
        ge=0.0,
        le=10.0,
        description="激进突变触发阈值"
    )
    max_internal_retries: int = Field(default=2, ge=0, le=5, description="内部重试次数")
    max_audit_iterations: int = Field(default=2, ge=1, le=5, description="审计迭代次数")


class PaperSearchConfig(BaseModel):
    """
    论文检索配置模型

    V7.1 新增：IF & 日期约束强制校验
    PubMed/ArXiv/Semantic Scholar 检索参数
    """
    use_two_stage_funnel: bool = Field(default=True, description="两阶段漏斗检索")
    stage1_max: int = Field(default=500, ge=50, le=1000, description="第一阶段粗筛数量")
    stage2_top_k: int = Field(default=40, ge=10, le=100, description="第二阶段精读数量")
    min_if: float = Field(default=0.0, ge=0.0, le=50.0, description="最低影响因子阈值")
    date_range_start: int = Field(default=2020, ge=1990, le=2030, description="起始年份")
    date_range_end: int = Field(default=2026, ge=2020, le=2030, description="结束年份")
    fetch_full_text: bool = Field(default=True, description="获取全文")
    max_full_text: int = Field(default=10, ge=0, le=50, description="最多获取全文数")
    pubmed_max_results: int = Field(
        default=30,
        ge=10,
        le=100,
        description="PubMed 检索上限 (范围: 10-100)"
    )

    if PYDANTIC_AVAILABLE:
        @model_validator(mode='after')
        def validate_date_range_order(self):
            """V7.1 强校验：结束年份必须 ≥ 起始年份"""
            if self.date_range_end < self.date_range_start:
                raise ValueError(
                    f"date_range_end ({self.date_range_end}) 必须大于等于 "
                    f"date_range_start ({self.date_range_start})"
                )
            return self

        @field_validator('min_if')
        @classmethod
        def validate_if_float(cls, v):
            """V7.1 强校验：IF 必须是有效浮点数"""
            if not isinstance(v, (int, float)):
                raise ValueError(f"min_if 必须为数值类型，当前: {type(v).__name__}")
            if v < 0:
                raise ValueError(f"min_if ({v}) 不能为负数")
            return float(v)


class MolecularDockingConfig(BaseModel):
    """
    分子对接配置模型 (V6.1 新增)

    AutoDock Vina 参数约束
    """
    autodock_energy_threshold: float = Field(
        default=-7.0,
        le=-5.0,
        description="AutoDock Vina 对接能量准入线 (强制负数，上限 -5.0 kcal/mol)"
    )
    autodock_search_mode: str = Field(default="balance", description="搜索模式: fast/balance/detail")
    autodock_exhaustiveness: int = Field(default=8, ge=1, le=32, description="搜索 exhaustiveness")

    if PYDANTIC_AVAILABLE:
        @field_validator('autodock_energy_threshold')
        @classmethod
        def validate_energy_negative(cls, v):
            """对接能量必须为负数（结合能）"""
            if v >= 0:
                raise ValueError(f"autodock_energy_threshold ({v}) 必须为负数（结合能）")
            return v


class AsyncTasksConfig(BaseModel):
    """
    Celery 异步任务配置模型
    """
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis 连接 URL")
    task_soft_time_limit: int = Field(default=300, ge=60, le=1800, description="任务软超时（秒）")
    task_hard_time_limit: int = Field(default=600, ge=120, le=3600, description="任务硬超时（秒）")
    task_max_retries: int = Field(default=3, ge=0, le=10, description="任务最大重试次数")
    webhook_timeout: int = Field(default=30, ge=5, le=120, description="Webhook 超时（秒）")

    if PYDANTIC_AVAILABLE:
        @model_validator(mode='after')
        def validate_time_limits(self):
            """软超时必须小于硬超时"""
            if self.task_soft_time_limit >= self.task_hard_time_limit:
                raise ValueError(
                    f"task_soft_time_limit ({self.task_soft_time_limit}) "
                    f"必须小于 task_hard_time_limit ({self.task_hard_time_limit})"
                )
            return self


class DataSourceRoutingConfig(BaseModel):
    """
    数据源路由配置模型
    """
    domain_mapping: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            'computational_biology': ['pubmed', 'arxiv'],
            'neuroscience': ['pubmed'],
            'ai': ['arxiv', 'semantic_scholar', 'pubmed'],
            'medicine': ['pubmed'],
            'computer_science': ['arxiv', 'semantic_scholar'],
            'physics': ['arxiv', 'semantic_scholar'],
            'psychology': ['semantic_scholar', 'pubmed'],
        },
        description="领域→数据源映射"
    )
    source_limits: Dict[str, int] = Field(
        default_factory=lambda: {
            'pubmed': 30,
            'arxiv': 20,
            'semantic_scholar': 20,
        },
        description="各数据源检索上限"
    )


class AgentOrchestrationConfig(BaseModel):
    """
    Agent 编排配置模型
    """
    enabled_agents: Dict[str, bool] = Field(
        default_factory=lambda: {
            'paper_search': True,
            'hypothesis': True,
            'validation': True,
            'tech_analysis': True,
            'genai_expert': True,
            'comp_bio': True,
            'digital_pathology': True,
            'biostats': True,
            'clinical_md': True,
            'data_hunter': True,
            'data_governance': True,
            'resource_estimator': True,
            'ethics_reviewer': True,
            'coder': True,
            'red_team': True,
            'defense_committee': True,
            'thesis_writer': True,
        },
        description="Agent 启用状态"
    )
    agent_models: Dict[str, str] = Field(
        default_factory=lambda: {
            'hypothesis_agent': 'claude-opus-4-6',
            'validation_agent': 'claude-opus-4-6',
            'red_team_agent': 'claude-haiku-4-5-20251001',
        },
        description="Agent 模型选择"
    )
    lazy_init: bool = Field(default=False, description="延迟初始化")


class RejectionReportConfig(BaseModel):
    """
    否决报告配置模型
    """
    enabled: bool = Field(default=True, description="否决报告开关")
    detail_level: str = Field(default="high", description="详细程度: low/medium/high")
    min_collision_papers: int = Field(default=3, ge=1, le=10, description="最少碰撞文献数")
    min_logical_flaws: int = Field(default=2, ge=1, le=10, description="最少逻辑断裂点数")
    include_alternative_directions: bool = Field(default=True, description="包含替代研究方向建议")


class AutonomousModeConfig(BaseModel):
    """
    自主循环模式配置模型
    """
    enabled: bool = Field(default=False, description="自主模式开关")
    max_iterations: int = Field(default=5, ge=1, le=20, description="最大迭代次数")
    target_score: float = Field(default=8.0, ge=0.0, le=10.0, description="目标综合分数")
    time_budget_minutes: int = Field(default=60, ge=10, le=480, description="总时间预算（分钟）")
    auto_select_papers: bool = Field(default=True, description="自动选择最高分论文")
    auto_approve_hypothesis: bool = Field(default=False, description="假设是否自动通过")
    auto_technical_analysis: bool = Field(default=True, description="自动技术分析")
    on_failure_action: str = Field(default="radical_pivot", description="失败策略: radical_pivot/retry/abort")
    max_pivot_attempts: int = Field(default=2, ge=1, le=5, description="激进突变尝试次数")
    experiment_log: bool = Field(default=True, description="记录每次迭代日志")
    output_dir: str = Field(default="experiments/", description="实验日志目录")


class WorkflowParamsConfig(BaseModel):
    """
    工作流参数配置模型
    """
    max_feedback_loop: int = Field(default=1, ge=0, le=5, description="反馈循环最大次数")
    best_of_n: int = Field(default=3, ge=1, le=10, description="多轨并行原型数")
    radical_pivot_threshold: float = Field(default=5.0, ge=0.0, le=10.0, description="激进突变触发阈值")
    max_audit_iterations: int = Field(default=2, ge=1, le=5, description="审计迭代次数")
    remedial_search_max_results: int = Field(default=5, ge=1, le=20, description="补救搜索最大结果数")


class ResearchGoalsConfig(BaseModel):
    """
    研究目标配置模型
    """
    primary_field: str = Field(default="计算生物学", description="主要研究领域")
    target_journal_level: str = Field(default="Nature级别", description="目标期刊级别")
    research_depth: str = Field(default="博士论文开题深度", description="研究深度")
    min_transformative_impact: float = Field(default=8.0, ge=0.0, le=10.0, description="最小颠覆性分数")
    min_methodological_originality: float = Field(default=7.5, ge=0.0, le=10.0, description="最小原创性分数")
    min_poc_feasibility: float = Field(default=7.0, ge=0.0, le=10.0, description="最小可行性分数")
    min_overall_score: float = Field(default=7.5, ge=0.0, le=10.0, description="最小综合平均分")


class OutputConfig(BaseModel):
    """
    输出配置模型
    """
    report_format: str = Field(default="markdown", description="报告格式")
    include_scores: bool = Field(default=True, description="包含评分")
    include_audit_log: bool = Field(default=True, description="包含审计日志")
    include_tool_calls: bool = Field(default=True, description="包含工具调用日志")
    reports_dir: str = Field(default="reports/", description="报告目录")
    experiments_dir: str = Field(default="experiments/", description="实验目录")


class V61ProgramConfig(BaseModel):
    """
    V6.1 全局配置模型（根模型）

    Pydantic 强校验 + 安全回退机制
    """
    research_goals: ResearchGoalsConfig = Field(default_factory=ResearchGoalsConfig)
    paper_search: PaperSearchConfig = Field(default_factory=PaperSearchConfig)
    hypothesis_generation: HypothesisGenerationConfig = Field(default_factory=HypothesisGenerationConfig)
    molecular_docking: MolecularDockingConfig = Field(default_factory=MolecularDockingConfig)
    defense_layer: DefenseLayerConfig = Field(default_factory=DefenseLayerConfig)
    workflow_params: WorkflowParamsConfig = Field(default_factory=WorkflowParamsConfig)
    async_tasks: AsyncTasksConfig = Field(default_factory=AsyncTasksConfig)
    data_source_routing: DataSourceRoutingConfig = Field(default_factory=DataSourceRoutingConfig)
    agent_orchestration: AgentOrchestrationConfig = Field(default_factory=AgentOrchestrationConfig)
    rejection_report: RejectionReportConfig = Field(default_factory=RejectionReportConfig)
    autonomous_mode: AutonomousModeConfig = Field(default_factory=AutonomousModeConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    # 配置元数据
    config_version: str = Field(default="v6.1", description="配置版本")
    last_loaded_time: Optional[str] = Field(default=None, description="最后加载时间")
    source_path: Optional[str] = Field(default=None, description="配置来源路径")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        if PYDANTIC_AVAILABLE:
            return self.model_dump()
        else:
            return {
                'research_goals': self.research_goals.model_dump() if hasattr(self.research_goals, 'model_dump') else {},
                'paper_search': self.paper_search.model_dump() if hasattr(self.paper_search, 'model_dump') else {},
                'hypothesis_generation': self.hypothesis_generation.model_dump() if hasattr(self.hypothesis_generation, 'model_dump') else {},
                'molecular_docking': self.molecular_docking.model_dump() if hasattr(self.molecular_docking, 'model_dump') else {},
                'defense_layer': self.defense_layer.model_dump() if hasattr(self.defense_layer, 'model_dump') else {},
                'workflow_params': self.workflow_params.model_dump() if hasattr(self.workflow_params, 'model_dump') else {},
                'async_tasks': self.async_tasks.model_dump() if hasattr(self.async_tasks, 'model_dump') else {},
                'data_source_routing': self.data_source_routing.model_dump() if hasattr(self.data_source_routing, 'model_dump') else {},
                'agent_orchestration': self.agent_orchestration.model_dump() if hasattr(self.agent_orchestration, 'model_dump') else {},
                'rejection_report': self.rejection_report.model_dump() if hasattr(self.rejection_report, 'model_dump') else {},
                'autonomous_mode': self.autonomous_mode.model_dump() if hasattr(self.autonomous_mode, 'model_dump') else {},
                'output': self.output.model_dump() if hasattr(self.output, 'model_dump') else {},
                'config_version': self.config_version,
                'last_loaded_time': self.last_loaded_time,
                'source_path': self.source_path,
            }


# ==================== 默认安全配置 ====================

DEFAULT_SAFE_CONFIG = V61ProgramConfig()


# ==================== 配置加载器（Lazy Evaluation） ====================

class ConfigLoader:
    """
    配置加载器 - Lazy Evaluation 模式

    核心原则：
    1. 禁止模块顶层实例化
    2. 每次 get_current_config() 强制触发 I/O 读取最新 YAML
    3. ValidationError 捕获 → 回退到 DEFAULT_SAFE_CONFIG
    """

    _instance: Optional['ConfigLoader'] = None
    _lock = threading.Lock()
    _config_cache: Optional[V61ProgramConfig] = None
    _cache_timestamp: Optional[float] = None
    _cache_ttl: float = 0.0  # 缓存 TTL = 0，强制每次读取

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化"""
        self._program_path = self._resolve_program_path()
        self._yaml_path = self._resolve_yaml_path()

    def _resolve_program_path(self) -> str:
        """解析 program.md 路径"""
        # 优先级：环境变量 → 项目根目录
        env_path = os.getenv('PROGRAM_MD_PATH')
        if env_path and os.path.exists(env_path):
            return env_path

        # 项目根目录
        project_root = Path(__file__).parent.parent.parent
        program_md = project_root / 'program.md'
        if program_md.exists():
            return str(program_md)

        # 回退
        return str(program_md)

    def _resolve_yaml_path(self) -> str:
        """解析 config.yaml 路径"""
        project_root = Path(__file__).parent.parent.parent
        config_yaml = project_root / 'config.yaml'
        if config_yaml.exists():
            return str(config_yaml)
        return str(config_yaml)

    def _extract_yaml_from_md(self, md_path: str) -> Dict[str, Any]:
        """
        从 program.md 提取 YAML 配置块

        支持多个 YAML 块合并
        """
        if not os.path.exists(md_path):
            logger.critical(f"[ConfigLoader] program.md 不存在: {md_path}")
            return {}

        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取所有 YAML 块
            yaml_blocks = re.findall(r'```yaml\s*(.*?)\s*```', content, re.DOTALL)

            merged_config = {}
            for block in yaml_blocks:
                try:
                    yaml_config = yaml.safe_load(block)
                    if yaml_config and isinstance(yaml_config, dict):
                        merged_config = self._deep_merge(merged_config, yaml_config)
                except yaml.YAMLError as e:
                    logger.critical(f"[ConfigLoader] YAML 解析错误: {e}")
                    continue

            return merged_config

        except Exception as e:
            logger.critical(f"[ConfigLoader] program.md 读取失败: {e}")
            return {}

    def _load_yaml_file(self, yaml_path: str) -> Dict[str, Any]:
        """
        直接加载 YAML 文件
        """
        if not os.path.exists(yaml_path):
            return {}

        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.critical(f"[ConfigLoader] YAML 文件读取失败: {e}")
            return {}

    def _deep_merge(self, base: Dict, overlay: Dict) -> Dict:
        """深度合并字典"""
        result = base.copy()
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _flatten_config_for_pydantic(self, raw_config: Dict) -> Dict:
        """
        将原始配置扁平化，适配 Pydantic 模型结构

        处理嵌套结构映射
        """
        flattened = {}

        # defense_layer 映射
        if 'defense_layer' in raw_config:
            dl = raw_config['defense_layer']
            if 'intent_sanitizer' in dl:
                flattened['intent_sanitizer_enabled'] = dl['intent_sanitizer'].get('enabled', True)
                flattened['intent_sanitizer_strict_mode'] = dl['intent_sanitizer'].get('strict_mode', True)
            if 'global_fuse' in dl:
                flattened['global_fuse_enabled'] = dl['global_fuse'].get('enabled', True)
                flattened['hard_cap'] = dl['global_fuse'].get('hard_cap', 15)
                flattened['warning_threshold'] = dl['global_fuse'].get('warning_threshold', 10)
            if 'hard_link_anchor' in dl:
                flattened['hard_link_anchor_enabled'] = dl['hard_link_anchor'].get('enabled', True)
                flattened['hard_link_anchor_strict_mode'] = dl['hard_link_anchor'].get('strict_mode', True)

        # hypothesis_generation 映射
        if 'hypothesis_generation' in raw_config:
            hg = raw_config['hypothesis_generation']
            flattened['hypothesis_generation'] = {
                'num_hypotheses': hg.get('num_hypotheses', 3),
                'best_of_n': hg.get('best_of_n', 3),
                'min_score_threshold': hg.get('min_score_threshold', 7.5),
                'enable_prevalidation': hg.get('enable_prevalidation', True),
                'radical_pivot_threshold': hg.get('radical_pivot_threshold', 5.0),
                'max_internal_retries': hg.get('max_internal_retries', 2),
                'max_audit_iterations': hg.get('max_audit_iterations', 2),
            }

        # paper_search 映射
        if 'paper_search' in raw_config:
            ps = raw_config['paper_search']
            flattened['paper_search'] = {
                'use_two_stage_funnel': ps.get('use_two_stage_funnel', True),
                'stage1_max': ps.get('stage1_max', 500),
                'stage2_top_k': ps.get('stage2_top_k', 40),
                'min_if': ps.get('min_if', 0.0),
                'date_range_start': ps.get('date_range_start', 2020),
                'date_range_end': ps.get('date_range_end', datetime.now().year),
                'fetch_full_text': ps.get('fetch_full_text', True),
                'max_full_text': ps.get('max_full_text', 10),
                'pubmed_max_results': ps.get('pubmed_max_results', 30),
            }

        # workflow_params 映射
        if 'workflow_params' in raw_config:
            wp = raw_config['workflow_params']
            remedial = wp.get('remedial_search', {})
            flattened['workflow_params'] = {
                'max_feedback_loop': wp.get('max_feedback_loop', 1),
                'best_of_n': wp.get('best_of_n', 3),
                'radical_pivot_threshold': wp.get('radical_pivot_threshold', 5.0),
                'max_audit_iterations': wp.get('max_audit_iterations', 2),
                'remedial_search_max_results': remedial.get('max_results', 5),
            }

        # async_tasks 映射
        if 'async_tasks' in raw_config:
            at = raw_config['async_tasks']
            flattened['async_tasks'] = {
                'redis_url': at.get('redis_url', 'redis://localhost:6379/0'),
                'task_soft_time_limit': at.get('task_soft_time_limit', 300),
                'task_hard_time_limit': at.get('task_hard_time_limit', 600),
                'task_max_retries': at.get('task_max_retries', 3),
                'webhook_timeout': at.get('webhook_timeout', 30),
            }

        # data_source_routing 映射
        if 'data_source_routing' in raw_config:
            dsr = raw_config['data_source_routing']
            flattened['data_source_routing'] = {
                'domain_mapping': dsr.get('domain_mapping', {}),
                'source_limits': dsr.get('source_limits', {}),
            }

        # agent_orchestration 映射
        if 'agent_orchestration' in raw_config:
            ao = raw_config['agent_orchestration']
            flattened['agent_orchestration'] = {
                'enabled_agents': ao.get('enabled_agents', {}),
                'agent_models': ao.get('agent_models', {}),
                'lazy_init': ao.get('lazy_init', False),
            }

        # rejection_report 映射
        if 'rejection_report' in raw_config:
            rr = raw_config['rejection_report']
            flattened['rejection_report'] = {
                'enabled': rr.get('enabled', True),
                'detail_level': rr.get('detail_level', 'high'),
                'min_collision_papers': rr.get('min_collision_papers', 3),
                'min_logical_flaws': rr.get('min_logical_flaws', 2),
                'include_alternative_directions': rr.get('include_alternative_directions', True),
            }

        # autonomous_mode 映射
        if 'autonomous_mode' in raw_config:
            am = raw_config['autonomous_mode']
            flattened['autonomous_mode'] = {
                'enabled': am.get('enabled', False),
                'max_iterations': am.get('max_iterations', 5),
                'target_score': am.get('target_score', 8.0),
                'time_budget_minutes': am.get('time_budget_minutes', 60),
                'auto_select_papers': am.get('auto_select_papers', True),
                'auto_approve_hypothesis': am.get('auto_approve_hypothesis', False),
                'auto_technical_analysis': am.get('auto_technical_analysis', True),
                'on_failure_action': am.get('on_failure_action', 'radical_pivot'),
                'max_pivot_attempts': am.get('max_pivot_attempts', 2),
                'experiment_log': am.get('experiment_log', True),
                'output_dir': am.get('output_dir', 'experiments/'),
            }

        # research_goals 映射
        if 'research_goals' in raw_config:
            rg = raw_config['research_goals']
            flattened['research_goals'] = {
                'primary_field': rg.get('primary_field', '计算生物学'),
                'target_journal_level': rg.get('target_journal_level', 'Nature级别'),
                'research_depth': rg.get('research_depth', '博士论文开题深度'),
                'min_transformative_impact': rg.get('min_transformative_impact', 8.0),
                'min_methodological_originality': rg.get('min_methodological_originality', 7.5),
                'min_poc_feasibility': rg.get('min_poc_feasibility', 7.0),
                'min_overall_score': rg.get('min_overall_score', 7.5),
            }

        # output 映射
        if 'output' in raw_config:
            out = raw_config['output']
            flattened['output'] = {
                'report_format': out.get('report_format', 'markdown'),
                'include_scores': out.get('include_scores', True),
                'include_audit_log': out.get('include_audit_log', True),
                'include_tool_calls': out.get('include_tool_calls', True),
                'reports_dir': out.get('reports_dir', 'reports/'),
                'experiments_dir': out.get('experiments_dir', 'experiments/'),
            }

        return flattened

    def load_config(self, force_reload: bool = True) -> V61ProgramConfig:
        """
        加载配置（Lazy Evaluation）

        Args:
            force_reload: 强制重新加载（默认 True）

        Returns:
            V61ProgramConfig: Pydantic 校验后的配置对象
        """
        # 强制每次 I/O 读取（消灭 Celery 状态幽灵）
        if force_reload or self._config_cache is None:
            # Step 1: 从 program.md 提取 YAML
            raw_config = self._extract_yaml_from_md(self._program_path)

            # Step 2: 从 config.yaml 补充
            yaml_config = self._load_yaml_file(self._yaml_path)
            raw_config = self._deep_merge(raw_config, yaml_config)

            # Step 3: 扁平化适配 Pydantic
            flattened = self._flatten_config_for_pydantic(raw_config)

            # Step 4: Pydantic 校验
            try:
                if PYDANTIC_AVAILABLE:
                    config = V61ProgramConfig(**flattened)
                else:
                    # Pydantic 未安装，使用回退
                    config = self._build_fallback_config(flattened)

                config.last_loaded_time = datetime.now().isoformat()
                config.source_path = self._program_path

                logger.info(f"[ConfigLoader] 配置加载成功: {self._program_path}")
                return config

            except ValidationError as e:
                # CRITICAL 级别错误日志
                logger.critical(
                    f"[ConfigLoader] Pydantic ValidationError 触发回退:\n"
                    f"  错误详情: {e}\n"
                    f"  回退策略: 使用 DEFAULT_SAFE_CONFIG"
                )
                return DEFAULT_SAFE_CONFIG

            except Exception as e:
                logger.critical(f"[ConfigLoader] 配置加载异常: {e}")
                return DEFAULT_SAFE_CONFIG

        return self._config_cache

    def _build_fallback_config(self, flattened: Dict) -> V61ProgramConfig:
        """Pydantic 未安装时的回退构建"""
        # 手动构建配置对象
        config = V61ProgramConfig()

        # 防御层
        if 'hard_cap' in flattened:
            config.defense_layer.hard_cap = flattened['hard_cap']
        if 'warning_threshold' in flattened:
            config.defense_layer.warning_threshold = flattened['warning_threshold']
        if 'intent_sanitizer_enabled' in flattened:
            config.defense_layer.intent_sanitizer_enabled = flattened['intent_sanitizer_enabled']
        if 'hard_link_anchor_enabled' in flattened:
            config.defense_layer.hard_link_anchor_enabled = flattened['hard_link_anchor_enabled']

        # 假设生成
        if 'hypothesis_generation' in flattened:
            hg = flattened['hypothesis_generation']
            config.hypothesis_generation.min_score_threshold = hg.get('min_score_threshold', 7.5)
            config.hypothesis_generation.best_of_n = hg.get('best_of_n', 3)
            config.hypothesis_generation.radical_pivot_threshold = hg.get('radical_pivot_threshold', 5.0)

        # 论文检索
        if 'paper_search' in flattened:
            ps = flattened['paper_search']
            config.paper_search.pubmed_max_results = ps.get('pubmed_max_results', 30)
            config.paper_search.min_if = ps.get('min_if', 0.0)

        # 异步任务
        if 'async_tasks' in flattened:
            at = flattened['async_tasks']
            config.async_tasks.redis_url = at.get('redis_url', 'redis://localhost:6379/0')
            config.async_tasks.task_soft_time_limit = at.get('task_soft_time_limit', 300)
            config.async_tasks.task_hard_time_limit = at.get('task_hard_time_limit', 600)

        return config


# ==================== 全局配置获取函数（Lazy Evaluation） ====================

_config_loader: Optional[ConfigLoader] = None
_loader_lock = threading.Lock()


def get_current_config(force_reload: bool = True) -> V61ProgramConfig:
    """
    获取当前配置（Lazy Evaluation + 强制 I/O）

    核心原则：
    1. 每次调用强制触发 I/O 读取最新 YAML
    2. 通过 Pydantic 校验
    3. ValidationError 捕获 → DEFAULT_SAFE_CONFIG 回退

    **Celery Worker 每次执行任务时必须调用此函数！**

    Args:
        force_reload: 强制重新读取磁盘（默认 True）

    Returns:
        V61ProgramConfig: Pydantic 校验后的配置对象
    """
    global _config_loader

    if _config_loader is None:
        with _loader_lock:
            if _config_loader is None:
                _config_loader = ConfigLoader()

    return _config_loader.load_config(force_reload=force_reload)


def reload_program_config() -> V61ProgramConfig:
    """
    热重载配置（显式调用）

    Returns:
        V61ProgramConfig: 最新配置
    """
    return get_current_config(force_reload=True)


# ==================== 配置摘要（调试用） ====================

def get_config_summary() -> Dict[str, Any]:
    """
    获取配置摘要（用于调试和展示）
    """
    config = get_current_config()

    return {
        'pydantic_available': PYDANTIC_AVAILABLE,
        'config_version': config.config_version,
        'last_loaded_time': config.last_loaded_time,
        'source_path': config.source_path,
        'defense_layer': {
            'hard_cap': config.defense_layer.hard_cap,
            'warning_threshold': config.defense_layer.warning_threshold,
            'global_fuse_enabled': config.defense_layer.global_fuse_enabled,
            'intent_sanitizer_enabled': config.defense_layer.intent_sanitizer_enabled,
        },
        'hypothesis_generation': {
            'min_score_threshold': config.hypothesis_generation.min_score_threshold,
            'best_of_n': config.hypothesis_generation.best_of_n,
            'radical_pivot_threshold': config.hypothesis_generation.radical_pivot_threshold,
        },
        'paper_search': {
            'pubmed_max_results': config.paper_search.pubmed_max_results,
            'min_if': config.paper_search.min_if,
        },
        'molecular_docking': {
            'autodock_energy_threshold': config.molecular_docking.autodock_energy_threshold,
        },
        'async_tasks': {
            'redis_url': config.async_tasks.redis_url,
            'soft_time_limit': config.async_tasks.task_soft_time_limit,
            'hard_time_limit': config.async_tasks.task_hard_time_limit,
        },
    }


# ==================== 配置校验状态 ====================

def validate_config_health() -> Dict[str, Any]:
    """
    配置健康检查

    Returns:
        Dict: 包含校验结果和建议
    """
    config = get_current_config()
    issues = []

    # 检查关键参数边界
    if config.defense_layer.hard_cap < 5:
        issues.append({
            'level': 'warning',
            'field': 'defense_layer.hard_cap',
            'value': config.defense_layer.hard_cap,
            'message': 'hard_cap < 5 可能导致过早熔断，建议 >= 10'
        })

    if config.hypothesis_generation.min_score_threshold > 9.0:
        issues.append({
            'level': 'warning',
            'field': 'hypothesis_generation.min_score_threshold',
            'value': config.hypothesis_generation.min_score_threshold,
            'message': 'min_score_threshold > 9.0 过高，可能导致无法生成有效假设'
        })

    if config.molecular_docking.autodock_energy_threshold > -5.0:
        issues.append({
            'level': 'warning',
            'field': 'molecular_docking.autodock_energy_threshold',
            'value': config.molecular_docking.autodock_energy_threshold,
            'message': 'autodock_energy_threshold 应为负数（结合能），建议 <= -7.0'
        })

    return {
        'status': 'healthy' if not issues else 'warning',
        'pydantic_validation': PYDANTIC_AVAILABLE,
        'config_loaded': config.last_loaded_time is not None,
        'issues': issues,
        'summary': get_config_summary(),
    }


# ==================== 兼容旧接口（过渡期） ====================

class ProgramConfig:
    """
    兼容旧版接口的适配器

    V6.1 重构后，推荐直接使用 get_current_config()
    """

    def __init__(self, program_path: str = None):
        """
        兼容旧版构造函数

        Args:
            program_path: 配置文件路径（可选）
        """
        # 强制使用 get_current_config()
        self._v61_config = get_current_config()
        self.program_path = self._v61_config.source_path or program_path

    def get(self, key: str, default: Any = None) -> Any:
        """
        兼容旧版 get() 方法（点分隔路径）
        """
        config = get_current_config()
        keys = key.split('.')
        value = config.to_dict()

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_global_fuse_hard_cap(self) -> int:
        """获取熔断器硬上限"""
        return get_current_config().defense_layer.hard_cap

    def get_min_score_threshold(self) -> float:
        """获取假设最低分数阈值"""
        return get_current_config().hypothesis_generation.min_score_threshold

    def get_redis_url(self) -> str:
        """获取 Redis URL"""
        return get_current_config().async_tasks.redis_url

    def get_task_soft_time_limit(self) -> int:
        """获取任务软超时"""
        return get_current_config().async_tasks.task_soft_time_limit

    def get_task_hard_time_limit(self) -> int:
        """获取任务硬超时"""
        return get_current_config().async_tasks.task_hard_time_limit

    def get_source_max_results(self, source: str) -> int:
        """获取指定数据源的最大检索结果数"""
        config = get_current_config()
        limits = config.data_source_routing.source_limits
        return limits.get(source, 30)

    def get_min_if(self) -> float:
        """获取最低影响因子阈值"""
        return get_current_config().paper_search.min_if

    def get_date_range(self) -> tuple:
        """获取日期范围"""
        config = get_current_config()
        return (config.paper_search.date_range_start, config.paper_search.date_range_end)

    def get_intent_sanitizer_strict_mode(self) -> bool:
        """获取意图清洗严格模式"""
        return get_current_config().defense_layer.intent_sanitizer_strict_mode

    def is_intent_sanitizer_enabled(self) -> bool:
        """检查意图清洗是否启用"""
        return get_current_config().defense_layer.intent_sanitizer_enabled

    def is_global_fuse_enabled(self) -> bool:
        """检查全局熔断器是否启用"""
        return get_current_config().defense_layer.global_fuse_enabled

    def get_hard_link_anchor_strict_mode(self) -> bool:
        """获取硬链接锚定严格模式"""
        return get_current_config().defense_layer.hard_link_anchor_strict_mode

    def is_hard_link_anchor_enabled(self) -> bool:
        """检查硬链接锚定是否启用"""
        return get_current_config().defense_layer.hard_link_anchor_enabled

    def get_best_of_n(self) -> int:
        """获取多轨并行原型数"""
        return get_current_config().hypothesis_generation.best_of_n

    def get_radical_pivot_threshold(self) -> float:
        """获取激进突变触发阈值"""
        return get_current_config().hypothesis_generation.radical_pivot_threshold

    def get_max_feedback_loop(self) -> int:
        """获取反馈循环最大次数"""
        return get_current_config().workflow_params.max_feedback_loop

    def get_remedial_search_max_results(self) -> int:
        """获取补救搜索最大结果数"""
        return get_current_config().workflow_params.remedial_search_max_results

    def reload(self) -> None:
        """热重载配置"""
        self._v61_config = reload_program_config()


# ==================== 测试用例 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V6.1 配置管理层测试 - Pydantic 强校验 + Lazy Evaluation")
    print("=" * 70)

    # 测试 1: Pydantic 可用性
    print(f"\n[测试 1] Pydantic 可用性: {PYDANTIC_AVAILABLE}")

    # 测试 2: 配置加载
    config = get_current_config()
    print(f"\n[测试 2] 配置加载:")
    print(f"  配置版本: {config.config_version}")
    print(f"  加载时间: {config.last_loaded_time}")
    print(f"  来源路径: {config.source_path}")

    # 测试 3: 边界约束验证
    print(f"\n[测试 3] 边界约束验证:")
    print(f"  hard_cap: {config.defense_layer.hard_cap} (范围: 1-50)")
    print(f"  min_score_threshold: {config.hypothesis_generation.min_score_threshold} (范围: 0.0-10.0)")
    print(f"  pubmed_max_results: {config.paper_search.pubmed_max_results} (范围: 10-100)")
    print(f"  autodock_energy_threshold: {config.molecular_docking.autodock_energy_threshold} (强制负数)")

    # 测试 4: ValidationError 模拟
    print(f"\n[测试 4] ValidationError 模拟:")
    try:
        if PYDANTIC_AVAILABLE:
            # 尝试创建非法配置
            bad_config = DefenseLayerConfig(
                hard_cap=100,  # 超出范围 1-50
                warning_threshold=150,  # 超出范围且大于 hard_cap
            )
            print(f"  [失败] 非法配置未被拦截")
        else:
            print(f"  [跳过] Pydantic 未安装，无法测试 ValidationError")
    except ValidationError as e:
        print(f"  [成功] ValidationError 触发:")
        print(f"  {e}")

    # 测试 5: 配置摘要
    print(f"\n[测试 5] 配置摘要:")
    summary = get_config_summary()
    for key, value in summary.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for sub_key, sub_value in value.items():
                print(f"    {sub_key}: {sub_value}")
        else:
            print(f"  {key}: {value}")

    # 测试 6: 配置健康检查
    print(f"\n[测试 6] 配置健康检查:")
    health = validate_config_health()
    print(f"  状态: {health['status']}")
    print(f"  Pydantic 校验: {health['pydantic_validation']}")
    if health['issues']:
        print(f"  问题:")
        for issue in health['issues']:
            print(f"    - [{issue['level']}] {issue['field']}: {issue['message']}")
    else:
        print(f"  问题: 无")

    print("\n" + "=" * 70)
    print("V6.1 配置管理层测试完成")
    print("=" * 70)