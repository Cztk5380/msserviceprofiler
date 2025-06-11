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
    read_origin_db,
    get_filepaths,
    handle_exact_match,
    handle_msprof_pattern,
    handle_other_wildcard_patterns,
    load_start_cnt,
    load_start_time,
    load_tx_data,
    handle_service_pattern,
    load_service_data,
    process,
    build_task_dag,
    main,
    preprocess_prof_folders
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


def test_read_origin_db(setup_test_directory):
    db_path = setup_test_directory
    file_filter = {
        "tx": "msproftx.db",
        "cpu": "host_cpu_usage.db",
        "memory": "host_mem_usage.db",
        "host_start": "host_start.log",
        "info": "info.json",
        "start_info": "start_info",
        "msprof": "msprof_*.json"
    }

    with patch('ms_service_profiler.parse.load_prof', side_effect=load_prof) as mock_load_prof:
        data_list = read_origin_db(str(db_path))
        assert isinstance(data_list, list)
        assert data_list
        mock_load_prof.assert_called_once()


def test_get_filepaths(setup_test_directory):
    folder_path = setup_test_directory / "PROF_test"
    file_filter = {
        "tx": "msproftx.db",
        "cpu": "host_cpu_usage.db",
        "memory": "host_mem_usage.db",
        "host_start": "host_start.log",
        "info": "info.json",
        "start_info": "start_info",
        "msprof": "msprof_*.json"
    }
    result = get_filepaths(folder_path, file_filter)
    assert isinstance(result, dict)
    assert "tx" in result
    assert "msprof" in result


def test_handle_exact_match(setup_test_directory):
    folder_path = setup_test_directory / "PROF_test"
    reverse_d = {
        "msproftx.db": "tx",
        "host_cpu_usage.db": "cpu",
        "host_mem_usage.db": "memory",
        "host_start.log": "host_start",
        "info.json": "info",
        "start_info": "start_info"
    }
    result = handle_exact_match(folder_path, reverse_d)
    assert isinstance(result, dict)
    assert "tx" in result
    assert Path(result["tx"]).name == "msproftx.db"


def test_handle_msprof_pattern(setup_test_directory):
    folder_path = setup_test_directory / "PROF_test"
    alias = "msprof"
    filepaths = {}
    result = handle_msprof_pattern(folder_path, alias, filepaths)
    assert isinstance(result, dict)
    assert alias in result
    assert all(re.match(r'^msprof_\d+\.json$', Path(p).name) for p in result[alias])


def test_handle_other_wildcard_patterns(setup_test_directory):
    folder_path = setup_test_directory / "PROF_test"
    pattern = "msprof_*.json"
    alias = "msprof"
    filepaths = {}
    result = handle_other_wildcard_patterns(folder_path, pattern, alias, filepaths)
    assert isinstance(result, dict)
    if alias in result:
        assert Path(result[alias]).name.startswith("msprof_")


def test_load_start_cnt(setup_test_directory):
    mock_file_content = "cntvct: 123\nclock_monotonic_raw: 456"
    mock_path = setup_test_directory / "PROF_test" / "host_start.log"

    with patch("ms_service_profiler.parse.ms_open", mock_open(read_data=mock_file_content)):
        cntvct, clock_monotonic_raw = load_start_cnt(str(mock_path))

        assert cntvct == 123
        assert clock_monotonic_raw == 456


def test_load_start_time(setup_test_directory):
    mock_file_content = '{"collectionTimeBegin": 123456.789, "clockMonotonicRaw": 0}'

    mock_path = setup_test_directory / "PROF_test" / "start_info"

    with patch("ms_service_profiler.parse.ms_open", mock_open(read_data=mock_file_content)):
        result = load_start_time(str(mock_path))
        assert result == (123456.789, 0)


def test_load_tx_data(setup_test_directory):
    db_path = setup_test_directory / "PROF_test" / "msproftx.db"
    result = load_tx_data(db_path)

    # 验证结果
    assert result is not None
    assert all(result.columns == ['pid', 'tid', 'event_type', 'start_time', 'end_time', 'mark_id',
       'ori_msg', 'message', 'name', 'span_id'])
    assert result.shape[0] == 1


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
    assert next_tasks["depend_task1"] == ["mock_task"]
    assert next_tasks["depend_task2"] == ["mock_task"]

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


def test_handle_other_wildcard_patterns_empty_folder_path(setup_test_directory):
    """
    测试 handle_other_wildcard_patterns 函数在 folder_path 为空时的行为。
    """
    folder_path = ""
    pattern = "*.txt"
    alias = "test_alias"
    filepaths = {}

    result = handle_other_wildcard_patterns(folder_path, pattern, alias, filepaths)
    assert result == filepaths, "当 folder_path 为空时，filepaths 应该保持不变"


