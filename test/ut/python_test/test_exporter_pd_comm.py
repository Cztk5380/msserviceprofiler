# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import unittest
from unittest.mock import patch
from pathlib import Path
from collections import namedtuple
import os
import shutil
import pandas as pd
from ms_service_profiler.exporters.exporter_pd_comm import ExporterPDComm


class TestExporterPDComm(unittest.TestCase):
    def setUp(self):
        test_path = os.path.join(os.getcwd(), "output_test")
        self.args = type('Args', (object,), {'output_path': test_path, 'format': ['csv']})
        ExporterPDComm.initialize(self.args)

    def test_export(self):
        # 创建一个示例数据
        try:
            test_path = os.path.join(os.getcwd(), "output_test")
            os.makedirs(test_path, exist_ok=True)
            os.chmod(test_path, 0o740)
            output_file_path = Path(test_path, 'pd_split_communication.csv')
            data = {'tx_data_df': pd.DataFrame([
                {'domain': 'Communication', 'rid': 1, 'name': 'receiveReq', 'start_datetime': '2023-01-01 00:00:00000'},
                {'domain': 'Communication', 'rid': 1, 'name': 'sendReqToD', 'start_datetime': '2023-01-01 00:00:01000'},
                {'domain': 'Communication', 'rid': 1, 'name': 'sendReqToDSucc',
                 'start_datetime': '2023-01-01 00:00:02000'},
                {'domain': 'Communication', 'rid': 1, 'name': 'prefillRes', 'start_datetime': '2023-01-01 00:00:03000'},
                {'domain': 'Communication', 'rid': 1, 'name': 'decodeRes', 'start_datetime': '2023-01-01 00:00:04000'}
            ])}
            ExporterPDComm.export(data)

            # 验证req_result_list是否正确
            self.assertEqual(ExporterPDComm.req_result_list, [
                {'rid': 1, 'http_req_time(ms)': '2023-01-01 00:00:00', 'send_request_time(ms)': '2023-01-01 00:00:01',
                'send_request_succ_time(ms)': '2023-01-01 00:00:02', 'prefill_res_time(ms)': '2023-01-01 00:00:03',
                'requset_end_time(ms)': '2023-01-01 00:00:04'}
            ])
            
            
        finally:
            # 清理
            shutil.rmtree(test_path)


if __name__ == '__main__':
    unittest.main()