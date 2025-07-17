import unittest
import os
import shutil
from datetime import datetime, timezone
import json
import sqlite3
from collections import defaultdict
import logging
import glob
import yaml
from typing import Dict, List
import re
import pandas as pd
from jsonschema import validate, ValidationError
from test.st.utils import execute_cmd
import pytest
from ms_service_profiler.exporters.utils import CURVE_VIEW_NAME_LIST

# 获取当前脚本所在的目录
script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)


def create_directory_with_timestamp(home_dir):
    # 获取当前时间戳
    timestamp = datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')

    # 构建目录路径
    directory_path = os.path.join(home_dir, f'test_dir_{timestamp}')

    # 检查目录是否已存在
    if os.path.exists(directory_path):
        print(f"目录 {directory_path} 已存在，正在删除...")
        shutil.rmtree(directory_path)

    # 创建目录
    os.makedirs(directory_path)
    print(f"目录 {directory_path} 创建成功")
    return directory_path


def update_json(file_path, keys, value):
    """
    更新 JSON 文件中指定键的值，并将更新后的 JSON 写回原文件。

    :param file_path: JSON 文件的路径
    :param keys: 键列表，表示不同层级的键
    :param value: 要设置的新值
    """
    # 读取 JSON 文件
    with open(file_path, 'r') as file:
        data = json.load(file)

    current = data
    for key in keys[:-1]:
        if key in current and isinstance(current[key], dict):
            current = current[key]
        else:
            raise KeyError(f"Key {key} not found or does not point to a dictionary")

    final_key = keys[-1]
    if final_key in current:
        current[final_key] = value
    else:
        raise KeyError(f"Key {final_key} not found")

    # 将更新后的 JSON 写回文件
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)


def check_table_header_in_directory(directory, table_name, required_columns):
    """
    检查指定目录下所有 SQLite 数据库文件中的表头是否与要求完全一致。

    :param directory: 目录路径
    :param table_name: 表名
    :param required_columns: 必需的列名列表
    :return: 如果所有数据库文件中的表头都与要求完全一致，返回 True；否则返回 False
    """
    print(f"Checking directory {directory} ...")

    # 获取目录下所有 .db 文件
    db_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.db')]

    for db_file in db_files:
        if not check_table_header(db_file, table_name, required_columns):
            return False

    return True


def check_table_header(db_file, table_name, required_columns):
    """
    检查 SQLite 数据库文件中的表头是否与要求完全一致。

    :param db_file: 数据库文件路径
    :param table_name: 表名
    :param required_columns: 必需的列名列表
    :return: 如果所有必需的列都存在且与表中的列完全一致，返回 True；否则返回 False
    """
    print(f"Checking {db_file} ...")
    # 连接到 SQLite 数据库
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    try:
        # 获取表的列信息
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()

        # 提取列名
        existing_columns = [column[1] for column in columns]

        # 检查所有必需的列是否与表中的列完全一致
        if set(required_columns) == set(existing_columns):
            return True
        else:
            missing_columns = set(required_columns) - set(existing_columns)
            extra_columns = set(existing_columns) - set(required_columns)
            if missing_columns:
                print(f"Columns {missing_columns} are missing in table '{table_name}' in {db_file}")
            if extra_columns:
                print(f"Columns {extra_columns} are extra in table '{table_name}' in {db_file}")
            return False

    finally:
        # 关闭数据库连接
        conn.close()


