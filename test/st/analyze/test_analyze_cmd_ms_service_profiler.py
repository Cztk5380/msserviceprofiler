# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import sqlite3
import glob
import os
import shutil
from unittest import TestCase
import argparse
import pytest
from pathlib import Path
import pandas as pd
from ms_service_profiler.exporters.exporter_kvcache import ExporterKVCacheData
from ms_service_profiler.parse import parse
from ms_service_profiler.plugins.plugin_metric import PluginMetric
from ms_service_profiler.plugins.plugin_req_status import PluginReqStatus
from ms_service_profiler.plugins import builtin_plugins
from ms_service_profiler.exporters.factory import ExporterFactory

from test.st.utils import execute_cmd


class TestAnalyzeCmd(TestCase):
    ST_DATA_PATH = os.getenv("MS_SERVICE_PROFILER", "/data/ms_service_profiler")
    INPUT_PATH = os.path.join(ST_DATA_PATH, "input/analyze/1230-1148-100Req")
    OUTPUT_PATH = os.path.join(ST_DATA_PATH, "output/analyze")
    COMMAND_SUCCESS = 0
    KVCACHE_CSV_FILE_NAME = "kvcache.csv"
    DB_FILE_NAME = "profiler.db"
    ANALYZE_PROFILER = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")),
                                         "ms_service_profiler/analyze.py")

    def setup_class(self):
        os.makedirs(self.OUTPUT_PATH, mode=0o755, exist_ok=True)
        args = argparse.Namespace(output_path=self.OUTPUT_PATH, input_path=self.INPUT_PATH)
        exporters = ExporterFactory.create_exporters(args)
        custom_plugins = [PluginReqStatus]
        parse(self.INPUT_PATH, custom_plugins, exporters)

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

    def test_kvcache_csv_generated(self):
        # 检查 CSV 文件是否生成
        csv_file = os.path.join(self.OUTPUT_PATH, self.KVCACHE_CSV_FILE_NAME)
        with self.subTest():
            pytest.assume(os.path.exists(csv_file), f"{self.KVCACHE_CSV_FILE_NAME} 文件未生成")

    def test_kvcache_db_generated(self):
        # 检查 SQLite 数据库文件是否生成
        db_file = os.path.join(self.OUTPUT_PATH, self.KVCACHE_CSV_FILE_NAME)
        with self.subTest():
            pytest.assume(os.path.exists(db_file), f"{self.KVCACHE_CSV_FILE_NAME} 文件未生成")

    def test_kvcache_csv_content(self):
        # 检查 CSV 文件内容是否符合预期
        csv_file = os.path.join(self.OUTPUT_PATH, self.KVCACHE_CSV_FILE_NAME)
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            # 检查是否包含预期的列
            expected_columns = ['domain', 'rid', 'start_time(microsecond)', 'end_time(microsecond)',
                                'name', 'device_kvcache_left', 'during_time(microsecond)']
            with self.subTest():
                pytest.assume(list(df.columns) == expected_columns, "CSV 文件列名不符合预期")
        else:
            with self.subTest():
                pytest.assume(f"{self.CSV_FILE_NAME} 文件未生成")

    def test_kvcache_db_content(self):
        # 检查 SQLite 数据库文件是否符合预期
        db_file = os.path.join(self.OUTPUT_PATH, self.DB_FILE_NAME)
        if os.path.exists(db_file):
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute('PRAGMA table_info("kvcache")')
            columns = cursor.fetchall()
            # 预期列名
            expected_columns = [
                'rid',
                'name',
                'real_start_time',
                'device_kvcache_left',
                'kvcache_usage_rate'
            ]
            actual_columns = [column[1] for column in columns]
            # 检查是否有额外的列
            extra_columns = set(actual_columns) - set(expected_columns)
            if extra_columns:
                print(f"提示: 表中存在额外的列: {extra_columns}")

            # 检查是否有缺失的列
            missing_columns = set(expected_columns) - set(actual_columns)
            if missing_columns:
                with self.subTest():
                    pytest.assume(f"表中缺少预期的列: {missing_columns}")
            conn.close()
        else:
            with self.subTest():
                pytest.assume(f"{self.DB_FILE_NAME} 文件未生成")
