# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import os
import shutil
import sqlite3
import ast
from unittest import TestCase

import pytest
import pandas as pd
from ...st.utils import execute_cmd


def check_column(actual_columns, expected_columns, context=""):
    # 检查是否有缺失的列
    missing_columns = set(expected_columns) - set(actual_columns)
    pytest.assume(not missing_columns, f"{context} 表中缺少列: {missing_columns}")


def check_kvcache_csv_content(output_path, csv_file_name):
    expected_csv_columns = [
        'domain', 'rid', 'start_time(microsecond)', 'end_time(microsecond)',
        'name', 'device_kvcache_left', 'during_time(microsecond)'
    ]
    csv_file = os.path.join(output_path, csv_file_name)
    # 检查文件是否存在
    assert os.path.exists(csv_file)
    assert os.path.isfile(csv_file)

    df = pd.read_csv(csv_file)
    actual_columns = df.columns.tolist()
    check_column(actual_columns, expected_csv_columns, context=csv_file_name)

    def is_whole_number(n):
        if n == int(n):
            return True
        else:
            return False

    # 定义一个函数，用于检查res_list的格式
    def check_row(df, row_index, columns):
        for column in columns:
            if not is_whole_number(df.iloc[row_index][column]):
                raise AssertionError(f"{row_index}行的{column}不是整数")

    # 检查数据框的第一行和最后一行的特定列
    rows_to_check = [0, -1]
    columns_to_check = ['device_kvcache_left']
    for row_index in rows_to_check:
        for column in columns_to_check:
            check_row(df, row_index, [column])


def check_kvcache_db_content(output_path, db_file_name):
    db_file = os.path.join(output_path, db_file_name)
    expected_db_columns = [
        'rid',
        'name',
        'real_start_time',
        'device_kvcache_left',
        'kvcache_usage_rate'
    ]
    assert os.path.exists(db_file)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('PRAGMA table_info("kvcache")')
    columns = cursor.fetchall()
    actual_columns = [column[1] for column in columns]

    check_column(actual_columns, expected_db_columns, context=db_file_name)

    conn.close()


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


class TestAnalyzeCmd(TestCase):
    ST_DATA_PATH = os.getenv("MS_SERVICE_PROFILER", "/data/ms_service_profiler")
    INPUT_PATH = os.path.join(ST_DATA_PATH, "input/analyze/1230-1148-100Req")
    OUTPUT_PATH = os.path.join(ST_DATA_PATH, "output/analyze")
    KVCACHE_CSV_FILE_NAME = "kvcache.csv"
    DB_FILE_NAME = "profiler.db"
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

        # kvcache校验
        with self.subTest("Check kvcache CSV content"):
            check_kvcache_csv_content(self.OUTPUT_PATH, self.KVCACHE_CSV_FILE_NAME)
        with self.subTest("Check kvcache DB content"):
            check_kvcache_db_content(self.OUTPUT_PATH, self.DB_FILE_NAME)

        # 校验时延数据生成
        with self.subTest():
            check_latency_data(self.OUTPUT_PATH)
