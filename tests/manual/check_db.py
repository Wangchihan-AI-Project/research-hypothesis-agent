# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

import sqlite3
import json

# 连接数据库
db_path = "C:/Users/PC/research-hypothesis-agent/data/research.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 80)
print("数据库内容检查")
print("=" * 80)

# 1. 检查论文
print("\n[1] 论文表 (papers)")
print("-" * 80)
cursor.execute("SELECT pmid, title, journal, publication_date FROM papers LIMIT 10")
papers = cursor.fetchall()
if papers:
    for p in papers:
        print(f"  PMID: {p['pmid']}")
        print(f"  标题: {p['title'][:60]}...")
        print(f"  期刊: {p['journal'] or 'N/A'}")
        print(f"  日期: {p['publication_date'] or 'N/A'}")
        print()
else:
    print("  无数据")

# 2. 检查假设
print("\n[2] 假设表 (hypotheses)")
print("-" * 80)
cursor.execute("SELECT id, title, status, feasibility_score, novelty_score, technical_score FROM hypotheses")
hypotheses = cursor.fetchall()
if hypotheses:
    print(f"  找到 {len(hypotheses)} 个假设:\n")
    for h in hypotheses:
        print(f"  ID: {h['id']}")
        print(f"  标题: {h['title'][:60]}...")
        print(f"  状态: {h['status'] or 'N/A'}")
        print(f"  评分 - 可行性: {h['feasibility_score'] or 'N/A'}, 新颖性: {h['novelty_score'] or 'N/A'}, 技术性: {h['technical_score'] or 'N/A'}")
        print()
else:
    print("  无数据")

# 3. 检查会话
print("\n[3] 研究会话表 (research_sessions)")
print("-" * 80)
cursor.execute("SELECT id, query, status, papers_found, hypotheses_generated, created_at FROM research_sessions ORDER BY id DESC LIMIT 5")
sessions = cursor.fetchall()
if sessions:
    for s in sessions:
        print(f"  ID: {s['id']}")
        print(f"  查询: {s['query'][:50]}...")
        print(f"  状态: {s['status'] or 'N/A'}")
        print(f"  统计 - 论文: {s['papers_found'] or 0}, 假设: {s['hypotheses_generated'] or 0}")
        print(f"  创建: {s['created_at'] or 'N/A'}")
        print()
else:
    print("  无数据")

conn.close()
print("\n" + "=" * 80)
