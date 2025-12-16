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
from unittest.mock import patch
from unittest.mock import ANY

import pandas as pd
import numpy as np

from ms_service_profiler.plugins.plugin_moe import (
    PluginMoeSlowRankProcess,
    MOE_DISTRIBUTED_COMBINE,
    MOE_DISTRIBUTED_DISPATCH
)


class TestPluginMoeSlowRankProcess(unittest.TestCase):

    @patch('ms_service_profiler.utils.log.logger.warning')
    def test_parse_no_communication_df(self, mock_logger):
        data = {}
        result = PluginMoeSlowRankProcess.parse(data)
        mock_logger.assert_called_once_with(ANY)
        self.assertEqual(result, data)

    @patch('ms_service_profiler.utils.log.logger.warning')
    def test_parse_empty_communication_df(self, mock_logger):
        data = {"communication_df": pd.DataFrame()}
        result = PluginMoeSlowRankProcess.parse(data)
        mock_logger.assert_called_once_with(ANY)
        self.assertEqual(result, data)

    @patch('ms_service_profiler.utils.log.logger.warning')
    def test_parse_no_relevant_rows(self, mock_logger):
        communication_df = pd.DataFrame({
            "name": ["other_name"],
            "db_id": [1],
            "start": [10],
            "end": [11]
        })
        data = {"communication_df": communication_df}
        result = PluginMoeSlowRankProcess.parse(data)
        mock_logger.assert_called_once_with(ANY)
        self.assertEqual(result, data)

    def test_parse_valid_data(self):
        communication_df = pd.DataFrame({
            "name": [MOE_DISTRIBUTED_COMBINE, MOE_DISTRIBUTED_COMBINE, MOE_DISTRIBUTED_DISPATCH],
            "db_id": [1, 1, 2],
            "start": [10, 20, 30],
            "end": [11, 21, 41]
        })
        data = {"communication_df": communication_df}
        result = PluginMoeSlowRankProcess.parse(data)
        self.assertIn("moe_analysis", result)
        moe_analysis = result["moe_analysis"]
        self.assertEqual(len(moe_analysis), 2)
        self.assertEqual(moe_analysis.columns.tolist(), ["Dataset", "Mean", "CI_Lower", "CI_Upper"])

    def test_parse_single_row(self):
        communication_df = pd.DataFrame({
            "name": [MOE_DISTRIBUTED_COMBINE],
            "db_id": [1],
            "start": [10],
            "end": [11]
        })
        data = {"communication_df": communication_df}
        result = PluginMoeSlowRankProcess.parse(data)
        self.assertIn("moe_analysis", result)
        moe_analysis = result["moe_analysis"]
        self.assertEqual(len(moe_analysis), 1)
        self.assertEqual(moe_analysis.columns.tolist(), ["Dataset", "Mean", "CI_Lower", "CI_Upper"])

    def test_parse_large_dataset(self):
        np.random.seed(0)
        communication_df = pd.DataFrame({
            "name": [MOE_DISTRIBUTED_COMBINE] * 1000,
            "db_id": np.random.randint(1, 10, size=1000),
            "start": np.random.rand(1000),
            "end": np.random.rand(1000)
        })
        data = {"communication_df": communication_df}
        result = PluginMoeSlowRankProcess.parse(data)
        self.assertIn("moe_analysis", result)
        moe_analysis = result["moe_analysis"]
        self.assertGreater(len(moe_analysis), 1)
        self.assertEqual(moe_analysis.columns.tolist(), ["Dataset", "Mean", "CI_Lower", "CI_Upper"])
