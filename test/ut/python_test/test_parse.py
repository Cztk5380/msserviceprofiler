# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import os
import pandas as pd
import sqlite3
from pathlib import Path
import json
import re
from unittest.mock import patch, MagicMock
import pytest
import shutil


from ms_service_profiler.parse import (
    read_origin_db,
    get_filepaths,
    handle_exact_match,
    handle_msprof_pattern,
    handle_other_wildcard_patterns,
    save_dataframe_to_csv,
    load_start_cnt,
    load_start_time,
    load_tx_data
)


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
    (prof_dir / "start_info").write_text('{"collectionTimeBegin": "123456.789"}')
    (prof_dir / "msprof_20250211122756.json").write_text('{"data": "example data"}')

    # 创建测试数据库文件
    db_path = prof_dir / "msproftx.db"
    build_msproftx_db(db_path)

    yield tmp_path  # 这里使用 yield 来返回 tmp_path，并允许在退出前执行清理操作

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
        assert len(data_list) == 1
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


def test_save_dataframe_to_csv(setup_test_directory):
    df = pd.DataFrame({
        'A': [1, 2, 3],
        'B': [4, 5, 6]
    })

    save_dataframe_to_csv(df, setup_test_directory, 'test.csv')

    # 检查文件是否创建
    output_file_path = os.path.join(setup_test_directory, 'test.csv')
    assert os.path.isfile(output_file_path)


def test_load_start_cnt(setup_test_directory):
    config_path = setup_test_directory / "PROF_test" / "host_start.log"

    # 测试函数并获取结果
    cntvct, clock_monotonic_raw = load_start_cnt(config_path)

    # 验证返回值
    assert cntvct == 123
    assert clock_monotonic_raw == 456


def test_load_start_time(setup_test_directory):
    start_info_path = setup_test_directory / "PROF_test" / "start_info"

    result = load_start_time(start_info_path)
    assert result == 123456.789

def test_load_tx_data(setup_test_directory):
    db_path = setup_test_directory / "PROF_test" / "msproftx.db"
    result = load_tx_data(db_path)

    # 验证结果
    assert result is not None
    assert all(result.columns == ['pid', 'tid', 'event_type', 'start_time', 'end_time', 'mark_id',
       'ori_msg', 'message', 'name', 'span_id'])
    assert result.shape[0] == 1
