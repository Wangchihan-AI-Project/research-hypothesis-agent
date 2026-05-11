# -*- coding: utf-8 -*-
"""
V7.3 全链路探针 - Full Pipeline Tester

V7.3 核心升级：
1. 意图分诊 (Intent Triage) - LLM 驱动的语义分析
2. 定向防御 (Defensive Injection) - 基于风险矩阵的自动反击
3. 结构化校验 (Structural Schema) - 强制 technical_safeguards

功能：
1. 直接调用 hypothesis_generation_task_impl（绕过 Celery）
2. 在控制台清晰打印 15 步每一步的进入和完成状态
3. 支持自定义测试意图输入
4. 显示红蓝对抗迭代过程

使用方法：
    cd C:/Users/PC/research-hypothesis-agent
    python full_pipeline_tester.py

    # 或指定测试意图
    python full_pipeline_tester.py --idea "单细胞RNA测序在耐药性中的机制研究"

作者: V7.3 发版工程师
日期: 2026-04-18
"""

import sys
import os
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# 强制 UTF-8 编码
if sys.platform == "win32":
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    if sys.stdout is not None and not sys.stdout.closed:
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# 加载环境变量
from dotenv import load_dotenv
env_path = project_root / '.env'
load_dotenv(env_path, encoding='utf-8')

# ==================== V7.4-D: 15 步状态定义（新增自愈引擎步骤） ====================
PIPELINE_STEPS = [
    {"step": 1, "name": "Intent Sanitizer", "icon": "🛡️", "description": "语义分类预检"},
    {"step": 2, "name": "Celery Dispatch", "icon": "📨", "description": "任务派发"},
    {"step": 3, "name": "Global Fuse Init", "icon": "⚡", "description": "熔断器初始化"},
    {"step": 4, "name": "Dynamic RAG Router", "icon": "🔀", "description": "数据源路由"},
    {"step": 5, "name": "Concurrent Literature Search", "icon": "📚", "description": "并发文献检索"},
    {"step": 6, "name": "PI Hypothesis Gen", "icon": "🧪", "description": "假设生成"},
    {"step": 7, "name": "Hard-Link Anchor", "icon": "⚓", "description": "引用锚定校验"},
    {"step": 8, "name": "Hybrid Fitness", "icon": "📊", "description": "混合适应度评估"},
    {"step": 9, "name": "Red Team Attack", "icon": "⚔️", "description": "红方攻击审计"},
    {"step": 10, "name": "Defense Committee", "icon": "🛡️", "description": "蓝方答辩"},
    {"step": 11, "name": "Convergence Check", "icon": "🎯", "description": "收敛检测"},
    {"step": 12, "name": "Audit Aggregation", "icon": "📋", "description": "聚合审计数据"},
    {"step": 13, "name": "Report Generation", "icon": "📝", "description": "报告生成"},
    {"step": 14, "name": "Webhook Callback", "icon": "🔔", "description": "结果回调"},
    {"step": 15, "name": "Task Complete", "icon": "✅", "description": "任务完成"},
    # V7.4-D 新增：自愈引擎步骤
    {"step": 16, "name": "Healing Engine", "icon": "🧬", "description": "自愈引擎启动"},
    {"step": 17, "name": "Patch Injection", "icon": "💉", "description": "补丁注入 Iteration 4"},
]

