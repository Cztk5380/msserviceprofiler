# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import unittest
from unittest.mock import patch, MagicMock

import pandas as pd

from ms_service_profiler.plugins.plugin_process_name import PluginProcessName
from ms_service_profiler.utils.log import logger


class TestPluginProcessName(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 设置测试所需的公共资源
        cls.tx_data_df = pd.DataFrame({
            "domain": ["KVCache", "KVCache", "Other"],
            "rid": [1, 2, 3],
            "scope#dp": ["dp1", "dp2", None],
            "pid": [100, 200, 300],
            "hostname": ["host1", "host2", "host3"],
            "hostuid": [1000, 2000, 3000],
            "name": ["preprocess", "preprocess", "other"],
            "rid_list": [[1], [2], [3]]
        })
        cls.data = {"tx_data_df": cls.tx_data_df}

    @patch.object(logger, 'debug')
    @patch.object(logger, 'info')
    def test_parse_no_scope_dp_or_rid(self, mock_logger_info, mock_logger_debug):
        # 测试当tx_data_df中没有scope#dp或rid时，parse方法直接返回数据
        data = {"tx_data_df": pd.DataFrame()}
        result = PluginProcessName.parse(data)
        self.assertEqual(result, data)
        mock_logger_debug.assert_not_called()
        mock_logger_info.assert_not_called()

    @patch.object(logger, 'debug')
    @patch.object(logger, 'info')
    def test_parse_with_scope_dp_and_rid(self, mock_logger_info, mock_logger_debug):
        # 测试当tx_data_df中有scope#dp和rid时，parse方法正确处理数据
        result = PluginProcessName.parse(self.data)

        # 验证pid_label_map是否正确生成
        expected_pid_label_map = {
            100: {'hostname': 'host1'},
            200: {'hostname': 'host2'},
            300: {'hostname': 'host3'}
        }
        self.assertEqual(result['pid_label_map'], expected_pid_label_map)


    @patch.object(logger, 'debug')
    @patch.object(logger, 'info')
    def test_parse_pid_label_map_with_missing_dp(self, mock_logger_info, mock_logger_debug):
        # 测试当rid_dp_dict中缺少dp时，pid_label_map是否正确生成
        modified_data = self.data.copy()
        modified_data["tx_data_df"].loc[1, 'scope#dp'] = None

        result = PluginProcessName.parse(modified_data)


if __name__ == '__main__':
    unittest.main()