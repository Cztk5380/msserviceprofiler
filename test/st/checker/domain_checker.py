# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import sqlite3
import re
from pathlib import Path

# 预编译正则
DOMAIN_PATTERN = re.compile(r'\^domain\^\s*\:\s*\^([^\\^]+)\^', re.IGNORECASE)

def extract_domain_from_message(message):
    """提取 domain 值"""
    if not isinstance(message, str):
        return None
    match = DOMAIN_PATTERN.search(message)
    return match.group(1) if match else None

def check_db_domain(output_path, target_domain=""):
    """
    使用 pytest 风格的 assert 检查所有 domain 是否为目标值。
    如果存在其他 domain，assert 失败并显示具体是哪些。

    :param output_path: 数据库文件目录
    :param target_domain: 期望的 domain 值
    :return: True（通过），失败则抛出 AssertionError
    """
    # 路径检查也用 assert
    path = Path(output_path)
    assert path.exists(), f" Error: Path does not exist: {output_path}"
    assert path.is_dir(), f" Error: Path is not a directory: {output_path}"

    db_files = list(path.rglob("*.db"))
    assert len(db_files) > 0, f" Error: No .db files found in directory: {output_path}"

    # 全局收集 domain 值
    domain_stats = {}
    total_extracted = 0

    for db_file in db_files:
        conn = None
        try:
            conn = sqlite3.connect(str(db_file), timeout=10)
            cursor = conn.cursor()

            # 获取所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                try:
                    # 检查是否有 message 字段
                    cursor.execute(f"PRAGMA table_info({table});")
                    columns = [col[1].lower() for col in cursor.fetchall()]
                    if 'message' not in columns:
                        continue

                    # 查询所有非空 message
                    query = f'SELECT message FROM "{table}" WHERE message IS NOT NULL;'
                    cursor.execute(query)
                    messages = cursor.fetchall()

                    for msg_tuple in messages:
                        message = msg_tuple[0]
                        domain = extract_domain_from_message(message)
                        if domain:
                            total_extracted += 1
                            domain_stats[domain] = domain_stats.get(domain, 0) + 1

                except Exception:
                    continue  # 静默跳过表错误

        except sqlite3.Error:
            continue  # 静默跳过数据库错误
        finally:
            if conn:
                conn.close()

    # 必须提取到至少一个 domain
    assert total_extracted > 0, f" Error: No domain values extracted from any database in {output_path}"

    # 检查是否所有 domain 都是 target_domain
    other_domains = [d for d in domain_stats.keys() if d != target_domain]

    # 🔥 核心 assert：如果不是全匹配，就列出“别的”
    assert len(other_domains) == 0, (
        f" Target domain: '{target_domain}'\n"
        f" Total domain values extracted: {total_extracted}\n"
        f" Unexpected domain values found: {sorted(set(other_domains))}\n"
        f" Full distribution: {dict(sorted(domain_stats.items()))}"
    )

    return True