def get_ip_address_for_request(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    ip = str(data['ServerConfig']['ipAddress'])
    port = str(data['ServerConfig']['port'])
    ip_address = f"{ip}:{port}/infer"
    return ip_address


def get_args_from_yaml(yaml_path):
    # 打开并读取YAML文件
    with open(yaml_path, 'r') as file:
        config = yaml.safe_load(file)

    # 获取特定的参数
    service_config = config.get('service_config', '')
    profiler_so = config.get('profiler_so', '')
    return service_config, profiler_so


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


def parse_message(message: str) -> dict:
    pattern = r"\^([^^]+)\^:(\^?.*?\^?)(?=\^|,|}|$)"
    matches = re.findall(pattern, message)
    return {
        k: v.strip('^').rstrip(',')
        for k, v in matches
    }


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


def collect_db_stats(root_dir, fields, table_name):
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


def check_chrome_tracing_content_valid(output_path):
    trace_view_json = glob.glob(f"{output_path}/chrome_tracing.json")[0]
    assert os.path.exists(trace_view_json)

    with open(trace_view_json, 'r', encoding='utf-8') as f:
        text = f.read()
    exist = ["NPU Usage"]
    for key in exist:
        pytest.assume(key in text, "The chrome_tracing.json should include NPU Usage.")


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


class TestPdCompetition(unittest.TestCase):
    ANALYZE_PROFILER = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")),
                                    "ms_service_profiler/parse.py")
    INPUT_PATH = create_directory_with_timestamp("/home")
    OUTPUT_PATH = "/data/ms_service_profiler/output/analyze"
    FORMAT = ['csv', 'json', 'db']
    KVCACHE_CSV_FILE_NAME = "kvcache.csv"
    DB_FILE_NAME = "profiler.db"

    def _validate_csv_count(self, csv_path: str, column: str, match_value: str = None) -> int:
        """通用CSV校验方法"""
        self.assertTrue(
            os.path.exists(csv_path),
            f"CSV file does not exist | path={csv_path}"
        )

        try:
            df = pd.read_csv(csv_path)
            self.assertIn(
                column,
                df.columns,
                f"CSV file is missing column | path={csv_path} column={column}"
            )

            # 匹配值计数 or 总行数
            if match_value is not None:
                return len(df[df[column] == match_value])
            return len(df)

        except Exception as e:
            raise self.failureException(f"Failed to read CSV file | path={csv_path} error={str(e)}")

    def _validate_db_consistency(self):
        """数据库与CSV总值一致性校验"""

        # 统计数据库总值
        db_stats = collect_db_stats(
            root_dir=self.INPUT_PATH,
            fields=["modelExec", "BatchSchedule", "batchFrameworkProcessing", "KVCache"],
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
            {
                "db_field": "batchFrameworkProcessing",
                "csv_path": os.path.join(self.OUTPUT_PATH, "batch.csv"),
                "csv_column": "name",
                "match_value": "batchFrameworkProcessing"
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
                msg = f"Count mismatch for {rule['db_field']}: DB={db_count} vs CSV={csv_count}"
                failures.append(msg)

        if failures:
            self.fail("\n".join(failures))
        else:
            self.assertTrue(True, "All data is consistent.")

    def check_req_data_csv_integrity(self):
        # 校验该路径下是否正确生成req_data的csv文件，以及文件内容
        csv_file_path = f"{self.OUTPUT_PATH}/request.csv"
        self.assertTrue(os.path.isfile(csv_file_path), "File is not exist".format(csv_file_path))
        df = pd.read_csv(csv_file_path)
        self.assertNotEqual(len(df), 0, msg="The data of req csv is empty.")

        expected_header = ['http_rid', 'start_time(ms)', 'recv_token_size', 'reply_token_size', \
                           'execution_time(ms)', 'queue_wait_time(ms)']
        check_column(df.columns.tolist(), expected_header, context='request.csv')
        # 检查是否有多余空行
        check_no_empty_lines_before_first_line(df, context='request.csv')
        check_no_empty_lines_between_first_last_line(df, context='request.csv')

    def check_batch_data_csv_integrity(self):
        # 校验该路径下是否正确生成batch_data的csv文件，以及文件内容
        csv_file_path = f"{self.OUTPUT_PATH}/batch.csv"
        self.assertTrue(os.path.isfile(csv_file_path), f"File is not exist: {csv_file_path}")
        df = pd.read_csv(csv_file_path)
        # 检查文件是否为空
        self.assertNotEqual(len(df), 0, "The data of batch csv is empty.")
        expected_header = ['name', 'res_list', 'start_time(ms)', 'end_time(ms)', 'batch_size', \
                           'batch_type', 'during_time(ms)']



    def test_example(self):
        service_config, profiler_so = get_args_from_yaml(os.path.join(script_dir, "collect_analyze_st_args.yaml"))

        ip_address = get_ip_address_for_request(service_config)

        execute_cmd(['bash', os.path.join(script_dir, "utils", "start_mindie_service.sh"), service_config, self.INPUT_PATH, profiler_so])

        update_json(os.path.join(self.INPUT_PATH, "profiler.json"), ["enable"], 1)

        execute_cmd(['bash', os.path.join(script_dir, "utils", "send_single_request.sh"), ip_address])

        os.makedirs(self.OUTPUT_PATH, mode=0o750, exist_ok=True)

        execute_cmd(["python", self.ANALYZE_PROFILER, "--input-path", self.INPUT_PATH, "--output-path", self.OUTPUT_PATH,
               "--format", *self.FORMAT])

        if not glob.glob(os.path.join(self.INPUT_PATH, "**ms_service_*.db"), recursive=True):
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

        # 校验Insight可视化数据生成
        with self.subTest():
            check_insight_table(self.OUTPUT_PATH)
            check_insight_views(self.OUTPUT_PATH)

        # 校验请求状态数的数据生成
        with self.subTest():
            check_req_status(self.OUTPUT_PATH)

        # 校验chrome_tracing的数据格式
        with self.subTest():
            check_chrome_tracing_valid(self.OUTPUT_PATH)

        # 校验chrome_tracing的数据内容
        with self.subTest():
            check_chrome_tracing_content_valid(self.OUTPUT_PATH)




if __name__ == '__main__':
    unittest.main()


