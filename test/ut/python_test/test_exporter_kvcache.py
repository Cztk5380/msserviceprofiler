# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import unittest
import logging
import os
import io
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from ms_service_profiler.exporters.utils import save_dataframe_to_csv
from ms_service_profiler.exporters.exporter_kvcache import ExporterKVCacheData


pd_separate_pull_kv_data = """,pid,tid,event_type,start_time,end_time,mark_id,ori_msg,message,name,type,domain,rid,QueueSize=,scope#queue,deviceBlock=,scope#dp,RUNNING+,WAITING+,PENDING+,replyTokenSize=,END+,span_id,during_time,start_datetime,end_datetime,recvTokenSize=,PREFILL_HOLD+,rank,batch_seq_len,block_tables,res_list,rid_list,token_id_list,batch_type,batch_size,prefill_batch_size,decode_batch_size
9765,17329,18655,start/end,1739329372248722.8,1739329372252357.0,1,,"{'name': 'PullKVCache', 'type': 2, 'domain': 'PullKVCache', 'rid': [0], 'rank': 1, 'batch_seq_len': [7], 'block_tables': [[2886795281, [0], [0]]]}",PullKVCache,2,PullKVCache,0,,,,,,,,,,1,3634.25,2025-02-12 03:02:52:248723,2025-02-12 03:02:52:252357,,,1.0,[7],"[[2886795281, [0], [0]]]",[0],[0],[None],Decode,1,,
9769,17327,18654,start/end,1739329372250254.8,1739329372253900.2,1,  ,"{'name': 'PullKVCache', 'type': 2, 'domain': 'PullKVCache', 'rid': [0], 'rank': 0, 'batch_seq_len': [7], 'block_tables': [[2886795281, [0], [0]]]}",PullKVCache,2,PullKVCache,0,,,,,,,,,,1,3645.5,2025-02-12 03:02:52:250255,2025-02-12 03:02:52:253900,,,0.0,[7],"[[2886795281, [0], [0]]]",[0],[0],[None],Decode,1,,
11604,17329,18655,start/end,1739329374128456.0,1739329374130807.5,347,,"{'name': 'PullKVCache', 'type': 2, 'domain': 'PullKVCache', 'rid': [1], 'rank': 1, 'batch_seq_len': [7], 'block_tables': [[2886795281, [1], [1]]]}",PullKVCache,2,PullKVCache,1,,,,,,,,,,347,2351.5,2025-02-12 03:02:54:128456,2025-02-12 03:02:54:130807,,,1.0,[7],"[[2886795281, [1], [1]]]",[1],[1],[None],Decode,1,,
11605,17327,18654,start/end,1739329374128533.8,1739329374131034.2,347,,"{'name': 'PullKVCache', 'type': 2, 'domain': 'PullKVCache', 'rid': [1], 'rank': 0, 'batch_seq_len': [7], 'block_tables': [[2886795281, [1], [1]]]}",PullKVCache,2,PullKVCache,1,,,,,,,,,,347,2500.5,2025-02-12 03:02:54:128534,2025-02-12 03:02:54:131034,,,0.0,[7],"[[2886795281, [1], [1]]]",[1],[1],[None],Decode,1,,
13236,17327,18654,start/end,1739329375663783.5,1739329375666292.8,693,,"{'name': 'PullKVCache', 'type': 2, 'domain': 'PullKVCache', 'rid': [2], 'rank': 0, 'batch_seq_len': [7], 'block_tables': [[2886795281, [2], [2]]]}",PullKVCache,2,PullKVCache,2,,,,,,,,,,693,2509.25,2025-02-12 03:02:55:663784,2025-02-12 03:02:55:666293,,,0.0,[7],"[[2886795281, [2], [2]]]",[2],[2],[None],Decode,1,,
13237,17329,18655,start/end,1739329375663866.0,1739329375666666.2,693,,"{'name': 'PullKVCache', 'type': 2, 'domain': 'PullKVCache', 'rid': [2], 'rank': 1, 'batch_seq_len': [7], 'block_tables': [[2886795281, [2], [2]]]}",PullKVCache,2,PullKVCache,2,,,,,,,,,,693,2800.25,2025-02-12 03:02:55:663866,2025-02-12 03:02:55:666666,,,1.0,[7],"[[2886795281, [2], [2]]]",[2],[2],[None],Decode,1,,
"""

