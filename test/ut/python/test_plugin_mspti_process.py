# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import unittest
from unittest.mock import patch

import pandas as pd

from ms_service_profiler.plugins.plugin_mspit_process import PluginMsptiProcess, replace_name


class TestPluginMsptiProcess(unittest.TestCase):

    @patch('ms_service_profiler.utils.log.logger.warning')
    def test_parse_no_data(self, mock_logger):
        data = []
        result = PluginMsptiProcess.parse(data)
        mock_logger.assert_called_once_with("No data found in all ascend_service_profiler_*.db, skipping parse.")
        self.assertIsNone(result)

    @patch('ms_service_profiler.utils.log.logger.warning')
    def test_parse_single_empty_api_df(self, mock_logger):
        data = [{
            "api_df": pd.DataFrame(),
            "kernel_df": pd.DataFrame({"correlationId": [1], "name": ["name1"]}),
            "communication_df": pd.DataFrame()
        }]
        result = PluginMsptiProcess.parse(data)
        expected_logs = [
            "No api data or kernel data detected in certain db, skipping process.",
            "No data found in all ascend_service_profiler_*.db, skipping parse."
        ]
        actual_logs = [call[0][0] for call in mock_logger.call_args_list]
        self.assertEqual(actual_logs, expected_logs)
        self.assertIsNone(result)

    @patch('ms_service_profiler.utils.log.logger.warning')
    def test_parse_single_empty_kernel_df(self, mock_logger):
        data = [{
            "api_df": pd.DataFrame({"correlationId": [1], "name": ["name1"]}),
            "kernel_df": pd.DataFrame(),
            "communication_df": pd.DataFrame()}]
        result = PluginMsptiProcess.parse(data)
        expected_logs = [
            "No api data or kernel data detected in certain db, skipping process.",
            "No data found in all ascend_service_profiler_*.db, skipping parse."
        ]
        actual_logs = [call[0][0] for call in mock_logger.call_args_list]
        self.assertEqual(actual_logs, expected_logs)
        self.assertIsNone(result)

    @patch('ms_service_profiler.utils.log.logger.warning')
    def test_parse_multiple_empty_api_df(self, mock_logger):
        data = [
            {
                "api_df": pd.DataFrame(),
                "kernel_df": pd.DataFrame({"correlationId": [1], "name": ["name1"]}),
                "communication_df": pd.DataFrame()
            },
            {
                "api_df": pd.DataFrame(),
                "kernel_df": pd.DataFrame({"correlationId": [1], "name": ["name1"]}),
                "communication_df": pd.DataFrame()
            }
        ]
        result = PluginMsptiProcess.parse(data)
        expected_logs = [
                            "No api data or kernel data detected in certain db, skipping process.",
                        ] * len(data) + [
                            "No data found in all ascend_service_profiler_*.db, skipping parse."
                        ]
        actual_logs = [call[0][0] for call in mock_logger.call_args_list]
        self.assertEqual(actual_logs, expected_logs)
        self.assertIsNone(result)

    @patch('ms_service_profiler.utils.log.logger.warning')
    def test_parse_multiple_empty_kernel_df(self, mock_logger):
        data = [
            {
                "api_df": pd.DataFrame({"correlationId": [1], "name": ["name1"]}),
                "kernel_df": pd.DataFrame(),
                "communication_df": pd.DataFrame()
            },
            {
                "api_df": pd.DataFrame({"correlationId": [1], "name": ["name1"]}),
                "kernel_df": pd.DataFrame(),
                "communication_df": pd.DataFrame()
            }
        ]
        result = PluginMsptiProcess.parse(data)
        expected_logs = [
                            "No api data or kernel data detected in certain db, skipping process.",
                        ] * len(data) + [
                            "No data found in all ascend_service_profiler_*.db, skipping parse."
                        ]
        actual_logs = [call[0][0] for call in mock_logger.call_args_list]
        self.assertEqual(actual_logs, expected_logs)
        self.assertIsNone(result)

    def test_parse_valid_data(self):
        api_df = pd.DataFrame({"correlationId": [1, 2], "name": ["api1", "api2"]})
        kernel_df = pd.DataFrame({"correlationId": [1, 2], "name": ["kernel1", "kernel2"]})
        communication_df = pd.DataFrame({"data": ["comm1", "comm2"]})
        data = [{"api_df": api_df, "kernel_df": kernel_df, "communication_df": communication_df}]
        result = PluginMsptiProcess.parse(data)
        self.assertIn("api_df", result)
        self.assertIn("kernel_df", result)
        self.assertIn("communication_df", result)
        self.assertEqual(len(result["api_df"]), 2)
        self.assertEqual(len(result["kernel_df"]), 2)
        self.assertEqual(len(result["communication_df"]), 2)

    def test_parse_multiple_items(self):
        api_df1 = pd.DataFrame({"correlationId": [1], "name": ["api1"]})
        kernel_df1 = pd.DataFrame({"correlationId": [1], "name": ["kernel1"]})
        communication_df1 = pd.DataFrame({"data": ["comm1"]})

        api_df2 = pd.DataFrame({"correlationId": [2], "name": ["api2"]})
        kernel_df2 = pd.DataFrame({"correlationId": [2], "name": ["kernel2"]})
        communication_df2 = pd.DataFrame({"data": ["comm2"]})

        data = [
            {"api_df": api_df1, "kernel_df": kernel_df1, "communication_df": communication_df1},
            {"api_df": api_df2, "kernel_df": kernel_df2, "communication_df": communication_df2}
        ]
        result = PluginMsptiProcess.parse(data)
        self.assertIn("api_df", result)
        self.assertIn("kernel_df", result)
        self.assertIn("communication_df", result)
        self.assertEqual(len(result["api_df"]), 2)
        self.assertEqual(len(result["kernel_df"]), 2)
        self.assertEqual(len(result["communication_df"]), 2)

    def test_replace_name(self):
        df1 = pd.DataFrame({"correlationId": [1, 2], "name": ["old_name1", "old_name2"]})
        df2 = pd.DataFrame({"correlationId": [1, 2], "name": ["new_name1", "new_name2"]})
        result_df = replace_name(df1, df2)
        self.assertEqual(result_df["name"].tolist(), ["new_name1", "new_name2"])
