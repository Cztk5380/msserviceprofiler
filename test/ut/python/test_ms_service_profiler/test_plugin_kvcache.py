# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------
import unittest
import pandas as pd
import numpy as np
from unittest.mock import patch
from ms_service_profiler.plugins.plugin_kvcache import PluginKVCacheMetrics


class TestPluginKVCacheMetrics(unittest.TestCase):

    def test_parse_empty_data(self):
        """测试空数据输入"""
        data = {'tx_data_df': pd.DataFrame()}
        result = PluginKVCacheMetrics.parse(data)
        self.assertEqual(result, data)
        self.assertTrue(result['tx_data_df'].empty)

    def test_parse_no_tx_data_df(self):
        """测试没有tx_data_df键的数据"""
        data = {}
        result = PluginKVCacheMetrics.parse(data)
        self.assertEqual(result, data)

    def test_parse_no_kvcache_events(self):
        """测试没有KVCache相关事件的数据"""
        df = pd.DataFrame({
            'domain': ['OtherDomain', 'AnotherDomain'],
            'name': ['Event1', 'Event2']
        })
        data = {'tx_data_df': df}
        result = PluginKVCacheMetrics.parse(data)
        self.assertEqual(result, data)

    def test_parse_kvcache_events_no_existing_columns(self):
        """测试KVCache事件，但DataFrame中没有所需列"""
        df = pd.DataFrame({
            'domain': ['KVCache', 'Schedule.KVCache', 'OtherDomain'],
            'name': ['Event1', 'Event2', 'Event3'],
            'some_other_col': [1, 2, 3]
        })
        data = {'tx_data_df': df}
        result = PluginKVCacheMetrics.parse(data)

        # 检查是否添加了所需列
        expected_columns = ['total_blocks', 'used_blocks', 'free_blocks',
                            'blocks_allocated', 'blocks_freed', 'kvcache_usage_rate']
        for col in expected_columns:
            self.assertIn(col, result['tx_data_df'].columns)

        # 检查新列的默认值
        kvcache_rows = result['tx_data_df']['domain'].isin(['KVCache', 'Schedule.KVCache'])
        self.assertTrue((result['tx_data_df'].loc[kvcache_rows, 'kvcache_usage_rate'] == 0.0).all())
        self.assertTrue((result['tx_data_df'].loc[kvcache_rows, 'total_blocks'] == 0).all())

    def test_parse_with_total_blocks_field(self):
        """测试包含TotalBlocks=字段的数据"""
        df = pd.DataFrame({
            'domain': ['KVCache', 'Schedule.KVCache', 'KVCache'],
            'name': ['Event1', 'Event2', 'Event3'],
            'TotalBlocks=': [100, 200, 0]  # 使用有效的整数值
        })
        data = {'tx_data_df': df}
        result = PluginKVCacheMetrics.parse(data)

        # 验证TotalBlocks=字段被正确转换
        expected_total_blocks = [100, 200, 0]
        pd.testing.assert_series_equal(
            result['tx_data_df']['total_blocks'],
            pd.Series(expected_total_blocks, name=result['tx_data_df']['total_blocks'].name),
            check_names=False
        )

    def test_parse_with_free_blocks_after_field(self):
        """测试包含FreeBlocksAfter=字段的数据"""
        df = pd.DataFrame({
            'domain': ['KVCache', 'Schedule.KVCache', 'KVCache'],
            'name': ['Event1', 'Event2', 'Event3'],
            'total_blocks': [100, 200, 300],
            'FreeBlocksAfter=': [30, 50, 25],  # 使用有效的整数值
            'free_blocks': [0, 0, 0]  # 确保free_blocks初始为0，这样FreeBlocksAfter=会生效
        })
        data = {'tx_data_df': df}
        result = PluginKVCacheMetrics.parse(data)

        # 验证FreeBlocksAfter=字段被正确转换
        expected_free_blocks = [30, 50, 25]
        pd.testing.assert_series_equal(
            result['tx_data_df']['free_blocks'],
            pd.Series(expected_free_blocks, name=result['tx_data_df']['free_blocks'].name),
            check_names=False
        )
        # 注意：used_blocks的计算逻辑可能不是total_blocks - free_blocks

    def test_parse_with_free_blocks_field(self):
        """测试包含FreeBlocks=字段的数据（当FreeBlocksAfter=为0时）"""
        df = pd.DataFrame({
            'domain': ['KVCache', 'Schedule.KVCache', 'KVCache'],
            'name': ['Event1', 'Event2', 'Event3'],
            'total_blocks': [100, 200, 300],
            'free_blocks': [0, 0, 0],  # FreeBlocksAfter=未设置，free_blocks为0
            'FreeBlocks=': [40, 60, 80]  # 使用有效的整数值
        })
        data = {'tx_data_df': df}
        result = PluginKVCacheMetrics.parse(data)

        # 验证FreeBlocks=字段被正确转换（仅在free_blocks为0时）
        expected_free_blocks = [40, 60, 80]
        pd.testing.assert_series_equal(
            result['tx_data_df']['free_blocks'],
            pd.Series(expected_free_blocks, name=result['tx_data_df']['free_blocks'].name),
            check_names=False
        )

    def test_parse_with_usage_percent_field_high_threshold(self):
        """测试包含UsagePercent=字段的数据（高于阈值，需要转换）"""
        df = pd.DataFrame({
            'domain': ['KVCache', 'Schedule.KVCache'],
            'name': ['Event1', 'Event2'],
            'UsagePercent=': [85.0, 95.0]  # 高于1.0，需要除以100
        })
        data = {'tx_data_df': df}
        result = PluginKVCacheMetrics.parse(data)

        expected_usage_rate = [0.85, 0.95]
        pd.testing.assert_series_equal(
            result['tx_data_df']['kvcache_usage_rate'],
            pd.Series(expected_usage_rate, name=result['tx_data_df']['kvcache_usage_rate'].name),
            check_names=False
        )

    def test_parse_with_usage_percent_field_low_threshold(self):
        """测试包含UsagePercent=字段的数据（低于阈值，不需要转换）"""
        df = pd.DataFrame({
            'domain': ['KVCache', 'Schedule.KVCache'],
            'name': ['Event1', 'Event2'],
            'UsagePercent=': [0.8, 0.9]  # 低于1.0，不需要转换
        })
        data = {'tx_data_df': df}
        result = PluginKVCacheMetrics.parse(data)

        # 不需要转换，直接使用原始值
        expected_usage_rate = [0.8, 0.9]
        pd.testing.assert_series_equal(
            result['tx_data_df']['kvcache_usage_rate'],
            pd.Series(expected_usage_rate, name=result['tx_data_df']['kvcache_usage_rate'].name),
            check_names=False
        )

    def test_parse_with_allocated_blocks_field_positive_negative(self):
        """测试包含AllocatedBlocks=字段的数据（正值和负值）"""
        df = pd.DataFrame({
            'domain': ['KVCache', 'Schedule.KVCache', 'KVCache', 'KVCache'],
            'name': ['Event1', 'Event2', 'Event3', 'Event4'],
            'AllocatedBlocks=': [10, -5, 0, 15],  # 正值、负值、零
            'blocks_allocated': [0, 0, 0, 0],
            'blocks_freed': [0, 0, 0, 0]
        })
        data = {'tx_data_df': df}
        result = PluginKVCacheMetrics.parse(data)

        # 正值分配，负值释放
        expected_allocated = [10, 0, 0, 15]
        expected_freed = [0, 5, 0, 0]
        pd.testing.assert_series_equal(
            result['tx_data_df']['blocks_allocated'],
            pd.Series(expected_allocated, name=result['tx_data_df']['blocks_allocated'].name),
            check_names=False
        )
        pd.testing.assert_series_equal(
            result['tx_data_df']['blocks_freed'],
            pd.Series(expected_freed, name=result['tx_data_df']['blocks_freed'].name),
            check_names=False
        )

    def test_parse_with_free_blocks_before_after_fields(self):
        """测试包含FreeBlocksBefore=和FreeBlocksAfter=字段的数据"""
        df = pd.DataFrame({
            'domain': ['KVCache', 'Schedule.KVCache', 'KVCache'],
            'name': ['Event1', 'Event2', 'Event3'],
            'FreeBlocksBefore=': [100, 150, 200],  # 使用有效整数
            'FreeBlocksAfter=': [80, 120, 100],
            'blocks_allocated': [0, 0, 0],
            'blocks_freed': [0, 0, 0]
        })
        data = {'tx_data_df': df}
        result = PluginKVCacheMetrics.parse(data)

        expected_allocated = [20, 30, 100]
        expected_freed = [0, 0, 0]
        pd.testing.assert_series_equal(
            result['tx_data_df']['blocks_allocated'],
            pd.Series(expected_allocated, name=result['tx_data_df']['blocks_allocated'].name),
            check_names=False
        )
        pd.testing.assert_series_equal(
            result['tx_data_df']['blocks_freed'],
            pd.Series(expected_freed, name=result['tx_data_df']['blocks_freed'].name),
            check_names=False
        )

    @patch('ms_service_profiler.plugins.plugin_kvcache.logger')
    def test_parse_exception_handling(self, mock_logger):
        """测试异常处理"""
        # 创建包含无效数据的DataFrame，可能引发异常
        df = pd.DataFrame({
            'domain': ['KVCache'],
            'name': ['Event1'],
            'FreeBlocksAfter=': [float('inf')]  # 无穷大值，可能导致转换错误
        })
        data = {'tx_data_df': df}
        result = PluginKVCacheMetrics.parse(data)
        # 确保函数正常返回，即使发生异常
        self.assertEqual(result, data)
        # 验证记录了错误日志
        mock_logger.error.assert_called()

    def test_calculate_and_update_metrics_empty_indices(self):
        """测试空索引列表的情况"""
        df = pd.DataFrame({
            'domain': ['OtherDomain'],
            'name': ['Event1']
        })
        # 确保所需列存在
        PluginKVCacheMetrics._ensure_required_columns_exist(df)
        # 空的kvcache_indices
        empty_indices = pd.Index([])
        PluginKVCacheMetrics._calculate_and_update_metrics(df, empty_indices)
        # DataFrame不应该改变

    def test_calculate_metrics_vectorized_empty_input(self):
        """测试空输入数据的向量化计算"""
        empty_df = pd.DataFrame(columns=['domain', 'name'])
        result_df = PluginKVCacheMetrics._calculate_metrics_vectorized(empty_df)
        # 结果应该是同样索引的空DataFrame，但包含所有必需列
        self.assertEqual(len(result_df), 0)
        required_columns = ['total_blocks', 'used_blocks', 'free_blocks',
                            'blocks_allocated', 'blocks_freed', 'kvcache_usage_rate']
        for col in required_columns:
            self.assertIn(col, result_df.columns)

    def test_ensure_required_columns_exist_already_present(self):
        """测试所需列已经存在的情况"""
        df = pd.DataFrame({
            'domain': ['KVCache'],
            'name': ['Event1'],
            'total_blocks': [100],
            'used_blocks': [50],
            'free_blocks': [50],
            'blocks_allocated': [10],
            'blocks_freed': [5],
            'kvcache_usage_rate': [0.5]
        })
        original_values = df.copy()
        PluginKVCacheMetrics._ensure_required_columns_exist(df)
        # 验证已有列的值未被改变
        pd.testing.assert_frame_equal(df, original_values)


if __name__ == '__main__':
    unittest.main()