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
import os
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from ms_service_profiler.parse import parse
from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.exporters.exporter_request import process_data, update_name, ExporterAnalyzeData


class TestProcessData(unittest.TestCase):

    def setUp(self):
        # 创建测试数据
        self.req_en_queue_df = pd.DataFrame({
            'rid': [1, 1],
            'start_time': [10, 15],
            'end_time': [10, 15]
        })

        self.req_running_df = pd.DataFrame({
            'rid': [1, 1, 1],
            'start_time': [13, 20, 26],
            'end_time': [13, 20, 26]
        })

        self.pending_df = pd.DataFrame({
            'rid': [1, 1],
            'start_time': [16, 22],
            'end_time': [16, 22]
        })

        self.test_data = pd.DataFrame({
            'RUNNING+': [1, 0, 0],
            'PENDING+': [0, 1, 0],
            'name': ['reqstate', 'PENDING', 'reqstate']
        })
        self.expected_results = pd.DataFrame({
            'RUNNING+': [1, 0, 0],
            'PENDING+': [0, 1, 0],
            'name': ['RUNNING', 'PENDING', 'reqstate']
        })

    def test_process_data_inconsistent_rows(self):
        # 测试当pending_df和req_running_df的行数不一致时
        self.req_running_df = self.req_running_df.iloc[:2]
        result = process_data(self.req_en_queue_df, self.req_running_df, self.pending_df)
        self.assertIsNone(result)


    def test_process_data_equal_rows(self):
        # 测试当req_en_queue_df和req_running_df的行数一致时
        result = process_data(self.req_en_queue_df, self.req_running_df, self.pending_df)
        expected = pd.DataFrame({
            'rid': [1],
            'queue_wait_time': [11]
        })
        pd.testing.assert_frame_equal(result, expected)

    def test_update_name(self):
        # 应用函数
        result = update_name(self.test_data.iloc[0])
        self.assertEqual(result['name'], self.expected_results.iloc[0]['name'])

        result = update_name(self.test_data.iloc[1])
        self.assertEqual(result['name'], self.expected_results.iloc[1]['name'])

        result = update_name(self.test_data.iloc[2])
        self.assertEqual(result['name'], self.expected_results.iloc[2]['name'])


class TestExporterAnalyzeData(unittest.TestCase):
    def setUp(self):
        current_dir = os.getcwd()
        self.args = type('Args', (object,), {'output_path': current_dir})
        self.data = {
            'tx_data_df': self.create_df()
        }

    def create_df(self):
        # 创建一个示例DataFrame
        data = {
            'name': ['httpReq', 'encode', 'ReqEnQueue', 'ReqState', 'ReqState', 'ReqState', 'DecodeEnd', 'httpRes'],
            'message': [
                {'domain': 'http', 'rid': 'endpoint_common_1', 'name': 'httpReq', 'type': 0},
                {'domain': 'http', 'rid': 'endpoint_common_1', 'name': 'encode', 'type': 2, '=recvTokenSize': 4},
                {'domain': 'Queue', 'rid': 0, '=QueueSize': 1, 'queue': 20, 'name': 'ReqEnQueue', 'type': 0},
                {'rid': 0, '+WAITING': -1, '+RUNNING': 1, 'name': 'ReqState', 'type': 0},
                {'rid': 0, '+RUNNING': -1, '+PENDING': 1, 'name': 'ReqState', 'type': 0},
                {'rid': 0, '+PENDING': -1, '+RUNNING': 1, 'name': 'ReqState', 'type': 0},
                {'domain': 'http', 'rid': 'endpoint_common_1', '=replyTokenSize': 250, 'name': 'DecodeEnd', 'type': 0},
                {'domain': 'http', 'rid': 'endpoint_common_1', 'action': 'Process', 'name': 'httpRes', 'type': 0}
            ],
            'start_time': [1, 2, 3, 4, 5, 6, 7, 8],
            'end_time': [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5],
            'rid':[1, 1, 1, 1, 1, 1, 1, 1],
            'recvTokenSize=':['', 4, '', '', '', '', '', ''],
            'replyTokenSize=':['', '', '', '', '', '', 250, ''],
            'RUNNING+':['', '', '', 1, '', 1, '', ''],
            'PENDING+':['', '', '', '', 1, '', '', ''],
            'during_time':[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        }

        return pd.DataFrame(data)

    def test_export(self):
        # 初始化args
        ExporterAnalyzeData.initialize(self.args)
        # 调用export方法
        ExporterAnalyzeData.export(self.data)
        # 验证CSV文件是否生成
        file_path = Path(os.path.join(os.getcwd(), 'request.csv'))
        self.assertTrue(file_path.is_file())
        # 清理
        file_path.unlink()

    @patch('ms_service_profiler.exporters.exporter_request.ExporterAnalyzeData.export')
    def test_export_with_missing_tx_data_df(self, mock_export):
        # 初始化args
        ExporterAnalyzeData.initialize(self.args)
        # 调用export方法，但模拟tx_data_df不存在的情况
        self.data['tx_data_df'] = None
        ExporterAnalyzeData.export(self.data)
        # 验证方法是否正确处理了tx_data_df不存在的情况
        mock_export.assert_called_once_with(self.data)
        # 验证CSV文件是否生成
        file_path = Path(os.path.join(os.getcwd(), 'request.csv'))
        self.assertFalse(file_path.is_file())


if __name__ == '__main__':
    unittest.main()