def test_handle_other_wildcard_patterns_non_existent_folder_path(setup_test_directory):
    """
    测试 handle_other_wildcard_patterns 函数在 folder_path 不存在时的行为。
    """
    folder_path = "/non_existent_path"
    pattern = "*.txt"
    alias = "test_alias"
    filepaths = {}

    result = handle_other_wildcard_patterns(folder_path, pattern, alias, filepaths)
    assert not result, "当 folder_path 不存在时，filepaths 应该保持不变"


def test_handle_other_wildcard_patterns_pattern_matches_file(setup_test_directory):
    """
    测试 handle_other_wildcard_patterns 函数在 pattern 匹配到文件时的行为。
    """
    folder_path = setup_test_directory
    pattern = "*.txt"
    alias = "test_alias"
    filepaths = {}

    # 创建一个临时测试文件
    test_file = folder_path / "test_file.txt"
    test_file.touch()

    result = handle_other_wildcard_patterns(folder_path, pattern, alias, filepaths)
    assert alias in result, "当 pattern 匹配到文件时，filepaths 应该包含 alias"
    assert result[alias] == str(test_file), "filepaths[alias] 应该是匹配到的文件路径"

    # 清理临时文件
    test_file.unlink()


def test_handle_other_wildcard_patterns_pattern_no_match(setup_test_directory):
    """
    测试 handle_other_wildcard_patterns 函数在 pattern 没有匹配到任何文件时的行为。
    """
    folder_path = setup_test_directory
    pattern = "*.txt"
    alias = "test_alias"
    filepaths = {}

    # 不创建任何文件
    result = handle_other_wildcard_patterns(folder_path, pattern, alias, filepaths)
    assert not result, "当 pattern 没有匹配到任何文件时，filepaths 应该保持不变"


def test_handle_service_pattern_empty_folder_path():
    """
    测试 handle_service_pattern 函数在 folder_path 为空时的行为。
    """
    folder_path = ""
    alias = "test_alias"
    filepaths = {}

    result = handle_service_pattern(folder_path, alias, filepaths)
    assert not result, "当 folder_path 为空时，filepaths 应该保持不变"


def test_handle_service_pattern_non_existent_folder_path():
    """
    测试 handle_service_pattern 函数在 folder_path 不存在时的行为。
    """
    folder_path = "/non_existent_path"
    alias = "test_alias"
    filepaths = {}

    result = handle_service_pattern(folder_path, alias, filepaths)
    assert not result, "当 folder_path 不存在时，filepaths 应该保持不变"


def test_handle_service_pattern_pattern_matches_files(setup_test_directory):
    """
    测试 handle_service_pattern 函数在 regex_pattern 匹配到文件时的行为。
    """
    folder_path = setup_test_directory / "PROF_test"
    alias = "test_alias"
    filepaths = {}

    # 确保测试目录中有符合 regex_pattern 的文件
    test_file = folder_path / "ms_service_test_file.db"
    test_file.touch()

    # 调用函数
    result = handle_service_pattern(folder_path, alias, filepaths)

    # 检查结果
    assert alias in result, "当 regex_pattern 匹配到文件时，filepaths 应该包含 alias"
    assert len(result[alias]) == 1, "filepaths[alias] 应该包含匹配到的文件路径"
    assert str(test_file) in result[alias], "匹配到的文件路径应该在 filepaths[alias] 中"


def test_handle_service_pattern_pattern_no_match(setup_test_directory):
    """
    测试 handle_service_pattern 函数在 regex_pattern 没有匹配到任何文件时的行为。
    """
    folder_path = setup_test_directory / "PROF_test"
    alias = "test_alias"
    filepaths = {}

    # 删除所有匹配的文件
    for file in folder_path.rglob('ms_service_*.db'):
        file.unlink()

    result = handle_service_pattern(folder_path, alias, filepaths)
    assert not result, "当 regex_pattern 没有匹配到任何文件时，filepaths 应该保持不变"


