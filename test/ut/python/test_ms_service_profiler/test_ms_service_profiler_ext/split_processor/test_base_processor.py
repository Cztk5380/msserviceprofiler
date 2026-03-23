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
import pandas as pd
from ms_service_profiler.processor.split_base_processor import (
    BaseFrameworkProcessor
)


class TestBatchSizeRecommend(unittest.TestCase):
    def setUp(self):
        self.framework_df = pd.DataFrame({
            "name": ["batch_start", "batch_end", "batch_start", "batch_end"],
            "batch_type": ["type1", "type1", "type2", "type2"],
            "batch_size": [32, 64, 1, 128]
        })
        self.instance = BaseFrameworkProcessor()  # 替换为实际的类实例

    @patch('ms_service_profiler.processor.split_base_processor.logger')
    def test_no_matching_rows(self, mock_logger):
        result = self.instance._get_batch_size_recommend(self.framework_df, "nonexistent_type")
        self.assertEqual(result, [-1])
        mock_logger.warning.assert_not_called()

    def test_non_empty_batch_size(self):
        result = self.instance._get_batch_size_recommend(self.framework_df, "type1")
        self.assertEqual(result, [32])

    @patch('ms_service_profiler.processor.split_base_processor.logger')
    def test_preprocess_framework_df_key_error(self, mock_logger):
        # 测试KeyError的情况
        df = pd.DataFrame({
            "name": ["Framework1", "Framework2"],
            "during_time": ["1.0", "2.0"],
            'pid': [1, 1]
        })
        missing_columns = ['tid', 'start_time', 'end_time', 'rid', 'start_datetime', 
                            'end_datetime', 'batch_type', 'batch_size', 'rid_list', 'token_id_list']
        result = self.instance.preprocess_framework_df(df)
        mock_logger.warning.assert_called_once_with(f"Field '{missing_columns} not in index' not found in datasource.")
        self.assertTrue(result.empty)