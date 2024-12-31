import os
from unittest import TestCase

from test.path_manager import PathManager
from test.st.utils import execute_cmd



class TestCompareToolsCmdPytorchNpuVsNpuEnableApiCompare(TestCase):
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
            self.assertEqual(False, True, msg="enable ms service profiler analyze task failed.")

    def teardown_class(self):
        PathManager.remove_path_safety(self.OUTPUT_PATH)

    def test_profiler(self):
        assert 1==1
