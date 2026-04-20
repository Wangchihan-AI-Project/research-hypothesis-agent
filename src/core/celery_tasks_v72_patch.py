# -*- coding: utf-8 -*-
"""
V7.2 对抗收敛循环补丁 - Convergence Loop Patch

使用方法：
1. 备份原 celery_tasks.py
2. 将此补丁内容替换 celery_tasks.py 中的 Phase 5-11 部分（约第808-997行）
3. 重启 Celery Worker

架构改进：
- 引入 while 循环实现红蓝对抗迭代
- 红方意见反馈��� PI Prompt，强制假设优化
- 最大迭代次数保护，防止死循环
"""

# ========================================
# 替换位置：celery_tasks.py 第 808-997 行
# 从 "Phase 5: PI 生成假设" 到 "Phase 10: Convergence Check"
# ========================================

# ==================== Phase 5-11: V7.2 对抗收敛循环 ====================
self.update_progress(50, "启动红蓝对抗收敛循环")

# V7.2: 从前端参数读取最大迭代次数（优先级高于 Pydantic）
max_iterations = frontend_max_iterations if frontend_max_iterations is not None else config.defense_layer.max_iterations
logger.info(f"[Task {task_id}] 对抗收敛循环: 最大迭代次数 = {max_iterations}")

# 初始化对抗状态
iteration = 0
defense_passed = False
hypothesis_result = None
fitness_result = None
red_team_result = None
defense_result = None
convergence_result = None

# 对抗历史追踪（用于收敛检测）
iteration_history = []
anchor_passed = False  # 初始化锚定状态

