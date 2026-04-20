# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

import sqlite3

# 连接数据库
db_path = "C:/Users/PC/research-hypothesis-agent/data/research.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 80)
print("数据库表结构")
print("=" * 80)

# 获取所有表名
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("\n表列表:")
for table in tables:
    print(f"  - {table[0]}")

# 查看每个表的结构
for table in tables:
    table_name = table[0]
    print(f"\n{'=' * 80}")
    print(f"表: {table_name}")
    print('=' * 80)
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    print("列信息:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")

    # 获取记录数
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"记录数: {count}")

    # 如果是 hypotheses 表，显示一些记录
    if table_name == 'hypotheses' and count > 0:
        print("\n最新记录:")
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        rows = cursor.fetchall()
        # 获取列名
        cursor.execute(f"PRAGMA table_info({table_name})")
        col_names = [c[1] for c in cursor.fetchall()]
        for row in rows:
            print(f"  记录: {dict(zip(col_names, row))}")

conn.close()
print("\n" + "=" * 80)
