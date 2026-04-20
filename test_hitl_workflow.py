"""
测试 Human-in-the-Loop 工作流
"""
import sys
import os

sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent/src')

print("=" * 60)
print("Human-in-the-Loop 工作流测试")
print("=" * 60)

# 测试导入
print("\n[测试 1] 导入模块...")
try:
    from cli.main import ResearchCLI
    from core.orchestrator import Orchestrator
    from agents.hypothesis_agent import ChiefScientistAgent
    from agents.validation_agent import ValidationAgent
    print("[OK] 所有模块导入成功")
except Exception as e:
    print(f"[FAIL] 导入失败: {e}")
    sys.exit(1)

# 测试 Orchestrator 初始化
print("\n[测试 2] 初始化 Orchestrator...")
try:
    orchestrator = Orchestrator()
    print("[OK] Orchestrator 初始化成功")
except Exception as e:
    print(f"[FAIL] Orchestrator 初始化失败: {e}")
    sys.exit(1)

# 测试假设生成代理
print("\n[测试 3] 初始化首席科学家代理...")
try:
    hypothesis_agent = ChiefScientistAgent()
    print("[OK] 首席科学家代理初始化成功")
except Exception as e:
    print(f"[FAIL] 首席科学家代理初始化失败: {e}")
    sys.exit(1)

# 测试验证代理
print("\n[测试 4] 初始化审稿人代理...")
try:
    validation_agent = ValidationAgent()
    print("[OK] 审稿人代理初始化成功")
except Exception as e:
    print(f"[FAIL] 审稿人代理初始化失败: {e}")
    sys.exit(1)

# 模拟 Human-in-the-Loop 流程
print("\n" + "=" * 60)
print("[模拟] Human-in-the-Loop 流程演示")
print("=" * 60)

print("""
工作流程：
  步骤 1: 确定研究方向
  步骤 2: 文献侦察员搜索论文
  步骤 3: 首席科学家生成假设
  步骤 4: [暂停] 显示假设，让用户选择 (0/1/2/3)
  步骤 5: 审稿人深度评估
  步骤 6: 输出评审报告

用户交互逻辑：
  - 输入 0: 打回给首席科学家重新生成
  - 输入 1/2/3: 选中的假设进入终审阶段
""")

# 模拟假设数据
mock_hypotheses = [
    {
        'title': 'Universal Gene Expression Transformer (UGET): 跨细胞类型的基因表达预测模型',
        'description': '提出基于 Transformer 的通用基因表达预测框架，实现跨细胞类型和组织的零样本迁移',
        'paradigm_framework': '生物学基础大模型',
        'grand_challenge': '通用生物学法则',
        'rationale': '当前模型都是组织特异性的，无法泛化',
        'novelty': '首个跨细胞类型的通用表示学习框架',
        'expected_value': '发现控制基因表达的通用法则'
    },
    {
        'title': 'Physics-Informed Protein Folding: 热力学约束的蛋白质结构预测',
        'description': '将热力学定律嵌入神经网络，实现物理约束的蛋白质折叠预测',
        'paradigm_framework': '物理/化学约束深度学习',
        'grand_challenge': '可计算的生命科学',
        'rationale': '现有方法忽略物理约束，预测结果可能违反热力学定律',
        'novelty': '首个物理约束的蛋白质折叠预测框架',
        'expected_value': '提高蛋白质结构预测的准确性和可靠性'
    },
    {
        'title': 'Causal Discovery from EHR: 百万级临床数据的因果推断框架',
        'description': '使用工具变量和孟德尔随机化从 EHR 数据中发现因果关系',
        'paradigm_framework': '从相关到因果',
        'grand_challenge': '临床范式转移',
        'rationale': '观察性研究只能发现相关性，无法确定因果',
        'novelty': '首个大规模 EHR 因果发现框架',
        'expected_value': '发现颠覆临床指南的因果关系'
    }
]

print("\n" + "-" * 60)
print("模拟显示假设摘要")
print("-" * 60 + "\n")

for i, hyp in enumerate(mock_hypotheses, 1):
    print(f"[假设 {i}] {hyp['title']}")
    print(f"  前沿框架: {hyp['paradigm_framework']}")
    print(f"  摘要: {hyp['description'][:60]}...")
    print()

print("-" * 60)
print("模拟用户交互")
print("-" * 60 + "\n")

print("老板，初步假设已生成。请选择您最看好的一个进入终审阶段：")
print("输入 1, 2, 3 选择对应假设，或输入 0 让他们重新想：")

# 模拟用户选择
for choice in ['0', '1', '2', '3']:
    if choice == '0':
        print(f"\n[模拟] 用户输入: {choice}")
        print("-> 打回给首席科学家重新生成 3 个新假设...\n")
    elif choice == '2':
        print(f"[模拟] 用户输入: {choice}")
        print(f"-> 您选择了假设 {choice}: {mock_hypotheses[int(choice)-1]['title'][:40]}...")
        print("-> 正在发送给 Nature 高级编辑进行深度评估...\n")
        break
    else:
        print(f"[模拟] 用户输入: {choice} (继续尝试...)")
        continue

print("=" * 60)
print("测试完成!")
print("=" * 60)

print("""
下一步：运行 `py main.py` 启动完整的 Human-in-the-Loop 研究流程。
""")