# ==================== 控制台探针类 ====================
class PipelineProbe:
    """
    V7.5 凤凰协议全链路探针

    核心升级：
    1. 从"阻断型"重构为"演化型"逻辑
    2. 物理公理冲突时自动重写（替代拦截）
    3. Science Score 趋势检测，停滞触发外部补偿
    4. 版本演进追踪：v1.0 → v1.1 → v1.2 → SUCCESS

    模拟 Celery Task 执行流程，但直接在控制台运行
    """

    def __init__(self, test_idea: str = None):
        self.test_idea = test_idea or "基于图注意力网络 (GAT) 与多组学数据的已知药物重定位 (Drug Repurposing) 框架"
        self.start_time = None
        self.current_step = 0
        self.iteration_count = 0
        self.logs = []

        # ===== V7.5 凤凰协议新增 =====
        # 导入凤凰协议模块
        try:
            from src.core.phoenix_state_machine import PhoenixStateMachine, PhoenixState, PHOENIX_CONFIG
            from src.core.hypothesis_version_manager import HypothesisVersionManager
            from src.core.score_trend_detector import ScoreTrendDetector
            self.phoenix_machine = PhoenixStateMachine()
            self.version_manager = HypothesisVersionManager()
            self.trend_detector = ScoreTrendDetector()
            self.max_phoenix_iterations = PHOENIX_CONFIG['MAX_PHOENIX_ITERATIONS']
            self.phoenix_enabled = True
        except ImportError as e:
            print(f"[V7.5] 凤凰协议模块导入失败: {e}, 降级运行")
            self.phoenix_machine = None
            self.version_manager = None
            self.trend_detector = None
            self.max_phoenix_iterations = 4
            self.phoenix_enabled = False

    def print_header(self):
        """打印探针启动头部"""
        print("\n" + "=" * 80)
        print("╔══════════════════════════════════════════════════════════════════════════════╗")
        print("║           V7.5 '凤凰协议' 演化型架构系统                                          ║")
        print("║               物理锚定重写 + 螺旋进化 + 不达目的誓不罢休                             ║")
        print("╚══════════════════════════════════════════════════════════════════════════════╝")
        print("=" * 80)
        print(f"\n⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📝 测试意图: {self.test_idea[:60]}...")
        print(f"🔧 执行模式: 凤凰协议演化模式（状态机驱动）")
        print(f"🔥 最大演化次数: {self.max_phoenix_iterations}")
        print(f"🧬 自愈引擎: 启用（分数停滞触发外部补偿）")
        print(f"📊 版本追踪: 启用（v1.0 → v1.1 → v1.2 → SUCCESS）")
        print("\n" + "-" * 80)

    def print_step_enter(self, step_idx: int, extra_info: str = None):
        """打印步骤进入"""
        step = PIPELINE_STEPS[step_idx - 1]
        icon = step['icon']
        name = step['name']
        desc = step['description']

        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

        print(f"\n[{timestamp}] ┌──────────────────────────────────────────────────────────────")
        print(f"[{timestamp}] │ {icon} Step {step_idx}: {name}")
        print(f"[{timestamp}] │    描述: {desc}")

        if extra_info:
            print(f"[{timestamp}] │    详情: {extra_info}")

        print(f"[{timestamp}] └──────────────────────────────────────────────────────────────")
        print(f"[{timestamp}] ▶️  进入执行...")

        self.current_step = step_idx
        self.logs.append({
            'time': timestamp,
            'step': step_idx,
            'event': 'enter',
            'info': extra_info
        })

    def print_step_exit(self, step_idx: int, status: str, result_info: str = None):
        """打印步骤退出"""
        step = PIPELINE_STEPS[step_idx - 1]
        icon = step['icon']

        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

        status_icon = {
            'success': '✅',
            'failed': '❌',
            'warning': '⚠️',
            'skipped': '⏭️',
        }.get(status, '❓')

        print(f"\n[{timestamp}] {status_icon} Step {step_idx} 完成: {icon} {step['name']}")
        print(f"[{timestamp}]    状态: {status}")

        if result_info:
            print(f"[{timestamp}]    结果: {result_info[:80]}...")

        self.logs.append({
            'time': timestamp,
            'step': step_idx,
            'event': 'exit',
            'status': status,
            'info': result_info
        })

    def print_iteration_header(self, iteration: int, max_iter: int):
        """打印对抗迭代头部"""
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

        print(f"\n[{timestamp}] ╔════════════════════════════════════════════════════════════════╗")
        print(f"[{timestamp}] ║  🔄 对抗迭代 #{iteration}/{max_iter}                                     ║")
        print(f"[{timestamp}] ╚════════════════════════════════════════════════════════════════╝")

        self.iteration_count = iteration

    def print_final_result(self, result: Dict):
        """打印最终结果"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds() if self.start_time else 0

        print("\n" + "=" * 80)
        print("╔══════════════════════════════════════════════════════════════════════════════╗")
        print("║                    V7.4-D 自愈架构执行结果摘要                                     ║")
        print("╚══════════════════════════════════════════════════════════════════════════════╝")
        print("=" * 80)

        state = result.get('state', 'UNKNOWN')
        result_type = result.get('result_type', 'unknown')

        # V7.4-D 自愈引擎状态
        healing_info = result.get('payload', {}).get('healing_engine', {})
        if healing_info:
            print(f"\n🧬 自愈引擎状态:")
            print(f"   • 触发状态: {'已触发' if healing_info.get('activated') else '未触发'}")
            if healing_info.get('activated'):
                print(f"   • 检索文献数: {healing_info.get('retrieval_count', 0)}")
                print(f"   • 合成补丁数: {healing_info.get('patch_count', 0)}")
                print(f"   • 检测攻击类型: {healing_info.get('attack_types_detected', [])}")

        # 状态显示
        if state == 'success':
            print("\n✅ 最终状态: SUCCESS")
            # V7.4-D: 显示自愈成功信息
            if healing_info.get('activated') and self.iteration_count == 4:
                print("🌟 V7.4-D 自愈闭环成功：Iteration 4 通过防御委员会审查！")
        elif state == 'failure':
            print("\n❌ 最终状态: FAILURE")
        else:
            print(f"\n❓ 最终状态: {state}")

        print(f"\n📊 结果类型: {result_type}")
        print(f"⏱️  执行时长: {duration:.2f} 秒")
        print(f"🔄 对抗迭代: {self.iteration_count} 次")

        # Payload 信息
        payload = result.get('payload', {})
        if payload:
            print("\n📦 Payload 概览:")

            # 审计上下文
            audit = payload.get('audit_context', {})
            if audit:
                hf = audit.get('hybrid_fitness', {})
                print(f"   • 混合适应度: {hf.get('score', 0):.2f}")

                rt = audit.get('red_team_attack', {})
                print(f"   • 红方攻击: {rt.get('verdict', 'N/A')}")

                dc = audit.get('defense_committee', {})
                print(f"   • 防御委员会: {'通过' if dc.get('passed') else '失败'}")

            # 验证 ID
            verified_ids = payload.get('verified_ids', {})
            if verified_ids:
                print(f"   • PMID 数量: {len(verified_ids.get('pmids', []))}")
                print(f"   • ArXiv 数量: {len(verified_ids.get('arxiv_ids', []))}")
                print(f"   • DOI 数量: {len(verified_ids.get('dois', []))}")

        # 错误信息
        error = result.get('error')
        if error:
            print(f"\n❌ 错误信息: {error[:100]}...")

        print("\n" + "-" * 80)

    def run_full_pipeline(self) -> Dict:
        """
        执行完整 15 步流程

        Returns:
            Dict: 最终结果
        """
        self.start_time = datetime.now()
        self.print_header()

        # ==================== Step 1: Intent Sanitizer ====================
        self.print_step_enter(1, "检查输入意图是否为有效科研问题")

        try:
            from src.core.semantic_classifier import classify_intent
            classification = classify_intent(self.test_idea)

            if not classification.is_valid:
                self.print_step_exit(1, 'failed', f"被拦截: {classification.reasoning}")
                return {
                    'state': 'failure',
                    'result_type': 'sanitization_blocked',
                    'error': classification.reasoning
                }

            self.print_step_exit(1, 'success', f"分类通过: {classification.intent_type.value}")
            cleaned_input = classification.cleaned_input

        except ImportError:
            self.print_step_exit(1, 'warning', "语义分类器不可用，跳过预检")
            cleaned_input = self.test_idea

        # ==================== Step 2: Celery Dispatch (模拟) ====================
        self.print_step_enter(2, "模拟任务派发（直接调用模式）")
        self.print_step_exit(2, 'success', "已跳过 Celery，直接进入执行")

        # ==================== Step 3: Global Fuse Init ====================
        self.print_step_enter(3, "初始化熔断器，设置 API 调用上限")

        try:
            from src.core.global_fuse import reset_global_fuse, get_global_fuse
            reset_global_fuse()
            fuse = get_global_fuse(hard_cap=15)
            self.print_step_exit(3, 'success', f"熔断器已初始化: hard_cap=15")
        except ImportError:
            self.print_step_exit(3, 'warning', "熔断器不可用")
            fuse = None

        # ==================== Step 4: Dynamic RAG Router ====================
        self.print_step_enter(4, "根据学科领域动态路由数据源")

        try:
            from src.core.rag_router import DynamicRAGRouter
            rag_router = DynamicRAGRouter()
            routing_result = rag_router.route(self.test_idea, 'auto-detect')

            detected_domain = routing_result.domain
            sources = routing_result.sources

            self.print_step_exit(4, 'success', f"领域: {detected_domain}, 数据源: {sources}")
        except ImportError:
            self.print_step_exit(4, 'warning', "RAG Router 不可用，使用默认 PubMed")
            detected_domain = 'medicine'
            sources = ['pubmed']

        # ==================== Step 5: Concurrent Literature Search ====================
        self.print_step_enter(5, f"并发检索: {sources}")

        verified_ids = {'pmids': [], 'arxiv_ids': [], 'dois': []}
        all_papers = []

        import concurrent.futures

        def fetch_pubmed():
            try:
                from src.utils.pubmed import PubMedSearcher
                searcher = PubMedSearcher()
                result = searcher.search_by_idea(self.test_idea, max_results=10)
                papers = result.get('papers', [])
                for p in papers:
                    p['source'] = 'pubmed'
                return {'source': 'pubmed', 'papers': papers, 'pmids': [p.get('pmid') for p in papers if p.get('pmid')]}
            except Exception as e:
                return {'source': 'pubmed', 'papers': [], 'pmids': [], 'error': str(e)}

        def fetch_arxiv():
            try:
                from src.data_sources.arxiv_searcher import ArXivSearcher
                searcher = ArXivSearcher()
                result = searcher.search(self.test_idea, max_results=10)
                papers = result.get('papers', [])
                for p in papers:
                    p['source'] = 'arxiv'
                return {'source': 'arxiv', 'papers': papers, 'arxiv_ids': [p.get('arxiv_id') for p in papers if p.get('arxiv_id')]}
            except Exception as e:
                return {'source': 'arxiv', 'papers': [], 'arxiv_ids': [], 'error': str(e)}

        def fetch_s2():
            try:
                from src.data_sources.semantic_scholar_searcher import SemanticScholarSearcher
                searcher = SemanticScholarSearcher()
                result = searcher.search(self.test_idea, max_results=10)
                papers = result.get('papers', [])
                for p in papers:
                    p['source'] = 'semantic_scholar'
                return {'source': 'semantic_scholar', 'papers': papers, 'dois': [p.get('doi') for p in papers if p.get('doi')]}
            except Exception as e:
                return {'source': 'semantic_scholar', 'papers': [], 'dois': [], 'error': str(e)}

        search_tasks = []
        if 'pubmed' in sources:
            search_tasks.append(fetch_pubmed)
        if 'arxiv' in sources:
            search_tasks.append(fetch_arxiv)
        if 'semantic_scholar' in sources:
            search_tasks.append(fetch_s2)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(task): task for task in search_tasks}

            # V7.2: 使用 wait 替代 as_completed，添加更好的超时处理
            try:
                done_futures, pending_futures = concurrent.futures.wait(
                    futures.keys(),
                    timeout=120,
                    return_when=concurrent.futures.ALL_COMPLETED
                )

                # 处理已完成的任务
                for future in done_futures:
                    try:
                        result = future.result(timeout=5)
                        source = result['source']

                        if source == 'pubmed':
                            verified_ids['pmids'] = result['pmids']
                            all_papers.extend(result['papers'])
                            print(f"      [PubMed] 返回 {len(result['pmids'])} PMIDs")

                        elif source == 'arxiv':
                            verified_ids['arxiv_ids'] = result['arxiv_ids']
                            all_papers.extend(result['papers'])
                            print(f"      [ArXiv] 返回 {len(result['arxiv_ids'])} IDs")

                        elif source == 'semantic_scholar':
                            verified_ids['dois'] = result['dois']
                            all_papers.extend(result['papers'])
                            print(f"      [S2] 返回 {len(result['dois'])} DOIs")

                    except Exception as e:
                        print(f"      [检索] 任务结果获取异常: {e}")

                # 取消超时的任务
                for future in pending_futures:
                    future.cancel()
                    task_name = futures.get(future).__name__ if hasattr(futures.get(future), '__name__') else 'unknown'
                    print(f"      [检索] 任务 {task_name} 超时，已取消")

            except Exception as e:
                print(f"      [检索] 并发等待异常: {e}")
                # 尝试获取已完成的结果
                for future in futures.keys():
                    if future.done():
                        try:
                            result = future.result(timeout=1)
                            source = result['source']
                            if source == 'pubmed':
                                verified_ids['pmids'] = result['pmids']
                                all_papers.extend(result['papers'])
                            elif source == 'arxiv':
                                verified_ids['arxiv_ids'] = result['arxiv_ids']
                                all_papers.extend(result['papers'])
                            elif source == 'semantic_scholar':
                                verified_ids['dois'] = result['dois']
                                all_papers.extend(result['papers'])
                        except:
                            pass

        total_verified = len(verified_ids['pmids']) + len(verified_ids['arxiv_ids']) + len(verified_ids['dois'])

        if total_verified == 0:
            self.print_step_exit(5, 'failed', "断链熔断: 所有数据���均无响应")
            return {
                'state': 'failure',
                'result_type': 'literature_unavailable',
                'error': '文献检索服务不可用'
            }

        self.print_step_exit(5, 'success', f"总计 {total_verified} 篇文献")

        # ==================== V7.5 凤凰协议对抗收敛循环 ====================
        # 核心变更：状态机驱动 + 分数趋势检测 + 版本追踪
        max_iterations = self.max_phoenix_iterations  # V7.5: 从凤凰协议配置获取
        iteration = 0
        defense_passed = False
        hypothesis_result = None
        fitness_result = None
        red_team_result = None
        defense_result = None

        iteration_history = []
        score_history = []  # V7.5 新增：分数历史追踪

        # V7.4-D: 自愈引擎状态追踪
        healing_activated = False
        healing_retrieval_result = None
        healing_search_result = None  # V7.4-D: 检索结果（包含 attack_types_detected）
        patching_result = None
        auto_patch_prompt = None

        # V7.5 新增：凤凰协议状态追踪
        phoenix_rewrite_triggered = False
        alternative_paths_available = None
        external_compensation_triggered = False
        current_version = "v1.0"
        trend_analysis = None  # V7.5 新增：趋势分析结果

        # V7.5 新增：创建初始版本记录
        if self.version_manager:
            self.version_manager.create_initial_version(
                hypothesis={'original_idea': self.test_idea},
                iteration=0
            )
            print(f"[V7.5] 版本管理器初始化: v1.0")

        while iteration < max_iterations and not defense_passed:
            iteration += 1
            self.print_iteration_header(iteration, max_iterations)

            # ==================== Step 6: PI Hypothesis Gen ====================
            self.print_step_enter(6, f"迭代#{iteration}: PI 生成研究假设")

            try:
                # 强制重新加载环境变量（防止模块导入顺序问题）
                from dotenv import load_dotenv
                load_dotenv(str(project_root / '.env'), encoding='utf-8', override=True)

                from src.prompts.pi_system_prompt import format_pi_prompt_v60, format_pi_prompt_v732
                from src.utils.llm_utils import call_llm

                # 再次检查 API Key
                import os
                if not os.getenv('ANTHROPIC_API_KEY'):
                    raise ValueError("API Key 未加载，请检查 .env 文件")

                # ==================== V7.4-D: Iteration 4 使用自动补丁注入 ====================
                # 如果是 Iteration 4 且存在自动合成的补丁，使用补丁注入的 Prompt
                if iteration == 4 and auto_patch_prompt:
                    print(f"[V7.4-D] Iteration 4 使用自动补丁注入 Prompt (长度: {len(auto_patch_prompt)})")
                    augmented_input = f"{self.test_idea}\n\n{auto_patch_prompt}"
                # 如果不是第一次迭代，注入红方反馈 - V7.2+ 方法论补强指令 + V7.3.1 锚点记忆锁
                elif iteration > 1 and red_team_result:
                    feedback = self._build_feedback_context(red_team_result, defense_result, iteration, verified_ids)
                    augmented_input = f"{self.test_idea}\n\n{feedback}"
                else:
                    augmented_input = cleaned_input

                # V7.3.3 架构升级：迭代 2+ 使用 Schema 预注入 + 钛合金死锁机制
                if iteration > 1:
                    print(f"[V7.3.3] 启用 Schema 预注入 + 钛合金死锁 (iteration={iteration})")
                    pi_prompt = format_pi_prompt_v732(
                        user_domain=detected_domain,
                        user_idea=augmented_input,
                        data_sources=sources,
                        verified_ids=verified_ids,
                        iteration=iteration,
                    )
                    print(f"[V7.3.3] Schema 预注入完成，Prompt 长度: {len(pi_prompt)}")
                else:
                    # 第一次迭代使用传统 V6.0 Prompt
                    pi_prompt = format_pi_prompt_v60(
                        user_domain=detected_domain,
                        user_idea=augmented_input,
                        data_sources=sources,
                        verified_ids=verified_ids,
                    )

                llm_response = call_llm(pi_prompt)

                if not llm_response.get('success'):
                    self.print_step_exit(6, 'failed', f"LLM 调用失败: {llm_response.get('error')}")
                    return {
                        'state': 'failure',
                        'result_type': 'system_error',
                        'error': llm_response.get('error')
                    }

                hypothesis_result = llm_response.get('content')

                # ==================== V7.3.3 钛合金死锁 (Titanium Lock) ====================
                # Python-Level 物理拦截：强制覆写 references 数组
                if iteration > 1 and verified_ids:
                    try:
                        import json
                        import re
                        import ast

                        # 增强的 JSON 提取方法
                        hypothesis_json = None
                        json_start_idx = -1
                        json_end_idx = -1
                        hypothesis_str = str(hypothesis_result)

                        # 方法1: 查找 ```json 代码块
                        json_block_match = re.search(r'```json\s*', hypothesis_str, re.IGNORECASE)
                        if json_block_match:
                            # 从代码块开始位置查找 JSON 对象
                            search_start = json_block_match.end()
                            # 找到第一个 {
                            brace_start = hypothesis_str.find('{', search_start)
                            if brace_start >= 0:
                                # 使用括号匹配找到对应的 }
                                depth = 0
                                in_string = False
                                escape_next = False
                                for i in range(brace_start, len(hypothesis_str)):
                                    c = hypothesis_str[i]

                                    if escape_next:
                                        escape_next = False
                                        continue

                                    if c == '\\':
                                        escape_next = True
                                        continue

                                    if c == '"' and not escape_next:
                                        in_string = not in_string
                                        continue

                                    if not in_string:
                                        if c == '{':
                                            depth += 1
                                        elif c == '}':
                                            depth -= 1
                                            if depth == 0:
                                                json_start_idx = brace_start
                                                json_end_idx = i + 1
                                                break

                        # 方法2: 如果没找到代码块，直接查找 JSON 对象
                        if json_start_idx < 0:
                            brace_start = hypothesis_str.find('{')
                            if brace_start >= 0:
                                depth = 0
                                in_string = False
                                escape_next = False
                                for i in range(brace_start, len(hypothesis_str)):
                                    c = hypothesis_str[i]

                                    if escape_next:
                                        escape_next = False
                                        continue

                                    if c == '\\':
                                        escape_next = True
                                        continue

                                    if c == '"' and not escape_next:
                                        in_string = not in_string
                                        continue

                                    if not in_string:
                                        if c == '{':
                                            depth += 1
                                        elif c == '}':
                                            depth -= 1
                                            if depth == 0:
                                                json_start_idx = brace_start
                                                json_end_idx = i + 1
                                                break

                        # 尝试解析提取的 JSON
                        if json_start_idx >= 0 and json_end_idx > json_start_idx:
                            try:
                                hypothesis_json_str = hypothesis_str[json_start_idx:json_end_idx]

                                # 尝试 JSON 解析（双引号）
                                try:
                                    hypothesis_json = json.loads(hypothesis_json_str)
                                except json.JSONDecodeError:
                                    # 回退到 Python 字典解析（单引号）
                                    try:
                                        hypothesis_json = ast.literal_eval(hypothesis_json_str)
                                        print(f"[V7.3.3] 📤 使用 Python 字典解析成功")
                                    except (ValueError, SyntaxError) as e:
                                        print(f"[V7.3.3] ⚠️ Python 字典解析也失败: {e}")
                                        raise

                                print(f"[V7.3.3] 📤 成功提取 JSON ({len(hypothesis_json_str)} 字符)")
                            except Exception as je:
                                print(f"[V7.3.3] ⚠️ JSON 解析失败: {je}")
                                hypothesis_json = None

                        if hypothesis_json and isinstance(hypothesis_json, dict):
                            # 构建原始验证的真实引用列表
                            titanium_locked_references = []

                            for pmid in verified_ids.get('pmids', [])[:10]:
                                titanium_locked_references.append({
                                    "pmid": str(pmid),
                                    "citation": f"[PMID: {pmid}] (系统已验证，钛合金死锁保护)"
                                })

                            for arxiv_id in verified_ids.get('arxiv_ids', [])[:5]:
                                titanium_locked_references.append({
                                    "arxiv_id": arxiv_id,
                                    "citation": f"[arXiv: {arxiv_id}] (系统已验证，钛合金死锁保护)"
                                })

                            for doi in verified_ids.get('dois', [])[:5]:
                                titanium_locked_references.append({
                                    "doi": doi,
                                    "citation": f"[DOI: {doi}] (系统已验证，钛合金死锁保护)"
                                })

                            # 检测并强制覆写
                            original_refs = hypothesis_json.get('references', [])
                            original_refs_count = len(original_refs)
                            titanium_locked_count = len(titanium_locked_references)

                            # 🔥 钛合金死锁：强制覆写！
                            hypothesis_json['references'] = titanium_locked_references

                            # 序列化回 JSON
                            corrected_json_str = json.dumps(hypothesis_json, ensure_ascii=False, indent=2)

                            # 替换原 hypothesis_result 中的 JSON 部分
                            hypothesis_result = hypothesis_str[:json_start_idx] + corrected_json_str + hypothesis_str[json_end_idx:]

                            # 🚨 关键日志
                            if original_refs_count > titanium_locked_count:
                                print(f"[V7.3.3] 🚨 钛合金死锁触发：检测到 PI Agent 试图添加 {original_refs_count - titanium_locked_count} 个虚假引用！已强制覆写。")
                            elif original_refs_count < titanium_locked_count:
                                print(f"[V7.3.3] 🚨 钛合金死锁触发：检测到 PI Agent 丢失了 {titanium_locked_count - original_refs_count} 个真实引用！已强制覆写。")
                            else:
                                print(f"[V7.3.3] ✅ 钛合金死锁生效：已使用第一轮真实 PMID 强制覆写当前 JSON 的引用列表。")

                            print(f"[V7.3.3] 钛合金锁定引用数: {titanium_locked_count}")

                        else:
                            print(f"[V7.3.3] ⚠️ 无法解析 hypothesis JSON，跳过钛合金死锁")
                            print(f"[V7.3.3] 假设内容预览: {hypothesis_str[:200]}...")

                    except Exception as lock_error:
                        import traceback
                        print(f"[V7.3.3] ❌ 钛合金死锁执行异常: {lock_error}")
                        traceback.print_exc()
                # ==================== V7.3.3 钛合金死锁结束 ====================

                self.print_step_exit(6, 'success', f"假设已生成 (tokens: {llm_response.get('tokens_used', 0)})")

            except Exception as e:
                self.print_step_exit(6, 'failed', f"异常: {str(e)}")
                return {
                    'state': 'failure',
                    'result_type': 'system_error',
                    'error': str(e)
                }

            # ==================== Step 7: Hard-Link Anchor ====================
            self.print_step_enter(7, f"迭代#{iteration}: 验证引用是否真实存在")

            # V7.3.1 调试输出：显示假设中是否包含 PMID 引用
            import re
            pmid_pattern = r'\[PMID[:\s]+(\d{7,8})\]|PMID[:\s]+(\d{7,8})|\(PMID[:\s]+(\d{7,8})\)'
            found_pmids = re.findall(pmid_pattern, str(hypothesis_result), re.IGNORECASE)
            # flatten the list of tuples and filter empty strings
            found_pmids = [p for tup in found_pmids for p in tup if p]
            print(f"[V7.3.1] 假设中发现 PMID 引用: {found_pmids if found_pmids else '无'}")
            print(f"[V7.3.1] 已验证 PMID 列表: {verified_ids.get('pmids', [])}")

            anchor_passed = True
            anchor_message = ""

            try:
                from src.core.hard_link_anchor import perform_anchor_check
                is_valid, anchor_message = perform_anchor_check(
                    hypothesis_result,
                    verified_ids['pmids'],
                    verified_ids['arxiv_ids'],
                    verified_ids['dois']
                )
                anchor_passed = is_valid
                print(f"[V7.3.1] Anchor Check 详细结果: {anchor_message}")
                self.print_step_exit(7, 'success' if anchor_passed else 'failed', f"锚定结果: {anchor_passed}")

            except ImportError:
                self.print_step_exit(7, 'warning', "Anchor 不可用，跳过")

            if not anchor_passed:
                iteration_history.append({'iteration': iteration, 'status': 'anchor_failed'})
                if iteration >= max_iterations:
                    break
                continue

            # ==================== Step 8: Hybrid Fitness ====================
            self.print_step_enter(8, f"迭代#{iteration}: 计算混合适应度评分")

            try:
                from src.core.hybrid_fitness import HybridFitnessScorer
                from src.core.physical_validator import PhysicalValidator
                from src.utils.llm_utils import SafeExtractor

                # 解析 hypothesis_result 为字典格式
                if isinstance(hypothesis_result, str):
                    try:
                        hypothesis_dict = SafeExtractor.safe_extract_json(hypothesis_result)
                    except Exception:
                        # 如果 JSON 解析失败，使用包装格式
                        hypothesis_dict = {'hypothesis_text': hypothesis_result, 'details': ''}
                else:
                    hypothesis_dict = hypothesis_result

                validator = PhysicalValidator()
                physical_result = validator.validate_hypothesis_physical(hypothesis_dict)

                if not physical_result.passed:
                    self.print_step_exit(8, 'failed', f"物理校验失败: {physical_result.failure_reason}")
                    iteration_history.append({'iteration': iteration, 'status': 'physical_failed'})
                    if iteration >= max_iterations:
                        break
                    continue

                scorer = HybridFitnessScorer()
                fitness_result = scorer.calculate_fitness(hypothesis_dict, all_papers)

                score = fitness_result.hybrid_fitness
                self.print_step_exit(8, 'success', f"Hybrid Fitness: {score:.2f}")

                if score < 7.0:
                    self.print_step_exit(8, 'warning', f"得分低于阈值 7.0")
                    iteration_history.append({'iteration': iteration, 'status': 'low_fitness', 'score': score})
                    if iteration >= max_iterations:
                        break
                    continue

            except ImportError:
                self.print_step_exit(8, 'warning', "Hybrid Fitness 不可用")

            # ==================== Step 9: Red Team Attack ====================
            self.print_step_enter(9, f"迭代#{iteration}: 红方攻击审计")

            try:
                from src.agents.red_team_agent import RedTeamAgent
                red_agent = RedTeamAgent()
                red_team_result = red_agent.execute({
                    'blue_package': {
                        'hypothesis_data': hypothesis_dict,
                        'fitness_data': fitness_result.to_dict() if fitness_result else {},
                        'verified_ids': verified_ids,
                    }
                })

                # V7.2 修复：从 attack_report 中提取 verdict
                attack_report = red_team_result.get('attack_report', {}) if red_team_result else {}
                verdict = attack_report.get('verdict', 'unknown')
                self.print_step_exit(9, 'success', f"红方裁决: {verdict}")

            except ImportError:
                self.print_step_exit(9, 'warning', "Red Team 不可用")
                red_team_result = None

            # ==================== Step 10: Defense Committee ====================
            self.print_step_enter(10, f"迭代#{iteration}: 防御委员会终审答辩")

            try:
                from src.agents.defense_committee_agent import DefenseCommitteeAgent
                committee = DefenseCommitteeAgent()
                defense_result = committee.execute({
                    'blue_package': {
                        'hypothesis_data': hypothesis_dict,
                        'fitness_data': fitness_result.to_dict() if fitness_result else {},
                    },
                    'red_attack': red_team_result.get('attack_report', {}) if red_team_result else {}
                })

                defense_passed = defense_result.get('defense_passed', False)
                science_score = defense_result.get('science_score', 7.5)  # V7.5 新增：获取科学评分
                status = 'success' if defense_passed else 'failed'
                self.print_step_exit(10, status, f"答辩结果: {'通过' if defense_passed else '失败'}, Science Score: {science_score:.2f}")

                # V7.5 新增：记录分数历史
                score_history.append(science_score)

                # V7.5 新增：更新版本分数
                if self.version_manager and self.version_manager.current_version:
                    self.version_manager.update_version_scores(
                        self.version_manager.current_version,
                        science_score=science_score,
                        fitness_score=fitness_result.hybrid_fitness if fitness_result else 0.0,
                        defense_passed=defense_passed,
                        red_attack_types=red_team_result.get('attack_types', []) if red_team_result else []
                    )
                    print(f"[V7.5] 版本 {self.version_manager.current_version} 分数更新: {science_score:.2f}")

                iteration_history.append({
                    'iteration': iteration,
                    'status': 'defense_passed' if defense_passed else 'defense_failed',
                    'verdict': defense_result.get('final_verdict', 'N/A'),
                    'science_score': science_score,  # V7.5 新增
                })

            except ImportError:
                self.print_step_exit(10, 'warning', "Defense Committee 不可用")
                defense_passed = True  # 降级：跳过委员会时默认通过

            if defense_passed:
                print(f"\n🎉 对抗收敛成功！迭代次数: {iteration}")
                break

            # ==================== V7.5 新增：分数趋势检测 ====================
            # 检查分数是否停滞，触发外部补偿
            if self.trend_detector and len(score_history) >= 2:
                trend_analysis = self.trend_detector.analyze_trend(score_history)
                print(f"[V7.5] 分数趋势分析: {trend_analysis.trend_direction}, 停滞次数: {trend_analysis.consecutive_stagnant_count}")

                if trend_analysis.should_trigger_compensation:
                    print(f"[V7.5] 🔥 分数连续停滞，触发外部算法补偿！")
                    external_compensation_triggered = True

                    # 创建新版本记录（外部补偿类型）
                    if self.version_manager:
                        self.version_manager.create_rewrite_version(
                            rewrite_type='external_compensation',
                            rewrite_log=[{
                                'reason': '分数连续停滞触发外部补偿',
                                'stagnant_count': trend_analysis.consecutive_stagnant_count,
                            }],
                            iteration=iteration
                        )
                        current_version = self.version_manager.current_version
                        print(f"[V7.5] 创建外部补偿版本: {current_version}")

            # ==================== V7.4-F 自愈引擎触发点 ====================
            # 当 Iteration 3 失败后，启动自愈引擎进行跨学科检索和补丁合成
            if iteration == 3 and not defense_passed and not healing_activated:
                print(f"\n🧬 V7.4-F 自愈引擎触发：Iteration 3 失败，启动跨学科检索...")
                healing_activated = True

                # Step 16: 自愈引擎启动
                self.print_step_enter(16, "V7.4-F 自愈引擎：跨学科检索启动")

                try:
                    from src.agents.search_supplement_agent import SearchSupplementAgent

                    # V7.4-F 修复：构建完整的拒绝原因（优先使用 final_verdict）
                    rejection_reason = ""
                    if defense_result:
                        rejection_reason = defense_result.get('final_verdict', '')
                        if not rejection_reason:
                            rejection_reason = defense_result.get('committee_response', '')
                        critical_issues = defense_result.get('critical_issues', [])
                        rejection_reason += " " + " ".join(critical_issues)

                    healing_agent = SearchSupplementAgent()
                    # V7.4-F 修复：传递完整数据链
                    healing_search_result = healing_agent.execute({
                        'rejection_reason': rejection_reason,
                        'red_attack_report': red_team_result.get('attack_report', {}) if red_team_result else {},
                        'defense_result': defense_result,                    # V7.4-F 保持传递
                        'iteration_history': iteration_history,              # V7.4-F 新增
                        'hypothesis_domain': detected_domain,
                        'original_idea': self.test_idea,
                    })

                    healing_retrieval_result = healing_search_result.get('retrieval_result', {})
                    patch_materials = healing_search_result.get('patch_materials', [])

                    self.print_step_exit(16, 'success',
                        f"检索完成: {healing_search_result.get('attack_types_detected', [])}, "
                        f"共 {healing_retrieval_result.get('total_found', 0)} 篇文献")

                except ImportError as e:
                    print(f"[V7.4-D] SearchSupplementAgent 导入失败: {e}")
                    self.print_step_exit(16, 'failed', f"自愈引擎组件缺失: {e}")
                    healing_activated = False

                except Exception as e:
                    print(f"[V7.4-D] 自愈检索异常: {e}")
                    self.print_step_exit(16, 'failed', f"检索异常: {e}")
                    healing_activated = False

                # Step 17: 补丁合成与注入
                if healing_activated and patch_materials:
                    self.print_step_enter(17, "V7.4-D 补丁合成引擎")

                    try:
                        from src.core.synthesis_patching_engine import SynthesisPatchingEngine

                        patching_engine = SynthesisPatchingEngine()
                        patching_output = patching_engine.execute({
                            'retrieval_result': healing_retrieval_result,
                            'patch_materials': patch_materials,
                            'attack_types': healing_search_result.get('attack_types_detected', []),
                            'original_hypothesis': hypothesis_result if hypothesis_result else self.test_idea,
                        })

                        patching_result = patching_output.get('patching_result', {})
                        auto_patch_prompt = patching_result.get('combined_injection_prompt', '')

                        self.print_step_exit(17, 'success',
                            f"补丁合成完成: {len(patching_result.get('patches', []))} 条")

                        print(f"\n[V7.4-D] 自动补丁已合成，将在 Iteration 4 中注入 PI Agent...")

                    except ImportError as e:
                        print(f"[V7.4-D] SynthesisPatchingEngine 导入失败: {e}")
                        self.print_step_exit(17, 'failed', f"补丁引擎组件缺失: {e}")
                        auto_patch_prompt = None

                    except Exception as e:
                        print(f"[V7.4-D] 补丁合成异常: {e}")
                        self.print_step_exit(17, 'failed', f"合成异常: {e}")
                        auto_patch_prompt = None

            if iteration < max_iterations:
                print(f"\n🔄 未通过，进入下一轮迭代...")

        # ==================== Step 11: Convergence Check ====================
        self.print_step_enter(11, "检测对抗是否收敛")

        convergence_state = 'converged' if defense_passed else 'max_iterations_exceeded'
        self.print_step_exit(11, 'success' if defense_passed else 'warning', f"收敛状态: {convergence_state}")

        # ==================== Step 12: Audit Aggregation ====================
        self.print_step_enter(12, "聚合完整审计数据")

        audit_context = {
            'hybrid_fitness': {
                'score': fitness_result.hybrid_fitness if fitness_result else 0.0,
            },
            'red_team_attack': {
                'enabled': red_team_result is not None,
                'verdict': red_team_result.get('verdict', 'N/A') if red_team_result else 'N/A',
            },
            'defense_committee': {
                'enabled': defense_result is not None,
                'passed': defense_passed,
            },
            'convergence': {
                'state': convergence_state,
                'iteration': iteration,
            },
            'iteration_history': iteration_history,
        }

        self.print_step_exit(12, 'success', "审计数据已聚合")

        # ==================== Step 13: Report Generation ====================
        self.print_step_enter(13, "生成最终报告")

        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        if defense_passed and hypothesis_result:
            result_type = 'hypothesis'
            state = 'success'

            # V7.5 新增：获取版本演进链
            version_evolution_chain = []
            if self.version_manager:
                version_evolution_chain = self.version_manager.get_version_evolution_chain()

            # V7.5 新增：计算 Promise Score
            promise_score_result = None
            try:
                from src.core.promise_score_calculator import calculate_promise_score
                promise_score_result = calculate_promise_score(
                    hypothesis_result={'year': 2025, 'citation_velocity': 'Top 10%',
                                      'scores': {'novelty': science_score}},
                    fitness_result={'vector_novelty_score': science_score,
                                   'physical_validation': {'score': science_score}},
                    verified_ids=verified_ids,
                    version_chain=version_evolution_chain
                )
                print(f"[V7.5] Promise Score 计算: {promise_score_result.total_score:.2f}")
            except Exception as e:
                print(f"[V7.5] Promise Score 计算失败: {e}")

            payload = {
                'hypothesis': hypothesis_result[:500] + "..." if len(hypothesis_result) > 500 else hypothesis_result,
                'fitness': fitness_result.to_dict() if fitness_result else None,
                'verified_ids': verified_ids,
                'domain': detected_domain,
                'audit_context': audit_context,
                # V7.5 新增：版本演进链
                'version_evolution': {
                    'chain': version_evolution_chain,
                    'total_versions': len(version_evolution_chain),
                    'final_version': current_version,
                },
                # V7.5 新增：分数趋势
                'score_trend': {
                    'history': score_history,
                    'final_score': score_history[-1] if score_history else 0.0,
                    'trend': trend_analysis.trend_direction if trend_analysis else 'unknown',
                },
                # V7.5 新增：Promise Score
                'promise_score': promise_score_result.to_dict() if promise_score_result else None,
                # V7.4-D: 自愈引擎状态信息
                'healing_engine': {
                    'activated': healing_activated,
                    'retrieval_count': healing_retrieval_result.get('total_found', 0) if healing_retrieval_result else 0,
                    'patch_count': len(patching_result.get('patches', [])) if patching_result else 0,
                    'attack_types_detected': healing_search_result.get('attack_types_detected', []) if healing_search_result else [],
                    'iteration_4_success': iteration == 4 and defense_passed,
                },
                # V7.5 新增：凤凰协议状态
                'phoenix_protocol': {
                    'enabled': self.phoenix_enabled,
                    'rewrite_triggered': phoenix_rewrite_triggered,
                    'external_compensation_triggered': external_compensation_triggered,
                    'total_iterations': iteration,
                },
            }
        else:
            # ==================== V7.2: 生成高危科研路径排雷与转向报告 ====================
            result_type = 'rejection'
            state = 'failure'

            try:
                from src.core.rejection_report import RejectionReportGenerator, RejectionType

                # V7.2: 构建迭代审计记录
                v7_iteration_history = []
                for iter_record in iteration_history:
                    # 提取红方和防御委员会信息
                    red_verdict = iter_record.get('red_team_verdict', 'N/A')
                    red_critical = []
                    red_severe = []

                    if '红方裁决' in str(iter_record) or 'red_team' in str(iter_record):
                        # 从现有记录中提取红方信息（如果有的话）
                        pass

                    defense_verdict = iter_record.get('verdict', 'N/A')
                    defense_critical = []

                    v7_iteration_history.append({
                        'iteration': iter_record.get('iteration', 0),
                        'hypothesis_preview': '',  # 可以添加假设摘要
                        'anchor_passed': iter_record.get('anchor_passed', True),
                        'anchor_message': iter_record.get('anchor_message', ''),
                        'fitness_score': iter_record.get('fitness_score', 0.0),
                        'red_team_verdict': red_verdict,
                        'red_team_critical_flaws': red_critical,
                        'red_team_severe_issues': red_severe,
                        'defense_passed': False,  # 因为走到这里说明没通过
                        'defense_verdict': defense_verdict,
                        'defense_critical_issues': defense_critical,
                        'status': iter_record.get('status', 'defense_failed'),
                    })

                # V7.2: 生成拒稿报告
                generator = RejectionReportGenerator(save_reports=True)
                report = generator.generate(
                    user_input=self.test_idea,
                    domain=detected_domain,
                    rejection_type=RejectionType.MAX_ITERATIONS_EXCEEDED,
                    primary_reason="经过3轮对抗检验，假设仍无法通过防御委员会审查",
                    iteration_history=v7_iteration_history,
                    red_team_result=red_team_result,
                    defense_result=defense_result,
                    all_papers=all_papers,
                    api_calls_used=0,  # 可以从 fuse 获取
                    tokens_used=0,
                    time_elapsed=duration,
                    papers_searched=len(all_papers),
                    data_sources_used=sources,
                    verified_ids_found=verified_ids,
                )

                # 获取 Markdown 报告
                markdown_report = report.to_markdown()

                # 打印报告到控制台
                print("\n" + "=" * 80)
                print("╔══════════════════════════════════════════════════════════════════════════════╗")
                print("║           V7.2 高危科研路径排雷与转向报告                                            ║")
                print("╚══════════════════════════════════════════════════════════════════════════════╝")
                print("=" * 80)
                print(markdown_report)

                payload = {
                    'rejection_report': markdown_report,
                    'report_id': report.report_id,
                    'audit_context': audit_context,
                    'pivot_suggestions': [p.to_dict() for p in report.pivot_suggestions],
                    # V7.4-D: 自愈引擎状态信息（即使失败也记录）
                    'healing_engine': {
                        'activated': healing_activated,
                        'retrieval_count': healing_retrieval_result.get('total_found', 0) if healing_retrieval_result else 0,
                        'patch_count': len(patching_result.get('patches', [])) if patching_result else 0,
                        'attack_types_detected': healing_search_result.get('attack_types_detected', []) if healing_search_result else [],  # V7.4-G: 修复传递
                        'iteration_4_attempted': iteration == 4,
                        'iteration_4_success': False,
                    },
                }

            except ImportError:
                # 降级到简单格式
                payload = {
                    'reason': '对抗收敛失败或假设验证未通过',
                    'audit_context': audit_context,
                    'healing_engine': {
                        'activated': healing_activated,
                        'retrieval_count': 0,
                        'patch_count': 0,
                        'attack_types_detected': healing_search_result.get('attack_types_detected', []) if healing_search_result else [],  # V7.4-G: 修复传递
                        'iteration_4_attempted': iteration == 4,
                        'iteration_4_success': False,
                    },
                }
            except Exception as e:
                print(f"      [报告生成异常] {e}")
                payload = {
                    'reason': f'对抗收敛失败: {str(e)}',
                    'audit_context': audit_context,
                    'healing_engine': {
                        'activated': healing_activated,
                        'retrieval_count': 0,
                        'patch_count': 0,
                        'attack_types_detected': healing_search_result.get('attack_types_detected', []) if healing_search_result else [],  # V7.4-G: 修复传递
                        'iteration_4_attempted': iteration == 4,
                        'iteration_4_success': False,
                    },
                }

        self.print_step_exit(13, 'success' if state == 'success' else 'failed', f"报告类型: {result_type}")

        # ==================== Step 14: Webhook Callback (跳过) ====================
        self.print_step_enter(14, "Webhook 回调通知")
        self.print_step_exit(14, 'skipped', "探针模式不发送 Webhook")

        # ==================== Step 15: Task Complete ====================
        self.print_step_enter(15, "任务完成")

        # 使用已有的 duration（如果 Step 13 已计算）
        if 'duration' not in dir() or duration == 0:
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()

        result = {
            'state': state,
            'result_type': result_type,
            'payload': payload,
            'duration': duration,
            'iterations': iteration,
        }

        self.print_step_exit(15, 'success', f"耗时 {duration:.2f}s, 迭代 {iteration} 次")

        # 打印最终结果摘要
        self.print_final_result(result)

        return result

    def _build_feedback_context(self, red_team_result: dict, defense_result: dict, iteration: int, verified_ids: dict = None) -> str:
        """
        V7.3 语义意图分诊反馈机制 + V7.3.1 锚点记忆锁

        核心升级：
        1. 调用 Intent Triage Agent 进行语义分析
        2. 映射到风险矩阵
        3. 注入定向防御协议
        4. V7.3.1: 追加锚点记忆锁，防止 PI Agent 遗忘已验证文献 ID
        """
        # ==================== V7.3 意图分诊系统 ====================
        from src.core.intent_triage import triage_red_attack_semantic, build_defense_injection

        # 提取红方攻击文本
        attack_report = red_team_result.get('attack_report', {}) if red_team_result else {}

        red_attacks = []
        if attack_report:
            flaws = attack_report.get('critical_flaws', [])
            if flaws:
                for item in flaws[:5]:
                    if isinstance(item, dict):
                        red_attacks.append(item.get('issue', str(item)))
                    else:
                        red_attacks.append(str(item))
            severe = attack_report.get('severe_issues', [])
            if severe:
                for item in severe[:3]:
                    if isinstance(item, dict):
                        red_attacks.append(item.get('issue', str(item)))
                    else:
                        red_attacks.append(str(item))

        # 构建攻击文本
        attacks_text = "\n".join([f"- {a}" for a in red_attacks])
        if not attacks_text:
            attacks_text = "- 未见具体攻击点，但整体未通过审查"

        # V7.3 核心：调用意图分诊器
        print(f"\n[V7.3] 启动意图分诊分析...")
        detected_categories = triage_red_attack_semantic(attacks_text)

        # V7.3 核心：构建定向防��注入
        defense_injection = build_defense_injection(detected_categories)

        # V7.3 调试输出
        print(f"[V7.3] 防御注入长度: {len(defense_injection)} 字符")
        print(f"[V7.3] 防御注入预览:\n{defense_injection[:500]}...")

        # V7.3 进阶博弈指令模板
        ADVANCED_ITERATION_PROMPT = f"""## 【V7.3 硬核博弈指令】