while iteration < max_iterations and not defense_passed:
    iteration += 1
    logger.info(f"[Task {task_id}] === 对抗迭代 #{iteration}/{max_iterations} ===")

    # ------------------- Sub-Step 6: PI 生成假设 -------------------
    self.update_progress(50 + (iteration * 3), f"迭代#{iteration}: PI 假设生成")

    current_hypothesis = None
    llm_system_error = None

    try:
        from src.prompts.pi_system_prompt import format_pi_prompt_v60
        from src.utils.llm_utils import call_llm

        # V7.2: 如果不是第一次迭代，注入红方反馈上下文
        if iteration > 1 and red_team_result:
            # 构建反馈上下文
            red_feedback = _build_red_team_feedback_context(red_team_result, defense_result)
            logger.info(f"[Task {task_id}] 注入红方反馈上下文:\n{red_feedback[:500]}...")

            # 将反馈附加到用户输入中
            augmented_user_input = f"{user_input}\n\n{red_feedback}"
        else:
            augmented_user_input = user_input

        pi_prompt = format_pi_prompt_v60(
            user_domain=detected_domain,
            user_idea=augmented_user_input,  # V7.2: 使用增强后的输入
            data_sources=sources,
            verified_ids=verified_ids,
        )

        self.update_progress(55 + (iteration * 3), f"迭代#{iteration}: 调用 PI Agent")
        llm_response = call_llm(pi_prompt)

        # 检查 LLM 调用是否成功
        if not llm_response.get('success'):
            llm_system_error = f"LLM API 调用失败: {llm_response.get('error', 'Unknown error')}"
            logger.error(f"[Task {task_id}] {llm_system_error}")
        else:
            current_hypothesis = llm_response.get('content')
            if current_hypothesis:
                hypothesis_result = current_hypothesis
                logger.info(f"[Task {task_id}] 迭代#{iteration} PI hypothesis generated (tokens: {llm_response.get('tokens_used', 0)})")
            else:
                logger.warning(f"[Task {task_id}] 迭代#{iteration} PI hypothesis generation failed: empty content")

    except ImportError as e:
        llm_system_error = f"模块导入失败: {str(e)}"
        logger.error(f"[Task {task_id}] {llm_system_error}")
        traceback.print_exc()

    except ValueError as e:
        llm_system_error = f"配置错误: {str(e)}"
        logger.error(f"[Task {task_id}] {llm_system_error}")
        traceback.print_exc()

    except Exception as e:
        llm_system_error = f"LLM 调用异常: {str(e)}"
        logger.error(f"[Task {task_id}] {llm_system_error}")
        traceback.print_exc()

    # 如果是系统级错误，直接退出循环
    if llm_system_error:
        logger.critical(f"[Task {task_id}] 系统级错误，中止对抗循环")
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        from src.core.rejection_report import RejectionType
        return TaskResult(
            task_id=task_id,
            state=TaskState.FAILURE,
            result_type='system_error',
            payload={
                'error_type': 'system_error',
                'error_message': llm_system_error,
                'user_input': user_input,
                'domain': detected_domain,
                'iteration': iteration,
                'iteration_history': iteration_history,
            },
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration=duration,
            config_version=config_version,
        ).to_dict()

    # ------------------- Sub-Step 7: Hard-Link Anchor 校验 -------------------
    self.update_progress(65 + (iteration * 3), f"迭代#{iteration}: Hard-Link Anchor 锚定校验")

    anchor_passed = True
    anchor_message = ""

    hard_link_anchor_enabled = frontend_v7_defenses.get('hard_link_anchor', config.defense_layer.hard_link_anchor_enabled)

    if hypothesis_result and hard_link_anchor_enabled:
        try:
            from src.core.hard_link_anchor import perform_anchor_check
            strict_mode = config.defense_layer.hard_link_anchor_strict_mode

            is_valid, anchor_message = perform_anchor_check(
                hypothesis_result,
                verified_ids.get('pmids', []),
                verified_ids.get('arxiv_ids', []),
                verified_ids.get('dois', []),
                strict_mode=strict_mode,
            )

            anchor_passed = is_valid
            logger.info(f"[Task {task_id}] 迭代#{iteration} Anchor check: {anchor_passed}")

            if not anchor_passed:
                logger.warning(f"[Task {task_id}] 迭代#{iteration} Anchor check failed: {anchor_message}")

        except ImportError:
            logger.warning(f"[Task {task_id}] Hard-Link Anchor not available, skipping check")
        except Exception as e:
            logger.error(f"[Task {task_id}] Anchor check error: {e}")

    # ------------------- Sub-Step 8: Physical Validator + Hybrid Fitness -------------------
    self.update_progress(70 + (iteration * 3), f"迭代#{iteration}: V6.1 混合适应度评估")

    fitness_result = None
    if hypothesis_result and anchor_passed:
        try:
            from src.core.hybrid_fitness import HybridFitnessScorer
            from src.core.physical_validator import PhysicalValidator

            # 物理铁闸校验
            validator = PhysicalValidator()
            physical_result = validator.validate_hypothesis_physical(hypothesis_result)

            if not physical_result.passed:
                logger.warning(f"[Task {task_id}] 迭代#{iteration} Physical validation failed: {physical_result.failure_reason}")
                anchor_passed = False
                anchor_message = physical_result.failure_reason
            else:
                # 混合适应度计算
                scorer = HybridFitnessScorer()
                fitness_result = scorer.calculate_fitness(
                    hypothesis_json=hypothesis_result,
                    retrieved_docs=all_papers if all_papers else [],
                )

                logger.info(f"[Task {task_id}] 迭代#{iteration} Hybrid fitness: {fitness_result.hybrid_fitness}")
                logger.info(f"[Task {task_id}]   Vector novelty: {fitness_result.vector_novelty_score}")
                logger.info(f"[Task {task_id}]   Rigor: {fitness_result.red_team_rigor_score}")

                # 检查是否达到阈值
                min_threshold = final_min_score_threshold
                if fitness_result.hybrid_fitness < min_threshold:
                    logger.warning(f"[Task {task_id}] 迭代#{iteration} Hybrid fitness {fitness_result.hybrid_fitness} < threshold {min_threshold}")
                    anchor_passed = False
                    anchor_message = f"混合适应度得分 {fitness_result.hybrid_fitness} 未达到阈值 {min_threshold}"

        except ImportError as e:
            logger.warning(f"[Task {task_id}] V6.1 Hybrid Fitness modules not available: {e}")
        except Exception as e:
            logger.error(f"[Task {task_id}] Hybrid fitness evaluation error: {e}")

    # 如果 Anchor/Physical/Fitness 不及格，记录本次迭代并继续
    if not anchor_passed:
        logger.info(f"[Task {task_id}] 迭代#{iteration} 校验未通过，记录并继续下一轮...")

        iteration_history.append({
            'iteration': iteration,
            'status': 'validation_failed',
            'anchor_passed': anchor_passed,
            'anchor_message': anchor_message,
            'fitness_score': fitness_result.hybrid_fitness if fitness_result else 0.0,
        })

        # 如果已经是最后一次迭代，不要继续
        if iteration >= max_iterations:
            logger.warning(f"[Task {task_id}] 已达最大迭代次数，终止对抗循环")
            break
        continue  # 继续下一轮迭代

    # ------------------- Sub-Step 9: Red Team Attack -------------------
    self.update_progress(80 + (iteration * 2), f"迭代#{iteration}: 红方攻击审计")

    red_team_result = None
    if hypothesis_result:
        try:
            from src.agents.red_team_agent import RedTeamAgent
            red_agent = RedTeamAgent()
            red_team_result = red_agent.execute({
                'blue_package': {
                    'hypothesis_data': hypothesis_result,
                    'fitness_data': fitness_result.to_dict() if fitness_result else {},
                    'verified_ids': verified_ids,
                }
            })
            logger.info(f"[Task {task_id}] 迭代#{iteration} Red Team attack completed, verdict: {red_team_result.get('verdict', 'unknown')}")
        except ImportError as e:
            logger.warning(f"[Task {task_id}] RedTeamAgent not available: {e}")
        except Exception as e:
            logger.error(f"[Task {task_id}] Red Team error: {e}")

    # ------------------- Sub-Step 10: Defense Committee -------------------
    self.update_progress(87 + (iteration * 2), f"迭代#{iteration}: 防御委员会终审答辩")

    defense_result = None
    defense_passed = False

    if hypothesis_result and red_team_result:
        try:
            from src.agents.defense_committee_agent import DefenseCommitteeAgent
            committee = DefenseCommitteeAgent()
            defense_result = committee.execute({
                'blue_package': {
                    'hypothesis_data': hypothesis_result,
                    'fitness_data': fitness_result.to_dict() if fitness_result else {},
                },
                'red_attack': red_team_result.get('attack_report', {})
            })
            defense_passed = defense_result.get('defense_passed', False)
            logger.info(f"[Task {task_id}] 迭代#{iteration} Defense Committee: {'PASSED ✓' if defense_passed else 'FAILED ✗'}")

            if defense_passed:
                logger.info(f"[Task {task_id}] 对抗收敛成功！迭代次数: {iteration}")
            else:
                logger.info(f"[Task {task_id}] 迭代#{iteration} 未通过委员会裁决，继续下一轮...")

        except ImportError as e:
            logger.warning(f"[Task {task_id}] DefenseCommitteeAgent not available: {e}")
        except Exception as e:
            logger.error(f"[Task {task_id}] Defense Committee error: {e}")

    # 记录本次迭代历史
    iteration_history.append({
        'iteration': iteration,
        'status': 'defense_passed' if defense_passed else 'defense_failed',
        'anchor_passed': anchor_passed,
        'fitness_score': fitness_result.hybrid_fitness if fitness_result else 0.0,
        'red_team_verdict': red_team_result.get('verdict', 'N/A') if red_team_result else 'N/A',
        'defense_verdict': defense_result.get('final_verdict', 'N/A') if defense_result else 'N/A',
    })

    # 如果通过防御委员会，退出循环
    if defense_passed:
        break

    # 如果未通过且未达到最大迭代次数，继续下一轮
    if iteration < max_iterations and not defense_passed:
        logger.info(f"[Task {task_id}] 对抗继续，准备进入迭代 #{iteration + 1}...")
        continue

