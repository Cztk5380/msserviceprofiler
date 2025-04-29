# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import io
import re
import os
import logging
import json
import shutil
import sqlite3
from typing import Dict, List
from collections import defaultdict
import ast
from unittest import TestCase
import ast
import pytest
import pandas as pd
from jsonschema import validate, ValidationError
from ...st.utils import execute_cmd


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
    check_no_empty_lines_before_first_line(df, context=csv_file_name)
    check_no_empty_lines_between_first_last_line(df, context=csv_file_name)
    

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


def check_pullkvcache_csv_content(csv_file):
    expected_csv_columns = [
        'domain', 'rank', 'rid', 'block_tables', 'batch_seq_len', 'during_time(microsecond)', \
        'start_datetime', 'end_datetime', 'start_time(microsecond)', 'end_time(microsecond)',
    ]
    # 检查文件是否存在
    assert os.path.exists(csv_file)
    assert os.path.isfile(csv_file)

    df = pd.read_csv(csv_file)
    actual_columns = df.columns.tolist()
    check_column(actual_columns, expected_csv_columns, context=csv_file)
    check_no_empty_lines_before_first_line(df, context=csv_file)
    check_no_empty_lines_between_first_last_line(df, context=csv_file)


def check_has_vaild_table(cursor, table_name, columns_to_check):
    # 校验存在数据表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
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


def check_req_status(output_path):
    from enum import Enum

    class ReqStatus(Enum):
        WAITING = 0
        PENDING = 1
        RUNNING = 2
        SWAPPED = 3
        RECOMPUTE = 4
        SUSPENDED = 5
        END = 6
        STOP = 7
        PREFILL_HOLD = 8

    # 校验db文件正常生成
    db_path = os.path.join(output_path, 'profiler.db')
    assert os.path.exists(db_path)

    # 获取数据表
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM request_status", conn)
    conn.close()

    # 校验列存在
    for col in ['timestamp', 'WAITING', 'PENDING', 'RUNNING']:
        assert col in df.columns.tolist()


def check_column(actual_columns, expected_columns, context=""):
    # 检查是否有缺失的列
    missing_columns = set(expected_columns) - set(actual_columns)
    pytest.assume(not missing_columns, f"{context} 表中缺少列: {missing_columns}")


def check_no_empty_lines_before_first_line(dataframe, context=""):
    empty_line = 0
    # 检查是否有空行
    for _, row in dataframe.iterrows():
        if row.isnull().all():
            empty_line += 1
        else:
            break
    
    pytest.assume(empty_line == 0, f"{context} table has {empty_line} empty lines.")


def check_no_empty_lines_between_first_last_line(dataframe, context=""):
    # 计算非空行的数量
    empty_rows = dataframe.eq('').all(axis=1)
    num_empty_rows = empty_rows.sum()
    pytest.assume(num_empty_rows == 0, f"{context} table has empty lines.")


def check_chrome_tracing_valid(output_path):
    trace_view_json = glob.glob(f"{output_path}/chrome_tracing.json")[0]
    assert os.path.exists(trace_view_json)

    schema = {
        "type": "object",
        "properties": {
            "traceEvents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "ph": {"type": "string", "enum": ["X", "I", "C", "M", "s", "f", "t"]},
                        "ts": {"type": ["number", "string"],
                               "pattern": "^\\d+(\\.\\d+)?$"
                               },  # 时间戳，单位为微秒
                        "dur": {"type": "number", "minimum": 0},  # 持续时间，适用于 X 类型事件
                        "pid": {"type": "integer"},  # 进程 ID
                        "tid": {"type": ["string", "integer"]},
                        "id": {"type": "string"},  # 时间线事件的 ID
                        "cat": {"type": "string"},  # 分类
                        "args": {
                            "type": "object",
                            "additionalProperties": True  # args 可以是任意键值对
                        }
                    },
                    "required": ["name", "ph", "pid"],  # 必需字段
                    "additionalProperties": False  # 防止额外字段
                }
            }
        },
        "required": ["traceEvents"],  # 必需字段
        "additionalProperties": False  # 防止额外字段
    }
    with open(trace_view_json) as f:
        data = json.load(f)

    validate(instance=data, schema=schema)


