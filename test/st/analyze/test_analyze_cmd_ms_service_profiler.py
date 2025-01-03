# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import os
import shutil
from unittest import TestCase

from test.st.utils import execute_cmd


class TestAnalyzeCmd(TestCase):
    ST_DATA_PATH = os.getenv("MS_SERVICE_PROFILER", "/data/ms_service_profiler")
    INPUT_PATH = os.path.join(ST_DATA_PATH, "input/analyze/1225-196-10Req")
    OUTPUT_PATH = os.path.join(ST_DATA_PATH, "output/analyze")
    COMMAND_SUCCESS = 0
    ANALYZE_PROFILER = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")),
                                         "ms_service_profiler/analyze.py")

    def setup_class(self):
        os.makedirs(self.OUTPUT_PATH, mode=0o750)

    def teardown_class(self):
        shutil.rmtree(self.OUTPUT_PATH)

    def test_profiler(self):
        cmd = ["python", self.ANALYZE_PROFILER, "--input_path", self.INPUT_PATH, "--output_path", self.OUTPUT_PATH]
        if execute_cmd(cmd) != self.COMMAND_SUCCESS or not os.path.exists(self.OUTPUT_PATH):
            self.assertFalse(True, msg="enable ms service profiler analyze task failed.")
        # 校验输出文件是否存在
        db_file = glob.glob(f"{self.OUTPUT_PATH}/*.db")
        csv_file = glob.glob(f"{self.OUTPUT_PATH}/*.csv")
        trace_view_json = glob.glob(f"{self.OUTPUT_PATH}/chrome_tracing.json")[0]

        self.assertEqual(len(db_file), 1, msg="The number of db files is incorrect.")
        self.assertEqual(len(csv_file), 3, msg="The number of csv files is incorrect.")
        if not os.path.exists(trace_view_json):
            self.fail("trace_view.json does not exist")

        with self.subTest():
            if db_file:
                self.check_req_status(db_file[0])

    def check_req_status(self, fp):
        """Check req_status output. Make sure this testcase after test_profiler."""
        from enum import Enum
        import pandas as pd
        
        class ReqStatus(Enum):
            WAITING = 0
            PENDING = 1
            RUNNING = 2
            SWAPPED = 3
            RECOMPUTE = 4
            SUSPENDED = 5
            END = 6
            STOP = 7
            PREFILL_HOLD = 8

        conn = sqlite3.connect(fp)
        df = pd.read_sql_query("SELECT * FROM request_status", conn)
        conn.close()
        
        for col in ['start_datetime']:
            self.assertIn(col, df.columns, msg=f"{col} should be found in request_status.")
        for col in df.columns:
            self.assertIn(col, ReqStatus.__members__, msg=f"{col} should not be found in request_status.")