# 循环结束后的收敛检测
self.update_progress(89, "收敛性检测")

convergence_result = None
if hypothesis_result and defense_passed:
    try:
        from src.core.convergence_detector import ConvergenceDetector, ConvergenceState
        detector = ConvergenceDetector()
        convergence_result = detector.check_convergence(
            hypothesis_data=hypothesis_result,
            fitness_score=fitness_result.hybrid_fitness if fitness_result else 0.0,
            rigor_score=red_team_result.get('rigor_report', {}).get('rigor_score', 0.0) if red_team_result else 0.0,
            defense_verdict=defense_result.get('final_verdict', '') if defense_result else ''
        )
        logger.info(f"[Task {task_id}] Convergence state: {convergence_result.state.value}")
    except ImportError as e:
        logger.warning(f"[Task {task_id}] ConvergenceDetector not available: {e}")
    except Exception as e:
        logger.error(f"[Task {task_id}] Convergence check error: {e}")

# 如果达到最大迭代次数仍未通过，记录收敛失败
if iteration >= max_iterations and not defense_passed:
    logger.warning(f"[Task {task_id}] 对抗收敛失败: 达到最大迭代次数 {max_iterations} 仍未通过委员会裁决")
    convergence_result = type('obj', (object,), {
        'state': type('obj', (object,), {'value': 'max_iterations_exceeded'}),
        'iteration': iteration
    })()


