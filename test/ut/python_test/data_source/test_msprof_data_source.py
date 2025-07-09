# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import os
import sqlite3

import pandas as pd

from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
from ms_service_profiler.data_source.msprof_data_source import MsprofDataSource
from ms_service_profiler.utils.error import LoadDataError
from test.ut.python_test.test_parse import build_msproftx_db, setup_test_directory


@patch('pathlib.Path.glob')
def test_get_prof_paths(mock_glob):
    # 设置glob方法的返回值
    mock_path1 = MagicMock()
    mock_path1.is_file.return_value = True
    mock_path1.name = 'PROF_file1'
    mock_path2 = MagicMock()
    mock_path2.is_file.return_value = True
    mock_path2.name = 'PROF_file2'
    mock_glob.return_value = [mock_path1, mock_path2]

    # 调用get_prof_paths方法
    result = MsprofDataSource.get_prof_paths('dummy_path')

    # 断言结果是一个列表
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0] == mock_path1
    assert result[1] == mock_path2


@patch('ms_service_profiler.data_source.msprof_data_source.MsprofDataSource.get_filepaths')
@patch('ms_service_profiler.data_source.msprof_data_source.MsprofDataSource.load_prof')
def test_load(mock_load_prof, mock_get_filepaths):
    # 设置get_filepaths和load_prof方法的返回值
    mock_get_filepaths.return_value = {
        "tx": "msproftx.db",
        "cpu": "host_cpu_usage.db",
        "memory": "host_mem_usage.db",
        "host_start": "host_start.log",
        "info": "info.json",
        "start_info": "start_info",
        "msprof": "msprof_*.json"
    }
    mock_load_prof.return_value = {"data": "dummy_data"}

    # 创建MsprofDataSource实例
    msprof_data_source = MsprofDataSource({})

    # 调用load方法
    result = msprof_data_source.load('dummy_path')

    # 断言结果是一个字典
    assert isinstance(result, dict)
    assert result == {"data": "dummy_data"}

    # 测试异常处理
    mock_load_prof.side_effect = Exception('Test exception')
    with pytest.raises(LoadDataError, match='dummy_path'):
        msprof_data_source.load('dummy_path')


def test_load_start_cnt(setup_test_directory):
    mock_file_content = "cntvct: 123\nclock_monotonic_raw: 456"
    mock_path = setup_test_directory / "PROF_test" / "host_start.log"

    with patch("ms_service_profiler.parse.ms_open", mock_open(read_data=mock_file_content)):
        cntvct, clock_monotonic_raw = MsprofDataSource.load_start_cnt(str(mock_path))

        assert cntvct == 123
        assert clock_monotonic_raw == 456


def test_load_start_time(setup_test_directory):
    mock_file_content = '{"collectionTimeBegin": 123456.789, "clockMonotonicRaw": 0}'

    mock_path = setup_test_directory / "PROF_test" / "start_info"

    with patch("ms_service_profiler.parse.ms_open", mock_open(read_data=mock_file_content)):
        result = MsprofDataSource.load_start_time(str(mock_path))
        assert result == (123456.789, 0)


def test_load_tx_data(setup_test_directory):
    db_path = setup_test_directory / "PROF_test" / "msproftx.db"
    result = MsprofDataSource.load_tx_data(db_path)

    # 验证结果
    assert result is not None
    assert all(result.columns == ['pid', 'tid', 'event_type', 'start_time', 'end_time', 'mark_id',
       'ori_msg', 'message', 'name', 'span_id'])
    assert result.shape[0] == 1


def test_load_cpu_data_with_valid_db_path(setup_test_directory):
    """
    测试当 db_path 有效时，load_cpu_data 函数是否正确加载数据。
    """
    tmp_path = setup_test_directory
    db_path = tmp_path / "PROF_test" / "msproftx.db"

    # 确保数据库文件存在
    assert os.path.exists(db_path)

    # 连接到数据库
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 创建 CpuUsage 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS CpuUsage (
            id INTEGER PRIMARY KEY,
            cpu_no TEXT,
            usage REAL,
            other_column REAL
        );
    """)

    # 插入数据到 CpuUsage 表
    cursor.execute("""
        INSERT INTO CpuUsage (cpu_no, usage, other_column) VALUES ('Avg', 50.0, 25.0)
    """)

    conn.commit()
    conn.close()
    # 调用 load_cpu_data 函数
    result = MsprofDataSource.load_cpu_data(str(db_path))

    # 验证返回的 DataFrame 是否正确
    expected_columns = ["id", "cpu_no", "usage", "other_column"]
    expected_data = [(1, 'Avg', 50.0, 25.0)]
    expected_df = pd.DataFrame(expected_data, columns=expected_columns)
    pd.testing.assert_frame_equal(result, expected_df)


def test_load_memory_data_with_valid_db_path(setup_test_directory):
    """
    测试当 db_path 有效时，load_memory_data 函数是否正确加载数据。
    """
    tmp_path = setup_test_directory
    db_path = tmp_path / "PROF_test" / "msproftx.db"

    # 确保数据库文件存在
    assert os.path.exists(db_path)

    # 连接到数据库
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 创建 MemUsage 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS MemUsage (
            id INTEGER PRIMARY KEY,
            mem_no TEXT,
            usage REAL,
            other_column REAL
        );
    """)

    # 插入数据到 MemUsage 表
    cursor.execute("""
        INSERT INTO MemUsage (mem_no, usage, other_column) VALUES ('Avg', 75.0, 30.0)
    """)

    conn.commit()
    conn.close()

    # 调用 load_memory_data 函数
    result = MsprofDataSource.load_memory_data(str(db_path))

    # 验证返回的 DataFrame 是否正确
    expected_columns = ["id", "mem_no", "usage", "other_column"]
    expected_data = [(1, 'Avg', 75.0, 30.0)]
    expected_df = pd.DataFrame(expected_data, columns=expected_columns)
    pd.testing.assert_frame_equal(result, expected_df)


def test_load_memory_data_with_none_db_path():
    """
    测试当 db_path 为 None 时，load_memory_data 函数是否返回 None。
    """
    result = MsprofDataSource.load_memory_data(None)
    assert result is None