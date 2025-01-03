# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import os
import pytest
import pandas as pd
import shutil
from unittest import TestCase

from test.st.utils import execute_cmd


def check_req_data(path):
    csv_file_path = f"{path}/request.csv"
    if not os.path.isfile(csv_file_path):
        return 0
    df = pd.read_csv(csv_file_path)
    if len(df) != 10:
        return 0
    expected_header = ['http_rid', 'start_time_httpReq(microsecond)', 'recv_token_size', 'reply_token_size',
                       'execution_time(microsecond)', 'queue_wait_time(microsecond)']
    for header in expected_header:
        if header not in df.columns.tolist():
            return 0
        return 1


def check_batch_data(path):
    csv_file_path = f"{path}/batch.csv"
    if not os.path.isfile(csv_file_path):
        return 0
    df = pd.read_csv(csv_file_path)
    if len(df) != 1002:
        return 0
    expected_header = ['name', 'res_list', 'start_time(microsecond)', 'end_time(microsecond)',
                       'batch_size', 'batch_type', 'during_time(microsecond)']
    for header in expected_header:
        if header not in df.columns.tolist():
            return 0
        return 1


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
        # 校验输出文件是否存在
        db_file = glob.glob(f"{self.OUTPUT_PATH}/*.db")
        csv_file = glob.glob(f"{self.OUTPUT_PATH}/*.csv")
        json_file = glob.glob(f"{self.OUTPUT_PATH}/*.json")

        pytest.assume(len(db_file) == 1)
        pytest.assume(len(csv_file) == 3)
        pytest.assume(len(json_file) == 1)
        pytest.assume(check_req_data(self.OUTPUT_PATH) == 1)
        pytest.assume(check_batch_data(self.OUTPUT_PATH) == 1)