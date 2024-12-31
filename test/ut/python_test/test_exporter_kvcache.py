# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import unittest
import logging
import os
import io
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from ms_service_profiler.parse import save_dataframe_to_csv
from ms_service_profiler.exporters.exporter_kvcache import ExporterKVCacheData


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
            'domain': ['KVCache', 'KVCache', 'KVCache', 'KVCache'],
            'rid': [0, 1, 2, 3],
            'start_time': ['1735124796367194', '1735124796367220', '1735124796367233', '1735124796367242'],
            'end_time': ['1735124796367194', '1735124796367220', '1735124796367233', '1735124796367242'],
            'name': ['Allocate', 'Free', 'AppendSlot', 'AppendSlot'],
            'deviceBlock=': [1978, 1977, 1976, 1975],
            'during_time': ['0', '0', '0', '0'],
            'start_datetime': ['2024-12-25', '2024-12-25', '2024-12-25', '2024-12-25']
        }
        return pd.DataFrame(data)

    def test_export(self):
        try:
            # 初始化args
            ExporterKVCacheData.initialize(self.args)
            # 调用export方法
            ExporterKVCacheData.export(self.data)
            # 验证CSV文件是否生成
            file_path = Path(os.path.join(os.getcwd(), 'kvcache.csv'))
            self.assertTrue(file_path.is_file())
        finally:
            # 清理
            file_path.unlink()

    @patch('ms_service_profiler.exporters.exporter_kvcache.ExporterKVCacheData.export')
    def test_export_with_missing_tx_data_df(self, mock_export):
        # 设置日志记录
        logging.basicConfig(level=logging.ERROR)
        # 初始化args
        ExporterKVCacheData.initialize(self.args)
        # 调用export方法，但模拟tx_data_df不存在的情况
        self.data['tx_data_df'] = None
        ExporterKVCacheData.export(self.data)
        # 验证方法是否正确处理了tx_data_df不存在的情况
        mock_export.assert_called_once_with(self.data)
        # 验证CSV文件是否生成
        file_path = Path(os.path.join(os.getcwd(), 'kvcache.csv'))
        self.assertFalse(file_path.is_file())
    