pd_separate_pull_kv_data_missing_key = """,pid,tid,event_type,start_time,end_time,mark_id,ori_msg,message,name,type,domain,rid,QueueSize=,scope#queue,deviceBlock=,scope#dp,RUNNING+,WAITING+,PENDING+,replyTokenSize=,END+,span_id,during_time,start_datetime,end_datetime,recvTokenSize=,PREFILL_HOLD+,rank,seq_len,block_tables,res_list,rid_list,token_id_list,batch_type,batch_size,prefill_batch_size,decode_batch_size
9765,17329,18655,start/end,1739329372248722.8,1739329372252357.0,1,,"{'name': 'PullKVCache', 'type': 2, 'domain': 'PullKVCache', 'rid': [0], 'rank': 1, 'batch_seq_len': [7], 'block_tables': [[2886795281, [0], [0]]]}",PullKVCache,2,PullKVCache,0,,,,,,,,,,1,3634.25,2025-02-12 03:02:52:248723,2025-02-12 03:02:52:252357,,,1.0,[7],"[[2886795281, [0], [0]]]",[0],[0],[None],Decode,1,,
9769,17327,18654,start/end,1739329372250254.8,1739329372253900.2,1,  ,"{'name': 'PullKVCache', 'type': 2, 'domain': 'PullKVCache', 'rid': [0], 'rank': 0, 'batch_seq_len': [7], 'block_tables': [[2886795281, [0], [0]]]}",PullKVCache,2,PullKVCache,0,,,,,,,,,,1,3645.5,2025-02-12 03:02:52:250255,2025-02-12 03:02:52:253900,,,0.0,[7],"[[2886795281, [0], [0]]]",[0],[0],[None],Decode,1,,
11604,17329,18655,start/end,1739329374128456.0,1739329374130807.5,347,,"{'name': 'PullKVCache', 'type': 2, 'domain': 'PullKVCache', 'rid': [1], 'rank': 1, 'batch_seq_len': [7], 'block_tables': [[2886795281, [1], [1]]]}",PullKVCache,2,PullKVCache,1,,,,,,,,,,347,2351.5,2025-02-12 03:02:54:128456,2025-02-12 03:02:54:130807,,,1.0,[7],"[[2886795281, [1], [1]]]",[1],[1],[None],Decode,1,,
11605,17327,18654,start/end,1739329374128533.8,1739329374131034.2,347,,"{'name': 'PullKVCache', 'type': 2, 'domain': 'PullKVCache', 'rid': [1], 'rank': 0, 'batch_seq_len': [7], 'block_tables': [[2886795281, [1], [1]]]}",PullKVCache,2,PullKVCache,1,,,,,,,,,,347,2500.5,2025-02-12 03:02:54:128534,2025-02-12 03:02:54:131034,,,0.0,[7],"[[2886795281, [1], [1]]]",[1],[1],[None],Decode,1,,
13236,17327,18654,start/end,1739329375663783.5,1739329375666292.8,693,,"{'name': 'PullKVCache', 'type': 2, 'domain': 'PullKVCache', 'rid': [2], 'rank': 0, 'batch_seq_len': [7], 'block_tables': [[2886795281, [2], [2]]]}",PullKVCache,2,PullKVCache,2,,,,,,,,,,693,2509.25,2025-02-12 03:02:55:663784,2025-02-12 03:02:55:666293,,,0.0,[7],"[[2886795281, [2], [2]]]",[2],[2],[None],Decode,1,,
13237,17329,18655,start/end,1739329375663866.0,1739329375666666.2,693,,"{'name': 'PullKVCache', 'type': 2, 'domain': 'PullKVCache', 'rid': [2], 'rank': 1, 'batch_seq_len': [7], 'block_tables': [[2886795281, [2], [2]]]}",PullKVCache,2,PullKVCache,2,,,,,,,,,,693,2800.25,2025-02-12 03:02:55:663866,2025-02-12 03:02:55:666666,,,1.0,[7],"[[2886795281, [2], [2]]]",[2],[2],[None],Decode,1,,
"""


class TestExporterBatchData(unittest.TestCase):
    def setUp(self):
        current_dir = os.getcwd()
        self.args = type('Args', (object,), {'output_path': current_dir})
        self.data = {
            'tx_data_df': self.create_df()
        }
        self.data_pd_separate = {
            'tx_data_df': self.create_df_pd_separate()
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

    def create_df_pd_separate(self):
        # 使用 io.StringIO 将字符串转换为类似文件的对象
        import io
        csv_file = io.StringIO(pd_separate_pull_kv_data)

        # 使用 pd.read_csv 读取数据并创建 DataFrame
        df = pd.read_csv(csv_file)

        return df

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

    def test_export_pd_separate(self):
        file_path_kvcache = Path(os.path.join(os.getcwd(), 'kvcache.csv'))
        file_path_pd_separate_kvcache = Path(os.path.join(os.getcwd(), 'pd_separate_kvcache.csv'))
        data = {'tx_data_df': pd.read_csv(io.StringIO(pd_separate_pull_kv_data))}
        try:
            # 初始化args
            ExporterKVCacheData.initialize(self.args)
            # 调用export方法
            ExporterKVCacheData.export(data)
            # 验证CSV文件是否生成
            self.assertTrue(file_path_pd_separate_kvcache.is_file())
        finally:
            # 清理
            if file_path_kvcache.is_file():
                file_path_kvcache.unlink()
            if file_path_pd_separate_kvcache.is_file():
                file_path_pd_separate_kvcache.unlink()

    def test_export_pd_separate_missing_key(self):
        file_path_kvcache = Path(os.path.join(os.getcwd(), 'kvcache.csv'))
        file_path_pd_separate_kvcache = Path(os.path.join(os.getcwd(), 'pd_separate_kvcache.csv'))
        data = {'tx_data_df': pd.read_csv(io.StringIO(pd_separate_pull_kv_data_missing_key))}
        try:
            # 初始化args
            ExporterKVCacheData.initialize(self.args)
            # 调用export方法
            ExporterKVCacheData.export(data)
            # 验证CSV文件是否生成
            self.assertTrue(file_path_pd_separate_kvcache.is_file())
        finally:
            # 清理
            if file_path_kvcache.is_file():
                file_path_kvcache.unlink()
            if file_path_pd_separate_kvcache.is_file():
                file_path_pd_separate_kvcache.unlink()

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
    