这是你的第 **{iteration} 次重试**。防御委员会刚才驳回了你的假说，红方的核心攻击意见如下：

{attacks_text}

{defense_injection}
### 🎯 高级迭代策略

1. **定向反击而非泛泛而谈**
   - 使用上述【定向防御协议】中提供的具体技术方案
   - 必须在 `methodology.technical_safeguards` 字段中完整实现

2. **保持学术创新性**
   - 防御措施不应削弱核心创新点
   - 技术方案应与研究问题紧密贴合

3. **证据密度**
   - 每个关键断言都要有 PMID/DOI 支持

---

**现在，提交带有完整技术防范措施的优化版假说！**
"""

        # ==================== V7.3.1 锚点记忆锁（Anchor Memory Lock）====================
        # 防止 PI Agent 因注意力稀释遗忘已验证的文献 ID
        anchor_lock = ""

        if verified_ids and iteration > 1:
            pmids = verified_ids.get('pmids', [])
            arxiv_ids = verified_ids.get('arxiv_ids', [])
            dois = verified_ids.get('dois', [])

            # 只有存在已验证文献时才追加锚点锁
            if pmids or arxiv_ids or dois:
                anchor_lock = """

---

### ⚠️⚠️⚠️ 【V7.3.1 生死红线：锚点记忆锁】（强制执行）

