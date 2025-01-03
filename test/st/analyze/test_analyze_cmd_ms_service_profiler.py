# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import os
import shutil
from unittest import TestCase
from test.st.utils import execute_cmd
import ast
import pytest
import pandas as pd


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

    def check_batch_data_csv_integrity(self):
        # 校验该路径下是否正确生成batch_data的csv文件，以及文件内容
        csv_file_path = f"{self.OUTPUT_PATH}/batch.csv"
        self.assertTrue(os.path.isfile(csv_file_path), f"文件不存在: {csv_file_path}")
        df = pd.read_csv(csv_file_path)
        # 检查文件是否为空
        self.assertNotEqual(len(df), 0, "The data of batch csv is empty.")
        expected_header = ['name', 'res_list', 'start_time(microsecond)', 'end_time(microsecond)', 'batch_size', \
            'batch_type', 'during_time(microsecond)']
        
        # 检查列名是否正确
        self.assertEqual(expected_header, df.columns.tolist(), "数据帧的列不正确")
        
        # 定义一个函数，用于检查res_list的格式
        def is_valid_res_list(res_list_str):
            # 将字符串转换为列表
            res_list = ast.literal_eval(res_list_str)
            # 检查res_list是否是一个列表，每个元素都是字典，且字典包含'rid'和'iter'这两个键
            return all(isinstance(item, dict) and 'rid' in item and 'iter' in item for item in res_list)

        # 检查数据框的第一行和最后一行的特定列
        rows_to_check = [0, -1]
        columns_to_check = ['res_list']
        for row_index in rows_to_check:
            for column in columns_to_check:
                self.assertTrue(is_valid_res_list(df.iloc[row_index][column]), f"{row_index}行的{column}格式不正确")

    def check_req_data_csv_integrity(self):
        # 校验该路径下是否正确生成req_data的csv文件，以及文件内容
        csv_file_path = f"{self.OUTPUT_PATH}/request.csv"
        self.assertTrue(os.path.isfile(csv_file_path), "文件不存在".format(csv_file_path))
        df = pd.read_csv(csv_file_path)
        self.assertNotEqual(len(df), 0, msg="The data of req csv is empty.")

        expected_header = ['http_rid', 'start_time_httpReq(microsecond)', 'recv_token_size', 'reply_token_size', \
            'execution_time(microsecond)', 'queue_wait_time(microsecond)']
        self.assertEqual(expected_header, df.columns.tolist(), "数据帧的列不正确")

        def is_whole_number(n):
            if n == int(n):
                return True
            else:
                return False

        # 定义一个函数，用于检查数据框的某一行的特定列是否满足条件
        def check_row(df, row_index, columns):
            for column in columns:
                if not is_whole_number(df.iloc[row_index][column]):
                    raise AssertionError(f"{row_index}行的{column}不是整数")

        # 检查数据框的第一行和最后一行的特定列
        rows_to_check = [0, -1]
        columns_to_check = ['recv_token_size', 'reply_token_size']
        for row_index in rows_to_check:
            for column in columns_to_check:
                check_row(df, row_index, [column])

    def test_prase_msserviceprofiler_data(self):
        #校验msserviceprofiler打点采集数据解析功能是否正常解析，校验输出文件及内容
        cmd = ["python", self.ANALYZE_PROFILER, "--input_path", self.INPUT_PATH, "--output_path", self.OUTPUT_PATH]
        if execute_cmd(cmd) != self.COMMAND_SUCCESS or not os.path.exists(self.OUTPUT_PATH):
            self.assertFalse(True, msg="enable ms service profiler analyze task failed.")
        with self.subTest():
            self.check_req_data_csv_integrity()
        with self.subTest():
            self.check_batch_data_csv_integrity()