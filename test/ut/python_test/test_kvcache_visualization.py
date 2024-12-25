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

import pandas as pd
import pytest

import ms_service_profiler.views.grafana_visualization as visual


@pytest.fixture
def df():
    data = {
        'action': ['KVCacheAlloc', 'AppendSlot', 'Free'],
        'device_kvcache_left': [150, 50, 200],
        'rid': [0, 0, 0],
        'start_time(microsecond)': [1.72794e+15, 1.72794e+15, 1.72794e+15]
    }
    return pd.DataFrame(data)


def test_timestamp_to_datetime():
    timestamp_sci = 1.72794e+15
    expected = '2024-10-03 15:20:00:000000'
    expected_key_part = expected[:10]
    result_key_part = visual.timestamp_to_datetime(timestamp_sci)[:10]
    assert result_key_part == expected_key_part


def test_timestamp_to_datetime_non_scientific():
    # 测试非科学计数法的时间戳输入
    timestamp = '1727940000000000'
    expected = '2024-10-03 15:20:00:000000'
    expected_key_part = expected[:10]
    result_key_part = visual.timestamp_to_datetime(timestamp)[:10]
    assert result_key_part == expected_key_part


def test_kvcache_usage_rate_calculator(df):
    result = visual.kvcache_usage_rate_calculator(df)
    expected = pd.DataFrame({
        'action': ['KVCacheAlloc', 'AppendSlot', 'Free'],
        'device_kvcache_left': [150, 50, 200],
        'rid': [0, 0, 0],
        'start_time(microsecond)': [1.727940e+15, 1.727940e+15, 1.727940e+15],
        'kvcache_usage_rate': [0.25, 0.75, 0.0]
    })
    pd.testing.assert_frame_equal(result, expected)


def test_add_column_to_kvcache(df):
    result = visual.add_column_to_kvcache('kvcache.csv', df)
    expected = pd.DataFrame({
        'action': ['KVCacheAlloc', 'AppendSlot', 'Free'],
        'device_kvcache_left': [150, 50, 200],
        'rid':[0, 0, 0],
        'start_time(microsecond)': [1.72794e+15, 1.72794e+15, 1.72794e+15],
        'real_start_time': ['2024-10-03 15:20:00:000000', '2024-10-03 15:20:00:000000', '2024-10-03 15:20:00:000000'],
        'kvcache_usage_rate': [0.25, 0.75, 0.00]
    })
    expected['kvcache_usage_rate'] = expected['kvcache_usage_rate']
    expected['real_start_time'] = expected['real_start_time'].apply(lambda x: x[:10])
    result['real_start_time'] = result['real_start_time'].apply(lambda x: x[:10])
    pd.testing.assert_frame_equal(result, expected)


def test_kvcache_usage_rate_calculator_mixed_data_types(df):

    df_mixed = df.copy()
    df_mixed.loc[0, 'device_kvcache_left'] = "abc"
    with pytest.raises(TypeError):
        visual.kvcache_usage_rate_calculator(df_mixed)


def kvcache_usage_rate_calculator():
    # 测试KVCacheAlloc分支
    df = pd.DataFrame({
        'action': ['KVCacheAlloc'],
        'device_kvcache_left': [100]
    })
    df_free = pd.DataFrame({
        'action': ['Free'],
        'device_kvcache_left': [200]
    })
    group = pd.concat([df, df_free])
    assert visual.calculate_usage_rate(group) == [0.5, 0]

    # 测试AppendSlot分支
    df = pd.DataFrame({
        'action': ['AppendSlot'],
        'device_kvcache_left': [50]
    })
    df_free = pd.DataFrame({
        'action': ['Free'],
        'device_kvcache_left': [200]
    })
    group = pd.concat([df, df_free])
    assert visual.calculate_usage_rate(group) == [0.75, 0]

    # 测试Free分支
    df = pd.DataFrame({
        'action': ['Free'],
        'device_kvcache_left': [1000]
    })
    assert visual.calculate_usage_rate(df) == [0]

    # 测试其他action分支
    df = pd.DataFrame({
        'action': ['Other'],
        'device_kvcache_left': [100]
    })
    assert visual.calculate_usage_rate(df) == [None]

    # 测试没有Free action的情况
    df = pd.DataFrame({
        'action': ['KVCacheAlloc'],
        'device_kvcache_left': [100]
    })
    assert visual.calculate_usage_rate(df) == [0]

    # 测试Free action的device_kvcache_left为0的情况
    df = pd.DataFrame({
        'action': ['KVCacheAlloc'],
        'device_kvcache_left': [100]
    })
    df_free = pd.DataFrame({
        'action': ['Free'],
        'device_kvcache_left': [0]
    })
    group = pd.concat([df, df_free])
    assert visual.calculate_usage_rate(group) == [0, 0]
