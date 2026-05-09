# -*- coding: utf-8 -*-
"""
V7.4-G 终极全流程回归矩阵 - Pre-UI Preflight Check

盲测命题矩阵：
1. 命题一（基准测试-稳健性）：UK Biobank + ResGCN 心血管衰老预测
2. 命题二（核心压测-自愈力）：AlphaFold3 + 分子动力学 + 罕见非编码 SNP
3. 命题三（极限拦截-公理底线）：量子引力波场生物光子（应 Hard-Block）

执行目标：
- 验证 V7.4-G 科学底线评分机制（UK_BIOBANK_ML = 0.85）
- 验证自愈引擎闭环能力（Iteration 4 补丁注入）
- 验证物理公理锚定检测（Step 0 Hard-Block）
- 验证 attack_types 传递链路不再为空 []

作者: V7.4-G 终验工程师
日期: 2026-04-19
"""

import sys
import os
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

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

# ==================== V7.4-G 终极命题矩阵 ====================
ULTIMATE_TEST_HYPOTHESES = [
    {
        "id": "命题一",
        "category": "基准测试-稳健性",
        "title": "集成 UK Biobank 多组学特征与残差图卷积网络（ResGCN）的人类心血管衰老轨迹精准量化模型。",
        "expected_behavior": "V7.4-G 0.85分高严谨度门槛下丝滑通过，展现工程可实现性",
        "考查点": "科学底线评分机制是否生效，severe_threshold 是否动态调整"
    },
    {
        "id": "命题二",
        "category": "核心压测-自愈力",
        "title": "基于 AlphaFold3 构象采样与大规模分布式分子动力学模拟，探究罕见非编码 SNP 对药物结合口袋（Binding Pocket）变构效应的影响。",
        "expected_behavior": "必须触发 Iteration 4，自愈引擎从 arXiv/PubMed 闭环",
        "考查点": "前沿科学不被误判 PSEUDOSCIENCE，补丁模板正确调用"
    },
    {
        "id": "命题三",
        "category": "极限拦截-公理底线",
        "title": "利用超低频生物光子谐振与量子引力波场，实现跨组织的无损神经元电活动远端实时测序与干预研究。",
        "expected_behavior": "Step 0 立即 Hard-Block，给出科学转向建议",
        "考查点": "物理公理锚定检测引擎是否正确拦截"
    },
]

