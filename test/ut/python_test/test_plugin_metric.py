# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from unittest.mock import patch

import pytest
import pandas as pd
import numpy as np

from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.plugins.plugin_metric import PluginMetric, is_metric
from ms_service_profiler.utils.error import DataFrameMissingError, ColumnMissingError


@pytest.fixture
def valid_tx_data():
    """包含必要列和指标列的合法数据"""
    return pd.DataFrame({
        'name': ['httpReq', 'other', 'httpReq'],
        'start_time': [100, 200, 300],
        'start_datetime': ['2023-01-01', '2023-01-02', '2023-01-03'],
        'CPU+': [1.0, 2.0, 3.0],
        'Memory=': [10, 20, 30],
        'invalid_metric': ['a', 'b', 'c']
    })


@pytest.fixture
def sample_data():
    data = {
        'tx_data_df': pd.DataFrame({
            'name': ['httpReq', 'ReqState', 'httpReq', 'ReqState'],
            'start_time': [1696321692, 1696321693, 1696321694, 169632165],
            'start_datetime': [1696321692, 1696321693, 1696321694, 169632165],
            'message': [{'0': 1}, {'1': 1}, {'0': 2}, {'2': 3}],
            '0+': [1, None, 2, None],
            '1+': [None, 1, None, 2],
            '2+': [None, None, None, 3],
        })
    }
    return data


@pytest.fixture
def sample_data_without_start_datetime():
    data = {
        'tx_data_df': pd.DataFrame({
            'name': ['httpReq', 'ReqState', 'httpReq', 'ReqState'],
            'start_time': [1696321692, 1696321693, 1696321694, 169632165],
            'message': [{'0': 1}, {'1': 1}, {'0': 2}, {'2': 3}],
            '0+': [1, None, 2, None],
            '1+': [None, 1, None, 2],
            '2+': [None, None, None, 3],
        })
    }
    return data


@pytest.fixture
def empty_data():
    return {}


def test_count(sample_data):
    plugin = PluginMetric()
    result = plugin.parse(sample_data)
    assert 'metric_data_df' in result
    assert all(result['metric_data_df']["0"] == [1, 1, 3, 3])


def test_no_tx_data_df(empty_data):
    plugin = PluginMetric()
    with pytest.raises(DataFrameMissingError):
        plugin.parse(empty_data)


def test_no_start_datetime(sample_data_without_start_datetime, capsys):
    plugin = PluginMetric()
    with patch("ms_service_profiler.utils.error.logger.warning") as mock_warning:
        plugin.parse(sample_data_without_start_datetime)
        mock_warning.assert_called_once_with(
            ColumnMissingError(("start_datetime",), "ignoring current process by default."))


def test_is_metric():
    assert is_metric('1+') is True
    assert is_metric('1=') is True
    assert is_metric('1') is False


def test_normal_processing(valid_tx_data):
    data = {'tx_data_df': valid_tx_data}
    result = PluginMetric.parse(data)

    # 验证新增的指标表
    df = result['metric_data_df']
    assert set(df.columns) == {'start_time',
                               'start_datetime', 'CPU', 'Memory'}

    # 验证指标列转换
    assert 'CPU' in df.columns
    assert 'Memory' in df.columns

    # 验证累加逻辑
    assert df['CPU'].tolist() == [1.0, 3.0, 6.0]


def test_missing_tx_data():
    with pytest.raises(DataFrameMissingError) as exc_info:
        PluginMetric.parse({})
    assert "tx_data_df" in str(exc_info.value)


def test_missing_required_columns(valid_tx_data):
    with patch("ms_service_profiler.utils.error.logger.warning") as mock_warning:
        # 删除start_time列测试
        invalid_data = valid_tx_data.drop(columns=['start_time'])
        PluginMetric.parse({'tx_data_df': invalid_data})
        mock_warning.assert_called_once_with(
            ColumnMissingError(("start_time",), "ignoring current process by default."))


def test_increase_calculation():
    # 测试增量指标计算逻辑
    data = pd.DataFrame({
        'name': ['a', 'b'],
        'start_time': [1, 2],
        'start_datetime': ['t1', 't2'],
        'Req+': ['10', 20]  # 测试类型转换
    })
    result = PluginMetric.parse({'tx_data_df': data})
    df = result['metric_data_df']
    assert df['Req'].tolist() == [10.0, 30.0]


def test_non_numeric_metric_values():
    # 测试无法转换为数值的情况
    data = pd.DataFrame({
        'name': ['test'],
        'start_time': [100],
        'start_datetime': ['2023-01-01'],
        'Error+': ['invalid']
    })
    result = PluginMetric.parse({'tx_data_df': data})
    assert result['metric_data_df']['Error'].iloc[0] == 0.0


def test_metric_renaming():
    # 测试指标重命名规则
    data = pd.DataFrame({
        'name': ['test'],
        'start_time': [100],
        'start_datetime': ['2023-01-01'],
        'Temp+': [5],
        'Pressure=': [10]
    })
    result = PluginMetric.parse({'tx_data_df': data})
    assert 'Temp' in result['metric_data_df'].columns
    assert 'Pressure' in result['metric_data_df'].columns