# ==================== 辅助函数 ====================

def _build_red_team_feedback_context(red_team_result: dict, defense_result: dict) -> str:
    """
    V7.2: 构建红方反馈上下文，注入到 PI Prompt

    Args:
        red_team_result: 红方攻击结果
        defense_result: 防御委员会裁决结果

    Returns:
        str: 格式化的反馈上下文
    """
    feedback_parts = ["## 【红方团队反馈 - 需要在下一版假设中改进】\n"]

    # 红方攻击意见
    if red_team_result:
        verdict = red_team_result.get('verdict', 'unknown')
        feedback_parts.append(f"### 红方攻击结论: {verdict}\n")

        critical_flaws = red_team_result.get('critical_flaws', [])
        if critical_flaws:
            feedback_parts.append("#### 致命缺陷（必须修复）:")
            for i, flaw in enumerate(critical_flaws[:5], 1):
                feedback_parts.append(f"{i}. {flaw}")
            feedback_parts.append("")

        severe_issues = red_team_result.get('severe_issues', [])
        if severe_issues:
            feedback_parts.append("#### 严重问题（强烈建议修复）:")
            for i, issue in enumerate(severe_issues[:5], 1):
                feedback_parts.append(f"{i}. {issue}")
            feedback_parts.append("")

    # 委员会裁决意见
    if defense_result:
        final_verdict = defense_result.get('final_verdict', '')
        if final_verdict:
            feedback_parts.append(f"### 防御委员会裁决: {final_verdict}\n")

        critical_issues = defense_result.get('critical_issues', [])
        if critical_issues:
            feedback_parts.append("#### 委员会指出的关键问题:")
            for i, issue in enumerate(critical_issues[:5], 1):
                feedback_parts.append(f"{i}. {issue}")
            feedback_parts.append("")

    # 添加改进指令
    feedback_parts.extend([
        "## 【改进指令】",
        "",
        "请根据上述反馈，重新生成一个改进版的研究假设。",
        "要求：",
        "1. 针对致命缺陷和严重问题进行实质性修改",
        "2. 保持核心研究问题的价值",
        "3. 确保引用真实文献",
        "4. 提供更详细的技术路线和参数设置",
        ""
    ])

    return "\n".join(feedback_parts)
