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
from ms_service_profiler.ms_service_profiler_ext.common.split_utils import (
    get_statistics_data, get_service_type,
    PREFILL_NAME, DECODE_NAME
)
from ms_service_profiler.ms_service_profiler_ext.split_processor import (
    VllmProcessor,
    MindIEProcessor,
    MindIEProcessorV2
)
from ms_service_profiler.ms_service_profiler_ext.common.constants import US_PER_MS


# 测试用例
class TestGetStatisticsData(unittest.TestCase):
    def setUp(self):
        self.framework_df = pd.DataFrame({
            "name": ["Prefill", "Decode", "Prefill", "Decode"],
            "during_time(ms)": [1000, 2000, 3000, 4000],
            "start_time(ms)": [1000, 2000, 3000, 4000],
            "end_time(ms)": [2000, 3000, 4000, 5000],
            "pid": [1, 2, 3, 4],
            "tid": [1, 2, 3, 4],
            "rid": [1, 2, 3, 4],
            "start_datetime": ["2025-01-01 00:00:00", "2025-01-01 00:00:01", 
                               "2025-01-01 00:00:02", "2025-01-01 00:00:03"],
            "end_datetime": ["2025-01-01 00:00:01", "2025-01-01 00:00:02", 
                             "2025-01-01 00:00:03", "2025-01-01 00:00:04"],
            "batch_type": ["batch", "batch", "batch", "batch"],
            "batch_size": [1, 2, 3, 4],
            "rid_list": [[1], [2], [3], [4]],
            "token_id_list": [[1], [2], [3], [4]]
        })

    def test_empty_dataframe(self):
        empty_df = pd.DataFrame()
        result = get_statistics_data(empty_df, "Prefill", PREFILL_NAME)
        self.assertTrue(result.empty)

    def test_filter_name_not_found(self):
        result = get_statistics_data(self.framework_df, "NonExistent", PREFILL_NAME)
        self.assertEqual(len(result), len(self.framework_df))

    def test_single_filter_index(self):
        result = get_statistics_data(self.framework_df, "Prefill", PREFILL_NAME)
        self.assertEqual(len(result), 1)

    def test_column_limit_decode_name(self):
        result = get_statistics_data(self.framework_df, "Decode", DECODE_NAME)
        self.assertEqual(len(result.columns), 10)

    def test_column_limit_prefill_name(self):
        result = get_statistics_data(self.framework_df, "Prefill", PREFILL_NAME)
        self.assertEqual(len(result.columns), 11)


class TestServiceType(unittest.TestCase):
    def test_get_service_type_with_deserialize(self):
        """测试包含deserializeExecuteResponse的情况"""
        data = {
            "name": ["deserializeExecuteResponse", "other_function"]
        }
        framework_df = pd.DataFrame(data)
        result = get_service_type(framework_df)
        self.assertIsInstance(result, MindIEProcessor)

    def test_get_service_type_with_serialize_requests(self):
        """测试包含SerializeRequests但不包含deserializeExecuteResponse的情况"""
        data = {
            "name": ["SerializeRequests", "other_function"]
        }
        framework_df = pd.DataFrame(data)
        result = get_service_type(framework_df)
        self.assertIsInstance(result, MindIEProcessorV2)

    def test_get_service_type_with_neither(self):
        """测试既不包含deserializeExecuteResponse也不包含SerializeRequests的情况"""
        data = {
            "name": ["some_function", "other_function"]
        }
        framework_df = pd.DataFrame(data)
        result = get_service_type(framework_df)
        self.assertIsInstance(result, VllmProcessor)
