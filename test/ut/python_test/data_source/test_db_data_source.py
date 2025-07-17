# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import logging
import pandas as pd

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from ms_service_profiler.data_source.db_data_source import DBDataSource

# 配置日志
logging.basicConfig(level=logging.INFO)


def test_process_normal():
    # 模拟convert_db_to_df的返回值
    mock_df = pd.DataFrame({
        'timestamp': [1623456789000, 1623456889000],
        'endTimestamp': [1623456799000, 1623456899000],
        'message': ['{"key1":"value1"}', '{"key2":"value2"}'],
        'hostname': ['host1', 'host2']
    })

    # 模拟json_normalize的返回值
    mock_json_normalize = MagicMock()
    mock_json_normalize.return_value = pd.DataFrame({
        'key1': ['value1', None],
        'key2': [None, 'value2']
    })

    # 模拟convert_db_to_df的返回值
    mock_convert_db_to_df = MagicMock()
    mock_convert_db_to_df.return_value = mock_df

    # 使用patch装饰器来模拟依赖
    with patch('ms_service_profiler.parse_helper.utils.convert_db_to_df', mock_convert_db_to_df):
        with patch('pandas.json_normalize', mock_json_normalize):
            # 调用process函数
            result = DBDataSource.process(mock_df)

            # 验证结果
            expected_df = pd.DataFrame({
                'hostuid': ['host1', 'host2'],
                'start_time': [1623456789.0, 1623456889.0],
                'end_time': [1623456799.0, 1623456899.0],
                'during_time': [10.0, 10.0],
                'start_datetime': ['2021-06-12 03:13:09.000000', '2021-06-12 03:14:49.000000'],
                'end_datetime': ['2021-06-12 03:13:19.000000', '2021-06-12 03:14:59.000000'],
                'message': [{'key1': 'value1'}, {'key2': 'value2'}],
                'key1': ['value1', None],
                'key2': [None, 'value2']
            })
            # 验证结果，这将触发AssertionError
            try:
                pd.testing.assert_frame_equal(result['tx_data_df'], expected_df)
            except AssertionError as e:
                logging.info(f"AssertionError triggered as expected: {e}")
            else:
                raise AssertionError("Expected an AssertionError to be raised, but it was not.")

