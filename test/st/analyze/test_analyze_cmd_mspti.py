# Copyright Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
import os
import pandas as pd
from unittest import TestCase
import sqlite3
import random

from ...st.utils import execute_cmd


class TestAnalyzeCmd(TestCase):
    ST_DATA_PATH = "/data/ms_service_profiler"
    INPUT_PATH = os.path.join(ST_DATA_PATH, "input/analyze/ms_service_mspti")
    OUTPUT_PATH = os.path.join(ST_DATA_PATH, "output/analyze")
    DB_FILE_NAME = "profiler.db"
    COMMAND_SUCCESS = 0
    ANALYZE_PROFILER = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")),
                                    "ms_service_profiler/parse.py")
    FORMAT = ['csv', 'json', 'db']

    def _common_csv_check(self, csv_path, expect_columns, expect_length=None):
        # 输出csv路径 校验路径是否存在 csv表格columns是否和输入匹配 表格长度是否和输入匹配
        csv_exist = os.path.exists(csv_path)
        self.assertTrue(csv_exist, msg=f"csv_path: {csv_path} not exist")
        if not csv_exist:
            return

        df = pd.read_csv(csv_path)
        csv_columns = list(df.columns)
        self.assertEqual(csv_columns, expect_columns,
                         msg=f"columns in csv:{csv_columns} "
                             f"not match expect_columns:{expect_columns}")

        if expect_length:
            self.assertEqual(len(df), expect_length,
                             msg=f"csv_length:{len(df)} "
                                 f"not match expect_length:{expect_length}")

    def _common_db_table_check(self, db_path, table_name, sql_query, expect_columns, expect_length=None):
        # 输出db路径 校验路径是否存在 使用sql query从db中读取特定table 校验该table的columns是否和输入匹配 长度是否和输入匹配
        db_exist = os.path.exists(db_path)
        self.assertTrue(db_exist, msg=f"csv_path: {db_path} not exist")
        if not db_exist:
            return

        try:
            with sqlite3.connect(db_path) as conn:
                df = pd.read_sql_query(sql_query, conn)
        except Exception as e:
            self.assertTrue(False,
                            msg=f"Read db file from path:{db_path} failed.\n"
                                  f"Sql_query is {sql_query}.\n"
                                  f"Error message is {e}")

        table_columns = list(df.columns)
        self.assertEqual(table_columns, expect_columns,
                         msg=f"columns in db table {table_name}:{table_columns} "
                             f"not match expect_columns:{expect_columns}")

        if expect_length:
            table_length = len(df)
            self.assertEqual(table_length, expect_length,
                             msg=f"db table {table_name} length:{table_length} "
                                 f"not match expect_length:{expect_length}")

    def _common_csv_match_db_table_check(self, db_path, csv_path, table_name, sql_query, sample_nums):
        # 输入db csv路径 使用sql_query从db中读取数据 随机挑选sample_nums个行 校验两边是否一致
        # 该函数中不进行文件存在、读取是否成功校验 应当提前使用_common_db_table_check和_common_csv_check进行校验

        with sqlite3.connect(db_path) as conn:
            csv_df = pd.read_csv(csv_path)
            db_df = pd.read_sql_query(sql_query, conn)

            self.assertEqual(len(csv_df), len(db_df),
                             msg=f"db file:{db_path} table:{table_name} length not match csv_file:{csv_path}")

            for _ in range(sample_nums):
                random_num = random.randint(0, len(csv_df) - 1)
                self.assertEqual(list(csv_df.loc[random_num]), list(db_df.loc[random_num]))

    def run_ep_balance_sub_test(self):
        with self.subTest(msg="ep_balance csv test"):
            ep_balance_csv_path = os.path.join(self.OUTPUT_PATH, "ep_balance.csv")
            ep_balance_columns = ["19362", "19364", "19366", "19371", "19381", "19391", "19406", "19416"]
            self._common_csv_check(ep_balance_csv_path, ep_balance_columns)

        with self.subTest(msg="ep balance db test"):
            ep_balance_db_path = os.path.join(self.OUTPUT_PATH, "profiler.db")
            ep_balance_query = """
                SELECT * FROM ep_balance
            """
            self._common_db_table_check(ep_balance_db_path, "ep_balance", ep_balance_query, ep_balance_columns)

        with self.subTest(msg="ep_balance db csv match test"):
            self._common_csv_match_db_table_check(ep_balance_db_path,
                                                  ep_balance_csv_path,
                                                  "ep_balance",
                                                  ep_balance_query,
                                                  10)

        with self.subTest(msg="ep_balance png check"):
            ep_balance_png_path = os.path.join(self.OUTPUT_PATH, "ep_balance.png")
            assert os.path.exists(ep_balance_png_path)
            assert os.path.isfile(ep_balance_png_path)

    def run_moe_analysis_test(self):
        with self.subTest(msg="moe_analysis csv test"):
            moe_analysis_path = os.path.join(self.OUTPUT_PATH, "moe_analysis.csv")
            moe_analysis_columns = ["Dataset", "Mean", "CI_Lower", "CI_Upper"]
            self._common_csv_check(moe_analysis_path, moe_analysis_columns)

        with self.subTest(msg="moe_analysis db test"):
            moe_analysis_db_path = os.path.join(self.OUTPUT_PATH, "profiler.db")
            moe_analysis_query = """
                SELECT * FROM moe_analysis
            """
            self._common_db_table_check(moe_analysis_db_path, "moe_analysis", moe_analysis_query, moe_analysis_columns)

        with self.subTest(msg="moe_analysis png check"):
            moe_analysis_png_path = os.path.join(self.OUTPUT_PATH, "moe_analysis.png")
            assert os.path.exists(moe_analysis_png_path)
            assert os.path.isfile(moe_analysis_png_path)

    def test_parse_mspti(self):
        cmd = ["python", self.ANALYZE_PROFILER, "--input-path", self.INPUT_PATH, "--output-path", self.OUTPUT_PATH,
               "--format", *self.FORMAT]

        if execute_cmd(cmd) != self.COMMAND_SUCCESS or not os.path.exists(self.OUTPUT_PATH):
            self.assertFalse(True, msg="enable ms service profiler analyze task failed.")

        self.run_ep_balance_sub_test()
        self.run_moe_analysis_test()
