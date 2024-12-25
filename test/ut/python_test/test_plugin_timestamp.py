# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import datetime
import psutil

import pytest
import pandas as pd

from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.plugins.plugin_timestamp import \
    PluginTimeStamp, convert_syscnt_to_ts, timestamp_converter


# Test Data Setup
@pytest.fixture
def sample_data():
    """Fixture for sample input data."""
    return {
        'tx_data_df': pd.DataFrame({
            'start_time': [100000, 200000, 300000],
            'end_time': [150000, 250000, 350000]
        }),
        'cpu_data_df': pd.DataFrame({
            'start_time': [500000, 600000, 700000],
            'end_time': [550000, 650000, 750000]
        }),
        'time_info':{
            'cpu_start_cnt': 1000,
            'cpu_frequency': 2.5,
            'sys_start_cnt': 2000,
            'sys_start_time': 124657,
        }
    }

@pytest.fixture
def edge_case_data():
    return {
        'tx_data_df': pd.DataFrame({
            'start_time': [],
            'end_time': []
        }),
        'cpu_data_df': pd.DataFrame({
            'start_time': [],
            'end_time': []
        }),
        'time_info':{
            'cpu_start_cnt': 1000,
            'cpu_frequency': 2.5,
            'sys_start_cnt': 2000,
            'sys_start_time': 124657,
        }
    }

def test_timestamp_converter():
    """Test timestamp_converter function."""
    timestamp = 1609459200000000  # Example: January 1st, 2021 00:00:00.000000 UTC in microseconds

    result = timestamp_converter(timestamp)
    expected = datetime.datetime.fromtimestamp(timestamp / 1000000).strftime("%Y-%m-%d %H:%M:%S:%f")
    assert result == expected


def test_plugin_timestamp_parse(sample_data):
    """Test the PluginTimeStamp.parse method with valid input."""
    plugin = PluginTimeStamp()

    # Run the parse method
    result = plugin.parse([sample_data])[0]

    # Assertions
    assert 'tx_data_df' in result
    assert 'cpu_data_df' in result

    # Validate the `tx_data_df` DataFrame columns
    tx_data_df = result['tx_data_df']
    assert 'start_time' in tx_data_df.columns
    assert 'end_time' in tx_data_df.columns
    assert 'start_datetime' in tx_data_df.columns
    assert 'end_datetime' in tx_data_df.columns
    assert 'during_time' in tx_data_df.columns

    # Validate that the start_time, end_time, start_datetime, and end_datetime are correctly processed
    assert isinstance(tx_data_df['start_datetime'].iloc[0], str)
    assert isinstance(tx_data_df['end_datetime'].iloc[0], str)
    assert isinstance(tx_data_df['during_time'].iloc[0], (int, float))

    # Validate the `cpu_data_df` DataFrame columns
    cpu_data_df = result['cpu_data_df']
    assert 'start_time' in cpu_data_df.columns
    assert 'end_time' in cpu_data_df.columns
    assert 'start_datetime' in cpu_data_df.columns
    assert 'end_datetime' in cpu_data_df.columns
    assert 'during_time' in cpu_data_df.columns

    assert isinstance(cpu_data_df['start_datetime'].iloc[0], str)
    assert isinstance(cpu_data_df['end_datetime'].iloc[0], str)
    assert isinstance(cpu_data_df['during_time'].iloc[0], (int, float))


@pytest.mark.parametrize("cnt, start_cnt, time_info, expected_result", [
    (1000000, 0, {"sys_start_time": 10, "cpu_frequency": 2.5}, (10 + ((1000000 - 0) / 2.5)) * 1000000),
    (2000000, 1000, {"sys_start_time": 20, "cpu_frequency": 1.5}, (20 + ((2000000 - 1000) / 1.5)) * 1000000),
    (3000000, 1000, {"sys_start_time": 20, "cpu_frequency": 3.0}, (20 + ((3000000 - 1000) / 3.0)) * 1000000),
])
def test_convert_syscnt_to_ts_parametric(cnt, start_cnt, time_info, expected_result):
    """Test convert_syscnt_to_ts with parameterized values."""
    result = convert_syscnt_to_ts(cnt, start_cnt, time_info)
    assert result == expected_result


@pytest.mark.parametrize("timestamp, expected", [
    (1609459200000000, "2021-01-01 00:00:00:000000"),
    (1614556800000000, "2021-03-01 00:00:00:000000"),
])
def test_timestamp_converter_parametric(timestamp, expected):
    """Test timestamp_converter with parameterized values."""
    result = timestamp_converter(timestamp)
    assert len(result) == len(expected)


def test_plugin_timestamp_with_edge_cases(edge_case_data):
    """Test PluginTimeStamp with edge cases (e.g., empty DataFrames)."""
    plugin = PluginTimeStamp()

    # Run parse method on edge case data
    result = plugin.parse([edge_case_data])[0]

    # Assert the result is empty DataFrames
    assert result['tx_data_df'].empty
    assert result['cpu_data_df'].empty


def test_plugin_timestamp_missing_data():
    """Test PluginTimeStamp.parse with missing required fields in the input data."""
    plugin = PluginTimeStamp()

    # Missing 'cpu_start_cnt' from the data
    missing_data = {
        'tx_data_df': pd.DataFrame({
            'start_time': [100000, 200000, 300000],
            'end_time': [150000, 250000, 350000]
        }),
        'cpu_data_df': pd.DataFrame({
            'start_time': [500000, 600000, 700000],
            'end_time': [550000, 650000, 750000]
        }),
        'cpu_frequency': 2.5,
        'sys_start_cnt': 2000
    }

    with pytest.raises(AttributeError):
        plugin.parse([missing_data])