def check_chrome_tracing_content_valid(output_path):
    trace_view_json = glob.glob(f"{output_path}/chrome_tracing.json")[0]
    assert os.path.exists(trace_view_json)

    with open(trace_view_json, 'r', encoding='utf-8') as f:
        text = f.read()
    exist = ["NPU Usage"]
    for key in exist:
        pytest.assume(key in text, "流水图中应该包含NPU Usage")


def parse_message(message: str) -> dict:
    pattern = r"\^([^^]+)\^:(\^?.*?\^?)(?=\^|,|}|$)"
    matches = re.findall(pattern, message)
    return {
        k: v.strip('^').rstrip(',')
        for k, v in matches
    }


def collect_db_stats(root_dir: str, fields: List[str], table_name: str) -> Dict[str, Dict]:
    """
    返回结构:
    {
        "PROF_001": {
            "db_path": "...",       # 数据库路径
            "counts": {             # 统计结果
                "modelExec": 250,
                "BatchSchedule": 250
            },
            "total_records": 500    # 总记录数
        },
        "PROF_002": ...,
        "_total": {                 # 总值汇总（当verbose=True时存在）
            "modelExec": 500,
            "BatchSchedule": 500
        }
    }
    """
    results = {}
    grand_total = defaultdict(int)

    # 递归查找PROF目录
    prof_dirs = [
        d.rstrip(os.sep)
        for d in glob.glob(os.path.join(root_dir, "**/PROF_*/"), recursive=True)
        if os.path.isdir(d)
    ]

    assert prof_dirs, f"根目录下未发现任何PROF目录 | path={root_dir}"

    for _, prof_dir in enumerate(prof_dirs, 1):
        dir_name = os.path.basename(prof_dir)
        db_path = os.path.join(prof_dir, "host", "sqlite", "msproftx.db")

        assert os.path.isfile(db_path), f"数据库文件缺失 | path={db_path}"

        conn = None
        try:
            conn = sqlite3.connect(db_path)

            # 验证表结构
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            db_fields = [col[1] for col in cursor.fetchall()]

            assert "message" in db_fields, f"表 {table_name} 缺少 message 字段"

            counter = defaultdict(int)
            kvcache_count = 0
            total_records = 0
            cursor = conn.execute(f"SELECT message FROM {table_name}")
            for row in cursor:
                parsed = parse_message(row[0])
                name_value = parsed.get("name", "").strip()
                if name_value in fields:
                    counter[name_value] += 1
                    grand_total[name_value] += 1

                if parsed.get('domain') == 'KVCache':
                    kvcache_count += 1
                    grand_total['KVCache'] += 1

            # 记录结果
            results[dir_name] = {
                "db_path": db_path,
                "counts": dict(counter),
                "KVCache": kvcache_count,
                "total_records": total_records,
                "_status": "success"
            }

        finally:
            if conn:
                conn.close()

        return {
            **results,
            "_total": dict(grand_total)
        }


