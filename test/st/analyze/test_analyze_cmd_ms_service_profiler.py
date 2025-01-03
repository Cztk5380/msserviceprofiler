# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import os
import shutil
import sqlite3
import pytest
from unittest import TestCase

from test.st.utils import execute_cmd


def check_has_latency_table(cursor, table_name):
    # 校验存在时延数据表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table_name,))
    table_exists = cursor.fetchone()
    pytest.assume(table_exists is not None)

    # 校验时延数据表中数据正常生成
    cursor.execute(f"SELECT * FROM {table_name}")
    data = cursor.fetchall()
    # 断言存在至少有一行所有列都不为空
    for row in data:
        if all(row):
            return
    pytest.assume(False)


# 校验时延数据生成
def check_latency_data(output_path):
    # 校验db文件正常生成
    db_path = os.path.join(output_path, 'profiler.db')
    if not os.path.exists(db_path):
        pytest.assume(False)
        logging.error(f"{db_path} does not exists.")
        return

    # 校验时延数据表
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    check_has_latency_table(cursor, 'decode_gen_speed')
    check_has_latency_table(cursor, 'first_token_latency')
    check_has_latency_table(cursor, 'prefill_gen_speed')
    check_has_latency_table(cursor, 'req_latency')

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

        check_latency_data(self.OUTPUT_PATH)
