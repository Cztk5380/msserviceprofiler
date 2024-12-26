# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import pytest
import os
import argparse
import unittest
from unittest.mock import patch
import pandas as pd
from ms_service_profiler.exporters.exporter_kvcache import(
kvcache_usage_rate_calculator,
check_db_path_valid,
timestamp_converter,
get_max_free_value,
calculate_action_usage_rate,
build_rid_to_action_usage_rates,
build_result_df,
kvcache_usage_rate_calculator,
save_csv_to_sqlite,
create_sqlite_db
)


class TestKvcacheFunctions(unittest.TestCase):
    def setUp(self):
        data = {
            'rid': [1, 1, 2, 2],
            'name': ['Allocate', 'Free', 'AppendSlot', 'Free'],
            'real_start_time': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04'],
            'device_kvcache_left': [10, 20, 15, 25]
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
        self.assertTrue(result, expected_result)

        action = 'OtherAction'
        result = calculate_action_usage_rate(action, value, max_free_value)
        self.assertTrue(result, 0)

    def test_build_rid_to_action_usage_rates(self):
        """
        测试build_rid_to_action_usage_rates函数
        """
        max_free_value = get_max_free_value(self.kvcache_df)
        result = build_rid_to_action_usage_rates(self.kvcache_df, max_free_value)
        self.assertTrue(isinstance(result, dict), True)
        rid = 1
        self.assertIn(rid, result)
        action_usage_rates_list = result[rid]
        self.assertTrue(isinstance(action_usage_rates_list, list), True)

    def test_build_result_df(self):
        """
        测试build_result_df函数
        """
        max_free_value = get_max_free_value(self.kvcache_df)
        rid_to_action_usage_rates = build_rid_to_action_usage_rates(self.kvcache_df, max_free_value)
        result = build_result_df(self.kvcache_df, rid_to_action_usage_rates)
        self.assertEqual(isinstance(result, pd.DataFrame), True)
        self.assertEqual(list(result.columns), ['rid', 'name', 'real_start_time', 'device_kvcache_left', 'kvcache_usage_rate'])

    def test_kvcache_usage_rate_calculator(self):
        """
        测试kvcache_usage_rate_calculator函数
        """
        result = kvcache_usage_rate_calculator(self.kvcache_df)
        self.assertTrue(isinstance(result, pd.DataFrame), True)


if __name__ == '__main__':
    unittest.main()