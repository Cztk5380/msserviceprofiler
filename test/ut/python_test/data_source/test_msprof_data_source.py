# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from ms_service_profiler.data_source.msprof_data_source import MsprofDataSource
from ms_service_profiler.utils.error import LoadDataError


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
@patch('ms_service_profiler.parse.load_prof')
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