# -*- coding: utf-8 -*-
"""
V7.5 端到端测试 - 验证输出增强功能

运行真实任务，验证新增的落地指南、创新点分析、前沿溯源分析
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.celery_tasks_v75 import submit_hypothesis_generation_v75, get_task_status


def test_enhanced_output():
    """测试增强输出功能"""

    print("\n" + "="*80)
    print("V7.5 端到端测试 - 输出增强功能验证")
    print("="*80 + "\n")

    # 测试假设
    TEST_IDEA = "使用因果推断方法分析心血管疾病风险因素，构建严格的预测模型"
    TEST_DOMAIN = "心血管疾病"

    print(f"测试假设: {TEST_IDEA}")
    print(f"测试领域: {TEST_DOMAIN}")
    print()

    # 提交任务
    print("[1/3] 提交任务...")
    submission = submit_hypothesis_generation_v75(
        user_input=TEST_IDEA,
        user_domain=TEST_DOMAIN,
        session_id=f"enhanced_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    task_id = submission.get('task_id')
    if not task_id:
        print("[ERROR] 任务提交失败")
        return False

    print(f"[OK] 任务ID: {task_id}")

    # 跟踪任务
    print("\n[2/3] 跟踪任务进度...")
    start_time = time.time()
    timeout = 600  # 10分钟

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"\n[TIMEOUT] {timeout}秒超时")
            break

        status = get_task_status(task_id)
        state = status.get('state', 'UNKNOWN')

        if state == 'SUCCESS':
            print(f"\n[OK] 任务完成 (耗时: {int(elapsed)}秒)")
            break
        elif state in ['FAILURE', 'REVOKED']:
            print(f"\n[FAIL] 任务失败: {state}")
            return False

        # 每5秒显示一次进度
        if int(elapsed) % 5 == 0:
            progress = status.get('progress', {})
            score = progress.get('current_score', 0) if isinstance(progress, dict) else 0
            print(f"  状态: {state} | 分数: {score:.1f} | 已耗时: {int(elapsed)}秒")

        time.sleep(2)

    # 验证输出
    print("\n[3/3] 验证增强输出...")
    final_status = get_task_status(task_id)
    result = final_status.get('result', {})
    payload = result.get('payload', {})

    # 检查新增的输出字段
    enhanced_fields = {
        'implementation_roadmap': '落地指南',
        'innovation_analysis': '创新点分析',
        'frontier_analysis': '前沿溯源分析'
    }

    print("\n" + "-"*60)
    print("增强输出字段检查:")
    print("-"*60)

    all_present = True
    for field_key, field_name in enhanced_fields.items():
        is_present = field_key in payload
        status_icon = "[PASS]" if is_present else "[FAIL]"
        print(f"  {status_icon} {field_name} ({field_key})")

        if is_present:
            field_data = payload[field_key]
            # 显示部分内容
            if field_key == 'implementation_roadmap':
                phases = field_data.get('phases', [])
                print(f"       阶段数: {len(phases)}")
                budget = field_data.get('budget', {})
                print(f"       预算: {budget.get('estimated_total', 'N/A')}")
            elif field_key == 'innovation_analysis':
                innovations = field_data.get('core_innovations', [])
                print(f"       核心创新点: {len(innovations)}")
                novelty = field_data.get('novelty_level', 'N/A')
                print(f"       新颖度: {novelty}")
            elif field_key == 'frontier_analysis':
                position = field_data.get('frontier_position', 'N/A')
                print(f"       前沿定位: {position[:30]}...")
        else:
            all_present = False

    # 保存完整结果
    print("\n" + "-"*60)
    output_path = project_root / "enhanced_e2e_result.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_status, f, ensure_ascii=False, indent=2)
    print(f"完整结果已保存到: {output_path}")

    # 汇总
    print("\n" + "="*80)
    if all_present:
        print("[SUCCESS] 增强输出功能验证成功！")
        print("所有新增字段均已生成并包含在输出中")
    else:
        print("[WARNING] 部分增强输出缺失")
    print("="*80 + "\n")

    return all_present


if __name__ == "__main__":
    try:
        success = test_enhanced_output()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
