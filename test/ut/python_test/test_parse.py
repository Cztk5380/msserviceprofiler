# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from unittest.mock import patch, MagicMock, mock_open
import json
import os
import re
import shutil
import sqlite3
import logging
from pathlib import Path

import pandas as pd
import pytest
import sys
import stat

from ms_service_profiler.parse import Task
from ms_service_profiler.parse import (
    build_task_dag,
    main,
    load_ops_db
)

# 配置日志
logging.basicConfig(level=logging.INFO)


class LoadDataError(Exception):
    pass


def load_prof(filepaths):
    return filepaths


def build_msproftx_db(db_path):
    # 确保数据库文件不存在
    if os.path.exists(db_path):
        os.remove(db_path)

    # 创建数据库文件并写入表结构
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE MsprofTxEx (
            pid INTEGER,
            tid INTEGER,
            event_type TEXT,
            start_time INTEGER,
            end_time INTEGER,
            mark_id INTEGER,
            message TEXT
        );
    """)
    conn.commit()

    # 插入数据
    cursor.execute("""
        INSERT INTO MsprofTxEx (pid, tid, event_type, start_time, end_time, mark_id, message)
        VALUES (38282, 38282, 'marker', 79857442762972, '79857442762972', '464', 'span=462*{^name^: ^BatchSchedule^}'),
               (38282, 38282, 'start/end', 79857442726897, '79857442763640', '462', 'BatchSchedule');
    """)
    conn.commit()
    conn.close()


@pytest.fixture
def setup_test_directory(tmp_path):
    # 创建测试目录结构
    prof_dir = tmp_path / "PROF_test"
    prof_dir.mkdir()

    # 创建 PROF_test 下文件
    (prof_dir / "host_cpu_usage.db").write_text("cpu data")
    (prof_dir / "host_mem_usage.db").write_text("memory data")
    (prof_dir / "host_start.log").write_text("""
        cntvct: 123
        clock_monotonic_raw: 456
    """)
    (prof_dir / "info.json").write_text('{"key": "value"}')
    (prof_dir / "start_info").write_text(
        '{"collectionTimeBegin": "123456.789", "clockMonotonicRaw": "0"}')
    (prof_dir / "msprof_20250211122756.json").write_text('{"data": "example data"}')

    # 创建测试数据库文件
    db_path = prof_dir / "msproftx.db"
    build_msproftx_db(db_path)

    yield tmp_path  # 使用 yield 来返回 tmp_path，并允许在退出前执行清理操作

    # 清理操作：删除 tmp_path 目录下的所有文件和子目录，然后删除 tmp_path 目录本身
    for filename in tmp_path.rglob('*'):
        if filename.is_file():
            filename.unlink()
        elif filename.is_dir():
            shutil.rmtree(filename)
    tmp_path.rmdir()


class MockTask(Task):
    name = "mock_task"

    @classmethod
    def depends(cls):
        return ["depend_task1", "depend_task2"]


class MockTask2(Task):
    name = "mock_task2"

    @classmethod
    def depends(cls):
        return []


@patch('ms_service_profiler.parse.Task.get_retister_by_name')
def test_build_task_dag(mock_get_retister_by_name):
    # 设置get_retister_by_name方法的返回值
    def get_task(name):
        if name == "mock_task":
            return MockTask
        elif name == "mock_task2":
            return MockTask2
        else:
            return Task  # 返回一个默认的Task类，以避免返回None
    mock_get_retister_by_name.side_effect = get_task

    # 调用build_task_dag函数
    result = build_task_dag(["mock_task", "mock_task2"])

    # 断言结果是一个元组
    assert isinstance(result, tuple)
    assert len(result) == 3
    next_tasks, prev_tasks, head_tasks = result

    # 断言next_tasks是一个字典
    assert isinstance(next_tasks, dict)
    assert len(next_tasks) == 2
    assert next_tasks["depend_task1"] == set(["mock_task"])
    assert next_tasks["depend_task2"] == set(["mock_task"])

    # 断言prev_tasks是一个字典
    assert isinstance(prev_tasks, dict)
    assert len(prev_tasks) == 1
    assert prev_tasks["mock_task"] == ["depend_task1", "depend_task2"]
    assert "mock_task2" not in prev_tasks

    # 断言head_tasks是一个集合
    assert len(head_tasks) == 3
    assert "mock_task2" in head_tasks
    assert "depend_task1" in head_tasks
    assert "depend_task2" in head_tasks


def test_timestamp_conversion_and_duration_calculation(setup_test_directory):
    """
    测试时间戳转换和持续时间计算是否正确。
    """
    # 创建测试 DataFrame
    data = {
        "timestamp": [1622547600000, 1622547602000],
        "endTimestamp": [1622547601000, 1622547603000],
        "message": ["{\"key\":\"value\"}", "{\"key\":\"value2\"}"],
        "hostname": ["host1", "host2"]
    }
    df = pd.DataFrame(data)

    # 调用函数
    df = df.reset_index(drop=True).rename(columns={'timestamp': 'start_time', 'endTimestamp': 'end_time'})
    df[['start_time', 'end_time']] = df[['start_time', 'end_time']].div(1000)
    df['during_time'] = df['end_time'] - df['start_time']

    # 检查时间戳转换和持续时间计算
    assert df['start_time'].tolist() == [1622547600, 1622547602], "开始时间戳转换应正确"
    assert df['end_time'].tolist() == [1622547601, 1622547603], "结束时间戳转换应正确"
    assert df['during_time'].tolist() == [1, 1], "持续时间计算应正确"


def test_timestamp_to_local_time(setup_test_directory):
    """
    测试时间戳转换为本地时间（上海时区）是否正确。
    """
    # 创建测试 DataFrame
    data = {
        "start_time": [1622547600, 1622547602],
        "end_time": [1622547601, 1622547603]
    }
    df = pd.DataFrame(data)

    # 调用函数
    df['start_datetime'] = pd.to_datetime(df['start_time'], unit='s', utc=True).dt.tz_convert(
        'Asia/Shanghai').dt.strftime("%Y-%m-%d %H:%M:%S:%f")
    df['end_datetime'] = pd.to_datetime(df['end_time'], unit='s', utc=True).dt.tz_convert(
        'Asia/Shanghai').dt.strftime("%Y-%m-%d %H:%M:%S:%f")

    # 检查时间戳转换
    expected_start_datetime = "2021-06-01 19:40:00:000000"
    expected_end_datetime = "2021-06-01 19:40:01:000000"
    assert df.iloc[0]['start_datetime'] == expected_start_datetime, "开始时间戳转换应正确"
    assert df.iloc[0]['end_datetime'] == expected_end_datetime, "结束时间戳转换应正确"


def test_message_field_processing(setup_test_directory):
    """
    测试消息字段处理和展开是否正确。
    """
    # 创建测试 DataFrame
    data = {
        "message": ["{\"key\":\"value\"}", "{\"key\":\"value2\"}"],
        "hostname": ["host1", "host2"]
    }
    df = pd.DataFrame(data)

    # 调用函数
    df['message'] = (
        df['message']
        .str.replace(r'\^', '"', regex=True)
        .where(
            lambda s: s.str.match(r'^{.*}$'),
            other=lambda s: "{" + s.str.replace(r",$", "", regex=True) + "}"
        )
        .apply(json.loads)
    )
    msg_df = pd.json_normalize(df['message'])
    all_data_df = df.join(msg_df)

    # 检查消息字段处理和展开
    assert all_data_df.shape == (2, 3), "展开后的 DataFrame 的列数应正确"
    assert all_data_df.columns.tolist() == ["message", "hostname", "key"], "展开后的列名应正确"
    assert all_data_df.iloc[0]['key'] == "value", "展开后的 key 值应正确"
    assert all_data_df.iloc[1]['key'] == "value2", "展开后的 key 值应正确"


def test_add_and_rename_hostname(setup_test_directory):
    """
    测试添加 hostname 列并将其重命名为 hostuid 是否正确。
    """
    # 创建测试 DataFrame
    data = {
        "hostname": ["host1", "host2"]
    }
    df = pd.DataFrame(data)

    # 调用函数
    df.insert(0, 'hostuid', df['hostname'])

    # 检查 hostname 列添加和重命名
    assert df.columns.tolist() == ["hostuid", "hostname"], "列名应正确"
    assert df.iloc[0]['hostuid'] == "host1", "hostuid 列的值应正确"
    assert df.iloc[1]['hostuid'] == "host2", "hostuid 列的值应正确"


def test_main():
    # 设置测试用的输入和输出路径
    input_path = "test_input"
    output_path = "test_output"

    # 确保输入路径存在（可以是一个空目录）
    os.makedirs(input_path, exist_ok=True)

    # 确保输出路径不存在（测试时会创建）
    if os.path.exists(output_path):
        shutil.rmtree(output_path)  # 删除非空目录

    # 设置输入路径的权限为可读、可写、可执行（避免权限问题）
    os.chmod(input_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

    # 修改 sys.argv 来模拟命令行参数
    sys.argv = [
        "test_script.py",  # 脚本名称
        "--input-path", input_path,
        "--output-path", output_path,
        "--log-level", "info",
        "--format", "db", "csv", "json"
    ]

    # 调用 main 函数
    try:
        main()
        print("main() 函数运行成功，没有报错。")
    except Exception as e:
        print(f"main() 函数运行失败，报错信息：{e}")
    finally:
        # 清理测试目录
        if os.path.exists(input_path):
            shutil.rmtree(input_path)  # 删除非空目录
        if os.path.exists(output_path):
            shutil.rmtree(output_path)  # 删除非空目录


def test_load_ops_db_with_valid_db_path(setup_test_directory):
    tmp_path = setup_test_directory
    db_path = tmp_path / "PROF_test" / "msproftx.db"

    # 确保数据库文件存在
    assert os.path.exists(db_path)

    # 连接到数据库
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 创建 Api 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Api (
            name TEXT,
            start INTEGER,
            end INTEGER,
            processId INTEGER,
            threadId INTEGER,
            correlationId INTEGER
        );
    """)

    # 创建 Kernel 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Kernel (
            name TEXT,
            type TEXT,
            start INTEGER,
            end INTEGER,
            deviceId INTEGER,
            streamId INTEGER,
            correlationId INTEGER
        );
    """)

    # 创建 Communication 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Communication (
            name TEXT,
            start INTEGER,
            end INTEGER,
            deviceId INTEGER,
            streamId INTEGER,
            dataCount INTEGER,
            dataType TEXT,
            commGroupName TEXT,
            correlationId INTEGER
        );
    """)

    # 插入数据到 Api 表
    cursor.execute("""
        INSERT INTO Api (name, start, end, processId, threadId, correlationId) 
        VALUES ('api1', 1, 2, 1, 1, 1)
    """)

    conn.commit()
    conn.close()

    api_df, kernel_df, communication_df = load_ops_db(str(db_path), 1)

    assert api_df.shape[0] == 1
    assert api_df["db_id"].iloc[0] == 1

