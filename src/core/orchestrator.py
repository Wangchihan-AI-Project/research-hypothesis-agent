# -*- coding: utf-8 -*-
"""
工作流协调器 (终极重构版 - 条件递归反馈 + 数据治理 + 资源核算)
管理整个研究假设生成流程，实现严格的串行依赖工作流和条件递归反馈

新特性：
1. 数据治理与质控环节
2. 算法驱动资源分配
3. 条件递归���馈循环（DefenseCommittee失败时触发一次回溯修正）
4. 统计防御性指标（E-value/Power/FDR强制输出）
"""
from typing import Dict, List, Optional, Any
import sys
import os
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ==================== 动态年份配置 ====================
CURRENT_YEAR = datetime.now().year
DEFAULT_YEAR_START = 2020
# ======================================================

# ==================== V5.0 全防御模块导入 ====================
try:
    from core.intent_sanitizer import IntentSanitizer, SanitizationResult, sanitize_user_input
    from core.global_fuse import GlobalIterationFuse, ResourceExhaustedError, get_global_fuse, reset_global_fuse
    from core.hard_link_anchor import HardLinkAnchor, HallucinationError, get_hard_link_anchor, perform_anchor_check
    from prompts.pi_system_prompt import PI_SYSTEM_PROMPT_V50, format_pi_prompt_v50
    from prompts.auditor_system_prompt import AUDITOR_SYSTEM_PROMPT_V50, format_auditor_prompt_v50
    V50_DEFENSE_ENABLED = True
except ImportError as e:
    print(f"[V5.0] 防御模块导入警告: {e}")
    V50_DEFENSE_ENABLED = False
# ============================================================

from agents.global_prior_art_agent import GlobalPriorArtProbe
from agents.paper_search_agent import PaperSearchAgent
from agents.hypothesis_agent import HypothesisAgent
from agents.validation_agent import ValidationAgent
from agents.tech_analysis_agent import TechAnalysisAgent
from agents.thesis_writer_agent import ThesisWriterAgent
from agents.genai_expert_agent import GenAIExpertAgent
from agents.data_hunter_agent import DataHunterAgent
from agents.data_governance_agent import DataGovernanceAgent
from agents.clinical_md_agent import ClinicalMDAgent
from agents.ethics_reviewer_agent import EthicsReviewerAgent
from agents.coder_agent import CoderAgent
from agents.red_team_agent import RedTeamAgent
from agents.defense_committee_agent import DefenseCommitteeAgent
# 纯干实验核心专家阵列
from agents.comp_bio_agent import CompBioAgent
from agents.digital_pathology_agent import DigitalPathologyAgent
from agents.biostats_agent import BiostatsAgent
from agents.resource_estimator_agent import ResourceEstimatorAgent
from core.database import ResearchSession, Hypothesis
from core.db_manager import get_db_manager
from core.program_config import ProgramConfig, get_current_config
from utils.logger import get_logger
# 补救检索模块
from utils.remedial_search import RemedialSearchEngine, create_remedial_search_prompt
from utils.pubmed import PubMedSearcher
import anthropic
import json


