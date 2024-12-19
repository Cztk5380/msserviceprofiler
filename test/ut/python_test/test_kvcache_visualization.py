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

from unittest.mock import patch, MagicMock
import os
import argparse
import pandas as pd
import pytest

import ms_service_profiler.views.grafana_visualization as visual


@pytest.fixture
def df():
    data = {
        'action': ['KVCacheAlloc', 'AppendSlot', 'Free'],
        'device_kvcache_left': [150, 50, 200],
        'start_time(microsecond)': [1.72794e+15, 1.72794e+15, 1.72794e+15]
    }
    return pd.DataFrame(data)


def test_timestamp_to_datetime():
    timestamp_sci = 1.72794e+15
    expected = '2024-10-03 07:20:00:000000'
    assert visual.timestamp_to_datetime(timestamp_sci) == expected


def test_kvcache_usage_rate_calculator(df):
    result = visual.kvcache_usage_rate_calculator(df)
    expected = pd.DataFrame({
        'action': ['KVCacheAlloc', 'AppendSlot', 'Free'],
        'device_kvcache_left': [150, 50, 200],
        'start_time(microsecond)': [1.72794e+15, 1.72794e+15, 1.72794e+15],
        'kvcache_usage_rate': [0.25, 0.75, 0.00]
    })
    pd.testing.assert_frame_equal(result, expected)


def test_add_column_to_kvcache(df):
    result = visual.add_column_to_kvcache('kvcache.csv', df)
    expected = pd.DataFrame({
        'action': ['KVCacheAlloc', 'AppendSlot', 'Free'],
        'device_kvcache_left': [150, 50, 200],
        'start_time(microsecond)': [1.72794e+15, 1.72794e+15, 1.72794e+15],
        'real_start_time': ['2024-10-03 07:20:00:000000', '2024-10-03 07:20:00:000000', '2024-10-03 07:20:00:000000'],
        'kvcache_usage_rate': [0.25, 0.75, 0.00]
    })
    pd.testing.assert_frame_equal(result, expected)


def test_timestamp_to_datetime_invalid_format_input():
    # 期望false
    invalid_timestamp = "abcdefg"  # 完全不符合数字格式的示例
    with pytest.raises(TypeError):
        visual.timestamp_to_datetime(invalid_timestamp)


def test_kvcache_usage_rate_calculator_duplicate_actions(df):
    duplicate_data = df.append(df.iloc[0:1], ignore_index=True)
    result = visual.kvcache_usage_rate_calculator(duplicate_data)
    assert len(result) == len(duplicate_data)


def test_kvcache_usage_rate_calculator_mixed_data_types(df):
    df_mixed = df.copy()
    df_mixed.loc[0, 'device_kvcache_left'] = "abc"
    with pytest.raises(TypeError):
        visual.kvcache_usage_rate_calculator(df_mixed)