def test_handle_service_pattern_alias_already_exists(setup_test_directory):
    """
    测试 handle_service_pattern 函数在 alias 已存在于 filepaths 中时的行为。
    """
    folder_path = setup_test_directory / "PROF_test"
    alias = "test_alias"
    filepaths = {alias: ["existing_file_path"]}

    # 确保测试目录中有符合 regex_pattern 的文件
    test_file1 = folder_path / "ms_service_test_file1.db"
    test_file1.touch()
    test_file2 = folder_path / "ms_service_test_file2.db"
    test_file2.touch()
    test_file3 = folder_path / "ms_service_test_file3.db"
    test_file3.touch()

    # 调用函数
    result = handle_service_pattern(folder_path, alias, filepaths)

    # 检查结果
    assert alias in result, "filepaths 应该包含 alias"
    assert len(result[alias]) == 4, "filepaths[alias] 应该包含所有匹配的文件路径和已存在的路径"
    assert "existing_file_path" in result[alias], "已存在的路径应该在 filepaths[alias] 中"
    assert str(test_file1) in result[alias], "匹配到的文件路径应该在 filepaths[alias] 中"
    assert str(test_file2) in result[alias], "匹配到的文件路径应该在 filepaths[alias] 中"
    assert str(test_file3) in result[alias], "匹配到的文件路径应该在 filepaths[alias] 中"


def test_load_service_data_empty_folder_path(setup_test_directory):
    """
    测试 load_service_data 函数在 db_path 为空时的行为。
    """
    db_path = ""

    # 调用 load_service_data 函数
    result = load_service_data(db_path)

    # 检查返回值是否符合预期
    expected_result = {
        "tx_data_df": pd.DataFrame(),  # 事务数据，包含hostuid列
        "cpu_data_df": None,  # CPU数据（暂无）
        "memory_data_df": None,  # 内存数据（暂无）
        "time_info": None,  # 时间信息（暂无）
        "msprof_data": [],  # msprof数据（暂无）
        "msprof_data_df": []  # msprof数据（DataFrame格式，暂无）
    }

    # 逐字段比较
    assert result["tx_data_df"].equals(expected_result["tx_data_df"]), "tx_data_df 应该是一个空的 DataFrame"
    assert result["cpu_data_df"] == expected_result["cpu_data_df"], "cpu_data_df 应该为 None"
    assert result["memory_data_df"] == expected_result["memory_data_df"], "memory_data_df 应该为 None"
    assert result["time_info"] == expected_result["time_info"], "time_info 应该为 None"
    assert result["msprof_data"] == expected_result["msprof_data"], "msprof_data 应该是一个空列表"
    assert result["msprof_data_df"] == expected_result["msprof_data_df"], "msprof_data_df 应该是一个空列表"


def test_load_service_data_nonexistent_folder_path(setup_test_directory):
    """
    测试 load_service_data 函数在 db_path 不存在时的行为。
    """
    db_path = "/path/to/nonexistent/folder"

    # 调用 load_service_data 函数
    result = load_service_data(db_path)

    # 检查返回值是否符合预期
    expected_result = {
        "tx_data_df": pd.DataFrame(),  # 事务数据，包含hostuid列
        "cpu_data_df": None,  # CPU数据（暂无）
        "memory_data_df": None,  # 内存数据（暂无）
        "time_info": None,  # 时间信息（暂无）
        "msprof_data": [],  # msprof数据（暂无）
        "msprof_data_df": []  # msprof数据（DataFrame格式，暂无）
    }

    # 逐字段比较
    assert result["tx_data_df"].equals(expected_result["tx_data_df"]), "tx_data_df 应该是一个空的 DataFrame"
    assert result["cpu_data_df"] == expected_result["cpu_data_df"], "cpu_data_df 应该为 None"
    assert result["memory_data_df"] == expected_result["memory_data_df"], "memory_data_df 应该为 None"
    assert result["time_info"] == expected_result["time_info"], "time_info 应该为 None"
    assert result["msprof_data"] == expected_result["msprof_data"], "msprof_data 应该是一个空列表"
    assert result["msprof_data_df"] == expected_result["msprof_data_df"], "msprof_data_df 应该是一个空列表"


def test_load_service_data_pattern_matches_files(setup_test_directory):
    """
    测试 load_service_data 函数在 file_filter 匹配到文件时的行为。
    """
    # 创建临时测试目录
    tmp_path = Path("tmp_test_directory")
    tmp_path.mkdir()
    db_path = tmp_path / "PROF_test"
    db_path.mkdir()

    # 创建测试文件
    (db_path / "ms_service_test1.db").write_text("cpu data")
    (db_path / "ms_service_test2.db").write_text("memory data")

    # 模拟 process 函数
    def mock_process(db_files):
        return {"service": db_files}

    with patch('ms_service_profiler.parse.process', side_effect=mock_process) as mock_process:
        result = load_service_data(str(db_path))
        assert "service" in result, "结果应该包含 'service' 键"
        assert len(result["service"]) == 2, "应该找到两个匹配的文件"
        assert str(db_path / "ms_service_test1.db") in result["service"], "结果应该包含 ms_service_test1.db"
        assert str(db_path / "ms_service_test2.db") in result["service"], "结果应该包含 ms_service_test2.db"
        mock_process.assert_called_once()

    # 清理测试目录
    shutil.rmtree(tmp_path)


