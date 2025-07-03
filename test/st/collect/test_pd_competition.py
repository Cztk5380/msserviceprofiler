import unittest
import os
import shutil
from datetime import datetime, timezone
import json
import sqlite3
import logging
import yaml
from ...st.utils import execute_cmd

# 获取当前脚本所在的目录
script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)


def create_directory_with_timestamp(home_dir):
    # 获取当前时间戳
    timestamp = datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')

    # 构建目录路径
    directory_path = os.path.join(home_dir, f'test_dir_{timestamp}')

    # 检查目录是否已存在
    if os.path.exists(directory_path):
        print(f"目录 {directory_path} 已存在，正在删除...")
        shutil.rmtree(directory_path)

    # 创建目录
    os.makedirs(directory_path)
    print(f"目录 {directory_path} 创建成功")
    return directory_path


def update_json(file_path, keys, value):
    """
    更新 JSON 文件中指定键的值，并将更新后的 JSON 写回原文件。

    :param file_path: JSON 文件的路径
    :param keys: 键列表，表示不同层级的键
    :param value: 要设置的新值
    """
    # 读取 JSON 文件
    with open(file_path, 'r') as file:
        data = json.load(file)

    current = data
    for key in keys[:-1]:
        if key in current and isinstance(current[key], dict):
            current = current[key]
        else:
            raise KeyError(f"Key {key} not found or does not point to a dictionary")

    final_key = keys[-1]
    if final_key in current:
        current[final_key] = value
    else:
        raise KeyError(f"Key {final_key} not found")

    # 将更新后的 JSON 写回文件
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)


def check_table_header_in_directory(directory, table_name, required_columns):
    """
    检查指定目录下所有 SQLite 数据库文件中的表头是否与要求完全一致。

    :param directory: 目录路径
    :param table_name: 表名
    :param required_columns: 必需的列名列表
    :return: 如果所有数据库文件中的表头都与要求完全一致，返回 True；否则返回 False
    """
    print(f"Checking directory {directory} ...")

    # 获取目录下所有 .db 文件
    db_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.db')]

    for db_file in db_files:
        if not check_table_header(db_file, table_name, required_columns):
            return False

    return True


def check_table_header(db_file, table_name, required_columns):
    """
    检查 SQLite 数据库文件中的表头是否与要求完全一致。

    :param db_file: 数据库文件路径
    :param table_name: 表名
    :param required_columns: 必需的列名列表
    :return: 如果所有必需的列都存在且与表中的列完全一致，返回 True；否则返回 False
    """
    print(f"Checking {db_file} ...")
    # 连接到 SQLite 数据库
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    try:
        # 获取表的列信息
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()

        # 提取列名
        existing_columns = [column[1] for column in columns]

        # 检查所有必需的列是否与表中的列完全一致
        if set(required_columns) == set(existing_columns):
            return True
        else:
            missing_columns = set(required_columns) - set(existing_columns)
            extra_columns = set(existing_columns) - set(required_columns)
            if missing_columns:
                print(f"Columns {missing_columns} are missing in table '{table_name}' in {db_file}")
            if extra_columns:
                print(f"Columns {extra_columns} are extra in table '{table_name}' in {db_file}")
            return False

    finally:
        # 关闭数据库连接
        conn.close()


def get_ip_address_for_request(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    ip = str(data['ServerConfig']['ipAddress'])
    port = str(data['ServerConfig']['port'])
    ip_address = f"{ip}:{port}/infer"
    return ip_address


def get_args_from_yaml(yaml_path):
    # 打开并读取YAML文件
    with open(yaml_path, 'r') as file:
        config = yaml.safe_load(file)

    # 获取特定的参数
    service_config = config.get('service_config', '')
    profiler_so = config.get('profiler_so', '')
    return service_config, profiler_so


class TestPdCompetition(unittest.TestCase):


    def test_example(self):
        service_config, profiler_so = get_args_from_yaml(os.path.join(script_dir, "collect_st_args.yaml"))

        ip_address = get_ip_address_for_request(service_config)

        test_dir = create_directory_with_timestamp("/home")

        execute_cmd(['bash', os.path.join(script_dir, "utils", "start_mindie_service.sh"), service_config, test_dir, profiler_so])

        update_json(os.path.join(test_dir, "profiler.json"), ["enable"], 1)

        execute_cmd(['bash', os.path.join(script_dir, "utils", "send_single_request.sh"), ip_address])

        assert check_table_header_in_directory(
            os.path.join(test_dir, "prof_result"),
            "Mstx", ["message", "flag", "timestamp", "endTimestamp", "markId", "tid", "pid"])


if __name__ == '__main__':
    unittest.main()


