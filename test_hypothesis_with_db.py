# -*- coding: utf-8 -*-
"""
使用数据库论文测试假设生成
"""
import sys
import os
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

from src.core.orchestrator import Orchestrator
from src.core.db_manager import get_db_manager
from src.core.database import Hypothesis, Paper
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 80)
print("假设生成与验证测试 (使用数据库论文)")
print("=" * 80)

# 初始化
orchestrator = Orchestrator()
db_manager = get_db_manager()

# 1. 从数据库获取论文
print("\n[步骤1] 从数据库获取论文...")
with db_manager.get_session() as session:
    papers = session.query(Paper).limit(5).all()
    print(f"  找到 {len(papers)} 篇论文")

    papers_data = []
    for p in papers:
        papers_data.append({
            'id': p.id,
            'pmid': p.pmid,
            'title': p.title,
            'abstract': p.abstract,
            'journal': p.journal,
            'publication_date': p.publication_date
        })
        print(f"  - {p.title[:50]}... (PMID: {p.pmid})")

# 2. 生成假设
print("\n[步骤2] 生成假设...")
hypothesis_result = orchestrator.generate_hypotheses(
    papers=papers_data,
    research_field="机器学习在生物医学中的应用",
    focus_areas=["机器学习", "生物信息学"]
)

if hypothesis_result['success']:
    hypotheses = hypothesis_result['hypotheses']
    print(f"  生成 {len(hypotheses)} 个假设")

    for i, h in enumerate(hypotheses, 1):
        print(f"\n  [假设 {i}]")
        print(f"    ID: {h.get('id', 'N/A')}")
        print(f"    标题: {h.get('title', 'N/A')[:70]}")
        print(f"    新颖性: {h.get('novelty', 'N/A')[:100]}...")
else:
    print(f"  失败: {hypothesis_result.get('error')}")

# 3. 验证假设
hypothesis_ids = hypothesis_result.get('hypothesis_ids', [])
if hypothesis_ids:
    print("\n[步骤3] 验证假设...")
    for i, hyp_id in enumerate(hypothesis_ids[:2], 1):
        print(f"\n  验证假设 {i} (ID: {hyp_id})...")
        validation_result = orchestrator.validate_hypothesis(hyp_id)

        if validation_result['success']:
            print(f"    可行性: {validation_result.get('feasibility_score', 'N/A')}/10")
            print(f"    新颖性: {validation_result.get('novelty_score', 'N/A')}/10")
            print(f"    技术性: {validation_result.get('technical_score', 'N/A')}/10")
        else:
            print(f"    失败: {validation_result.get('error')}")

    # 4. 技术分析
    print("\n[步骤4] 技术分析...")
    tech_result = orchestrator.analyze_technology(hypothesis_ids[0])
    if tech_result['success']:
        print(f"    所需技术: {tech_result.get('required_techniques', 'N/A')[:80]}...")
        print(f"    时间预估: {tech_result.get('estimated_timeline', 'N/A')}")
    else:
        print(f"    失败: {tech_result.get('error')}")

# 5. 查询最终结果
print("\n[步骤5] 查询数据库中的假设...")
with db_manager.get_session() as session:
    all_hypotheses = session.query(Hypothesis).all()
    print(f"  总共 {len(all_hypotheses)} 个假设")

    for h in all_hypotheses[-3:]:
        print(f"\n  [ID: {h.id}]")
        print(f"    标题: {h.title[:60]}...")
        print(f"    状态: {h.validation_status or 'pending'}")
        print(f"    评分: 可行性={h.feasibility_score or 'N/A'}, 新颖性={h.novelty_score or 'N/A'}, 技术性={h.technical_score or 'N/A'}")

print("\n" + "=" * 80)
print("测试完成!")
print("=" * 80)
