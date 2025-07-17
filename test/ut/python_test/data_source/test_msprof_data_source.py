# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import os

import shutil
import sqlite3

import pandas as pd
import pytest

from unittest.mock import patch, MagicMock, mock_open
from ms_service_profiler.data_source.msprof_data_source import MsprofDataSource
from ms_service_profiler.utils.error import LoadDataError
from ms_service_profiler.utils.file_open_check import ms_open


def build_db(db_path):
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
def setup_test_msprof_directory(tmp_path):
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
    build_db(db_path)

    yield tmp_path  # 使用 yield 来返回 tmp_path，并允许在退出前执行清理操作

    # 清理操作：删除 tmp_path 目录下的所有文件和子目录，然后删除 tmp_path 目录本身
    for filename in tmp_path.rglob('*'):
        if filename.is_file():
            filename.unlink()
        elif filename.is_dir():
            shutil.rmtree(filename)
    tmp_path.rmdir()


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


def test_load_tx_data(setup_test_msprof_directory):
    db_path = setup_test_msprof_directory / "PROF_test" / "msproftx.db"
    result = MsprofDataSource.load_tx_data(db_path)

    # 验证结果
    assert result is not None
    assert all(result.columns == ['pid', 'tid', 'event_type', 'start_time', 'end_time', 'mark_id',
       'ori_msg', 'message', 'name', 'span_id'])
    assert result.shape[0] == 1


def test_load_cpu_data_with_valid_db_path(setup_test_msprof_directory):
    """
    测试当 db_path 有效时，load_cpu_data 函数是否正确加载数据。
    """
    tmp_path = setup_test_msprof_directory
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


def test_load_memory_data_with_valid_db_path(setup_test_msprof_directory):
    """
    测试当 db_path 有效时，load_memory_data 函数是否正确加载数据。
    """
    tmp_path = setup_test_msprof_directory
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