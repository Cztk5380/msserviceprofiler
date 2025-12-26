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
from unittest.mock import patch, MagicMock, call
import pandas as pd
import numpy as np
from modelevalstate.data_feature.dataset import MyDataSet
from modelevalstate.inference.constant import OpAlgorithm
from modelevalstate.inference.data_format_v1 import (
    MODEL_OP_FIELD,
    MODEL_STRUCT_FIELD,
    MODEL_CONFIG_FIELD,
    MINDIE_FIELD,
    ENV_FIELD,
    HARDWARE_FIELD,
)
from modelevalstate.inference.dataset import TOTAL_OUTPUT_LENGTH, \
    TOTAL_SEQ_LENGTH, TOTAL_PREFILL_TOKEN
from modelevalstate.data_feature.dataset_with_swifter import MyDataSetWithSwifter  


class TestMyDataSetWithSwifter(unittest.TestCase):
    def setUp(self):
        # 创建测试数据
        self.sample_data = pd.DataFrame({
            "batch_field": ["[[1,2],[3,4]]"] * 3,
            "request_field": ["[[5,6],[7,8]]"] * 3,
            "op_field": ["[[9,10]]"] * 3,
            "model_execute_time": [0.1, 0.2, 0.3]
        })
        self.dataset = MyDataSetWithSwifter()

    @patch('modelevalstate.data_feature.dataset_with_swifter.logger.debug')
    @patch('modelevalstate.data_feature.dataset_with_swifter.MyDataSetWithSwifter.'\
           'proprocess_with_swifter')
    def test_preprocess_dispatch_success(self, mock_process, mock_logger):
        """测试swifter预处理成功路径"""
        expected_features = pd.DataFrame({'feat': [1, 2, 3]})
        expected_labels = pd.DataFrame({'label': [0.1, 0.2, 0.3]})
        mock_process.return_value = (expected_features, expected_labels)
        
        # 调用测试方法
        result = self.dataset.preprocess_dispatch(self.sample_data)
        
        # 验证行为
        mock_logger.assert_called_with(f"start construct_data with swifter, shape {self.sample_data.shape}")
        mock_process.assert_called_once_with(self.sample_data)
        self.assertEqual(result, (expected_features, expected_labels))

    @patch('modelevalstate.data_feature.dataset_with_swifter.logger.error')
    @patch('modelevalstate.data_feature.dataset_with_swifter.MyDataSetWithSwifter.'\
        'proprocess_with_swifter')
    @patch('modelevalstate.data_feature.dataset_with_swifter.MyDataSet.preprocess_dispatch')
    def test_preprocess_dispatch_fallback(self, mock_parent, mock_process, mock_logger):
        """测试swifter失败时回退到父类实现"""
        # 模拟swifter处理失败
        mock_process.side_effect = Exception("Mocked swifter error")
        expected_fallback = (pd.DataFrame(), pd.DataFrame())
        mock_parent.return_value = expected_fallback
        
        # 调用测试方法
        result = self.dataset.preprocess_dispatch(self.sample_data)
        
        # 验证行为
        mock_process.assert_called_once_with(self.sample_data)
        mock_logger.assert_called_with("Failed in construct data with swifter. error: Mocked swifter error")
        mock_parent.assert_called_once_with(self.sample_data)
        self.assertEqual(result, expected_fallback)

    @patch('modelevalstate.data_feature.dataset_with_swifter.logger.info')
    @patch('modelevalstate.data_feature.dataset_with_swifter.MyDataSetWithSwifter.'\
           'proprocess_with_swifter')
    def test_preprocess_dispatch_none_input(self, mock_process, mock_logger):
        """测试None输入直接回退父类"""
        mock_parent_return = MagicMock()
        with patch.object(MyDataSetWithSwifter, 'preprocess_dispatch', 
                         side_effect=[mock_parent_return]) as mock_parent:
            result = self.dataset.preprocess_dispatch(None)
            mock_parent.assert_called_once_with(None)
            self.assertEqual(result, mock_parent_return)
            mock_process.assert_not_called()

    def test_less_than_two_columns(self):
        lines_data = pd.DataFrame({'col1': ['1', '2', '3']})
        result = self.dataset.proprocess_with_swifter(lines_data)
        self.assertEqual(result, (None, None))