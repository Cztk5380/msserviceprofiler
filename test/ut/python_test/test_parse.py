# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from pathlib import Path
import re
from unittest.mock import patch, MagicMock
import pytest

from ms_service_profiler.parse import (
    read_origin_db,
    get_filepaths,
    handle_exact_match,
    handle_msprof_pattern,
    handle_other_wildcard_patterns
)


class LoadDataError(Exception):
    pass


def load_prof(filepaths):
    return filepaths


@pytest.fixture
def setup_test_directory(tmp_path):
    # 创建测试目录结构
    prof_dir = tmp_path / "PROF_test"
    prof_dir.mkdir()

    # 精确匹配文件
    (prof_dir / "msproftx.db").write_text("tx data")
    (prof_dir / "host_cpu_usage.db").write_text("cpu data")
    (prof_dir / "host_mem_usage.db").write_text("memory data")
    (prof_dir / "host_start.log").write_text("host start log")
    (prof_dir / "info.json").write_text('{"key": "value"}')

    # 创建 start_info 目录
    start_info_dir = prof_dir / "start_info"
    start_info_dir.mkdir()

    # 创建 msprof_*.json 文件
    (prof_dir / "msprof_20250211122756.json").write_text('{"data": "example data"}')

    return tmp_path


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
