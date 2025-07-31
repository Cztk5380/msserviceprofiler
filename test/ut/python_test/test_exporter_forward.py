# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import shutil
import pandas as pd
from ms_service_profiler.exporters.utils import create_sqlite_db
from ms_service_profiler.exporters.exporter_forward import (
    ExporterForwardData,
    calculate_relative_times,
    calculate_bubble_time,
    get_batch_name,
    get_filter_forward_df,
    get_batch_info,
    get_relative_and_bubble,
    REQUIED_NAME
)


class TestExporterForwardData(unittest.TestCase):
    def setUp(self):
        self.data = {
            'tx_data_df': self.create_df()
        }

    def create_df(self):
        # 创建一个示例DataFrame
        data = {
            'name': ['BatchSchedule', 'modelExec', 'dpBatch', 'forward', 'forward', \
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
            'batch_size': [2, 2, 2, 1, 1, 2, 2, 2, 1, 1],
            'batch_type': ['Prefill', 'Prefill', 'Prefill', None, None,
                'Decode', '', 'Decode', '', ''],
            'res_list': [
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
            'rid': ['11, 12', '11, 12', '11, 12', '11, 12', '11, 12',
                '13, 14', '13, 14', '13, 14', '13, 14', '13, 14'],
            'dp_rank': ['', '', '', '0', '1', '', '', '', '0', '1'],
            'hostname': ['host1', '', '', 'host1', 'host1', 'host1', '', '', 'host1', 'host1'],
            'prof_id': ['prof1', '', '', 'prof1', 'prof1', 'prof1', '', '', 'prof1', 'prof1']
        }
        return pd.DataFrame(data)

    @patch('ms_service_profiler.exporters.exporter_forward.get_batch_name')
    @patch('ms_service_profiler.exporters.exporter_forward.logger')
    def test_export_incomplete_data(self, mock_logger, mock_get_batch_name):
        # 测试数据不完整的情况
        mock_get_batch_name.return_value = 'BatchSchedule'
        df = pd.DataFrame({
            'name': ['forward'],
            'domain': 'ModelExecute'
        })
        ExporterForwardData.args = MagicMock(format=['csv'])
        ExporterForwardData.export({'tx_data_df': df})
        mock_logger.warning.assert_called_once_with(f"The data is not complete, please check. \
                            The required data for forward.csv is {REQUIED_NAME}")

    def test_export(self):
        try:
            # 设置模拟方法返回安全父目录
            ExporterForwardData.args = MagicMock(output_path='output_test', format=['csv', 'db'])
            test_path = os.path.join(os.getcwd(), 'output_test')
            # 创建目录
            os.makedirs(test_path, exist_ok=True, mode=0o750)
            
            # 设置日志记录
            file_path = Path(test_path, 'forward.csv')
            # 调用export方法
            create_sqlite_db(test_path)
            ExporterForwardData.initialize(ExporterForwardData.args)
            ExporterForwardData.export(self.data)
            # 验证CSV文件是否生成
            self.assertTrue(file_path.is_file())
        finally:
            # 清理
            shutil.rmtree(test_path)

    @patch('ms_service_profiler.exporters.exporter_forward.logger')
    def test_export_empty_data(self, mock_logger):
        # 测试数据为空的情况
        ExporterForwardData.args = MagicMock(format=['csv'])
        ExporterForwardData.export({})
        mock_logger.warning.assert_called_once_with("The data is empty, please check")


class TestForwardDataUtils(unittest.TestCase):
    def test_calculate_relative_times(self):
        # 测试计算相对时间
        df = pd.DataFrame({
            'start_time': [100, 200, 300],
            'end_time': [150, 250, 350]
        })
        result_df = calculate_relative_times(df)
        self.assertEqual(result_df['relative_start_time'].tolist(), [0.0, 100.0, 200.0])

    def test_calculate_bubble_time(self):
        # 测试计算 bubble_time
        df = pd.DataFrame({
            'start_time': [100, 200, 300],
            'end_time': [150, 250, 350],
            'prof_id': [1, 1, 1]
        })
        result_df = calculate_bubble_time(df)
        result_df = result_df.fillna(0)
        self.assertEqual(result_df['bubble_time'].tolist(), [50.0, 50.0, 0.0])

    def test_get_batch_name(self):
        # 测试获取 batch_name
        df = pd.DataFrame({
            'name': ['BatchSchedule', 'forward']
        })
        self.assertEqual(get_batch_name(df), 'BatchSchedule')

    def test_get_filter_forward_df(self):
        # 测试过滤 forward 数据
        df = pd.DataFrame({
            'name': ['forward', 'BatchSchedule'],
            'start_time': [100, 200],
            'end_time': [150, 250],
            'during_time': [50, 50],
            'rid': [1, 1]
        })
        result_df = get_filter_forward_df(['forward', 'BatchSchedule'], df)
        self.assertEqual(result_df['name'].tolist(), ['forward', 'BatchSchedule'])
        self.assertEqual(result_df['start_time'].tolist(), [0.1, 0.2])

    @patch('ms_service_profiler.exporters.exporter_forward.get_batch_name')
    def test_get_batch_info(self, mock_get_batch_name):
        # 测试获取 batch_info
        mock_get_batch_name.return_value = 'BatchSchedule'
        df = pd.DataFrame({
            'name': ['BatchSchedule', 'forward'],
            'start_time': [100, 200],
            'rid': [1, 1],
            'batch_type': ['type1', None],
            'batch_size': [10, None]
        })
        result_df = get_batch_info(df, 'BatchSchedule')
        self.assertEqual(result_df['batch_type'].tolist(), ['type1'])

    def test_get_relative_and_bubble(self):
        # 测试获取相对时间和 bubble_time
        df = pd.DataFrame({
            'start_time': [100, 200, 300],
            'end_time': [150, 250, 350],
            'hostname': ['host1', 'host1', 'host2'],
            'prof_id': [1, 1, 2],
            'pid': [1, 1, 2]
        })
        result_df = get_relative_and_bubble(df)
        result_df = result_df.fillna(0)
        self.assertEqual(result_df['relative_start_time'].tolist(), [0.0, 100.0, 0.0])
        self.assertEqual(result_df['bubble_time'].tolist(), [50.0, 0, 0])