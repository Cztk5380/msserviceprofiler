# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import unittest
import logging
import os
import io
from pathlib import Path
import shutil
from unittest import mock
from unittest.mock import patch
import pandas as pd
from ms_service_profiler.exporters.utils import save_dataframe_to_csv, create_sqlite_db
from ms_service_profiler.exporters.exporter_batch import ExporterBatchData


class TestExporterBatchData(unittest.TestCase):
    def setUp(self):
        test_path = os.path.join(os.getcwd(), "output_test")
        self.args = type('Args', (object,), {'output_path': test_path, 'format': ['csv', 'db']})
        self.data = {
            'tx_data_df': self.create_df()
        }

    def create_df(self):
        # 创建一个示例DataFrame
        data = {
            'name': ['BatchSchedule', 'modelExec', 'dpBatch', 'forward', 'forward',\
                'BatchSchedule', 'modelExec', 'dpBatch', 'forward', 'forward'],
            'domain': ['BatchSchedule', 'ModelExecute', 'ModelExecute', 'ModelExecute', 'ModelExecute', \
                'BatchSchedule', 'ModelExecute', 'ModelExecute', 'ModelExecute', 'ModelExecute'],
            'message': [
                {'rid': [{'rid': 11, 'iter': 0}, {'rid': 12, 'iter': 0}], 'data': 'data1'},
                {'rid': [{'rid': 11, 'iter': 0}, {'rid': 12, 'iter': 0}], 'data': 'data2'},
                {'rid': [11, 12], 'data': 'data1'},
                {'rid': [0], 'data': 'data1'},
                {'rid': [1], 'data': 'data2'},

                {'rid': [{'rid': 13, 'iter': 1}, {'rid': 14, 'iter': 1}], 'data': 'data3'},
                {'rid': [{'rid': 13, 'iter': 1}, {'rid': 14, 'iter': 1}], 'data': 'data4'},
                {'rid': [13, 14], 'data': 'data1'},
                {'rid': [0], 'data': 'data1'},
                {'rid': [1], 'data': 'data2'}
            ],
            'start_time': [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000],
            'end_time': [1500, 2500, 3500, 4500, 5500, 6500, 7500, 8500, 9500, 10500],
            'batch_size':[2, 2, 2, 1, 1, 2, 2, 2, 1, 1],
            'batch_type':['Prefill', 'Prefill', 'Prefill', 'Prefill', 'Prefill',
                'Decode', 'Decode', 'Decode', 'Decode', 'Decode'],
            'res_list':[
                {'rid': [{'rid': 11, 'iter': 0}, {'rid': 12, 'iter': 0}]},
                {'rid': [{'rid': 11, 'iter': 0}, {'rid': 12, 'iter': 0}]},
                {'rid': [11, 12]},
                {'rid': [0]},
                {'rid': [1]},

                {'rid': [{'rid': 13, 'iter': 1}, {'rid': 14, 'iter': 1}]},
                {'rid': [{'rid': 13, 'iter': 1}, {'rid': 14, 'iter': 1}]},
                {'rid': [13, 14]},
                {'rid': [0]},
                {'rid': [1]}
            ],
            'during_time': [500, 500, 500, 500, 500, 500, 500, 500, 500, 500],
            'pid': [0, 0, 1, 1, 2, 0, 0, 1, 1, 2],
            'rid_list': [[11, 12], [11, 12], [11, 12], [11, 12], [11, 12],
                [13, 14], [13, 14], [13, 14], [13, 14], [13, 14]],
            'dp_list': [[], [], [0, 1], [], [], [], [], [0, 1], [], []],
            'rid': ['11, 12', '11, 12', '11, 12', '', '',
                '13, 14', '13, 14', '13, 14', '', ''],
            'dp_rank': ['', '', '', '0', '1', '', '', '', '0', '1']
        }
        return pd.DataFrame(data)

    def check_dp_info(self, csv_file_path):
        df = pd.read_csv(csv_file_path)
        dp_columns = ['during_time', 'dp0_rid', 'dp0_size', 'dp0_forward',
            'dp1_rid', 'dp1_size', 'dp1_forward']

        # 校验是否存在上述列
        col_index = []
        for col_name in dp_columns:
            col_index.append(df.columns.get_loc(col_name))
            self.assertIn(col_name, df.columns)

        # 校验上述列是否按顺序排列
        self.assertEqual(col_index, sorted(col_index))

    def test_export(self):
        try:
            # 设置模拟方法返回安全父目录
            test_path = os.path.join(os.getcwd(), "output_test")
            
            # 创建目录
            os.makedirs(test_path, exist_ok=True)
            
            # 设置权限为640
            os.chmod(test_path, 0o740)
            
            # 设置日志记录
            file_path = Path(test_path, 'batch.csv')
            logging.basicConfig(level=logging.ERROR)
            # 初始化args
            ExporterBatchData.initialize(self.args)
            create_sqlite_db(test_path)
            # 调用export方法
            ExporterBatchData.export(self.data)
            # 验证CSV文件是否生成
            self.assertTrue(file_path.is_file())

            # 验证dp域信息是否正确
            self.check_dp_info(file_path)
        finally:
            # 清理
            shutil.rmtree(test_path)

    @patch('ms_service_profiler.exporters.exporter_batch.ExporterBatchData.export')
    def test_export_with_missing_tx_data_df(self, mock_export):
        # 设置日志记录
        try:
            logging.basicConfig(level=logging.ERROR)
            test_path = os.path.join(os.getcwd(), "output_test")
                
            # 创建目录
            os.makedirs(test_path, exist_ok=True)
                
            # 设置权限为640
            os.chmod(test_path, 0o740)
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
        finally:
            # 清理
            shutil.rmtree(test_path)
    
