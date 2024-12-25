# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
import logging
import os
import io
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from ms_service_profiler.parse import save_dataframe_to_csv
from ms_service_profiler.exporters.exporter_batch import ExporterBatchData


class TestExporterBatchData(unittest.TestCase):
    def setUp(self):
        current_dir = os.getcwd()
        self.args = type('Args', (object,), {'output_path': current_dir})
        self.data = {
            'tx_data_df': self.create_df()
        }

    def create_df(self):
        # 创建一个示例DataFrame
        data = {
            'name': ['BatchSchedule', 'modelExec', 'BatchSchedule', 'modelExec'],
            'message': [
                {'rid': [{'rid': 0, 'iter': 0}], 'data': 'data1'},
                {'rid': [{'rid': 0, 'iter': 0}], 'data': 'data2'},
                {'rid': [{'rid': 0, 'iter': 1}], 'data': 'data3'},
                {'rid': [{'rid': 0, 'iter': 1}], 'data': 'data4'}
            ],
            'start_time': [1, 2, 3, 4],
            'end_time': [1.5, 2.5, 3.5, 4.5],
            'batch_size':[1, 1, 1, 1],
            'batch_type':['Prefill', 'Prefill', 'Decode', 'Decode'],
            'res_list':[
                {'rid': [{'rid': 0, 'iter': 0}]},
                {'rid': [{'rid': 0, 'iter': 0}]},
                {'rid': [{'rid': 0, 'iter': 1}]},
                {'rid': [{'rid': 0, 'iter': 1}]}
            ],
            'during_time':[0.5, 0.5, 0.5, 0.5]
        }
        return pd.DataFrame(data)

    def test_export(self):
        try:
            # 设置日志记录
            logging.basicConfig(level=logging.ERROR)
            # 初始化args
            ExporterBatchData.initialize(self.args)
            # 调用export方法
            ExporterBatchData.export(self.data)
            # 验证CSV文件是否生成
            file_path = Path(os.path.join(os.getcwd(), 'batch.csv'))
            self.assertTrue(file_path.is_file())
        finally:
            # 清理
            file_path.unlink()

    @patch('ms_service_profiler.exporters.exporter_batch.ExporterBatchData.export')
    def test_export_with_missing_tx_data_df(self, mock_export):
        # 设置日志记录
        logging.basicConfig(level=logging.ERROR)
        # 初始化args
        ExporterBatchData.initialize(self.args)
        # 调用export方法，但模拟tx_data_df不存在的情况
        self.data['tx_data_df'] = None
        ExporterBatchData.export(self.data)
        # 验证方法是否正确处理了tx_data_df不存在的情况
        mock_export.assert_called_once_with(self.data)
        # 验证CSV文件是否生成
        file_path = Path(os.path.join(os.getcwd(), 'batch.csv'))
        self.assertFalse(file_path.is_file())
    