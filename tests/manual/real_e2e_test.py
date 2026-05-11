# -*- coding: utf-8 -*-
"""
V7.5 真实端到端测试脚本

这个脚本会:
1. 提交真实的 Celery 任务
2. 调用 LLM 生成假设
3. 调用 Red Team/Blue Team
4. 执行文献检索
5. 完整的凤凰协议迭代

预计耗时: 10-30 分钟/假设
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.celery_tasks_v75 import submit_hypothesis_generation_v75, get_task_status
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 测试假设 ====================

TEST_IDEA = "利用单细胞多组学测序分析阿尔茨海默病患��小胶质细胞异质性，发现新的治疗靶点"

TEST_DOMAIN = "神经科学"


# ==================== 任务跟踪 ====================

def track_task_progress(task_id: str, timeout: int = 1800):
    """
    跟踪任务进度

    Args:
        task_id: 任务 ID
        timeout: 超时时间（秒），默认 30 分钟
    """
    start_time = time.time()
    last_update = start_time
    last_progress = ""

    print("\n" + "="*70)
    print(f"V7.5 真实端到端测试")
    print("="*70)
    print(f"\n任务 ID: {task_id}")
    print(f"提交时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试假设: {TEST_IDEA}")
    print(f"测试领域: {TEST_DOMAIN}")
    print("\n开始跟踪任务进度...")
    print("-"*70)

    progress_bar_chars = ['/', '-', '\\', '|']
    bar_idx = 0

    while True:
        # 检查超时
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"\n[TIMEOUT] 任务超过 {timeout} 秒未完成")
            break

        # 获取任务状态
        status = get_task_status(task_id)

        # 更新进度显示
        current_time = time.time()
        if current_time - last_update > 2:  # 每 2 秒更新一次
            state = status.get('state', 'UNKNOWN')
            progress = status.get('progress', {})

            # 构建进度信息
            progress_info = f"State: {state}"
            if 'current_phase' in progress:
                progress_info += f" | Phase: {progress['current_phase']}"
            if 'iteration' in progress:
                progress_info += f" | Iteration: {progress['iteration']}"
            if 'current_score' in progress:
                progress_info += f" | Score: {progress['current_score']}"

            # 动画效果
            bar_char = progress_bar_chars[bar_idx % 4]
            bar_idx += 1

            # 如果进度有变化，打印
            if progress_info != last_progress:
                elapsed_min = int(elapsed // 60)
                elapsed_sec = int(elapsed % 60)
                print(f"[{bar_char}] {elapsed_min:02d}:{elapsed_sec:02d} | {progress_info}")
                last_progress = progress_info

            last_update = current_time

        # 检查任务是否完成
        state = status.get('state', '')
        if state in ['SUCCESS', 'FAILURE', 'REVOKED']:
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            status_icon = "[OK]" if state == 'SUCCESS' else "[FAIL]"
            print(f"\n{status_icon} Task complete ({elapsed_min:02d}:{elapsed_sec:02d})")
            break

        # 短暂休眠
        time.sleep(1)

    # 获取最终结果
    final_status = get_task_status(task_id)
    return final_status


# ==================== 结果展示 ====================

def display_results(final_status: dict):
    """展示最终结果"""
    print("\n" + "="*70)
    print("最终结果")
    print("="*70 + "\n")

    state = final_status.get('state', 'UNKNOWN')
    result = final_status.get('result', {})
    error = final_status.get('error', '')

    if state == 'SUCCESS' and result:
        # Success result
        print("[OK] Task completed successfully!\n")

        # Hypothesis info
        if 'hypothesis' in result:
            hypothesis = result['hypothesis']
            print("[HYPOTHESIS] Generated research hypothesis:")
            print(f"   Title: {hypothesis.get('title', 'N/A')}")
            print(f"   Details: {hypothesis.get('details', 'N/A')[:100]}...")
            print()

        # Version evolution
        if 'version_chain' in result:
            versions = result['version_chain']
            print(f"[EVOLUTION] Version chain ({len(versions)} versions):")
            for v in versions:
                score = v.get('science_score', 0)
                passed = v.get('defense_passed', False)
                status_icon = "[OK]" if passed else "[IN PROGRESS]"
                print(f"   {status_icon} {v.get('version', 'N/A')}: {score:.1f}/10 - {v.get('type_display', 'N/A')}")
            print()

        # Score trend
        if 'score_history' in result:
            scores = result['score_history']
            print(f"[SCORE] Science Score evolution:")
            print(f"   {' -> '.join(f'{s:.1f}' for s in scores)}")
            if len(scores) >= 2:
                delta = scores[-1] - scores[0]
                print(f"   Total gain: +{delta:.1f}")
            print()

        # Promise Score
        if 'promise_score' in result:
            ps = result['promise_score']
            print(f"[PROMISE] Promise Score: {ps:.1f}/10")
            if 'promise_grade' in result:
                print(f"   Grade: {result['promise_grade']}")
            print()

        # Iteration stats
        if 'total_iterations' in result:
            print(f"[STATS] Iteration stats:")
            print(f"   Total iterations: {result['total_iterations']}")
            if 'rewrite_attempts' in result:
                print(f"   Rewrite attempts: {result['rewrite_attempts']}")
            if 'patch_attempts' in result:
                print(f"   Patch attempts: {result['patch_attempts']}")
            print()

    else:
        # Failure result
        print("[FAIL] Task failed\n")
        if error:
            print(f"Error: {error}")
        else:
            print(f"State: {state}")

    print("="*70)


# ==================== 主函数 ====================

def main(auto_confirm=False):
    """主函数"""
    print("\n" + "="*70)
    print("V7.5 Real End-to-End Test")
    print("="*70)
    print("\n[WARNING] This test will call real LLM and literature search APIs")
    print("   Estimated time: 10-30 minutes")
    print()

    # Confirm
    if not auto_confirm:
        confirm = input("Continue? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Test cancelled")
            return
    else:
        print("[AUTO] Auto-confirmed, proceeding...")

    print("\n正在提交任务...")

    # Submit task
    submission = submit_hypothesis_generation_v75(
        user_input=TEST_IDEA,
        user_domain=TEST_DOMAIN,
        session_id=f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    task_id = submission.get('task_id')
    if not task_id:
        print("[ERROR] Task submission failed")
        return

    print(f"[OK] Task submitted: {task_id}")
    print(f"  Estimated: {submission.get('estimated_duration', 'N/A')}")
    print(f"  Phoenix: {'Enabled' if submission.get('phoenix_enabled') else 'Disabled'}")

    # 跟踪进度
    final_status = track_task_progress(task_id, timeout=1800)

    # 展示结果
    display_results(final_status)

    # 保存结果
    report_path = Path(__file__).parent / "real_e2e_result.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(final_status, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {report_path}")


if __name__ == "__main__":
    import sys
    auto_confirm = '--auto' in sys.argv or '-y' in sys.argv
    try:
        main(auto_confirm=auto_confirm)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Test exception: {e}")
        import traceback
        traceback.print_exc()