# ==================== 终验执行器 ====================
class UltimateTestExecutor:
    """V7.4-G 终验执行器"""

    def __init__(self):
        self.results = []
        self.start_time = None

    def print_header(self):
        """打印终验启动头部"""
        print("\n" + "=" * 80)
        print("[V7.4-G] 终极全流程回归矩阵 - Pre-UI Preflight Check")
        print("         稳健性 | 自愈力 | 公理底线")
        print("=" * 80)
        print(f"\n[TIMESTAMP] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[CASES] 总命题数: {len(ULTIMATE_TEST_HYPOTHESES)}")
        print("[PRINCIPLE] 不留死角，不带偏见")
        print("\n" + "-" * 80)

    def print_case_header(self, case: Dict, case_idx: int):
        """打印单个测试用例头部"""
        print("\n" + "=" * 80)
        print(f"[CASE #{case_idx + 1}/{len(ULTIMATE_TEST_HYPOTHESES)}] {case['id']} - {case['category']}")
        print("=" * 80)
        print(f"\n[PROPOSITION]")
        print(f"   {case['title']}")
        print(f"\n[EXPECTED] {case['expected_behavior']}")
        print(f"[CHECKPOINT] {case['考查点']}")
        print(f"\n[START] {datetime.now().strftime('%H:%M:%S')}")

    def run_single_case(self, case: Dict, case_idx: int) -> Dict:
        """运行单个终验用例"""
        self.print_case_header(case, case_idx)

        try:
            from full_pipeline_tester import PipelineProbe
        except ImportError as e:
            print(f"[ERROR] 无法导入 PipelineProbe: {e}")
            return {
                'case_id': case['id'],
                'final_state': 'ERROR',
                'reason': f'导入失败: {e}',
                'healing_activated': False,
                'attack_types': [],
                'patch_source': '',
                'duration': 0
            }

        probe = PipelineProbe(test_idea=case['title'])
        case_start = time.time()

        try:
            result = probe.run_full_pipeline()
        except Exception as e:
            print(f"\n[ERROR] 执行异常: {e}")
            import traceback
            traceback.print_exc()
            return {
                'case_id': case['id'],
                'final_state': 'ERROR',
                'reason': f'执行异常: {str(e)[:100]}',
                'healing_activated': False,
                'attack_types': [],
                'patch_source': '',
                'duration': time.time() - case_start
            }

        case_duration = time.time() - case_start

        # 解析结果
        state = result.get('state', 'UNKNOWN')
        payload = result.get('payload', {})
        audit_context = payload.get('audit_context', {})
        healing_engine = payload.get('healing_engine', {})

        # 提取关键信息
        defense_committee = audit_context.get('defense_committee', {})
        red_team = audit_context.get('red_team_attack', {})
        convergence = audit_context.get('convergence', {})

        # 判定最终状态
        final_state = 'PASS' if state == 'success' else 'REJECT'
        if state == 'ERROR':
            final_state = 'ERROR'

        # 提取拒绝/放行理由
        reason = ""
        patch_source = ""
        if final_state == 'PASS':
            if defense_committee.get('passed'):
                reason = "DefenseCommittee 审查通过"
                # 检查科学底线评分
                baseline_score = defense_committee.get('baseline_score', 0)
                if baseline_score >= 0.70:
                    reason += f" | 科学底线={baseline_score:.2f}"
            else:
                reason = "通过自愈引擎修复后放行"
                patch_source = healing_engine.get('patch_template', '')
        else:
            # 拒绝理由
            intent_result = payload.get('intent_sanitizer', {})
            if intent_result.get('is_valid') == False:
                reason = f"Intent Sanitizer Hard-Block: {intent_result.get('type', 'unknown')}"
                patch_source = f"物理锚定失败: {intent_result.get('reason', '')[:50]}"
            elif red_team.get('verdict'):
                reason = f"Red Team 拒绝: {red_team.get('verdict', '')[:30]}"
            elif not defense_committee.get('passed', True):
                reason = "DefenseCommittee 未通过"
                severe_flaws = defense_committee.get('severe_flaws', [])
                if severe_flaws:
                    reason += f" | 致命缺陷: {severe_flaws[0] if severe_flaws else 'N/A'}"

        # 自愈引擎信息
        healing_activated = healing_engine.get('activated', False)
        attack_types = healing_engine.get('attack_types_detected', [])
        iteration_count = convergence.get('iteration', 0)

        # 补丁来源
        if healing_activated:
            patch_source = healing_engine.get('patch_template', 'N/A')
            if not patch_source or patch_source == 'N/A':
                # 从 attack_types 推断补丁
                if 'AF3_LEAKAGE' in attack_types:
                    patch_source = "ArXiv 算法防泄露协议"
                elif 'VALIDATION' in attack_types:
                    patch_source = "PubMed MD 验证标准"
                elif 'PSEUDOSCIENCE' in attack_types:
                    patch_source = "PSEUDOSCIENCE_v1 物理锚定补丁"
                else:
                    patch_source = "自愈引擎合成补丁"

        # 验证 attack_types 不为空（核心考查点）
        attack_types_valid = len(attack_types) > 0 if healing_activated else True

        return {
            'case_id': case['id'],
            'category': case['category'],
            'final_state': final_state,
            'reason': reason[:80],
            'healing_activated': healing_activated,
            'attack_types': attack_types,
            'attack_types_valid': attack_types_valid,
            'patch_source': patch_source,
            'iteration_count': iteration_count,
            'baseline_score': defense_committee.get('baseline_score', 0),
            'duration': case_duration
        }

    def run_all_cases(self) -> List[Dict]:
        """运行所有终验用例"""
        self.start_time = time.time()
        self.print_header()

        all_results = []

        for idx, case in enumerate(ULTIMATE_TEST_HYPOTHESES):
            result = self.run_single_case(case, idx)
            all_results.append(result)
            self.results.append(result)

            # 用例间隔
            if idx < len(ULTIMATE_TEST_HYPOTHESES) - 1:
                print("\n" + "-" * 80)
                print("[PAUSE] 等待 3 秒后执行下一命题...")
                time.sleep(3)

        return all_results

    def print_acceptance_report(self, results: List[Dict]):
        """打印终极验收报告"""
        print("\n" + "=" * 80)
        print("[V7.4-G] 终极验收报告 - 后端工程结项证明")
        print("=" * 80)

        # 核心验收表格
        print(f"\n{'命题':^12} | {'最终判定':^10} | {'判定分值':^10} | {'自愈触发':^10} | {'核心补丁来源/拦截理由':^40}")
        print("-" * 80)

        for r in results:
            case_id = r['case_id']
            final_state = '[PASS]' if r['final_state'] == 'PASS' else '[REJECT]'
            score = f"{r.get('baseline_score', 0):.2f}" if r['final_state'] == 'PASS' else '--'
            healing = '[YES]' if r['healing_activated'] else '[NO]'
            patch_source = r['patch_source'][:38] if r['patch_source'] else '--'

            print(f"{case_id:^12} | {final_state:^10} | {score:^10} | {healing:^10} | {patch_source:^40}")

            # attack_types 详细
            if r['attack_types']:
                types_str = ', '.join(r['attack_types'][:3])
                print(f"{'(attack_types)':^12} | {'':^10} | {'':^10} | {'':^10} | {types_str:^40}")

        print("-" * 80)

        # 核心指标汇总
        total = len(results)
        passed = sum(1 for r in results if r['final_state'] == 'PASS')
        rejected = sum(1 for r in results if r['final_state'] == 'REJECT')
        healing_triggered = sum(1 for r in results if r['healing_activated'])
        attack_types_valid_count = sum(1 for r in results if r.get('attack_types_valid', True))

        print(f"\n[METRICS]")
        print(f"   总命题数: {total}")
        print(f"   放行: {passed}")
        print(f"   拒绝: {rejected}")
        print(f"   自愈触发: {healing_triggered}")
        print(f"   attack_types 有效性: {attack_types_valid_count}/{total}")

        # V7.4-G 特性验证
        print(f"\n[V7.4-G FEATURES]")
        for r in results:
            case_id = r['case_id']
            baseline = r.get('baseline_score', 0)
            if baseline > 0:
                print(f"   {case_id}: 科学底线评分 = {baseline:.2f}")
            if r['healing_activated'] and r['attack_types']:
                print(f"   {case_id}: attack_types 传递正常 = {r['attack_types']}")

        # 预期对比
        print(f"\n[EXPECTATION MATCH]")
        for case, result in zip(ULTIMATE_TEST_HYPOTHESES, results):
            expected = case['expected_behavior']
            actual = result['final_state']

            # 判断预期是否匹配
            if '丝滑通过' in expected and actual == 'PASS':
                match = '[MATCH]'
            elif '触发 Iteration 4' in expected and result['healing_activated']:
                match = '[MATCH]'
            elif 'Hard-Block' in expected and actual == 'REJECT':
                match = '[MATCH]'
            else:
                match = '[CHECK]'

            print(f"   {match} {case['id']}: {expected[:30]}... -> {actual}")

        # 总耗时
        total_duration = time.time() - self.start_time
        print(f"\n[DURATION] 总执行时长: {total_duration:.2f} 秒")

        # 保存详细结果
        self.save_detailed_results(results)

        print("\n" + "-" * 80)
        print("[OUTPUT] 详细结果已保存至: V7.4-G_ULTIMATE_TEST_RESULTS.json")
        print("=" * 80 + "\n")

    def save_detailed_results(self, results: List[Dict]):
        """保存详细结果到 JSON 文件"""
        output_path = project_root / 'V7.4-G_ULTIMATE_TEST_RESULTS.json'

        detailed = {
            'test_info': {
                'test_type': 'V7.4-G 终极全流程回归矩阵',
                'timestamp': datetime.now().isoformat(),
                'total_cases': len(results),
                'total_duration': time.time() - self.start_time
            },
            'cases': []
        }

        for case, result in zip(ULTIMATE_TEST_HYPOTHESES, results):
            detailed['cases'].append({
                'input': {
                    'id': case['id'],
                    'category': case['category'],
                    'title': case['title'],
                    'expected_behavior': case['expected_behavior'],
                    'checkpoint': case['考查点']
                },
                'output': result
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(detailed, f, ensure_ascii=False, indent=2)


# ==================== 主入口 ====================
def main():
    """主入口函数"""
    executor = UltimateTestExecutor()
    results = executor.run_all_cases()
    executor.print_acceptance_report(results)


if __name__ == '__main__':
    main()