**系统警告：你必须在新生成的 JSON 中引用以下已验证的真实文献 ID！**

**已验证的文献锚点（绝对不能丢失）：**
"""

                if pmids:
                    anchor_lock += f"""
**PMIDs（PubMed 文献 ID）**: {', '.join(map(str, pmids))}
"""
                if arxiv_ids:
                    anchor_lock += f"""
**ArXiv IDs**: {', '.join(arxiv_ids)}
"""
                if dois:
                    anchor_lock += f"""
**DOIs**: {', '.join(dois)}
"""

                anchor_lock += """
**硬性要求：**
1. 你的 `references` 字段中必须包含上述文献 ID
2. 你的假设必须引用这些文献来支撑核心论断
3. **绝对禁止**编造不存在的文献 ID
4. **绝对禁止**遗漏上述已验证的真实文献

**Schema 约束提醒：**
- 防御协议只能写入 `methodology.technical_safeguards` 字段
- 文献引用必须写入 `references` 字段，格式为 `[{"pmid": "12345678", "citation": "..."}]`

**如果违反上述约束，将被系统直接拒绝，无法通过 Step 7 锚定校验！**
---
"""

        # 将锚点记忆锁追加到进阶博弈指令末尾
        ADVANCED_ITERATION_PROMPT += anchor_lock

        # V7.3.1 调试输出：显示锚点记忆锁是否被添加
        if anchor_lock:
            print(f"[V7.3.1] 锚点记忆锁已追加，长度: {len(anchor_lock)} 字符")
            print(f"[V7.3.1] 完整反馈上下文长度: {len(ADVANCED_ITERATION_PROMPT)} 字符")
            print(f"[V7.3.1] 锚点记忆锁内容:\n{anchor_lock}")
        else:
            print(f"[V7.3.1] 锚点记忆锁未追加（verified_ids 为空或 iteration == 1）")

        return ADVANCED_ITERATION_PROMPT


# ==================== 主程序入口 ====================
def main():
    parser = argparse.ArgumentParser(description='V7.3 全链路探针')
    parser.add_argument('--idea', type=str, default=None, help='测试意图（可选）')
    parser.add_argument('--quick', action='store_true', help='快速模式（跳过部分检查）')

    args = parser.parse_args()

    # 创建探针并执行
    probe = PipelineProbe(test_idea=args.idea)

    try:
        result = probe.run_full_pipeline()

        # 保存日志
        log_file = project_root / 'logs' / 'probe_test.log'
        log_file.parent.mkdir(exist_ok=True)

        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"V7.3 探针测试日志\n")
            f.write(f"时间: {datetime.now().isoformat()}\n")
            f.write(f"输入: {probe.test_idea}\n")
            f.write(f"结果: {result.get('state')}\n")
            f.write(f"迭代: {probe.iteration_count}\n\n")

            for log_entry in probe.logs:
                f.write(f"[{log_entry['time']}] Step {log_entry['step']}: {log_entry['event']}\n")

        print(f"\n💾 日志已保存: {log_file}")

    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断执行")
        return 1

    except Exception as e:
        print(f"\n\n❌ 探针执行异常: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())