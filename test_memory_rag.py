"""
测试永久记忆与RAG功能
"""
import sys
import os
from datetime import datetime

# 设置输出编码
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

print("=" * 60)
print("永久记忆与RAG功能测试")
print("=" * 60)

# ==================== 测试 1: memory_manager 基本功能 ====================
print("\n[测试 1] memory_manager 基本功能")

try:
    from memory_manager import MemoryManager, save_to_memory, search_past_literature, get_memory_stats
    print("[OK] memory_manager 导入成功")
except Exception as e:
    print(f"[FAIL] 导入失败: {e}")
    sys.exit(1)

# 初始化记忆管理器
try:
    manager = MemoryManager()
    print("[OK] 记忆管理器初始化成功")
except Exception as e:
    print(f"[FAIL] 初始化失败: {e}")
    sys.exit(1)

# 测试存储
test_text = """
单细胞图神经网络在生物医学中的应用研究

摘要：近年来，单细胞RNA测序技术的快速发展使得研究者能够在单细胞分辨率下深入理解生物系统。
图神经网络(GNN)作为一种强大的深度学习工具，已被广泛应用于单细胞数据分析领域。
本文系统综述了GNN在单细胞聚类、细胞类型识别、基因调控网络推断等关键任务中的应用。

主要发现：
1. GNN能有效捕捉细胞之间的拓扑关系和相似性结构
2. 结合注意力机制的GNN可以识别关键细胞亚群
3. 空间转录组数据与GNN结合可实现细胞空间定位预测

结论：图神经网络为单细胞数据分析提供了新的计算范式，有望推动精准医学的发展。
"""

test_metadata = {
    'doi': '10.1234/test.gnn.singlecell.2024',
    'title': '单细胞图神经网络综述论文',
    'source': 'test_script',
    'fetch_time': datetime.now().isoformat()
}

print("\n测试存储功能...")
save_result = save_to_memory(test_text, test_metadata)
if save_result.get('success'):
    print(f"[OK] 存储成功: {save_result.get('chunks_saved')} 个切片")
else:
    print(f"[FAIL] 存储失败: {save_result.get('message')}")

# 测试搜索
print("\n测试搜索功能...")
search_queries = [
    "单细胞图神经网络的应用",
    "GNN细胞聚类方法",
    "空间转录组分析"
]

for query in search_queries:
    search_result = search_past_literature(query, n_results=3)
    if search_result.get('success'):
        print(f"[OK] 搜索 '{query[:30]}...' 成功: {len(search_result.get('results', []))} 条结果")
        for i, r in enumerate(search_result.get('results', []), 1):
            print(f"  [{i}] DOI: {r.get('doi')}, 相关性: {r.get('relevance_score', 0):.2f}")
            print(f"      内容预览: {r.get('text', '')[:80]}...")
    else:
        print(f"[FAIL] 搜索失败: {search_result.get('message')}")

# 查看统计
print("\n记忆库统计信息:")
stats = get_memory_stats()
print(f"  总切片数: {stats.get('total_chunks')}")
print(f"  独立DOI数: {stats.get('unique_dois')}")
print(f"  数据库路径: {stats.get('db_path')}")

# ==================== 测试 2: tools.py 自动存储功能 ====================
print("\n" + "=" * 60)
print("[测试 2] tools.py 自动存储功能")

try:
    from tools import AutoPaperFetcher
    print("[OK] AutoPaperFetcher 导入成功")
except Exception as e:
    print(f"[FAIL] 导入失败: {e}")

# ==================== 测试 3: hypothesis_agent 记忆搜索 ====================
print("\n" + "=" * 60)
print("[测试 3] hypothesis_agent 记忆搜索功能")

sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent/src')
try:
    from agents.hypothesis_agent import ChiefScientistAgent
    print("[OK] ChiefScientistAgent 导入成功")

    # 测试记忆搜索方法
    print("\n测试 _search_memory_for_context 方法...")
    # 创建一个简单的测试（不实际初始化完整agent，因为需要API key���
    agent_test = ChiefScientistAgent()
    memory_context = agent_test._search_memory_for_context("单细胞图神经网络研究")

    print(f"搜索状态: {memory_context.get('success')}")
    print(f"摘要: {memory_context.get('summary')}")
    if memory_context.get('results'):
        print(f"找到 {len(memory_context.get('results'))} 条历史记录")

except Exception as e:
    print(f"[FAIL] 测试失败: {e}")

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)