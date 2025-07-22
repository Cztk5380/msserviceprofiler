# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import unittest
import os
from pathlib import Path
from unittest.mock import patch
import shutil
import pandas as pd
from ms_service_profiler.parse import parse
from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.exporters.exporter_req_data import ExporterReqData


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


class TestExporterReqData(unittest.TestCase):
    def setUp(self):
        test_path = os.path.join(os.getcwd(), "output_test")
        self.args = type('Args', (object,), {'output_path': test_path, 'format': ['csv']})
        self.data = {
            'tx_data_df': self.create_df()
        }

    def create_df(self):
        # 创建一个示例DataFrame
        data = {
            'name': ['httpReq', 'encode', 'Enqueue', 'ReqState', 'ReqState', 'ReqState', 'DecodeEnd', 'httpRes'],
            'message': [
                {'domain': 'Request', 'rid': 0, 'name': 'httpReq', 'type': 0},
                {'domain': 'Request', 'rid': 'endpoint_common_1', 'name': 'encode', 'type': 2, '=recvTokenSize': 4},
                {'domain': 'Request', 'rid': 0, '=QueueSize': 1, 'queue': 20, 'name': 'Enqueue', 'type': 0},
                {'domain': 'Request', 'rid': 0, '+WAITING': -1, '+RUNNING': 1, 'name': 'ReqState', 'type': 0},
                {'domain': 'Request', 'rid': 0, '+RUNNING': -1, '+PENDING': 1, 'name': 'ReqState', 'type': 0},
                {'domain': 'Request', 'rid': 0, '+PENDING': -1, '+RUNNING': 1, 'name': 'ReqState', 'type': 0},
                {'domain': 'Request', 'rid': 'endpoint_common_1',
                 '=replyTokenSize': 250, 'name': 'DecodeEnd', 'type': 0},
                {'domain': 'Request', 'rid': 'endpoint_common_1', 'action': 'Process', 'name': 'httpRes', 'type': 0}
            ],
            'start_time': [1, 2, 3, 4, 5, 6, 7, 8],
            'end_time': [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5],
            'rid':[1, 1, 1, 1, 1, 1, 1, 1],
            'recvTokenSize=':['', 4, '', '', '', '', '', ''],
            'replyTokenSize=':['', '', '', '', '', '', 250, ''],
            'RUNNING+':['', '', '', 1, '', 1, '', ''],
            'PENDING+':['', '', '', '', 1, '', '', ''],
            'during_time':[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            'domain':['Request', 'Request', 'Request', 'Request', 'Request', 'Request', 'Request', 'Request'],
            'rid_list':[1, 1, 1, 1, 1, 1, 1, 1],
            'token_id_list':[0, 0, 0, 0, 0, 0, 0, 0]
        }

        return pd.DataFrame(data)

    def test_export(self):
        try:
            test_path = os.path.join(os.getcwd(), "output_test")
            os.makedirs(test_path, exist_ok=True)
            os.chmod(test_path, 0o740)
            file_path = Path(test_path, 'request.csv')
            # 初始化args
            ExporterReqData.initialize(self.args)
            # 调用export方法
            ExporterReqData.export(self.data)
            # 验证CSV文件是否生成
            
            self.assertTrue(file_path.is_file())
        finally:
            # 清理
            shutil.rmtree(test_path)

    @patch('ms_service_profiler.exporters.exporter_req_data.ExporterReqData.export')
    def test_export_with_missing_tx_data_df(self, mock_export):
        try:
            test_path = os.path.join(os.getcwd(), "output_test")
            os.makedirs(test_path, exist_ok=True)
            os.chmod(test_path, 0o740)
            file_path = Path(test_path, 'request.csv')
            # 初始化args
            ExporterReqData.initialize(self.args)
            # 调用export方法，但模拟tx_data_df不存在的情况
            self.data['tx_data_df'] = None
            ExporterReqData.export(self.data)
            # 验证方法是否正确处理了tx_data_df不存在的情况
            mock_export.assert_called_once_with(self.data)
            self.assertFalse(file_path.is_file())
        finally:
            # 清理
            shutil.rmtree(test_path)


if __name__ == '__main__':
    unittest.main()