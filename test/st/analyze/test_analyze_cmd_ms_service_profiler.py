# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import os
import shutil
from unittest import TestCase
from test.st.utils import execute_cmd
import ast
import pytest
import pandas as pd


def check_req_data_csv_integrity(path, test_case):
    # 校验该路径下是否正确生成req_data的csv文件，以及文件内容
    csv_file_path = f"{path}/request.csv"
    test_case.assertTrue(os.path.isfile(csv_file_path), "文件不存在".format(csv_file_path))
    df = pd.read_csv(csv_file_path)
    test_case.assertNotEqual(len(df), 0, msg="The data of req csv is empty.")

    expected_header = ['http_rid', 'start_time_httpReq(microsecond)', 'recv_token_size', 'reply_token_size',
                    'execution_time(microsecond)', 'queue_wait_time(microsecond)']
    test_case.assertEqual(expected_header, df.columns.tolist(), "数据帧的列不正确")

    # 检查第一行和最后一行数据
    first_row = df.iloc[0]
    last_row = df.iloc[-1]

    # 检查recv_token_size和reply_token_size是否为整数
    def is_whole_number(n):
        if n == int(n):
            return True
        else:
            return False

    # 检查第一行的recv_token_size
    if not is_whole_number(first_row['recv_token_size']):
        raise AssertionError("第一行的recv_token_size不是整数")

    # 检查最后一行的recv_token_size
    if not is_whole_number(last_row['recv_token_size']):
        raise AssertionError("最后一行的recv_token_size不是整数")

    # 检查第一行的reply_token_size
    if not is_whole_number(first_row['reply_token_size']):
        raise AssertionError("第一行的reply_token_size不是整数")

    # 检查最后一行的reply_token_size
    if not is_whole_number(last_row['reply_token_size']):
        raise AssertionError("最后一行的reply_token_size不是整数")

    # 检查execution_time(microsecond)和queue_wait_time(microsecond)是否大于0
    test_case.assertGreater(first_row['execution_time(microsecond)'], 0, "第一行的execution_time(microsecond)不是大于0的数")
    test_case.assertGreater(last_row['execution_time(microsecond)'], 0, "最后一行的execution_time(microsecond)不是大于0的数")
    test_case.assertGreater(first_row['queue_wait_time(microsecond)'], 0, "第一行的queue_wait_time(microsecond)不是大于0的数")
    test_case.assertGreater(last_row['queue_wait_time(microsecond)'], 0, "最后一行的queue_wait_time(microsecond)不是大于0的数")
    

def check_batch_data_csv_integrity(path, test_case):
    # 校验该路径下是否正确生成batch_data的csv文件，以及文件内容
    csv_file_path = os.path.join(path, "batch.csv")
    
    # 检查文件是否存在
    test_case.assertTrue(os.path.isfile(csv_file_path), f"文件不存在: {csv_file_path}")
    
    # 读取csv文件内容
    df = pd.read_csv(csv_file_path)
    
    # 检查文件是否为空
    test_case.assertNotEqual(len(df), 0, "The data of batch csv is empty.")
    
    # 预期的列名
    expected_header = ['name', 'res_list', 'start_time(microsecond)', 'end_time(microsecond)',
                    'batch_size', 'batch_type', 'during_time(microsecond)']
    
    # 检查列名是否正确
    test_case.assertEqual(expected_header, df.columns.tolist(), "数据帧的列不正确")
    
    # 检查第一行和最后一行数据
    first_row = df.iloc[0]
    last_row = df.iloc[-1]
    
    # 检查res_list的格式
    def is_valid_res_list(res_list_str):
        # 将字符串转换为列表
        res_list = ast.literal_eval(res_list_str)
        # 检查res_list是否是一个列表，每个元素都是字典，且字典包含'rid'和'iter'这两个键
        return all(isinstance(item, dict) and 'rid' in item and 'iter' in item for item in res_list)
    
    # 检查第一行和最后一行的res_list格式
    test_case.assertTrue(is_valid_res_list(first_row['res_list']), "第一行的res_list格式不正确")
    test_case.assertTrue(is_valid_res_list(last_row['res_list']), "最后一行的res_list格式不正确")


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
        with self.subTest():
            check_req_data_csv_integrity(self.OUTPUT_PATH, self)
        with self.subTest():
            check_batch_data_csv_integrity(self.OUTPUT_PATH, self)