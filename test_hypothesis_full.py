# -*- coding: utf-8 -*-
"""
完整测试 - 假设生成和验证
"""
import sys
import os
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

from src.core.orchestrator import Orchestrator
from src.core.db_manager import get_db_manager
from src.core.database import Hypothesis

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 80)
print("研究假设生成系统 - 假设生成与验证测试")
print("=" * 80)

# 初始化协调器
orchestrator = Orchestrator()

# 1. 启动会话
print("\n[步骤1] 启动研究会话...")
session_result = orchestrator.start_session("CRISPR gene editing therapy")
print(f"  会话ID: {session_result['session_id']}")

# 2. 搜索论文
print("\n[步骤2] 搜索论文...")
search_result = orchestrator.search_papers("CRISPR gene therapy", max_results=3)
if search_result['success']:
    papers = search_result['papers']
    print(f"  找到 {len(papers)} 篇论文")
    for i, p in enumerate(papers[:3], 1):
        print(f"  [{i}] {p.get('title', 'N/A')[:60]}...")
else:
    print(f"  搜索失败: {search_result.get('error')}")
    sys.exit(1)

# 3. 生成假设
print("\n[步骤3] 生成假设...")
hypothesis_result = orchestrator.generate_hypotheses(
    papers=papers,
    research_field="基因编辑治疗",
    focus_areas=["CRISPR", "基因疗法"]
)

if hypothesis_result['success']:
    hypotheses = hypothesis_result['hypotheses']
    print(f"  生成 {len(hypotheses)} 个假设")

    for i, h in enumerate(hypotheses, 1):
        print(f"\n  [假设 {i}]")
        print(f"    ID: {h.get('id', 'N/A')}")
        print(f"    标题: {h.get('title', 'N/A')[:60]}...")
        print(f"    描述: {h.get('description', 'N/A')[:80]}...")
        print(f"    新颖性: {h.get('novelty', 'N/A')[:60]}...")
else:
    print(f"  假设生成失败: {hypothesis_result.get('error')}")
    print(f"  详情: {hypothesis_result}")

# 4. 获取假设ID并验证
print("\n[步骤4] 验证假设...")
hypothesis_ids = hypothesis_result.get('hypothesis_ids', [])
if hypothesis_ids:
    for hyp_id in hypothesis_ids[:2]:  # 只验证前2个
        print(f"\n  验证假设 ID: {hyp_id}")
        validation_result = orchestrator.validate_hypothesis(hyp_id)

        if validation_result['success']:
            print(f"    可行性评分: {validation_result.get('feasibility_score', 'N/A')}")
            print(f"    新颖性评分: {validation_result.get('novelty_score', 'N/A')}")
            print(f"    技术性评分: {validation_result.get('technical_score', 'N/A')}")
        else:
            print(f"    验证失败: {validation_result.get('error')}")
else:
    print("  没有假设ID")

# 5. 查询数据库中的假设
print("\n[步骤5] 查询数据库中的假设...")
db_manager = get_db_manager()
with db_manager.get_session() as session:
    all_hypotheses = session.query(Hypothesis).all()
    print(f"  数据库中共有 {len(all_hypotheses)} 个假设")

    for h in all_hypotheses[-3:]:  # 显示最新的3个
        print(f"\n  假设 ID: {h.id}")
        print(f"    标题: {h.title[:50]}...")
        print(f"    验证状态: {h.validation_status or 'pending'}")
        print(f"    可行性: {h.feasibility_score or 'N/A'}")
        print(f"    新颖性: {h.novelty_score or 'N/A'}")
        print(f"    技术性: {h.technical_score or 'N/A'}")

# 6. 技术分析
print("\n[步骤6] 技术分析...")
if hypothesis_ids:
    hyp_id = hypothesis_ids[0]
    print(f"  分析假设 ID: {hyp_id}")
    tech_result = orchestrator.analyze_technology(hyp_id)

    if tech_result['success']:
        print(f"    技术分析完成")
        print(f"    所需技术: {tech_result.get('required_techniques', 'N/A')[:60]}...")
        print(f"    时间预估: {tech_result.get('estimated_timeline', 'N/A')}")
    else:
        print(f"    分析失败: {tech_result.get('error')}")

# 7. 完成会话
print("\n[步骤7] 完成会话...")
complete_result = orchestrator.complete_session()
print(f"  搜索论文: {complete_result['summary']['papers_found']} 篇")
print(f"  生成假设: {complete_result['summary']['hypotheses_generated']} 个")
print(f"  验证假设: {complete_result['summary']['hypotheses_validated']} 个")

print("\n" + "=" * 80)
print("测试完成!")
print("=" * 80)