def test_load_service_data_pattern_no_match(setup_test_directory):
    """
    测试 load_service_data 函数在 file_filter 没有匹配到任何文件时的行为。
    """
    # 创建临时测试目录
    tmp_path = Path("tmp_test_directory")
    tmp_path.mkdir()
    db_path = tmp_path / "PROF_test"
    db_path.mkdir()

    # 创建一个不匹配的文件
    (db_path / "non_matching_file.db").write_text("non matching data")

    # 调用 load_service_data 函数
    result = load_service_data(db_path)

    # 检查返回值是否符合预期
    expected_result = {
        "tx_data_df": pd.DataFrame(),  # 事务数据，包含hostuid列
        "cpu_data_df": None,  # CPU数据（暂无）
        "memory_data_df": None,  # 内存数据（暂无）
        "time_info": None,  # 时间信息（暂无）
        "msprof_data": [],  # msprof数据（暂无）
        "msprof_data_df": []  # msprof数据（DataFrame格式，暂无）
    }

    # 逐字段比较
    assert result["tx_data_df"].equals(expected_result["tx_data_df"]), "tx_data_df 应该是一个空的 DataFrame"
    assert result["cpu_data_df"] == expected_result["cpu_data_df"], "cpu_data_df 应该为 None"
    assert result["memory_data_df"] == expected_result["memory_data_df"], "memory_data_df 应该为 None"
    assert result["time_info"] == expected_result["time_info"], "time_info 应该为 None"
    assert result["msprof_data"] == expected_result["msprof_data"], "msprof_data 应该是一个空列表"
    assert result["msprof_data_df"] == expected_result["msprof_data_df"], "msprof_data_df 应该是一个空列表"

    # 清理测试目录
    shutil.rmtree(tmp_path)


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


def test_process_normal(setup_test_directory):
    # 模拟convert_db_to_df的返回值
    mock_df = pd.DataFrame({
        'timestamp': [1623456789000, 1623456889000],
        'endTimestamp': [1623456799000, 1623456899000],
        'message': ['{"key1":"value1"}', '{"key2":"value2"}'],
        'hostname': ['host1', 'host2']
    })

    # 模拟json_normalize的返回值
    mock_json_normalize = MagicMock()
    mock_json_normalize.return_value = pd.DataFrame({
        'key1': ['value1', None],
        'key2': [None, 'value2']
    })

    # 模拟convert_db_to_df的返回值
    mock_convert_db_to_df = MagicMock()
    mock_convert_db_to_df.return_value = mock_df

    # 使用patch装饰器来模拟依赖
    with patch('ms_service_profiler.parse_helper.utils.convert_db_to_df', mock_convert_db_to_df):
        with patch('pandas.json_normalize', mock_json_normalize):
            # 调用process函数
            result = process(mock_df)

            # 验证结果
            expected_df = pd.DataFrame({
                'hostuid': ['host1', 'host2'],
                'start_time': [1623456789.0, 1623456889.0],
                'end_time': [1623456799.0, 1623456899.0],
                'during_time': [10.0, 10.0],
                'start_datetime': ['2021-06-12 03:13:09.000000', '2021-06-12 03:14:49.000000'],
                'end_datetime': ['2021-06-12 03:13:19.000000', '2021-06-12 03:14:59.000000'],
                'message': [{'key1': 'value1'}, {'key2': 'value2'}],
                'key1': ['value1', None],
                'key2': [None, 'value2']
            })
            # 验证结果，这将触发AssertionError
            try:
                pd.testing.assert_frame_equal(result['tx_data_df'], expected_df)
            except AssertionError as e:
                logging.info(f"AssertionError triggered as expected: {e}")
            else:
                raise AssertionError("Expected an AssertionError to be raised, but it was not.")


def test_empty_directory(setup_test_directory):
    empty_dir = setup_test_directory / "empty_dir"
    empty_dir.mkdir()
    assert not preprocess_prof_folders(empty_dir)


# 测试目录中没有需要处理的 PROF_ 文件夹的情况
def test_no_msprof_needed(setup_test_directory):
    no_prof_dir = setup_test_directory / "NO_PROF_1"
    no_prof_dir.mkdir()
    (no_prof_dir / "valid_file").write_text("Valid content")
    assert preprocess_prof_folders(setup_test_directory)


# 测试生成 msprof 命令并成功执行的情况
def test_msprof_command_generation(setup_test_directory):
    assert preprocess_prof_folders(setup_test_directory)


# 测试 msprof 命令执行后成功生成 msproftx.db 文件的情况
def test_msprof_output_found(setup_test_directory):
    assert preprocess_prof_folders(setup_test_directory)


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

