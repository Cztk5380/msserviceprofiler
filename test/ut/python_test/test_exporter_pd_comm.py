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
        self.args = type('Args', (object,), {'output_path': test_path})
        ExporterPDComm.initialize(self.args)

    def test_export(self):
        # 创建一个示例数据
        try:
            test_path = os.path.join(os.getcwd(), "output_test")
            os.makedirs(test_path, exist_ok=True)
            os.chmod(test_path, 0o740)
            output_file_path = Path(test_path, 'pdSplitComm.csv')
            data = {'tx_data_df': pd.DataFrame([
                {'domain': 'PDSplit', 'rid': 1, 'name': 'receiveReq', 'start_datetime': '2023-01-01 00:00:00'},
                {'domain': 'PDSplit', 'rid': 1, 'name': 'sendReqToD', 'start_datetime': '2023-01-01 00:00:01'},
                {'domain': 'PDSplit', 'rid': 1, 'name': 'sendReqToDSucc', 'start_datetime': '2023-01-01 00:00:02'},
                {'domain': 'PDSplit', 'rid': 1, 'name': 'prefillRes', 'start_datetime': '2023-01-01 00:00:03'},
                {'domain': 'PDSplit', 'rid': 1, 'name': 'decodeRes', 'start_datetime': '2023-01-01 00:00:04'}
            ])}
            ExporterPDComm.export(data)

            # 验证req_result_list是否正确
            self.assertEqual(ExporterPDComm.req_result_list, [
                {'rid': 1, 'httpReqTime': '2023-01-01 00:00:00', 'requestSendTime': '2023-01-01 00:00:01',
                'requestSendSuccTime': '2023-01-01 00:00:02', 'prefillResTime': '2023-01-01 00:00:03',
                'requsetEndTime': '2023-01-01 00:00:04'}
            ])
            
            
        finally:
            # 清理
            shutil.rmtree(test_path)


if __name__ == '__main__':
    unittest.main()