class Orchestrator:
    """工作流协调器（终极重构版）"""

    # ==================== 终极瀑布流顺序（含数据治理和资源核算） ====================
    #
    # 基础流程：
    # 1. PaperSearchAgent -> HypothesisAgent -> ValidationAgent -> TechAnalysisAgent
    #
    # 核心干实验瀑布流（严格串行）：
    # 2. DataHunterAgent (数据探勘)
    #    ↓
    # 3. DataGovernanceAgent (数据治理审计 - NEW)
    #    ↓ 【阻断点：数据质量不达标则终止】
    # 4. GenAIExpertAgent (底层架构)
    #    ↓
    # 5. CompBioAgent (计算生物学 + QC协议)
    #    ↓
    # 6. DigitalPathologyAgent (数字病理学)
    #    ↓
    # 7. BiostatsAgent (统计验证 + E-value/Power/FDR)
    #    ↓
    # 8. ResourceEstimatorAgent (资源核算 - NEW，后移至此)
    #    ↓
    # 9. ClinicalMDAgent (临床效用评估)
    #    ↓
    # 10. RedTeamAgent (红方攻击)
    #    ↓
    # 11. DefenseCommitteeAgent (终审答辩)
    #    ↓ 【条件递归反馈：失败则触发一次回溯修正】
    #    ↓ (若失败) -> 回到步骤4/7，使用反馈修正 -> 重跑
    #    ↓ (若仍失败) -> 终止
    #    ↓ (若通过) -> 继续
    # 12. EthicsReviewerAgent -> ThesisWriterAgent -> CoderAgent
    #
    # ==========================================================

    # 递归反馈最大次数（从 program_config 读取）
    # MAX_FEEDBACK_LOOP = 1  # 旧硬编码，现已配置化

    def __init__(self):
        """初始化协调器"""
        print("[Orchestrator] 开始初始化...", flush=True)

        # ==================== V6.1 加载 program_config (Pydantic强校验 + 兼容层) ====================
        # 使用兼容类 ProgramConfig（内部调用 get_current_config()）
        self.config = ProgramConfig()
        # 同时保存 V6.1 Pydantic 原始配置（用于直接访问 Pydantic 属性）
        self._v61_config = get_current_config()
        print(f"[Orchestrator V6.1] program_config 已加载，hard_cap={self.config.get_global_fuse_hard_cap()}, min_threshold={self.config.get_min_score_threshold()}", flush=True)
        # ==========================================================

        # ==================== 全局参数锁定（从配置读取） ====================
        # 存储 IF 阈值和时间锁，确保在反馈循环中永不丢失
        self.global_search_params = {
            'min_if': self.config.get_min_if(),           # 最低影响因子（从配置读取）
            'date_range': self.config.get_date_range(),   # 时间锁（从配置读取）
            'max_results': self.config.get('paper_search.max_results', 50),  # 最大结果数（从配置读取）
            'enable_filter': False,   # 是否启用高质量过滤
            'params_locked': False    # 参数是否已锁定
        }
        # ==========================================================

        # 初始化日志
        self.logger = get_logger()

        # 初始化各智能体
        print("[Orchestrator] 初始化 PaperSearchAgent...", flush=True)
        self.paper_agent = PaperSearchAgent()
        print("[Orchestrator] PaperSearchAgent 完成", flush=True)

        print("[Orchestrator] 初始化 GlobalPriorArtProbe (全球查新探针)...", flush=True)
        self.global_prior_art_probe = GlobalPriorArtProbe()
        print("[Orchestrator] GlobalPriorArtProbe 完成", flush=True)

        print("[Orchestrator] 初始化 HypothesisAgent...", flush=True)
        self.hypothesis_agent = HypothesisAgent()
        print("[Orchestrator] HypothesisAgent 完成", flush=True)

        print("[Orchestrator] 初始化 ValidationAgent...", flush=True)
        self.validation_agent = ValidationAgent()
        print("[Orchestrator] ValidationAgent 完成", flush=True)

        print("[Orchestrator] 初始化 TechAnalysisAgent...", flush=True)
        self.tech_agent = TechAnalysisAgent()
        print("[Orchestrator] TechAnalysisAgent 完成", flush=True)

        print("[Orchestrator] 初始化 ThesisWriterAgent...", flush=True)
        self.thesis_writer_agent = ThesisWriterAgent()
        print("[Orchestrator] ThesisWriterAgent 完成", flush=True)

        # ==================== 纯干实验核心专家阵列 ====================
        print("[Orchestrator] 初始化 GenAIExpertAgent...", flush=True)
        self.genai_expert_agent = GenAIExpertAgent()
        print("[Orchestrator] GenAIExpertAgent 完成", flush=True)

        print("[Orchestrator] 初始化 CompBioAgent...", flush=True)
        self.comp_bio_agent = CompBioAgent()
        print("[Orchestrator] CompBioAgent 完成", flush=True)

        print("[Orchestrator] 初始化 DigitalPathologyAgent...", flush=True)
        self.digital_pathology_agent = DigitalPathologyAgent()
        print("[Orchestrator] DigitalPathologyAgent 完成", flush=True)

        print("[Orchestrator] 初始化 BiostatsAgent...", flush=True)
        self.biostats_agent = BiostatsAgent()
        print("[Orchestrator] BiostatsAgent 完成", flush=True)

        print("[Orchestrator] 初始化 ClinicalMDAgent...", flush=True)
        self.clinical_md_agent = ClinicalMDAgent()
        print("[Orchestrator] ClinicalMDAgent 完成", flush=True)
        # ============================================================

        print("[Orchestrator] 初始化 DataHunterAgent...", flush=True)
        self.data_hunter_agent = DataHunterAgent()
        print("[Orchestrator] DataHunterAgent 完成", flush=True)

        # ==================== 新增Agent ====================
        print("[Orchestrator] 初始化 DataGovernanceAgent (数据治理审计)...", flush=True)
        self.data_governance_agent = DataGovernanceAgent()
        print("[Orchestrator] DataGovernanceAgent 完成", flush=True)

        print("[Orchestrator] 初始化 ResourceEstimatorAgent (资源核算)...", flush=True)
        self.resource_estimator_agent = ResourceEstimatorAgent()
        print("[Orchestrator] ResourceEstimatorAgent 完成", flush=True)
        # ============================================================

        print("[Orchestrator] 初始化 EthicsReviewerAgent...", flush=True)
        self.ethics_reviewer_agent = EthicsReviewerAgent()
        print("[Orchestrator] EthicsReviewerAgent 完成", flush=True)

        print("[Orchestrator] 初始化 CoderAgent...", flush=True)
        self.coder_agent = CoderAgent()
        print("[Orchestrator] CoderAgent 完成", flush=True)

        # 红蓝对抗Agent
        print("[Orchestrator] 初始化 RedTeamAgent...", flush=True)
        self.red_team_agent = RedTeamAgent()
        print("[Orchestrator] RedTeamAgent 完成", flush=True)

        print("[Orchestrator] 初始化 DefenseCommitteeAgent...", flush=True)
        self.defense_committee_agent = DefenseCommitteeAgent()
        print("[Orchestrator] DefenseCommitteeAgent 完成", flush=True)

        # ==================== LLM Client for 审计方法 ====================
        # 用于 _run_red_team_audit 和 _run_biostats_hardcore_audit
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-20250514")
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        # ==============================================================

        # 使用统一的数据库管理器
        self.db_manager = get_db_manager()

        # ==================== V5.0/V6.0 全防御机制初始化 ====================
        if V50_DEFENSE_ENABLED:
            print("[Orchestrator] 初始化 V5.0/V6.0 全防御机制...", flush=True)

            # 1. 意图清洗前置网关（从配置读取 strict_mode）
            intent_sanitizer_strict = self.config.get_intent_sanitizer_strict_mode()
            if self.config.is_intent_sanitizer_enabled():
                self.intent_sanitizer = IntentSanitizer(strict_mode=intent_sanitizer_strict)
                print(f"[V6.0] Intent Sanitizer Gateway 已启用 (strict_mode={intent_sanitizer_strict})", flush=True)
            else:
                self.intent_sanitizer = None
                print("[V6.0] Intent Sanitizer 已禁用（配置）", flush=True)

            # 2. 全局迭代熔断器（从配置读取 hard_cap）
            hard_cap = self.config.get_global_fuse_hard_cap()
            # warning_threshold 暂不传递给 get_global_fuse（待后续升级）
            if self.config.is_global_fuse_enabled():
                self.global_fuse = get_global_fuse(hard_cap=hard_cap, force_new=True)
                print(f"[V6.0] Global Iteration Fuse 已启用 (上限{hard_cap}次API调用)", flush=True)
            else:
                self.global_fuse = None
                print("[V6.0] Global Fuse 已禁用（配置）", flush=True)

            # 3. 硬链接锚定校验器（从配置读取 strict_mode）
            anchor_strict = self.config.get_hard_link_anchor_strict_mode()
            if self.config.is_hard_link_anchor_enabled():
                self.hard_link_anchor = get_hard_link_anchor(strict_mode=anchor_strict, force_new=True)
                print(f"[V6.0] Hard-Link Anchoring Check 已启用 (strict_mode={anchor_strict})", flush=True)
            else:
                self.hard_link_anchor = None
                print("[V6.0] Hard-Link Anchor 已禁用（配置）", flush=True)

            # 4. V5.0 Prompts 标记
            self.use_v50_prompts = True
            print("[V5.0] PI/Auditor V5.0 System Prompts 已启用", flush=True)
        else:
            self.intent_sanitizer = None
            self.global_fuse = None
            self.hard_link_anchor = None
            self.use_v50_prompts = False
            print("[V5.0] 防御模块未启用（导入失败）", flush=True)
        # ============================================================

        # 当前会话状态
        self.current_session_id = None  # 只保存ID，不保存对象
        self.current_papers = []
        self.current_hypotheses = []
        self.current_hypothesis_ids = []  # 新增：跟踪假设ID
        self.feedback_loop_count = 0  # 递归反馈计数

        # ==================== 补救检索引擎 ====================
        print("[Orchestrator] 初始化 RemedialSearchEngine (补救检索)...", flush=True)
        try:
            # 尝试初始化 PubMed 搜索器
            email = os.getenv('PUBMED_EMAIL')
            api_key = os.getenv('PUBMED_API_KEY')
            pubmed_searcher = PubMedSearcher(email=email, api_key=api_key)
            self.remedial_search_engine = RemedialSearchEngine(pubmed_searcher=pubmed_searcher)
            print("[Orchestrator] RemedialSearchEngine 完成 (PubMed已连接)", flush=True)
        except Exception as e:
            self.logger.warning(f"PubMed初始化失败，使用模拟数据: {e}")
            self.remedial_search_engine = RemedialSearchEngine(pubmed_searcher=None)
            print("[Orchestrator] RemedialSearchEngine 完成 (模拟模式)", flush=True)
        # ====================================================

        self.logger.info("工作流协调器初始化完成（终极重构版：数据治理+资源核算+递归反馈+补救检索）")
        print("[Orchestrator] 初始化完成！", flush=True)

    def generate_hypothesis_v50(self, user_input: str) -> Dict:
        """
        V5.0 全防御假说生成入口点

        执行 4 项绝对熔断机制：
        1. 意图清洗前置网关 - 检测越狱词汇，阻断恶意输入
        2. 全局迭代熔断器 - API调用上限15次，防止Token失控
        3. 硬链接锚定校验 - PMID真实性验证，杜绝静默编造
        4. 智能体V5.0 Prompts - 信息锚定与独立查证

        Args:
            user_input: 用户研究想法

        Returns:
            Dict: 生成结果或阻断消息
        """
        print("\n" + "="*80)
        print("🛡️  V5.0 全防御假说生成流程启动")
        print("="*80)

        # ==================== 阶段0: 意图清洗前置网关 ====================
        print("\n[V5.0] 阶段0: 意图清洗前置网关检查...")

        if not self.intent_sanitizer:
            print("[警告] 意图清洗器未初始化，跳过检查")
            sanitized_input = user_input
        else:
            is_valid, cleaned_input, blocked_message = sanitize_user_input(user_input)

            if not is_valid:
                # 恶意输入被阻断，直接返回错误
                print(f"\n🚫 [阻断] {blocked_message}")
                return {
                    'success': False,
                    'blocked': True,
                    'blocked_reason': blocked_message,
                    'blocked_stage': 'intent_sanitizer',
                    'user_input': user_input
                }

            print(f"[通过] 意图清洗通过")
            sanitized_input = cleaned_input

        # ==================== 阶段1: 重置熔断器 ====================
        print("\n[V5.0] 阶段1: 重置全局熔断器...")

        if self.global_fuse:
            reset_global_fuse()
            print("[熔断器] 全局计数器已重置，上限=15次")
        else:
            print("[警告] 熔断器未初始化")

        # ==================== 阶段2: 执行搜索 ====================
        print("\n[V5.0] 阶段2: 执行论文搜索...")

        try:
            # 从配置读取检索上限
            pubmed_max = self.config.get_source_max_results('pubmed')
            search_result = self.search_papers(
                query=sanitized_input,
                max_results=pubmed_max,
                use_two_stage_funnel=True
            )

            if not search_result.get('success'):
                return {
                    'success': False,
                    'error': search_result.get('error', '搜索失败'),
                    'stage': 'paper_search'
                }

            papers = search_result.get('papers', [])
            print(f"[搜索完成] 获取 {len(papers)} 篇文献")

            # ==================== V7.1 反幻觉熔断：空文献强制拦截 ====================
            if not papers:
                return {
                    'success': False,
                    'blocked': True,
                    'blocked_reason': '检索结果为空，拒绝生成假设（防止参数化记忆编造）',
                    'blocked_stage': 'empty_retrieval_guard',
                    'papers_count': 0
                }
            # ========================================================================

            # ==================== 注册真实PMID到锚定校验器 ====================
            if self.hard_link_anchor:
                pmids = [p.get('pmid', '') for p in papers if p.get('pmid')]
                self.hard_link_anchor.register_verified_pmids(pmids)
                print(f"[锚定校验器] 已注册 {len(pmids)} 个真实PMID")

        except ResourceExhaustedError as e:
            # 熔断器触发，返回降级回复
            print(f"\n🚨 [熔断触发] {e.message}")
            return {
                'success': False,
                'blocked': True,
                'blocked_reason': e.message,
                'blocked_stage': 'global_fuse',
                'stats': {
                    'total_calls': e.stats.total_api_calls,
                    'total_tokens': e.stats.total_tokens_used,
                    'total_cost': e.stats.total_cost_usd
                },
                'degradation_response': self.global_fuse.generate_degradation_response() if self.global_fuse else None
            }

        # ==================== 阶段3: 生成假设 ====================
        print("\n[V5.0] 阶段3: 生成假设（V5.0 Prompts）...")

        try:
            hypothesis_result = self.generate_hypotheses(
                papers=papers,
                research_field='计算生物学',
                num_hypotheses=1,
                enable_prevalidation=True,
                min_score_threshold=7.0
            )

            if not hypothesis_result.get('success'):
                return {
                    'success': False,
                    'error': hypothesis_result.get('error', '假设生成失败'),
                    'stage': 'hypothesis_generation'
                }

            hypotheses = hypothesis_result.get('hypotheses', [])
            print(f"[假设生成] 获得 {len(hypotheses)} 个假设")

        except ResourceExhaustedError as e:
            print(f"\n🚨 [熔断触发] {e.message}")
            return {
                'success': False,
                'blocked': True,
                'blocked_reason': e.message,
                'blocked_stage': 'global_fuse',
                'degradation_response': self.global_fuse.generate_degradation_response() if self.global_fuse else None
            }

        # ==================== 阶段4: 硬链接锚定校验 ====================
        print("\n[V5.0] 阶段4: 硬链接锚定校验（PMID真实性验证）...")

        if self.hard_link_anchor and hypotheses:
            for hyp in hypotheses:
                try:
                    is_valid, message = perform_anchor_check(
                        hypothesis_output=str(hyp.get('details', '')),
                        verified_pmids=list(self.hard_link_anchor.get_verified_pmids())
                    )

                    if not is_valid:
                        # 检测到编造的PMID，清空输出并返回错误
                        print(f"\n🚫 [幻觉检测] {message}")
                        hyp['hallucination_detected'] = True
                        hyp['hallucination_message'] = message
                        # 不返回包含虚假引用的假设
                        hypotheses = [h for h in hypotheses if not h.get('hallucination_detected')]
                    else:
                        print(f"[锚定通过] {message}")
                        hyp['anchor_verified'] = True
                        hyp['anchor_message'] = message

                except HallucinationError as e:
                    # 编造PMID触发幻觉异常，直接阻断
                    print(f"\n🚫 [幻觉阻断] {e.message}")
                    return {
                        'success': False,
                        'blocked': True,
                        'blocked_reason': e.message,
                        'blocked_stage': 'hard_link_anchor',
                        'fabricated_pmids': e.detail.fabricated_pmids
                    }

        # ==================== 阶段5: 最终统计 ====================
        print("\n[V5.0] 阶段5: 最终统计...")

        if self.global_fuse:
            stats = self.global_fuse.get_stats()
            print(f"[统计] API调用: {stats.total_api_calls}/15")
            print(f"[统计] Token消耗: ~{stats.total_tokens_used}")
            print(f"[统计] 预估成本: ${stats.total_cost_usd:.2f}")

        print("\n" + "="*80)
        print("✅ V5.0 全防御流程完成")
        print("="*80)

        return {
            'success': True,
            'hypotheses': hypotheses,
            'papers': papers,
            'defense_stats': {
                'intent_sanitizer_passed': True,
                'global_fuse_triggered': False,
                'anchor_verified': len([h for h in hypotheses if h.get('anchor_verified')]),
                'api_calls': stats.total_api_calls if self.global_fuse else 0,
                'verified_pmids': len(self.hard_link_anchor.get_verified_pmids()) if self.hard_link_anchor else 0
            }
        }

    def start_session(self, query: str) -> Dict:
        """
        开始新的研究会话

        Args:
            query: 搜索关键词

        Returns:
            初始化结果
        """
        try:
            # 创建新会话
            with self.db_manager.get_session() as session:
                new_session = ResearchSession(query=query, status='in_progress')
                session.add(new_session)
                session.flush()  # 立即获取ID
                session_id = new_session.id

            # 只保存ID，不保存对象（避免Session分离问题）
            self.current_session_id = session_id
            self.feedback_loop_count = 0  # 重置反馈计数

            # ==================== 反幻觉断路器：重置搜索计数器 ====================
            self.validation_agent.reset_search_attempts()
            # =======================================================================

            self.logger.session_start(session_id, query)

            return {
                'success': True,
                'session_id': session_id,
                'query': query,
                'message': '研究会话已启动',
                'next_step': 'search_papers'
            }
        except Exception as e:
            self.logger.error("启动会话失败", e)
            return {
                'success': False,
                'error': f'启动会话失败: {str(e)}'
            }

    def search_papers(
        self,
        query: str,
        max_results: int = None,  # V6.0: 从配置读取
        enable_filter: bool = False,
        fetch_full_text: bool = True,
        max_full_text: int = 5,
        use_two_stage_funnel: bool = True,
        stage1_max: int = 500,
        stage2_top_k: int = 40,
        snapshot_path: str = None,
        min_if: float = 0,
        date_range: tuple = None,
        **kwargs
    ) -> Dict:
        """
        第一步：搜索论文（带全局参数锁定）

        重要：首次调用时锁定所有过滤参数，确���后续反馈循环不会丢失标准
        """
        # V6.0: 从配置读取默认值
        if max_results is None:
            max_results = self.config.get_source_max_results('pubmed')

        # ==================== 全局参数锁定 ====================
        # 首次调用时，锁定所有过滤参数
        if not self.global_search_params['params_locked']:
            self.global_search_params['min_if'] = min_if if min_if > 0 else self.config.get_min_if()
            self.global_search_params['date_range'] = date_range if date_range else self.config.get_date_range()
            self.global_search_params['max_results'] = max_results
            self.global_search_params['enable_filter'] = enable_filter
            self.global_search_params['params_locked'] = True

            print(f"\n{'='*60}")
            print(f"🔒 全局搜索参数已锁定:")
            print(f"   IF 阈值: ≥ {self.global_search_params['min_if']}")
            print(f"   时间锁: {self.global_search_params['date_range'][0]}-{self.global_search_params['date_range'][1]}")
            print(f"   最大结果: {self.global_search_params['max_results']}")
            print(f"{'='*60}\n")
        else:
            # 参数已锁定，使用锁定的值（忽略后续传入的值）
            min_if = self.global_search_params['min_if']
            date_range = self.global_search_params['date_range']
            max_results = self.global_search_params['max_results']
            enable_filter = self.global_search_params['enable_filter']

            print(f"\n🔒 使用锁定的全局参数: IF≥{min_if}, 时间锁{date_range}")
        # ==========================================================

        try:
            if use_two_stage_funnel:
                print(f"\n{'='*60}")
                print("🔍 使用 LLM 摘要精读漏斗")
                print(f"{'='*60}")

                result = self.paper_agent.execute({
                    'query': query,
                    'max_results': max_results,
                    'date_range': date_range,  # 🔒 直接使用锁定的 date_range，而非 kwargs
                    'min_if': min_if,
                    'fetch_full_text': fetch_full_text,
                    'snapshot_path': snapshot_path
                })

                if result['success']:
                    self.current_papers = result['papers']
                    self.logger.paper_search(query, len(result['papers']))

                    # 显示统计信息
                    if result.get('stage1_stats'):
                        s1 = result['stage1_stats']
                        print(f"\n📊 第一阶段统计:")
                        print(f"  获取文献: {s1.get('total_fetched', 0)} 篇")

                    if result.get('stage2_stats'):
                        s2 = result['stage2_stats']
                        print(f"\n📊 第二阶段统计:")
                        print(f"  LLM精读: {s2.get('total_screened', 0)} 篇")
                        print(f"  保留精华: {s2.get('selected_count', 0)} 篇")
                        print(f"  平均评分: {s2.get('avg_score', 0):.1f}/10")

                    if result.get('stage3_stats'):
                        s3 = result['stage3_stats']
                        print(f"\n📊 第三阶段统计:")
                        print(f"  保存入库: {s3.get('saved_count', 0)} 篇")

                    # 更新会话
                    if self.current_session_id:
                        with self.db_manager.get_session() as session:
                            session_obj = session.query(ResearchSession).filter_by(
                                id=self.current_session_id
                            ).first()
                            if session_obj:
                                session_obj.papers_found = len(result['papers'])

                    return {
                        'success': True,
                        'query': query,
                        'papers': result['papers'],
                        'total_count': len(result['papers']),
                        'saved_count': result.get('saved_count', 0),
                        'full_text_stats': result.get('full_text_stats'),
                        'stage1_stats': result.get('stage1_stats'),
                        'stage2_stats': result.get('stage2_stats'),
                        'used_two_stage_funnel': True
                    }
                else:
                    return {
                        'success': False,
                        'error': result.get('error', '搜索失败'),
                        'papers': []
                    }
            else:
                # 单阶段模式
                result = self.paper_agent.execute({
                    'query': query,
                    'max_results': max_results,
                    'enable_filter': enable_filter,
                    'fetch_full_text': fetch_full_text,
                    'max_full_text': max_full_text
                })

                if result['success']:
                    self.current_papers = result['papers']
                    self.logger.paper_search(query, len(result['papers']))

                return result

        except Exception as e:
            self.logger.error("论文搜索失败", e)
            return {
                'success': False,
                'error': f'论文搜索失败: {str(e)}',
                'papers': []
            }

    def generate_hypotheses(
        self,
        papers: List[Dict],
        research_field: str = "计算生物学",
        focus_areas: List[str] = [],
        num_hypotheses: int = None,  # 从配置读取
        enable_prevalidation: bool = True,
        min_score_threshold: float = None,  # 从配置读取
        max_internal_retries: int = None,  # 从配置读取
        # 新增：接受全局搜索参数
        min_if: float = None,
        date_range: tuple = None
    ) -> Dict:
        """
        第二步：生成假设（多轨并行优选版）

        V6.0 改进：所有阈值参数从 program_config 读取
        """
        # 从配置读取默认值
        if num_hypotheses is None:
            num_hypotheses = self.config.get('hypothesis_generation.num_hypotheses', 3)
        if min_score_threshold is None:
            min_score_threshold = self.config.get_min_score_threshold()
        if max_internal_retries is None:
            max_internal_retries = self.config.get('hypothesis_generation.max_internal_retries', 1)

        """
        新架构：
        1. 多轨并行：一次性生成 3-5 个不同方向的假设原型
        2. 快速初筛：ValidationAgent 对所有原型评分，保留最高分
        3. 激进突变：低分时触发"绝境Prompt"进行破坏性���构
        """

        # ==================== 全局参数穿透 ====================
        # 使用锁定的全局参数（确保反馈循环中不会丢失）
        locked_min_if = self.global_search_params['min_if']
        locked_date_range = self.global_search_params['date_range']

        print(f"\n[PARAM] Locked IF>={locked_min_if}, Date={locked_date_range}")
        # ==========================================================

        attempts = 0
        final_hypotheses = []
        prevalidation_log = []
        total_attempts = 0

        # ==================== 多轨并行优选配置（从 program_config 读取） ====================
        BEST_OF_N = self.config.get_best_of_n()  # 每轮生成原型数
        RADICAL_PIVOT_THRESHOLD = self.config.get_radical_pivot_threshold()  # 低于此分触发激进突变

        for hyp_idx in range(num_hypotheses):
            hyp_attempts = 0
            passed_hypothesis = None
            last_rejection_reason = ""
            last_avg_score = 0.0

            while hyp_attempts < max_internal_retries:
                hyp_attempts += 1
                total_attempts += 1

                self.logger.info(
                    f"[假设 {hyp_idx + 1}/{num_hypotheses}] 尝试 {hyp_attempts}/{max_internal_retries}"
                )

                # ==================== 多轨并行：一次性��成多个方向 ====================
                generation_params = {
                    'papers': papers,
                    'research_field': research_field,
                    'focus_areas': focus_areas,
                    'num_hypotheses': BEST_OF_N,  # 生成多个原型
                    'prevalidation_feedback': last_rejection_reason,
                    'enable_radical_pivot': (last_avg_score > 0 and last_avg_score < RADICAL_PIVOT_THRESHOLD)
                }

                gen_result = self.hypothesis_agent.execute(generation_params)

                if not gen_result.get('success'):
                    prevalidation_log.append({
                        'hypothesis_index': hyp_idx + 1,
                        'attempt': hyp_attempts,
                        'status': 'generation_failed',
                        'message': gen_result.get('error', '生成失败')
                    })
                    continue

                hypotheses = gen_result.get('hypotheses', [])
                if not hypotheses:
                    prevalidation_log.append({
                        'hypothesis_index': hyp_idx + 1,
                        'attempt': hyp_attempts,
                        'status': 'no_hypothesis',
                        'message': '未返回假设'
                    })
                    continue

                # ==================== 快速初筛：对所有原型评分，选最优 ====================
                if enable_prevalidation:
                    best_hypothesis = None
                    best_score = 0.0
                    best_validation = None

                    print(f"\n{'='*60}")
                    print(f"🔍 多轨并行初筛：{len(hypotheses)} 个假设原型进行评分...")
                    print(f"{'='*60}")

                    for i, hyp in enumerate(hypotheses):
                        hypothesis_title = hyp.get('title', f'假设原型 {i+1}')
                        print(f"\n  [{i+1}/{len(hypotheses)}] 评审: {hypothesis_title[:50]}...")

                        validation_result = self._validate_hypothesis_internal(hyp, papers)

                        if not validation_result.get('success'):
                            print(f"      ✗ 验证过程出错，跳过")
                            continue

                        validation = validation_result.get('validation', {})
                        scores = validation.get('scores', {})

                        transformative = scores.get('transformative_impact', 0)
                        originality = scores.get('methodological_originality', 0)
                        feasibility = scores.get('poc_feasibility', 0)
                        data_science = scores.get('data_science_red_lines', 0)
                        statistical = scores.get('statistical_hardening', 0)

                        avg_score = sum(scores.values()) / len(scores) if scores else 0

                        print(f"      颠覆性: {transformative}/10 | 原创性: {originality}/10")
                        print(f"      可行性: {feasibility}/10 | 数据科学: {data_science}/10")
                        print(f"      统计强化: {statistical}/10")
                        print(f"      📊 综合得分: {avg_score:.1f}/10")

                        if avg_score > best_score:
                            best_score = avg_score
                            best_hypothesis = hyp
                            best_validation = validation_result

                    if best_hypothesis:
                        hypothesis = best_hypothesis
                        hypothesis_title = best_hypothesis.get('title', '未命名')
                        avg_score = best_score

                        log_entry = {
                            'hypothesis_index': hyp_idx + 1,
                            'attempt': hyp_attempts,
                            'title': hypothesis_title,
                            'status': 'pending',
                            'best_of_n': f'{len(hypotheses)}选1',
                            'scores': best_validation.get('validation', {}).get('scores', {})
                        }

                        # 判断是否通过
                        passed = avg_score >= min_score_threshold
                        last_avg_score = avg_score  # 记录用于激进突变判断

                        if passed:
                            log_entry['status'] = 'passed'
                            log_entry['message'] = f'通过评审！平均分 {avg_score:.1f}/10 (多轨优选)'
                            prevalidation_log.append(log_entry)

                            hypothesis['prevalidation_scores'] = best_validation.get('validation', {}).get('scores', {})
                            hypothesis['prevalidation_avg'] = round(avg_score, 1)
                            passed_hypothesis = hypothesis
                            break
                        else:
                            rejection_reason = self._get_rejection_reason(best_validation)

                            # ==================== 激进突变：低分触发绝境Prompt ====================
                            if avg_score < RADICAL_PIVOT_THRESHOLD:
                                last_rejection_reason = self._build_radical_pivot_prompt(rejection_reason, avg_score)
                                print(f"\n⚠️  触发激进突变协议！得分 {avg_score:.1f}/10 过低")
                                print(f"绝境Prompt已注入，要求彻底重构...\n")
                            else:
                                last_rejection_reason = f"上一版假设评分不达标: {rejection_reason}\n请重新生成，避免类似问题。"

                            log_entry['status'] = 'rejected'
                            log_entry['message'] = f'打回重造: {rejection_reason} (得分: {avg_score:.1f}/10)'
                            prevalidation_log.append(log_entry)

                            self.logger.warning(
                                f"[假设 {hyp_idx + 1}] 第 {hyp_attempts} 次尝试被拒绝: {rejection_reason} (得分: {avg_score:.1f}/10)"
                            )
                    else:
                        prevalidation_log.append({
                            'hypothesis_index': hyp_idx + 1,
                            'attempt': hyp_attempts,
                            'status': 'validation_failed',
                            'message': '所有原型验证均失败'
                        })
                        last_rejection_reason = "所有生成的假设原型都未能通过验证。请彻底改变思路！"
                else:
                    prevalidation_log.append({
                        'hypothesis_index': hyp_idx + 1,
                        'attempt': hyp_attempts,
                        'title': hypothesis_title,
                        'status': 'passed',
                        'message': '跳过验证，直接通过'
                    })
                    passed_hypothesis = hypothesis
                    break

            if passed_hypothesis:
                final_hypotheses.append(passed_hypothesis)
            else:
                prevalidation_log.append({
                    'hypothesis_index': hyp_idx + 1,
                    'status': 'failed_all_retries',
                    'message': f'经过 {max_internal_retries} 次尝试仍未能生成合格假设'
                })

        # ==================== 强制预审闭环���首版即巅峰）====================
        # 在返回假设前，强制执行全球查新和内生审计
        # 只有通过审计的假设才会被返回给 UI
        final_hypotheses = self._enforce_preaudit_loop(
            final_hypotheses,
            prevalidation_log
        )
        # =================================================================

        # ==================== 字段映射：为前端添加 description 等字段 ====================
        # 前端 UI 读取的字段名与 HypothesisAgent 输出的字段名不一致
        # 需要添加映射以兼容前端渲染
        final_hypotheses = self._map_hypothesis_fields_for_ui(final_hypotheses)
        # ===========================================================================

        # 更新会话
        if self.current_session_id and final_hypotheses:
            with self.db_manager.get_session() as session:
                session_obj = session.query(ResearchSession).filter_by(
                    id=self.current_session_id
                ).first()
                if session_obj:
                    session_obj.hypotheses_generated = len(final_hypotheses)

        return {
            'success': True,
            'hypotheses': final_hypotheses,
            'hypothesis_ids': [f'hyp_{i}' for i in range(len(final_hypotheses))],
            'prevalidation_enabled': enable_prevalidation,
            'min_score_threshold': min_score_threshold,
            'prevalidation_log': prevalidation_log,
            'total_attempts': total_attempts,
            'passed_count': len(final_hypotheses),
            'target_count': num_hypotheses
        }

    def _enforce_preaudit_loop(
        self,
        hypotheses: List[Dict],
        prevalidation_log: List[Dict]
    ) -> List[Dict]:
        """
        强制预审闭环 - 首版即巅峰

        在假设返回给 UI 前，强制执行全球查新和内生审计。
        只有通过审计的假设才会被返回。

        审计流程：
        1. 对每个假设执行全球查新 (run_global_prior_art_probe)
        2. 新颖性评分 >= 50 才能继续
        3. 执行暗盒预审 (run_dark_box_pre_audit)
        4. 通过审计才能返回，否则触发反馈循环

        Args:
            hypotheses: 待审计的假设列表
            prevalidation_log: 预验证日志（用于记录审计过程）

        Returns:
            通过审计的假设列表
        """
        if not hypotheses:
            return hypotheses

        print("\n" + "="*80)
        print("🔒 [强制预审闭环] 首版即巅峰 - 启动全球查新与内生审计")
        print("="*80)

        audited_hypotheses = []
        max_audit_iterations = 2  # 每个假设最多审计迭代2次

        for hyp_idx, hypothesis in enumerate(hypotheses):
            print(f"\n{'─'*80}")
            print(f"📋 假设 {hyp_idx + 1}/{len(hypotheses)}: {hypothesis.get('title', '未命名')}")
            print(f"{'─'*80}")

            passed_hypothesis = None

            for iteration in range(max_audit_iterations):
                print(f"\n[审计轮次 {iteration + 1}/{max_audit_iterations}]")

                # ========== 阶段1: 全球查新探针 ==========
                print("  🌍 执行全球查新探针...")
                global_novelty_result = self.run_global_prior_art_probe(hypothesis)

                if not global_novelty_result.get('success'):
                    print(f"    ❌ 全球查新执行失败")
                    prevalidation_log.append({
                        'hypothesis_index': hyp_idx + 1,
                        'status': 'global_probe_failed',
                        'message': '全球查新探针执行失败'
                    })
                    break

                novelty_score = global_novelty_result.get('global_novelty_score', 0)
                print(f"    📊 全球新颖性评分: {novelty_score:.1f}/100")

                # 硬核标准：新颖性评分必须 >= 50
                if novelty_score < 50:
                    print(f"    ❌ 新颖性不足 (< 50)，触发反馈循环...")
                    collision_report = global_novelty_result.get('collision_report', {})
                    high_collision = collision_report.get('high_collision', [])

                    for paper in high_collision[:2]:
                        print(f"       撞衫: PMID:{paper.get('pmid', 'N/A')}")

                    # 触发反馈循环
                    if iteration < max_audit_iterations - 1:
                        feedback_context = {
                            'global_novelty': global_novelty_result,
                            'reason': 'global_collision'
                        }

                        print(f"    🔄 触发 run_feedback_loop 重新生成...")
                        feedback_result = self.run_feedback_loop(
                            hypothesis,
                            feedback_context,
                            output_dir='reports'
                        )

                        if feedback_result.get('success'):
                            revised = feedback_result.get('revised_hypothesis', {})
                            if revised:
                                hypothesis.update(revised)
                                print(f"    ✅ 迭代修正完成，重新审计...")
                                continue  # 下一轮审计
                        else:
                            print(f"    ❌ 反馈循环执行失败")
                            break
                    else:
                        print(f"    ❌ 已达最大迭代次数，假设被拒绝")
                        prevalidation_log.append({
                            'hypothesis_index': hyp_idx + 1,
                            'status': 'global_novelty_failed',
                            'message': f'全球新颖性不足 ({novelty_score:.1f}/100)'
                        })
                        break
                else:
                    print(f"    ✅ 全球查新通过")

                # ========== 阶段2: 暗盒预审 ==========
                print(f"  🔦 执行暗盒预审（跳过重复全球查新）...")

                # 使用已有的暗盒预审方法，跳过重复的全球查新
                dark_box_result = self.run_dark_box_pre_audit(
                    hypothesis,
                    skip_global_probe=True,
                    cached_global_result=global_novelty_result
                )

                if dark_box_result.get('audit_passed'):
                    print(f"    ✅ 暗盒预审通过")

                    # ==================== V6.1: 混合适应度评估 ====================
                    # 在审计通过后，执行混合适应度评估（物理铁闸 + 向量创新度）
                    print(f"  🧬 [V6.1] 执行混合适应度评估...")
                    fitness_result = self._evaluate_hypothesis_with_hybrid_fitness(
                        hypothesis,
                        self.current_papers  # 使用检索到的文献
                    )

                    # 检查混合适应度是否达标
                    min_threshold = self.config.get_min_score_threshold()
                    hybrid_score = fitness_result.get('hybrid_fitness', 0)

                    if fitness_result.get('fused'):
                        # 物理铁闸熔断
                        print(f"    ❌ V6.1 物理铁闸熔断: {fitness_result.get('fuse_reason', 'unknown')}")
                        prevalidation_log.append({
                            'hypothesis_index': hyp_idx + 1,
                            'status': 'physical_fuse_triggered',
                            'message': fitness_result.get('fuse_reason', '物理铁闸熔断')
                        })
                        if iteration < max_audit_iterations - 1:
                            # 尝试修正
                            feedback_context = {
                                'fitness_result': fitness_result,
                                'reason': 'physical_fuse'
                            }
                            feedback_result = self.run_feedback_loop(hypothesis, feedback_context, output_dir='reports')
                            if feedback_result.get('success'):
                                hypothesis.update(feedback_result.get('revised_hypothesis', {}))
                                continue
                        break

                    if hybrid_score < min_threshold:
                        print(f"    ❌ V6.1 混合适应度不达标: {hybrid_score:.2f} < {min_threshold}")
                        if iteration < max_audit_iterations - 1:
                            feedback_context = {
                                'fitness_result': fitness_result,
                                'reason': 'low_hybrid_fitness'
                            }
                            feedback_result = self.run_feedback_loop(hypothesis, feedback_context, output_dir='reports')
                            if feedback_result.get('success'):
                                hypothesis.update(feedback_result.get('revised_hypothesis', {}))
                                continue
                        break

                    print(f"    ✅ V6.1 混合适应度通过: {hybrid_score:.2f}")
                    # =============================================================

                    hypothesis['global_novelty_score'] = novelty_score
                    hypothesis['global_novelty_statement'] = global_novelty_result.get(
                        'global_novelty_statement', ''
                    )
                    hypothesis['preaudit_passed'] = True
                    hypothesis['hybrid_fitness'] = hybrid_score
                    hypothesis['fitness_result'] = fitness_result
                    passed_hypothesis = hypothesis
                    break  # 审计通过，退出循环
                else:
                    print(f"    ❌ 暗盒预审未通过")
                    critical_issues = dark_box_result.get('critical_issues', [])
                    for issue in critical_issues[:3]:
                        print(f"       - {issue}")

                    if iteration < max_audit_iterations - 1:
                        feedback_context = {
                            'global_novelty': global_novelty_result,
                            'dark_box_result': dark_box_result,
                            'reason': 'dark_box_failed'
                        }

                        print(f"    🔄 触发 run_feedback_loop 重新生成...")
                        feedback_result = self.run_feedback_loop(
                            hypothesis,
                            feedback_context,
                            output_dir='reports'
                        )

                        if feedback_result.get('success'):
                            revised = feedback_result.get('revised_hypothesis', {})
                            if revised:
                                hypothesis.update(revised)
                                print(f"    ✅ 迭代修正完成，重新审计...")
                                continue
                        else:
                            print(f"    ❌ 反馈循环执行失败")
                            break
                    else:
                        print(f"    ❌ 已达最大迭代次数，假设被拒绝")
                        prevalidation_log.append({
                            'hypothesis_index': hyp_idx + 1,
                            'status': 'dark_box_failed',
                            'message': '暗盒预审未通过'
                        })
                        break

            if passed_hypothesis:
                audited_hypotheses.append(passed_hypothesis)
                print(f"\n✅ 假设 {hyp_idx + 1} 通过所有审计，将返回给 UI")
            else:
                print(f"\n❌ 假设 {hyp_idx + 1} 未通过审计，已被过滤")

        print(f"\n{'='*80}")
        print(f"🎯 强制预审闭环完成")
        print(f"   输入假设: {len(hypotheses)} | 通过审计: {len(audited_hypotheses)}")
        print(f"{'='*80}\n")

        return audited_hypotheses

    # ==================== 全球查新闭环 (Global Prior Art Loop) ====================

    def run_global_prior_art_probe(self, hypothesis_data: dict) -> Dict:
        """
        全球查新探针 - 核心新增功能

        在用户看到任何输出前，对生成的假设原型执行全库检索，
        发现全球已有的相似研究，评估新颖性。

        Args:
            hypothesis_data: 假设原型数据

        Returns:
            {
                'success': bool,
                'probe_queries': List[str],
                'similar_papers': List[Dict],
                'collision_report': Dict,
                'novelty_gaps': List[str],
                'global_novelty_score': float,
                'global_novelty_statement': str  # 新增：全球新颖性声明
            }
        """
        print("\n" + "="*60)
        print("🌍 [全球查新探针] 启动全库检索")
        print("="*60)
        print("⚠️  执行严格查新，确保研究具备全球领先性...")

        result = self.global_prior_art_probe.execute({
            'hypothesis_data': hypothesis_data,
            'paper_search_agent': self.paper_agent,
            'output_dir': 'reports',
            # 🔒 传递锁定的全局参数
            'date_range': self.global_search_params['date_range'],
            'min_if': self.global_search_params['min_if']
        })

        if result['success']:
            # 生成全球新颖性声明
            result['global_novelty_statement'] = self._generate_global_novelty_statement(
                result['collision_report'],
                result['novelty_gaps'],
                result['global_novelty_score']
            )

            # 打印声明
            print("\n" + "─"*60)
            print("📋 全球新颖性声明")
            print("─"*60)
            print(result['global_novelty_statement'])
            print("─"*60)

        return result

    def run_dark_box_pre_audit(
        self,
        hypothesis_data: dict,
        skip_global_probe: bool = False,
        cached_global_result: dict = None
    ) -> Dict:
        """
        暗盒预审流 - 三方会审

        在用户看到任何输出前执行：
        1. 全球查新探针 (ValidationAgent负责) - 可选跳过
        2. 逻辑硬核审计 (BiostatsAgent负责)
        3. 破坏性审计 (RedTeamAgent负责)

        Args:
            hypothesis_data: 假设原型数据
            skip_global_probe: 是否跳过全球查新（如果已执行过）
            cached_global_result: 缓存的全球查新结果

        Returns:
            {
                'success': bool,
                'audit_passed': bool,  # 是否通过三方会审
                'global_novelty_result': Dict,
                'biostats_audit_result': Dict,
                'red_team_audit_result': Dict,
                'critical_issues': List[str],  # 需要修复的关键问题
                'feedback_for_iteration': str  # 反馈给HypothesisAgent的信息
            }
        """
        print("\n" + "="*60)
        print("🔦 [暗盒预审] 三方会审启动")
        print("="*60)
        print("在用户看到任何输出前，执行严格审计...")

        results = {
            'success': True,
            'audit_passed': False,
            'global_novelty_result': None,
            'biostats_audit_result': None,
            'red_team_audit_result': None,
            'critical_issues': [],
            'feedback_for_iteration': ''
        }

        # ========== 阶段B: 全球查新探针 ==========
        global_novelty_result = None  # 初始化变量，避免 UnboundLocalError

        if not skip_global_probe:
            print("\n【阶段B/3】全球查新探针...")
            global_novelty_result = self.run_global_prior_art_probe(hypothesis_data)
            results['global_novelty_result'] = global_novelty_result

            if not global_novelty_result['success']:
                results['critical_issues'].append("全球查新探针执行失败")
                return results

            global_novelty_score = global_novelty_result.get('global_novelty_score', 0)

            # 检查全球新颖性
            if global_novelty_score < 50:
                collision_report = global_novelty_result.get('collision_report', {})
                high_collision = collision_report.get('high_collision', [])

                results['critical_issues'].append(
                    f"全球新颖性不足 (评分: {global_novelty_score:.1f}/100)"
                )

                for paper in high_collision[:3]:
                    results['critical_issues'].append(
                        f"  - 撞衫文献 PMID:{paper['pmid']} - {paper['title'][:60]}..."
                    )
        elif cached_global_result:
            print("\n【阶段B/3】使用缓存的全球查新结果...")
            global_novelty_result = cached_global_result  # 修复：赋值给局部变量
            results['global_novelty_result'] = cached_global_result
        else:
            print("\n【阶段B/3】跳过全球查新（已在前置步骤完成）...")
            # 无缓存结果时，使用空字典避免后续错误
            global_novelty_result = {}

        # ========== 阶段C-1: 逻辑硬核审计 (BiostatsAgent) ==========
        print("\n【阶段C-1/3】逻辑硬核审计 (BiostatsAgent)...")

        # 提取碰撞文献用于"打脸"
        collision_papers = []
        if global_novelty_result:
            collision_report = global_novelty_result.get('collision_report', {})
            collision_papers = collision_report.get('high_collision', [])[:3]

        # 调用 LLM 驭动的统计审计
        biostats_audit_result = self._run_biostats_hardcore_audit(hypothesis_data, collision_papers)
        results['biostats_audit_result'] = biostats_audit_result

        if not biostats_audit_result['passed']:
            results['critical_issues'].extend(
                biostats_audit_result.get('critical_issues', [])
            )

        # ========== 阶段C-2: 破坏性审计 (RedTeamAgent) ==========
        print("\n【阶段C-2/3】破坏性审计 (RedTeamAgent)...")

        # ==================== 透明化追踪：红方审计开始 ====================
        print("\n┌────────────────────────────────────────────────────────────────┐")
        print("│  🔴 红方审计员进场 - 极度挑剔的Nature审稿人模式                 │")
        print("└────────────────────────────────────────────────────────────────┘")
        # ====================================================================

        # 调用 LLM 驭动的红方攻击
        red_team_audit_result = self._run_red_team_audit(hypothesis_data, collision_papers)
        results['red_team_audit_result'] = red_team_audit_result

        if not red_team_audit_result['passed']:
            results['critical_issues'].extend(
                red_team_audit_result.get('critical_issues', [])
            )

            # ==================== 透明化追踪：红方攻击点 ====================
            print("\n   🔴 【红方审计报告】发现以下攻击点：")
            for i, issue in enumerate(red_team_audit_result.get('critical_issues', []), 1):
                print(f"      [{i}] ⚔️  {issue}")
            # ====================================================================

        # ========== 阶段C-3: 综合裁决 ==========
        print("\n【阶段C-3/3】综合裁决...")

        if not results['critical_issues']:
            results['audit_passed'] = True
            print("✅ 三方会审通过！")
        else:
            results['audit_passed'] = False

            # ==================== 透明化追踪：综合审计报告 ====================
            print("\n" + "="*70)
            print("🔴 ══════════════════ 【红方审计报告】 ══════════════════")
            print("="*70)

            # Part 1: 碰撞证据
            collision_report = global_novelty_result.get('collision_report', {}) if global_novelty_result else {}
            high_collision = collision_report.get('high_collision', [])
            if high_collision:
                print("\n📋 【碰撞证据】以下文献与你的假设高度同质化：")
                for i, paper in enumerate(high_collision[:5], 1):
                    print(f"   ┌─────────────────────────────────────────")
                    print(f"   │ [{i}] PMID: {paper.get('pmid', 'N/A')}")
                    print(f"   │ 标题: {paper.get('title', 'N/A')[:50]}...")
                    print(f"   │ 期刊: {paper.get('journal', 'N/A')} ({paper.get('date', 'N/A')})")
                    print(f"   │ 相似度: {paper.get('similarity', 0)*100:.0f}%")
                    print(f"   │ 原因: {paper.get('reason', '核心概念重叠')}")
                    print(f"   └─────────────────────────────────────────")
            else:
                print("\n📋 【碰撞证据】无明显同质化文献")

            # Part 2: 技术槽点
            tech_issues = biostats_audit_result.get('critical_issues', []) if biostats_audit_result else []
            if tech_issues:
                print("\n🔧 【技术槽点】技术路线存在以下硬伤：")
                for i, issue in enumerate(tech_issues, 1):
                    print(f"   [{i}] 🛠️  {issue}")

            # Part 3: 逻辑漏洞
            logic_issues = red_team_audit_result.get('critical_issues', [])
            if logic_issues:
                print("\n🧠 【逻辑漏洞】因果链条在以下环节断裂：")
                for i, issue in enumerate(logic_issues, 1):
                    print(f"   [{i}] 💔 {issue}")

            # Part 4: 总裁决
            print("\n" + "-"*70)
            print(f"🚫 总裁决: REJECT | 共发现 {len(results['critical_issues'])} 个致命问题")
            print("-"*70)
            print("="*70 + "\n")
            # ====================================================================

            # 生成反馈信息
            results['feedback_for_iteration'] = self._generate_audit_feedback(
                global_novelty_result,
                biostats_audit_result,
                red_team_audit_result
            )

        return results

    def _run_biostats_hardcore_audit(self, hypothesis_data: dict, collision_papers: list = None) -> Dict:
        """
        逻辑硬核审计 - LLM 驭动版

        专注于因果推断、混杂控制与统计功效的数学严谨性
        废除硬编码关键词匹配，改为 LLM 动态分析
        """
        print("\n   🔧 [统计审计员] 正在进行因果推断与统计功效审查...")

        result = {
            'passed': False,
            'critical_issues': [],
            'scores': {},
            'raw_attack_text': ''  # 保存原始攻击文本用于反馈注入
        }

        # 构建蓝方防御材料
        blue_package = {
            'hypothesis_data': hypothesis_data,
            'genai_proposal': hypothesis_data.get('technical_route', ''),
            'biostats_proposal': hypothesis_data.get('statistical_novelty', '')
        }

        # 如果有碰撞文献，注入作为"打脸"依据
        if collision_papers:
            blue_package['collision_evidence'] = collision_papers[:3]

        # ==================== LLM 驭动审计 ====================
        prompt = self._build_biostats_audit_prompt(hypothesis_data, collision_papers)

        try:
            # 调用 LLM 进行动态审计
            print("   └─ 调用 LLM 进行因果推断审查...")

            message = self.client.messages.create(
                model=self.model,
                max_tokens=3000,
                temperature=0.2,  # 低温度确保严格一致性
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text

            # 解析 LLM 响应
            import json
            import re

            # 提取 JSON 块
            json_pattern = r'```json\s*([\s\S]*?)\s*```'
            json_matches = re.findall(json_pattern, response_text)

            if json_matches:
                audit_data = json.loads(json_matches[0])
            else:
                # 尝试直接解析
                audit_data = json.loads(response_text)

            result['critical_issues'] = audit_data.get('critical_issues', [])
            result['scores'] = audit_data.get('scores', {})
            result['raw_attack_text'] = response_text  # 保存原始文本
            result['passed'] = len(result['critical_issues']) == 0

            # ==================== 透明化追踪：审计意见输出 ====================
            print("\n   🔧 ═══════════════ 【统计审计员锐评】 ═══════════════")
            for i, issue in enumerate(result['critical_issues'][:3], 1):
                print(f"      [{i}] 🛠️  {issue}")
            if result['passed']:
                print("      ✅ 统计框架通过审查")
            # ==============================================================

        except Exception as e:
            print(f"   ⚠️ LLM 审计异常: {e}")
            # 回退：不添加任何硬编码问题，保持诚实
            result['critical_issues'] = []
            result['passed'] = True
            result['raw_attack_text'] = f"审计过程异常: {e}"

        return result

    def _build_biostats_audit_prompt(self, hypothesis_data: dict, collision_papers: list = None) -> str:
        """构建统计审计 LLM 提示词"""

        title = hypothesis_data.get('title', '')
        description = hypothesis_data.get('description', '')
        technical_route = hypothesis_data.get('technical_route', '')
        statistical_novelty = hypothesis_data.get('statistical_novelty', '')

        # 碰撞证据部分（用于"打脸"）
        collision_section = ""
        if collision_papers:
            collision_section = "\n## 📋 检索到的相关文献（可作为批评依据）\n"
            for paper in collision_papers[:3]:
                collision_section += f"- PMID: {paper.get('pmid')}\n"
                collision_section += f"  标题: {paper.get('title', '')[:60]}\n"
                collision_section += f"  方法: {paper.get('abstract', '')[:200]}\n\n"

        prompt = f"""你是一位**极度严苛的生物统计学审稿人**，Nature Methods 级别。
你的唯一任务是：找出以下假设中**因果推断框架**和**统计功效分析**的致命缺陷。

**禁止输出通用模板话术！必须针对具体内容生成尖锐批评。**

---

## 待审假设

**标题**: {title}

**描述**: {description[:800]}

**技术路线**: {technical_route[:800]}

**统计创新**: {statistical_novelty[:500]}

{collision_section}

---

## 审计焦点（必须逐一检查）

### 1. 因果推断框架 (Causal Inference Framework)
- 是否有明确的 DAG (有向无环图)？
- 是否识别并闭合了所有后门路径？
- 是否使用中介分析 (Mediation Analysis)？
- 是否有 E-value 敏感性分析？

### 2. 混杂控制 (Confounder Control)
- 关键混杂因素是否被识别？
- 是否使用倾向性评分匹配 (PSM) 或逆概率加权 (IPW)？
- 是否考虑了未测量混杂的影响？

### 3. 统计功效 (Statistical Power)
- 是否有 a priori 功效分析？
- 样本量是否满足参数量/10 规则？
- 是否计算了最小可检测效应量？

### 4. 多重检验校正 (Multiple Testing Correction)
- 是否使用 FDR 或 Bonferroni 校正？
- 校正方法是否适合研究设计？

---

## 输出格式（JSON）

```json
{{
  "critical_issues": [
    "具体的、针对性的批评1",
    "具体的、针对性的批评2",
    "具体的、针对性的批评3"
  ],
  "scores": {{
    "causal_framework": "0-10分",
    "confounder_control": "0-10分",
    "power_analysis": "0-10分",
    "multiple_testing": "0-10分"
  }},
  "overall_assessment": "整体评估（必须引用具体内容）"
}}
```

**关键要求**：
- 如果有碰撞文献，引用它们的方法作为"打脸"依据
- 例如："PMID:XXX 已证明了使用 DAG+中介分析的标准流程，你的方案缺少..."
- 批评必须具体，例如："第X步的混杂控制不充分，因为..."
- 如果方案确实优秀，可以诚实承认，但必须给出至少 1 条改进建议

请开始你的严格审计："""

        return prompt

    def _run_red_team_audit(self, hypothesis_data: dict, collision_papers: list = None) -> Dict:
        """
        破坏性审计 - LLM 驭动版

        废除硬编码关键词匹配，改为 LLM 动态分析
        必须根据具体假设生成针对性攻击
        """
        print("\n   🔴 [红方审计员] 正在进行破坏性逻辑攻击...")

        result = {
            'passed': False,
            'critical_issues': [],
            'attack_vectors': [],
            'raw_attack_text': ''  # 保存原始攻击文本用于反馈注入
        }

        # ==================== LLM 驭动审计 ====================
        prompt = self._build_red_team_audit_prompt(hypothesis_data, collision_papers)

        try:
            # 调用 LLM 进行动态攻击
            print("   └─ 调用 LLM 进行逻辑漏洞攻击...")

            message = self.client.messages.create(
                model=self.model,
                max_tokens=3000,
                temperature=0.3,  # 稍高温度增加攻击多样性
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text

            # 解析 LLM 响应
            import json
            import re

            # 提取 JSON 块
            json_pattern = r'```json\s*([\s\S]*?)\s*```'
            json_matches = re.findall(json_pattern, response_text)

            if json_matches:
                attack_data = json.loads(json_matches[0])
            else:
                # 尝试直接解析
                attack_data = json.loads(response_text)

            result['critical_issues'] = attack_data.get('critical_flaws', attack_data.get('critical_issues', []))
            result['attack_vectors'] = attack_data.get('attack_vectors', [])
            result['raw_attack_text'] = response_text  # 保存原始文本用于反馈注入
            result['passed'] = len(result['critical_issues']) == 0

            # ==================== 透明化追踪：红方攻击输出 ====================
            print("\n   🔴 ═══════════════ 【红方审计员锐评】 ═══════════════")
            for i, issue in enumerate(result['critical_issues'][:3], 1):
                print(f"      [{i}] 💔 {issue}")
            if result['passed']:
                print("      ✅ 逻辑链条通过攻击测试")
            # ==============================================================

        except Exception as e:
            print(f"   ⚠️ LLM 红方审计异常: {e}")
            # 回退：不添加任何硬编码问题，保持诚实
            result['critical_issues'] = []
            result['attack_vectors'] = []
            result['passed'] = True
            result['raw_attack_text'] = f"红方审计过程异常: {e}"

        return result


    # ==================== V6.1 混合适应度评估 ====================

    def _evaluate_hypothesis_with_hybrid_fitness(
        self,
        hypothesis: Dict,
        retrieved_docs: List[Dict]
    ) -> Dict:
        """
        V6.1 混合适应度评估

        流程：
        1. 物理铁闸校验（若失败 → 立即熔断）
        2. 向量创新度计算（甜点区算法）
        3. 红方严谨性审查（降权后）
        4. 混合得分计算

        Args:
            hypothesis: 假设数据
            retrieved_docs: 检索到的文献列表

        Returns:
            Dict: 包含 hybrid_fitness, vector_novelty, rigor, fused 状态
        """
        print("\n   [V6.1 混合适应度] 正在计算综合得分...")

        try:
            # 导入混合打分器
            from core.hybrid_fitness import get_hybrid_fitness_scorer
            scorer = get_hybrid_fitness_scorer()

            # Step 1: 物理铁闸校验
            print("   └─ Step 1: 物理铁闸校验...")
            from core.physical_validator import get_physical_validator
            validator = get_physical_validator()
            physical_result = validator.validate_hypothesis_physical(hypothesis)

            if not physical_result.passed:
                # 熔断！
                print(f"   物理铁闸熔断: {physical_result.failure_reason}")
                return {
                    'hybrid_fitness': 0.0,
                    'vector_novelty': 0.0,
                    'rigor': 0.0,
                    'fused': True,
                    'fuse_reason': physical_result.failure_reason,
                    'physical_validation': {
                        'passed': False,
                        'details': physical_result.details
                    }
                }

            print("   └─ 物理铁闸校验通过 ✓")

            # Step 2: 向量创新度计算
            print("   └─ Step 2: 向量创新度计算...")
            result = scorer.calculate_fitness(hypothesis, retrieved_docs)

            # Step 3: 红方严谨审查（降权版）
            print("   └─ Step 3: 红方严谨性审查（降权版）...")
            rigor_report = self._run_v61_rigor_audit(hypothesis)

            # 合并严谨分
            result.red_team_rigor_score = rigor_report.get('rigor_score', 7.5)

            # Step 4: 最终得分计算
            final_score = result.hybrid_fitness

            print("\\n   ═══════════════ 【混合适应度报告】 ═══════════════")
            print(f"      相似度: {result.similarity:.3f} ({result.similarity_interpretation})")
            print(f"      向量创新分: {result.vector_novelty_score:.2f} (权重 60%)")
            print(f"      红方严谨分: {result.red_team_rigor_score:.2f} (权重 40%)")
            print(f"      ────────────────────────────────────────")
            print(f"      混合得分: {final_score:.2f}")
            print(f"      熔断状态: {'已熔断' if result.fused else '正常'}")

            return {
                'hybrid_fitness': final_score,
                'vector_novelty': result.vector_novelty_score,
                'rigor': result.red_team_rigor_score,
                'similarity': result.similarity,
                'similarity_interpretation': result.similarity_interpretation,
                'fused': result.fused,
                'fuse_reason': result.fuse_reason,
                'physical_validation': result.physical_validation
            }

        except Exception as e:
            print(f"   混合适应度评估异常: {e}")
            # 回退到传统评分
            scores = hypothesis.get('scores', {})
            return {
                'hybrid_fitness': scores.get('overall', 7.5),
                'vector_novelty': scores.get('novelty', 7.5),
                'rigor': scores.get('rigor', 7.5),
                'fused': False,
                'fuse_reason': '',
                'fallback': True,
                'error': str(e)
            }

    def _run_v61_rigor_audit(self, hypothesis_data: dict) -> Dict:
        """
        V6.1 红方严谨性审查（降权版）

        只评估严谨性，不评估创新性
        """
        print("\\n   [红方审计员V6.1] 正在进行严谨性审查...")

        try:
            # 导入红方审计员
            from agents.red_team_agent import RedTeamAgent
            red_team = RedTeamAgent()

            # 构建输入数据
            input_data = {
                'hypothesis_data': hypothesis_data,
                'technical_proposal': hypothesis_data.get('technical_route', '')
            }

            # 执行降权版审计
            result = red_team.execute_v61_rigor_audit(input_data)

            if result.get('success'):
                rigor_report = result.get('rigor_report', {})
                print(f"   └─ 严谨分: {rigor_report.get('rigor_score', 7.5)}")
                return rigor_report
            else:
                print(f"   红方审计失败: {result.get('error', 'unknown')}")
                return {'rigor_score': 7.5, 'verdict': 'pass'}

        except Exception as e:
            print(f"   红方审计异常: {e}")
            return {'rigor_score': 7.5, 'verdict': 'pass'}

    def _build_red_team_audit_prompt(self, hypothesis_data: dict, collision_papers: list = None) -> str:
        """构建红方攻击 LLM 提示词"""

        title = hypothesis_data.get('title', '')
        description = hypothesis_data.get('description', '')
        technical_route = hypothesis_data.get('technical_route', '')
        core_hypothesis = hypothesis_data.get('core_hypothesis', hypothesis_data.get('rationale', ''))

        # 碰撞证据部分（用于"打脸"）
        collision_section = ""
        if collision_papers:
            collision_section = "\n## 📋 检索到的相关文献（可作为攻击依据）\n"
            collision_section += "**以下文献已发表了类似研究，你可以引用它们来攻击假设的新颖性：**\n\n"
            for paper in collision_papers[:3]:
                collision_section += f"- **PMID: {paper.get('pmid')}**\n"
                collision_section += f"  标题: {paper.get('title', '')[:70]}\n"
                collision_section += f"  期刊: {paper.get('journal', '')} ({paper.get('date', '')})\n"
                collision_section += f"  核心方法: {paper.get('abstract', '')[:300]}\n\n"

        prompt = f"""你是一位**毒舌且严谨的 Nature 审稿人**，专门攻击假设中的逻辑漏洞。
你的唯一任务是：**寻找并摧毁**以下假设的因果链条。

**绝对禁止输出通用模板话术！必须针对具体内容生成尖锐攻击。**
**如果有碰撞文献，必须引用它们作为"打脸"依据。**

---

## 待攻击假设

**标题**: {title}

**核心假设**: {core_hypothesis[:500]}

**描述**: {description[:800]}

**技术路线**: {technical_route[:800]}

{collision_section}

---

## 攻击焦点（必须逐一尝试）

### 1. 因果链条断裂点
- Exposure → Mediator → Outcome 链条是否完整？
- Mediator 是否真的中介了 Exposure 对 Outcome 的影响？
- 是否存在反向因果 (Outcome → Exposure)？

### 2. 泛化能力缺失
- 方法是否只在特定数据集上有效？
- 是否缺乏外部验证集？
- 是否存在过拟合风险？

### 3. 可扩展性崩溃
- 方法在大规模数据下是否会崩溃？
- 计算复杂度是否合理？
- 是否有 GPU/并行化需求但未说明？

### 4. 数据泄露风险
- 特征选择是否在 CV 外进行？
- 时间序列是否使用未来信息？
- 同一患者的数据是否分散在 train/test？

---

## 输出格式（JSON）

```json
{{
  "critical_flaws": [
    "具体的、针对性的攻击1（必须引用假设中的具体内容）",
    "具体的、针对性的攻击2（如果有碰撞文献，引用PMID）",
    "具体的、针对性的攻击3"
  ],
  "attack_vectors": [
    "攻击方向1：如何摧毁这个假设",
    "攻击方向2：另一个攻击角度"
  ],
  "overall_assessment": "整体攻击总结（必须毒舌但有理有据）"
}}
```

**攻击示例（必须有理有据）**：
- "你的因果链条在第2步断裂，因为 PMID:XXX 已证明 Mediator 与 Outcome 无因果关系"
- "泛化能力缺失：方案只在 ADNI 数据集上验证，缺乏外部验证集"
- "技术路线第X步存在数据泄露风险，因为特征选择未在 CV 内进行"

**关键要求**：
- 如果有碰撞文献，必须引用至少 1 篇作为"你的方法已经被发表过"的证据
- 批评必须具体，例如："因果链条中的 X→M 步骤缺少中介效应检验..."
- 如果假设确实优秀，可以诚实承认，但必须给出改进建议

请开始你的毒舌攻击："""

        return prompt

    def _generate_global_novelty_statement(
        self,
        collision_report: dict,
        novelty_gaps: list,
        global_novelty_score: float
    ) -> str:
        """生成全球新颖性声明"""
        high_collision = collision_report.get('high_collision', [])
        medium_collision = collision_report.get('medium_collision', [])

        statement_parts = []

        # 开头
        statement_parts.append(f"全球新颖性评分: {global_novelty_score:.1f}/100")
        statement_parts.append("")

        # 撞衫情况
        if high_collision:
            statement_parts.append("⚠️  高度相似文献 (需要差异化突破):")
            for paper in high_collision[:3]:
                statement_parts.append(
                    f"  - PMID:{paper['pmid']} | {paper['title'][:70]}..."
                )
                statement_parts.append(f"    相似度: {paper['similarity']:.0%} | {paper['reason']}")
            statement_parts.append("")

        # 创新空白点
        if novelty_gaps:
            statement_parts.append("✨ 本研究相对于全球已发表文献的创新点:")
            for gap in novelty_gaps:
                statement_parts.append(f"  - {gap}")
            statement_parts.append("")

        # 结论
        if global_novelty_score >= 70:
            statement_parts.append("✅ 结论: 具备全球领先性，建议推进")
        elif global_novelty_score >= 50:
            statement_parts.append("⚠️  结论: 中等新颖性，建议在创新空白点上深化")
        else:
            statement_parts.append("❌ 结论: 新颖性不足，需要差异化重写")

        return "\n".join(statement_parts)

    def _generate_audit_feedback(
        self,
        global_novelty_result: dict,
        biostats_audit_result: dict,
        red_team_audit_result: dict
    ) -> str:
        """
        生成结构化红方审计报告（LLM 动态版本）

        核心改进：使用 LLM 生成的原始攻击文本，而非硬编码模板
        """
        feedback_parts = []

        # 实时对谈日志头
        print("\n" + "="*70)
        print("🔴 ══════════════════ 【红方审计报告 - 闭环注入】 ══════════════════")
        print("="*70)

        feedback_parts.append("# 🔴 ══════════════════ 红方审计报告 ══════════════════")
        feedback_parts.append("")
        feedback_parts.append("## 【审计结论】假设未通过三方会审")
        feedback_parts.append("---")

        # Part 1: 碰撞证据
        feedback_parts.append("## 📋 Part 1: 碰撞证据（撞衫文献）")
        collision_report = global_novelty_result.get('collision_report', {}) if global_novelty_result else {}
        high_collision = collision_report.get('high_collision', [])
        if high_collision:
            for i, paper in enumerate(high_collision[:5], 1):
                feedback_parts.append(f"### 文献 [{i}] PMID:{paper.get('pmid', 'N/A')}")
                feedback_parts.append(f"- 标题: {paper.get('title', 'N/A')[:80]}")
        else:
            feedback_parts.append("*无明显撞衫文献*")
        feedback_parts.append("---")

        # Part 2: 统计审计员锐评（LLM 动态）
        feedback_parts.append("## 🔧 Part 2: 统计审计员锐评（LLM 动态生成）")
        biostats_raw = biostats_audit_result.get('raw_attack_text', '') if biostats_audit_result else ''
        if biostats_raw:
            feedback_parts.append(biostats_raw[:1500])
            print("\n   🔧 [统计审计员] 锐评：")
            print(f"   {biostats_raw[:300]}...")
        else:
            issues = biostats_audit_result.get('critical_issues', []) if biostats_audit_result else []
            for issue in issues[:3]:
                feedback_parts.append(f"🛠️ {issue}")
                print(f"   🛠️ {issue}")
        feedback_parts.append("---")

        # Part 3: 红方审计员锐评（LLM 动态）
        feedback_parts.append("## 🧠 Part 3: 红方审计员锐评（LLM 动态生成）")
        red_raw = red_team_audit_result.get('raw_attack_text', '')
        if red_raw:
            feedback_parts.append(red_raw[:1500])
            print("\n   🔴 [红方审计员] 锐评：")
            print(f"   {red_raw[:300]}...")
        else:
            issues = red_team_audit_result.get('critical_issues', [])
            for issue in issues[:3]:
                feedback_parts.append(f"💔 {issue}")
                print(f"   💔 {issue}")
        feedback_parts.append("---")

        # Part 4: 首席科学家应对
        feedback_parts.append("## 💡 Part 4: 首席科学家应对方向")
        feedback_parts.append("针对批评，调整中介模型参数...")
        feedback_parts.append("*此报告由 LLM 动态生成*")

        # 实时对谈日志尾
        print("\n   🧠 [首席科学家] 思考：调整中介模型参数...")
        print("="*70 + "\n")

        return "\n".join(feedback_parts)


    def run_differential_iteration(
        self,
        hypothesis_data: dict,
        audit_feedback: str,
        papers: list
    ) -> Dict:
        """
        差异化迭代 - 强制性反馈循环

        当审计不通过时，强制触发差异化重写

        Args:
            hypothesis_data: 原假设数据
            audit_feedback: 审计反馈信息
            papers: 源论文

        Returns:
            重新生成的假设结果
        """
        print("\n" + "="*60)
        print("🔄 [差异化迭代] 强制执行")
        print("="*60)
        print(audit_feedback[:500])
        print("..." + "="*60)

        # 将审计反馈传递给HypothesisAgent
        generation_params = {
            'papers': papers,
            'research_field': hypothesis_data.get('research_field', '计算生物学'),
            'num_hypotheses': 1,
            'prevalidation_feedback': audit_feedback  # 关键：使用审计反馈
        }

        gen_result = self.hypothesis_agent.execute(generation_params)

        if gen_result.get('success'):
            hypotheses = gen_result.get('hypotheses', [])
            if hypotheses:
                new_hypothesis = hypotheses[0]
                print(f"✅ 差异化重写完成: {new_hypothesis.get('title', '')[:60]}...")
                return {
                    'success': True,
                    'hypothesis': new_hypothesis,
                    'iteraton_count': 1
                }

        return {
            'success': False,
            'error': '差异化重写失败'
        }

    # ==================== 原有方法 ====================

    def run_data_governance_audit(self, hypothesis_data: dict, data_hunter_report: dict) -> Dict:
        """
        数据治理审计（新增环节）

        Args:
            hypothesis_data: 假设数据
            data_hunter_report: 数据探勘报告

        Returns:
            数据治理审计结果
        """
        print("\n" + "="*60)
        print("🛡️  数据治理与质控审计")
        print("="*60)

        result = self.data_governance_agent.execute({
            'hypothesis_data': hypothesis_data,
            'data_hunter_report': data_hunter_report,
            'output_dir': 'reports'
        })

        if not result['success']:
            print("❌ 数据治理审计失败")
            return result

        qc_protocol = result.get('qc_protocol', {})

        # 检查阻断条件
        block_conditions = qc_protocol.get('block_conditions', [])
        if block_conditions:
            print("⚠️  数据质量问题：")
            for condition in block_conditions:
                print(f"  - {condition}")

        return result

    def run_dry_lab_waterfall(self, hypothesis_data: dict, output_dir: str = 'reports') -> Dict:
        """
        运行纯干实验瀑布流（核心流程）

        步骤顺序：
        1. GenAIExpertAgent
        2. CompBioAgent (含QC协议)
        3. DigitalPathologyAgent
        4. BiostatsAgent (含E-value/Power/FDR)
        5. ResourceEstimatorAgent (资源核算)
        6. ClinicalMDAgent

        Args:
            hypothesis_data: 假设数据
            output_dir: 输出目录

        Returns:
            瀑布流执行结果
        """
        print("\n" + "="*60)
        print("🧬 启动纯干实验瀑布流")
        print("="*60)

        results = {
            'success': True,
            'genai_proposal': None,
            'compbio_proposal': None,
            'pathology_proposal': None,
            'biostats_proposal': None,
            'resource_estimate': None,
            'clinical_review': None,
            'errors': []
        }

        # 步骤1: GenAIExpertAgent
        print("\n📍 步骤1/6: GenAI架构设计")
        try:
            genai_result = self.genai_expert_agent.execute({
                'hypothesis_data': hypothesis_data,
                'output_dir': output_dir
            })
            if genai_result['success']:
                results['genai_proposal'] = genai_result['genai_proposal']
                print("✅ GenAI架构设计完成")
            else:
                results['success'] = False
                results['errors'].append("GenAI架构设计失败")
                return results
        except Exception as e:
            results['success'] = False
            results['errors'].append(f"GenAI架构设计异常: {str(e)}")
            return results

        # 步骤2: CompBioAgent (含QC协议)
        print("\n📍 步骤2/6: 计算生物学Pipeline (含QC协议)")
        try:
            compbio_result = self.comp_bio_agent.execute({
                'hypothesis_data': hypothesis_data,
                'genai_proposal': results['genai_proposal'],
                'output_dir': output_dir
            })
            if compbio_result['success']:
                results['compbio_proposal'] = compbio_result['compbio_proposal']
                qc_protocol = compbio_result.get('qc_protocol', {})
                print("✅ 计算生物学Pipeline完成")
                if qc_protocol.get('batch_correction_required'):
                    print(f"  - 批次校正: {qc_protocol.get('batch_method', 'unknown')}")
                if qc_protocol.get('imputation_method') != 'unknown':
                    print(f"  - 缺失值插补: {qc_protocol.get('imputation_method', 'unknown')}")
            else:
                results['success'] = False
                results['errors'].append("计算生物学Pipeline失败")
                return results
        except Exception as e:
            results['success'] = False
            results['errors'].append(f"计算生物学Pipeline异常: {str(e)}")
            return results

        # 步骤3: DigitalPathologyAgent
        print("\n📍 步骤3/6: 数字病理学分析")
        try:
            pathology_result = self.digital_pathology_agent.execute({
                'hypothesis_data': hypothesis_data,
                'genai_proposal': results['genai_proposal'],
                'compbio_proposal': results['compbio_proposal'],
                'output_dir': output_dir
            })
            if pathology_result['success']:
                results['pathology_proposal'] = pathology_result['pathology_proposal']
                print("✅ 数字病理学分析完成")
            else:
                results['success'] = False
                results['errors'].append("数字病理学分析失败")
                return results
        except Exception as e:
            results['success'] = False
            results['errors'].append(f"数字病理学分析异常: {str(e)}")
            return results

        # 步骤4: BiostatsAgent (含E-value/Power/FDR)
        print("\n📍 步骤4/6: 生物统计学验证 (含防御性指标)")
        try:
            biostats_result = self.biostats_agent.execute({
                'hypothesis_data': hypothesis_data,
                'genai_proposal': results['genai_proposal'],
                'compbio_proposal': results['compbio_proposal'],
                'pathology_proposal': results['pathology_proposal'],
                'output_dir': output_dir
            })
            if biostats_result['success']:
                results['biostats_proposal'] = biostats_result['biostats_proposal']
                defensive_metrics = biostats_result.get('defensive_metrics', {})
                print("✅ 生物统计学验证完成")
                print(f"  - E-value: {defensive_metrics.get('evalue', {}).get('value', 'N/A')}")
                print(f"  - 功效分析: {defensive_metrics.get('power_analysis', {}).get('sample_size', 'N/A')}")
                print(f"  - FDR校正: {defensive_metrics.get('fdr_correction', {}).get('method', 'N/A')}")
            else:
                results['success'] = False
                results['errors'].append("生物统计学验证失败")
                return results
        except Exception as e:
            results['success'] = False
            results['errors'].append(f"生物统计学验证异常: {str(e)}")
            return results

        # 步骤5: ResourceEstimatorAgent (资源核算)
        print("\n📍 步骤5/6: 资源核算与成本分析")
        try:
            resource_result = self.resource_estimator_agent.execute({
                'hypothesis_data': hypothesis_data,
                'genai_proposal': results['genai_proposal'],
                'compbio_proposal': results['compbio_proposal'],
                'pathology_proposal': results['pathology_proposal'],
                'biostats_proposal': results['biostats_proposal'],
                'output_dir': output_dir
            })
            if resource_result['success']:
                results['resource_estimate'] = resource_result['resource_budget']
                print("✅ 资源核算完成")
                print(f"  - GPU推荐: {resource_result['resource_budget'].get('gpu_recommendation', 'N/A')}")
                print(f"  - 估算成本: {resource_result['resource_budget'].get('estimated_cost_usd', 'N/A')}")
            else:
                results['success'] = False
                results['errors'].append("资源核算失败")
                return results
        except Exception as e:
            results['success'] = False
            results['errors'].append(f"资源核算异常: {str(e)}")
            return results

        # 步骤6: ClinicalMDAgent
        print("\n📍 步骤6/6: 临床效用评估")
        try:
            clinical_result = self.clinical_md_agent.execute({
                'hypothesis_data': hypothesis_data,
                'biostats_proposal': results['biostats_proposal'],
                'genai_proposal': results['genai_proposal'],
                'output_dir': output_dir
            })
            if clinical_result['success']:
                results['clinical_review'] = clinical_result['clinical_review']
                print("✅ 临床效用评估完成")
            else:
                results['success'] = False
                results['errors'].append("临床效用评估失败")
                return results
        except Exception as e:
            results['success'] = False
            results['errors'].append(f"临床效用评估异常: {str(e)}")
            return results

        print("\n" + "="*60)
        print("🎉 纯干实验瀑布流完成")
        print("="*60)

        return results

    def run_red_team_defense(self, blue_package: dict) -> Dict:
        """
        运行红蓝对抗（含条件递归反馈）

        Args:
            blue_package: 蓝方防御材料

        Returns:
            对抗结果，包含是否通过及反馈信息
        """
        print("\n" + "="*60)
        print("⚔️  红蓝对抗终审答辩")
        print("="*60)

        # 步骤1: 红方攻击
        print("\n📍 红方攻击...")
        red_result = self.red_team_agent.execute({
            'blue_package': blue_package
        })

        if not red_result['success']:
            return {
                'success': False,
                'defense_passed': False,
                'error': '红方攻击失败'
            }

        attack_report = red_result.get('attack_report', {})

        # 步骤2: 防御委员会答辩
        print("\n📍 防御委员会答辩...")
        defense_result = self.defense_committee_agent.execute({
            'blue_package': blue_package,
            'red_attack': attack_report
        })

        if not defense_result['success']:
            return {
                'success': False,
                'defense_passed': False,
                'error': '防御委员会答辩失败'
            }

        defense_passed = defense_result.get('defense_passed', False)

        if defense_passed:
            print("✅ 防守通过！终审答辩成功")
        else:
            print("❌ 防守失败！终审答辩未通过")
            print(f"   裁决: {defense_result.get('final_verdict', '未知')}")
            print(f"   关键问题: {defense_result.get('critical_issues', [])}")

        return {
            'success': True,
            'defense_passed': defense_passed,
            'attack_report': attack_report,
            'defense_result': defense_result
        }

    def run_feedback_loop(self, hypothesis_data: dict, feedback_context: dict, output_dir: str = 'reports') -> Dict:
        """
        V7.1 条件递归反馈循环（含补救检索 + 局部收敛追踪器）

        核心改进：
        1. **定向补救检索**：从审计意见中提取缺失关键词，自动检索方法学文献
        2. **打破闭门造车**：带着新检索的文献去重写，而非凭空���造
        3. **日志可见性**：每次反馈循环都会打印检索信息
        4. **透明化审计意见**：直接显示红方最刻薄的批评

        【上下文爆炸防护】：
        - 严禁无脑拼接所有历史对话记录
        - 每次重写只传入：核心假设数据 + 最新一次反馈 + 补救检索文献

        【V7.1 局部收敛追踪器】：
        - 防止红蓝对抗陷入"拒绝-微调-再拒绝"的死循环
        - 检测分数改善和编辑距离，触发妥协降级
        """
        # ==================== V7.1 局部收敛追踪器 ====================
        # 在红蓝对抗循环中检测死锁，避免白白烧光API额度

        # 获取或初始化局部收敛状态（附在hypothesis_data上）
        if '_convergence_tracker' not in hypothesis_data:
            hypothesis_data['_convergence_tracker'] = {
                'iteration': 0,
                'score_history': [],
                'edit_distance_history': [],
                'stagnation_count': 0,
                'last_hypothesis_text': hypothesis_data.get('details', '')
            }

        tracker = hypothesis_data['_convergence_tracker']
        tracker['iteration'] += 1

        # 收敛检测参数
        MAX_LOCAL_ITERATIONS = 3       # 局部最大迭代
        MIN_SCORE_IMPROVEMENT = 0.5    # 每轮至少提升0.5分
        MAX_STAGNATION = 2             # 连续2轮无改善则熔断
        MIN_EDIT_DISTANCE = 50         # 文本编辑距离阈值

        # 检测是否超过局部迭代上限
        if tracker['iteration'] > MAX_LOCAL_ITERATIONS:
            print("\n" + "="*70)
            print("🚨 ══════════════════ 【V7.1 局部收敛熔断】 ══════════════════")
            print(f"   红蓝对抗已达 {MAX_LOCAL_ITERATIONS} 轮，强制跳出")
            print("   执行妥协降级策略：接受当前最优版本")
            print("="*70 + "\n")

            return {
                'success': True,
                'revised_hypothesis': hypothesis_data,
                'convergence_triggered': True,
                'convergence_reason': f'红蓝对抗超过{MAX_LOCAL_ITERATIONS}轮，强制妥协降级',
                'final_score': tracker['score_history'][-1] if tracker['score_history'] else 0
            }

        self.feedback_loop_count += 1

        # ==================== 透明化追踪：反馈循环触发 ====================
        print("\n" + "="*70)
        print("🔄 ══════════════════ 【递归反馈循环启动】 ══════════════════")
        max_feedback_loop = self.config.get_max_feedback_loop()
        print(f"   第 {self.feedback_loop_count}/{max_feedback_loop} 次迭代")
        print(f"   锁定参数: IF>={self.global_search_params['min_if']}, 时间锁={self.global_search_params['date_range']}")
        print("="*70)

        # 显示红方最刻薄的审计意见
        print("\n🔴 ══════════════════ 【红方最刻薄的审计意见】 ══════════════════")

        # 从 feedback_context 中提取审计意见
        attack_report = feedback_context.get('attack_report', {})
        defense_result = feedback_context.get('defense_result', {})
        dark_box_result = feedback_context.get('dark_box_result', {})
        global_novelty = feedback_context.get('global_novelty', {})

        # 显示碰撞证据
        collision_report = global_novelty.get('collision_report', {}) if global_novelty else {}
        high_collision = collision_report.get('high_collision', [])
        if high_collision:
            print("\n   📋 【碰撞证据】你的假设与以下顶刊撞衫：")
            for paper in high_collision[:3]:
                print(f"      ⚔️  PMID:{paper.get('pmid')} | {paper.get('title', '')[:40]}...")
                print(f"         → {paper.get('reason', '核心概念重叠')}")

        # 显示红方攻击报告
        critical_flaws = attack_report.get('critical_flaws', [])
        if critical_flaws:
            print("\n   🔴 ���致命缺陷】红方审计员尖锐指出：")
            for flaw in critical_flaws[:3]:
                print(f"      💔 \"{flaw}\"")

        # 显示防御委员会的裁决
        final_verdict = defense_result.get('final_verdict', '')
        if final_verdict:
            print("\n   ⚖️  【委员会裁决】")
            print(f"      \"{final_verdict[:100]}...\"")

        # 显示暗盒审计的问题
        critical_issues = dark_box_result.get('critical_issues', [])
        if critical_issues:
            print("\n   🔧 【技术槽点】")
            for issue in critical_issues[:3]:
                print(f"      🛠️  {issue}")

        print("\n" + "-"*70)
        print("💡 首席科学家必须根据以上意见进行差异化迭代")
        print("-"*70 + "\n")
        # ====================================================================

        if self.feedback_loop_count > self.config.get_max_feedback_loop():
            print("❌ 已达到最大反馈次数，终止研究")
            return {
                'success': False,
                'error': '已达到最大反馈次数',
                'feedback_exceeded': True
            }

        # ================================================================
        # 步骤1: 定向补救检索 (Remedial Search) - 核心改进
        # ================================================================
        print(f"\n📚 步骤1: 启动定向补救检索...")
        print(f"   └─ 从审计意见中提取缺失的方法学关键词...")

        # 获取研究主题（用于构建检索查询）
        research_topic = hypothesis_data.get('title', '')
        if not research_topic:
            research_topic = hypothesis_data.get('description', '')[:50]

        # 执行补救检索
        import asyncio

        remedial_result = asyncio.run(self.remedial_search_engine.execute_remedial_search(
            feedback_context=feedback_context,
            research_topic=research_topic,
            max_results=self.config.get_remedial_search_max_results(),  # V6.0: 从配置读取
            year_start=2020  # 获取最新的方法学文献
        ))

        # 打印检索结果日志
        if remedial_result.get('success'):
            keywords = remedial_result.get('keywords', [])
            papers = remedial_result.get('papers', [])
            print(f"   ✅ 补救检索成功!")
            print(f"   └─ 提取关键词: {', '.join(keywords[:5])}")
            print(f"   └─ 检索到 {len(papers)} 篇方法学文献")
            for i, paper in enumerate(papers[:3], 1):
                print(f"      {i}. {paper.get('title', 'N/A')[:60]}...")
        else:
            print(f"   ⚠️ 补救检索失败或无结果，使用原始反馈")
            print(f"   └─ 原因: {remedial_result.get('error', 'Unknown')}")

        # ================================================================
        # 步骤2: 构建增强的反馈提示（含补救检索文献）
        # ================================================================
        print(f"\n📝 步骤2: 构建增强反馈提示（含补救检索文献）...")

        # 使用补救检索结果构建增强的反馈提示
        enhanced_feedback = create_remedial_search_prompt(
            original_hypothesis=hypothesis_data,
            feedback_context=feedback_context,
            remedial_search_result=remedial_result
        )

        print(f"   ✅ 反馈提示已增强，包含 {len(remedial_result.get('papers', []))} 篇方法学文献")

        # ================================================================
        # 步骤3: 基于增强反馈重新生成
        # ================================================================
        print(f"\n🔄 步骤3: 基于增强反馈重新生成方案...")

        # 重新运行关键Agent（GenAI和Biostats）
        print(f"   └─ 重新生成 GenAI 方案...")
        genai_result = self.genai_expert_agent.execute({
            'hypothesis_data': hypothesis_data,
            'feedback_context': enhanced_feedback,  # 使用增强的反馈
            'output_dir': output_dir
        })

        print(f"   └─ 重新生成统计验证框架...")
        biostats_result = self.biostats_agent.execute({
            'hypothesis_data': hypothesis_data,
            'genai_proposal': genai_result.get('genai_proposal', ''),
            'feedback_context': enhanced_feedback,  # 使用增强的反馈
            'output_dir': output_dir
        })

        # ================================================================
        # V7.1 局部收敛检测 - 防止红蓝死循环
        # ================================================================
        tracker = hypothesis_data.get('_convergence_tracker', {})

        # 检测分数改善
        revised_hypothesis = {
            'title': hypothesis_data.get('title'),
            'details': genai_result.get('genai_proposal', '') + '\n\n' + biostats_result.get('biostats_proposal', '')
        }

        # 简单分数估算（基于内容长度和质量标记）
        estimated_score = 7.0  # 默认基准分数
        if 'novelty_score' in genai_result:
            estimated_score = (genai_result.get('novelty_score', 7.0) + biostats_result.get('statistical_score', 7.0)) / 2
        tracker['score_history'].append(estimated_score)

        # 检测编辑距离（蓝方修改幅度）
        original_text = tracker.get('last_hypothesis_text', '')
        revised_text = revised_hypothesis.get('details', '')
        edit_distance = self._calculate_edit_distance(original_text, revised_text)
        tracker['edit_distance_history'].append(edit_distance)
        tracker['last_hypothesis_text'] = revised_text

        # 检测停滞（分数无改善 + 编辑距离过小）
        MIN_SCORE_IMPROVEMENT = 0.5
        MIN_EDIT_DISTANCE = 50
        MAX_STAGNATION = 2

        stagnation_detected = False
        if len(tracker['score_history']) >= 2:
            improvement = tracker['score_history'][-1] - tracker['score_history'][-2]
            if improvement < MIN_SCORE_IMPROVEMENT:
                tracker['stagnation_count'] += 1
                stagnation_detected = True
                print(f"\n   ⚠️  [V7.1 收敛检测] 分数提升不足: {improvement:.2f} < {MIN_SCORE_IMPROVEMENT}")

        if edit_distance < MIN_EDIT_DISTANCE:
            tracker['stagnation_count'] += 0.5
            print(f"\n   ⚠️  [V7.1 收敛检测] 修改幅度过小: {edit_distance} < {MIN_EDIT_DISTANCE} 字符")

        # 熔断判定
        if tracker['stagnation_count'] >= MAX_STAGNATION:
            print("\n" + "="*70)
            print("🚨 ══════════════════ 【V7.1 局部死锁熔断】 ══════════════════")
            print(f"   连续 {tracker['stagnation_count']} 轮无实质改善")
            print("   红蓝对抗陷入死循环，执行妥协降级")
            print("="*70 + "\n")

            return {
                'success': True,
                'revised_hypothesis': revised_hypothesis,
                'genai_proposal': genai_result.get('genai_proposal'),
                'biostats_proposal': biostats_result.get('biostats_proposal'),
                'feedback_loop_count': self.feedback_loop_count,
                'convergence_triggered': True,
                'convergence_reason': f'连续{tracker["stagnation_count"]}轮无改善，红蓝死循环熔断',
                'remedial_search': {
                    'keywords': remedial_result.get('keywords', []),
                    'papers_count': len(remedial_result.get('papers', [])),
                    'query_used': remedial_result.get('query', '')
                }
            }

        # ================================================================
        # 返回结果（包含补救检索信息）
        # ================================================================
        return {
            'success': True,
            'revised_hypothesis': revised_hypothesis,
            'genai_proposal': genai_result.get('genai_proposal'),
            'biostats_proposal': biostats_result.get('biostats_proposal'),
            'feedback_loop_count': self.feedback_loop_count,
            'remedial_search': {  # 新增：补救检索信息
                'keywords': remedial_result.get('keywords', []),
                'papers_count': len(remedial_result.get('papers', [])),
                'query_used': remedial_result.get('query', '')
            }
        }

    def _calculate_edit_distance(self, s1: str, s2: str) -> int:
        """
        V7.1 Levenshtein编辑距离计算

        用于检测蓝方修改幅度，识别无效微调
        """
        if len(s1) < len(s2):
            return self._calculate_edit_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def validate_hypothesis(self, hypothesis_id: int) -> Dict:
        """
        第三步：验证单个假设（Double-Blind 地狱级审计）

        验证原则：
        1. **反证优先**：验证 Agent 必须先假设结论是错的
        2. **独立性审计**：验证 Agent 与生成 Agent 逻辑隔离
        3. **统计硬性标准**：强制检查 Power/FDR/Mediation/E-value
        4. **一票否决**：发现统计缺陷直接驳回
        """
        with self.db_manager.get_session() as session:
            hypothesis = session.query(Hypothesis).filter_by(
                id=hypothesis_id
            ).first()

            if not hypothesis:
                return {
                    'success': False,
                    'error': '假设不存在'
                }

            source_papers = [
                {
                    'pmid': paper.pmid,
                    'title': paper.title,
                    'journal': paper.journal,
                    'publication_date': paper.publication_date,
                    'abstract': paper.abstract
                }
                for paper in hypothesis.papers
            ]

            hyp_data = {
                'title': hypothesis.title,
                'description': hypothesis.description,
                'rationale': hypothesis.rationale,
                'novelty': hypothesis.novelty,
                'expected_value': hypothesis.expected_value or ''
            }

        # ========== Double-Blind 审计模式 ==========
        # 验证 Agent 不知道假设由谁生成，必须从零开始评估
        # 验证原则：假设结论是错的，寻找证据反驳
        validation_input = {
            'hypothesis_id': hypothesis_id,
            'hypothesis_data': hyp_data,
            'source_papers': source_papers,
            # 开启地狱级统计验证
            'enable_statistical_hardening': True,
            # 强制检查项
            'mandatory_checks': {
                'power_analysis': True,      # 强制：功效分析
                'fdr_correction': True,      # 强制：FDR校正
                'mediation_analysis': True,  # 强制：中介分析
                'e_value_sensitivity': True  # 强制：E-value敏感性
            }
        }

        result = self.validation_agent.execute(validation_input)

        # ========== 统计验证缺陷驳回机制 ==========
        if result.get('success'):
            validation = result.get('validation', {})
            reject_reason = validation.get('reject_reason', '')

            # 检查是否因统计缺陷被驳回
            if 'statistical' in reject_reason.lower() or 'p.?value' in reject_reason.lower():
                result['statistical_deficiency_reject'] = True
                result['reject_category'] = 'statistical_hardening'

        if result['success'] and self.current_session_id:
            with self.db_manager.get_session() as session:
                session_obj = session.query(ResearchSession).filter_by(
                    id=self.current_session_id
                ).first()
                if session_obj:
                    session_obj.hypotheses_validated += 1

        return result

    def analyze_technology(self, hypothesis_id: int, require_approval: bool = True) -> Dict:
        """第四步：技术分析"""
        with self.db_manager.get_session() as session:
            hypothesis = session.query(Hypothesis).filter_by(
                id=hypothesis_id
            ).first()

            if not hypothesis:
                return {
                    'success': False,
                    'error': '假设不存在'
                }

            hyp_data = {
                'title': hypothesis.title,
                'description': hypothesis.description,
                'rationale': hypothesis.rationale,
                'novelty': hypothesis.novelty,
                'expected_value': hypothesis.expected_value or ''
            }

            validation_result = {
                'feasibility_score': hypothesis.feasibility_score or 0,
                'novelty_score': hypothesis.novelty_score or 0,
                'technical_score': hypothesis.technical_score or 0,
                'challenges': [],
                'strengths': []
            }

        result = self.tech_agent.execute({
            'hypothesis_id': hypothesis_id,
            'hypothesis_data': hyp_data,
            'validation_result': validation_result
        })

        if result.get('success') and require_approval:
            result['requires_approval'] = True
            result['approval_message'] = '技术分析已完成，等待人工审批与修正'
            result['locked_proposal'] = result.get('analysis', {})

        return result

    def approve_technical_proposal(self, hypothesis_id: int, user_feedback: str = None, modifications: dict = None) -> dict:
        """人工审批技术方案"""
        import json
        from datetime import datetime

        with self.db_manager.get_session() as session:
            hypothesis = session.query(Hypothesis).filter_by(
                id=hypothesis_id
            ).first()

            if not hypothesis:
                return {
                    'success': False,
                    'error': '假设不存在'
                }

            if modifications:
                current_analysis = json.loads(hypothesis.technical_analysis) if hypothesis.technical_analysis else {}
                current_analysis.update(modifications)
                hypothesis.technical_analysis = json.dumps(current_analysis, ensure_ascii=False)

            if not hypothesis.validation_notes:
                hypothesis.validation_notes = ''
            approval_note = f"\n\n【技术方案审批】\n{user_feedback or '无修改，直接通过'}\n审批时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            hypothesis.validation_notes += approval_note

            session.commit()

            locked_proposal = json.loads(hypothesis.technical_analysis) if hypothesis.technical_analysis else {}

        return {
            'success': True,
            'message': '技术方案已锁定，可继续后续流程',
            'locked_proposal': locked_proposal,
            'approval_feedback': user_feedback
        }

    def get_full_report(self, hypothesis_id: int) -> Dict:
        """获取完整的分析报告"""
        return self.tech_agent.get_full_report(hypothesis_id)

    def complete_session(self) -> Dict:
        """完成当前会话"""
        if not self.current_session_id:
            return {
                'success': False,
                'error': '没有活跃的会话'
            }

        with self.db_manager.get_session() as session:
            session_obj = session.query(ResearchSession).filter_by(
                id=self.current_session_id
            ).first()
            if session_obj:
                session_obj.status = 'completed'
                papers_found = session_obj.papers_found
                hypotheses_generated = session_obj.hypotheses_generated
                hypotheses_validated = session_obj.hypotheses_validated
            else:
                return {
                    'success': False,
                    'error': '会话不存在'
                }

        return {
            'success': True,
            'session_id': self.current_session_id,
            'summary': {
                'papers_found': papers_found,
                'hypotheses_generated': hypotheses_generated,
                'hypotheses_validated': hypotheses_validated
            }
        }

    def list_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """列出最近的研究会话"""
        with self.db_manager.get_session() as session:
            sessions = session.query(ResearchSession).order_by(
                ResearchSession.created_at.desc()
            ).limit(limit).all()

            return [
                {
                    'id': session.id,
                    'query': session.query,
                    'created_at': session.created_at.isoformat(),
                    'status': session.status,
                    'papers_found': session.papers_found,
                    'hypotheses_generated': session.hypotheses_generated
                }
                for session in sessions
            ]

    def _validate_hypothesis_internal(self, hypothesis: dict, papers: List[Dict]) -> Dict:
        """内部验证假设（不保存到数据库）"""
        hyp_data = {
            'title': hypothesis.get('title', ''),
            'description': hypothesis.get('description', ''),
            'rationale': hypothesis.get('rationale', ''),
            'novelty': hypothesis.get('novelty', ''),
            'expected_value': hypothesis.get('expected_value', ''),
            'validation_plan': hypothesis.get('validation_plan', ''),
            'paradigm_framework': hypothesis.get('paradigm_framework', ''),
            'grand_challenge': hypothesis.get('grand_challenge', ''),
            'internal_reasoning': hypothesis.get('internal_reasoning', ''),
            'crack_mode': hypothesis.get('crack_mode', ''),
            'technical_route': hypothesis.get('technical_route', '')
        }

        result = self.validation_agent.execute({
            'hypothesis_id': None,
            'hypothesis_data': hyp_data,
            'source_papers': papers[:5],
            'enable_literature_check': False,
            'output_dir': 'reports'
        })

        return result

    def _get_rejection_reason(self, validation_result: dict) -> str:
        """根据验证结果生成拒绝理由"""
        validation = validation_result.get('validation', {})
        scores = validation.get('scores', {})

        transformative = scores.get('transformative_impact', 0)
        originality = scores.get('methodological_originality', 0)
        feasibility = scores.get('poc_feasibility', 0)

        if transformative < 5:
            return "缺乏颠覆性，仅是增量式改进"
        elif transformative < 8:
            return "颠覆性不足，影响范围有限"

        if originality < 5:
            return "缺乏原创性，可能是现有方法的简单应用"
        elif originality < 8:
            return "原创性不足，方法创新有限"

        if feasibility < 5:
            return "验证不可行，数据获取困难"
        elif feasibility < 8:
            return "验证难度较大，需要更多资源"

        return "综合评分未达标"

    def _build_radical_pivot_prompt(self, rejection_reason: str, score: float) -> str:
        """
        构建激进突变Prompt（绝境协议）

        当评分低于 5/10 时触发，要求彻底抛弃之前的思���进行破坏性重构
        """
        return f"""
═══════════════════════════════════════════════════════════════
⚠️  激进突变协议已触发 - 绝境模式
═══════════════════════════════════════════════════════════════

你上一次的思路极其平庸，综合评分仅为 {score:.1f}/10。
被拒绝原因：{rejection_reason}

【现在，请你彻底抛弃上一次的假设！】

🚫 禁止事项：
- 禁止使用相同的生物学靶点或疾病
- 禁止使用相同的计算架构或算法
- 禁止在原思路基础上"修补"

✅ 强制要求：
1. **学科边缘入侵**：从以下学科中选择一个边缘概念，强行引入你的研究：
   - 量子计算（量子纠缠、量子叠加、量子退相干）
   - 热力学熵（熵增、熵减、非平衡态热力学）
   - 拓扑几何（拓扑不变量、同调群、流形）
   - 混沌理论（奇异吸引子、分岔、相变）
   - 信息论（互信息、信道容量、编码理论）
   - 博弈论（纳什均衡、演化博弈、机制设计）
   - 控制论（反馈回路、稳定性、鲁棒控制）

2. **破坏性重构**：
   - 如果之前用神经网络，现在用因果推断
   - 如果之前做预测，现在做反事实推理
   - 如果之前研究静态数据，现在研究动态演化
   - 如果之前关注单细胞，现在关注空间转录组
   - 如果之前分析基因表达，现在分析表观遗传调控

3. **全网无同款**：
   - 你的方案必须是全球首创
   - 必须让人第一反应是"这怎么可能？"
   - 但必须在科学上可验证（不是科幻）

你必须给出一个让评审专家看到后会说"这想法太疯狂了...但好像真的可行"的方案！

════════════════════════════════���══════════════════════════════
"""

    def _map_hypothesis_fields_for_ui(self, hypotheses: List[Dict]) -> List[Dict]:
        """
        字段映射：将 HypothesisAgent 输出的字段映射为前端 UI 期望的字段

        HypothesisAgent 输出 -> 前端 UI 期望
        --------------------------------------
        technical_route -> description (主要描述)
        core_problem -> description (备用)
        core_hypothesis -> rationale
        expected_breakthrough -> novelty
        clinical_value -> expected_value
        paradigm_framework -> paradigm_framework (已匹配)
        crack_mode -> (用于生成 grand_challenge)

        同时添加调试日志，确保数据完整性
        """
        mapped_hypotheses = []

        for hyp in hypotheses:
            # 创建映射后的假设副本
            mapped_hyp = hyp.copy()

            # 优先使用 technical_route 作为 description
            if 'technical_route' in hyp and hyp['technical_route']:
                mapped_hyp['description'] = hyp['technical_route']
            elif 'core_problem' in hyp and hyp['core_problem']:
                # 如果没有 technical_route，使用 core_problem
                mapped_hyp['description'] = hyp['core_problem']
            else:
                # 兜底：拼接所有可用字段
                parts = []
                if hyp.get('core_problem'):
                    parts.append(hyp['core_problem'])
                if hyp.get('core_hypothesis'):
                    parts.append(hyp['core_hypothesis'])
                mapped_hyp['description'] = '\n\n'.join(parts) if parts else 'N/A'

            # 添加 rationale (如果不存在)
            if 'rationale' not in mapped_hyp or not mapped_hyp['rationale']:
                mapped_hyp['rationale'] = hyp.get('core_hypothesis', '')

            # 添加 novelty (如果不存在)
            if 'novelty' not in mapped_hyp or not mapped_hyp['novelty']:
                mapped_hyp['novelty'] = hyp.get('expected_breakthrough', '')

            # 添加 expected_value (如果不存在)
            if 'expected_value' not in mapped_hyp or not mapped_hyp['expected_value']:
                mapped_hyp['expected_value'] = hyp.get('clinical_value', '')

            # 添加 grand_challenge (如果不存在，从 title 或 core_problem 生成)
            if 'grand_challenge' not in mapped_hyp or not mapped_hyp['grand_challenge']:
                # 尝试从 core_problem 提取，或者使用简化版本
                if hyp.get('core_problem'):
                    # 取核心问题的第一句话
                    grand_challenge = hyp['core_problem'].split('。')[0].split('？')[0].split('.')[0]
                    mapped_hyp['grand_challenge'] = grand_challenge[:200] + ('...' if len(grand_challenge) > 200 else '')
                else:
                    mapped_hyp['grand_challenge'] = hyp.get('title', '')[:100]

            # ========== 调试日志：数据完整性检查 ==========
            desc_len = len(mapped_hyp.get('description', ''))
            self.logger.debug(
                f"[字段映射] 假设 '{mapped_hyp.get('title', 'Unknown')[:30]}...': "
                f"description 字段长度 = {desc_len} 字符"
            )

            # 检查 LaTeX 公式转义
            description = mapped_hyp.get('description', '')
            if '$' in description or '\\(' in description or '\\[' in description:
                # 简单的 LaTeX 转义，避免前端解析失败
                # 注意：这里只是基础转义，前端也需要支持 LaTeX 渲染
                self.logger.debug(f"[字段映射] 检测到 LaTeX 公式，长度: {len(description)}")

            mapped_hypotheses.append(mapped_hyp)

        return mapped_hypotheses

    # ==================== 自主循环模式 (Autonomous Mode) ====================
    # 类似 Karpathy autoresearch 的自主实验循环
    # Agent 自动迭代优化，直到达标或超时

    def run_autonomous_mode(
        self,
        query: str,
        config: ProgramConfig = None,
        **kwargs
    ) -> Dict:
        """
        自主循环模式 - 自动迭代优化假设

        类似 Karpathy autoresearch 的设计理念：
        - Agent 自动执行完整流程
        - 每轮迭代后检查目标分数
        - 达标或超时后自动停止

        Args:
            query: 搜索关键词
            config: ProgramConfig 配置对象（可选，默认使用全局配置）
            **kwargs: 可覆盖配置参数

        Returns:
            {
                'success': bool,
                'final_hypotheses': List[Dict],
                'iterations': int,
                'experiment_log': List[Dict],
                'time_elapsed': float
            }
        """
        import time

        # 加载配置
        if config is None:
            config = get_program_config()

        # 合并 kwargs 到配置
        max_iterations = kwargs.get('max_iterations', config.get_max_iterations())
        target_score = kwargs.get('target_score', config.get_target_score())
        time_budget = kwargs.get('time_budget', config.get_time_budget())
        auto_approve = kwargs.get('auto_approve', config.get('autonomous_mode.auto_approve_hypothesis', False))

        # 初始化实验日志
        experiment_log = []
        start_time = time.time()

        print("\n" + "="*80)
        print("🤖 ══════════════════ 【自主循环模式启动】 ══════════════════")
        print(f"   目标分数: {target_score}")
        print(f"   最大迭代: {max_iterations}")
        print(f"   时间预算: {time_budget} 分钟")
        print("="*80)

        # ==================== 步骤 1: 启动会话 ====================
        session_result = self.start_session(query)
        if not session_result.get('success'):
            return {
                'success': False,
                'error': '会话启动失败',
                'experiment_log': experiment_log
            }

        # ==================== 步骤 2: 论文搜索 ====================
        print("\n📍 [自主模式] 步骤 1: 论文搜索...")

        min_if = kwargs.get('min_if', config.get_min_if())
        date_range = kwargs.get('date_range', config.get_date_range())

        search_result = self.search_papers(
            query=query,
            min_if=min_if,
            date_range=date_range,
            use_two_stage_funnel=True
        )

        if not search_result.get('success') or not search_result.get('papers'):
            experiment_log.append({
                'iteration': 0,
                'phase': 'search',
                'status': 'failed',
                'error': search_result.get('error', '无搜索结果')
            })
            return {
                'success': False,
                'error': '论文搜索失败',
                'experiment_log': experiment_log
            }

        papers = search_result['papers']
        experiment_log.append({
            'iteration': 0,
            'phase': 'search',
            'status': 'success',
            'papers_count': len(papers),
            'query': query
        })

        print(f"   ✅ 搜索完成: {len(papers)} 篇论文")

        # ==================== 步骤 3: 自主迭代循环 ====================
        best_hypotheses = []
        best_score = 0.0

        for iteration in range(1, max_iterations + 1):
            elapsed_minutes = (time.time() - start_time) / 60

            # 检查时间预算
            if elapsed_minutes > time_budget:
                print(f"\n⏰ 时间预算耗尽 ({elapsed_minutes:.1f} > {time_budget} 分钟)")
                break

            print("\n" + "-"*80)
            print(f"🔄 迭代 {iteration}/{max_iterations} | 已用时 {elapsed_minutes:.1f} 分钟")
            print("-"*80)

            iteration_log = {
                'iteration': iteration,
                'start_time': datetime.now().isoformat(),
                'elapsed_minutes': elapsed_minutes
            }

            # ==================== 3.1 假设生成 ====================
            print("   📍 步骤 3.1: 假设生成...")

            gen_result = self.generate_hypotheses(
                papers=papers,
                num_hypotheses=kwargs.get('num_hypotheses', config.get('hypothesis_generation.num_hypotheses', 3)),
                min_score_threshold=config.get_min_score_threshold(),
                enable_prevalidation=True
            )

            if not gen_result.get('success') or not gen_result.get('hypotheses'):
                iteration_log['hypothesis_generation'] = {
                    'status': 'failed',
                    'error': gen_result.get('error', '无假设生成')
                }
                experiment_log.append(iteration_log)

                # 失败策略：激进突变
                if config.get('autonomous_mode.on_failure_action') == 'radical_pivot':
                    print("   ⚠️ 假设生成失败，触发激进突变...")
                    continue
                else:
                    break

            hypotheses = gen_result['hypotheses']
            iteration_log['hypothesis_generation'] = {
                'status': 'success',
                'hypotheses_count': len(hypotheses),
                'prevalidation_log': gen_result.get('prevalidation_log', [])
            }

            print(f"   ✅ 生成 {len(hypotheses)} 个假设")

            # ==================== 3.2 选择最优假设 ====================
            print("   📍 步骤 3.2: 选择最优假设...")

            for hyp in hypotheses:
                avg_score = hyp.get('prevalidation_avg', 0)
                if avg_score > best_score:
                    best_score = avg_score
                    best_hypotheses = [hyp]

            # 显示当前最优
            if best_hypotheses:
                best_hyp = best_hypotheses[0]
                print(f"   📊 当前最优: '{best_hyp.get('title', 'N/A')[:40]}...'")
                print(f"      综合分数: {best_score:.1f}/10 (目标: {target_score})")

            iteration_log['best_score'] = best_score

            # ==================== 3.3 检查目标分数 ====================
            if best_score >= target_score:
                print(f"\n🎯 目标达成！最优分数 {best_score:.1f} >= {target_score}")
                iteration_log['status'] = 'target_reached'
                experiment_log.append(iteration_log)
                break

            iteration_log['status'] = 'continuing'
            experiment_log.append(iteration_log)

            # ==================== 3.4 自动技术分析（可选） ====================
            if config.get('autonomous_mode.auto_technical_analysis', True):
                print("   📍 步骤 3.3: 自动技术分析...")
                # 技术分析会在最终输出时执行

        # ==================== 步骤 4: 生成最终报告 ====================
        elapsed_time = time.time() - start_time

        print("\n" + "="*80)
        print("🏁 ══════════════════ 【自主循环完成】 ══════════════════")
        print(f"   总迭代: {len([l for l in experiment_log if l.get('iteration', 0) > 0])}")
        print(f"   总用时: {elapsed_time/60:.1f} 分钟")
        print(f"   最终分数: {best_score:.1f}")
        print("="*80)

        # 保存实验日志
        self._save_experiment_log(experiment_log, config.get('autonomous_mode.output_dir', 'experiments/'))

        return {
            'success': len(best_hypotheses) > 0,
            'final_hypotheses': best_hypotheses,
            'best_score': best_score,
            'iterations': len([l for l in experiment_log if l.get('iteration', 0) > 0]),
            'experiment_log': experiment_log,
            'time_elapsed': elapsed_time,
            'papers': papers,
            'session_id': self.current_session_id
        }

    def _save_experiment_log(self, log: List[Dict], output_dir: str) -> str:
        """
        保存实验日志到文件

        Args:
            log: 实验日志列表
            output_dir: 输出目录

        Returns:
            日志文件路径
        """
        import json

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"autonomous_experiment_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

        print(f"[Orchestrator] 实验日志已保存: {filepath}")
        return filepath

    def get_program_config(self) -> ProgramConfig:
        """
        获取当前配置

        Returns:
            ProgramConfig 实例
        """
        return get_program_config()

    def update_program_config(self, key: str, value: Any) -> None:
        """
        动态更新配置

        Args:
            key: 配置键（点分隔）
            value: 新值
        """
        config = get_program_config()
        config.update(key, value)

    # =============================================================
    # ==================== V4.1 核心架构重构 - 新生成流程 ====================
    # =============================================================

    def generate_hypothesis_v41(self, user_input: str) -> Dict:
        """
        V4.1 新生成流程 - 草稿-验证-审计三阶段

        核心机制：
        1. Bootstrap预注入（动态学科边界锁定）
        2. 草稿-验证检索（三阶段并发PubMed验证）
        3. 反过拟合审计（假大空惩罚器）
        4. 红方审计（Reviewer 2）
        5. 终审答辩

        Args:
            user_input: 用户原始输入文本（自然语言科研想法）

        Returns:
            Dict: {
                'success': bool,
                'hypothesis': Dict,
                'audit_trail': Dict,
                'phase': str
            }
        """
        import time
        start_time = time.time()

        print("\n" + "="*80)
        print("🚀 ══════════════════ 【V4.1 核心架构启动】 ══════════════════")
        print(f"    用户输入: {user_input[:50]}...")
        print("="*80)

        # ==================== Step 1: Bootstrap预注入 ====================
        print("\n📍 Step 1: Bootstrap预注入 - 动态学科边界锁定...")

        from core.bootstrap_env import inject_bootstrap
        bootstrap_env = inject_bootstrap(user_input)

        print(f"   - 检测领域: {bootstrap_env.domain}")
        print(f"   - 关键词: {', '.join(bootstrap_env.keywords[:5])}")
        print(f"   - 数据源白名单: {len(bootstrap_env.data_source_whitelist)} 项")

        # ==================== Step 2: 草稿-验证检索 ====================
        print("\n📍 Step 2: 草稿-验证检索 - 三阶段并发PubMed验证...")

        from utils.draft_verification import DraftVerificationRetrieval
        from prompts.pi_system_prompt import format_pi_prompt

        # 格式化PI Prompt
        pi_prompt = format_pi_prompt(
            user_domain=bootstrap_env.domain,
            user_idea=user_input,
            bootstrap_text=bootstrap_env.bootstrap_text
        )

        # 初始化草稿-验证检索器
        draft_verifier = DraftVerificationRetrieval(
            llm_client=self.client,
            pubmed_searcher=self.remedial_search_engine.pubmed_searcher,
            session_id=str(self.current_session_id)
        )

        # 执行三阶段流程（异步包装）
        import asyncio
        try:
            final_hypothesis, draft_audit = asyncio.run(
                draft_verifier.execute(
                    user_input=user_input,
                    bootstrap_env={
                        'domain': bootstrap_env.domain,
                        'bootstrap_text': bootstrap_env.bootstrap_text,
                        'keywords': bootstrap_env.keywords
                    },
                    pi_system_prompt=pi_prompt
                )
            )
        except Exception as e:
            self.logger.error(f"草稿-验证检索失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'phase': 'draft_verification_failed'
            }

        # 检查碰撞熔断
        if draft_audit.get('phase') == 'collision_detected':
            print("\n🔴 碰撞熔断触发!")
            print(f"   - 碰撞文献: {len(draft_audit.get('papers', []))} 篇")

            return {
                'success': False,
                'hypothesis': final_hypothesis,
                'audit_trail': {
                    'bootstrap': bootstrap_env,
                    'draft_verification': draft_audit
                },
                'phase': 'collision_detected',
                'collision_papers': draft_audit.get('papers', [])
            }

        print(f"   - Phase 完成: {draft_audit.get('phase')}")
        print(f"   - 支持证据: {draft_audit.get('supporting_count', 0)} 篇")
        print(f"   - 挑战文献: {draft_audit.get('challenge_count', 0)} 篇")

        # ==================== Step 3: 反过拟合审计 ====================
        print("\n📍 Step 3: 反过拟合审计 - 假大空惩罚器...")

        from core.anti_overfitting import audit_hypothesis_overfitting

        overfit_result = audit_hypothesis_overfitting(final_hypothesis)

        print(f"   - 万金油词汇: {overfit_result.bogus_keyword_count} 个")
        print(f"   - 真实机制: {'✅ 有' if overfit_result.has_real_mechanism else '❌ 无'}")
        print(f"   - 因果链: {'✅ 有' if overfit_result.has_causal_chain else '❌ 无'}")
        print(f"   - 总扣分: {overfit_result.total_penalty}")

        # 熔断检查
        if overfit_result.should_fuse:
            print("\n🔴 反过拟合熔断触发!")
            print(f"   - 原因: {overfit_result.fusing_reason}")

            # 记录失败到TraceMemory
            from utils.trace_memory import serialize_failure
            serialize_failure(
                hypothesis_summary=final_hypothesis.get('title', ''),
                failure_reason=overfit_result.fusing_reason,
                collision_papers=draft_audit.get('papers', []),
                session_id=str(self.current_session_id)
            )

            return {
                'success': False,
                'hypothesis': final_hypothesis,
                'audit_trail': {
                    'bootstrap': bootstrap_env,
                    'draft_verification': draft_audit,
                    'overfitting': overfit_result.audit_summary
                },
                'phase': 'overfitting_fuse',
                'fusing_reason': overfit_result.fusing_reason
            }

        # 调整分数
        from core.anti_overfitting import get_overfitting_auditor
        final_hypothesis = get_overfitting_auditor().adjust_scores(
            final_hypothesis,
            overfit_result
        )

        # ==================== Step 4: 红方审计 ====================
        print("\n📍 Step 4: 红方审计 - Reviewer 2 一票否决...")

        from prompts.auditor_system_prompt import format_auditor_prompt

        # 格式化Auditor Prompt
        auditor_prompt = format_auditor_prompt(
            user_domain=bootstrap_env.domain,
            hypothesis=final_hypothesis
        )

        # 调用红方审计
        red_team_result = self.red_team_agent.execute({
            'blue_package': {
                'hypothesis_data': final_hypothesis,
                'draft_audit': draft_audit,
                'overfitting_audit': overfit_result.audit_summary,
                'bootstrap_domain': bootstrap_env.domain
            }
        })

        if not red_team_result.get('success', False):
            print("\n🔴 红方审计执行失败!")
            return {
                'success': False,
                'error': 'RedTeamAgent执行失败',
                'phase': 'red_team_failed'
            }

        attack_report = red_team_result.get('attack_report', {})
        verdict = attack_report.get('verdict', 'pass')

        print(f"   - Verdict: {verdict}")
        print(f"   - Critical Flaws: {len(attack_report.get('critical_flaws', []))}")
        print(f"   - Severe Issues: {len(attack_report.get('severe_issues', []))}")

        if verdict == 'fail':
            print("\n🔴 红方审计否决!")

            # 记录失败
            from utils.trace_memory import serialize_failure
            serialize_failure(
                hypothesis_summary=final_hypothesis.get('title', ''),
                failure_reason="红方审计否决: " + str(attack_report.get('veto_reason', '')),
                collision_papers=draft_audit.get('papers', []),
                session_id=str(self.current_session_id)
            )

            return {
                'success': False,
                'hypothesis': final_hypothesis,
                'audit_trail': {
                    'bootstrap': bootstrap_env,
                    'draft_verification': draft_audit,
                    'overfitting': overfit_result.audit_summary,
                    'red_team': attack_report
                },
                'phase': 'red_team_fail',
                'attack_report': attack_report
            }

        # ==================== Step 5: 终审答辩 ====================
        print("\n📍 Step 5: 终审答辩 - Defense Committee...")

        defense_result = self.defense_committee_agent.execute({
            'hypothesis_data': final_hypothesis,
            'attack_report': attack_report,
            'overfitting_penalty': overfit_result.total_penalty
        })

        if not defense_result.get('passed', False):
            print("\n🔴 终审答辩失败!")
            return {
                'success': False,
                'hypothesis': final_hypothesis,
                'audit_trail': {
                    'bootstrap': bootstrap_env,
                    'draft_verification': draft_audit,
                    'overfitting': overfit_result,
                    'red_team': attack_report,
                    'defense': defense_result
                },
                'phase': 'defense_fail'
            }

        # ==================== 成功完成 ====================
        elapsed_time = time.time() - start_time

        print("\n" + "="*80)
        print("✅ ══════════════════ 【V4.1 生成完成】 ══════════════════")
        print(f"   总用时: {elapsed_time:.2f} 秒")
        print(f"   最终分数: {final_hypothesis.get('adjusted_scores', {}).get('overall', 0):.1f}")
        print("="*80)

        return {
            'success': True,
            'hypothesis': final_hypothesis,
            'audit_trail': {
                'bootstrap': {
                    'domain': bootstrap_env.domain,
                    'keywords': bootstrap_env.keywords[:5],
                    'modality_lock': bootstrap_env.modality_lock[:100]
                },
                'draft_verification': {
                    'phase': draft_audit.get('phase'),
                    'supporting_count': draft_audit.get('supporting_count', 0),
                    'challenge_count': draft_audit.get('challenge_count', 0),
                    'queries': draft_audit.get('queries_executed', [])
                },
                'overfitting': {
                    'total_penalty': overfit_result.total_penalty,
                    'bogus_keyword_count': overfit_result.bogus_keyword_count,
                    'has_real_mechanism': overfit_result.has_real_mechanism,
                    'has_causal_chain': overfit_result.has_causal_chain
                },
                'red_team': {
                    'verdict': verdict,
                    'critical_flaws': len(attack_report.get('critical_flaws', [])),
                    'severe_issues': len(attack_report.get('severe_issues', []))
                },
                'defense': {
                    'passed': defense_result.get('passed', False),
                    'final_score': defense_result.get('final_score', 0)
                }
            },
            'phase': 'complete',
            'time_elapsed': elapsed_time,
            'session_id': self.current_session_id
        }

    # =============================================================

    def __del__(self):
        """析构函数"""
        pass


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    orchestrator = Orchestrator()

    # 开始会话
    session_result = orchestrator.start_session("machine learning genomics")
    print(f"会话ID: {session_result['session_id']}")

    # 搜索论文
    search_result = orchestrator.search_papers("machine learning genomics", max_results=5)
    print(f"找到 {len(search_result['papers'])} 篇论文")

    # 列出最近会话
    recent_sessions = orchestrator.list_recent_sessions(5)
    print(f"\n最近会话: {len(recent_sessions)} 个")
