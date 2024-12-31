# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import os
from unittest import TestCase

from test.path_manager import PathManager
from test.st.utils import execute_cmd



class TestAnalyzeCmd(TestCase):
    ST_DATA_PATH = os.getenv("MS_SERVICE_PROFILER",
                             "/home/xujintao")
    INPUT_PATH = os.path.join(ST_DATA_PATH, "1230-1148-100Req")
    OUTPUT_PATH = os.path.join(ST_DATA_PATH, "test")
    COMMAND_SUCCESS = 0
    ANALYZE_PROFILER = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")),
                                         "ms_service_profiler/analyze.py")

    def setup_class(self):
        PathManager.make_dir_safety(self.OUTPUT_PATH)
        cmd = ["python", self.ANALYZE_PROFILER, "--input_path", self.INPUT_PATH, "--output_path", self.OUTPUT_PATH]
        if execute_cmd(cmd) != self.COMMAND_SUCCESS or not os.path.exists(self.OUTPUT_PATH):
            self.assertFalse(True, msg="enable ms service profiler analyze task failed.")

    def teardown_class(self):
        PathManager.remove_path_safety(self.OUTPUT_PATH)

    def test_profiler(self):
        # 校验输出文件是否存在
        db_file = glob.glob(f"{self.OUTPUT_PATH}/*.db")
        csv_file = glob.glob(f"{self.OUTPUT_PATH}/*.csv")
        trace_view_json = glob.glob(f"{self.OUTPUT_PATH}/chrome_tracing.json")[0]

        self.assertEqual(len(db_file), 1, msg="The number of db files is incorrect.")
        self.assertEqual(len(csv_file), 3, msg="The number of csv files is incorrect.")
        if not os.path.exists(trace_view_json):
            self.fail("trace_view.json does not exist")
