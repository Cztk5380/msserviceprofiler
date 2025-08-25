# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import io
import re
import os
import json
import shutil
import sqlite3
from typing import Dict, List
from collections import defaultdict
import ast
import ast
import pytest
from pytest_check import check
import pandas as pd
from jsonschema import validate, ValidationError
from ms_service_profiler.exporters.utils import CURVE_VIEW_NAME_LIST
from test.st.executor.exec_parse import ExecParse


def check_kvcache_csv_content(output_path, csv_file_name):
    expected_csv_columns = [
        'domain', 'rid', 'timestamp(ms)',
        'name', 'device_kvcache_left'
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
                raise AssertionError(f"The value in row {row_index}, column {column} is not an integer")

    # 检查数据框的第一行和最后一行的特定列
    rows_to_check = [0, -1]
    columns_to_check = ['device_kvcache_left']
    for row_index in rows_to_check:
        if df.iloc[row_index]['name'] != 'allocate':
            for column in columns_to_check:
                check_row(df, row_index, [column])


def check_kvcache_db_content(output_path, db_file_name):
    db_file = os.path.join(output_path, db_file_name)
    expected_db_columns = [
        'rid',
        'name',
        'start_datetime',
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
        'domain', 'rank', 'rid', 'block_tables', 'batch_seq_len', 'during_time(ms)', \
        'start_datetime(ms)', 'end_datetime(ms)', 'start_time(ms)', 'end_time(ms)',
    ]
    # 检查文件是否存在
    assert os.path.exists(csv_file)
    assert os.path.isfile(csv_file)

    df = pd.read_csv(csv_file)
    actual_columns = df.columns.tolist()
    check_column(actual_columns, expected_csv_columns, context=csv_file)
    check_no_empty_lines_before_first_line(df, context=csv_file)
    check_no_empty_lines_between_first_last_line(df, context=csv_file)


def check_communication_csv_content(csv_file):
    expected_csv_columns = [
        'rid', 'http_req_time(ms)', 'send_request_time(ms)', 'send_request_succ_time(ms)', \
        'prefill_res_time(ms)', 'request_end_time(ms)'
    ]
    # 检查文件是否存在
    assert os.path.exists(csv_file)
    assert os.path.isfile(csv_file)

    df = pd.read_csv(csv_file)
    actual_columns = df.columns.tolist()
    check_column(actual_columns, expected_csv_columns, context=csv_file)
    check_no_empty_lines_before_first_line(df, context=csv_file)
    check_no_empty_lines_between_first_last_line(df, context=csv_file)


def check_table_with_no_empty_data(cursor, table_name, columns_to_check):
    # 校验存在数据表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    table_exists = cursor.fetchone()
    assert table_exists is not None

    # 校验生成的列
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns_in_table = [row[1] for row in cursor]
    pytest.assume(all(column in columns_in_table for column in columns_to_check))

    # 校验所有列数据每行都不为空（严格检查 NULL 值）
    cursor.execute(f"SELECT * FROM {table_name}")
    data = cursor.fetchall()
    
    # 若表为空则直接失败
    if not data:
        pytest.assume(False, f"Table {table_name} is empty")

    # 逐行检查是否存在空值（NULL）
    for row_idx, row in enumerate(data, start=1):
        # 检查每个字段是否为 None（即 SQL NULL）
        if any(field is None for field in row):
            pytest.assume(False, f"Null values detected in row {row_idx}")


def check_has_vaild_table(cursor, table_name, columns_to_check):
    # 校验存在数据表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    table_exists = cursor.fetchone()
    assert table_exists is not None

    # 校验生成的列
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns_info = cursor.fetchall()
    columns_in_table = [col[1] for col in columns_info]  # 提取列名
    pytest.assume(
        all(column in columns_in_table for column in columns_to_check),
        f"Missing required columns in {table_name}"
    )

    # 构建列名到索引的映射 {列名: 列位置}
    column_indices = {col[1]: col[0] for col in columns_info}

    # 仅查询目标列并检查空值
    query_columns = ", ".join(columns_to_check)
    cursor.execute(f"SELECT {query_columns} FROM {table_name}")
    data = cursor.fetchall()

    # 检查至少有一行所有目标列不为空
    for row in data:
        if all(field is not None for field in row):
            return  # 找到有效行，校验通过

    pytest.assume(False, f"No rows with all non-null values in columns: {columns_to_check}")


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


def check_insight_table(output_path):
    # 校验db文件正常生成
    db_path = os.path.join(output_path, 'profiler.db')
    assert os.path.exists(db_path)

    # 校验Insight中table名称及列
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 校验trace图可视化数据
    check_has_vaild_table(cursor, 'counter', ['id', 'name', 'pid', 'args', 'timestamp'])
    check_has_vaild_table(cursor, 'flow', ['id', 'flow_id', 'name', 'cat', 'timestamp', 'track_id', 'type'])
    check_has_vaild_table(cursor, 'process', ['pid', 'process_name', 'process_sort_index'])
    check_has_vaild_table(cursor, 'slice', ['id', 'timestamp', 'duration', 'name', 'track_id', 'args', 'end_time'])
    check_has_vaild_table(cursor, 'thread', ['tid', 'pid', 'thread_name', 'track_id'])

    # 校验纯表数据
    check_table_with_no_empty_data(cursor, 'batch', ['name', 'res_list', 'batch_size', 'batch_type'])
    check_table_with_no_empty_data(cursor, 'batch_exec', ['batch_id', 'name', 'pid', 'start', 'end'])
    check_table_with_no_empty_data(cursor, 'batch_req', ['req_id', 'iter', 'rid', 'block', 'batch_id'])
    check_has_vaild_table(cursor, 'request', ['http_rid', 'recv_token_size', 'reply_token_size'])
    check_table_with_no_empty_data(cursor, 'data_table', ['id', 'name', 'view_name'])

    # 关闭连接
    conn.close()


def check_insight_views(output_path):
    # 校验db文件正常生成
    db_path = os.path.join(output_path, 'profiler.db')
    assert os.path.exists(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 校验table中是否包含下述views
    for view in CURVE_VIEW_NAME_LIST.values():
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name=?", (view,))
        assert cursor.fetchone() is not None, f"View {view} does not exist"

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
    pytest.assume(not missing_columns, f"Table {context} is missing columns: {missing_columns}")


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
        pytest.assume(key in text, "The chrome_tracing.json should include NPU Usage.")


def parse_message(message: str) -> dict:
    pattern = r"\^([^^]+)\^:(\^?.*?\^?)(?=\^|,|}|$)"
    matches = re.findall(pattern, message)
    return {
        k: v.strip('^').rstrip(',')
        for k, v in matches
    }


def collect_db_stats(root_dir: str, fields: List[str], table_name: str) -> Dict[str, Dict]:
    results = {}
    grand_total = defaultdict(int)

    # 查找PROF目录
    prof_dirs = [
        d.rstrip(os.sep)
        for d in glob.glob(os.path.join(root_dir, "**/PROF_*/"), recursive=True)
        if os.path.isdir(d)
    ]
    assert prof_dirs, f"No PROF directories found under root directory | path={root_dir}"

    for prof_dir in prof_dirs:
        dir_name = os.path.basename(prof_dir)
        db_path = get_db_path(prof_dir)

        # 处理单个数据库
        conn = sqlite3.connect(db_path)
        try:
            validate_table(conn, table_name)
            counter, kvcache_count = process_database_messages(conn, table_name, fields, grand_total)
            results[dir_name] = {
                "db_path": db_path,
                "counts": dict(counter),
                "KVCache": kvcache_count,
                "total_records": sum(counter.values()) + kvcache_count,
                "_status": "success"
            }
        finally:
            conn.close()

    return {**results, "_total": dict(grand_total)}


def get_db_path(prof_dir: str) -> str:
    """验证数据库路径"""
    db_path = os.path.join(prof_dir, "host", "sqlite", "msproftx.db")
    assert os.path.isfile(db_path), f"Database file missing | path={db_path}"
    return db_path


def validate_table(conn: sqlite3.Connection, table_name: str) -> None:
    """验证表结构"""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    db_fields = [col[1] for col in cursor.fetchall()]
    assert "message" in db_fields, "Table {table_name} is missing message field"


def process_database_messages(
        conn: sqlite3.Connection,
        table_name: str,
        fields: List[str],
        grand_total: defaultdict
) -> tuple[defaultdict, int]:

    counter = defaultdict(int)
    kvcache_count = 0

    cursor = conn.execute(f"SELECT message FROM {table_name}")
    for row in cursor:
        parsed = parse_message(row[0])
        name_value = parsed.get("name", "").strip()

        # 统计目标字段
        if name_value in fields:
            counter[name_value] += 1
            grand_total[name_value] += 1

        # 统计KVCache
        if parsed.get('domain') == 'KVCache':
            kvcache_count += 1
            grand_total['KVCache'] += 1

    return counter, kvcache_count


class TestAnalyzeCmd():

    @staticmethod
    def check_batch_data_csv_integrity(output_path):
        # 校验该路径下是否正确生成batch_data的csv文件，以及文件内容
        csv_file_path = f"{output_path}/batch.csv"
        assert os.path.isfile(csv_file_path), f"File is not exist: {csv_file_path}"
        df = pd.read_csv(csv_file_path)
        # 检查文件是否为空
        assert len(df) > 0, "The data of batch csv is empty."
        expected_header = ['name', 'res_list', 'start_time(ms)', 'end_time(ms)', 'batch_size', \
                           'batch_type', 'during_time(ms)']

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
        for row_index in rows_to_check:
            assert is_valid_res_list(df.iloc[row_index]['res_list']), f"Row {row_index}, column 'res_list': invalid format."

    @staticmethod
    def check_req_data_csv_integrity(output_path):
        # 校验该路径下是否正确生成req_data的csv文件，以及文件内容
        csv_file_path = f"{output_path}/request.csv"
        assert os.path.isfile(csv_file_path), "File is not exist".format(csv_file_path)
        df = pd.read_csv(csv_file_path)
        assert len(df) > 0, "The data of req csv is empty."

        expected_header = ['http_rid', 'start_time(ms)', 'recv_token_size', 'reply_token_size', \
                           'execution_time(ms)', 'queue_wait_time(ms)']
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
                    raise AssertionError(f"Row {row_index}, column {column}: not an integer.")

        # 检查execution_time(ms)列有数据行
        rows_to_check = df[df['execution_time(ms)'].notna()]
        columns_to_check = ['recv_token_size', 'reply_token_size']
        for row_index, _ in rows_to_check.iterrows():
            for column in columns_to_check:
                check_row(df, row_index, [column])

    @staticmethod
    def _validate_db_consistency(input_path, output_path):
        """数据库与CSV总值一致性校验"""

        # 统计数据库总值
        db_stats = collect_db_stats(
            root_dir=input_path,
            fields=["modelExec", "BatchSchedule", "batchFrameworkProcessing", "KVCache"],
            table_name="MsprofTxEx",
        )
        db_total = db_stats.get("_total", {})

        validation_rules = [
            # batch.csv 校验
            {
                "db_field": "modelExec",
                "csv_path": os.path.join(output_path, "batch.csv"),
                "csv_column": "name",
                "match_value": "modelExec"
            },
            {
                "db_field": "BatchSchedule",
                "csv_path": os.path.join(output_path, "batch.csv"),
                "csv_column": "name",
                "match_value": "BatchSchedule"
            },
            {
                "db_field": "batchFrameworkProcessing",
                "csv_path": os.path.join(output_path, "batch.csv"),
                "csv_column": "name",
                "match_value": "batchFrameworkProcessing"
            },
            # kvcache.csv 校验
            {
                "db_field": "KVCache",
                "csv_path": os.path.join(output_path, "kvcache.csv"),
                "csv_column": "device_kvcache_left",
                "match_value": None # 统计行数
            }
        ]

        # 统一校验逻辑
        failures = []
        for rule in validation_rules:
            db_count = db_total.get(rule["db_field"], 0)
            csv_count = TestAnalyzeCmd._validate_csv_count(
                csv_path=rule["csv_path"],
                column=rule["csv_column"],
                match_value=rule["match_value"]
            )

            if db_count != csv_count:
                msg = f"Count mismatch for {rule['db_field']}: DB={db_count} vs CSV={csv_count}"
                failures.append(msg)

        check.is_false(failures, "\n".join(failures))


    @staticmethod
    def _validate_csv_count(csv_path: str, column: str, match_value: str = None) -> int:
        """通用CSV校验方法"""
        check.is_true(
            os.path.exists(csv_path),
            f"CSV file does not exist | path={csv_path}"
        )

        try:
            df = pd.read_csv(csv_path)
            check.is_in(
                column,
                df.columns,
                f"CSV file is missing column | path={csv_path} column={column}"
            )

            # 匹配值计数 or 总行数
            if match_value is not None:
                return len(df[df[column] == match_value])
            return len(df)

        except Exception as e:
            pytest.fail(f"Failed to read CSV file | path={csv_path} error={str(e)}")


def test_prase_ms_service_profiler_data(smoke_args, tmp_workspace):
    # 校验msserviceprofiler打点采集数据解析功能是否正常解析，校验输出文件及内容
    input_path = os.path.join(smoke_args.get("workspace"), "smokedata/analyze/latest_PD_competition")
    output_path = tmp_workspace
    parser = ExecParse()
    parser.set_input_path(input_path)
    parser.set_output_path(output_path)
    assert parser.ready_go()
    # 新增数据库字段校验子测试
    if not glob.glob(os.path.join(input_path, "**ms_service_*.db"), recursive=True):
        with check("Validate DB field consistency across PROF directories"):
            TestAnalyzeCmd._validate_db_consistency(input_path, output_path)
    # 校验输出文件是否存在
    with check:
        TestAnalyzeCmd.check_req_data_csv_integrity(output_path)
    with check:
        TestAnalyzeCmd.check_batch_data_csv_integrity(output_path)

    # kvcache校验
    with check("Check kvcache CSV content"):
        check_kvcache_csv_content(output_path, "kvcache.csv")
    with check("Check kvcache DB content"):
        check_kvcache_db_content(output_path, "profiler.db")

    # 校验时延数据生成
    with check:
        check_latency_data(output_path)

    # 校验Insight可视化数据生成
    with check:
        check_insight_table(output_path)
        check_insight_views(output_path)

    # 校验请求状态数的数据生成
    with check:
        check_req_status(output_path)

    # 校验chrome_tracing的数据格式
    with check:
        check_chrome_tracing_valid(output_path)

    # 校验chrome_tracing的数据内容
    with check:
        check_chrome_tracing_content_valid(output_path)


def test_parse_data_in_pd_separate(smoke_args, tmp_workspace):
    # 校验msserviceprofiler打点PD分离数据解析功能是否正常解析，校验输出文件及内容
    
    input_path = os.path.join(smoke_args.get("workspace"), "smokedata//analyze/latest_PD_split")
    output_path = tmp_workspace
    parser = ExecParse()
    parser.set_input_path(input_path)
    parser.set_output_path(output_path)
    assert parser.ready_go()
    
    with check("Check pullkvcache csv content"):
        check_pullkvcache_csv_content(os.path.join(output_path, "pd_split_kvcache.csv"))

    with check("Check pdSplitCommunication csv content"):
        check_communication_csv_content(os.path.join(output_path, "pd_split_communication.csv"))