class TestAnalyzeCmd(TestCase):
    ST_DATA_PATH = os.getenv("MS_SERVICE_PROFILER", "/data/ms_service_profiler")
    INPUT_PATH = os.path.join(ST_DATA_PATH, "input/analyze/0211-1226")
    INPUT_PATH_PD_SEPARATE = os.path.join(ST_DATA_PATH, "input/analyze/pullkv_0212")
    OUTPUT_PATH = os.path.join(ST_DATA_PATH, "output/analyze")
    KVCACHE_CSV_FILE_NAME = "kvcache.csv"
    DB_FILE_NAME = "profiler.db"
    COMMAND_SUCCESS = 0
    ANALYZE_PROFILER = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")),
                                    "ms_service_profiler/parse.py")

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
        # 检查是否有多余空行
        check_no_empty_lines_before_first_line(df, context='batch.csv')
        check_no_empty_lines_between_first_last_line(df, context='batch.csv')

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
        # 检查是否有多余空行
        check_no_empty_lines_before_first_line(df, context='request.csv')
        check_no_empty_lines_between_first_last_line(df, context='request.csv')

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
        # 校验msserviceprofiler打点采集数据解析功能是否正常解析，校验输出文件及内容
        cmd = ["python", self.ANALYZE_PROFILER, "--input-path", self.INPUT_PATH, "--output-path", self.OUTPUT_PATH]
        if execute_cmd(cmd) != self.COMMAND_SUCCESS or not os.path.exists(self.OUTPUT_PATH):
            self.assertFalse(True, msg="enable ms service profiler analyze task failed.")
        # 新增数据库字段校验子测试
        with self.subTest("Validate DB field consistency across PROF directories"):
            self._validate_db_consistency()
        # 校验输出文件是否存在
        with self.subTest():
            self.check_req_data_csv_integrity()
        with self.subTest():
            self.check_batch_data_csv_integrity()

        # kvcache校验
        with self.subTest("Check kvcache CSV content"):
            check_kvcache_csv_content(self.OUTPUT_PATH, self.KVCACHE_CSV_FILE_NAME)
        with self.subTest("Check kvcache DB content"):
            check_kvcache_db_content(self.OUTPUT_PATH, self.DB_FILE_NAME)

        # 校验时延数据生成
        with self.subTest():
            check_latency_data(self.OUTPUT_PATH)

        # 校验请求状态数的数据生成
        with self.subTest():
            check_req_status(self.OUTPUT_PATH)

        # 校验chrome_tracing的数据格式
        with self.subTest():
            check_chrome_tracing_valid(self.OUTPUT_PATH)

        # 校验chrome_tracing的数据内容
        with self.subTest():
            check_chrome_tracing_content_valid(self.OUTPUT_PATH)

    def test_parse_data_in_pd_separate(self):
        # 校验msserviceprofiler打点PD分离数据解析功能是否正常解析，校验输出文件及内容
        cmd = ["python", self.ANALYZE_PROFILER, "--input-path", self.INPUT_PATH_PD_SEPARATE, \
            "--output-path", self.OUTPUT_PATH]
        if execute_cmd(cmd) != self.COMMAND_SUCCESS or not os.path.exists(self.OUTPUT_PATH):
            self.assertFalse(True, msg="enable ms service profiler analyze task failed.")

        with self.subTest("Check pullkvcache csv content"):
            check_pullkvcache_csv_content(os.path.join(self.OUTPUT_PATH, "pd_separate_kvcache.csv"))

    def _validate_db_consistency(self):
        """数据库与CSV总值一致性校验"""

        # 统计数据库总值
        db_stats = collect_db_stats(
            root_dir=self.INPUT_PATH,
            fields=["modelExec", "BatchSchedule", "KVCache"],
            table_name="MsprofTxEx",
        )
        db_total = db_stats.get("_total", {})

        validation_rules = [
            # batch.csv 校验
            {
                "db_field": "modelExec",
                "csv_path": os.path.join(self.OUTPUT_PATH, "batch.csv"),
                "csv_column": "name",
                "match_value": "modelExec"
            },
            {
                "db_field": "BatchSchedule",
                "csv_path": os.path.join(self.OUTPUT_PATH, "batch.csv"),
                "csv_column": "name",
                "match_value": "BatchSchedule"
            },
            # kvcache.csv 校验
            {
                "db_field": "KVCache",
                "csv_path": os.path.join(self.OUTPUT_PATH, "kvcache.csv"),
                "csv_column": "device_kvcache_left",
                "match_value": None # 统计行数
            }
        ]

        # 统一校验逻辑
        failures = []
        for rule in validation_rules:
            db_count = db_total.get(rule["db_field"], 0)
            csv_count = self._validate_csv_count(
                csv_path=rule["csv_path"],
                column=rule["csv_column"],
                match_value=rule["match_value"]
            )

            if db_count != csv_count:
                msg = f"{rule['db_field']} 次数不匹配: DB={db_count} vs CSV={csv_count}"
                failures.append(msg)

        if failures:
            self.fail("\n".join(failures))
        else:
            self.assertTrue(True, "所有数据校验一致")

    def _validate_csv_count(self, csv_path: str, column: str, match_value: str = None) -> int:
        """通用CSV校验方法"""
        self.assertTrue(
            os.path.exists(csv_path),
            f"CSV文件不存在 | path={csv_path}"
        )

        try:
            df = pd.read_csv(csv_path)
            self.assertIn(
                column,
                df.columns,
                f"CSV文件缺少列 | path={csv_path} column={column}"
            )

            # 匹配值计数 or 总行数
            if match_value is not None:
                return len(df[df[column] == match_value])
            return len(df)

        except Exception as e:
            raise self.failureException(f"读取CSV文件失败 | path={csv_path} error={str(e)}")