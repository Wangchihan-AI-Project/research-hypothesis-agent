# -*- coding: utf-8 -*-
"""
数据库迁移脚本 - 添加 LLM 评分字段

运行方式: python migrations/add_llm_fields.py
"""
import sys
import os
import sqlite3

# 设置 UTF-8 编码输出（Windows 兼容）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def migrate():
    """���行数据库迁移"""
    print("\n" + "="*60)
    print("  数据库迁移 - 添加 LLM 评分字段")
    print("="*60 + "\n")

    # 数据库路径
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'research.db')

    # 确保 data 目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # 如果数据库不存在，先创建基础表
    if not os.path.exists(db_path):
        print("  数据库不存在，将在首次运行时自动创建")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 检查现有表结构
    cursor.execute("PRAGMA table_info(papers)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    print(f"  现有字段数: {len(existing_columns)}")

    # 要添加的新字段
    new_fields = [
        ("llm_score", "REAL DEFAULT 0.0"),
        ("llm_reason", "TEXT"),
        ("llm_innovation", "VARCHAR(500)"),
        ("llm_data_quality", "VARCHAR(500)"),
        ("llm_research_type", "VARCHAR(100)"),
        ("screening_date", "DATETIME")
    ]

    # 添加缺失的字段
    for field_name, field_type in new_fields:
        if field_name not in existing_columns:
            sql = f"ALTER TABLE papers ADD COLUMN {field_name} {field_type}"
            print(f"  添加字段: {field_name} ({field_type})")
            cursor.execute(sql)
        else:
            print(f"  跳过已存在字段: {field_name}")

    conn.commit()
    conn.close()

    print("\n" + "="*60)
    print("  ✓ 迁移完成！")
    print("="*60 + "\n")


if __name__ == '__main__':
    migrate()
