# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
from collections import defaultdict

import pytest
import pandas as pd
from ms_service_profiler.plugins.plugin_concat import PluginConcat


@pytest.fixture
def sample_dataframes():
    df1 = pd.DataFrame({'start_time': [2, 1], 'data': [20, 10]})
    df2 = pd.DataFrame({'start_time': [4, 3], 'data': [40, 30]})
    return [{'merged_key': df1}, {'merged_key': df2}]


def test_merge_multiple_dataframes(sample_dataframes):
    result = PluginConcat.parse(sample_dataframes)
    merged_df = result['merged_key']

    assert len(merged_df) == 4
    pd.testing.assert_series_equal(
        merged_df['start_time'],
        pd.Series([1, 2, 3, 4], name='start_time')
    )


def test_msprof_merge_with_variants():
    df_list = [pd.DataFrame({'start_time': [1]}),
               pd.DataFrame({'start_time': [2]})]
    df_single = pd.DataFrame({'start_time': [3]})

    data = [
        {'msprof_data': df_list},
        {'msprof_data': df_single},
        {'msprof_data': None}  # 测试None值情况
    ]
    result = PluginConcat.parse(data)

    assert len(result['msprof_data']) == 3
    assert all(isinstance(df, pd.DataFrame) for df in result['msprof_data'])


def test_non_dataframe_values_ignored():
    data = [{'str_key': 'invalid_data'}, {'int_key': 123}]
    result = PluginConcat.parse(data)

    assert 'str_key' not in result
    assert 'int_key' not in result


def test_empty_data_input():
    result = PluginConcat.parse([])
    assert isinstance(result, defaultdict)
    assert len(result) == 0


def test_dataframe_sorting_reset_index():
    unsorted_df = pd.DataFrame({
        'start_time': [30, 10, 20],
        'data': ['c', 'a', 'b']
    })
    data = [{'sorted_key': unsorted_df}]
    result = PluginConcat.parse(data)

    sorted_df = result['sorted_key']
    expected_order = [10, 20, 30]
    assert sorted_df['start_time'].tolist() == expected_order
    assert sorted_df.index.tolist() == [0, 1, 2]
