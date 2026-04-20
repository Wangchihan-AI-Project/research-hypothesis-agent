# -*- coding: utf-8 -*-
"""
V7.4-D 全局后端盲测脚本

盲测命题矩阵：
1. 命题一（临床预测）：UK Biobank + XGBoost 预测早发性2型糖尿病
2. 命题二（前沿交叉）：AlphaFold3 + 图神经网络预测罕见突变蛋白-配体结合
3. 命题三（边界测试）：量子引力 + 跨时空生物信号监测（伪科学）

执行目标：
- 零预设全局压力测试
- 验证系统自主识别课题严谨性边界
- 完整对抗与自愈流程验证

作者: V7.4-D 盲测工程师
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

# ==================== 盲测命题矩阵 ====================
BLIND_TEST_HYPOTHESES = [
    {
        "id": "命题一",
        "category": "临床预测",
        "title": "基于 UK Biobank 多组学数据与集成梯度提升树（XGBoost）的早发性 2 型糖尿病风险评估框架。",
        "expected_behavior": "合理学术课题，应通过审查"
    },
    {
        "id": "命题二",
        "category": "前沿交叉",
        "title": "利用 AlphaFold3 预测人类罕见致病突变引起的蛋白-配体结合能变化，并结合深度图神经网络进行小分子筛选。",
        "expected_behavior": "涉及 AF3 数据泄露与物理验证风险，可能触发自愈"
    },
    {
        "id": "命题三",
        "category": "边界测试",
        "title": "基于量子引力效应的跨时空生物分子信号实时监测与远端意识干扰建模研究。",
        "expected_behavior": "极端非学术假设，应被拒稿"
    },
]

# ==================== 盲测执行器 ====================
class BlindTestExecutor:
    """V7.4-D 盲测执行器"""

    def __init__(self):
        self.results = []
        self.start_time = None

    def print_header(self):
        """打印盲测启动头部"""
        print("\n" + "=" * 80)
        print("╔══════════════════════════════════════════════════════════════════════════════╗")
        print("║                 V7.4-D 全局后端盲测 - 回归验证                                    ║")
        print("║              零预设压力测试 | 严谨性边界识别 | 自愈闭环验证                          ║")
        print("╚══════════════════════════════════════════════════════════════════════════════╝")
        print("=" * 80)
        print(f"\n⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🧪 盲测命题数量: {len(BLIND_TEST_HYPOTHESES)}")
        print(f"⚠️  测试原则: 不设预期，只看真相")
        print("\n" + "-" * 80)

    def print_case_header(self, case: Dict, case_idx: int):
        """打印单个测试用例头部"""
        print("\n" + "=" * 80)
        print(f"╔══════════════════════════════════════════════════════════════════════════════╗")
        print(f"║  盲测用例 #{case_idx + 1}/{len(BLIND_TEST_HYPOTHESES)}: {case['id']} - {case['category']}                  ║")
        print(f"╚══════════════════════════════════════════════════════════════════════════════╝")
        print("=" * 80)
        print(f"\n📝 研究命题:")
        print(f"   {case['title']}")
        print(f"\n⏱️  开始时间: {datetime.now().strftime('%H:%M:%S')}")

    def run_single_case(self, case: Dict, case_idx: int) -> Dict:
        """
        运行单个盲测用例

        Args:
            case: 测试用例配置
            case_idx: 用例索引

        Returns:
            Dict: 测试结果
        """
        self.print_case_header(case, case_idx)

        # 导入 PipelineProbe
        try:
            from full_pipeline_tester import PipelineProbe
        except ImportError as e:
            print(f"❌ 无法导入 PipelineProbe: {e}")
            return {
                'case_id': case['id'],
                'final_state': 'ERROR',
                'reason': f'导入失败: {e}',
                'healing_activated': False,
                'retrieval_sources': [],
                'duration': 0
            }

        # 创建探针并执行
        probe = PipelineProbe(test_idea=case['title'])
        case_start = time.time()

        try:
            result = probe.run_full_pipeline()
        except Exception as e:
            print(f"\n❌ 执行异常: {e}")
            import traceback
            traceback.print_exc()
            return {
                'case_id': case['id'],
                'final_state': 'ERROR',
                'reason': f'执行异常: {str(e)[:100]}',
                'healing_activated': False,
                'retrieval_sources': [],
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
        if final_state == 'PASS':
            reason = "通过防御委员会审查"
        else:
            # 从红方或防御委员会提取拒绝理由
            if red_team.get('verdict'):
                reason += f"红方裁决: {red_team.get('verdict')}"
            if defense_committee:
                passed = defense_committee.get('passed', True)
                if not passed:
                    reason += " | 防御委员会未通过"

        # 自愈引擎信息
        healing_activated = healing_engine.get('activated', False)
        retrieval_count = healing_engine.get('retrieval_count', 0)
        patch_count = healing_engine.get('patch_count', 0)
        attack_types = healing_engine.get('attack_types_detected', [])

        # 检索源（从 attack_types 推断）
        retrieval_sources = []
        if attack_types:
            # 根据攻击类型推断可能的数据源
            if 'AF3_LEAKAGE' in attack_types:
                retrieval_sources.extend(['ArXiv', 'PubMed'])
            if 'LEAKAGE' in attack_types:
                retrieval_sources.extend(['ArXiv', 'IEEE'])
            if 'BIAS' in attack_types:
                retrieval_sources.extend(['PubMed'])
            if 'DYNAMIC_VALIDATION' in attack_types:
                retrieval_sources.extend(['UK Biobank'])
            # 去重
            retrieval_sources = list(set(retrieval_sources))

        # 返回结果
        return {
            'case_id': case['id'],
            'category': case['category'],
            'final_state': final_state,
            'reason': reason[:100],
            'healing_activated': healing_activated,
            'retrieval_count': retrieval_count,
            'patch_count': patch_count,
            'attack_types': attack_types,
            'retrieval_sources': retrieval_sources,
            'iteration_count': convergence.get('iteration', 0),
            'duration': case_duration
        }

    def run_all_cases(self) -> List[Dict]:
        """运行所有盲测用例"""
        self.start_time = time.time()
        self.print_header()

        all_results = []

        for idx, case in enumerate(BLIND_TEST_HYPOTHESES):
            result = self.run_single_case(case, idx)
            all_results.append(result)
            self.results.append(result)

            # 用例间隔
            if idx < len(BLIND_TEST_HYPOTHESES) - 1:
                print("\n" + "-" * 80)
                print("⏸️  等待 3 秒后执行下一个用例...")
                time.sleep(3)

        return all_results

    def print_anonymous_report(self, results: List[Dict]):
        """打印匿名化体检表"""
        print("\n" + "=" * 80)
        print("╔══════════════════════════════════════════════════════════════════════════════╗")
        print("║                    V7.4-D 盲测匿名化体检表                                        ║")
        print("╚══════════════════════════════════════════════════════════════════════════════╝")
        print("=" * 80)

        print(f"\n┌{'─' * 78}┐")
        print(f"│ {'命题编号':^12} │ {'最终判定状态':^14} │ {'核心拒绝/放行理由':^30} │ {'是否触发自愈':^12} │")
        print(f"├{'─' * 78}┤")

        for r in results:
            case_id = r['case_id']
            final_state = r['final_state']
            reason = r['reason'][:28] + '..' if len(r['reason']) > 30 else r['reason']
            healing = '✅ 是' if r['healing_activated'] else '❌ 否'

            # 状态颜色
            state_display = final_state
            if final_state == 'PASS':
                state_display = '✅ 放行'
            elif final_state == 'REJECT':
                state_display = '❌ 拒绝'
            else:
                state_display = '⚠️  错误'

            print(f"│ {case_id:^12} │ {state_display:^14} │ {reason:^30} │ {healing:^12} │")

            # 如果有自愈，打印检索源
            if r['healing_activated']:
                sources = ', '.join(r.get('retrieval_sources', []))
                print(f"│ {'(检索源)':^12} │ {'':^14} │ {sources:^30} │ {'':^12} │")

        print(f"└{'─' * 78}┘")

        # 汇总统计
        total = len(results)
        passed = sum(1 for r in results if r['final_state'] == 'PASS')
        rejected = sum(1 for r in results if r['final_state'] == 'REJECT')
        error = sum(1 for r in results if r['final_state'] == 'ERROR')
        healing_triggered = sum(1 for r in results if r['healing_activated'])

        print(f"\n📊 盲测统计:")
        print(f"   • 总测试用例: {total}")
        print(f"   • 放行: {passed}")
        print(f"   • 拒绝: {rejected}")
        print(f"   • 错误: {error}")
        print(f"   • 自愈触发: {healing_triggered}")

        # 预期对比（仅显示是否与预期行为一致）
        print(f"\n🎯 预期行为对比:")
        for idx, (case, result) in enumerate(zip(BLIND_TEST_HYPOTHESES, results)):
            expected = case.get('expected_behavior', '')
            actual = result['final_state']
            match = '✅' if (
                ('通过' in expected and actual == 'PASS') or
                ('拒稿' in expected and actual == 'REJECT') or
                ('应被拒稿' in expected and actual == 'REJECT')
            ) else '❓'

            print(f"   {match} {case['id']}: {expected} → {actual}")

        # 总耗时
        total_duration = time.time() - self.start_time
        print(f"\n⏱️  总执行时长: {total_duration:.2f} 秒")

        # 保存详细结果
        self.save_detailed_results(results)

        print("\n" + "-" * 80)
        print("✅ 盲测完成。详细结果已保存至: V7.4-D_BLIND_TEST_RESULTS.json")
        print("=" * 80 + "\n")

    def save_detailed_results(self, results: List[Dict]):
        """保存详细结果到 JSON 文件"""
        output_path = project_root / 'V7.4-D_BLIND_TEST_RESULTS.json'

        detailed = {
            'test_info': {
                'test_type': 'V7.4-D 全局后端盲测',
                'timestamp': datetime.now().isoformat(),
                'total_cases': len(results),
                'total_duration': time.time() - self.start_time
            },
            'cases': []
        }

        for case, result in zip(BLIND_TEST_HYPOTHESES, results):
            detailed['cases'].append({
                'input': {
                    'id': case['id'],
                    'category': case['category'],
                    'title': case['title'],
                    'expected_behavior': case.get('expected_behavior', '')
                },
                'output': result
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(detailed, f, ensure_ascii=False, indent=2)


# ==================== 主入口 ====================
def main():
    """主入口函数"""
    executor = BlindTestExecutor()
    results = executor.run_all_cases()
    executor.print_anonymous_report(results)


if __name__ == '__main__':
    main()
