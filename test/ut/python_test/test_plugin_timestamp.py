# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
from datetime import datetime

import pytest
import pandas as pd
import numpy as np
from ms_service_profiler.constant import US_PER_SECOND, NS_PER_US
from ms_service_profiler.plugins.plugin_timestamp import (
    PluginTimeStampHelper,
    PluginTimeStamp,
    convert_syscnt_to_ts,
    convert_systs_to_ts,
    timestamp_converter,
    calculate_timestamp,
)


@pytest.fixture
def sample_time_info():
    """提供时间信息"""
    return {
        'cpu_frequency': 1e9,  # 1 GHz
        'collection_time_begin': 1000000,  # 1秒，单位微秒
        'cntvct': 500,  # 系统计数起始值
        'clock_monotonic_raw': 2000000000,  # 2秒，单位纳秒
        'host_clock_monotonic_raw': 2000000000,
        'start_clock_monotonic_raw': 2000000000
    }


@pytest.fixture
def sample_tx_data():
    """提供事务数据"""
    return pd.DataFrame({
        'start_time': [600, 700],  # 系统计数
        'end_time': [800, 900],
    })


@pytest.fixture
def sample_cpu_data():
    """提供CPU数据"""
    return pd.DataFrame({
        'start_time': [2100000000, 2200000000],  # 系统时间戳，单位纳秒
        'end_time': [2300000000, 2400000000],
    })


@pytest.fixture
def sample_cpu_data_wrong_format():
    """提供CPU数据"""
    return pd.DataFrame({
        'start_time': ["2100000000", 2200000000],  # 系统时间戳，单位纳秒
        'end_time': [2300000000, 2400000000],
    })


def test_convert_syscnt_to_ts(sample_time_info):
    """测试系统计数转换为时间戳"""
    cnt = 600
    expected_ts = 1000000.1
    assert convert_syscnt_to_ts(
        cnt, sample_time_info) == pytest.approx(expected_ts)


def test_convert_syscnt_to_ts_wrong_format(sample_cpu_data_wrong_format):
    """测试系统计数转换为时间戳"""
    cnt = 600
    expected_ts = 1000000.1
    with pytest.raises(AttributeError) as exc_info:
        assert convert_syscnt_to_ts(
            cnt, sample_cpu_data_wrong_format) == pytest.approx(expected_ts)


def test_convert_systs_to_ts(sample_time_info):
    """测试系统时间戳转换为时间戳"""
    systs = 2100000000
    expected_ts = 1100000  # 1秒 + (2100000000-2000000000)/1000 = 1.1秒
    assert convert_systs_to_ts(
        systs, sample_time_info) == pytest.approx(expected_ts)


def test_convert_systs_to_ts_wrong_format(sample_cpu_data_wrong_format):
    """测试系统时间戳转换为时间戳"""
    systs = 2100000000
    expected_ts = 1100000  # 1秒 + (2100000000-2000000000)/1000 = 1.1秒
    with pytest.raises(AttributeError) as exc_info:
        assert convert_systs_to_ts(
            systs, sample_cpu_data_wrong_format) == pytest.approx(expected_ts)


def test_timestamp_converter():
    """测试时间戳转换为日期时间字符串"""
    timestamp = 1000000  # 1秒
    expected_str = datetime.fromtimestamp(1).strftime("%Y-%m-%d %H:%M:%S:%f")
    assert timestamp_converter(timestamp) == expected_str


def test_calculate_timestamp_system_count(sample_tx_data, sample_time_info):
    """测试系统计数的时间戳计算"""
    calculate_timestamp(sample_tx_data, sample_time_info,
                        prof_type='system_count')
    assert 'during_time' in sample_tx_data.columns
    assert 'start_datetime' in sample_tx_data.columns
    assert 'end_datetime' in sample_tx_data.columns
    assert sample_tx_data['during_time'].iloc[0] == pytest.approx(0.2)


def test_calculate_timestamp_system_timestamp(sample_cpu_data, sample_time_info):
    """测试系统时间戳的时间戳计算"""
    calculate_timestamp(sample_cpu_data, sample_time_info,
                        prof_type='system_timestamp')
    assert 'during_time' in sample_cpu_data.columns
    assert 'start_datetime' in sample_cpu_data.columns
    assert 'end_datetime' in sample_cpu_data.columns
    assert sample_cpu_data['during_time'].iloc[0] == pytest.approx(200000)


def test_calculate_timestamp_missing_columns(sample_tx_data, sample_time_info):
    """测试缺少必要列的情况"""
    sample_tx_data.drop(columns=['start_time'], inplace=True)
    with pytest.raises(KeyError):
        calculate_timestamp(sample_tx_data, sample_time_info)


def test_plugin_timestamp_helper(sample_tx_data, sample_cpu_data, sample_time_info):
    """测试PluginTimeStampHelper的parse方法"""
    data = {
        'tx_data_df': sample_tx_data,
        'cpu_data_df': sample_cpu_data,
        'memory_data_df': None,
        'msprof_data': None,
        'time_info': sample_time_info,
    }
    result = PluginTimeStampHelper.parse(data)
    assert 'tx_data_df' in result
    assert 'cpu_data_df' in result
    assert 'memory_data_df' in result
    assert 'msprof_data_df' in result


def test_plugin_timestamp_helper_missing_time_info(sample_tx_data):
    """测试缺少time_info的情况"""
    data = {
        'tx_data_df': sample_tx_data,
        'cpu_data_df': None,
        'memory_data_df': None,
        'msprof_data': None,
        'time_info': None,
    }
    with pytest.raises(ValueError):
        PluginTimeStampHelper.parse(data)


def test_plugin_timestamp(sample_tx_data, sample_cpu_data, sample_time_info):
    """测试PluginTimeStamp的parse方法"""
    data = [{
        'tx_data_df': sample_tx_data,
        'cpu_data_df': sample_cpu_data,
        'memory_data_df': None,
        'msprof_data': None,
        'time_info': sample_time_info,
    }]
    result = PluginTimeStamp.parse(data)
    assert len(result) == 1
    assert 'tx_data_df' in result[0]
    assert 'cpu_data_df' in result[0]
