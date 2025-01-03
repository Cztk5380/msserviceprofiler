# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import os
import shutil
from unittest import TestCase
from test.st.utils import execute_cmd
import pytest
import pandas as pd


def check_req_data_csv_integrity(path, test_case):
    #校验该路径下是否正确的生成req_data的csv文件，以及文件内容
    csv_file_path = f"{path}/request.csv"
    test_case.assertTrue(os.path.isfile(csv_file_path), "文件不存在".format(csv_file_path))
    df = pd.read_csv(csv_file_path)
    test_case.assertNotEqual(len(df), 0, msg="The data of req csv is empty.")
    expected_header = ['http_rid', 'start_time_httpReq(microsecond)', 'recv_token_size', 'reply_token_size',
                    'execution_time(microsecond)', 'queue_wait_time(microsecond)']
    test_case.assertEqual(expected_header, df.columns.tolist(), "数据帧的列不正确")
    

def check_batch_data_csv_integrity(path, test_case):
    #校验该路径下是否正确的生成batch_data的csv文件，以及文件内容
    csv_file_path = f"{path}/batch.csv"
    test_case.assertTrue(os.path.isfile(csv_file_path), "文件不存在".format(csv_file_path))
    df = pd.read_csv(csv_file_path)
    test_case.assertNotEqual(len(df), 0, msg="The data of batch csv is empty.")
    expected_header = ['name', 'res_list', 'start_time(microsecond)', 'end_time(microsecond)',
                    'batch_size', 'batch_type', 'during_time(microsecond)']
    test_case.assertEqual(expected_header, df.columns.tolist(), "数据帧的列不正确")


class TestAnalyzeCmd(TestCase):
    ST_DATA_PATH = os.getenv("MS_SERVICE_PROFILER", "/data/ms_service_profiler")
    INPUT_PATH = os.path.join(ST_DATA_PATH, "input/analyze/1225-196-10Req")
    OUTPUT_PATH = os.path.join(ST_DATA_PATH, "output/analyze")
    COMMAND_SUCCESS = 0
    ANALYZE_PROFILER = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")),
                                    "ms_service_profiler/analyze.py")

    def setup_class(self):
        os.makedirs(self.OUTPUT_PATH, mode=0o750, exist_ok=True)

    def teardown_class(self):
        shutil.rmtree(self.OUTPUT_PATH)

    def test_profiler(self):
        cmd = ["python", self.ANALYZE_PROFILER, "--input_path", self.INPUT_PATH, "--output_path", self.OUTPUT_PATH]
        if execute_cmd(cmd) != self.COMMAND_SUCCESS or not os.path.exists(self.OUTPUT_PATH):
            self.assertFalse(True, msg="enable ms service profiler analyze task failed.")
        check_req_data_csv_integrity(self.OUTPUT_PATH, self)
        check_batch_data_csv_integrity(self.OUTPUT_PATH, self)