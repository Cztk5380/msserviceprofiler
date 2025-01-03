# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from unittest.mock import patch

import pytest
import pandas as pd

from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.plugins.plugin_metric import PluginMetric, is_metric
from ms_service_profiler.utils.error import DataFrameMissingError, ColumnMissingError


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
    with pytest.raises(ColumnMissingError):
        plugin.parse(sample_data_without_start_datetime)


def test_is_metric():
    assert is_metric('1+') is True
    assert is_metric('1=') is True
    assert is_metric('1') is False
