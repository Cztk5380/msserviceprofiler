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
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from msguard import GlobalConfig
from msguard.security import sanitize_csv_value
from ms_serviceparam_optimizer.config.config import (
    PerformanceIndex,
    OptimizerConfigField,
    get_settings
)
from ms_serviceparam_optimizer.optimizer.plugins.benchmark import VllmBenchMark
from ms_serviceparam_optimizer.optimizer.store import DataStorage



class TestDataStorage(unittest.TestCase):
    def setUp(self):
        self.data_storage = DataStorage(get_settings().data_storage, MagicMock(), MagicMock())

    @patch('ms_serviceparam_optimizer.optimizer.store.Path')
    @patch('ms_serviceparam_optimizer.optimizer.store.csv')
    @patch('msguard.security.sanitize_csv_value')
    def test_save_existing_file(self, mock_sanitize_csv_value, mock_csv, mock_path):
        # 设置模拟对象的行为
        mock_path.exists.return_value = True
        mock_file = MagicMock()
        mock_file.__enter__.return_value = mock_file
        mock_path.open.return_value = mock_file

        # 创建DataStorage实例
        config = MagicMock()
        config.store_dir = Path('/tmp/fake/dir')
        storage = DataStorage(config)

        # 创建测试数据
        performance_index = PerformanceIndex()
        params = [OptimizerConfigField(name='param1', value=1), OptimizerConfigField(name='param2', value=2)]
        kwargs = {'key1': 'value1', 'key2': 'value2'}

        # 调用save方法
        storage.save(performance_index, params, **kwargs)

    @patch('ms_serviceparam_optimizer.optimizer.store.Path')
    def test_load_history_position_dir_not_exist(self, mock_path):
        mock_path.exists.return_value = False
        with self.assertRaises(FileNotFoundError):
            DataStorage.load_history_position(mock_path)

    @patch('ms_serviceparam_optimizer.optimizer.store.Path')
    def test_load_history_position_not_a_dir(self, mock_path):
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = False
        with self.assertRaises(ValueError):
            DataStorage.load_history_position(mock_path)

    @patch('ms_serviceparam_optimizer.optimizer.store.Path')
    @patch('ms_serviceparam_optimizer.optimizer.store.read_csv_s')
    def test_load_history_position_no_data(self, mock_read_csv_s, mock_path):
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = True
        mock_path.iterdir.return_value = []
        result = DataStorage.load_history_position(mock_path)
        self.assertIsNone(result)

    @patch('ms_serviceparam_optimizer.optimizer.store.Path')
    @patch('ms_serviceparam_optimizer.optimizer.store.read_csv_s')
    def test_load_history_position_with_data(self, mock_read_csv_s, mock_path):
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = True
        mock_file = MagicMock()
        mock_file.name.startswith.return_value = True
        mock_file.suffix = '.csv'
        mock_path.iterdir.return_value = [mock_file]
        mock_read_csv_s.return_value.to_dict.return_value = [{'data': 'value'}]

        result = DataStorage.load_history_position(mock_path)
        self.assertEqual(result, [{'data': 'value'}])

    def test_filter_data_no_filter_field(self):
        datas = [{'data': 'value'}, {'data': 'value2'}]
        result = DataStorage.filter_data(datas)
        self.assertEqual(result, datas)

    def test_filter_data_with_filter_field(self):
        datas = [
            {'data': 'value', 'filter': 'field1'},
            {'data': 'value2', 'filter': 'field2'},
            {'data': 'value3', 'filter': 'field1'}
        ]
        filter_field = {'filter': 'field1'}
        result = DataStorage.filter_data(datas, filter_field)
        self.assertEqual(result, [
            {'data': 'value', 'filter': 'field1'},
            {'data': 'value3', 'filter': 'field1'}
        ])

    def test_filter_data_with_non_matching_filter_field(self):
        datas = [
            {'data': 'value', 'filter': 'field1'},
            {'data': 'value2', 'filter': 'field2'},
            {'data': 'value3', 'filter': 'field1'}
        ]
        filter_field = {'filter': 'field3'}
        result = DataStorage.filter_data(datas, filter_field)
        self.assertEqual(result, [])
