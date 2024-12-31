# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import os
import argparse
import unittest
from unittest.mock import patch
import pandas as pd
from ms_service_profiler.exporters.exporter_kvcache import (
kvcache_usage_rate_calculator,
get_max_free_value,
calculate_action_usage_rate,
build_rid_to_action_usage_rates,
build_result_df,
kvcache_usage_rate_calculator,
)


class TestKvcacheFunctions(unittest.TestCase):
    def setUp(self):
        data = {
            'domain': ['KVCache', 'KVCache', 'KVCache', 'KVCache'],
            'rid': [0, 1, 2, 3],
            'start_time(microsecond)': ['1735124796367194', '1735124796367220', '1735124796367233', '1735124796367242'],
            'end_time(microsecond)': ['1735124796367194', '1735124796367220', '1735124796367233', '1735124796367242'],
            'name': ['Allocate', 'Free', 'AppendSlot', 'AppendSlot'],
            'device_kvcache_left': [1978, 1977, 1976, 1975],
            'during_time(microsecond)': ['0', '0', '0', '0'],
            'real_start_time': ['2024-12-25', '2024-12-25', '2024-12-25', '2024-12-25']
        }
        self.kvcache_df = pd.DataFrame(data)

    def test_get_max_free_value(self):
        """
        测试get_max_free_value函数
        """
        result = get_max_free_value(self.kvcache_df)
        expected_max_value = self.kvcache_df[self.kvcache_df['name'] == 'Free']['device_kvcache_left'].max()
        self.assertEqual(result, expected_max_value)

    def test_calculate_action_usage_rate(self):
        """
        测试calculate_action_usage_rate函数
        """
        action = 'Allocate'
        value = 10
        max_free_value = 20
        result = calculate_action_usage_rate(action, value, max_free_value)
        expected_result = (max_free_value - value) / max_free_value
        self.assertEqual(result, expected_result)

        action = 'OtherAction'
        result = calculate_action_usage_rate(action, value, max_free_value)
        self.assertEqual(result, 0)

    def test_build_rid_to_action_usage_rates(self):
        """
        测试build_rid_to_action_usage_rates函数
        """
        max_free_value = get_max_free_value(self.kvcache_df)
        result = build_rid_to_action_usage_rates(self.kvcache_df, max_free_value)
        self.assertIsInstance(result, dict)
        rid = 1
        self.assertIn(rid, result)
        action_usage_rates_list = result[rid]
        self.assertIsInstance(action_usage_rates_list, list)

    def test_build_result_df(self):
        """
        测试build_result_df函数
        """
        max_free_value = get_max_free_value(self.kvcache_df)
        rid_to_action_usage_rates = build_rid_to_action_usage_rates(self.kvcache_df, max_free_value)
        result = build_result_df(self.kvcache_df, rid_to_action_usage_rates)
        self.assertIsInstance(result, pd.DataFrame)
        expected_columns = [
            'rid',
            'name',
            'real_start_time',
            'device_kvcache_left',
            'kvcache_usage_rate'
        ]
        self.assertEqual(list(result.columns), expected_columns)

    def test_kvcache_usage_rate_calculator(self):
        """
        测试kvcache_usage_rate_calculator函数
        """
        result = kvcache_usage_rate_calculator(self.kvcache_df)
        self.assertIsInstance(result, pd.DataFrame)


if __name__ == '__main__':
    unittest.main()