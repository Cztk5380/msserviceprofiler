# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import subprocess
import os
import re
import logging
import sqlite3

COMMAND_SUCCESS = 0


def execute_cmd(cmd):
    logging.info('Execute command:%s' % " ".join(cmd))
    completed_process = subprocess.run(cmd, shell=False, stderr=subprocess.PIPE)
    if completed_process.returncode != COMMAND_SUCCESS:
        logging.error(completed_process.stderr.decode())
    return completed_process.returncode


def execute_script(cmd):
    logging.info('Execute command:%s' % " ".join(cmd))
    process = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while process.poll() is None:
        line = process.stdout.readline().strip()
        if line:
            logging.debug(line)
    return process.returncode


def check_result_file(out_path):
    pass



def select_count(db_path: str, query: str):
    """
    Execute a SQL query to count the number of records in the database.
    """
    conn, cursor = create_connect_db(db_path)
    cursor.execute(query)
    count = cursor.fetchone()
    destroy_db_connect(conn, cursor)
    return count[0]


def select_by_query(db_path: str, query: str, db_class):
    """
    Execute a SQL query and return the first record as an instance of db_class.
    """
    conn, cursor = create_connect_db(db_path)
    cursor.execute(query)
    rows = cursor.fetchall()
    dbs = [db_class(*row) for row in rows]
    destroy_db_connect(conn, cursor)
    return dbs[0]


def create_connect_db(db_file: str) -> tuple:
    """
    Create a connection to the SQLite database.
    """
    try:
        conn = sqlite3.connect(db_file)
        curs = conn.cursor()
        return conn, curs
    except sqlite3.Error as e:
        logging.error("Unable to connect to database: %s", e)
        return None, None


def destroy_db_connect(conn: any, curs: any) -> None:
    """
    Close the database connection and cursor.
    """
    try:
        if isinstance(curs, sqlite3.Cursor):
            curs.close()
    except sqlite3.Error as err:
        logging.error("%s", err)
    try:
        if isinstance(conn, sqlite3.Connection):
            conn.close()
    except sqlite3.Error as err:
        logging.error("%s", err)


def change_dict(obj, *keys, value=None):
    """
    修改嵌套数据结构中指定路径的值

    参数:
        obj: 要修改的数据结构（字典、列表或元组）
        *keys: 表示路径的键序列
        value: 要设置的值

    返回:
        修改后的数据结构（注意：元组会被转换为列表）

    异常情况:
        如果路径不存在或类型不支持，会引发KeyError或TypeError
    """
    if not keys:
        return value

    current = obj
    # 遍历除最后一个key外的所有key
    for key in keys[:-1]:
        if isinstance(current, dict):
            if key not in current:
                current[key] = {}  # 自动创建中间字典
            current = current[key]
        elif isinstance(current, (list, tuple)):
            if not isinstance(key, int) or key < 0 or key >= len(current):
                raise IndexError(f"Invalid list index: {key}")
            current = current[key]
        else:
            raise TypeError(f"Cannot access key '{key}' in object of type {type(current)}")

    # 设置最终的值
    last_key = keys[-1]
    if isinstance(current, dict):
        current[last_key] = value
    elif isinstance(current, (list, tuple)):
        if not isinstance(last_key, int) or last_key < 0 or last_key > len(current):
            raise IndexError(f"Invalid list index: {last_key}")
        if last_key == len(current):
            # 扩展列表
            current.append(value)
        else:
            current[last_key] = value
    else:
        raise TypeError(f"Cannot set key '{last_key}' in object of type {type(current)}")

    return obj
