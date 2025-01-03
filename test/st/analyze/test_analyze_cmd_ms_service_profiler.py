# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import os
import shutil
import sqlite3

from unittest import TestCase
import ast
import pytest
import pandas as pd
from ...st.utils import execute_cmd


def check_has_vaild_table(cursor, table_name, columns_to_check):
    # 校验存在数据表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name, ))
    table_exists = cursor.fetchone()
    assert table_exists is not None

    # 校验生成的列
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns_in_table = [row[1] for row in cursor]
    pytest.assume(all(column in columns_in_table for column in columns_to_check))

    # 校验至少存在一行所有的列都不为空
    cursor.execute(f"SELECT * FROM {table_name}")
    data = cursor.fetchall()
    for row in data:
        if all(row):
            return
    pytest.assume(False)


def check_latency_data(output_path):
    # 校验db文件正常生成
    db_path = os.path.join(output_path, 'profiler.db')
    assert os.path.exists(db_path)

    # 校验时延数据表
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    columns_to_check = ['avg', 'p50', 'p90', 'p99', 'timestamp']
    check_has_vaild_table(cursor, 'decode_gen_speed', columns_to_check)
    check_has_vaild_table(cursor, 'first_token_latency', columns_to_check)
    check_has_vaild_table(cursor, 'prefill_gen_speed', columns_to_check)
    check_has_vaild_table(cursor, 'req_latency', columns_to_check)

    # 关闭连接
    conn.close()

def check_column(actual_columns, expected_columns, context=""):
        # 检查是否有缺失的列
        missing_columns = set(expected_columns) - set(actual_columns)
        pytest.assume(not missing_columns, f"{context} 表中缺少列: {missing_columns}")


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
        check_column(df.columns.tolist(), expected_header, context='batch.csv')
        
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
        check_column(df.columns.tolist(), expected_header, context='request.csv')

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

    def test_prase_ms_service_profiler_data(self):
        #校验msserviceprofiler打点采集数据解析功能是否正常解析，校验输出文件及内容
        cmd = ["python", self.ANALYZE_PROFILER, "--input_path", self.INPUT_PATH, "--output_path", self.OUTPUT_PATH]
        if execute_cmd(cmd) != self.COMMAND_SUCCESS or not os.path.exists(self.OUTPUT_PATH):
            self.assertFalse(True, msg="enable ms service profiler analyze task failed.")
        # 校验输出文件是否存在
        with self.subTest():
            self.check_req_data_csv_integrity()
        with self.subTest():
            self.check_batch_data_csv_integrity()

        # 校验时延数据生成
        with self.subTest():
            check_latency_data(self.OUTPUT_PATH)
