# -*- coding: utf-8 -*-
"""
V7.5 多领域并行真实测试

测试领域:
1. 心血管 - 心肌缺血再灌注损伤
2. 癌症 - CAR-T 细胞治疗实体瘤
3. 神经科学 - 帕金森病 α-突触核蛋白
4. 代谢 - NAFLD 脂肪肝
5. 衰老 - 端粒缩短与细胞衰老
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.celery_tasks_v75 import submit_hypothesis_generation_v75, get_task_status

# ==================== 测试假设列表 ====================

TEST_HYPOTHESES = [
    {
        "field": "心血管",
        "idea": "靶向线粒体通透性转换孔 (mPTP) 抑制心肌缺血再灌注损伤，通过环孢素A类似物减少心肌细胞死亡",
        "domain": "心血管疾病"
    },
    {
        "field": "癌症",
        "idea": "工程化 CAR-T 细胞表达 PD-1 敲除和 TGF-β 受体显性负性，克服实体瘤免疫抑制微环境",
        "domain": "癌症免疫治疗"
    },
    {
        "field": "神经科学",
        "idea": "使用免疫疗法清除帕金森病中聚集的 α-突触核蛋白，通过单克隆抗体促进小胶质细胞吞噬",
        "domain": "神经退行性疾病"
    },
    {
        "field": "代谢",
        "idea": "靶向 FXR 受体和 FGF21 信号轴改善非酒精性脂肪肝病 (NAFLD) 的肝脏脂肪变性和炎症",
        "domain": "代谢疾病"
    },
    {
        "field": "衰老",
        "idea": "通过端粒酶激活和 senolytics 药物联合清除衰老细胞，延缓多组织器官的衰老相关功能障碍",
        "domain": "衰老生物学"
    }
]

# ==================== 任务提交 ====================

def submit_all_tasks():
    """提交所有测试任务"""
    print("\n" + "="*80)
    print("V7.5 Multi-Domain Real Test")
    print("="*80)
    print(f"\nTest Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Hypotheses: {len(TEST_HYPOTHESES)}")
    print()

    tasks = []
    for i, hypothesis in enumerate(TEST_HYPOTHESES, 1):
        print(f"[{i}/{len(TEST_HYPOTHESES)}] Submitting: {hypothesis['field']}")

        submission = submit_hypothesis_generation_v75(
            user_input=hypothesis['idea'],
            user_domain=hypothesis['domain'],
            session_id=f"multifield_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}"
        )

        task_id = submission.get('task_id')
        if task_id:
            tasks.append({
                'index': i,
                'field': hypothesis['field'],
                'idea': hypothesis['idea'],
                'domain': hypothesis['domain'],
                'task_id': task_id,
                'submit_time': datetime.now().isoformat(),
                'status': 'PENDING'
            })
            print(f"    Task ID: {task_id}")
        else:
            print(f"    [ERROR] Submission failed")
        print()

    return tasks


# ==================== 进度跟踪 ====================

def track_all_tasks(tasks, timeout=1800):
    """跟踪所有任务进度"""
    start_time = time.time()

    print("="*80)
    print("Tracking Task Progress...")
    print("="*80)
    print()

    # 进度条字符
    bars = ['|', '/', '-', '\\']

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"\n[TIMEOUT] {timeout} seconds elapsed")
            break

        all_done = True
        current_time = datetime.now().strftime('%H:%M:%S')

        # 每 5 秒更新一次显示
        print(f"[{current_time}] ", end='')

        for task in tasks:
            status = get_task_status(task['task_id'])
            state = status.get('state', 'UNKNOWN')
            task['status'] = state
            task['result'] = status

            if state not in ['SUCCESS', 'FAILURE', 'REVOKED']:
                all_done = False

            # 显示状态
            if state == 'SUCCESS':
                icon = '[OK]'
            elif state == 'FAILURE':
                icon = '[FAIL]'
            elif state == 'PROGRESS':
                icon = '[>>]'
            elif state == 'STARTED':
                icon = '[...]'
            else:
                icon = '[...]'

            progress = status.get('progress', {})
            if isinstance(progress, dict):
                score = progress.get('current_score', 0)
                iteration = progress.get('iteration', 0)
            else:
                score = 0
                iteration = 0

            print(f"{task['field']}: {icon}", end=' ')
            if score > 0:
                print(f"({iteration}it, {score:.1f})", end=' ')
            else:
                print(f"({state})", end=' ')

        print()

        if all_done:
            print("\n[COMPLETE] All tasks finished!")
            break

        time.sleep(5)

    return tasks


# ==================== 结果展示 ====================

def display_results(tasks):
    """展示所有结果"""
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80 + "\n")

    for task in tasks:
        field = task['field']
        state = task['status']
        result = task.get('result', {})

        print(f"{'='*80}")
        print(f"Field: {field}")
        print(f"Idea: {task['idea'][:60]}...")
        print(f"Task ID: {task['task_id']}")
        print(f"State: {state}")
        print(f"{'='*80}")

        if state == 'SUCCESS' and result:
            payload = result.get('result', {}).get('payload', {})

            # Hypothesis
            hypothesis = payload.get('hypothesis', {})
            if hypothesis:
                print(f"\n[HYPOTHESIS]")
                print(f"  Title: {hypothesis.get('title', 'N/A')[:80]}...")
                print(f"  Version: {hypothesis.get('version', 'N/A')}")

            # Fitness
            fitness = payload.get('fitness', {})
            if fitness:
                score = fitness.get('hybrid_fitness', 0)
                vector_score = fitness.get('vector_novelty_score', 0)
                print(f"\n[FITNESS]")
                print(f"  Hybrid Score: {score:.2f}/10")
                print(f"  Vector Novelty: {vector_score:.2f}/10")

            # Audit Context
            audit = payload.get('audit_context', {})
            if audit:
                iterations = audit.get('iterations', 0)
                patches = audit.get('patches', 0)
                score_history = audit.get('score_history', [])
                print(f"\n[AUDIT]")
                print(f"  Iterations: {iterations}")
                print(f"  Patches: {patches}")
                if score_history:
                    print(f"  Score Evolution: {' -> '.join(f'{s:.1f}' for s in score_history)}")

            # Phoenix Protocol
            phoenix = result.get('phoenix_protocol', {})
            if phoenix:
                phoenix_state = phoenix.get('final_state', 'N/A')
                print(f"\n[PHOENIX]")
                print(f"  Final State: {phoenix_state}")

            # Promise Score
            promise = result.get('promise_score', {})
            if promise:
                total = promise.get('total_score', 0)
                grade = promise.get('grade', 'N/A')
                print(f"\n[PROMISE]")
                print(f"  Score: {total:.2f}/10")
                print(f"  Grade: {grade}")

        else:
            print(f"\n[ERROR] Task failed or incomplete")
            if result.get('error'):
                print(f"  Error: {result.get('error')}")

        print()

    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    success_count = sum(1 for t in tasks if t['status'] == 'SUCCESS')
    fail_count = sum(1 for t in tasks if t['status'] == 'FAILURE')
    pending_count = sum(1 for t in tasks if t['status'] not in ['SUCCESS', 'FAILURE'])

    print(f"Total: {len(tasks)}")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Pending/Other: {pending_count}")
    print()

    # Calculate average scores
    scores = []
    for task in tasks:
        if task['status'] == 'SUCCESS':
            payload = task.get('result', {}).get('result', {}).get('payload', {})
            fitness = payload.get('fitness', {})
            score = fitness.get('hybrid_fitness', 0)
            if score > 0:
                scores.append(score)

    if scores:
        avg_score = sum(scores) / len(scores)
        print(f"Average Hybrid Fitness Score: {avg_score:.2f}/10")

    print("="*80 + "\n")


# ==================== 主函数 ====================

def main():
    """主函数"""
    # Submit all tasks
    tasks = submit_all_tasks()

    if not tasks:
        print("[ERROR] No tasks submitted")
        return

    print(f"\n[INFO] {len(tasks)} tasks submitted successfully")
    print("[INFO] Starting progress tracking...\n")

    # Track all tasks
    tasks = track_all_tasks(tasks, timeout=1800)

    # Display results
    display_results(tasks)

    # Save results
    report_path = Path(__file__).parent / "multifield_test_results.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    print(f"Results saved to: {report_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[Test interrupted by user]")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
