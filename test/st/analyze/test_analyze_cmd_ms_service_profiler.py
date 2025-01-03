# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import os
import shutil
import sqlite3
from unittest import TestCase

import pytest
from test.st.utils import execute_cmd


def check_has_vaild_table(cursor, table_name, columns_to_check):
    # 校验存在数据表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table_name, ))
    table_exists = cursor.fetchone()
    if table_exists is None:
        pytest.fail(f"{table_name} does not exists.")

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
    if not os.path.exists(db_path):
        pytest.fail(f"{db_path} does not exists.")

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

        # 校验时延数据生成
        with self.subTest():
            check_latency_data(self.OUTPUT_PATH)
