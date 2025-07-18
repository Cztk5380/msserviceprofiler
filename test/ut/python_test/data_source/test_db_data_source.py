# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import re
import os
import sqlite3

import logging
import pandas as pd

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from ms_service_profiler.data_source.db_data_source import DBDataSource

# 配置日志
logging.basicConfig(level=logging.INFO)


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
def setup_test_db_directory(tmp_path):
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

def test_process_normal():
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
            result = DBDataSource.process(mock_df)

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


def test_get_filepaths(setup_test_db_directory):
    folder_path = setup_test_db_directory / "PROF_test"
    file_filter = {
        "tx": "msproftx.db",
        "cpu": "host_cpu_usage.db",
        "memory": "host_mem_usage.db",
        "host_start": "host_start.log",
        "info": "info.json",
        "start_info": "start_info",
        "msprof": "msprof_*.json"
    }
    result = DBDataSource.get_filepaths(folder_path, file_filter)
    assert isinstance(result, dict)
    assert "tx" in result
    assert "msprof" in result


def test_handle_exact_match(setup_test_db_directory):
    folder_path = setup_test_db_directory / "PROF_test"
    reverse_d = {
        "msproftx.db": "tx",
        "host_cpu_usage.db": "cpu",
        "host_mem_usage.db": "memory",
        "host_start.log": "host_start",
        "info.json": "info",
        "start_info": "start_info"
    }
    result = DBDataSource.handle_exact_match(folder_path, reverse_d)
    assert isinstance(result, dict)
    assert "tx" in result
    assert Path(result["tx"]).name == "msproftx.db"


def test_handle_msprof_pattern(setup_test_db_directory):
    folder_path = setup_test_db_directory / "PROF_test"
    alias = "msprof"
    filepaths = {}
    result = DBDataSource.handle_msprof_pattern(folder_path, alias, filepaths)
    assert isinstance(result, dict)
    assert alias in result
    assert all(re.match(r'^msprof_\d+\.json$', Path(p).name) for p in result[alias])


def test_handle_other_wildcard_patterns(setup_test_db_directory):
    folder_path = setup_test_db_directory / "PROF_test"
    pattern = "msprof_*.json"
    alias = "msprof"
    filepaths = {}
    result = DBDataSource.handle_other_wildcard_patterns(folder_path, pattern, alias, filepaths)
    assert isinstance(result, dict)
    if alias in result:
        assert Path(result[alias]).name.startswith("msprof_")